"""HWA02-B1 typed timer runtime bridge over the HWA02-A action boundary.

Only SET_TIMER and CANCEL_TIMER are registered. Trusted composition owns the
issuer; command data receives only the scoped TimerAutomaticPort. Failure
diagnostics are bounded local receipts and never become authority or broker
output. This remains a cooperative same-process Python boundary, not an OS
sandbox.
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

TIMER_INTENTS = frozenset({"SET_TIMER", "CANCEL_TIMER"})
SET_SPEC = ActionSpec(
    action="SET_TIMER", version=1, executor_id="hwa02b1.legacy_timer",
    policy_revision="hwa02b1-handler-completion-v1",
    risk=ActionRiskClass.REVERSIBLE, effect=ActionEffectClass.MEMORY,
    parameters=(ParameterRule("duration_seconds", "integer", minimum=1, maximum=86400),),
    max_grant_ms=5000, max_execution_ms=1000,
)
CANCEL_SPEC = ActionSpec(
    action="CANCEL_TIMER", version=1, executor_id="hwa02b1.legacy_timer",
    policy_revision="hwa02b1-handler-completion-v1",
    risk=ActionRiskClass.REVERSIBLE, effect=ActionEffectClass.MEMORY,
    max_grant_ms=5000, max_execution_ms=1000,
)
SPECS = (SET_SPEC, CANCEL_SPEC)


class _LocalOnly:
    __slots__ = ()
    def __copy__(self):
        raise TypeError("process_local_timer_capability")
    def __deepcopy__(self, memo):
        raise TypeError("process_local_timer_capability")
    def __reduce_ex__(self, protocol):
        raise TypeError("process_local_timer_capability")


class FailureKind(Enum):
    UNAVAILABLE = "UNAVAILABLE"
    CANCEL_REPORTED = "CANCEL_REPORTED"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True, slots=True)
class _FailureReceipt:
    # There are deliberately no exception/message/detail/context fields.
    attempt_tag: object
    request_fp: str
    policy_fp: str
    action: str
    failure: FailureKind


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


class _ReceiptBox:
    __slots__ = ("active",)
    def __init__(self):
        self.active: _Attempt | None = None


def _check(condition: bool, code: str) -> None:
    if not condition:
        raise ActionContractError(code)


def _spec_for(request: ActionRequest) -> ActionSpec:
    _check(type(request) is ActionRequest, "request_exact_type")
    request.validate()
    spec = next((s for s in SPECS if s.action == request.action), None)
    _check(spec is not None, "timer_action_not_supported")
    spec.check_request(request)
    return spec


def _normalise_failure(error: ActionExecutionError, request: ActionRequest) -> FailureKind:
    # Exact tuples from current production code / existing regression fixture.
    # No arbitrary message, detail, context, or exception subclass is trusted.
    if type(error) is not ActionExecutionError or error.intent != request.action:
        return FailureKind.UNCLASSIFIED
    expected_operation = "timer.start" if request.action == "SET_TIMER" else "timer.cancel"
    if error.error_code == "timer_unavailable" and error.operation == expected_operation:
        return FailureKind.UNAVAILABLE
    if (request.action == "CANCEL_TIMER" and error.error_code == "timer_cancel_failed"
            and error.operation in ("timer.cancel", "cancel_timer")):
        return FailureKind.CANCEL_REPORTED
    return FailureKind.UNCLASSIFIED


class _Executor:
    __slots__ = ("box", "start", "cancel")
    def __init__(self, box: _ReceiptBox, start: Callable[[int], None], cancel: Callable[[], None]):
        self.box, self.start, self.cancel = box, start, cancel

    def execute(self, request: ActionRequest, *, deadline_ns: int) -> ExecutorOutcome:
        _spec_for(request)
        attempt = self.box.active
        _check(attempt is not None and not attempt.entered, "attempt_absent_or_used")
        _check(request.to_bytes() == attempt.request_bytes, "attempt_request_mismatch")
        attempt.entered = True
        try:
            if request.action == "SET_TIMER":
                returned = self.start(dict(request.parameters)["duration_seconds"])
            else:
                returned = self.cancel()
        except ActionExecutionError as error:
            if type(error) is not ActionExecutionError:
                raise RuntimeError("non_exact_structured_error") from None
            attempt.failure = _FailureReceipt(
                attempt.tag, attempt.request_fp, attempt.policy_fp,
                request.action, _normalise_failure(error, request),
            )
            return ExecutorOutcome(ExecutorStatus.FAILED)
        # Legacy _exec_* handlers return None. Other return values are not success.
        _check(returned is None, "legacy_callback_return_invalid")
        outcome = ExecutorOutcome(ExecutorStatus.SUCCEEDED)
        attempt.success_outcome = outcome
        return outcome


class _Verifier:
    __slots__ = ("box",)
    def __init__(self, box: _ReceiptBox):
        self.box = box
    def verify(self, request: ActionRequest, outcome: ExecutorOutcome) -> ActionVerification:
        spec = _spec_for(request)
        attempt = self.box.active
        accepted = (attempt is not None and attempt.entered and
                    attempt.request_bytes == request.to_bytes() and
                    attempt.policy_fp == spec.fingerprint() and
                    attempt.failure is None and attempt.success_outcome is outcome and
                    outcome.status is ExecutorStatus.SUCCEEDED and outcome.output == ())
        return ActionVerification(
            request.fingerprint(), spec.fingerprint(), outcome.fingerprint(),
            VerificationStatus.VERIFIED if accepted else VerificationStatus.REJECTED,
        )


class _State:
    __slots__ = ("scope", "pid", "gate", "closed", "box", "issuer", "broker")
    def __init__(self, start: Callable[[int], None], cancel: Callable[[], None]):
        self.scope = uuid.uuid4().hex
        self.pid = os.getpid()
        self.gate = threading.Lock()
        self.closed = threading.Event()
        self.box = _ReceiptBox()
        executor = _Executor(self.box, start, cancel)
        verifier = _Verifier(self.box)
        self.issuer, self.broker = compose_action_boundary(tuple(
            ExecutorRegistration(spec, executor, verifier) for spec in SPECS
        ))


def _refusal(request: object, code: str) -> ActionResult:
    if type(request) is ActionRequest:
        try:
            spec = _spec_for(request)
            return ActionResult(ActionStatus.DENIED, code, request.fingerprint(), spec.fingerprint())
        except (ActionContractError, TypeError, ValueError):
            pass
    return ActionResult(ActionStatus.DENIED, code)


def _dispatch(state: _State, request: object) -> tuple[ActionResult, FailureKind | None]:
    # PID is checked before taking a possibly inherited lock.
    if state.pid != os.getpid():
        return _refusal(request, "foreign_process"), None
    if state.closed.is_set():
        return _refusal(request, "timer_port_closed"), None
    try:
        spec = _spec_for(request)
        _check(request.scope_id == state.scope, "timer_scope_mismatch")
    except (ActionContractError, TypeError, ValueError):
        return _refusal(request, "timer_request_invalid"), None
    if not state.gate.acquire(blocking=False):
        return _refusal(request, "timer_port_busy"), None
    attempt = _Attempt(object(), request.to_bytes(), request.fingerprint(), spec.fingerprint(), request.action)
    try:
        if state.closed.is_set():
            return _refusal(request, "timer_port_closed"), None
        state.box.active = attempt
        try:
            grant = state.issuer.issue(request, ttl_ms=5000)
        except (ActionAuthorityError, ActionContractError):
            return _refusal(request, "timer_grant_refused"), None
        result = state.broker.execute(request, grant)
        binding_ok = (type(result) is ActionResult and
                      result.request_fingerprint == attempt.request_fp and
                      result.policy_fingerprint == attempt.policy_fp)
        if not binding_ok:
            if not attempt.entered:
                return _refusal(request, "timer_result_binding_invalid"), None
            return ActionResult(ActionStatus.UNKNOWN, "timer_result_binding_invalid", attempt.request_fp,
                                attempt.policy_fp, VerificationStatus.UNKNOWN, EffectState.MAY_HAVE_OCCURRED), None
        receipt = attempt.failure
        if (result.status is ActionStatus.FAILED and result.code == "executor_reported_failure"
                and state.box.active is attempt and attempt.entered
                and type(receipt) is _FailureReceipt and receipt.attempt_tag is attempt.tag
                and receipt.request_fp == result.request_fingerprint
                and receipt.policy_fp == result.policy_fingerprint
                and receipt.action == request.action and type(receipt.failure) is FailureKind):
            return result, receipt.failure
        return result, None
    finally:
        state.box.active = None
        attempt.failure = None
        attempt.success_outcome = None
        state.gate.release()


def _runtime_error(request: ActionRequest, result: ActionResult, failure: FailureKind | None) -> ActionExecutionError:
    operation = "timer.start" if request.action == "SET_TIMER" else "timer.cancel"
    error_code = "action_failed"
    message = DEFAULT_ACTION_FAILURE_MESSAGE
    if result.status is ActionStatus.DENIED:
        error_code, message = "timer_action_denied", "Команда таймера не выполнена: допуск отклонён."
    elif result.status is ActionStatus.UNKNOWN:
        error_code = "timer_action_unknown"
        message = "Не удалось подтвердить результат команды таймера. Автоматического повтора не будет."
    elif failure is FailureKind.UNAVAILABLE:
        error_code, message = "timer_unavailable", "Таймер сейчас недоступен."
    elif failure is FailureKind.CANCEL_REPORTED:
        error_code, message = "timer_cancel_failed", "Не получилось отменить таймер."
    return ActionExecutionError(
        intent=request.action, operation=operation, detail="Bounded timer execution diagnostic",
        user_message=message, error_code=error_code,
        context={"service": "timer", "boundary": "hwa02b1", "request_fingerprint": request.fingerprint(),
                 "broker_status": result.status.value, "broker_code": result.code, "effect": result.effect.value},
    )


class TimerAutomaticPort(_LocalOnly):
    __slots__ = ("_state",)
    def __new__(cls):
        raise TypeError("timer_port_requires_composition")
    def __init_subclass__(cls, **kwargs):
        raise TypeError("timer_port_subclass_forbidden")
    def prepare(self, *, intent: str, slots: dict) -> ActionRequest:
        if self._state.pid != os.getpid() or self._state.closed.is_set():
            raise ActionContractError("timer_port_unavailable")
        _check(type(intent) is str and intent in TIMER_INTENTS, "timer_intent")
        _check(type(slots) is dict, "timer_slots_type")
        if intent == "SET_TIMER":
            _check(set(slots) == {"duration_seconds"}, "timer_slots")
            value = slots["duration_seconds"]
            _check(type(value) is int and 1 <= value <= 86400, "timer_duration")
            params = (("duration_seconds", value),)
        else:
            _check(slots == {}, "timer_slots")
            params = ()
        return ActionRequest(uuid.uuid4().hex, self._state.scope, intent, 1, params)
    def execute(self, request: ActionRequest) -> None:
        result, failure = _dispatch(self._state, request)
        if result.status is not ActionStatus.SUCCEEDED:
            # No original exception/traceback is retained at this point.
            if type(request) is not ActionRequest or request.action not in TIMER_INTENTS:
                raise ActionExecutionError(intent="", operation="timer.dispatch", detail="Invalid timer request",
                                           user_message="Команда таймера отклонена.", error_code="timer_action_denied")
            raise _runtime_error(request, result, failure) from None


class TimerActionOwner(_LocalOnly):
    __slots__ = ("_state",)
    def __new__(cls):
        raise TypeError("timer_owner_requires_composition")
    def __init_subclass__(cls, **kwargs):
        raise TypeError("timer_owner_subclass_forbidden")
    def close(self) -> None:
        if self._state.pid != os.getpid():
            raise ActionContractError("foreign_process")
        self._state.closed.set()
        self._state.issuer.close()


def compose_timer_action_runtime(*, start_timer: Callable[[int], None], cancel_timer: Callable[[], None]
                                 ) -> tuple[TimerActionOwner, TimerAutomaticPort]:
    _check(callable(start_timer) and callable(cancel_timer), "timer_callbacks")
    state = _State(start_timer, cancel_timer)
    owner = object.__new__(TimerActionOwner)
    port = object.__new__(TimerAutomaticPort)
    owner._state = port._state = state
    return owner, port
