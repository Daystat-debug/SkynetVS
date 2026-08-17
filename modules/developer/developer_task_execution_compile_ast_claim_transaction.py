from __future__ import annotations

"""V1C2C0 host-only process-local plan/runtime claim transaction capability."""

import hashlib
import hmac
import json
import secrets
import threading
import time
import weakref

from dataclasses import dataclass, field
from typing import Any

from modules.developer.developer_task_execution_compile_ast_claim_transaction_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_BINDING_NONCE_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_CLOCK_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_FINGERPRINT_ALGORITHM,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_SECRET_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_TTL_SECONDS,
    validate_developer_task_execution_compile_ast_claim_transaction_policy,
)
from modules.developer.developer_task_execution_compile_ast_plan import (
    COMPILE_AST_PLAN_STATE_ISSUED,
    DeveloperTaskExecutionCompileAstPlan,
    DeveloperTaskExecutionCompileAstPlanError,
    DeveloperTaskExecutionCompileAstPlanMaterial,
    DeveloperTaskExecutionCompileAstPlanReport,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_COUNT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_TOTAL_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_bundle import (
    DeveloperTaskPythonRuntimeBundle,
    DeveloperTaskPythonRuntimeBundleReport,
)
from modules.developer.developer_task_execution_runtime_lease import (
    LEASE_STATE_ISSUED,
    DeveloperTaskExecutionRuntimeLease,
    DeveloperTaskExecutionRuntimeLeaseError,
    DeveloperTaskExecutionRuntimeLeaseStatus,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
)


COMPILE_AST_CLAIM_TRANSACTION_STATE_ISSUED = "issued"
COMPILE_AST_CLAIM_TRANSACTION_STATE_CLAIMED = "claimed"
COMPILE_AST_CLAIM_TRANSACTION_STATE_PLAN_CLAIM_FAILED = "plan_claim_failed"
COMPILE_AST_CLAIM_TRANSACTION_STATE_RUNTIME_LEASE_CLAIM_FAILED = (
    "runtime_lease_claim_failed"
)
COMPILE_AST_CLAIM_TRANSACTION_STATE_EXPIRED = "expired"
COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED = "invalidated"

_CONSTRUCTOR_KEY = object()
_MATERIAL_CONSTRUCTOR_KEY = object()
_ISSUER_ID = object()
_ISSUER_SECRET = secrets.token_bytes(32)
_REGISTRY_LOCK = threading.RLock()
_ISSUANCE_SEQUENCE = 0


class DeveloperTaskExecutionCompileAstClaimTransactionError(RuntimeError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        self.code = code
        self.message = message
        self.actual = actual
        super().__init__(message)


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstClaimTransactionReport:
    policy_id: str
    policy_fingerprint: str
    operation: str
    plan_policy_fingerprint: str
    plan_fingerprint: str
    source_manifest_sha256: str
    selected_file_count: int
    selected_total_bytes: int
    runtime_lease_policy_fingerprint: str
    runtime_bundle_fingerprint: str
    runtime_lease_fingerprint: str
    ttl_seconds: int
    plan_reserved: bool
    runtime_lease_reserved: bool
    plan_claimed: bool = False
    runtime_lease_claimed: bool = False
    repository_mutated: bool = False
    network_attempted: bool = False
    artifact_download_attempted: bool = False
    dependency_install_attempted: bool = False
    sandbox_launched: bool = False
    candidate_interpreter_executed: bool = False
    changed_source_processed: bool = False
    changed_code_executed: bool = False
    reusable_lease_issued: bool = False
    execution_authorized: bool = False

    @property
    def ok(self) -> bool:
        return (
            self.policy_id
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID
            and self.policy_fingerprint
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT
            and self.operation
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_OPERATION
            and self.plan_policy_fingerprint
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT
            and _is_sha256(self.plan_fingerprint)
            and _is_sha256(self.source_manifest_sha256)
            and 1 <= self.selected_file_count <= DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_COUNT
            and 0 <= self.selected_total_bytes <= DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_TOTAL_BYTES
            and self.runtime_lease_policy_fingerprint == RUNTIME_LEASE_POLICY_FINGERPRINT
            and self.runtime_bundle_fingerprint == RUNTIME_BUNDLE_FINGERPRINT
            and _is_sha256(self.runtime_lease_fingerprint)
            and self.ttl_seconds
            == DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_TTL_SECONDS
            and self.plan_reserved
            and self.runtime_lease_reserved
            and not any(
                (
                    self.plan_claimed,
                    self.runtime_lease_claimed,
                    self.repository_mutated,
                    self.network_attempted,
                    self.artifact_download_attempted,
                    self.dependency_install_attempted,
                    self.sandbox_launched,
                    self.candidate_interpreter_executed,
                    self.changed_source_processed,
                    self.changed_code_executed,
                    self.reusable_lease_issued,
                    self.execution_authorized,
                )
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "operation": self.operation,
            "plan_policy_fingerprint": self.plan_policy_fingerprint,
            "plan_fingerprint": self.plan_fingerprint,
            "source_manifest_sha256": self.source_manifest_sha256,
            "selected_file_count": self.selected_file_count,
            "selected_total_bytes": self.selected_total_bytes,
            "runtime_lease_policy_fingerprint": self.runtime_lease_policy_fingerprint,
            "runtime_bundle_fingerprint": self.runtime_bundle_fingerprint,
            "runtime_lease_fingerprint": self.runtime_lease_fingerprint,
            "ttl_seconds": self.ttl_seconds,
            "plan_reserved": self.plan_reserved,
            "runtime_lease_reserved": self.runtime_lease_reserved,
            "plan_claimed": False,
            "runtime_lease_claimed": False,
            "repository_mutated": False,
            "network_attempted": False,
            "artifact_download_attempted": False,
            "dependency_install_attempted": False,
            "sandbox_launched": False,
            "candidate_interpreter_executed": False,
            "changed_source_processed": False,
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstClaimTransactionStatus:
    state: str
    plan_fingerprint: str
    runtime_lease_fingerprint: str
    policy_id: str = DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID
    policy_fingerprint: str = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT
    )
    ttl_seconds: int = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_TTL_SECONDS
    )
    execution_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "plan_fingerprint": self.plan_fingerprint,
            "runtime_lease_fingerprint": self.runtime_lease_fingerprint,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "ttl_seconds": self.ttl_seconds,
            "execution_authorized": False,
        }


@dataclass
class _ClaimTransactionState:
    state: str
    plan: DeveloperTaskExecutionCompileAstPlan | None = field(repr=False)
    runtime_lease: DeveloperTaskExecutionRuntimeLease | None = field(repr=False)
    issued_at_ns: int
    expires_at_ns: int
    secret: bytes = field(repr=False)
    binding_nonce: bytes = field(repr=False)
    binding_fingerprint: str = field(repr=False)
    issuer_id: object = field(repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


@dataclass(frozen=True)
class _ClaimTransactionServices:
    monotonic_ns: Any = time.monotonic_ns
    token_bytes: Any = secrets.token_bytes


_SERVICES = _ClaimTransactionServices()
_REGISTRY: weakref.WeakKeyDictionary[
    DeveloperTaskExecutionCompileAstClaimTransaction,
    _ClaimTransactionState,
] = weakref.WeakKeyDictionary()
_PLAN_RESERVATIONS: weakref.WeakKeyDictionary[
    DeveloperTaskExecutionCompileAstPlan,
    weakref.ReferenceType[DeveloperTaskExecutionCompileAstClaimTransaction],
] = weakref.WeakKeyDictionary()
_RUNTIME_LEASE_RESERVATIONS: weakref.WeakKeyDictionary[
    DeveloperTaskExecutionRuntimeLease,
    weakref.ReferenceType[DeveloperTaskExecutionCompileAstClaimTransaction],
] = weakref.WeakKeyDictionary()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _next_issuance_sequence() -> int:
    global _ISSUANCE_SEQUENCE
    with _REGISTRY_LOCK:
        _ISSUANCE_SEQUENCE += 1
        return _ISSUANCE_SEQUENCE


def _runtime_lease_fingerprint(
    plan: DeveloperTaskExecutionCompileAstPlan,
    runtime_lease: DeveloperTaskExecutionRuntimeLease,
    binding_nonce: bytes,
    issuance_sequence: int,
) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "algorithm": (
                    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_FINGERPRINT_ALGORITHM
                ),
                "transaction_policy_fingerprint": (
                    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT
                ),
                "plan_policy_fingerprint": plan.report.policy_fingerprint,
                "plan_fingerprint": plan.report.plan_fingerprint,
                "plan_object_identity": id(plan),
                "runtime_lease_policy_fingerprint": runtime_lease.status().policy_fingerprint,
                "runtime_lease_object_identity": id(runtime_lease),
                "binding_nonce": binding_nonce.hex(),
                "issuance_sequence": issuance_sequence,
            }
        )
    )


def _binding_fingerprint(
    report: DeveloperTaskExecutionCompileAstClaimTransactionReport,
    plan: DeveloperTaskExecutionCompileAstPlan,
    runtime_lease: DeveloperTaskExecutionRuntimeLease,
    binding_nonce: bytes,
) -> str:
    return _sha256(
        _canonical_json_bytes(
            {
                "policy_fingerprint": report.policy_fingerprint,
                "operation": report.operation,
                "plan_fingerprint": report.plan_fingerprint,
                "source_manifest_sha256": report.source_manifest_sha256,
                "runtime_lease_fingerprint": report.runtime_lease_fingerprint,
                "plan_object_identity": id(plan),
                "runtime_lease_object_identity": id(runtime_lease),
                "binding_nonce": binding_nonce.hex(),
            }
        )
    )


def _claim_guard(secret: bytes, binding_fingerprint: str) -> bytes:
    return hmac.new(
        _ISSUER_SECRET,
        secret + binding_fingerprint.encode("ascii"),
        hashlib.sha256,
    ).digest()


def _reservation_owner(
    reservations: weakref.WeakKeyDictionary[Any, weakref.ReferenceType[Any]],
    capability: Any,
) -> Any | None:
    reference = reservations.get(capability)
    if reference is None:
        return None
    owner = reference()
    if owner is None:
        try:
            del reservations[capability]
        except KeyError:
            pass
    return owner


def _release_reservations_locked(
    transaction: DeveloperTaskExecutionCompileAstClaimTransaction,
    state: _ClaimTransactionState,
) -> None:
    plan = state.plan
    runtime_lease = state.runtime_lease
    if plan is not None and _reservation_owner(_PLAN_RESERVATIONS, plan) is transaction:
        try:
            del _PLAN_RESERVATIONS[plan]
        except KeyError:
            pass
    if (
        runtime_lease is not None
        and _reservation_owner(_RUNTIME_LEASE_RESERVATIONS, runtime_lease) is transaction
    ):
        try:
            del _RUNTIME_LEASE_RESERVATIONS[runtime_lease]
        except KeyError:
            pass


def _terminalize_state(
    transaction: DeveloperTaskExecutionCompileAstClaimTransaction,
    state: _ClaimTransactionState,
    terminal_state: str,
) -> None:
    with _REGISTRY_LOCK:
        _release_reservations_locked(transaction, state)
    state.state = terminal_state
    state.plan = None
    state.runtime_lease = None
    state.issued_at_ns = 0
    state.expires_at_ns = 0
    state.secret = b""
    state.binding_nonce = b""
    state.binding_fingerprint = ""
    state.issuer_id = object()


def _validate_plan(plan: DeveloperTaskExecutionCompileAstPlan) -> None:
    if type(plan) is not DeveloperTaskExecutionCompileAstPlan:
        raise TypeError("plan must be DeveloperTaskExecutionCompileAstPlan")
    if type(plan.report) is not DeveloperTaskExecutionCompileAstPlanReport or not plan.report.ok:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_plan_invalid",
            "V1C1B plan report is not canonical and successful.",
        )
    if plan.report.policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_plan_policy_mismatch",
            "V1C1B plan policy fingerprint does not match V1C2C0.",
            actual=plan.report.policy_fingerprint,
        )
    status = plan.status()
    if status.state != COMPILE_AST_PLAN_STATE_ISSUED:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_plan_not_issued",
            "V1C1B plan must still be issued before transaction reservation.",
            actual=status.state,
        )


def _validate_runtime_lease(runtime_lease: DeveloperTaskExecutionRuntimeLease) -> None:
    if type(runtime_lease) is not DeveloperTaskExecutionRuntimeLease:
        raise TypeError("runtime_lease must be DeveloperTaskExecutionRuntimeLease")
    status = runtime_lease.status()
    if type(status) is not DeveloperTaskExecutionRuntimeLeaseStatus:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_runtime_lease_status_invalid",
            "V1B4D runtime lease returned an invalid status type.",
        )
    if status.policy_fingerprint != RUNTIME_LEASE_POLICY_FINGERPRINT:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_runtime_lease_policy_mismatch",
            "V1B4D runtime lease policy fingerprint does not match V1C2C0.",
            actual=status.policy_fingerprint,
        )
    if status.state != LEASE_STATE_ISSUED:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_runtime_lease_not_issued",
            "V1B4D runtime lease must still be issued before transaction reservation.",
            actual=status.state,
        )


def _validate_claimed_material(
    plan: DeveloperTaskExecutionCompileAstPlan,
    plan_material: DeveloperTaskExecutionCompileAstPlanMaterial,
    runtime_bundle: DeveloperTaskPythonRuntimeBundle,
) -> None:
    if type(plan_material) is not DeveloperTaskExecutionCompileAstPlanMaterial:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_plan_material_invalid",
            "V1C1B claim returned an invalid material type.",
        )
    if plan_material.report is not plan.report:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_plan_material_invalid",
            "V1C1B material is not bound to the exact reserved plan report.",
        )
    if type(runtime_bundle) is not DeveloperTaskPythonRuntimeBundle:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_runtime_bundle_invalid",
            "V1B4D claim returned an invalid runtime bundle type.",
        )
    if (
        type(runtime_bundle.report) is not DeveloperTaskPythonRuntimeBundleReport
        or not runtime_bundle.ok
        or runtime_bundle.report.bundle_fingerprint != RUNTIME_BUNDLE_FINGERPRINT
    ):
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_runtime_bundle_invalid",
            "Claimed runtime bundle does not match the canonical V1B4B identity.",
        )


class DeveloperTaskExecutionCompileAstClaimTransactionMaterial:
    __slots__ = ("report", "_plan_material", "_runtime_bundle")

    def __init__(
        self,
        constructor_key: object,
        report: DeveloperTaskExecutionCompileAstClaimTransactionReport,
        plan_material: DeveloperTaskExecutionCompileAstPlanMaterial,
        runtime_bundle: DeveloperTaskPythonRuntimeBundle,
    ) -> None:
        if constructor_key is not _MATERIAL_CONSTRUCTOR_KEY:
            raise TypeError(
                "DeveloperTaskExecutionCompileAstClaimTransactionMaterial cannot be constructed directly"
            )
        if type(report) is not DeveloperTaskExecutionCompileAstClaimTransactionReport or not report.ok:
            raise TypeError("invalid compile/AST claim transaction report")
        if type(plan_material) is not DeveloperTaskExecutionCompileAstPlanMaterial:
            raise TypeError("invalid compile/AST plan material")
        if type(runtime_bundle) is not DeveloperTaskPythonRuntimeBundle:
            raise TypeError("invalid trusted runtime bundle")
        self.report = report
        self._plan_material = plan_material
        self._runtime_bundle = runtime_bundle

    @property
    def plan_material(self) -> DeveloperTaskExecutionCompileAstPlanMaterial:
        return self._plan_material

    @property
    def runtime_bundle(self) -> DeveloperTaskPythonRuntimeBundle:
        return self._runtime_bundle

    @property
    def runtime_lease_fingerprint(self) -> str:
        return self.report.runtime_lease_fingerprint

    @property
    def plan_claimed(self) -> bool:
        return True

    @property
    def runtime_lease_claimed(self) -> bool:
        return True

    @property
    def execution_authorized(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.report.policy_id,
            "policy_fingerprint": self.report.policy_fingerprint,
            "operation": self.report.operation,
            "plan_fingerprint": self.report.plan_fingerprint,
            "runtime_lease_fingerprint": self.report.runtime_lease_fingerprint,
            "runtime_bundle_fingerprint": self.report.runtime_bundle_fingerprint,
            "selected_file_count": self.report.selected_file_count,
            "selected_total_bytes": self.report.selected_total_bytes,
            "plan_claimed": True,
            "runtime_lease_claimed": True,
            "sandbox_launched": False,
            "candidate_interpreter_executed": False,
            "changed_source_processed": False,
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
        }

    def __copy__(self):
        raise TypeError(
            "DeveloperTaskExecutionCompileAstClaimTransactionMaterial is non-copyable"
        )

    def __deepcopy__(self, memo):
        raise TypeError(
            "DeveloperTaskExecutionCompileAstClaimTransactionMaterial is non-copyable"
        )

    def __reduce__(self):
        raise TypeError(
            "DeveloperTaskExecutionCompileAstClaimTransactionMaterial is non-serializable"
        )

    def __reduce_ex__(self, protocol):
        raise TypeError(
            "DeveloperTaskExecutionCompileAstClaimTransactionMaterial is non-serializable"
        )

    def __getstate__(self):
        raise TypeError(
            "DeveloperTaskExecutionCompileAstClaimTransactionMaterial is non-serializable"
        )


class DeveloperTaskExecutionCompileAstClaimTransaction:
    __slots__ = ("_guard", "report", "__weakref__")

    def __init__(
        self,
        constructor_key: object,
        guard: bytes,
        report: DeveloperTaskExecutionCompileAstClaimTransactionReport,
    ) -> None:
        if constructor_key is not _CONSTRUCTOR_KEY:
            raise TypeError(
                "DeveloperTaskExecutionCompileAstClaimTransaction cannot be constructed directly"
            )
        if type(guard) is not bytes or len(guard) != hashlib.sha256().digest_size:
            raise TypeError("invalid compile/AST claim transaction guard")
        if type(report) is not DeveloperTaskExecutionCompileAstClaimTransactionReport or not report.ok:
            raise TypeError("invalid compile/AST claim transaction report")
        self._guard = guard
        self.report = report

    @property
    def execution_authorized(self) -> bool:
        return False

    def status(self) -> DeveloperTaskExecutionCompileAstClaimTransactionStatus:
        return _compile_ast_claim_transaction_status(self)

    def claim(self) -> DeveloperTaskExecutionCompileAstClaimTransactionMaterial:
        return _claim_developer_task_execution_compile_ast_claim_transaction(self)

    def __repr__(self) -> str:
        status = self.status()
        return (
            "DeveloperTaskExecutionCompileAstClaimTransaction("
            f"state={status.state!r}, plan_fingerprint={status.plan_fingerprint!r}, "
            f"runtime_lease_fingerprint={status.runtime_lease_fingerprint!r}, "
            "execution_authorized=False)"
        )

    def __copy__(self):
        raise TypeError(
            "DeveloperTaskExecutionCompileAstClaimTransaction is non-copyable"
        )

    def __deepcopy__(self, memo):
        raise TypeError(
            "DeveloperTaskExecutionCompileAstClaimTransaction is non-copyable"
        )

    def __reduce__(self):
        raise TypeError(
            "DeveloperTaskExecutionCompileAstClaimTransaction is non-serializable"
        )

    def __reduce_ex__(self, protocol):
        raise TypeError(
            "DeveloperTaskExecutionCompileAstClaimTransaction is non-serializable"
        )

    def __getstate__(self):
        raise TypeError(
            "DeveloperTaskExecutionCompileAstClaimTransaction is non-serializable"
        )


def _compile_ast_claim_transaction_status(
    transaction: DeveloperTaskExecutionCompileAstClaimTransaction,
) -> DeveloperTaskExecutionCompileAstClaimTransactionStatus:
    if type(transaction) is not DeveloperTaskExecutionCompileAstClaimTransaction:
        raise TypeError(
            "transaction must be DeveloperTaskExecutionCompileAstClaimTransaction"
        )
    with _REGISTRY_LOCK:
        state = _REGISTRY.get(transaction)
    if state is None:
        return DeveloperTaskExecutionCompileAstClaimTransactionStatus(
            state=COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
            plan_fingerprint=transaction.report.plan_fingerprint,
            runtime_lease_fingerprint=transaction.report.runtime_lease_fingerprint,
        )
    with state.lock:
        if state.state == COMPILE_AST_CLAIM_TRANSACTION_STATE_ISSUED:
            now_ns = _SERVICES.monotonic_ns()
            if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
                _terminalize_state(
                    transaction,
                    state,
                    COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
                )
            elif now_ns >= state.expires_at_ns:
                _terminalize_state(
                    transaction,
                    state,
                    COMPILE_AST_CLAIM_TRANSACTION_STATE_EXPIRED,
                )
        return DeveloperTaskExecutionCompileAstClaimTransactionStatus(
            state=state.state,
            plan_fingerprint=transaction.report.plan_fingerprint,
            runtime_lease_fingerprint=transaction.report.runtime_lease_fingerprint,
        )


def issue_developer_task_execution_compile_ast_claim_transaction(
    plan: DeveloperTaskExecutionCompileAstPlan,
    runtime_lease: DeveloperTaskExecutionRuntimeLease,
) -> DeveloperTaskExecutionCompileAstClaimTransaction:
    """Reserve one exact plan and runtime lease without claiming either capability."""

    _validate_plan(plan)
    _validate_runtime_lease(runtime_lease)
    policy_errors = validate_developer_task_execution_compile_ast_claim_transaction_policy(
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY
    )
    if policy_errors:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_policy_invalid",
            "Canonical V1C2C0 policy is invalid.",
            actual=",".join(policy_errors),
        )

    now_ns = _SERVICES.monotonic_ns()
    if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_clock_invalid",
            "Monotonic V1C2C0 clock returned an invalid issuance value.",
        )
    try:
        secret = _SERVICES.token_bytes(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_SECRET_BYTES
        )
    except Exception as exc:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_secret_generation_failed",
            "V1C2C0 capability secret generation failed.",
            actual=type(exc).__name__,
        ) from exc
    if (
        type(secret) is not bytes
        or len(secret)
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_SECRET_BYTES
    ):
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_secret_generation_failed",
            "V1C2C0 capability secret generator returned invalid bytes.",
        )
    try:
        binding_nonce = _SERVICES.token_bytes(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_BINDING_NONCE_BYTES
        )
    except Exception as exc:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_binding_nonce_generation_failed",
            "V1C2C0 binding nonce generation failed.",
            actual=type(exc).__name__,
        ) from exc
    if (
        type(binding_nonce) is not bytes
        or len(binding_nonce)
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_BINDING_NONCE_BYTES
    ):
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_binding_nonce_generation_failed",
            "V1C2C0 binding nonce generator returned invalid bytes.",
        )

    issuance_sequence = _next_issuance_sequence()
    runtime_lease_fingerprint = _runtime_lease_fingerprint(
        plan,
        runtime_lease,
        binding_nonce,
        issuance_sequence,
    )
    report = DeveloperTaskExecutionCompileAstClaimTransactionReport(
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID,
        policy_fingerprint=(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT
        ),
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_OPERATION,
        plan_policy_fingerprint=plan.report.policy_fingerprint,
        plan_fingerprint=plan.report.plan_fingerprint,
        source_manifest_sha256=plan.report.source_manifest_sha256,
        selected_file_count=plan.report.selected_file_count,
        selected_total_bytes=plan.report.selected_total_bytes,
        runtime_lease_policy_fingerprint=runtime_lease.status().policy_fingerprint,
        runtime_bundle_fingerprint=RUNTIME_BUNDLE_FINGERPRINT,
        runtime_lease_fingerprint=runtime_lease_fingerprint,
        ttl_seconds=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_TTL_SECONDS,
        plan_reserved=True,
        runtime_lease_reserved=True,
    )
    if not report.ok:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_report_invalid",
            "Derived V1C2C0 transaction report failed canonical validation.",
        )
    binding_fingerprint = _binding_fingerprint(
        report,
        plan,
        runtime_lease,
        binding_nonce,
    )
    guard = _claim_guard(secret, binding_fingerprint)
    transaction = DeveloperTaskExecutionCompileAstClaimTransaction(
        _CONSTRUCTOR_KEY,
        guard,
        report,
    )
    state = _ClaimTransactionState(
        state=COMPILE_AST_CLAIM_TRANSACTION_STATE_ISSUED,
        plan=plan,
        runtime_lease=runtime_lease,
        issued_at_ns=now_ns,
        expires_at_ns=(
            now_ns
            + DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_TTL_SECONDS
            * 1_000_000_000
        ),
        secret=secret,
        binding_nonce=binding_nonce,
        binding_fingerprint=binding_fingerprint,
        issuer_id=_ISSUER_ID,
    )

    with _REGISTRY_LOCK:
        if _reservation_owner(_PLAN_RESERVATIONS, plan) is not None:
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_plan_reserved",
                "The exact V1C1B plan already has a live V1C2C0 transaction reservation.",
            )
        if _reservation_owner(_RUNTIME_LEASE_RESERVATIONS, runtime_lease) is not None:
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_runtime_lease_reserved",
                "The exact V1B4D runtime lease already has a live V1C2C0 transaction reservation.",
            )
        _validate_plan(plan)
        _validate_runtime_lease(runtime_lease)
        _REGISTRY[transaction] = state
        _PLAN_RESERVATIONS[plan] = weakref.ref(transaction)
        _RUNTIME_LEASE_RESERVATIONS[runtime_lease] = weakref.ref(transaction)
    return transaction


def _claim_developer_task_execution_compile_ast_claim_transaction(
    transaction: DeveloperTaskExecutionCompileAstClaimTransaction,
) -> DeveloperTaskExecutionCompileAstClaimTransactionMaterial:
    if type(transaction) is not DeveloperTaskExecutionCompileAstClaimTransaction:
        raise TypeError(
            "transaction must be DeveloperTaskExecutionCompileAstClaimTransaction"
        )
    with _REGISTRY_LOCK:
        state = _REGISTRY.get(transaction)
    if state is None:
        raise DeveloperTaskExecutionCompileAstClaimTransactionError(
            "compile_ast_claim_transaction_unregistered",
            "V1C2C0 transaction is not registered in this process issuer.",
        )

    with state.lock:
        terminal_errors = {
            COMPILE_AST_CLAIM_TRANSACTION_STATE_CLAIMED: (
                "compile_ast_claim_transaction_already_claimed",
                "V1C2C0 transaction has already been claimed.",
            ),
            COMPILE_AST_CLAIM_TRANSACTION_STATE_PLAN_CLAIM_FAILED: (
                "compile_ast_claim_transaction_plan_claim_failed",
                "V1C2C0 transaction already failed while claiming the plan.",
            ),
            COMPILE_AST_CLAIM_TRANSACTION_STATE_RUNTIME_LEASE_CLAIM_FAILED: (
                "compile_ast_claim_transaction_runtime_lease_claim_failed",
                "V1C2C0 transaction already failed while claiming the runtime lease.",
            ),
            COMPILE_AST_CLAIM_TRANSACTION_STATE_EXPIRED: (
                "compile_ast_claim_transaction_expired",
                "V1C2C0 transaction has expired.",
            ),
            COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED: (
                "compile_ast_claim_transaction_invalidated",
                "V1C2C0 transaction is permanently invalidated.",
            ),
        }
        if state.state in terminal_errors:
            code, message = terminal_errors[state.state]
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(code, message)
        if state.state != COMPILE_AST_CLAIM_TRANSACTION_STATE_ISSUED:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_invalidated",
                "V1C2C0 transaction state is invalid.",
            )

        now_ns = _SERVICES.monotonic_ns()
        if not isinstance(now_ns, int) or isinstance(now_ns, bool) or now_ns < 0:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_clock_invalid",
                "Monotonic V1C2C0 clock returned an invalid claim value.",
            )
        if now_ns >= state.expires_at_ns:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_EXPIRED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_expired",
                "V1C2C0 transaction has expired.",
            )

        plan = state.plan
        runtime_lease = state.runtime_lease
        if (
            type(plan) is not DeveloperTaskExecutionCompileAstPlan
            or type(runtime_lease) is not DeveloperTaskExecutionRuntimeLease
        ):
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_binding_invalid",
                "V1C2C0 transaction no longer retains exact typed capabilities.",
            )
        if (
            state.issuer_id is not _ISSUER_ID
            or len(state.secret)
            != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_SECRET_BYTES
            or len(state.binding_nonce)
            != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_BINDING_NONCE_BYTES
            or len(state.binding_fingerprint) != 64
            or not transaction.report.ok
            or state.binding_fingerprint
            != _binding_fingerprint(
                transaction.report,
                plan,
                runtime_lease,
                state.binding_nonce,
            )
            or not hmac.compare_digest(
                transaction._guard,
                _claim_guard(state.secret, state.binding_fingerprint),
            )
        ):
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_issuer_binding_invalid",
                "V1C2C0 issuer/secret/object binding is invalid.",
            )
        with _REGISTRY_LOCK:
            reservations_valid = (
                _reservation_owner(_PLAN_RESERVATIONS, plan) is transaction
                and _reservation_owner(_RUNTIME_LEASE_RESERVATIONS, runtime_lease)
                is transaction
            )
        if not reservations_valid:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_reservation_invalid",
                "V1C2C0 exact capability reservations changed before claim.",
            )
        policy_errors = validate_developer_task_execution_compile_ast_claim_transaction_policy(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY
        )
        if policy_errors:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_policy_invalid",
                "Canonical V1C2C0 policy changed before claim.",
                actual=",".join(policy_errors),
            )

        plan_status = plan.status()
        if (
            plan_status.state != COMPILE_AST_PLAN_STATE_ISSUED
            or plan_status.policy_fingerprint
            != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT
            or plan_status.plan_fingerprint != transaction.report.plan_fingerprint
        ):
            actual = plan_status.state
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_PLAN_CLAIM_FAILED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_plan_claim_failed",
                "The exact reserved V1C1B plan is no longer claimable.",
                actual=actual,
            )
        runtime_lease_status = runtime_lease.status()
        if (
            runtime_lease_status.state != LEASE_STATE_ISSUED
            or runtime_lease_status.policy_fingerprint != RUNTIME_LEASE_POLICY_FINGERPRINT
        ):
            actual = runtime_lease_status.state
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_RUNTIME_LEASE_CLAIM_FAILED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_runtime_lease_claim_failed",
                "The exact reserved V1B4D runtime lease is no longer claimable.",
                actual=actual,
            )

        final_now_ns = _SERVICES.monotonic_ns()
        if (
            not isinstance(final_now_ns, int)
            or isinstance(final_now_ns, bool)
            or final_now_ns < 0
        ):
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_clock_invalid",
                "Monotonic V1C2C0 clock returned an invalid final claim value.",
            )
        if final_now_ns >= state.expires_at_ns:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_EXPIRED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_expired",
                "V1C2C0 transaction expired during atomic claim validation.",
            )

        try:
            plan_material = plan.claim_for_compile_ast_gate()
        except DeveloperTaskExecutionCompileAstPlanError as exc:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_PLAN_CLAIM_FAILED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_plan_claim_failed",
                "V1C2C0 could not claim the exact reserved V1C1B plan.",
                actual=exc.code,
            ) from exc
        except Exception as exc:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_PLAN_CLAIM_FAILED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_plan_claim_failed",
                "V1C2C0 plan claim failed unexpectedly.",
                actual=type(exc).__name__,
            ) from exc

        try:
            runtime_bundle = runtime_lease.claim()
        except DeveloperTaskExecutionRuntimeLeaseError as exc:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_RUNTIME_LEASE_CLAIM_FAILED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_runtime_lease_claim_failed",
                "V1C2C0 claimed the plan but could not claim the exact runtime lease.",
                actual=exc.code,
            ) from exc
        except Exception as exc:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_RUNTIME_LEASE_CLAIM_FAILED,
            )
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_runtime_lease_claim_failed",
                "V1C2C0 runtime lease claim failed unexpectedly after plan consumption.",
                actual=type(exc).__name__,
            ) from exc

        try:
            _validate_claimed_material(plan, plan_material, runtime_bundle)
            material = DeveloperTaskExecutionCompileAstClaimTransactionMaterial(
                _MATERIAL_CONSTRUCTOR_KEY,
                transaction.report,
                plan_material,
                runtime_bundle,
            )
        except Exception as exc:
            _terminalize_state(
                transaction,
                state,
                COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
            )
            if isinstance(
                exc,
                DeveloperTaskExecutionCompileAstClaimTransactionError,
            ):
                raise
            raise DeveloperTaskExecutionCompileAstClaimTransactionError(
                "compile_ast_claim_transaction_material_invalid",
                "V1C2C0 claimed capabilities returned an invalid handoff material.",
                actual=type(exc).__name__,
            ) from exc

        _terminalize_state(
            transaction,
            state,
            COMPILE_AST_CLAIM_TRANSACTION_STATE_CLAIMED,
        )
        return material
