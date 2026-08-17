from __future__ import annotations

"""V1C2C0 immutable policy for the process-local compile/AST claim transaction."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
)


DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID = (
    "skynetvs-v1c2c0-compile-ast-claim-transaction-v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT = (
    "092f17cbbdac961c6be254fbed196d9ff3c639c47957882f6fbbdaa9624b8caa"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_OPERATION = (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_TTL_SECONDS = 300
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_SECRET_BYTES = 32
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_BINDING_NONCE_BYTES = 32
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_CLOCK_ID = "time.monotonic_ns"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_FINGERPRINT_ALGORITHM = (
    "sha256_canonical_process_local_binding_v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_STATES = (
    "issued",
    "claimed",
    "plan_claim_failed",
    "runtime_lease_claim_failed",
    "expired",
    "invalidated",
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_CLAIM_ORDER = (
    "plan",
    "runtime_lease",
)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstClaimTransactionPolicy:
    schema_version: int
    policy_id: str
    policy_fingerprint: str
    operation: str
    plan_policy_fingerprint: str
    runtime_lease_policy_fingerprint: str
    runtime_bundle_fingerprint: str
    transaction_ttl_seconds: int
    secret_bytes: int
    binding_nonce_bytes: int
    clock: str
    states: tuple[str, ...]
    claim_order: tuple[str, ...]
    process_local: bool
    single_use: bool
    serializable: bool
    copyable: bool
    pickleable: bool
    one_live_transaction_per_plan: bool
    one_live_transaction_per_runtime_lease: bool
    reservation_released_on_terminal_state: bool
    runtime_lease_fingerprint_algorithm: str
    runtime_lease_fingerprint_binds_exact_runtime_lease_object: bool
    runtime_lease_fingerprint_binds_plan_fingerprint: bool
    runtime_lease_fingerprint_unique_per_transaction: bool
    runtime_lease_fingerprint_serializes_secret: bool
    runtime_lease_fingerprint_claims_execution_authority: bool
    plan_claimed_before_claim: bool
    runtime_lease_claimed_before_claim: bool
    sandbox_launched_before_claim: bool
    interpreter_executed_before_claim: bool
    changed_source_processed_before_claim: bool
    execution_authorized_before_claim: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "operation": self.operation,
            "plan_policy_fingerprint": self.plan_policy_fingerprint,
            "runtime_lease_policy_fingerprint": self.runtime_lease_policy_fingerprint,
            "runtime_bundle_fingerprint": self.runtime_bundle_fingerprint,
            "transaction_ttl_seconds": self.transaction_ttl_seconds,
            "secret_bytes": self.secret_bytes,
            "binding_nonce_bytes": self.binding_nonce_bytes,
            "clock": self.clock,
            "states": list(self.states),
            "claim_order": list(self.claim_order),
            "capability": {
                "process_local": self.process_local,
                "single_use": self.single_use,
                "serializable": self.serializable,
                "copyable": self.copyable,
                "pickleable": self.pickleable,
            },
            "reservation": {
                "one_live_transaction_per_plan": self.one_live_transaction_per_plan,
                "one_live_transaction_per_runtime_lease": self.one_live_transaction_per_runtime_lease,
                "released_on_terminal_state": self.reservation_released_on_terminal_state,
            },
            "runtime_lease_fingerprint_semantics": {
                "algorithm": self.runtime_lease_fingerprint_algorithm,
                "binds_exact_runtime_lease_object": self.runtime_lease_fingerprint_binds_exact_runtime_lease_object,
                "binds_plan_fingerprint": self.runtime_lease_fingerprint_binds_plan_fingerprint,
                "unique_per_transaction": self.runtime_lease_fingerprint_unique_per_transaction,
                "serializes_secret": self.runtime_lease_fingerprint_serializes_secret,
                "claims_execution_authority": self.runtime_lease_fingerprint_claims_execution_authority,
            },
            "effects_before_claim": {
                "plan_claimed": self.plan_claimed_before_claim,
                "runtime_lease_claimed": self.runtime_lease_claimed_before_claim,
                "sandbox_launched": self.sandbox_launched_before_claim,
                "interpreter_executed": self.interpreter_executed_before_claim,
                "changed_source_processed": self.changed_source_processed_before_claim,
                "execution_authorized": self.execution_authorized_before_claim,
            },
        }


DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY = (
    DeveloperTaskExecutionCompileAstClaimTransactionPolicy(
        schema_version=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_SCHEMA_VERSION,
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_OPERATION,
        plan_policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
        runtime_lease_policy_fingerprint=RUNTIME_LEASE_POLICY_FINGERPRINT,
        runtime_bundle_fingerprint=RUNTIME_BUNDLE_FINGERPRINT,
        transaction_ttl_seconds=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_TTL_SECONDS,
        secret_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_SECRET_BYTES,
        binding_nonce_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_BINDING_NONCE_BYTES,
        clock=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_CLOCK_ID,
        states=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_STATES,
        claim_order=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_CLAIM_ORDER,
        process_local=True,
        single_use=True,
        serializable=False,
        copyable=False,
        pickleable=False,
        one_live_transaction_per_plan=True,
        one_live_transaction_per_runtime_lease=True,
        reservation_released_on_terminal_state=True,
        runtime_lease_fingerprint_algorithm=(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_FINGERPRINT_ALGORITHM
        ),
        runtime_lease_fingerprint_binds_exact_runtime_lease_object=True,
        runtime_lease_fingerprint_binds_plan_fingerprint=True,
        runtime_lease_fingerprint_unique_per_transaction=True,
        runtime_lease_fingerprint_serializes_secret=False,
        runtime_lease_fingerprint_claims_execution_authority=False,
        plan_claimed_before_claim=False,
        runtime_lease_claimed_before_claim=False,
        sandbox_launched_before_claim=False,
        interpreter_executed_before_claim=False,
        changed_source_processed_before_claim=False,
        execution_authorized_before_claim=False,
    )
)


def canonical_developer_task_execution_compile_ast_claim_transaction_policy_json(
    policy: DeveloperTaskExecutionCompileAstClaimTransactionPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY
    ),
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstClaimTransactionPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionCompileAstClaimTransactionPolicy")
    return _canonical_json_bytes(policy.to_dict()).decode("utf-8")


def developer_task_execution_compile_ast_claim_transaction_policy_fingerprint(
    policy: DeveloperTaskExecutionCompileAstClaimTransactionPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY
    ),
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstClaimTransactionPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionCompileAstClaimTransactionPolicy")
    payload = policy.to_dict().copy()
    payload.pop("policy_fingerprint")
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def validate_developer_task_execution_compile_ast_claim_transaction_policy(
    policy: DeveloperTaskExecutionCompileAstClaimTransactionPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY
    ),
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstClaimTransactionPolicy):
        return ("policy_type_invalid",)

    errors: list[str] = []
    if (
        policy.schema_version
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_SCHEMA_VERSION
        or policy.policy_id
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID
    ):
        errors.append("policy_identity_invalid")
    if policy.operation != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_OPERATION:
        errors.append("operation_invalid")
    if policy.plan_policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT:
        errors.append("plan_policy_invalid")
    if policy.runtime_lease_policy_fingerprint != RUNTIME_LEASE_POLICY_FINGERPRINT:
        errors.append("runtime_lease_policy_invalid")
    if policy.runtime_bundle_fingerprint != RUNTIME_BUNDLE_FINGERPRINT:
        errors.append("runtime_bundle_invalid")
    if (
        policy.transaction_ttl_seconds
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_TTL_SECONDS
        or policy.secret_bytes
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_SECRET_BYTES
        or policy.binding_nonce_bytes
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_BINDING_NONCE_BYTES
        or policy.clock
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_CLOCK_ID
    ):
        errors.append("capability_limits_invalid")
    if (
        policy.states
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_STATES
        or policy.claim_order
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_CLAIM_ORDER
    ):
        errors.append("state_machine_invalid")
    if not all(
        (
            policy.process_local,
            policy.single_use,
            policy.one_live_transaction_per_plan,
            policy.one_live_transaction_per_runtime_lease,
            policy.reservation_released_on_terminal_state,
            policy.runtime_lease_fingerprint_binds_exact_runtime_lease_object,
            policy.runtime_lease_fingerprint_binds_plan_fingerprint,
            policy.runtime_lease_fingerprint_unique_per_transaction,
        )
    ):
        errors.append("required_capability_guards_missing")
    if any(
        (
            policy.serializable,
            policy.copyable,
            policy.pickleable,
            policy.runtime_lease_fingerprint_serializes_secret,
            policy.runtime_lease_fingerprint_claims_execution_authority,
            policy.plan_claimed_before_claim,
            policy.runtime_lease_claimed_before_claim,
            policy.sandbox_launched_before_claim,
            policy.interpreter_executed_before_claim,
            policy.changed_source_processed_before_claim,
            policy.execution_authorized_before_claim,
        )
    ):
        errors.append("forbidden_capability_effect_enabled")
    if (
        policy.runtime_lease_fingerprint_algorithm
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_FINGERPRINT_ALGORITHM
    ):
        errors.append("runtime_lease_fingerprint_algorithm_invalid")

    comparable = policy.to_dict().copy()
    expected = DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY.to_dict().copy()
    comparable["policy_fingerprint"] = ""
    expected["policy_fingerprint"] = ""
    if comparable != expected:
        errors.append("policy_values_changed")
    if (
        developer_task_execution_compile_ast_claim_transaction_policy_fingerprint(policy)
        != policy.policy_fingerprint
    ):
        errors.append("policy_fingerprint_mismatch")
    return tuple(errors)
