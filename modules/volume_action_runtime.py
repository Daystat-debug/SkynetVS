"""HWA02-B2 typed volume runtime bridge over the HWA02-A action boundary.

Only VOLUME_UP and VOLUME_DOWN are registered. Trusted composition captures the
configured volume step and the history-only callback. Command/model data receives
only a scoped VolumeAutomaticPort. A prepared plan is immutable data, not
authority; every execution gets a fresh one-shot grant. Failure diagnostics and
observed audio state are bounded local receipts. This remains a cooperative
same-process Python boundary, not an OS sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
import threading
import uuid
from typing import Callable

from modules.action_contract import (
    ActionContractError, ActionRequest, ActionResult, ActionSpec, ActionStatus,
    ActionRiskClass, ActionEffectClass, ParameterRule, EffectState,
    ExecutorOutcome, ExecutorStatus, ActionVerification, VerificationStatus,
)
from modules.action_authority import ActionAuthorityError
from modules.action_broker import ExecutorRegistration, compose_action_boundary
from modules.action_error import ActionExecutionError, DEFAULT_ACTION_FAILURE_MESSAGE

VOLUME_INTENTS = frozenset({"VOLUME_UP", "VOLUME_DOWN"})


class _LocalOnly:
    __slots__ = ()
    def __copy__(self):
        raise TypeError("process_local_volume_capability")
    def __deepcopy__(self, memo):
        raise TypeError("process_local_volume_capability")
    def __reduce_ex__(self, protocol):
        raise TypeError("process_local_volume_capability")


class FailureKind(Enum):
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNEXPECTED = "UNEXPECTED"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True, slots=True)
class VolumeRepeatRecord:
    intent: str
    slots: tuple = ()


@dataclass(frozen=True, slots=True)
class PreparedVolumeAction:
    request: ActionRequest
    repeat_record: VolumeRepeatRecord


@dataclass(frozen=True, slots=True)
class _FailureReceipt:
    attempt_tag: object
    request_fp: str
    policy_fp: str
    action: str
    failure: FailureKind


@dataclass(frozen=True, slots=True)
class _SuccessReceipt:
    attempt_tag: object
    request_fp: str
    policy_fp: str
    action: str
    volume: int
    muted: bool


@dataclass(slots=True)
class _Attempt:
    tag: object
    request_bytes: bytes
    request_fp: str
    policy_fp: str
    action: str
    entered: bool = False
    success_outcome: ExecutorOutcome | None = None
    failure: _FailureReceipt | None = None
    success: _SuccessReceipt | None = None


class _ReceiptBox:
    __slots__ = ("active",)
    def __init__(self):
        self.active: _Attempt | None = None


def _check(condition: bool, code: str) -> None:
    if not condition:
        raise ActionContractError(code)


def _make_specs(step: int) -> tuple[ActionSpec, ActionSpec]:
    _check(type(step) is int and 1 <= step <= 100, "volume_step")
    common = dict(
        version=1,
        executor_id="hwa02b2.legacy_audio",
        policy_revision="hwa02b2-current-default-endpoint-refresh-v1",
        risk=ActionRiskClass.REVERSIBLE,
        effect=ActionEffectClass.HOST_UI,
        max_grant_ms=5000,
        max_execution_ms=3000,
    )
    up = ActionSpec(
        action="VOLUME_UP",
        parameters=(ParameterRule("delta", "integer", minimum=step, maximum=step),),
        **common,
    )
    down = ActionSpec(
        action="VOLUME_DOWN",
        parameters=(ParameterRule("delta", "integer", minimum=-step, maximum=-step),),
        **common,
    )
    return up, down


def _spec_for(request: ActionRequest, specs: tuple[ActionSpec, ActionSpec]) -> ActionSpec:
    _check(type(request) is ActionRequest, "request_exact_type")
    request.validate()
    spec = next((s for s in specs if s.action == request.action), None)
    _check(spec is not None, "volume_action_not_supported")
    spec.check_request(request)
    return spec


def _normalise_failure(error: ActionExecutionError, request: ActionRequest) -> FailureKind:
    if type(error) is not ActionExecutionError or error.intent != request.action:
        return FailureKind.UNCLASSIFIED
    if error.operation != "audio_control.change_volume":
        return FailureKind.UNCLASSIFIED
    return {
        "audio_control_unavailable": FailureKind.UNAVAILABLE,
        "audio_control_failed": FailureKind.FAILED,
        "audio_control_invalid_request": FailureKind.INVALID_REQUEST,
        "audio_control_unexpected_error": FailureKind.UNEXPECTED,
    }.get(error.error_code, FailureKind.UNCLASSIFIED)


def _validate_observed_state(value: object) -> tuple[int, bool]:
    _check(type(value) is tuple and len(value) == 2, "volume_state_shape")
    volume, muted = value
    _check(type(volume) is int and 0 <= volume <= 100, "volume_state_value")
    _check(type(muted) is bool, "volume_state_muted")
    return volume, muted


class _Executor:
    __slots__ = ("box", "change", "specs")
    def __init__(
        self,
        box: _ReceiptBox,
        change: Callable[[str, int], tuple[int, bool]],
        specs: tuple[ActionSpec, ActionSpec],
    ):
        self.box, self.change, self.specs = box, change, specs

    def execute(self, request: ActionRequest, *, deadline_ns: int) -> ExecutorOutcome:
        spec = _spec_for(request, self.specs)
        state = self.box.active
        _check(state is not None and not state.entered, "attempt_absent_or_used")
        _check(request.to_bytes() == state.request_bytes, "attempt_request_mismatch")
        _check(state.policy_fp == spec.fingerprint(), "attempt_policy_mismatch")
        state.entered = True
        delta = dict(request.parameters)["delta"]
        try:
            observed = self.change(request.action, delta)
        except ActionExecutionError as error:
            if type(error) is not ActionExecutionError:
                raise RuntimeError("non_exact_structured_error") from None
            state.failure = _FailureReceipt(
                state.tag, state.request_fp, state.policy_fp,
                request.action, _normalise_failure(error, request),
            )
            return ExecutorOutcome(ExecutorStatus.FAILED)
        volume, muted = _validate_observed_state(observed)
        outcome = ExecutorOutcome(
            ExecutorStatus.SUCCEEDED,
            (("muted", muted), ("volume", volume)),
        )
        state.success = _SuccessReceipt(
            state.tag, state.request_fp, state.policy_fp,
            request.action, volume, muted,
        )
        state.success_outcome = outcome
        return outcome


class _Verifier:
    __slots__ = ("box", "specs")
    def __init__(self, box: _ReceiptBox, specs: tuple[ActionSpec, ActionSpec]):
        self.box, self.specs = box, specs

    def verify(self, request: ActionRequest, outcome: ExecutorOutcome) -> ActionVerification:
        spec = _spec_for(request, self.specs)
        attempt = self.box.active
        receipt = attempt.success if attempt is not None else None
        expected_output = ()
        if type(receipt) is _SuccessReceipt:
            expected_output = (("muted", receipt.muted), ("volume", receipt.volume))
        accepted = (
            attempt is not None
            and attempt.entered
            and attempt.request_bytes == request.to_bytes()
            and attempt.policy_fp == spec.fingerprint()
            and attempt.failure is None
            and type(receipt) is _SuccessReceipt
            and receipt.attempt_tag is attempt.tag
            and receipt.request_fp == request.fingerprint()
            and receipt.policy_fp == spec.fingerprint()
            and receipt.action == request.action
            and attempt.success_outcome is outcome
            and outcome.status is ExecutorStatus.SUCCEEDED
            and outcome.output == expected_output
        )
        return ActionVerification(
            request.fingerprint(), spec.fingerprint(), outcome.fingerprint(),
            VerificationStatus.VERIFIED if accepted else VerificationStatus.REJECTED,
        )


class _State:
    __slots__ = (
        "scope", "pid", "step", "gate", "closed", "box", "issuer", "broker",
        "specs", "remember",
    )
    def __init__(
        self,
        step: int,
        change: Callable[[str, int], tuple[int, bool]],
        remember: Callable[[str], None],
    ):
        self.scope = uuid.uuid4().hex
        self.pid = os.getpid()
        self.step = step
        self.gate = threading.Lock()
        self.closed = threading.Event()
        self.box = _ReceiptBox()
        self.specs = _make_specs(step)
        self.remember = remember
        executor = _Executor(self.box, change, self.specs)
        verifier = _Verifier(self.box, self.specs)
        self.issuer, self.broker = compose_action_boundary(tuple(
            ExecutorRegistration(spec, executor, verifier) for spec in self.specs
        ))


def _refusal(state: _State, request: object, code: str) -> ActionResult:
    if type(request) is ActionRequest:
        try:
            spec = _spec_for(request, state.specs)
            return ActionResult(ActionStatus.DENIED, code, request.fingerprint(), spec.fingerprint())
        except (ActionContractError, TypeError, ValueError):
            pass
    return ActionResult(ActionStatus.DENIED, code)


def _dispatch(state: _State, request: object) -> tuple[ActionResult, FailureKind | None]:
    if state.pid != os.getpid():
        return _refusal(state, request, "foreign_process"), None
    if state.closed.is_set():
        return _refusal(state, request, "volume_port_closed"), None
    try:
        spec = _spec_for(request, state.specs)
        _check(request.scope_id == state.scope, "volume_scope_mismatch")
    except (ActionContractError, TypeError, ValueError):
        return _refusal(state, request, "volume_request_invalid"), None
    if not state.gate.acquire(blocking=False):
        return _refusal(state, request, "volume_port_busy"), None
    attempt = _Attempt(
        object(), request.to_bytes(), request.fingerprint(), spec.fingerprint(), request.action,
    )
    try:
        if state.closed.is_set():
            return _refusal(state, request, "volume_port_closed"), None
        state.box.active = attempt
        try:
            grant = state.issuer.issue(request, ttl_ms=5000)
        except (ActionAuthorityError, ActionContractError):
            return _refusal(state, request, "volume_grant_refused"), None
        result = state.broker.execute(request, grant)
        binding_ok = (
            type(result) is ActionResult
            and result.request_fingerprint == attempt.request_fp
            and result.policy_fingerprint == attempt.policy_fp
        )
        if not binding_ok:
            if not attempt.entered:
                return _refusal(state, request, "volume_result_binding_invalid"), None
            return ActionResult(
                ActionStatus.UNKNOWN, "volume_result_binding_invalid",
                attempt.request_fp, attempt.policy_fp,
                VerificationStatus.UNKNOWN, EffectState.MAY_HAVE_OCCURRED,
            ), None
        receipt = attempt.failure
        if (
            result.status is ActionStatus.FAILED
            and result.code == "executor_reported_failure"
            and state.box.active is attempt
            and attempt.entered
            and type(receipt) is _FailureReceipt
            and receipt.attempt_tag is attempt.tag
            and receipt.request_fp == result.request_fingerprint
            and receipt.policy_fp == result.policy_fingerprint
            and receipt.action == request.action
            and type(receipt.failure) is FailureKind
        ):
            return result, receipt.failure
        return result, None
    finally:
        state.box.active = None
        attempt.failure = None
        attempt.success = None
        attempt.success_outcome = None
        state.gate.release()


def _runtime_error(
    request: ActionRequest,
    result: ActionResult,
    failure: FailureKind | None,
) -> ActionExecutionError:
    error_code = "action_failed"
    message = DEFAULT_ACTION_FAILURE_MESSAGE
    if result.status is ActionStatus.DENIED:
        error_code = "volume_action_denied"
        message = "Команда изменения громкости отклонена."
    elif result.status is ActionStatus.UNKNOWN:
        error_code = "volume_action_unknown"
        message = "Не удалось подтвердить результат изменения громкости. Автоматического повтора не будет."
    elif failure is FailureKind.UNAVAILABLE:
        error_code = "audio_control_unavailable"
        message = "Управление звуком сейчас недоступно."
    elif failure is FailureKind.FAILED:
        error_code = "audio_control_failed"
        message = "Не получилось изменить звук."
    elif failure is FailureKind.INVALID_REQUEST:
        error_code = "volume_action_internal_error"
        message = "Не получилось выполнить проверенную команду изменения громкости."
    elif failure is FailureKind.UNEXPECTED:
        error_code = "audio_control_unexpected_error"
        message = "Не получилось изменить звук."
    return ActionExecutionError(
        intent=request.action,
        operation="audio_control.change_volume",
        detail="Bounded volume execution diagnostic",
        user_message=message,
        error_code=error_code,
        context={
            "service": "audio_control",
            "boundary": "hwa02b2",
            "request_fingerprint": request.fingerprint(),
            "broker_status": result.status.value,
            "broker_code": result.code,
            "effect": result.effect.value,
        },
    )


def _history_error(plan: PreparedVolumeAction, result: ActionResult) -> ActionExecutionError:
    return ActionExecutionError(
        intent=plan.request.action,
        operation="repeat_history.remember_volume_success",
        detail="Audio effect verified; repeat history commit failed",
        user_message="Громкость изменена, но повтор команды сохранить не удалось.",
        error_code="volume_history_commit_failed",
        context={
            "service": "repeat_history",
            "boundary": "hwa02b2",
            "request_fingerprint": plan.request.fingerprint(),
            "broker_status": result.status.value,
            "broker_code": result.code,
            "effect": result.effect.value,
            "audio_effect_verified": True,
            "history_state": "unknown",
        },
    )


class VolumeAutomaticPort(_LocalOnly):
    __slots__ = ("_state",)
    def __new__(cls):
        raise TypeError("volume_port_requires_composition")
    def __init_subclass__(cls, **kwargs):
        raise TypeError("volume_port_subclass_forbidden")

    def prepare(self, *, intent: str, slots: dict) -> PreparedVolumeAction:
        if self._state.pid != os.getpid() or self._state.closed.is_set():
            raise ActionContractError("volume_port_unavailable")
        _check(type(intent) is str and intent in VOLUME_INTENTS, "volume_intent")
        _check(type(slots) is dict and slots == {}, "volume_slots")
        delta = self._state.step if intent == "VOLUME_UP" else -self._state.step
        request = ActionRequest(
            uuid.uuid4().hex, self._state.scope, intent, 1, (("delta", delta),),
        )
        return PreparedVolumeAction(request, VolumeRepeatRecord(intent, ()))

    def execute(self, plan: PreparedVolumeAction) -> None:
        if type(plan) is not PreparedVolumeAction:
            raise ActionExecutionError(
                intent="", operation="volume.dispatch", detail="Invalid volume plan",
                user_message="Команда изменения громкости отклонена.",
                error_code="volume_action_denied",
            )
        request = plan.request
        record = plan.repeat_record
        try:
            spec = _spec_for(request, self._state.specs)
            _check(request.scope_id == self._state.scope, "volume_scope_mismatch")
            _check(type(record) is VolumeRepeatRecord, "volume_repeat_record_type")
            _check(record.intent == request.action and record.slots == (), "volume_repeat_record_mismatch")
            _check(spec.action == record.intent, "volume_repeat_record_policy_mismatch")
        except (ActionContractError, TypeError, ValueError):
            raise ActionExecutionError(
                intent=getattr(request, "action", ""),
                operation="volume.dispatch", detail="Invalid volume plan",
                user_message="Команда изменения громкости отклонена.",
                error_code="volume_action_denied",
            ) from None

        result, failure = _dispatch(self._state, request)
        if result.status is not ActionStatus.SUCCEEDED:
            raise _runtime_error(request, result, failure) from None

        try:
            self._state.remember(record.intent)
        except Exception:
            raise _history_error(plan, result) from None


class VolumeActionOwner(_LocalOnly):
    __slots__ = ("_state",)
    def __new__(cls):
        raise TypeError("volume_owner_requires_composition")
    def __init_subclass__(cls, **kwargs):
        raise TypeError("volume_owner_subclass_forbidden")
    def close(self) -> None:
        if self._state.pid != os.getpid():
            raise ActionContractError("foreign_process")
        self._state.closed.set()
        self._state.issuer.close()


def compose_volume_action_runtime(
    *,
    step: int,
    change_volume: Callable[[str, int], tuple[int, bool]],
    remember_volume_success: Callable[[str], None],
) -> tuple[VolumeActionOwner, VolumeAutomaticPort]:
    _check(type(step) is int and 1 <= step <= 100, "volume_step")
    _check(callable(change_volume) and callable(remember_volume_success), "volume_callbacks")
    state = _State(step, change_volume, remember_volume_success)
    owner = object.__new__(VolumeActionOwner)
    port = object.__new__(VolumeAutomaticPort)
    owner._state = port._state = state
    return owner, port
