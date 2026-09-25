"""HWA02-A explicit typed dispatch; no host backend or runtime wiring.

Registry and issuer construction are trusted operations. ActionBroker() is
empty/closed. No caller-supplied import path, function name, argv or authority
boolean is interpreted. Python introspection/hostile same-process code is out
of scope; a process-local grant is not a substitute for OS confinement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from modules.action_contract import (
    ActionContractError, ActionRequest, ActionResult, ActionSpec, ActionStatus,
    ActionVerification, EffectState, ExecutorOutcome, ExecutorStatus,
    VerificationStatus, require,
)
from modules.action_authority import (
    ActionAuthority, ActionAuthorityError, ActionGrant, _Binding, _Domain,
    _LocalOnly, _issuer_for,
)


class ActionExecutor(Protocol):
    def execute(self, request: ActionRequest, *, deadline_ns: int) -> ExecutorOutcome:
        ...


class ActionVerifier(Protocol):
    def verify(self, request: ActionRequest, outcome: ExecutorOutcome) -> ActionVerification:
        ...


@dataclass(frozen=True, slots=True)
class ExecutorRegistration:
    spec: ActionSpec
    executor: ActionExecutor
    verifier: ActionVerifier


class ActionBroker(_LocalOnly):
    """Consumer role only. No issue/approve/register API is exposed."""
    __slots__ = ("_domain",)

    def __init__(self) -> None:
        self._domain = _Domain(())
        self._domain.broker = self

    def __init_subclass__(cls, **kwargs):
        raise TypeError("broker_subclass_forbidden")

    def execute(self, request: object, grant: object = None) -> ActionResult:
        """At most one dispatch per grant. Synchronous callback: no hard timeout."""
        request_fp = ""
        policy_fp = ""
        try:
            claim = self._domain.claim(grant, self)
            request_fp = claim.request_fingerprint
            policy_fp = claim.binding.policy_fingerprint
            binding = self._domain.resolve(request)
            require(request.to_bytes() == claim.request_bytes, "request_mismatch")
            require(binding is claim.binding, "executor_binding_mismatch")
            deadline_ns = self._domain.before_dispatch(claim, self)
        except (ActionAuthorityError, ActionContractError) as exc:
            return ActionResult(ActionStatus.DENIED, str(exc), request_fp, policy_fp)
        except Exception:
            return ActionResult(ActionStatus.DENIED, "admission_error", request_fp, policy_fp)

        def unknown(code: str, verification: VerificationStatus = VerificationStatus.UNKNOWN) -> ActionResult:
            return ActionResult(ActionStatus.UNKNOWN, code, request_fp, policy_fp,
                                verification, EffectState.MAY_HAVE_OCCURRED)

        # Claim has been removed; no retry path even after a callback exception.
        try:
            outcome = binding.execute(request, deadline_ns=deadline_ns)
        except Exception:
            return unknown("executor_exception")
        try:
            require(type(outcome) is ExecutorOutcome, "outcome_type")
            outcome.validate()
            if self._domain.now() >= deadline_ns:
                return unknown("execution_deadline")
            if outcome.status is ExecutorStatus.FAILED:
                return ActionResult(ActionStatus.FAILED, "executor_reported_failure", request_fp,
                                    policy_fp, VerificationStatus.NOT_RUN, EffectState.MAY_HAVE_OCCURRED)
            outcome_fp = outcome.fingerprint()
        except Exception:
            return unknown("executor_result_invalid")
        try:
            evidence = binding.verify(request, outcome)
        except Exception:
            return unknown("verifier_exception")
        try:
            require(type(evidence) is ActionVerification, "verification_type")
            evidence.validate()
            require(request.to_bytes() == claim.request_bytes and
                    binding.spec.fingerprint() == policy_fp and
                    outcome.fingerprint() == outcome_fp, "post_dispatch_data_changed")
            require(evidence.request_fingerprint == request_fp and
                    evidence.policy_fingerprint == policy_fp and
                    evidence.outcome_fingerprint == outcome_fp, "verification_binding")
            if self._domain.now() >= deadline_ns:
                return unknown("verification_deadline")
            if evidence.status is not VerificationStatus.VERIFIED:
                return unknown("verification_not_accepted", evidence.status)
        except Exception:
            return unknown("verification_invalid")
        return ActionResult(ActionStatus.SUCCEEDED, "verified", request_fp, policy_fp,
                            VerificationStatus.VERIFIED, EffectState.VERIFIED, outcome.output)


def compose_action_boundary(
    registrations: tuple[ExecutorRegistration, ...] = (),
) -> tuple[ActionAuthority, ActionBroker]:
    """Trusted composition ONLY. Keep issuer away from command/model/executor code.

    No production caller is added in HWA02-A. Each invocation creates a separate
    domain, not access to an existing broker. Registrations are fixed for its
    lifetime. Executor/verifier objects and bound methods are captured once.
    """
    require(type(registrations) is tuple and len(registrations) <= 128, "registry_type_or_size")
    bindings = []
    keys = set()
    executor_ids = {}
    for registration in registrations:
        require(type(registration) is ExecutorRegistration, "registration_type")
        spec = registration.spec
        require(type(spec) is ActionSpec, "spec_exact_type")
        spec.validate()
        key = (spec.action, spec.version)
        require(key not in keys, "duplicate_action")
        keys.add(key)
        execute = getattr(registration.executor, "execute", None)
        verify = getattr(registration.verifier, "verify", None)
        require(callable(execute) and callable(verify), "executor_or_verifier_missing")
        if spec.executor_id in executor_ids:
            require(executor_ids[spec.executor_id] is registration.executor, "executor_id_collision")
        executor_ids[spec.executor_id] = registration.executor
        bindings.append(_Binding(spec, spec.fingerprint(), registration.executor,
                                 registration.verifier, execute, verify))
    domain = _Domain(tuple(bindings))
    broker = object.__new__(ActionBroker)
    broker._domain = domain
    domain.broker = broker
    return _issuer_for(domain), broker
