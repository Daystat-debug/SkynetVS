from __future__ import annotations

"""Pinned host-only policy for V1C2B signed compile/AST transcript verification."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
)
from modules.developer.developer_task_execution_compile_ast_runner_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
)


DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_ID = (
    "skynetvs-v1c2b-signed-compile-ast-transcript-verifier-v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT = "d7fc8c5011e6dd353202ebd04567d1e7f59d7af523c8c9b20769afc6b38d45a2"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_SIGNATURE_ALGORITHM = (
    "ECDSA_P256_SHA256_P1363_64_BYTES"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_CRYPTO_BACKEND = (
    "windows_cng_ecdsa_p256_sha256_v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_SIGNATURE_BYTES = 64
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_READY_TOLERANCE_SECONDS = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_TERMINAL_TOLERANCE_SECONDS = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_PINNED = (
    "compile_ast_transcript_pinned"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_VERIFIED = (
    "compile_ast_transcript_verified"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_STATUS_FAILED = "failed"


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstVerifierPolicy:
    schema_version: int
    policy_id: str
    fingerprint: str
    contract_policy_fingerprint: str
    runner_policy_fingerprint: str
    runner_bundle_fingerprint: str
    contract_policy_sha256: str
    runner_sha256: str
    payload_sha256: str
    operation: str
    signature_algorithm: str
    signature_bytes: int
    default_crypto_backend: str
    ready_timing_tolerance_seconds: int
    terminal_timing_tolerance_seconds: int
    result_optional_only_for_boundary_failed: bool
    authentic_syntax_failure_is_valid: bool
    authentic_boundary_failure_is_valid: bool
    pin_capability_required: bool
    post_pin_reparse_required: bool
    verifier_reads_filesystem: bool
    verifier_launches_processes: bool
    verifier_launches_sandbox: bool
    verifier_uses_network: bool
    verifier_executes_candidate_interpreter: bool
    verifier_processes_changed_source: bool
    verifier_authorizes_execution: bool
    reusable_lease_issued: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "fingerprint": self.fingerprint,
            "operation": self.operation,
            "trusted_inputs": {
                "contract_policy_fingerprint": self.contract_policy_fingerprint,
                "runner_policy_fingerprint": self.runner_policy_fingerprint,
                "runner_bundle_fingerprint": self.runner_bundle_fingerprint,
                "contract_policy_sha256": self.contract_policy_sha256,
                "runner_sha256": self.runner_sha256,
                "payload_sha256": self.payload_sha256,
            },
            "crypto": {
                "signature_algorithm": self.signature_algorithm,
                "signature_bytes": self.signature_bytes,
                "default_backend": self.default_crypto_backend,
            },
            "timing": {
                "ready_tolerance_seconds": self.ready_timing_tolerance_seconds,
                "terminal_tolerance_seconds": self.terminal_timing_tolerance_seconds,
            },
            "semantics": {
                "result_optional_only_for_boundary_failed": self.result_optional_only_for_boundary_failed,
                "authentic_syntax_failure_is_valid": self.authentic_syntax_failure_is_valid,
                "authentic_boundary_failure_is_valid": self.authentic_boundary_failure_is_valid,
                "pin_capability_required": self.pin_capability_required,
                "post_pin_reparse_required": self.post_pin_reparse_required,
            },
            "host_only_boundary": {
                "reads_filesystem": self.verifier_reads_filesystem,
                "launches_processes": self.verifier_launches_processes,
                "launches_sandbox": self.verifier_launches_sandbox,
                "uses_network": self.verifier_uses_network,
                "executes_candidate_interpreter": self.verifier_executes_candidate_interpreter,
                "processes_changed_source": self.verifier_processes_changed_source,
                "execution_authorized": self.verifier_authorizes_execution,
                "reusable_lease_issued": self.reusable_lease_issued,
            },
        }


def canonical_developer_task_execution_compile_ast_verifier_policy_json(
    policy: DeveloperTaskExecutionCompileAstVerifierPolicy,
) -> bytes:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstVerifierPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionCompileAstVerifierPolicy")
    payload = policy.to_dict()
    payload["fingerprint"] = ""
    return _canonical_json_bytes(payload)


def developer_task_execution_compile_ast_verifier_policy_fingerprint(
    policy: DeveloperTaskExecutionCompileAstVerifierPolicy,
) -> str:
    return hashlib.sha256(
        canonical_developer_task_execution_compile_ast_verifier_policy_json(policy)
    ).hexdigest()


DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_V1 = (
    DeveloperTaskExecutionCompileAstVerifierPolicy(
        schema_version=DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_SCHEMA_VERSION,
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_ID,
        fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
        contract_policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        runner_policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
        runner_bundle_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
        contract_policy_sha256=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
        runner_sha256=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
        payload_sha256=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        signature_algorithm=DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_SIGNATURE_ALGORITHM,
        signature_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_SIGNATURE_BYTES,
        default_crypto_backend=DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_CRYPTO_BACKEND,
        ready_timing_tolerance_seconds=DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_READY_TOLERANCE_SECONDS,
        terminal_timing_tolerance_seconds=DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_TERMINAL_TOLERANCE_SECONDS,
        result_optional_only_for_boundary_failed=True,
        authentic_syntax_failure_is_valid=True,
        authentic_boundary_failure_is_valid=True,
        pin_capability_required=True,
        post_pin_reparse_required=True,
        verifier_reads_filesystem=False,
        verifier_launches_processes=False,
        verifier_launches_sandbox=False,
        verifier_uses_network=False,
        verifier_executes_candidate_interpreter=False,
        verifier_processes_changed_source=False,
        verifier_authorizes_execution=False,
        reusable_lease_issued=False,
    )
)


def validate_developer_task_execution_compile_ast_verifier_policy(
    policy: DeveloperTaskExecutionCompileAstVerifierPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_V1
    ),
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstVerifierPolicy):
        return ("policy_type_invalid",)
    errors: list[str] = []
    expected = DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_V1
    if policy.schema_version != 1 or policy.policy_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_ID:
        errors.append("policy_identity_invalid")
    if (
        policy.contract_policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT
        or policy.runner_policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT
        or policy.runner_bundle_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT
        or policy.contract_policy_sha256 != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256
        or policy.runner_sha256 != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256
        or policy.payload_sha256 != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256
    ):
        errors.append("trusted_inputs_invalid")
    if policy.operation != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION:
        errors.append("operation_invalid")
    if (
        policy.signature_algorithm != DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_SIGNATURE_ALGORITHM
        or policy.signature_bytes != 64
        or policy.default_crypto_backend != DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_CRYPTO_BACKEND
    ):
        errors.append("crypto_invalid")
    if policy.ready_timing_tolerance_seconds != 1 or policy.terminal_timing_tolerance_seconds != 1:
        errors.append("timing_invalid")
    if not all(
        (
            policy.result_optional_only_for_boundary_failed,
            policy.authentic_syntax_failure_is_valid,
            policy.authentic_boundary_failure_is_valid,
            policy.pin_capability_required,
            policy.post_pin_reparse_required,
        )
    ):
        errors.append("semantics_invalid")
    if any(
        (
            policy.verifier_reads_filesystem,
            policy.verifier_launches_processes,
            policy.verifier_launches_sandbox,
            policy.verifier_uses_network,
            policy.verifier_executes_candidate_interpreter,
            policy.verifier_processes_changed_source,
            policy.verifier_authorizes_execution,
            policy.reusable_lease_issued,
        )
    ):
        errors.append("host_only_boundary_invalid")
    comparable = policy.to_dict()
    expected_comparable = expected.to_dict()
    comparable["fingerprint"] = ""
    expected_comparable["fingerprint"] = ""
    if comparable != expected_comparable:
        errors.append("policy_values_changed")
    if developer_task_execution_compile_ast_verifier_policy_fingerprint(policy) != policy.fingerprint:
        errors.append("policy_fingerprint_mismatch")
    return tuple(errors)
