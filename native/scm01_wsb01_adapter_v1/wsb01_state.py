"""Deterministic model reducer. Injected timestamps; no clock, I/O or effect executor."""
from dataclasses import dataclass, replace
from enum import Enum
from .wsb01_policy import CoreError, ModelOnly, ModelResult, need
from .wsb01_contract import uint, MessageKind, parse_message
from .wsb01_ports import (RunExpectation, ModelEvent, ModelEventKind as E,
                         ModelEffectKind as F, PlannedEffect, ModelRetirementObservation,
                         ModelObservations, PostExitModelData, ArtifactBytes, TranscriptBytes)
from .wsb01_transcript import (ModelPin, pin_ready_model, authorization_bytes_model,
                              assert_pending_model, validate_transcript_model, ModelTranscriptCheck,
                              sha256)


class ModelPhase(str, Enum):
    NEW = "NEW"
    INPUTS_VALIDATED = "INPUTS_VALIDATED"
    RESERVATION_INTENT_RECORDED = "RESERVATION_INTENT_RECORDED"
    HOST_RESERVATION_CONSUMED = "HOST_RESERVATION_CONSUMED"
    LAUNCH_INTENT_RECORDED = "LAUNCH_INTENT_RECORDED"
    SESSION_BOUND = "SESSION_BOUND"
    READY_PINNED = "READY_PINNED"
    AUTHORIZATION_INTENT_RECORDED = "AUTHORIZATION_INTENT_RECORDED"
    AUTHORIZATION_PUBLISHED = "AUTHORIZATION_PUBLISHED"
    TERMINAL_PENDING_RETIREMENT = "TERMINAL_PENDING_RETIREMENT"
    NORMAL_RETIREMENT_CONFIRMED = "NORMAL_RETIREMENT_CONFIRMED"
    POST_EXIT_BYTES_VERIFIED = "POST_EXIT_BYTES_VERIFIED"
    MODEL_TRACE_VALID = "MODEL_TRACE_VALID"
    FAILED_CLOSED = "FAILED_CLOSED"
    FAILED_ACTIVE_UNKNOWN = "FAILED_ACTIVE_UNKNOWN"
    FAILED_RETIRED = "FAILED_RETIRED"


@dataclass(frozen=True)
class ModelState(ModelOnly):
    expectation: RunExpectation
    phase: ModelPhase
    last_host_ns: int
    reservation_attempted: bool = False
    reservation_confirmed: bool = False
    launch_attempted: bool = False
    authorization_attempted: bool = False
    authorization_published: bool = False
    session_bound: bool = False
    failure_sticky: bool = False
    retirement_confirmed: bool = False
    forced_cleanup: bool = False
    launcher_exited: bool = False
    pin: ModelPin | None = None
    authorization: bytes | None = None
    publication_commit: bytes | None = None
    pending_artifacts: tuple[ArtifactBytes, ...] | None = None
    retirement: ModelRetirementObservation | None = None
    transcript_check: ModelTranscriptCheck | None = None
    result: ModelResult = ModelResult.INVALID
    reason: str = ""


@dataclass(frozen=True)
class ModelTransition(ModelOnly):
    state: ModelState
    planned_effects: tuple[PlannedEffect, ...] = ()


def initial_model(expectation: RunExpectation) -> ModelState:
    need(type(expectation) is RunExpectation, "expectation_type")
    expectation.__post_init__()
    return ModelState(expectation, ModelPhase.NEW, expectation.host_started_ns)


def _effect(state, kind, digest=None):
    return PlannedEffect(kind, state.expectation.run_id, digest)


def _failed(state, reason):
    phase = (ModelPhase.FAILED_RETIRED if state.retirement_confirmed else
             ModelPhase.FAILED_ACTIVE_UNKNOWN if state.launch_attempted else ModelPhase.FAILED_CLOSED)
    failed = replace(state, phase=phase, failure_sticky=True, result=ModelResult.INVALID, reason=reason)
    return ModelTransition(failed, (_effect(failed, F.QUARANTINE_OUTPUT), _effect(failed, F.PRESERVE_EVIDENCE)))


def _valid_retirement(state, observation, forced):
    need(type(observation) is ModelRetirementObservation, "retirement_type")
    need(state.session_bound and observation.session_binding_sha256 == state.expectation.session_binding_sha256,
         "retirement_session_binding")
    need(observation.unknown is False, "retirement_unknown")
    if forced:
        need(observation.forced is True and observation.normal is False, "forced_retirement_shape")
    else:
        need(observation.normal is True and observation.forced is False, "normal_retirement_shape")


def reduce_model(state: ModelState, event: ModelEvent) -> ModelTransition:
    need(type(state) is ModelState, "state_type")
    # The reducer operates on well-formed model state; it issues no live capability.
    try:
        need(type(event) is ModelEvent and type(event.kind) is E, "event_type")
        uint(event.at_ns, label="host_tick")
        need(type(event.experiment) is type(state.expectation.experiment), "event_experiment_type")
        need(event.run_id == state.expectation.run_id and event.nonce == state.expectation.nonce and
             event.experiment is state.expectation.experiment, "event_run_or_scope")
        need(event.at_ns >= state.last_host_ns, "host_clock_regression")
        state = replace(state, last_host_ns=event.at_ns)
        # A deadline failure cannot be cleared by a later valid-looking event.
        if event.at_ns > state.expectation.host_deadline_ns and not state.failure_sticky:
            # Expiry forbids success, but must not discard a valid retirement
            # observation carried by this same event. The sticky-failure branch
            # below can record normal retirement; forced cleanup stays failure.
            state = _failed(state, "host_deadline").state
        if event.kind in (E.FAILURE, E.UNKNOWN):
            need(type(event.payload) is str and 1 <= len(event.payload) <= 128, "failure_event_code")
            return _failed(state, event.kind.value + ":" + event.payload)
        if event.kind is E.FORCED_CLEANUP:
            _valid_retirement(state, event.payload, forced=True)
            state = replace(state, forced_cleanup=True, retirement_confirmed=True, retirement=event.payload)
            return _failed(state, "forced_cleanup_never_success")
        if state.failure_sticky:
            if event.kind is E.NORMAL_RETIREMENT:
                _valid_retirement(state, event.payload, forced=False)
                state = replace(state, retirement_confirmed=True, retirement=event.payload)
            # No effect that launches, publishes or accepts is returned after any failure.
            return _failed(state, state.reason or "sticky_failure")
        if event.kind is E.TICK:
            need(event.payload is None, "tick_has_no_payload")
            return ModelTransition(state)
        if event.kind is E.LAUNCHER_EXITED:
            need(state.launch_attempted and event.payload is None, "launcher_exit_order")
            return ModelTransition(replace(state, launcher_exited=True))

        transitions = {
            E.INPUTS_VALIDATED: (ModelPhase.NEW, ModelPhase.INPUTS_VALIDATED),
            E.RESERVATION_INTENT: (ModelPhase.INPUTS_VALIDATED, ModelPhase.RESERVATION_INTENT_RECORDED),
            E.RESERVATION_CONFIRMED: (ModelPhase.RESERVATION_INTENT_RECORDED, ModelPhase.HOST_RESERVATION_CONSUMED),
            E.LAUNCH_INTENT: (ModelPhase.HOST_RESERVATION_CONSUMED, ModelPhase.LAUNCH_INTENT_RECORDED),
            E.SESSION_BOUND: (ModelPhase.LAUNCH_INTENT_RECORDED, ModelPhase.SESSION_BOUND),
            E.READY_RECEIVED: (ModelPhase.SESSION_BOUND, ModelPhase.READY_PINNED),
            E.AUTHORIZATION_INTENT: (ModelPhase.READY_PINNED, ModelPhase.AUTHORIZATION_INTENT_RECORDED),
            E.AUTHORIZATION_PUBLISHED: (ModelPhase.AUTHORIZATION_INTENT_RECORDED, ModelPhase.AUTHORIZATION_PUBLISHED),
            E.TERMINAL_RECEIVED: (ModelPhase.AUTHORIZATION_PUBLISHED, ModelPhase.TERMINAL_PENDING_RETIREMENT),
            E.NORMAL_RETIREMENT: (ModelPhase.TERMINAL_PENDING_RETIREMENT, ModelPhase.NORMAL_RETIREMENT_CONFIRMED),
            E.POST_EXIT_BYTES: (ModelPhase.NORMAL_RETIREMENT_CONFIRMED, ModelPhase.POST_EXIT_BYTES_VERIFIED),
            E.FINALIZE: (ModelPhase.POST_EXIT_BYTES_VERIFIED, ModelPhase.MODEL_TRACE_VALID),
        }
        need(event.kind in transitions, "unknown_transition")
        before, after = transitions[event.kind]
        need(state.phase is before, "illegal_transition:" + state.phase.value + ":" + event.kind.value)
        effects = ()
        if event.kind is E.INPUTS_VALIDATED:
            need(event.payload is None, "inputs_payload")
            state.expectation.__post_init__()
        elif event.kind is E.RESERVATION_INTENT:
            need(event.payload is None and not state.reservation_attempted, "reservation_budget")
            state = replace(state, reservation_attempted=True)
            effects = (_effect(state, F.RESERVE_HOST_MARKER),)
        elif event.kind is E.RESERVATION_CONFIRMED:
            need(event.payload is None and state.reservation_attempted, "reservation_confirmation")
            state = replace(state, reservation_confirmed=True)
        elif event.kind is E.LAUNCH_INTENT:
            need(event.payload is None and state.reservation_confirmed and not state.launch_attempted, "launch_budget")
            state = replace(state, launch_attempted=True)
            effects = (_effect(state, F.LAUNCH_SANDBOX),)
        elif event.kind is E.SESSION_BOUND:
            need(type(event.payload) is str and event.payload == state.expectation.session_binding_sha256, "host_session_binding")
            state = replace(state, session_bound=True)
        elif event.kind is E.READY_RECEIVED:
            pin = pin_ready_model(state.expectation, event.payload)
            state = replace(state, pin=pin)
        elif event.kind is E.AUTHORIZATION_INTENT:
            need(event.payload is None and not state.authorization_attempted, "authorization_budget")
            authorization, commit = authorization_bytes_model(state.pin)
            state = replace(state, authorization_attempted=True, authorization=authorization, publication_commit=commit)
            effects = (_effect(state, F.PUBLISH_AUTHORIZATION, sha256(authorization)),)
        elif event.kind is E.AUTHORIZATION_PUBLISHED:
            need(type(event.payload) is bytes and event.payload == state.publication_commit, "publication_not_established")
            state = replace(state, authorization_published=True)
        elif event.kind is E.TERMINAL_RECEIVED:
            need(type(event.payload) is tuple, "terminal_snapshot_type")
            assert_pending_model(state.pin, state.authorization, state.publication_commit, event.payload)
            state = replace(state, pending_artifacts=event.payload)
            # assert_pending_model validated all four artifacts and their trace.
            # A valid failure transcript is still a failure now, not only when
            # POST_EXIT_BYTES arrives. Keep its bytes and await retirement under
            # the same sticky-failure rules as every other failed observation.
            terminal_raw = next(x.data for x in event.payload if x.name == "terminal.json")
            terminal = parse_message(MessageKind.TERMINAL, terminal_raw)
            if terminal.fields["result"] == ModelResult.FAILURE.value:
                return _failed(state, "terminal_reports_model_failure")
            effects = (_effect(state, F.OBSERVE_RETIREMENT),)
        elif event.kind is E.NORMAL_RETIREMENT:
            _valid_retirement(state, event.payload, forced=False)
            state = replace(state, retirement_confirmed=True, retirement=event.payload)
        elif event.kind is E.POST_EXIT_BYTES:
            need(type(event.payload) is PostExitModelData, "post_exit_type")
            snapshot = TranscriptBytes(state.authorization, state.publication_commit,
                                       state.pending_artifacts, event.payload.artifacts)
            check = validate_transcript_model(state.pin, snapshot,
                                              ModelObservations(event.payload.crypto, state.retirement))
            need(check.successful, "post_exit_or_trace_failed:" + ",".join(check.reasons))
            state = replace(state, transcript_check=check)
        elif event.kind is E.FINALIZE:
            need(event.payload is None and state.transcript_check is not None and state.transcript_check.successful,
                 "finalize_without_model_check")
            state = replace(state, result=state.transcript_check.result)
            effects = (_effect(state, F.RECORD_MODEL_ACCEPTANCE, state.transcript_check.terminal_sha256),)
        return ModelTransition(replace(state, phase=after), effects)
    except CoreError as exc:
        return _failed(state, str(exc))
