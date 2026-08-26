from __future__ import annotations

"""Canonical V1C2C2 active compile/AST Sandbox-composition policy.

The Roadmap Change 016 value remains an immutable architecture-slice identity.
This module defines separate, reproducible implementation-policy identities.
"""

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_compile_ast_claim_transaction_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID,
)
from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_SHA256,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
)
from modules.developer.developer_task_execution_compile_ast_runner_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_ID,
)
from modules.developer.developer_task_execution_compile_ast_verifier_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_ID,
)
from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
    RUNTIME_ATTESTATION_POLICY_ID,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
    RUNTIME_LEASE_POLICY_ID,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_TREE_MANIFEST_SHA256,
)


DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_ID = (
    "skynetvs-v1c2c2-active-compile-ast-sandbox-composition-v1"
)
# Filled after the exact semantic payload is frozen.
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_FINGERPRINT = (
    "b4d254963b38caaf1031e85d304eda186eeb784c46ce42af97f0eb3c8c215976"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_BYTES_SHA256 = (
    "fb34f1e7d41f8c5f2ef79a39b8a833c7eb4981769bf1b894f14e7b19b7eddd16"
)

DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_DECISION_ID = (
    "skynetvs-v1c2c-active-compile-ast-composition-split-v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_DECISION_FINGERPRINT = (
    "56bfd2ca196ca2b6d8f6ad426ea06141fe1535a28a281f0d7661bc8e32ee8ff6"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_SLICE = "V1C2C2"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_SLICE_IDENTITY = (
    "d5a6fe191f0bc25d8f3aa708bd36f4383071c50189a070879926382f2075e484"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SOURCE_CONTEXT_SHA256 = (
    "10bbd47cb7809c0e5f152314d06500ea58aaf8dd34fffde391ed284a6bb8f3d4"
)

DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARTIFACT_PREFIX = (
    "skynetvs-compile-ast-composition-"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_READY_FILE_NAME = "ready.json"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_FILE_NAME = "authorize.json"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_AUTHORIZE_COMMIT_FILE_NAME = (
    "authorize.sha256"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_TERMINAL_FILE_NAME = (
    "terminal_payload.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SIGNATURE_FILE_NAME = (
    "terminal_signature.bin"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_BOOTSTRAP_FAILURE_FILE_NAME = (
    "bootstrap_failure.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_CONTROLLER_FAILURE_FILE_NAME = (
    "controller_failure.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_ATTESTED = (
    "active_compile_ast_attested_passed"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED = "failed"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_STATUS_FAILED_ACTIVE = "failed_active"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ACCEPTED_TERMINAL_STATUS = (
    "compile_ast_attested_passed"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLL_INTERVAL_SECONDS = 0.25
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_PROCESS_APPEARANCE_GRACE_SECONDS = 5.0
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_FORCE_CLEANUP_TIMEOUT_SECONDS = 10.0
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_EXIT_EMPTY_SCANS = 3
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_HOST_BOOT_TOLERANCE_SECONDS = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_FAILURE_MAX_BYTES = 64 * 1024


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstCompositionPolicy:
    schema_version: int
    policy_id: str
    policy_fingerprint: str
    architecture_decision_id: str
    architecture_decision_fingerprint: str
    architecture_slice: str
    architecture_slice_identity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "architecture_lock": {
                "decision_id": self.architecture_decision_id,
                "decision_fingerprint": self.architecture_decision_fingerprint,
                "slice": self.architecture_slice,
                "slice_identity": self.architecture_slice_identity,
                "source_context_sha256": (
                    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SOURCE_CONTEXT_SHA256
                ),
            },
            "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
            "public_api": {
                "name": "attest_developer_task_execution_compile_ast_composition",
                "positional": ["host_report", "transaction"],
                "keyword_only": ["artifact_parent"],
                "caller_paths": False,
                "caller_command": False,
                "caller_argv": False,
                "caller_environment": False,
                "caller_timeouts": False,
                "caller_job_limits": False,
                "caller_wsb_settings": False,
                "caller_signature_verifier": False,
                "caller_fault_hooks": False,
            },
            "dependencies": {
                "backend": {
                    "backend_id": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.backend_id,
                    "policy_fingerprint": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
                },
                "claim_transaction": {
                    "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID,
                    "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
                },
                "plan": {
                    "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
                    "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
                },
                "contract": {
                    "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
                    "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
                    "policy_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
                },
                "runner": {
                    "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_ID,
                    "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
                    "bundle_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
                    "runner_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
                    "payload_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
                },
                "verifier": {
                    "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_ID,
                    "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
                    "production_signature_path": "Windows_CNG_ECDSA_P256_SHA256",
                },
                "controller_worker": {
                    "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID,
                    "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
                    "policy_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
                    "bundle_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_FINGERPRINT,
                    "bootstrap_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_SHA256,
                    "controller_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_SHA256,
                    "native_helper_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_SHA256,
                    "wsb_template_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_SHA256,
                },
                "runtime": {
                    "bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
                    "tree_manifest_sha256": RUNTIME_TREE_MANIFEST_SHA256,
                    "file_count": RUNTIME_BUNDLE_FILE_COUNT,
                    "total_bytes": RUNTIME_BUNDLE_TOTAL_BYTES,
                    "lease_policy_id": RUNTIME_LEASE_POLICY_ID,
                    "lease_policy_fingerprint": RUNTIME_LEASE_POLICY_FINGERPRINT,
                    "attestation_policy_id": RUNTIME_ATTESTATION_POLICY_ID,
                    "attestation_policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
                    "attestation_payload_fingerprint": RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
                },
            },
            "claim_order": ["compile_ast_plan", "runtime_lease"],
            "materialization": {
                "runtime": "exact_retained_v1b4b_bundle",
                "sources": "exact_retained_v1c1b_selected_bytes",
                "source_strategy": "flat_sorted_ordinal_files_v1",
                "workspace_mapped": False,
                "git_directory_mapped": False,
                "host_venv_mapped": False,
                "host_git_mapped": False,
                "input_read_only": True,
                "runtime_read_only": True,
                "control_read_only_in_guest": True,
                "output_writable": True,
            },
            "lifecycle": {
                "one_fresh_sandbox": True,
                "ready_timeout_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS,
                "authorization_timeout_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS,
                "worker_timeout_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
                "shutdown_grace_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS,
                "poll_interval_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLL_INTERVAL_SECONDS,
                "process_appearance_grace_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_PROCESS_APPEARANCE_GRACE_SECONDS,
                "exit_consecutive_empty_scans": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_EXIT_EMPTY_SCANS,
                "success_requires_full_exit": True,
                "success_requires_post_exit_exact_reread": True,
                "forced_cleanup_can_succeed": False,
            },
            "controller_evidence_transport": {
                "architecture_decision_id": (
                    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID
                ),
                "architecture_decision_fingerprint": (
                    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT
                ),
                "key": "ephemeral_controller_ecc_key",
                "ready_pinned_before_worker_creation": True,
                "ready_post_exit_stability_required": True,
                "host_transport": "untrusted_writable_wsb_mapping",
                "payload_file": (
                    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME
                ),
                "signature_file": (
                    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME
                ),
                "payload_max_bytes": (
                    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES
                ),
                "terminal_success_signed": True,
                "terminal_failure_signed": True,
                "failure_artifact_authority": "signed_controller_terminal_only",
                "unsigned_guest_artifacts_authoritative": False,
                "worker_may_only_cause_dos": True,
                "legacy_success_terminal_signature_required": True,
                "legacy_v1c2b_transcript_verification_required": True,
                "stable_post_exit_reads": 2,
                "terminal_bindings": [
                    "request_id",
                    "host_nonce",
                    "request_sha256",
                    "ready_sha256",
                    "authorize_sha256",
                    "public_key_sha256",
                    "runtime_bundle_fingerprint",
                    "runtime_lease_fingerprint",
                    "plan_fingerprint",
                    "source_manifest_sha256",
                    "private_result_sha256",
                    "relayed_result_sha256",
                    "terminal_status",
                ],
            },
            "accepted_result": {
                "terminal_status": DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ACCEPTED_TERMINAL_STATUS,
                "boundary_ok": True,
                "check_passed": True,
                "changed_source_processed": True,
                "changed_source_ast_parsed": True,
                "changed_source_compiled": True,
                "changed_code_executed": False,
            },
            "prohibitions": {
                "guest_network_allowed": False,
                "dependency_installation_allowed": False,
                "import_execution_allowed": False,
                "top_level_execution_allowed": False,
                "exec_allowed": False,
                "eval_allowed": False,
                "bytecode_write_allowed": False,
                "arbitrary_shell_allowed": False,
                "host_fallback_allowed": False,
                "python_module_allowed": False,
                "pipeline_allowed": False,
                "commit_merge_push_promotion_allowed": False,
            },
            "result_flags": {
                "changed_code_executed": False,
                "reusable_lease_issued": False,
                "execution_authorized": False,
            },
        }


DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1 = (
    DeveloperTaskExecutionCompileAstCompositionPolicy(
        schema_version=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SCHEMA_VERSION,
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_FINGERPRINT,
        architecture_decision_id=(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_DECISION_ID
        ),
        architecture_decision_fingerprint=(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_DECISION_FINGERPRINT
        ),
        architecture_slice=(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_SLICE
        ),
        architecture_slice_identity=(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_SLICE_IDENTITY
        ),
    )
)


def canonical_developer_task_execution_compile_ast_composition_policy_json(
    policy: DeveloperTaskExecutionCompileAstCompositionPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1
    ),
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstCompositionPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionCompileAstCompositionPolicy")
    return _canonical_json_bytes(policy.to_dict()).decode("utf-8")


def developer_task_execution_compile_ast_composition_policy_fingerprint(
    policy: DeveloperTaskExecutionCompileAstCompositionPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1
    ),
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstCompositionPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionCompileAstCompositionPolicy")
    payload = policy.to_dict().copy()
    payload.pop("policy_fingerprint")
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def developer_task_execution_compile_ast_composition_policy_bytes(
    policy: DeveloperTaskExecutionCompileAstCompositionPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1
    ),
) -> bytes:
    return canonical_developer_task_execution_compile_ast_composition_policy_json(
        policy
    ).encode("utf-8") + b"\n"


def validate_developer_task_execution_compile_ast_composition_policy(
    policy: DeveloperTaskExecutionCompileAstCompositionPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1
    ),
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstCompositionPolicy):
        return ("policy_type_invalid",)
    errors: list[str] = []
    if (
        policy.schema_version
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_SCHEMA_VERSION
        or policy.policy_id
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_ID
        or policy.architecture_decision_id
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_DECISION_ID
        or policy.architecture_decision_fingerprint
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_DECISION_FINGERPRINT
        or policy.architecture_slice
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_SLICE
        or policy.architecture_slice_identity
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_ARCHITECTURE_SLICE_IDENTITY
    ):
        errors.append("policy_identity_invalid")
    actual_fingerprint = developer_task_execution_compile_ast_composition_policy_fingerprint(
        policy
    )
    if (
        policy.policy_fingerprint
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_FINGERPRINT
        or actual_fingerprint
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_FINGERPRINT
    ):
        errors.append("policy_fingerprint_invalid")
    actual_bytes_sha256 = hashlib.sha256(
        developer_task_execution_compile_ast_composition_policy_bytes(policy)
    ).hexdigest()
    if (
        actual_bytes_sha256
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_BYTES_SHA256
    ):
        errors.append("policy_bytes_invalid")
    payload = policy.to_dict()
    if payload["operation"] != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION:
        errors.append("operation_invalid")
    if payload["claim_order"] != ["compile_ast_plan", "runtime_lease"]:
        errors.append("claim_order_invalid")
    if payload["accepted_result"] != {
        "terminal_status": "compile_ast_attested_passed",
        "boundary_ok": True,
        "check_passed": True,
        "changed_source_processed": True,
        "changed_source_ast_parsed": True,
        "changed_source_compiled": True,
        "changed_code_executed": False,
    }:
        errors.append("accepted_result_invalid")
    if payload["controller_evidence_transport"] != {
        "architecture_decision_id": (
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID
        ),
        "architecture_decision_fingerprint": (
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT
        ),
        "key": "ephemeral_controller_ecc_key",
        "ready_pinned_before_worker_creation": True,
        "ready_post_exit_stability_required": True,
        "host_transport": "untrusted_writable_wsb_mapping",
        "payload_file": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME,
        "signature_file": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME,
        "payload_max_bytes": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES,
        "terminal_success_signed": True,
        "terminal_failure_signed": True,
        "failure_artifact_authority": "signed_controller_terminal_only",
        "unsigned_guest_artifacts_authoritative": False,
        "worker_may_only_cause_dos": True,
        "legacy_success_terminal_signature_required": True,
        "legacy_v1c2b_transcript_verification_required": True,
        "stable_post_exit_reads": 2,
        "terminal_bindings": [
            "request_id",
            "host_nonce",
            "request_sha256",
            "ready_sha256",
            "authorize_sha256",
            "public_key_sha256",
            "runtime_bundle_fingerprint",
            "runtime_lease_fingerprint",
            "plan_fingerprint",
            "source_manifest_sha256",
            "private_result_sha256",
            "relayed_result_sha256",
            "terminal_status",
        ],
    }:
        errors.append("controller_evidence_transport_invalid")
    if any(payload["prohibitions"].values()):
        errors.append("prohibitions_invalid")
    if any(payload["result_flags"].values()):
        errors.append("result_flags_invalid")
    return tuple(errors)


if validate_developer_task_execution_compile_ast_composition_policy():
    raise RuntimeError("V1C2C2 active composition policy self-check failed.")
