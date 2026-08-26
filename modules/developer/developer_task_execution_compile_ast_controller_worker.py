from __future__ import annotations

"""V1C2C1R4 deterministic SYSTEM-controller signed-evidence bundle.

This module constructs immutable controller-worker bytes and provides a host-only
strict verifier for controller-signed evidence transported through an untrusted
writable WSB mapping.  It does not claim a plan or runtime lease, materialize
task/runtime sources, launch Windows Sandbox or execute Python.
"""

import hashlib
import json
import re

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from modules.developer.developer_task_execution_boundary_crypto import (
    DeveloperTaskExecutionBoundaryCryptoError,
    validate_ecdsa_p256_public_blob,
    validate_ecdsa_p256_signature,
    verify_ecdsa_p256_sha256_cng,
)
from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZE_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_TOTAL_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_HOST_OUTPUT_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_TASK_PREFIX,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_USERNAME_PREFIX,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1,
    developer_task_execution_compile_ast_controller_worker_policy_bytes,
    validate_developer_task_execution_compile_ast_controller_worker_policy,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
)
from modules.developer.developer_task_execution_compile_ast_runner_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROL_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_INPUT_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME,
)
from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_payload import (
    build_runtime_attestation_bootstrap_script,
    build_runtime_attestation_controller_script,
    build_runtime_attestation_native_helper_source,
    build_runtime_attestation_wsb_template,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_EXPECTED_RUNTIME_FILES,
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
)


# Filled after the exact builders below are frozen.  The module self-checks them
# every time the public bundle is constructed.
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_SHA256 = (
    "7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_SHA256 = (
    "f05437852c9204bcdb0cce70e30989544251070a836f55d748d559f289ddd8e8"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_SHA256 = (
    "75ebefd7c3d6fa06f9176ba4f1c75424940b7e92e3f2cfb4901c656da4326653"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_SHA256 = (
    "3de7527400c576ce9ce75ef58f616622ab52a57426811b193270e292d641c281"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_FINGERPRINT = (
    "6e09456eb4d0c76eef136dd7f1d0c40510932dba6887f738529d19481fb5ead0"
)


class DeveloperTaskExecutionCompileAstControllerWorkerBundleError(ValueError):
    pass


_CONTROLLER_EVIDENCE_FIELDS = (
    "schema_version",
    "evidence_type",
    "implementation_revision",
    "outcome",
    "terminal_status",
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
    "terminal_payload_sha256",
    "failure_stage",
    "failure_type",
    "failure_code",
    "failure_message_sha256",
    "completed_at_utc",
    "changed_code_executed",
    "reusable_lease_issued",
    "execution_authorized",
)
_CONTROLLER_EVIDENCE_SUCCESS_STATUSES = (
    "compile_ast_attested_passed",
    "compile_ast_attested_failed",
    "compile_ast_boundary_failed",
)
_CONTROLLER_EVIDENCE_FAILURE_STATUS = "compile_ast_controller_failed"
_CONTROLLER_EVIDENCE_TYPE = "compile_ast_controller_terminal_v1"
_CONTROLLER_EVIDENCE_REVISION = "V1C2C1R4"
_CONTROLLER_EVIDENCE_RESERVED_ARTIFACTS = frozenset(
    {
        "result.json",
        "terminal_payload.json",
        "terminal_signature.bin",
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME,
    }
)
_HEX_32 = re.compile(r"^[0-9a-f]{32}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?Z$")


def canonical_developer_task_execution_compile_ast_controller_evidence_payload_bytes(
    payload: Mapping[str, Any],
) -> bytes:
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    if tuple(payload.keys()) != _CONTROLLER_EVIDENCE_FIELDS:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_evidence_payload_fields_invalid"
        )
    try:
        data = json.dumps(
            dict(payload),
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_evidence_payload_json_invalid"
        ) from error
    if (
        not data
        or len(data) > DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES
        or data.startswith(b"\xef\xbb\xbf")
        or b"\r" in data
        or data.endswith(b"\n")
    ):
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_evidence_payload_encoding_invalid"
        )
    return data


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstControllerEvidenceExpectation:
    request_id: str
    host_nonce: str
    request_sha256: str
    ready_sha256: str
    authorize_sha256: str
    public_key_sha256: str
    runtime_bundle_fingerprint: str
    runtime_lease_fingerprint: str
    plan_fingerprint: str
    source_manifest_sha256: str


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstControllerEvidenceTransportReport:
    ok: bool
    status: str
    terminal_status: str
    issue_codes: tuple[str, ...]
    signature_valid: bool
    legacy_terminal_signature_valid: bool
    ready_stable: bool
    evidence_stable: bool
    result_stable: bool
    private_relay_hash_bound: bool
    changed_code_executed: bool = False
    reusable_lease_issued: bool = False
    execution_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "terminal_status": self.terminal_status,
            "issue_codes": list(self.issue_codes),
            "signature_valid": self.signature_valid,
            "legacy_terminal_signature_valid": self.legacy_terminal_signature_valid,
            "ready_stable": self.ready_stable,
            "evidence_stable": self.evidence_stable,
            "result_stable": self.result_stable,
            "private_relay_hash_bound": self.private_relay_hash_bound,
            "changed_code_executed": self.changed_code_executed,
            "reusable_lease_issued": self.reusable_lease_issued,
            "execution_authorized": self.execution_authorized,
        }


def _stable_exact_reads(
    reads: Sequence[bytes] | None,
    *,
    issue_code: str,
    issues: list[str],
    required: bool,
) -> tuple[bytes, bool]:
    if reads is None:
        if required:
            issues.append(issue_code)
        return b"", False
    values = tuple(reads)
    if len(values) != 2 or any(not isinstance(value, bytes) for value in values):
        issues.append(issue_code)
        return b"", False
    if not values[0] or values[0] != values[1]:
        issues.append(issue_code)
        return values[0] if values else b"", False
    return values[0], True


def _parse_controller_evidence_payload(
    payload_bytes: bytes,
    issues: list[str],
) -> dict[str, Any]:
    if (
        not payload_bytes
        or len(payload_bytes)
        > DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES
        or payload_bytes.startswith(b"\xef\xbb\xbf")
        or b"\r" in payload_bytes
        or payload_bytes.endswith(b"\n")
    ):
        issues.append("controller_evidence_payload_encoding_invalid")
        return {}
    try:
        text = payload_bytes.decode("utf-8", errors="strict")
        pairs = json.loads(text, object_pairs_hook=lambda value: value)
    except (UnicodeDecodeError, json.JSONDecodeError):
        issues.append("controller_evidence_payload_json_invalid")
        return {}
    if not isinstance(pairs, list) or any(
        not isinstance(item, tuple) or len(item) != 2 for item in pairs
    ):
        issues.append("controller_evidence_payload_object_invalid")
        return {}
    keys = tuple(str(item[0]) for item in pairs)
    if len(set(keys)) != len(keys):
        issues.append("controller_evidence_payload_duplicate_field")
        return {}
    if keys != _CONTROLLER_EVIDENCE_FIELDS:
        issues.append("controller_evidence_payload_fields_invalid")
        return {}
    return {str(key): value for key, value in pairs}


def _parse_legacy_terminal_payload(
    payload_bytes: bytes,
    issues: list[str],
) -> dict[str, Any]:
    if (
        not payload_bytes
        or len(payload_bytes) > DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES
        or payload_bytes.startswith(b"\xef\xbb\xbf")
        or b"\r" in payload_bytes
        or payload_bytes.endswith(b"\n")
    ):
        issues.append("controller_evidence_legacy_terminal_encoding_invalid")
        return {}
    try:
        value = json.loads(payload_bytes.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        issues.append("controller_evidence_legacy_terminal_json_invalid")
        return {}
    if not isinstance(value, dict):
        issues.append("controller_evidence_legacy_terminal_object_invalid")
        return {}
    return value


def verify_developer_task_execution_compile_ast_controller_evidence_transport(
    expectation: DeveloperTaskExecutionCompileAstControllerEvidenceExpectation,
    *,
    public_key_blob: bytes,
    pinned_ready_bytes: bytes,
    post_exit_ready_reads: Sequence[bytes],
    evidence_payload_reads: Sequence[bytes],
    evidence_signature_reads: Sequence[bytes],
    pre_worker_reserved_artifacts: Sequence[str] = (),
    relayed_result_reads: Sequence[bytes] | None = None,
    terminal_payload_reads: Sequence[bytes] | None = None,
    terminal_signature_reads: Sequence[bytes] | None = None,
    signature_verifier: Callable[[bytes, bytes, bytes], bool] | None = None,
) -> DeveloperTaskExecutionCompileAstControllerEvidenceTransportReport:
    if not isinstance(
        expectation,
        DeveloperTaskExecutionCompileAstControllerEvidenceExpectation,
    ):
        raise TypeError(
            "expectation must be DeveloperTaskExecutionCompileAstControllerEvidenceExpectation"
        )
    if not isinstance(public_key_blob, bytes) or not isinstance(
        pinned_ready_bytes, bytes
    ):
        raise TypeError("public_key_blob and pinned_ready_bytes must be bytes")

    issues: list[str] = []
    unexpected_pre_worker = sorted(
        set(str(item) for item in pre_worker_reserved_artifacts).intersection(
            _CONTROLLER_EVIDENCE_RESERVED_ARTIFACTS
        )
    )
    if unexpected_pre_worker:
        issues.append("controller_evidence_precreated_artifact")

    expected_values = {
        "request_id": expectation.request_id,
        "host_nonce": expectation.host_nonce,
        "request_sha256": expectation.request_sha256,
        "ready_sha256": expectation.ready_sha256,
        "authorize_sha256": expectation.authorize_sha256,
        "public_key_sha256": expectation.public_key_sha256,
        "runtime_bundle_fingerprint": expectation.runtime_bundle_fingerprint,
        "runtime_lease_fingerprint": expectation.runtime_lease_fingerprint,
        "plan_fingerprint": expectation.plan_fingerprint,
        "source_manifest_sha256": expectation.source_manifest_sha256,
    }
    for field_name, value in expected_values.items():
        pattern = _HEX_32 if field_name == "request_id" else _HEX_64
        if not isinstance(value, str) or pattern.fullmatch(value) is None:
            issues.append("controller_evidence_expectation_invalid")
            break

    ready_bytes, ready_stable = _stable_exact_reads(
        post_exit_ready_reads,
        issue_code="controller_evidence_ready_mutated",
        issues=issues,
        required=True,
    )
    if ready_bytes != pinned_ready_bytes:
        issues.append("controller_evidence_ready_pin_mismatch")
        ready_stable = False
    if _sha256(pinned_ready_bytes) != expectation.ready_sha256:
        issues.append("controller_evidence_ready_hash_mismatch")
        ready_stable = False

    public_key_valid = True
    try:
        public_key = validate_ecdsa_p256_public_blob(public_key_blob)
    except (TypeError, DeveloperTaskExecutionBoundaryCryptoError):
        issues.append("controller_evidence_public_key_invalid")
        public_key_valid = False
        public_key = None
    if (
        public_key is None
        or public_key.blob_sha256 != expectation.public_key_sha256
    ):
        issues.append("controller_evidence_public_key_mismatch")
        public_key_valid = False

    payload_bytes, payload_stable = _stable_exact_reads(
        evidence_payload_reads,
        issue_code="controller_evidence_payload_mutated",
        issues=issues,
        required=True,
    )
    signature_bytes, signature_stable = _stable_exact_reads(
        evidence_signature_reads,
        issue_code="controller_evidence_signature_mutated",
        issues=issues,
        required=True,
    )
    evidence_stable = payload_stable and signature_stable
    payload = _parse_controller_evidence_payload(payload_bytes, issues)

    terminal_status = str(payload.get("terminal_status", ""))
    if payload:
        if payload.get("schema_version") != 1:
            issues.append("controller_evidence_schema_invalid")
        if payload.get("evidence_type") != _CONTROLLER_EVIDENCE_TYPE:
            issues.append("controller_evidence_type_invalid")
        if payload.get("implementation_revision") != _CONTROLLER_EVIDENCE_REVISION:
            issues.append("controller_evidence_revision_invalid")
        for field_name, expected in expected_values.items():
            if payload.get(field_name) != expected:
                issues.append(f"controller_evidence_{field_name}_mismatch")
        if any(
            payload.get(field_name) is not False
            for field_name in (
                "changed_code_executed",
                "reusable_lease_issued",
                "execution_authorized",
            )
        ):
            issues.append("controller_evidence_forbidden_effect")
        if not isinstance(payload.get("outcome"), str):
            issues.append("controller_evidence_outcome_type_invalid")
        if not isinstance(payload.get("terminal_status"), str):
            issues.append("controller_evidence_terminal_status_type_invalid")
        completed_at = payload.get("completed_at_utc")
        if not isinstance(completed_at, str) or _UTC_TIMESTAMP.fullmatch(completed_at) is None:
            issues.append("controller_evidence_completed_at_invalid")
        for hash_field in (
            "request_sha256",
            "ready_sha256",
            "authorize_sha256",
            "public_key_sha256",
            "runtime_bundle_fingerprint",
            "runtime_lease_fingerprint",
            "plan_fingerprint",
            "source_manifest_sha256",
        ):
            if _HEX_64.fullmatch(str(payload.get(hash_field, ""))) is None:
                issues.append(f"controller_evidence_{hash_field}_invalid")

    signature_valid = False
    if public_key_valid and payload_bytes and signature_bytes:
        try:
            validate_ecdsa_p256_signature(signature_bytes)
            verifier = signature_verifier or verify_ecdsa_p256_sha256_cng
            verified = verifier(public_key_blob, payload_bytes, signature_bytes)
            if not isinstance(verified, bool):
                issues.append("controller_evidence_signature_verifier_invalid")
            else:
                signature_valid = verified
        except (
            TypeError,
            DeveloperTaskExecutionBoundaryCryptoError,
            ValueError,
            RuntimeError,
        ):
            issues.append("controller_evidence_signature_verification_failed")
        if not signature_valid:
            issues.append("controller_evidence_signature_invalid")

    legacy_terminal_signature_valid = False
    result_stable = False
    private_relay_hash_bound = False
    outcome = str(payload.get("outcome", "")) if payload else ""
    if outcome == "success":
        if terminal_status not in _CONTROLLER_EVIDENCE_SUCCESS_STATUSES:
            issues.append("controller_evidence_success_status_invalid")
        private_hash = str(payload.get("private_result_sha256", ""))
        relayed_hash = str(payload.get("relayed_result_sha256", ""))
        terminal_hash = str(payload.get("terminal_payload_sha256", ""))
        result_required = terminal_status != "compile_ast_boundary_failed"
        if result_required:
            if (
                _HEX_64.fullmatch(private_hash) is None
                or _HEX_64.fullmatch(relayed_hash) is None
                or private_hash != relayed_hash
            ):
                issues.append("controller_evidence_private_relay_hash_invalid")
            else:
                private_relay_hash_bound = True
        else:
            if private_hash != "" or relayed_hash != "":
                issues.append("controller_evidence_boundary_result_fields_invalid")
            else:
                private_relay_hash_bound = True
        if _HEX_64.fullmatch(terminal_hash) is None:
            issues.append("controller_evidence_terminal_hash_invalid")
        for field_name in (
            "failure_stage",
            "failure_type",
            "failure_code",
            "failure_message_sha256",
        ):
            if payload.get(field_name) != "":
                issues.append("controller_evidence_success_failure_fields_invalid")
                break

        if result_required:
            relayed_bytes, relayed_stable = _stable_exact_reads(
                relayed_result_reads,
                issue_code="controller_evidence_relayed_result_mutated",
                issues=issues,
                required=True,
            )
            if relayed_bytes and _sha256(relayed_bytes) != relayed_hash:
                issues.append("controller_evidence_relayed_result_hash_mismatch")
        else:
            relayed_bytes = b""
            relayed_stable = True
            if relayed_result_reads is not None and any(relayed_result_reads):
                issues.append("controller_evidence_boundary_result_unexpected")

        terminal_bytes, terminal_stable = _stable_exact_reads(
            terminal_payload_reads,
            issue_code="controller_evidence_terminal_payload_mutated",
            issues=issues,
            required=True,
        )
        terminal_signature, terminal_signature_stable = _stable_exact_reads(
            terminal_signature_reads,
            issue_code="controller_evidence_terminal_signature_mutated",
            issues=issues,
            required=True,
        )
        result_stable = relayed_stable and terminal_stable and terminal_signature_stable
        if terminal_bytes and _sha256(terminal_bytes) != terminal_hash:
            issues.append("controller_evidence_terminal_payload_hash_mismatch")

        legacy = _parse_legacy_terminal_payload(terminal_bytes, issues)
        if legacy:
            legacy_expected = {
                "request_id": expectation.request_id,
                "host_nonce": expectation.host_nonce,
                "request_sha256": expectation.request_sha256,
                "ready_sha256": expectation.ready_sha256,
                "authorize_sha256": expectation.authorize_sha256,
                "public_key_sha256": expectation.public_key_sha256,
                "runtime_bundle_fingerprint": expectation.runtime_bundle_fingerprint,
                "runtime_lease_fingerprint": expectation.runtime_lease_fingerprint,
                "plan_fingerprint": expectation.plan_fingerprint,
                "source_manifest_sha256": expectation.source_manifest_sha256,
                "status": terminal_status,
            }
            for field_name, expected in legacy_expected.items():
                if legacy.get(field_name) != expected:
                    issues.append(f"controller_evidence_legacy_{field_name}_mismatch")
            legacy_result_hash = legacy.get("result_sha256")
            if result_required:
                if legacy_result_hash != relayed_hash:
                    issues.append("controller_evidence_legacy_result_hash_mismatch")
            elif legacy_result_hash is not None:
                issues.append("controller_evidence_legacy_boundary_result_invalid")
            if legacy.get("reusable_lease_issued") is not False or legacy.get("execution_authorized") is not False:
                issues.append("controller_evidence_legacy_forbidden_effect")
            check_payload = legacy.get("check")
            if isinstance(check_payload, dict) and check_payload.get("changed_code_executed") is not False:
                issues.append("controller_evidence_legacy_changed_code_execution")

        if public_key_valid and terminal_bytes and terminal_signature:
            try:
                validate_ecdsa_p256_signature(terminal_signature)
                verifier = signature_verifier or verify_ecdsa_p256_sha256_cng
                verified = verifier(public_key_blob, terminal_bytes, terminal_signature)
                if isinstance(verified, bool):
                    legacy_terminal_signature_valid = verified
                else:
                    issues.append("controller_evidence_legacy_verifier_invalid")
            except (
                TypeError,
                DeveloperTaskExecutionBoundaryCryptoError,
                ValueError,
                RuntimeError,
            ):
                issues.append("controller_evidence_legacy_signature_verification_failed")
            if not legacy_terminal_signature_valid:
                issues.append("controller_evidence_legacy_signature_invalid")
    elif outcome == "failure":
        if terminal_status != _CONTROLLER_EVIDENCE_FAILURE_STATUS:
            issues.append("controller_evidence_failure_status_invalid")
        if any(
            payload.get(field_name) != ""
            for field_name in (
                "private_result_sha256",
                "relayed_result_sha256",
                "terminal_payload_sha256",
            )
        ):
            issues.append("controller_evidence_failure_result_fields_invalid")
        if any(
            not isinstance(payload.get(field_name), str)
            or not str(payload.get(field_name))
            for field_name in ("failure_stage", "failure_type", "failure_code")
        ):
            issues.append("controller_evidence_failure_fields_invalid")
        if _HEX_64.fullmatch(str(payload.get("failure_message_sha256", ""))) is None:
            issues.append("controller_evidence_failure_message_hash_invalid")
        if any(
            reads is not None and any(reads)
            for reads in (
                relayed_result_reads,
                terminal_payload_reads,
                terminal_signature_reads,
            )
        ):
            issues.append("controller_evidence_failure_unsigned_artifact_injection")
        result_stable = True
        private_relay_hash_bound = True
        legacy_terminal_signature_valid = True
    elif payload:
        issues.append("controller_evidence_outcome_invalid")

    unique_issues = tuple(dict.fromkeys(issues))
    ok = not unique_issues
    status = (
        "controller_signed_success"
        if ok and outcome == "success"
        else "controller_signed_failure"
        if ok and outcome == "failure"
        else "failed"
    )
    return DeveloperTaskExecutionCompileAstControllerEvidenceTransportReport(
        ok=ok,
        status=status,
        terminal_status=terminal_status,
        issue_codes=unique_issues,
        signature_valid=signature_valid,
        legacy_terminal_signature_valid=legacy_terminal_signature_valid,
        ready_stable=ready_stable,
        evidence_stable=evidence_stable,
        result_stable=result_stable,
        private_relay_hash_bound=private_relay_hash_bound,
    )


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstControllerWorkerPayload:
    kind: str
    file_name: str
    size_bytes: int
    sha256: str
    _bytes: bytes

    def exact_bytes(self) -> bytes:
        return bytes(self._bytes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "file_name": self.file_name,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }

    def __repr__(self) -> str:
        return (
            "DeveloperTaskExecutionCompileAstControllerWorkerPayload("
            f"kind={self.kind!r}, file_name={self.file_name!r}, "
            f"size_bytes={self.size_bytes!r}, sha256={self.sha256!r})"
        )


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstControllerWorkerBundle:
    bundle_id: str
    bundle_fingerprint: str
    policy_id: str
    policy_fingerprint: str
    architecture_decision_id: str
    architecture_decision_fingerprint: str
    architecture_slice: str
    architecture_slice_identity: str
    operation: str
    policy: DeveloperTaskExecutionCompileAstControllerWorkerPayload
    bootstrap: DeveloperTaskExecutionCompileAstControllerWorkerPayload
    native_helper: DeveloperTaskExecutionCompileAstControllerWorkerPayload
    controller: DeveloperTaskExecutionCompileAstControllerWorkerPayload
    wsb_template: DeveloperTaskExecutionCompileAstControllerWorkerPayload
    runtime_executable: str
    runtime_flags: tuple[str, ...]
    runner_path: str
    working_directory: str
    active_process_limit: int
    process_memory_bytes: int
    job_memory_bytes: int
    kill_on_close: bool
    inherit_handles: bool
    create_suspended: bool
    assign_before_resume: bool
    environment_scrub_prefixes: tuple[str, ...]
    environment_scrub_exact: tuple[str, ...]
    sandbox_launched: bool
    claim_transaction_consumed: bool
    runtime_lease_claimed: bool
    candidate_interpreter_executed: bool
    changed_source_processed: bool
    changed_source_ast_parsed: bool
    changed_source_compiled: bool
    changed_code_executed: bool
    reusable_lease_issued: bool
    execution_authorized: bool

    @property
    def ok(self) -> bool:
        return _bundle_errors(self) == ()

    @property
    def payloads(self) -> tuple[DeveloperTaskExecutionCompileAstControllerWorkerPayload, ...]:
        return (
            self.policy,
            self.bootstrap,
            self.native_helper,
            self.controller,
            self.wsb_template,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "bundle_fingerprint": self.bundle_fingerprint,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "architecture_lock": {
                "decision_id": self.architecture_decision_id,
                "decision_fingerprint": self.architecture_decision_fingerprint,
                "slice": self.architecture_slice,
                "slice_identity": self.architecture_slice_identity,
            },
            "operation": self.operation,
            "payloads": [payload.to_dict() for payload in self.payloads],
            "launch": {
                "runtime_executable": self.runtime_executable,
                "runtime_flags": list(self.runtime_flags),
                "runner_path": self.runner_path,
                "working_directory": self.working_directory,
                "inherit_handles": self.inherit_handles,
                "create_suspended": self.create_suspended,
                "assign_before_resume": self.assign_before_resume,
                "shell": False,
                "caller_arguments": False,
                "caller_environment": False,
            },
            "job": {
                "active_process_limit": self.active_process_limit,
                "process_memory_bytes": self.process_memory_bytes,
                "job_memory_bytes": self.job_memory_bytes,
                "kill_on_close": self.kill_on_close,
                "breakaway_allowed": False,
                "silent_breakaway_allowed": False,
            },
            "environment": {
                "source": "CreateEnvironmentBlock_false",
                "inherit_controller_environment": False,
                "scrub_prefixes": list(self.environment_scrub_prefixes),
                "scrub_exact": list(self.environment_scrub_exact),
            },
            "boundary": {
                "sandbox_launched": self.sandbox_launched,
                "claim_transaction_consumed": self.claim_transaction_consumed,
                "runtime_lease_claimed": self.runtime_lease_claimed,
                "candidate_interpreter_executed": self.candidate_interpreter_executed,
                "changed_source_processed": self.changed_source_processed,
                "changed_source_ast_parsed": self.changed_source_ast_parsed,
                "changed_source_compiled": self.changed_source_compiled,
                "changed_code_executed": self.changed_code_executed,
                "reusable_lease_issued": self.reusable_lease_issued,
                "execution_authorized": self.execution_authorized,
            },
        }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_source_bytes(source: str, *, label: str) -> bytes:
    if not isinstance(source, str):
        raise TypeError(f"{label} source must be text")
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    if not source.endswith("\n"):
        source += "\n"
    data = source.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            f"{label}_canonical_text_invalid"
        )
    return data


def build_developer_task_execution_compile_ast_controller_worker_bootstrap_script() -> bytes:
    source = build_runtime_attestation_bootstrap_script().decode("utf-8", errors="strict")
    replacements = {
        "SkynetVS-V1B4C-": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_TASK_PREFIX,
        "SkynetVS V1B4C one-time SYSTEM runtime controller": (
            "SkynetVS V1C2C1 one-time SYSTEM compile AST controller"
        ),
        "SYSTEM runtime controller task did not start.": (
            "SYSTEM compile AST controller task did not start."
        ),
        "runtime_attestation_bootstrap_failed": (
            "compile_ast_controller_worker_bootstrap_failed"
        ),
    }
    for old, new in replacements.items():
        source = source.replace(old, new)
    if "V1B4C" in source or "runtime_attestation_bootstrap_failed" in source:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "bootstrap_transformation_incomplete"
        )
    return _canonical_source_bytes(source, label="bootstrap")


def _replace_source_section(
    source: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "native_helper_start_marker_missing"
        )
    end = source.find(end_marker, start)
    if end < 0:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "native_helper_end_marker_missing"
        )
    return source[:start] + replacement + source[end:]


def build_developer_task_execution_compile_ast_controller_worker_native_helper_source() -> bytes:
    source = build_runtime_attestation_native_helper_source().decode(
        "utf-8", errors="strict"
    )
    source = source.replace("V1B4CNative", "V1C2C1Native")
    source = source.replace(
        '"svb4c"',
        '"' + DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_USERNAME_PREFIX + '"',
    )
    source = source.replace(
        'info.usri1_comment = "SkynetVS V1B4C trusted runtime worker";',
        'info.usri1_comment = "SkynetVS V1C2C1 compile AST worker";',
    )
    source = source.replace(
        "public const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;",
        "\n".join(
            (
                "public const uint JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008;",
                "    public const uint JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100;",
                "    public const uint JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200;",
                "    public const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;",
                "    public const uint COMPILE_AST_ACTIVE_PROCESS_LIMIT = 1;",
                "    public const ulong COMPILE_AST_PROCESS_MEMORY_BYTES = 536870912UL;",
                "    public const ulong COMPILE_AST_JOB_MEMORY_BYTES = 805306368UL;",
            )
        ),
    )
    source = source.replace(
        "    public bool ProcessInJob;\n}",
        """    public bool ProcessInJob;
    public bool InheritHandles;
    public uint ActiveProcessLimit;
    public ulong ProcessMemoryBytes;
    public ulong JobMemoryBytes;
}
""",
    )


    acl_snapshot_class_anchor = "public sealed class WorkerPasswordSecret : IDisposable\n"
    acl_snapshot_class_source = r'''public sealed class DirectoryAclSnapshot
{
    public string OwnerSid;
    public bool AccessRulesProtected;
    public string RuleMultisetCanonical;
    public string RuleMultisetSha256;
    public int RuleCount;
}

'''
    if acl_snapshot_class_anchor not in source:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "directory_acl_snapshot_class_anchor_missing"
        )
    source = source.replace(
        acl_snapshot_class_anchor,
        acl_snapshot_class_source + acl_snapshot_class_anchor,
        1,
    )

    private_result_public_anchor = r'''    public static void PrepareWorkerResultDirectory(string path, string workerSid)
    {
        ApplyProtectedDirectoryAcl(
            path,
            workerSid,
            FileSystemRights.Write | FileSystemRights.ReadAttributes | FileSystemRights.ReadPermissions | FileSystemRights.Synchronize
        );
    }
'''
    private_result_public_replacement = private_result_public_anchor + r'''

    public static DirectoryAclSnapshot CaptureDirectoryAclSnapshot(string path)
    {
        if (String.IsNullOrEmpty(path) || !Path.IsPathRooted(path)) throw new ArgumentException("Directory path must be absolute.", "path");
        if (!Directory.Exists(path)) throw new DirectoryNotFoundException(path);
        DirectorySecurity security = Directory.GetAccessControl(path, AccessControlSections.Access | AccessControlSections.Owner);
        SecurityIdentifier owner = (SecurityIdentifier)security.GetOwner(typeof(SecurityIdentifier));
        int ruleCount;
        string canonical = BuildAccessRuleMultisetCanonical(security, out ruleCount);
        return new DirectoryAclSnapshot
        {
            OwnerSid = owner.Value,
            AccessRulesProtected = security.AreAccessRulesProtected,
            RuleMultisetCanonical = canonical,
            RuleMultisetSha256 = Sha256Utf8(canonical),
            RuleCount = ruleCount
        };
    }

    public static void AssertDirectoryAclSnapshotUnchanged(string path, DirectoryAclSnapshot expected)
    {
        if (expected == null) throw new ArgumentNullException("expected");
        DirectoryAclSnapshot actual = CaptureDirectoryAclSnapshot(path);
        if (!String.Equals(expected.OwnerSid, actual.OwnerSid, StringComparison.Ordinal)) throw new InvalidOperationException("Mapped output owner changed.");
        if (expected.AccessRulesProtected != actual.AccessRulesProtected) throw new InvalidOperationException("Mapped output access-rule protection changed.");
        if (expected.RuleCount != actual.RuleCount) throw new InvalidOperationException("Mapped output ACL rule count changed.");
        if (!String.Equals(expected.RuleMultisetSha256, actual.RuleMultisetSha256, StringComparison.Ordinal)) throw new InvalidOperationException("Mapped output ACL rule multiset changed.");
        if (!String.Equals(expected.RuleMultisetCanonical, actual.RuleMultisetCanonical, StringComparison.Ordinal)) throw new InvalidOperationException("Mapped output ACL canonical rule multiset changed.");
    }

    public static void AssertPrivateWorkerResultDirectory(string path, string workerSid)
    {
        if (String.IsNullOrEmpty(workerSid)) throw new ArgumentException("Worker SID is required.", "workerSid");
        DirectorySecurity security = Directory.GetAccessControl(path, AccessControlSections.Access | AccessControlSections.Owner);
        SecurityIdentifier systemSid = new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null);
        SecurityIdentifier worker = new SecurityIdentifier(workerSid);
        SecurityIdentifier owner = (SecurityIdentifier)security.GetOwner(typeof(SecurityIdentifier));
        if (!String.Equals(owner.Value, systemSid.Value, StringComparison.Ordinal)) throw new InvalidOperationException("Private worker result owner is not LocalSystem.");
        if (!security.AreAccessRulesProtected) throw new InvalidOperationException("Private worker result ACL is not protected.");
        AuthorizationRuleCollection rules = security.GetAccessRules(true, true, typeof(SecurityIdentifier));
        FileSystemRights workerRights = FileSystemRights.Write | FileSystemRights.ReadAttributes | FileSystemRights.ReadPermissions | FileSystemRights.Synchronize;
        FileSystemAccessRule expectedSystem = new FileSystemAccessRule(systemSid, FileSystemRights.FullControl, InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow);
        FileSystemAccessRule expectedWorker = new FileSystemAccessRule(worker, workerRights, InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit, PropagationFlags.None, AccessControlType.Allow);
        string systemSignature = BuildAccessRuleSignature(expectedSystem);
        string workerSignature = BuildAccessRuleSignature(expectedWorker);
        int systemCount = 0;
        int workerCount = 0;
        int totalCount = 0;
        foreach (AuthorizationRule authorizationRule in rules)
        {
            FileSystemAccessRule rule = authorizationRule as FileSystemAccessRule;
            if (rule == null) throw new InvalidOperationException("Unexpected non-filesystem ACL rule.");
            if (rule.IsInherited) throw new InvalidOperationException("Private worker result ACL contains an inherited rule.");
            string signature = BuildAccessRuleSignature(rule);
            if (String.Equals(signature, systemSignature, StringComparison.Ordinal)) systemCount++;
            else if (String.Equals(signature, workerSignature, StringComparison.Ordinal)) workerCount++;
            else throw new InvalidOperationException("Private worker result ACL contains an unexpected rule.");
            totalCount++;
        }
        if (totalCount != 2 || systemCount != 1 || workerCount != 1) throw new InvalidOperationException("Private worker result ACL is not exact.");
    }

    public static bool ProbeTokenHostOutputWriteDenied(IntPtr token, string directoryPath, string existingFilePath)
    {
        if (token == IntPtr.Zero) throw new ArgumentException("Worker token is required.", "token");
        if (String.IsNullOrEmpty(directoryPath) || !Path.IsPathRooted(directoryPath)) throw new ArgumentException("Directory path must be absolute.", "directoryPath");
        if (String.IsNullOrEmpty(existingFilePath) || !Path.IsPathRooted(existingFilePath)) throw new ArgumentException("Existing file path must be absolute.", "existingFilePath");
        if (!Directory.Exists(directoryPath)) throw new DirectoryNotFoundException(directoryPath);
        if (!File.Exists(existingFilePath)) throw new FileNotFoundException("Existing controller artifact is missing.", existingFilePath);
        string probePath = Path.Combine(directoryPath, ".skynetvs-worker-write-probe-" + Guid.NewGuid().ToString("N") + ".tmp");
        bool created = false;
        bool createDenied = false;
        bool existingWriteDenied = false;
        WindowsImpersonationContext context = null;
        try
        {
            context = WindowsIdentity.Impersonate(token);
            try
            {
                using (FileStream stream = new FileStream(probePath, FileMode.CreateNew, FileAccess.Write, FileShare.None, 1, FileOptions.WriteThrough))
                {
                    created = true;
                    stream.WriteByte(0x5A);
                    stream.Flush(true);
                }
            }
            catch (UnauthorizedAccessException)
            {
                createDenied = true;
            }

            try
            {
                using (FileStream stream = new FileStream(existingFilePath, FileMode.Open, FileAccess.Write, FileShare.Read))
                {
                }
            }
            catch (UnauthorizedAccessException)
            {
                existingWriteDenied = true;
            }
            return createDenied && existingWriteDenied;
        }
        finally
        {
            if (context != null)
            {
                context.Undo();
                context.Dispose();
            }
            if (created && File.Exists(probePath)) File.Delete(probePath);
        }
    }
'''
    if private_result_public_anchor not in source:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "private_result_public_acl_anchor_missing"
        )
    source = source.replace(
        private_result_public_anchor,
        private_result_public_replacement,
        1,
    )

    private_result_private_anchor = "    private static void ApplyProtectedDirectoryAcl(string path, string workerSid, FileSystemRights workerRights)\n"
    private_result_private_helpers = r'''    private static string BuildAccessRuleSignature(FileSystemAccessRule rule)
    {
        SecurityIdentifier identity = rule.IdentityReference as SecurityIdentifier;
        if (identity == null) throw new InvalidOperationException("ACL identity is not a SecurityIdentifier.");
        return identity.Value + "|" +
            ((long)rule.FileSystemRights).ToString() + "|" +
            ((int)rule.InheritanceFlags).ToString() + "|" +
            ((int)rule.PropagationFlags).ToString() + "|" +
            ((int)rule.AccessControlType).ToString() + "|" +
            (rule.IsInherited ? "1" : "0");
    }

    private static string BuildAccessRuleMultisetCanonical(DirectorySecurity security, out int ruleCount)
    {
        Dictionary<string, int> counts = new Dictionary<string, int>(StringComparer.Ordinal);
        AuthorizationRuleCollection rules = security.GetAccessRules(true, true, typeof(SecurityIdentifier));
        ruleCount = 0;
        foreach (AuthorizationRule authorizationRule in rules)
        {
            FileSystemAccessRule rule = authorizationRule as FileSystemAccessRule;
            if (rule == null) throw new InvalidOperationException("Unexpected non-filesystem ACL rule.");
            string signature = BuildAccessRuleSignature(rule);
            int count;
            counts.TryGetValue(signature, out count);
            counts[signature] = count + 1;
            ruleCount++;
        }
        List<string> keys = new List<string>(counts.Keys);
        keys.Sort(StringComparer.Ordinal);
        StringBuilder canonical = new StringBuilder();
        foreach (string key in keys)
        {
            canonical.Append(key);
            canonical.Append("|");
            canonical.Append(counts[key].ToString());
            canonical.Append("\n");
        }
        return canonical.ToString();
    }

    private static string Sha256Utf8(string text)
    {
        byte[] bytes = Encoding.UTF8.GetBytes(text);
        byte[] digest;
        using (SHA256 sha = SHA256.Create()) digest = sha.ComputeHash(bytes);
        StringBuilder value = new StringBuilder(digest.Length * 2);
        foreach (byte item in digest) value.Append(item.ToString("x2"));
        Array.Clear(bytes, 0, bytes.Length);
        Array.Clear(digest, 0, digest.Length);
        return value.ToString();
    }

'''
    if private_result_private_anchor not in source:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "private_result_private_acl_anchor_missing"
        )
    source = source.replace(
        private_result_private_anchor,
        private_result_private_helpers + private_result_private_anchor,
        1,
    )

    launch_replacement = r'''public static WorkerLaunchState LaunchFixedCompileAstWorkerSuspendedInJob(IntPtr token)
    {
        const string runtimeExecutablePath = @"C:\SkynetVSRuntime\python.exe";
        const string runnerPath = @"C:\SkynetVSInput\SkynetVS_V1C2A2_runner.py";
        const string resultRoot = @"C:\SkynetVSOutput";
        if (!File.Exists(runtimeExecutablePath)) throw new FileNotFoundException("Pinned runtime executable is missing.", runtimeExecutablePath);
        if (!File.Exists(runnerPath)) throw new FileNotFoundException("Pinned compile AST runner is missing.", runnerPath);
        if (!Directory.Exists(resultRoot)) throw new DirectoryNotFoundException(resultRoot);

        IntPtr originalEnvironment = IntPtr.Zero;
        IntPtr sanitizedEnvironment = IntPtr.Zero;
        int sanitizedEnvironmentBytes = 0;
        IntPtr job = IntPtr.Zero;
        PROCESS_INFORMATION processInformation = new PROCESS_INFORMATION();
        WorkerLaunchState state = null;
        Exception launchError = null;
        int destroyEnvironmentError = 0;
        try
        {
            sanitizedEnvironment = BuildSanitizedEnvironmentBlock(token, out originalEnvironment, out sanitizedEnvironmentBytes);
            job = CreateJobObjectW(IntPtr.Zero, null);
            if (job == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateJobObjectW failed.");

            JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            limits.BasicLimitInformation.LimitFlags =
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
                JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
                JOB_OBJECT_LIMIT_PROCESS_MEMORY |
                JOB_OBJECT_LIMIT_JOB_MEMORY;
            limits.BasicLimitInformation.ActiveProcessLimit = COMPILE_AST_ACTIVE_PROCESS_LIMIT;
            limits.ProcessMemoryLimit = new UIntPtr(COMPILE_AST_PROCESS_MEMORY_BYTES);
            limits.JobMemoryLimit = new UIntPtr(COMPILE_AST_JOB_MEMORY_BYTES);
            int limitsSize = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
            IntPtr limitsBuffer = Marshal.AllocHGlobal(limitsSize);
            try
            {
                Marshal.StructureToPtr(limits, limitsBuffer, false);
                if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, limitsBuffer, (uint)limitsSize))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "SetInformationJobObject failed.");
                }
            }
            finally
            {
                Marshal.FreeHGlobal(limitsBuffer);
            }

            STARTUPINFO startup = new STARTUPINFO();
            startup.cb = Marshal.SizeOf(typeof(STARTUPINFO));
            uint creationFlags = CREATE_SUSPENDED | CREATE_DEFAULT_ERROR_MODE | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT;
            StringBuilder commandLine = new StringBuilder(BuildFixedCompileAstCommandLine(runtimeExecutablePath, runnerPath));
            const bool inheritHandles = false;
            if (!CreateProcessAsUserW(
                token,
                runtimeExecutablePath,
                commandLine,
                IntPtr.Zero,
                IntPtr.Zero,
                inheritHandles,
                creationFlags,
                sanitizedEnvironment,
                resultRoot,
                ref startup,
                out processInformation))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateProcessAsUserW failed.");
            }

            if (!AssignProcessToJobObject(job, processInformation.hProcess)) throw new Win32Exception(Marshal.GetLastWin32Error(), "AssignProcessToJobObject failed.");
            bool inJob;
            if (!IsProcessInJob(processInformation.hProcess, job, out inJob)) throw new Win32Exception(Marshal.GetLastWin32Error(), "IsProcessInJob failed.");
            if (!inJob) throw new InvalidOperationException("Compile AST worker process is not in the expected Job Object.");

            state = new WorkerLaunchState
            {
                ProcessHandle = processInformation.hProcess,
                ThreadHandle = processInformation.hThread,
                JobHandle = job,
                ProcessId = processInformation.dwProcessId,
                ThreadId = processInformation.dwThreadId,
                CreatedSuspended = true,
                AssignedBeforeResume = true,
                ProcessInJob = true,
                InheritHandles = inheritHandles,
                ActiveProcessLimit = COMPILE_AST_ACTIVE_PROCESS_LIMIT,
                ProcessMemoryBytes = COMPILE_AST_PROCESS_MEMORY_BYTES,
                JobMemoryBytes = COMPILE_AST_JOB_MEMORY_BYTES
            };
        }
        catch (Exception error)
        {
            launchError = error;
        }
        finally
        {
            ZeroAndFreeEnvironmentBlock(sanitizedEnvironment, sanitizedEnvironmentBytes);
            if (originalEnvironment != IntPtr.Zero && !DestroyEnvironmentBlock(originalEnvironment)) destroyEnvironmentError = Marshal.GetLastWin32Error();
        }

        if (launchError != null || destroyEnvironmentError != 0)
        {
            if (processInformation.hProcess != IntPtr.Zero)
            {
                TerminateProcess(processInformation.hProcess, 0xEE);
                WaitForSingleObject(processInformation.hProcess, 5000);
            }
            if (processInformation.hThread != IntPtr.Zero) CloseHandle(processInformation.hThread);
            if (processInformation.hProcess != IntPtr.Zero) CloseHandle(processInformation.hProcess);
            if (job != IntPtr.Zero) CloseHandle(job);
            if (launchError != null) throw launchError;
            throw new Win32Exception(destroyEnvironmentError, "DestroyEnvironmentBlock failed.");
        }

        return state;
    }

    public static uint ResumeCompileAstWorker(IntPtr threadHandle)
    {
        uint previous = ResumeThread(threadHandle);
        if (previous == 0xFFFFFFFF) throw new Win32Exception(Marshal.GetLastWin32Error(), "ResumeThread failed.");
        if (previous != 1) throw new InvalidOperationException("Compile AST worker primary thread was not suspended exactly once.");
        return previous;
    }

    '''
    source = _replace_source_section(
        source,
        "public static WorkerLaunchState LaunchFixedRuntimeProbeSuspendedInJob(",
        "public static bool IsPidInSpecificJob(",
        launch_replacement + "public static bool IsPidInSpecificJob(",
    )

    source = source.replace(
        "private static string BuildFixedRuntimeCommandLine(",
        "private static string BuildFixedCompileAstCommandLine(",
    )
    source = source.replace(
        "public static bool IsPidInSpecificJob(public static bool IsPidInSpecificJob(",
        "public static bool IsPidInSpecificJob(",
    )
    forbidden = (
        "V1B4CNative",
        "svb4c",
        "LaunchFixedRuntimeProbeSuspendedInJob",
        "ResumeRuntimeWorker",
        "BuildFixedRuntimeCommandLine",
    )
    if any(marker in source for marker in forbidden):
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "native_helper_transformation_incomplete"
        )
    if (
        "PrepareSharedWorkerOutputDirectory" in source
        or "CaptureDirectoryAclSnapshot" not in source
        or "AssertDirectoryAclSnapshotUnchanged" not in source
        or "AssertPrivateWorkerResultDirectory" not in source
        or "ProbeTokenHostOutputWriteDenied" not in source
    ):
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "guest_local_result_relay_transformation_incomplete"
        )
    return _canonical_source_bytes(source, label="native_helper")


def _runtime_files_powershell_literal() -> str:
    rows: list[str] = []
    for item in RUNTIME_ATTESTATION_EXPECTED_RUNTIME_FILES:
        rows.append(
            '    [ordered]@{ path = "'
            + item.path
            + '"; size_bytes = '
            + str(item.size_bytes)
            + '; sha256 = "'
            + item.sha256
            + '" }'
        )
    return ",\n".join(rows)


def _controller_common_functions() -> str:
    source = build_runtime_attestation_controller_script().decode(
        "utf-8", errors="strict"
    )
    start = source.find("function Write-Utf8Atomic {")
    end = source.find("$cngKey = $null", start)
    if start < 0 or end < 0:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_common_functions_missing"
        )
    return source[start:end]


def build_developer_task_execution_compile_ast_controller_worker_controller_script(
    *,
    native_helper_sha256: str,
) -> bytes:
    if not isinstance(native_helper_sha256, str) or len(native_helper_sha256) != 64:
        raise TypeError("native_helper_sha256 must be a lowercase SHA-256 string")

    expected_runtime_files = _runtime_files_powershell_literal()
    runtime_flags_literal = " ".join(DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS)
    common = _controller_common_functions()
    script = r'''Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BackendId = "@@BACKEND_ID@@"
$BackendPolicyFingerprint = "@@BACKEND_POLICY_FINGERPRINT@@"
$ContractPolicyId = "@@CONTRACT_POLICY_ID@@"
$ContractPolicyFingerprint = "@@CONTRACT_POLICY_FINGERPRINT@@"
$Operation = "@@OPERATION@@"
$ExpectedControllerWorkerPolicySha256 = "@@CONTROLLER_WORKER_POLICY_SHA256@@"
$ExpectedNativeHelperSha256 = "@@NATIVE_HELPER_SHA256@@"
$ExpectedContractPolicySha256 = "@@CONTRACT_POLICY_SHA256@@"
$ExpectedRunnerSha256 = "@@RUNNER_SHA256@@"
$ExpectedPayloadSha256 = "@@PAYLOAD_SHA256@@"
$ExpectedRunnerPolicyFingerprint = "@@RUNNER_POLICY_FINGERPRINT@@"
$ExpectedRunnerBundleFingerprint = "@@RUNNER_BUNDLE_FINGERPRINT@@"
$ExpectedRuntimeAttestationPolicyFingerprint = "@@RUNTIME_ATTESTATION_POLICY_FINGERPRINT@@"
$ExpectedRuntimeAttestationPayloadFingerprint = "@@RUNTIME_ATTESTATION_PAYLOAD_FINGERPRINT@@"
$ExpectedRuntimeBundleFingerprint = "@@RUNTIME_BUNDLE_FINGERPRINT@@"
$ExpectedRuntimeLeasePolicyFingerprint = "@@RUNTIME_LEASE_POLICY_FINGERPRINT@@"
$ExpectedPlanPolicyFingerprint = "@@PLAN_POLICY_FINGERPRINT@@"
$ExpectedRuntimeFileCount = @@RUNTIME_FILE_COUNT@@
$ExpectedRuntimeTotalBytes = @@RUNTIME_TOTAL_BYTES@@
$ExpectedTaskPrefix = "@@TASK_PREFIX@@"
$ExpectedActiveProcessLimit = @@ACTIVE_PROCESS_LIMIT@@
$ExpectedProcessMemoryBytes = @@PROCESS_MEMORY_BYTES@@
$ExpectedJobMemoryBytes = @@JOB_MEMORY_BYTES@@
$ExpectedRuntimeFlags = "@@RUNTIME_FLAGS@@"

$inputRoot = "@@INPUT_ROOT@@"
$sourceRoot = "@@SOURCE_ROOT@@"
$runtimeRoot = "@@RUNTIME_ROOT@@"
$controlRoot = "@@CONTROL_ROOT@@"
$hostOutputRoot = "@@HOST_OUTPUT_ROOT@@"
$workerResultRoot = "@@WORKER_RESULT_ROOT@@"
$requestPath = Join-Path $inputRoot "@@REQUEST_FILE@@"
$sourceManifestPath = Join-Path $inputRoot "@@SOURCE_MANIFEST_FILE@@"
$controllerWorkerPolicyPath = Join-Path $inputRoot "@@CONTROLLER_WORKER_POLICY_FILE@@"
$contractPolicyPath = Join-Path $inputRoot "@@CONTRACT_POLICY_FILE@@"
$bootstrapPath = Join-Path $inputRoot "@@BOOTSTRAP_FILE@@"
$controllerPath = Join-Path $inputRoot "@@CONTROLLER_FILE@@"
$nativeHelperPath = Join-Path $inputRoot "@@NATIVE_HELPER_FILE@@"
$runnerPath = Join-Path $inputRoot "@@RUNNER_FILE@@"
$payloadPath = Join-Path $inputRoot "@@PAYLOAD_FILE@@"
$wsbPath = Join-Path $inputRoot "@@WSB_FILE@@"
$readyPath = Join-Path $hostOutputRoot "ready.json"
$authorizeCommitPath = Join-Path $controlRoot "authorize.sha256"
$hostResultPath = Join-Path $hostOutputRoot "@@RESULT_FILE@@"
$localResultPath = Join-Path $workerResultRoot "@@RESULT_FILE@@"
$terminalPayloadPath = Join-Path $hostOutputRoot "terminal_payload.json"
$terminalSignaturePath = Join-Path $hostOutputRoot "terminal_signature.bin"
$controllerEvidencePayloadPath = Join-Path $hostOutputRoot "@@CONTROLLER_EVIDENCE_PAYLOAD_FILE@@"
$controllerEvidenceSignaturePath = Join-Path $hostOutputRoot "@@CONTROLLER_EVIDENCE_SIGNATURE_FILE@@"
$failurePath = Join-Path $hostOutputRoot "controller_failure.json"
$stage = "request_validation"

$ExpectedRuntimeFiles = @(
@@EXPECTED_RUNTIME_FILES@@
)

@@COMMON_FUNCTIONS@@
function Assert-CompileAstStaticPayload {
    param([object]$Request)
    if ((Get-FileSha256 -Path $controllerWorkerPolicyPath) -cne $ExpectedControllerWorkerPolicySha256) { throw "Controller-worker policy hash mismatch." }
    if ($ExpectedContractPolicySha256 -cne [string]$Request.policy_sha256) { throw "Compile AST contract request policy hash mismatch." }
    if ((Get-FileSha256 -Path $bootstrapPath) -cne [string]$Request.bootstrap_sha256) { throw "Bootstrap file hash mismatch." }
    if ((Get-FileSha256 -Path $controllerPath) -cne [string]$Request.controller_sha256) { throw "Controller file hash mismatch." }
    if ((Get-FileSha256 -Path $nativeHelperPath) -cne $ExpectedNativeHelperSha256) { throw "Native helper hash mismatch." }
    if ($ExpectedNativeHelperSha256 -cne [string]$Request.native_helper_sha256) { throw "Native helper request hash mismatch." }
    if ((Get-FileSha256 -Path $contractPolicyPath) -cne $ExpectedContractPolicySha256) { throw "Compile AST contract policy hash mismatch." }
    if ((Get-FileSha256 -Path $runnerPath) -cne $ExpectedRunnerSha256) { throw "Compile AST runner hash mismatch." }
    if ($ExpectedRunnerSha256 -cne [string]$Request.runner_sha256) { throw "Compile AST runner request hash mismatch." }
    if ((Get-FileSha256 -Path $payloadPath) -cne $ExpectedPayloadSha256) { throw "Compile AST payload hash mismatch." }
    if ($ExpectedPayloadSha256 -cne [string]$Request.payload_sha256) { throw "Compile AST payload request hash mismatch." }
    if ((Get-FileSha256 -Path $wsbPath) -cne [string]$Request.wsb_sha256) { throw "WSB file hash mismatch." }
    return $true
}

function Assert-SourceManifestAndTree {
    param([object]$Request, [byte[]]$ManifestBytes)
    $manifestSha256 = Get-BytesSha256 -Bytes $ManifestBytes
    if ($manifestSha256 -cne [string]$Request.source_manifest_sha256) { throw "Source manifest hash mismatch." }
    $manifestText = [System.Text.UTF8Encoding]::new($false, $true).GetString($ManifestBytes)
    $manifest = $manifestText | ConvertFrom-Json
    if ([int]$manifest.schema_version -ne 1) { throw "Source manifest schema mismatch." }
    if ([string]$manifest.contract_policy_id -cne $ContractPolicyId) { throw "Source manifest contract policy mismatch." }
    if ([string]$manifest.contract_policy_fingerprint -cne $ContractPolicyFingerprint) { throw "Source manifest contract fingerprint mismatch." }
    if ([string]$manifest.operation -cne $Operation) { throw "Source manifest operation mismatch." }
    if ([string]$manifest.request_id -cne [string]$Request.request_id) { throw "Source manifest request ID mismatch." }
    if ([string]$manifest.host_nonce -cne [string]$Request.host_nonce) { throw "Source manifest host nonce mismatch." }
    if ([string]$manifest.plan_policy_fingerprint -cne $ExpectedPlanPolicyFingerprint) { throw "Source manifest plan policy mismatch." }
    if ([string]$manifest.plan_fingerprint -cne [string]$Request.plan_fingerprint) { throw "Source manifest plan fingerprint mismatch." }
    if ([string]$manifest.source_strategy -cne "flat_sorted_ordinal_files_v1") { throw "Source strategy mismatch." }
    if ([string]$manifest.source_root -cne $sourceRoot) { throw "Source root mismatch." }
    if ([bool]$manifest.original_path_used_as_guest_filesystem_path) { throw "Original path cannot be a guest filesystem path." }
    if (-not [bool]$manifest.read_only_mapping) { throw "Source mapping must be read-only." }
    [int]$selectedCount = [int]$manifest.selected_file_count
    [int64]$selectedTotal = [int64]$manifest.selected_total_bytes
    if ($selectedCount -lt 1 -or $selectedCount -gt @@MAX_FILE_COUNT@@) { throw "Selected source count is invalid." }
    if ($selectedCount -ne [int]$Request.selected_file_count) { throw "Selected source count does not match request." }
    if ($selectedTotal -lt 0 -or $selectedTotal -gt @@MAX_TOTAL_BYTES@@) { throw "Selected source total is invalid." }
    if ($selectedTotal -ne [int64]$Request.selected_total_bytes) { throw "Selected source total does not match request." }
    $sources = @($manifest.sources)
    if ($sources.Count -ne $selectedCount) { throw "Source list count mismatch." }
    $actualItems = @(Get-ChildItem -LiteralPath $sourceRoot -Force)
    if ($actualItems.Count -ne $selectedCount) { throw "Source root file count mismatch." }
    [int64]$actualTotal = 0
    for ($index = 0; $index -lt $sources.Count; $index++) {
        $source = $sources[$index]
        $ordinal = $index + 1
        $expectedName = "source-{0:D4}.py" -f $ordinal
        if ([int]$source.ordinal -ne $ordinal) { throw "Source ordinal mismatch." }
        if ([string]$source.guest_file_name -cne $expectedName) { throw "Guest source name mismatch." }
        if ([string]$source.git_mode -cne "100644") { throw "Source mode mismatch." }
        if ([string]$source.encoding -cne "utf-8") { throw "Source encoding mismatch." }
        if ([string]$source.line_endings -cnotin @("lf", "none")) { throw "Source line endings mismatch." }
        [int64]$sizeBytes = [int64]$source.size_bytes
        if ($sizeBytes -lt 0 -or $sizeBytes -gt @@MAX_FILE_BYTES@@) { throw "Source size limit mismatch." }
        $path = Join-Path $sourceRoot $expectedName
        $item = Get-Item -LiteralPath $path -Force
        if ($item.PSIsContainer) { throw "Source tree contains a directory." }
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Source tree contains a reparse point." }
        if ([int64]$item.Length -ne $sizeBytes) { throw "Source file size mismatch." }
        if ((Get-FileSha256 -Path $path) -cne [string]$source.sha256) { throw "Source file hash mismatch." }
        $actualTotal += [int64]$item.Length
    }
    if ($actualTotal -ne $selectedTotal) { throw "Source tree total mismatch." }
    return $manifest
}

function Read-TrustedCompileAstResult {
    param([object]$Request, [object]$Manifest, [string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $bytes = Read-StrictUtf8Bytes -Path $Path -MaximumBytes @@RESULT_MAX_BYTES@@
    if ($bytes.Length -lt 2 -or $bytes[$bytes.Length - 1] -ne 10 -or $bytes[$bytes.Length - 2] -eq 13) { throw "Compile AST result does not have the exact LF terminator." }
    $text = [System.Text.UTF8Encoding]::new($false, $true).GetString($bytes)
    $result = $text | ConvertFrom-Json
    if ([int]$result.schema_version -ne 1) { throw "Compile AST result schema mismatch." }
    if ([string]$result.contract_policy_id -cne $ContractPolicyId) { throw "Compile AST result policy mismatch." }
    if ([string]$result.contract_policy_fingerprint -cne $ContractPolicyFingerprint) { throw "Compile AST result fingerprint mismatch." }
    if ([string]$result.operation -cne $Operation) { throw "Compile AST result operation mismatch." }
    if ([string]$result.request_id -cne [string]$Request.request_id) { throw "Compile AST result request mismatch." }
    if ([string]$result.plan_fingerprint -cne [string]$Request.plan_fingerprint) { throw "Compile AST result plan mismatch." }
    if ([string]$result.source_manifest_sha256 -cne [string]$Request.source_manifest_sha256) { throw "Compile AST result source manifest mismatch." }
    if ([string]$result.runtime_bundle_fingerprint -cne $ExpectedRuntimeBundleFingerprint) { throw "Compile AST result runtime mismatch." }
    if ([string]$result.implementation -cne "CPython") { throw "Compile AST result implementation mismatch." }
    if (@($result.version_info).Count -ne 3 -or [int]$result.version_info[0] -ne 3 -or [int]$result.version_info[1] -ne 13 -or [int]$result.version_info[2] -ne 15) { throw "Compile AST result version mismatch." }
    if ([int]$result.architecture_bits -ne 64) { throw "Compile AST result architecture mismatch." }
    if (([string]$result.machine).ToUpperInvariant() -notin @("AMD64", "X86_64")) { throw "Compile AST result machine mismatch." }
    [int]$selected = [int]$result.selected_file_count
    [int]$processed = [int]$result.processed_file_count
    [int]$passed = [int]$result.passed_file_count
    [int]$failed = [int]$result.failed_file_count
    if ($selected -ne [int]$Request.selected_file_count -or $selected -ne [int]$Manifest.selected_file_count) { throw "Compile AST result selected count mismatch." }
    if ($processed -ne $selected -or ($passed + $failed) -ne $selected) { throw "Compile AST result counts mismatch." }
    if (@($result.files).Count -ne $selected) { throw "Compile AST result file list mismatch." }
    if (-not [bool]$result.trusted_interpreter_executed -or -not [bool]$result.changed_source_processed) { throw "Compile AST result interpreter evidence is invalid." }
    if ([bool]$result.changed_code_executed -or [bool]$result.imports_executed -or [bool]$result.top_level_executed -or [bool]$result.bytecode_written -or [bool]$result.execution_authorized) { throw "Compile AST result contains forbidden execution evidence." }
    $expectedPassed = ($failed -eq 0)
    if ([bool]$result.check_passed -ne $expectedPassed) { throw "Compile AST result pass state mismatch." }
    return [pscustomobject]@{ Document = $result; Bytes = $bytes; Sha256 = (Get-BytesSha256 -Bytes $bytes) }
}

function Relay-TrustedCompileAstResult {
    param([object]$Evidence)
    if ($null -eq $Evidence) { throw "Trusted local compile AST result is missing." }
    if (Test-Path -LiteralPath $hostResultPath) { throw "Host-observed compile AST result path already exists." }
    Write-BytesAtomic -Path $hostResultPath -Bytes ([byte[]]$Evidence.Bytes)
    $relayedBytes = Read-StrictUtf8Bytes -Path $hostResultPath -MaximumBytes @@RESULT_MAX_BYTES@@
    $relayedSha256 = Get-BytesSha256 -Bytes $relayedBytes
    if ($relayedSha256 -cne [string]$Evidence.Sha256) { throw "Relayed compile AST result hash mismatch." }
    if ($relayedBytes.Length -ne ([byte[]]$Evidence.Bytes).Length) { throw "Relayed compile AST result size mismatch." }
    for ($index = 0; $index -lt $relayedBytes.Length; $index++) {
        if ($relayedBytes[$index] -ne ([byte[]]$Evidence.Bytes)[$index]) { throw "Relayed compile AST result bytes changed." }
    }
    return [pscustomobject]@{ Document = $Evidence.Document; Bytes = $relayedBytes; Sha256 = $relayedSha256 }
}

function Assert-HostTransportReservedArtifactsAbsent {
    param([string]$Phase)
    $reserved = @(
        $hostResultPath,
        $terminalPayloadPath,
        $terminalSignaturePath,
        $controllerEvidencePayloadPath,
        $controllerEvidenceSignaturePath,
        $failurePath
    )
    foreach ($path in $reserved) {
        if (Test-Path -LiteralPath $path) {
            throw ("Untrusted host transport contains a reserved artifact at " + $Phase + ": " + [System.IO.Path]::GetFileName($path))
        }
    }
}

function Assert-ReadyPinStable {
    if (-not (Test-Path -LiteralPath $readyPath -PathType Leaf)) { throw "Pinned ready artifact is missing." }
    if ((Get-FileSha256 -Path $readyPath) -cne $readySha256) { throw "Pinned ready artifact changed after publication." }
}

function Get-TextSha256 {
    param([string]$Text)
    return Get-BytesSha256 -Bytes ([System.Text.UTF8Encoding]::new($false).GetBytes($Text))
}

function Publish-SignedControllerEvidence {
    param(
        [ValidateSet("success", "failure")][string]$Outcome,
        [string]$TerminalStatus,
        [string]$PrivateResultSha256,
        [string]$RelayedResultSha256,
        [string]$TerminalPayloadSha256,
        [string]$FailureStage,
        [string]$FailureType,
        [string]$FailureCode,
        [string]$FailureMessageSha256
    )
    if ($null -eq $ecdsa) { throw "Controller evidence signing key is unavailable." }
    $payload = [ordered]@{
        schema_version = 1
        evidence_type = "compile_ast_controller_terminal_v1"
        implementation_revision = "V1C2C1R4"
        outcome = $Outcome
        terminal_status = $TerminalStatus
        request_id = $requestId
        host_nonce = [string]$request.host_nonce
        request_sha256 = $requestSha256
        ready_sha256 = $readySha256
        authorize_sha256 = $authorizeSha256
        public_key_sha256 = $publicKeySha256
        runtime_bundle_fingerprint = $ExpectedRuntimeBundleFingerprint
        runtime_lease_fingerprint = [string]$request.runtime_lease_fingerprint
        plan_fingerprint = [string]$request.plan_fingerprint
        source_manifest_sha256 = [string]$request.source_manifest_sha256
        private_result_sha256 = $PrivateResultSha256
        relayed_result_sha256 = $RelayedResultSha256
        terminal_payload_sha256 = $TerminalPayloadSha256
        failure_stage = $FailureStage
        failure_type = $FailureType
        failure_code = $FailureCode
        failure_message_sha256 = $FailureMessageSha256
        completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        changed_code_executed = $false
        reusable_lease_issued = $false
        execution_authorized = $false
    }
    $text = $payload | ConvertTo-Json -Depth 8 -Compress
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($text)
    if ($bytes.Length -le 0 -or $bytes.Length -gt @@EVIDENCE_MAX_BYTES@@) { throw "Controller evidence payload size is invalid." }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $digest = $sha.ComputeHash($bytes) }
    finally { $sha.Dispose() }
    $signature = $ecdsa.SignHash($digest)
    if ($signature.Length -ne 64) { throw "Controller evidence signature size is invalid." }
    Write-Utf8Atomic -Path $controllerEvidencePayloadPath -Text $text
    Write-BytesAtomic -Path $controllerEvidenceSignaturePath -Bytes $signature
    $writtenPayload = Read-StrictUtf8Bytes -Path $controllerEvidencePayloadPath -MaximumBytes @@EVIDENCE_MAX_BYTES@@
    $writtenSignature = [System.IO.File]::ReadAllBytes($controllerEvidenceSignaturePath)
    if ((Get-BytesSha256 -Bytes $writtenPayload) -cne (Get-BytesSha256 -Bytes $bytes)) { throw "Controller evidence payload changed after publication." }
    if ((Get-BytesSha256 -Bytes $writtenSignature) -cne (Get-BytesSha256 -Bytes $signature)) { throw "Controller evidence signature changed after publication." }
    return [pscustomobject]@{
        PayloadSha256 = (Get-BytesSha256 -Bytes $writtenPayload)
        SignatureSha256 = (Get-BytesSha256 -Bytes $writtenSignature)
    }
}

$cngKey = $null
$ecdsa = $null
$tokenState = $null
$launchState = $null
$workerUser = ""
$workerSid = ""
$workerAccountCreated = $false
$workerAccountDeleted = $false
$workerSidProcessSetEmpty = $false
$jobClosed = $false
$request = $null
$authorize = $null
$requestId = ""
$requestSha256 = ""
$readySha256 = ""
$authorizeSha256 = ""
$publicKeySha256 = ""
$hostOutputAclSnapshot = $null
$resumePreviousCount = 0
$workerExitCode = [uint32]70
$resultEvidence = $null
$localResultEvidence = $null
$manifest = $null
$privateResultSha256 = ""
$relayedResultSha256 = ""
$terminalPayloadSha256 = ""
$controllerEvidencePublished = $false

try {
    if (Test-Path -LiteralPath $readyPath) { throw "Ready artifact path already exists." }
    Assert-HostTransportReservedArtifactsAbsent -Phase "controller_start"
    $requestBytes = Read-StrictUtf8Bytes -Path $requestPath -MaximumBytes @@REQUEST_MAX_BYTES@@
    $requestSha256 = Get-BytesSha256 -Bytes $requestBytes
    $requestText = [System.Text.UTF8Encoding]::new($false, $true).GetString($requestBytes)
    $request = $requestText | ConvertFrom-Json
    $requestId = [string]$request.request_id
    if ($requestId -cnotmatch "^[0-9a-f]{32}$") { throw "Request ID is invalid." }
    if ([string]$request.host_nonce -cnotmatch "^[0-9a-f]{64}$") { throw "Host nonce is invalid." }
    if ([int]$request.schema_version -ne 1) { throw "Request schema mismatch." }
    if ([string]$request.backend_id -cne $BackendId) { throw "Backend ID mismatch." }
    if ([string]$request.backend_policy_fingerprint -cne $BackendPolicyFingerprint) { throw "Backend policy mismatch." }
    if ([string]$request.contract_policy_id -cne $ContractPolicyId) { throw "Contract policy mismatch." }
    if ([string]$request.contract_policy_fingerprint -cne $ContractPolicyFingerprint) { throw "Contract policy fingerprint mismatch." }
    if ([string]$request.operation -cne $Operation) { throw "Operation mismatch." }
    if ([int]$request.ready_timeout_seconds -ne 120 -or [int]$request.authorization_timeout_seconds -ne 90 -or [int]$request.worker_timeout_seconds -ne 60 -or [int]$request.shutdown_grace_seconds -ne 45) { throw "Request timeout policy mismatch." }
    if ([string]$request.runtime_attestation_policy_fingerprint -cne $ExpectedRuntimeAttestationPolicyFingerprint) { throw "Runtime attestation policy mismatch." }
    if ([string]$request.runtime_bundle_fingerprint -cne $ExpectedRuntimeBundleFingerprint) { throw "Runtime bundle mismatch." }
    if ([string]$request.runtime_lease_policy_fingerprint -cne $ExpectedRuntimeLeasePolicyFingerprint) { throw "Runtime lease policy mismatch." }
    if ([string]$request.runtime_lease_fingerprint -cnotmatch "^[0-9a-f]{64}$") { throw "Runtime lease fingerprint is invalid." }
    if ([string]$request.plan_policy_fingerprint -cne $ExpectedPlanPolicyFingerprint) { throw "Plan policy mismatch." }
    if ([string]$request.plan_fingerprint -cnotmatch "^[0-9a-f]{64}$") { throw "Plan fingerprint is invalid." }
    if ([string]$request.source_manifest_sha256 -cnotmatch "^[0-9a-f]{64}$") { throw "Source manifest identity is invalid." }
    if ([int]$request.selected_file_count -lt 1 -or [int]$request.selected_file_count -gt @@MAX_FILE_COUNT@@) { throw "Selected file count is invalid." }
    if ([int64]$request.selected_total_bytes -lt 0 -or [int64]$request.selected_total_bytes -gt @@MAX_TOTAL_BYTES@@) { throw "Selected byte total is invalid." }
    if ([string]$request.trusted_scope -cne "compile_ast_changed_python_only_v1" -or [bool]$request.execution_authorized) { throw "Request scope is invalid." }

    $requestIdentityVerified = Assert-CompileAstStaticPayload -Request $request
    $sourceManifestBytes = Read-StrictUtf8Bytes -Path $sourceManifestPath -MaximumBytes @@SOURCE_MANIFEST_MAX_BYTES@@
    $manifest = Assert-SourceManifestAndTree -Request $request -ManifestBytes $sourceManifestBytes

    $stage = "controller_identity"
    Add-Type -Path $nativeHelperPath -ErrorAction Stop
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    $controllerSid = [string]$identity.User.Value
    $controllerName = [string]$identity.Name
    $controllerIsSystem = ($controllerSid -eq "S-1-5-18")
    $controllerIsAdmin = $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
    $controllerIntegrityRid = [V1C2C1Native]::GetCurrentIntegrityRid()
    $expectedTaskName = $ExpectedTaskPrefix + $requestId.Substring(0, 8)
    $bootstrapTaskDeleted = Remove-BootstrapTask -TaskName $expectedTaskName

    $cngKey = [V1C2C1Native]::CreateEphemeralEcdsaP256SigningKey()
    $ecdsa = [System.Security.Cryptography.ECDsaCng]::new($cngKey)
    $publicBlob = $cngKey.Export([System.Security.Cryptography.CngKeyBlobFormat]::EccPublicBlob)
    $publicKeySha256 = Get-BytesSha256 -Bytes $publicBlob
    $keyIsEphemeral = [bool]$cngKey.IsEphemeral
    $keyName = [string]$cngKey.KeyName
    $keyUniqueName = [string]$cngKey.UniqueName

    $stage = "ready_identity"
    $runtimeIdentityVerified = Assert-RuntimeTree
    $inputWriteBlocked = Test-WriteBlocked -Root $inputRoot -Name "controller_input_write_probe.txt"
    $sourceWriteBlocked = Test-WriteBlocked -Root $sourceRoot -Name "controller_source_write_probe.py"
    $runtimeWriteBlocked = Test-WriteBlocked -Root $runtimeRoot -Name ".skynetvs_controller_runtime_write_probe"
    $controlWriteBlocked = Test-WriteBlocked -Root $controlRoot -Name "controller_control_write_probe.txt"
    $hostOutputAclSnapshot = [V1C2C1Native]::CaptureDirectoryAclSnapshot($hostOutputRoot)
    $outputWritable = Test-OutputWritable -Root $hostOutputRoot
    [V1C2C1Native]::AssertDirectoryAclSnapshotUnchanged($hostOutputRoot, $hostOutputAclSnapshot)

    $readyChecks = [ordered]@{
        controller_is_system = $controllerIsSystem
        controller_is_administrator = $controllerIsAdmin
        controller_integrity_is_system = ($controllerIntegrityRid -ge 0x4000)
        key_is_ephemeral = $keyIsEphemeral
        key_name_empty = [string]::IsNullOrEmpty($keyName)
        key_unique_name_empty = [string]::IsNullOrEmpty($keyUniqueName)
        request_identity_verified = $requestIdentityVerified
        source_manifest_verified = $true
        runtime_identity_verified = $runtimeIdentityVerified
        input_write_blocked = $inputWriteBlocked
        source_write_blocked = $sourceWriteBlocked
        runtime_write_blocked = $runtimeWriteBlocked
        control_write_blocked = $controlWriteBlocked
        output_writable = $outputWritable
    }
    $failedReadyChecks = @($readyChecks.GetEnumerator() | Where-Object { -not [bool]$_.Value } | ForEach-Object { [string]$_.Key })
    if (-not $bootstrapTaskDeleted) { $failedReadyChecks += "bootstrap_task_deleted" }

    $ready = [ordered]@{
        schema_version = 1
        backend_id = $BackendId
        backend_policy_fingerprint = $BackendPolicyFingerprint
        contract_policy_id = $ContractPolicyId
        contract_policy_fingerprint = $ContractPolicyFingerprint
        operation = $Operation
        request_id = $requestId
        host_nonce = [string]$request.host_nonce
        request_sha256 = $requestSha256
        source_manifest_sha256 = [string]$request.source_manifest_sha256
        policy_sha256 = Get-FileSha256 -Path $contractPolicyPath
        bootstrap_sha256 = Get-FileSha256 -Path $bootstrapPath
        controller_sha256 = Get-FileSha256 -Path $controllerPath
        native_helper_sha256 = Get-FileSha256 -Path $nativeHelperPath
        runner_sha256 = Get-FileSha256 -Path $runnerPath
        payload_sha256 = Get-FileSha256 -Path $payloadPath
        wsb_sha256 = Get-FileSha256 -Path $wsbPath
        controller_sid = $controllerSid
        controller_name = $controllerName
        controller_is_system = $controllerIsSystem
        controller_is_administrator = $controllerIsAdmin
        controller_integrity_rid = $controllerIntegrityRid
        key_is_ephemeral = $keyIsEphemeral
        key_name_empty = [string]::IsNullOrEmpty($keyName)
        key_unique_name_empty = [string]::IsNullOrEmpty($keyUniqueName)
        public_key_format = "EccPublicBlob"
        public_key_blob_base64 = [Convert]::ToBase64String($publicBlob)
        public_key_sha256 = $publicKeySha256
        runtime_attestation_policy_fingerprint = $ExpectedRuntimeAttestationPolicyFingerprint
        runtime_bundle_fingerprint = $ExpectedRuntimeBundleFingerprint
        runtime_lease_policy_fingerprint = $ExpectedRuntimeLeasePolicyFingerprint
        runtime_lease_fingerprint = [string]$request.runtime_lease_fingerprint
        plan_policy_fingerprint = $ExpectedPlanPolicyFingerprint
        plan_fingerprint = [string]$request.plan_fingerprint
        input_write_blocked = $inputWriteBlocked
        source_write_blocked = $sourceWriteBlocked
        runtime_write_blocked = $runtimeWriteBlocked
        control_write_blocked = $controlWriteBlocked
        output_writable = $outputWritable
        bootstrap_task_deleted = $bootstrapTaskDeleted
        ready_checks = $readyChecks
        failed_ready_checks = $failedReadyChecks
        created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        overall_ok = ($failedReadyChecks.Count -eq 0)
        execution_authorized = $false
    }
    if (-not [bool]$ready.overall_ok) { throw "Ready evidence failed." }
    $readyText = $ready | ConvertTo-Json -Depth 12 -Compress
    Write-Utf8Atomic -Path $readyPath -Text $readyText
    $readySha256 = Get-FileSha256 -Path $readyPath

    $stage = "authorization"
    $authorizePath = Join-Path $controlRoot "authorize.json"
    $authorizationDeadline = (Get-Date).AddSeconds([int]$request.authorization_timeout_seconds)
    $authorizeBytes = $null
    $authorizationReadError = ""
    while ((Get-Date) -lt $authorizationDeadline) {
        if (Test-Path -LiteralPath $authorizeCommitPath -PathType Leaf) {
            try {
                $commitBytes = Read-StrictUtf8Bytes -Path $authorizeCommitPath -MaximumBytes 64
                if ($commitBytes.Length -ne 64) { throw "Authorization commit size is invalid." }
                $commitText = [System.Text.UTF8Encoding]::new($false, $true).GetString($commitBytes)
                if ($commitText -cnotmatch "^[0-9a-f]{64}$") { throw "Authorization commit hash is invalid." }
                if (-not (Test-Path -LiteralPath $authorizePath -PathType Leaf)) { throw "Authorization data is missing." }
                $candidateBytes = Read-StrictUtf8Bytes -Path $authorizePath -MaximumBytes @@AUTHORIZE_MAX_BYTES@@
                $candidateSha256 = Get-BytesSha256 -Bytes $candidateBytes
                if ($candidateSha256 -cne $commitText) { throw "Authorization commit hash mismatch." }
                $authorizeBytes = $candidateBytes
                $authorizeSha256 = $candidateSha256
                break
            }
            catch { $authorizationReadError = $_.Exception.Message }
        }
        Start-Sleep -Milliseconds 200
    }
    if ($null -eq $authorizeBytes) {
        if ([string]::IsNullOrWhiteSpace($authorizationReadError)) { throw "Authorization was not received." }
        throw ("Authorization was not committed: " + $authorizationReadError)
    }
    $authorizeText = [System.Text.UTF8Encoding]::new($false, $true).GetString($authorizeBytes)
    $authorize = $authorizeText | ConvertFrom-Json
    $nowEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    if ([int]$authorize.schema_version -ne 1) { throw "Authorization schema mismatch." }
    if ([string]$authorize.request_id -cne $requestId) { throw "Authorization request mismatch." }
    if ([string]$authorize.host_nonce -cne [string]$request.host_nonce) { throw "Authorization host nonce mismatch." }
    if ([string]$authorize.request_sha256 -cne $requestSha256) { throw "Authorization request hash mismatch." }
    if ([string]$authorize.ready_sha256 -cne $readySha256) { throw "Authorization ready hash mismatch." }
    if ([string]$authorize.public_key_sha256 -cne $publicKeySha256) { throw "Authorization public key mismatch." }
    if ([string]$authorize.runtime_bundle_fingerprint -cne $ExpectedRuntimeBundleFingerprint) { throw "Authorization runtime bundle mismatch." }
    if ([string]$authorize.runtime_lease_fingerprint -cne [string]$request.runtime_lease_fingerprint) { throw "Authorization runtime lease mismatch." }
    if ([string]$authorize.plan_fingerprint -cne [string]$request.plan_fingerprint) { throw "Authorization plan mismatch." }
    if ([string]$authorize.source_manifest_sha256 -cne [string]$request.source_manifest_sha256) { throw "Authorization source manifest mismatch." }
    if (-not [bool]$authorize.allow_compile_ast -or [bool]$authorize.execution_authorized) { throw "Authorization scope is invalid." }
    if ([int64]$authorize.authorization_deadline_epoch -lt $nowEpoch) { throw "Authorization expired." }

    $stage = "post_authorization_revalidation"
    Assert-CompileAstStaticPayload -Request $request | Out-Null
    Assert-RuntimeTree | Out-Null
    # Source changes after ready are deliberately left for the fixed runner to
    # reject so V1C2C3 can obtain a signed boundary-failure transcript after the
    # standard-user/Job/account cleanup boundary has also been proved.

    $stage = "compile_ast_worker"
    if (Test-Path -LiteralPath $hostResultPath) { throw "Host-observed compile AST result path already exists." }
    if (Test-Path -LiteralPath $workerResultRoot) { throw "Private worker result root already exists." }
    $workerUser = [V1C2C1Native]::BuildWorkerUserName($requestId)
    $tokenState = [V1C2C1Native]::CreateFreshStandardUserAndLogon($workerUser)
    $workerAccountCreated = $true
    $workerSid = [string]$tokenState.UserSid
    if ($tokenState.IsAdministrator -or $tokenState.IntegrityRid -ne 8192 -or $tokenState.TokenType -ne 1) { throw "Compile AST worker token boundary mismatch." }
    Assert-ReadyPinStable
    Assert-HostTransportReservedArtifactsAbsent -Phase "before_worker_launch"
    [V1C2C1Native]::AssertDirectoryAclSnapshotUnchanged($hostOutputRoot, $hostOutputAclSnapshot)
    New-Item -ItemType Directory -Path $workerResultRoot -ErrorAction Stop | Out-Null
    [V1C2C1Native]::PrepareWorkerResultDirectory($workerResultRoot, $workerSid)
    [V1C2C1Native]::AssertPrivateWorkerResultDirectory($workerResultRoot, $workerSid)
    if (Test-Path -LiteralPath $localResultPath) { throw "Private compile AST result path already exists." }

    $launchState = [V1C2C1Native]::LaunchFixedCompileAstWorkerSuspendedInJob($tokenState.TokenHandle)
    if ($launchState.InheritHandles) { throw "Compile AST worker inherited handles." }
    if ([uint32]$launchState.ActiveProcessLimit -ne [uint32]$ExpectedActiveProcessLimit -or [uint64]$launchState.ProcessMemoryBytes -ne [uint64]$ExpectedProcessMemoryBytes -or [uint64]$launchState.JobMemoryBytes -ne [uint64]$ExpectedJobMemoryBytes) { throw "Compile AST Job limits mismatch." }
    $resumePreviousCount = [V1C2C1Native]::ResumeCompileAstWorker($launchState.ThreadHandle)
    [V1C2C1Native]::CloseHandle($launchState.ThreadHandle) | Out-Null
    $launchState.ThreadHandle = [IntPtr]::Zero
    $workerWait = [V1C2C1Native]::WaitForSingleObject($launchState.ProcessHandle, [uint32](@@WORKER_TIMEOUT_SECONDS@@ * 1000))
    if ($workerWait -eq [V1C2C1Native]::WAIT_TIMEOUT) {
        [V1C2C1Native]::CloseHandle($launchState.JobHandle) | Out-Null
        $launchState.JobHandle = [IntPtr]::Zero
        $jobClosed = $true
        [V1C2C1Native]::WaitForSingleObject($launchState.ProcessHandle, 5000) | Out-Null
    }
    elseif ($workerWait -ne [V1C2C1Native]::WAIT_OBJECT_0) { throw "Compile AST worker wait failed." }
    if (-not [V1C2C1Native]::GetExitCodeProcess($launchState.ProcessHandle, [ref]$workerExitCode)) { throw "Compile AST worker exit code could not be read." }
    [V1C2C1Native]::CloseHandle($launchState.ProcessHandle) | Out-Null
    $launchState.ProcessHandle = [IntPtr]::Zero
    if (-not $jobClosed) {
        [V1C2C1Native]::CloseHandle($launchState.JobHandle) | Out-Null
        $launchState.JobHandle = [IntPtr]::Zero
        $jobClosed = $true
    }
    $sweep = [V1C2C1Native]::WaitForWorkerSidQuiescence($workerSid)
    $workerSidProcessSetEmpty = ($sweep.MatchingProcessIds.Length -eq 0 -and $sweep.ConsecutiveEmptyScans -ge 3)
    if (-not $workerSidProcessSetEmpty) { throw "Compile AST worker SID process set is not empty." }
    [V1C2C1Native]::DeleteLocalUserExact($workerUser, $workerSid)
    $workerAccountDeleted = $true
    Assert-ReadyPinStable
    Assert-HostTransportReservedArtifactsAbsent -Phase "after_worker_cleanup"
    if ($workerWait -eq [V1C2C1Native]::WAIT_OBJECT_0 -and $workerExitCode -eq 0) {
        try {
            $localResultEvidence = Read-TrustedCompileAstResult -Request $request -Manifest $manifest -Path $localResultPath
            if ($null -ne $localResultEvidence) {
                $privateResultSha256 = [string]$localResultEvidence.Sha256
                $resultEvidence = Relay-TrustedCompileAstResult -Evidence $localResultEvidence
                $relayedResultSha256 = [string]$resultEvidence.Sha256
            }
        }
        catch {
            $resultEvidence = $null
            $privateResultSha256 = ""
            $relayedResultSha256 = ""
        }
    }
    [V1C2C1Native]::AssertDirectoryAclSnapshotUnchanged($hostOutputRoot, $hostOutputAclSnapshot)
    if (Test-Path -LiteralPath $workerResultRoot) { Remove-Item -LiteralPath $workerResultRoot -Recurse -Force -ErrorAction Stop }

    $stage = "network_and_terminal"
    $ipv4DefaultRoutePresent = Test-DefaultRoute -Family IPv4
    $ipv6DefaultRoutePresent = Test-DefaultRoute -Family IPv6
    $ipv4TcpReachable = Invoke-TcpProbe -AddressFamily ([System.Net.Sockets.AddressFamily]::InterNetwork) -Address "1.1.1.1" -Port 443
    $ipv6TcpReachable = Invoke-TcpProbe -AddressFamily ([System.Net.Sockets.AddressFamily]::InterNetworkV6) -Address "2606:4700:4700::1111" -Port 443
    $shutdownScheduled = Schedule-Shutdown
    if (-not $shutdownScheduled) { throw "Sandbox self-shutdown could not be scheduled." }

    $resultReceived = ($null -ne $resultEvidence)
    $resultDocument = if ($resultReceived) { $resultEvidence.Document } else { $null }
    $resultSha256 = if ($resultReceived) { [string]$resultEvidence.Sha256 } else { $null }
    $processedCount = if ($resultReceived) { [int]$resultDocument.processed_file_count } else { 0 }
    $passedCount = if ($resultReceived) { [int]$resultDocument.passed_file_count } else { 0 }
    $failedCount = if ($resultReceived) { [int]$resultDocument.failed_file_count } else { 0 }
    $boundaryOk = $resultReceived -and ($workerExitCode -eq 0)
    $checkPassed = $boundaryOk -and [bool]$resultDocument.check_passed
    $status = if (-not $boundaryOk) { "compile_ast_boundary_failed" } elseif ($checkPassed) { "compile_ast_attested_passed" } else { "compile_ast_attested_failed" }

    $terminalPayload = [ordered]@{
        schema_version = 1
        backend_id = $BackendId
        backend_policy_fingerprint = $BackendPolicyFingerprint
        contract_policy_id = $ContractPolicyId
        contract_policy_fingerprint = $ContractPolicyFingerprint
        operation = $Operation
        request_id = $requestId
        host_nonce = [string]$request.host_nonce
        authorization_nonce = [string]$authorize.authorization_nonce
        request_sha256 = $requestSha256
        ready_sha256 = $readySha256
        authorize_sha256 = $authorizeSha256
        source_manifest_sha256 = [string]$request.source_manifest_sha256
        result_sha256 = $resultSha256
        policy_sha256 = Get-FileSha256 -Path $contractPolicyPath
        bootstrap_sha256 = Get-FileSha256 -Path $bootstrapPath
        controller_sha256 = Get-FileSha256 -Path $controllerPath
        native_helper_sha256 = Get-FileSha256 -Path $nativeHelperPath
        runner_sha256 = Get-FileSha256 -Path $runnerPath
        payload_sha256 = Get-FileSha256 -Path $payloadPath
        wsb_sha256 = Get-FileSha256 -Path $wsbPath
        public_key_sha256 = $publicKeySha256
        runtime_attestation_policy_fingerprint = $ExpectedRuntimeAttestationPolicyFingerprint
        runtime_bundle_fingerprint = $ExpectedRuntimeBundleFingerprint
        runtime_lease_policy_fingerprint = $ExpectedRuntimeLeasePolicyFingerprint
        runtime_lease_fingerprint = [string]$request.runtime_lease_fingerprint
        plan_policy_fingerprint = $ExpectedPlanPolicyFingerprint
        plan_fingerprint = [string]$request.plan_fingerprint
        controller = [ordered]@{
            sid = $controllerSid
            name = $controllerName
            is_system = $controllerIsSystem
            is_administrator = $controllerIsAdmin
            integrity_rid = $controllerIntegrityRid
            key_is_ephemeral = $keyIsEphemeral
            key_name_empty = [string]::IsNullOrEmpty($keyName)
            key_unique_name_empty = [string]::IsNullOrEmpty($keyUniqueName)
        }
        worker = [ordered]@{
            account_created = $workerAccountCreated
            sid = $workerSid
            created_suspended = [bool]$launchState.CreatedSuspended
            resume_previous_count = [int]$resumePreviousCount
            assigned_before_resume = [bool]$launchState.AssignedBeforeResume
            result_received = $resultReceived
            exit_code = [uint32]$workerExitCode
            is_administrator = [bool]$tokenState.IsAdministrator
            integrity_rid = [int]$tokenState.IntegrityRid
            worker_in_job = [bool]$launchState.ProcessInJob
            active_process_limit = [uint32]$launchState.ActiveProcessLimit
            process_memory_bytes = [uint64]$launchState.ProcessMemoryBytes
            job_memory_bytes = [uint64]$launchState.JobMemoryBytes
            job_closed = $jobClosed
            sid_process_set_empty = $workerSidProcessSetEmpty
            account_deleted = $workerAccountDeleted
        }
        controls = [ordered]@{
            input_write_blocked = $inputWriteBlocked
            source_write_blocked = $sourceWriteBlocked
            runtime_write_blocked = $runtimeWriteBlocked
            control_write_blocked = $controlWriteBlocked
            output_writable = $outputWritable
            ipv4_default_route_present = $ipv4DefaultRoutePresent
            ipv4_external_tcp_reachable = $ipv4TcpReachable
            ipv6_default_route_present = $ipv6DefaultRoutePresent
            ipv6_external_tcp_reachable = $ipv6TcpReachable
        }
        runtime = [ordered]@{
            implementation = "CPython"
            version = @(3, 13, 15)
            architecture_bits = 64
            machine = "AMD64"
            bundle_fingerprint = $ExpectedRuntimeBundleFingerprint
            environment_clean = $true
            pip_absent = $true
            ensurepip_absent = $true
            site_absent = $true
            sys_path_exact = $true
            dont_write_bytecode = $true
        }
        check = [ordered]@{
            result_received = $resultReceived
            result_sha256 = $resultSha256
            selected_file_count = [int]$request.selected_file_count
            processed_file_count = $processedCount
            passed_file_count = $passedCount
            failed_file_count = $failedCount
            trusted_interpreter_executed = $resultReceived
            changed_source_processed = $resultReceived
            changed_source_ast_parsed = $(if ($resultReceived) { [bool]$resultDocument.changed_source_ast_parsed } else { $false })
            changed_source_compiled = $(if ($resultReceived) { [bool]$resultDocument.changed_source_compiled } else { $false })
            changed_code_executed = $false
            imports_executed = $false
            top_level_executed = $false
            bytecode_written = $false
        }
        shutdown = [ordered]@{
            scheduled = $shutdownScheduled
            delay_seconds = 8
        }
        completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        status = $status
        boundary_ok = $boundaryOk
        check_passed = $checkPassed
        reusable_lease_issued = $false
        execution_authorized = $false
    }
    $terminalText = $terminalPayload | ConvertTo-Json -Depth 14 -Compress
    $terminalBytes = [System.Text.UTF8Encoding]::new($false).GetBytes($terminalText)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $terminalDigest = $sha.ComputeHash($terminalBytes) }
    finally { $sha.Dispose() }
    $signatureBytes = $ecdsa.SignHash($terminalDigest)
    Write-Utf8Atomic -Path $terminalPayloadPath -Text $terminalText
    Write-BytesAtomic -Path $terminalSignaturePath -Bytes $signatureBytes
    $terminalPayloadSha256 = Get-BytesSha256 -Bytes $terminalBytes
    Publish-SignedControllerEvidence `
        -Outcome "success" `
        -TerminalStatus $status `
        -PrivateResultSha256 $privateResultSha256 `
        -RelayedResultSha256 $relayedResultSha256 `
        -TerminalPayloadSha256 $terminalPayloadSha256 `
        -FailureStage "" `
        -FailureType "" `
        -FailureCode "" `
        -FailureMessageSha256 "" | Out-Null
    $controllerEvidencePublished = $true
    [V1C2C1Native]::AssertDirectoryAclSnapshotUnchanged($hostOutputRoot, $hostOutputAclSnapshot)
}
catch {
    $caughtError = $_
    $failureStage = $stage
    $failureType = $caughtError.Exception.GetType().FullName
    $failureCode = "compile_ast_controller_worker_stage_failed"
    $failureMessage = [string]$caughtError.Exception.Message
    $failureMessageSha256 = Get-TextSha256 -Text $failureMessage
    try {
        if ($null -ne $launchState -and $launchState.JobHandle -ne [IntPtr]::Zero) {
            [V1C2C1Native]::CloseHandle($launchState.JobHandle) | Out-Null
            $launchState.JobHandle = [IntPtr]::Zero
            $jobClosed = $true
        }
    }
    catch { }
    try {
        if (-not [string]::IsNullOrEmpty($workerSid)) {
            [V1C2C1Native]::WaitForWorkerSidQuiescence($workerSid) | Out-Null
            $workerSidProcessSetEmpty = $true
        }
    }
    catch { }
    try {
        if ($workerAccountCreated -and $workerSidProcessSetEmpty -and -not $workerAccountDeleted) {
            [V1C2C1Native]::DeleteLocalUserExact($workerUser, $workerSid)
            $workerAccountDeleted = $true
        }
    }
    catch { }
    try { if (Test-Path -LiteralPath $workerResultRoot) { Remove-Item -LiteralPath $workerResultRoot -Recurse -Force -ErrorAction Stop } } catch { }
    try { if ($null -ne $hostOutputAclSnapshot) { [V1C2C1Native]::AssertDirectoryAclSnapshotUnchanged($hostOutputRoot, $hostOutputAclSnapshot) } } catch { }
    $failure = [ordered]@{
        schema_version = 1
        request_id = if ($null -ne $request) { [string]$request.request_id } else { "" }
        stage = $failureStage
        error_type = $failureType
        error_code = $failureCode
        error_message = $failureMessage
        error_message_sha256 = $failureMessageSha256
        authoritative = $false
        worker_account_created = $workerAccountCreated
        worker_account_deleted = $workerAccountDeleted
        worker_sid_process_set_empty = $workerSidProcessSetEmpty
        job_closed = $jobClosed
        completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        execution_authorized = $false
    }
    try { Write-Utf8Atomic -Path $failurePath -Text ($failure | ConvertTo-Json -Depth 8 -Compress) } catch { }
    $shutdownScheduled = Schedule-Shutdown
    try {
        if (
            $null -ne $ecdsa -and
            $requestId -cmatch "^[0-9a-f]{32}$" -and
            $requestSha256 -cmatch "^[0-9a-f]{64}$" -and
            $readySha256 -cmatch "^[0-9a-f]{64}$" -and
            $authorizeSha256 -cmatch "^[0-9a-f]{64}$" -and
            $publicKeySha256 -cmatch "^[0-9a-f]{64}$"
        ) {
            Publish-SignedControllerEvidence `
                -Outcome "failure" `
                -TerminalStatus "compile_ast_controller_failed" `
                -PrivateResultSha256 "" `
                -RelayedResultSha256 "" `
                -TerminalPayloadSha256 "" `
                -FailureStage $failureStage `
                -FailureType $failureType `
                -FailureCode $failureCode `
                -FailureMessageSha256 $failureMessageSha256 | Out-Null
            $controllerEvidencePublished = $true
        }
    }
    catch { }
}
finally {
    try { if ($null -ne $launchState -and $launchState.ThreadHandle -ne [IntPtr]::Zero) { [V1C2C1Native]::CloseHandle($launchState.ThreadHandle) | Out-Null } } catch { }
    try { if ($null -ne $launchState -and $launchState.ProcessHandle -ne [IntPtr]::Zero) { [V1C2C1Native]::CloseHandle($launchState.ProcessHandle) | Out-Null } } catch { }
    try { if ($null -ne $launchState -and $launchState.JobHandle -ne [IntPtr]::Zero) { [V1C2C1Native]::CloseHandle($launchState.JobHandle) | Out-Null } } catch { }
    try { if ($null -ne $tokenState -and $tokenState.TokenHandle -ne [IntPtr]::Zero) { [V1C2C1Native]::CloseHandle($tokenState.TokenHandle) | Out-Null } } catch { }
    try { if ($null -ne $ecdsa) { $ecdsa.Dispose() } } catch { }
    try { if ($null -ne $cngKey) { $cngKey.Dispose() } } catch { }
}
'''
    replacements = {
        "@@BACKEND_ID@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1.to_dict()["dependencies"]["backend"]["backend_id"],
        "@@BACKEND_POLICY_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1.to_dict()["dependencies"]["backend"]["policy_fingerprint"],
        "@@CONTRACT_POLICY_ID@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
        "@@CONTRACT_POLICY_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        "@@OPERATION@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        "@@CONTROLLER_WORKER_POLICY_SHA256@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
        "@@NATIVE_HELPER_SHA256@@": native_helper_sha256,
        "@@CONTRACT_POLICY_SHA256@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
        "@@RUNNER_SHA256@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
        "@@PAYLOAD_SHA256@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
        "@@RUNNER_POLICY_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
        "@@RUNNER_BUNDLE_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
        "@@RUNTIME_ATTESTATION_POLICY_FINGERPRINT@@": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
        "@@RUNTIME_ATTESTATION_PAYLOAD_FINGERPRINT@@": RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
        "@@RUNTIME_BUNDLE_FINGERPRINT@@": RUNTIME_BUNDLE_FINGERPRINT,
        "@@RUNTIME_LEASE_POLICY_FINGERPRINT@@": RUNTIME_LEASE_POLICY_FINGERPRINT,
        "@@PLAN_POLICY_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
        "@@RUNTIME_FILE_COUNT@@": str(RUNTIME_BUNDLE_FILE_COUNT),
        "@@RUNTIME_TOTAL_BYTES@@": str(RUNTIME_BUNDLE_TOTAL_BYTES),
        "@@TASK_PREFIX@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_TASK_PREFIX,
        "@@ACTIVE_PROCESS_LIMIT@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT),
        "@@PROCESS_MEMORY_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES),
        "@@JOB_MEMORY_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES),
        "@@RUNTIME_FLAGS@@": runtime_flags_literal,
        "@@INPUT_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_INPUT_ROOT,
        "@@SOURCE_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
        "@@RUNTIME_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_ROOT,
        "@@CONTROL_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROL_ROOT,
        "@@HOST_OUTPUT_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_HOST_OUTPUT_ROOT,
        "@@WORKER_RESULT_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
        "@@REQUEST_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME,
        "@@SOURCE_MANIFEST_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME,
        "@@CONTROLLER_WORKER_POLICY_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME,
        "@@CONTRACT_POLICY_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME,
        "@@BOOTSTRAP_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME,
        "@@CONTROLLER_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME,
        "@@NATIVE_HELPER_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME,
        "@@RUNNER_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME,
        "@@PAYLOAD_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME,
        "@@WSB_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME,
        "@@RESULT_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
        "@@CONTROLLER_EVIDENCE_PAYLOAD_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_PAYLOAD_FILE_NAME,
        "@@CONTROLLER_EVIDENCE_SIGNATURE_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_SIGNATURE_FILE_NAME,
        "@@EVIDENCE_MAX_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_EVIDENCE_MAX_BYTES),
        "@@EXPECTED_RUNTIME_FILES@@": expected_runtime_files,
        "@@COMMON_FUNCTIONS@@": common,
        "@@MAX_FILE_COUNT@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT),
        "@@MAX_FILE_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_BYTES),
        "@@MAX_TOTAL_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_TOTAL_BYTES),
        "@@REQUEST_MAX_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES),
        "@@SOURCE_MANIFEST_MAX_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES),
        "@@AUTHORIZE_MAX_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZE_MAX_BYTES),
        "@@RESULT_MAX_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_MAX_BYTES),
        "@@WORKER_TIMEOUT_SECONDS@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS),
    }
    for token, value in replacements.items():
        script = script.replace(token, value)
    if "@@" in script:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_template_token_unresolved"
        )
    if "WindowsSandbox.exe" in script:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_contains_host_sandbox_launcher"
        )
    return _canonical_source_bytes(script, label="controller")


def build_developer_task_execution_compile_ast_controller_worker_wsb_template() -> bytes:
    data = build_runtime_attestation_wsb_template()
    text = data.decode("utf-8", errors="strict")
    if DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME != "bootstrap.ps1":
        text = text.replace(
            r'\bootstrap.ps1"',
            "\\" + DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME + '"',
        )
    text = text.replace(
        "<SandboxFolder>" + DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT + "</SandboxFolder>",
        "<SandboxFolder>" + DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_HOST_OUTPUT_ROOT + "</SandboxFolder>",
    )
    if "<SandboxFolder>" + DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT + "</SandboxFolder>" in text:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "worker_result_root_must_not_be_mapped"
        )
    return _canonical_source_bytes(text, label="wsb_template")


def _payload(
    kind: str,
    file_name: str,
    data: bytes,
) -> DeveloperTaskExecutionCompileAstControllerWorkerPayload:
    return DeveloperTaskExecutionCompileAstControllerWorkerPayload(
        kind=kind,
        file_name=file_name,
        size_bytes=len(data),
        sha256=_sha256(data),
        _bytes=bytes(data),
    )


def _bundle_fingerprint(
    payloads: tuple[DeveloperTaskExecutionCompileAstControllerWorkerPayload, ...],
) -> str:
    value = {
        "schema_version": 1,
        "bundle_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_ID,
        "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
        "architecture_decision_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT,
        "architecture_slice_identity": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY,
        "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        "payloads": [payload.to_dict() for payload in payloads],
        "runner_bundle_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        "active_process_limit": DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT,
        "process_memory_bytes": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES,
        "job_memory_bytes": DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES,
        "kill_on_close": True,
        "inherit_handles": False,
        "create_suspended": True,
        "assign_before_resume": True,
        "execution_authorized": False,
    }
    return _sha256(_canonical_json_bytes(value))


def build_developer_task_execution_compile_ast_controller_worker_bundle(
) -> DeveloperTaskExecutionCompileAstControllerWorkerBundle:
    policy_errors = validate_developer_task_execution_compile_ast_controller_worker_policy()
    if policy_errors:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_worker_policy_invalid:" + ",".join(policy_errors)
        )
    policy_bytes = developer_task_execution_compile_ast_controller_worker_policy_bytes()
    bootstrap_bytes = build_developer_task_execution_compile_ast_controller_worker_bootstrap_script()
    native_helper_bytes = build_developer_task_execution_compile_ast_controller_worker_native_helper_source()
    controller_bytes = build_developer_task_execution_compile_ast_controller_worker_controller_script(
        native_helper_sha256=_sha256(native_helper_bytes),
    )
    wsb_template_bytes = build_developer_task_execution_compile_ast_controller_worker_wsb_template()
    payloads = (
        _payload(
            "compile_ast_controller_worker_policy",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME,
            policy_bytes,
        ),
        _payload(
            "trusted_bootstrap",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME,
            bootstrap_bytes,
        ),
        _payload(
            "trusted_native_helper",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME,
            native_helper_bytes,
        ),
        _payload(
            "trusted_system_controller",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME,
            controller_bytes,
        ),
        _payload(
            "windows_sandbox_template",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME,
            wsb_template_bytes,
        ),
    )
    bundle = DeveloperTaskExecutionCompileAstControllerWorkerBundle(
        bundle_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_ID,
        bundle_fingerprint=_bundle_fingerprint(payloads),
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
        architecture_decision_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID,
        architecture_decision_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT,
        architecture_slice=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE,
        architecture_slice_identity=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY,
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        policy=payloads[0],
        bootstrap=payloads[1],
        native_helper=payloads[2],
        controller=payloads[3],
        wsb_template=payloads[4],
        runtime_executable=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE,
        runtime_flags=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS,
        runner_path=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH,
        working_directory=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
        active_process_limit=DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT,
        process_memory_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES,
        job_memory_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES,
        kill_on_close=True,
        inherit_handles=False,
        create_suspended=True,
        assign_before_resume=True,
        environment_scrub_prefixes=("PYTHON", "PIP_", "PYLAUNCHER_"),
        environment_scrub_exact=("VIRTUAL_ENV",),
        sandbox_launched=False,
        claim_transaction_consumed=False,
        runtime_lease_claimed=False,
        candidate_interpreter_executed=False,
        changed_source_processed=False,
        changed_source_ast_parsed=False,
        changed_source_compiled=False,
        changed_code_executed=False,
        reusable_lease_issued=False,
        execution_authorized=False,
    )
    errors = _bundle_errors(bundle)
    if errors:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_worker_bundle_invalid:" + ",".join(errors)
        )
    return bundle


def _bundle_errors(
    bundle: DeveloperTaskExecutionCompileAstControllerWorkerBundle,
) -> tuple[str, ...]:
    if not isinstance(bundle, DeveloperTaskExecutionCompileAstControllerWorkerBundle):
        return ("bundle_type_invalid",)
    errors: list[str] = []
    if bundle.bundle_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_ID:
        errors.append("bundle_id_invalid")
    if bundle.policy_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID:
        errors.append("policy_id_invalid")
    if bundle.policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT:
        errors.append("policy_fingerprint_invalid")
    if bundle.architecture_decision_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID or bundle.architecture_decision_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT or bundle.architecture_slice != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE or bundle.architecture_slice_identity != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY:
        errors.append("architecture_lock_invalid")
    if bundle.operation != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION:
        errors.append("operation_invalid")

    expected_hashes = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_SHA256,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_SHA256,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_SHA256,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_SHA256,
    )
    for payload, expected_hash in zip(bundle.payloads, expected_hashes, strict=True):
        data = payload.exact_bytes()
        if payload.size_bytes != len(data) or payload.sha256 != _sha256(data):
            errors.append(payload.kind + "_identity_invalid")
        if payload.sha256 != expected_hash:
            errors.append(payload.kind + "_hash_not_pinned")
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            errors.append(payload.kind + "_utf8_invalid")
        else:
            if data.startswith(b"\xef\xbb\xbf") or b"\r" in data or not text.endswith("\n"):
                errors.append(payload.kind + "_canonical_text_invalid")
    if bundle.bundle_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_FINGERPRINT:
        errors.append("bundle_fingerprint_not_pinned")
    if bundle.bundle_fingerprint != _bundle_fingerprint(bundle.payloads):
        errors.append("bundle_fingerprint_invalid")
    if bundle.runtime_executable != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE or bundle.runtime_flags != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS or bundle.runner_path != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH or bundle.working_directory != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT:
        errors.append("launch_contract_invalid")
    if (
        bundle.active_process_limit != 1
        or bundle.process_memory_bytes != 512 * 1024 * 1024
        or bundle.job_memory_bytes != 768 * 1024 * 1024
        or not bundle.kill_on_close
        or bundle.inherit_handles
        or not bundle.create_suspended
        or not bundle.assign_before_resume
    ):
        errors.append("worker_boundary_invalid")
    if bundle.environment_scrub_prefixes != ("PYTHON", "PIP_", "PYLAUNCHER_") or bundle.environment_scrub_exact != ("VIRTUAL_ENV",):
        errors.append("environment_boundary_invalid")
    if any(
        (
            bundle.sandbox_launched,
            bundle.claim_transaction_consumed,
            bundle.runtime_lease_claimed,
            bundle.candidate_interpreter_executed,
            bundle.changed_source_processed,
            bundle.changed_source_ast_parsed,
            bundle.changed_source_compiled,
            bundle.changed_code_executed,
            bundle.reusable_lease_issued,
            bundle.execution_authorized,
        )
    ):
        errors.append("execution_boundary_invalid")
    return tuple(errors)
