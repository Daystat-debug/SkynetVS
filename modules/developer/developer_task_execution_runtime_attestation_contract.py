from __future__ import annotations

"""Strict immutable JSON contracts for the V1B4 trusted-runtime attestation transcript."""

import base64
import hashlib
import json
import re

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_AUTHORIZATION_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_ID,
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
    RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_RUNTIME_ROOT,
    RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS,
    RUNTIME_ATTESTATION_TRUSTED_SCOPE,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_POLICY_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
    RUNTIME_LOCKED_PTH_SHA256,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_PROBE_SHA256,
    RUNTIME_RUNNER_SHA256,
    RUNTIME_SOURCE_FINGERPRINT,
    RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
    RUNTIME_SOURCE_PYTHON_DLL_SHA256,
    RUNTIME_SOURCE_PYTHON_EXE_SHA256,
    RUNTIME_SOURCE_SHA256,
    RUNTIME_SOURCE_STDLIB_SHA256,
    RUNTIME_TREE_MANIFEST_SHA256,
)


RUNTIME_ATTESTATION_SCHEMA_VERSION = 1
RUNTIME_ATTESTATION_REQUEST_MAX_BYTES = 32 * 1024
RUNTIME_ATTESTATION_READY_MAX_BYTES = 48 * 1024
RUNTIME_ATTESTATION_AUTHORIZE_MAX_BYTES = 16 * 1024
RUNTIME_ATTESTATION_RESULT_MAX_BYTES = 32 * 1024
RUNTIME_ATTESTATION_TERMINAL_MAX_BYTES = 96 * 1024
RUNTIME_ATTESTATION_SIGNATURE_BYTES = 64
RUNTIME_ATTESTATION_PROBE_ID = "skynetvs-v1b4-runtime-probe-v1"

_HEX_32 = re.compile(r"^[0-9a-f]{32}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_SID = re.compile(r"^S-1(?:-[0-9]+)+$")

_REQUEST_FIELDS = (
    "schema_version",
    "backend_id",
    "backend_policy_fingerprint",
    "runtime_attestation_id",
    "runtime_attestation_policy_fingerprint",
    "request_id",
    "host_nonce",
    "created_at_utc",
    "ready_timeout_seconds",
    "authorization_timeout_seconds",
    "runtime_timeout_seconds",
    "shutdown_grace_seconds",
    "policy_sha256",
    "bootstrap_sha256",
    "controller_sha256",
    "native_helper_sha256",
    "wsb_sha256",
    "runtime_source_sha256",
    "runtime_source_fingerprint",
    "runtime_source_provenance_policy_fingerprint",
    "runtime_bundle_policy_fingerprint",
    "runtime_tree_manifest_sha256",
    "runtime_manifest_sha256",
    "runtime_bundle_fingerprint",
    "runtime_file_count",
    "runtime_total_bytes",
    "python_executable_sha256",
    "python_dll_sha256",
    "python_pth_sha256",
    "stdlib_sha256",
    "runtime_probe_sha256",
    "runtime_runner_sha256",
    "launch_contract_fingerprint",
    "trusted_scope",
    "execution_authorized",
)
_READY_FIELDS = (
    "schema_version",
    "backend_id",
    "backend_policy_fingerprint",
    "runtime_attestation_id",
    "runtime_attestation_policy_fingerprint",
    "request_id",
    "host_nonce",
    "request_sha256",
    "policy_sha256",
    "bootstrap_sha256",
    "controller_sha256",
    "native_helper_sha256",
    "wsb_sha256",
    "controller_sid",
    "controller_name",
    "controller_is_system",
    "controller_is_administrator",
    "controller_integrity_rid",
    "key_is_ephemeral",
    "key_name_empty",
    "key_unique_name_empty",
    "public_key_format",
    "public_key_blob_base64",
    "public_key_sha256",
    "runtime_source_sha256",
    "runtime_source_fingerprint",
    "runtime_source_provenance_policy_fingerprint",
    "runtime_bundle_policy_fingerprint",
    "runtime_tree_manifest_sha256",
    "runtime_manifest_sha256",
    "runtime_bundle_fingerprint",
    "runtime_file_count",
    "runtime_total_bytes",
    "python_executable_sha256",
    "python_dll_sha256",
    "python_pth_sha256",
    "stdlib_sha256",
    "runtime_probe_sha256",
    "runtime_runner_sha256",
    "launch_contract_fingerprint",
    "input_write_blocked",
    "runtime_write_blocked",
    "control_write_blocked",
    "output_writable",
    "bootstrap_task_deleted",
    "ready_checks",
    "failed_ready_checks",
    "created_at_utc",
    "overall_ok",
    "execution_authorized",
)
_READY_CHECK_FIELDS = (
    "controller_is_system",
    "controller_is_administrator",
    "controller_integrity_is_system",
    "key_is_ephemeral",
    "key_name_empty",
    "key_unique_name_empty",
    "runtime_identity_verified",
    "input_write_blocked",
    "runtime_write_blocked",
    "control_write_blocked",
    "output_writable",
)
_AUTHORIZE_FIELDS = (
    "schema_version",
    "request_id",
    "host_nonce",
    "request_sha256",
    "ready_sha256",
    "public_key_sha256",
    "runtime_bundle_fingerprint",
    "launch_contract_fingerprint",
    "authorization_nonce",
    "authorization_deadline_epoch",
    "allow_benign_runtime_probe",
    "execution_authorized",
)
_RESULT_FIELDS = (
    "architecture_bits",
    "ensurepip_available",
    "executable_name",
    "execution_authorized",
    "flags",
    "implementation",
    "machine",
    "pip_available",
    "probe_id",
    "python_environment_keys",
    "runtime_root_name",
    "runtime_root_write_blocked",
    "runtime_root_write_error",
    "schema_version",
    "site_imported",
    "sys_path",
    "version_info",
)
_RESULT_FLAG_FIELDS = (
    "dont_write_bytecode",
    "ignore_environment",
    "isolated",
    "no_user_site",
    "safe_path",
    "utf8_mode",
)
_TERMINAL_FIELDS = (
    "schema_version",
    "backend_id",
    "backend_policy_fingerprint",
    "runtime_attestation_id",
    "runtime_attestation_policy_fingerprint",
    "request_id",
    "host_nonce",
    "authorization_nonce",
    "request_sha256",
    "ready_sha256",
    "authorize_sha256",
    "policy_sha256",
    "bootstrap_sha256",
    "controller_sha256",
    "native_helper_sha256",
    "wsb_sha256",
    "runtime_result_sha256",
    "public_key_sha256",
    "runtime_bundle_fingerprint",
    "runtime_tree_manifest_sha256",
    "runtime_manifest_sha256",
    "python_executable_sha256",
    "python_pth_sha256",
    "runtime_probe_sha256",
    "runtime_runner_sha256",
    "launch_contract_fingerprint",
    "controller",
    "worker",
    "controls",
    "runtime",
    "shutdown",
    "completed_at_utc",
    "overall_ok",
    "execution_authorized",
)
_TERMINAL_CONTROLLER_FIELDS = (
    "sid",
    "name",
    "is_system",
    "is_administrator",
    "integrity_rid",
    "key_is_ephemeral",
    "key_name_empty",
    "key_unique_name_empty",
)
_TERMINAL_WORKER_FIELDS = (
    "account_created",
    "sid",
    "created_suspended",
    "resume_previous_count",
    "assigned_before_resume",
    "result_ok",
    "exit_code",
    "is_administrator",
    "integrity_rid",
    "worker_in_job",
    "job_closed",
    "sid_process_set_empty",
    "account_deleted",
)
_TERMINAL_CONTROL_FIELDS = (
    "input_write_blocked",
    "runtime_write_blocked",
    "control_write_blocked",
    "output_writable",
    "ipv4_default_route_present",
    "ipv4_external_tcp_reachable",
    "ipv6_default_route_present",
    "ipv6_external_tcp_reachable",
)
_TERMINAL_RUNTIME_FIELDS = (
    "result_ok",
    "probe_id",
    "implementation",
    "version",
    "architecture_bits",
    "machine",
    "runtime_root_write_blocked",
    "environment_clean",
    "pip_absent",
    "ensurepip_absent",
    "site_absent",
    "sys_path_exact",
)
_TERMINAL_SHUTDOWN_FIELDS = ("scheduled", "delay_seconds")


class DeveloperTaskRuntimeAttestationContractError(ValueError):
    def __init__(self, code: str, message: str, *, field_name: str = "", actual: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.field_name = field_name
        self.actual = actual


@dataclass(frozen=True)
class _FrozenObject:
    items: tuple[tuple[str, Any], ...]


@dataclass(frozen=True)
class _FrozenList:
    items: tuple[Any, ...]


@dataclass(frozen=True)
class DeveloperTaskRuntimeAttestationDocument:
    kind: str
    size_bytes: int
    sha256: str
    canonical_bytes: bytes = field(repr=False)
    _payload: _FrozenObject = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self._payload)

    def field(self, name: str) -> Any:
        return self.to_dict()[name]


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return _FrozenObject(tuple((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, list):
        return _FrozenList(tuple(_freeze(item) for item in value))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, _FrozenObject):
        return {key: _thaw(item) for key, item in value.items}
    if isinstance(value, _FrozenList):
        return [_thaw(item) for item in value.items]
    return value


def _reject_float(value: str) -> None:
    raise DeveloperTaskRuntimeAttestationContractError(
        "runtime_attestation_json_number_invalid",
        "Floating-point JSON values are not allowed.",
        actual=value,
    )


def _reject_constant(value: str) -> None:
    raise DeveloperTaskRuntimeAttestationContractError(
        "runtime_attestation_json_constant_invalid",
        "Non-finite JSON values are not allowed.",
        actual=value,
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DeveloperTaskRuntimeAttestationContractError(
                "runtime_attestation_json_duplicate_field",
                "Duplicate JSON field is not allowed.",
                field_name=key,
            )
        result[key] = value
    return result


def _load_document(
    data: bytes,
    *,
    kind: str,
    max_bytes: int,
    validator: Callable[[dict[str, Any]], None],
    trailing_lf: bool = False,
) -> DeveloperTaskRuntimeAttestationDocument:
    if not isinstance(data, bytes):
        raise TypeError(f"{kind}_bytes must be bytes")
    if not data:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_document_empty",
            "Runtime-attestation JSON document is empty.",
            actual=kind,
        )
    if len(data) > max_bytes:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_document_too_large",
            "Runtime-attestation JSON document exceeds its size limit.",
            actual=f"{kind}:{len(data)}>{max_bytes}",
        )
    if data.startswith(b"\xef\xbb\xbf"):
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_json_bom_forbidden",
            "Runtime-attestation JSON must not contain a UTF-8 BOM.",
            actual=kind,
        )
    body = data[:-1] if trailing_lf and data.endswith(b"\n") else data
    if trailing_lf and (not data.endswith(b"\n") or body.endswith(b"\r")):
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_json_line_ending_invalid",
            "Runtime result must end with exactly one LF byte.",
            actual=kind,
        )
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_json_utf8_invalid",
            "Runtime-attestation JSON is not strict UTF-8.",
            actual=f"{kind}:{exc}",
        ) from exc
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except DeveloperTaskRuntimeAttestationContractError:
        raise
    except json.JSONDecodeError as exc:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_json_invalid",
            "Runtime-attestation JSON is invalid.",
            actual=f"{kind}:{exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_json_not_object",
            "Runtime-attestation JSON must be an object.",
            actual=kind,
        )
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if trailing_lf:
        canonical += b"\n"
    if canonical != data:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_json_not_canonical",
            "Runtime-attestation JSON bytes are not canonical.",
            actual=kind,
        )
    validator(payload)
    return DeveloperTaskRuntimeAttestationDocument(
        kind=kind,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        canonical_bytes=data,
        _payload=_freeze(payload),
    )


def _expect_order(payload: dict[str, Any], fields: tuple[str, ...], section: str) -> None:
    actual = tuple(payload.keys())
    if actual != fields:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_fields_invalid",
            "Runtime-attestation fields or field order are invalid.",
            field_name=section,
            actual=repr(actual),
        )


def _expect_object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_field_type_invalid",
            "Runtime-attestation field must be an object.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    return value


def _expect_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_field_type_invalid",
            "Runtime-attestation field must be an array.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    return value


def _expect_str(value: Any, field_name: str, *, nonempty: bool = True) -> str:
    if type(value) is not str:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_field_type_invalid",
            "Runtime-attestation field must be a string.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    if nonempty and not value:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_field_value_invalid",
            "Runtime-attestation string field must not be empty.",
            field_name=field_name,
        )
    return value


def _expect_bool(value: Any, field_name: str, expected: bool | None = None) -> bool:
    if type(value) is not bool:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_field_type_invalid",
            "Runtime-attestation field must be a boolean.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    if expected is not None and value is not expected:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_field_value_invalid",
            "Runtime-attestation boolean field has an invalid value.",
            field_name=field_name,
            actual=str(value),
        )
    return value


def _expect_int(
    value: Any,
    field_name: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
    expected: int | None = None,
) -> int:
    if type(value) is not int:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_field_type_invalid",
            "Runtime-attestation field must be an integer.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    if expected is not None and value != expected:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_field_value_invalid",
            "Runtime-attestation integer field has an invalid value.",
            field_name=field_name,
            actual=str(value),
        )
    if minimum is not None and value < minimum:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_field_value_invalid",
            "Runtime-attestation integer field is below its minimum.",
            field_name=field_name,
            actual=str(value),
        )
    if maximum is not None and value > maximum:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_field_value_invalid",
            "Runtime-attestation integer field exceeds its maximum.",
            field_name=field_name,
            actual=str(value),
        )
    return value


def _expect_hex(value: Any, field_name: str, pattern: re.Pattern[str]) -> str:
    text = _expect_str(value, field_name)
    if not pattern.fullmatch(text):
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_hex_invalid",
            "Runtime-attestation hexadecimal field is invalid.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_sha256(value: Any, field_name: str, expected: str | None = None) -> str:
    text = _expect_hex(value, field_name, _HEX_64)
    if expected is not None and text != expected:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_identity_mismatch",
            "Runtime-attestation pinned identity does not match.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_sid(value: Any, field_name: str) -> str:
    text = _expect_str(value, field_name)
    if not _SID.fullmatch(text):
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_sid_invalid",
            "Runtime-attestation SID field is invalid.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_utc(value: Any, field_name: str) -> str:
    text = _expect_str(value, field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_datetime_invalid",
            "Runtime-attestation timestamp is invalid.",
            field_name=field_name,
            actual=text,
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_datetime_invalid",
            "Runtime-attestation timestamp must be UTC.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_ecc_public_blob(value: Any, sha256_value: Any) -> bytes:
    encoded = _expect_str(value, "public_key_blob_base64")
    try:
        blob = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_public_key_base64_invalid",
            "Runtime-attestation public key is not strict base64.",
        ) from exc
    if len(blob) != 72 or blob[:4] != b"ECS1" or blob[4:8] != b"\x20\x00\x00\x00":
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_public_key_blob_invalid",
            "Runtime-attestation EccPublicBlob is invalid for P-256.",
            actual=f"size={len(blob)},header={blob[:8].hex()}",
        )
    expected_hash = _expect_sha256(sha256_value, "public_key_sha256")
    actual_hash = hashlib.sha256(blob).hexdigest()
    if actual_hash != expected_hash:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_public_key_hash_mismatch",
            "Runtime-attestation public key hash does not match its blob.",
            actual=actual_hash,
        )
    return blob


def _validate_common_identity(payload: dict[str, Any]) -> None:
    _expect_int(payload["schema_version"], "schema_version", expected=RUNTIME_ATTESTATION_SCHEMA_VERSION)
    if _expect_str(payload["backend_id"], "backend_id") != WINDOWS_SANDBOX_EXECUTION_POLICY_V1.backend_id:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_backend_mismatch", "Unexpected backend identity.")
    _expect_sha256(payload["backend_policy_fingerprint"], "backend_policy_fingerprint", WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint)
    if _expect_str(payload["runtime_attestation_id"], "runtime_attestation_id") != RUNTIME_ATTESTATION_ID:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_id_mismatch", "Unexpected runtime-attestation identity.")
    _expect_sha256(payload["runtime_attestation_policy_fingerprint"], "runtime_attestation_policy_fingerprint", RUNTIME_ATTESTATION_POLICY_FINGERPRINT)
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_hex(payload["host_nonce"], "host_nonce", _HEX_64)


def _validate_runtime_identity(payload: dict[str, Any]) -> None:
    pairs = (
        ("runtime_source_sha256", RUNTIME_SOURCE_SHA256),
        ("runtime_source_fingerprint", RUNTIME_SOURCE_FINGERPRINT),
        ("runtime_source_provenance_policy_fingerprint", RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT),
        ("runtime_bundle_policy_fingerprint", RUNTIME_BUNDLE_POLICY_FINGERPRINT),
        ("runtime_tree_manifest_sha256", RUNTIME_TREE_MANIFEST_SHA256),
        ("runtime_manifest_sha256", RUNTIME_MANIFEST_SHA256),
        ("runtime_bundle_fingerprint", RUNTIME_BUNDLE_FINGERPRINT),
        ("python_executable_sha256", RUNTIME_SOURCE_PYTHON_EXE_SHA256),
        ("python_dll_sha256", RUNTIME_SOURCE_PYTHON_DLL_SHA256),
        ("python_pth_sha256", RUNTIME_LOCKED_PTH_SHA256),
        ("stdlib_sha256", RUNTIME_SOURCE_STDLIB_SHA256),
        ("runtime_probe_sha256", RUNTIME_PROBE_SHA256),
        ("runtime_runner_sha256", RUNTIME_RUNNER_SHA256),
        ("launch_contract_fingerprint", RUNTIME_LAUNCH_CONTRACT_FINGERPRINT),
    )
    for field_name, expected in pairs:
        _expect_sha256(payload[field_name], field_name, expected)
    _expect_int(payload["runtime_file_count"], "runtime_file_count", expected=RUNTIME_BUNDLE_FILE_COUNT)
    _expect_int(payload["runtime_total_bytes"], "runtime_total_bytes", expected=RUNTIME_BUNDLE_TOTAL_BYTES)


def _validate_request(payload: dict[str, Any]) -> None:
    _expect_order(payload, _REQUEST_FIELDS, "request")
    _validate_common_identity(payload)
    _expect_utc(payload["created_at_utc"], "created_at_utc")
    _expect_int(payload["ready_timeout_seconds"], "ready_timeout_seconds", expected=RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS)
    _expect_int(payload["authorization_timeout_seconds"], "authorization_timeout_seconds", expected=RUNTIME_ATTESTATION_AUTHORIZATION_TIMEOUT_SECONDS)
    _expect_int(payload["runtime_timeout_seconds"], "runtime_timeout_seconds", expected=RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS)
    _expect_int(payload["shutdown_grace_seconds"], "shutdown_grace_seconds", expected=RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS)
    for field_name in ("policy_sha256", "bootstrap_sha256", "controller_sha256", "native_helper_sha256", "wsb_sha256"):
        _expect_sha256(payload[field_name], field_name)
    _validate_runtime_identity(payload)
    if _expect_str(payload["trusted_scope"], "trusted_scope") != RUNTIME_ATTESTATION_TRUSTED_SCOPE:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_scope_invalid", "Runtime-attestation trusted scope is invalid.")
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_ready(payload: dict[str, Any]) -> None:
    _expect_order(payload, _READY_FIELDS, "ready")
    _validate_common_identity(payload)
    for field_name in ("request_sha256", "policy_sha256", "bootstrap_sha256", "controller_sha256", "native_helper_sha256", "wsb_sha256"):
        _expect_sha256(payload[field_name], field_name)
    if _expect_sid(payload["controller_sid"], "controller_sid") != "S-1-5-18":
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_controller_identity_invalid", "Ready controller SID is not LocalSystem.")
    _expect_str(payload["controller_name"], "controller_name")
    _expect_bool(payload["controller_is_system"], "controller_is_system", True)
    _expect_bool(payload["controller_is_administrator"], "controller_is_administrator", True)
    _expect_int(payload["controller_integrity_rid"], "controller_integrity_rid", minimum=0x4000)
    _expect_bool(payload["key_is_ephemeral"], "key_is_ephemeral", True)
    _expect_bool(payload["key_name_empty"], "key_name_empty", True)
    _expect_bool(payload["key_unique_name_empty"], "key_unique_name_empty", True)
    if _expect_str(payload["public_key_format"], "public_key_format") != "EccPublicBlob":
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_public_key_format_invalid", "Runtime-attestation public key format is invalid.")
    _expect_ecc_public_blob(payload["public_key_blob_base64"], payload["public_key_sha256"])
    _validate_runtime_identity(payload)
    _expect_bool(payload["input_write_blocked"], "input_write_blocked", True)
    _expect_bool(payload["runtime_write_blocked"], "runtime_write_blocked", True)
    _expect_bool(payload["control_write_blocked"], "control_write_blocked", True)
    _expect_bool(payload["output_writable"], "output_writable", True)
    _expect_bool(payload["bootstrap_task_deleted"], "bootstrap_task_deleted", True)
    checks = _expect_object(payload["ready_checks"], "ready_checks")
    _expect_order(checks, _READY_CHECK_FIELDS, "ready_checks")
    for field_name in _READY_CHECK_FIELDS:
        _expect_bool(checks[field_name], f"ready_checks.{field_name}", True)
    failed = _expect_list(payload["failed_ready_checks"], "failed_ready_checks")
    if failed:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_ready_checks_failed", "Runtime-attestation ready checks are not empty.")
    _expect_utc(payload["created_at_utc"], "created_at_utc")
    _expect_bool(payload["overall_ok"], "overall_ok", True)
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_authorize(payload: dict[str, Any]) -> None:
    _expect_order(payload, _AUTHORIZE_FIELDS, "authorize")
    _expect_int(payload["schema_version"], "schema_version", expected=RUNTIME_ATTESTATION_SCHEMA_VERSION)
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_hex(payload["host_nonce"], "host_nonce", _HEX_64)
    for field_name in ("request_sha256", "ready_sha256", "public_key_sha256"):
        _expect_sha256(payload[field_name], field_name)
    _expect_sha256(payload["runtime_bundle_fingerprint"], "runtime_bundle_fingerprint", RUNTIME_BUNDLE_FINGERPRINT)
    _expect_sha256(payload["launch_contract_fingerprint"], "launch_contract_fingerprint", RUNTIME_LAUNCH_CONTRACT_FINGERPRINT)
    _expect_hex(payload["authorization_nonce"], "authorization_nonce", _HEX_64)
    _expect_int(payload["authorization_deadline_epoch"], "authorization_deadline_epoch", minimum=1)
    _expect_bool(payload["allow_benign_runtime_probe"], "allow_benign_runtime_probe", True)
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_runtime_result(payload: dict[str, Any]) -> None:
    _expect_order(payload, _RESULT_FIELDS, "runtime_result")
    _expect_int(payload["architecture_bits"], "architecture_bits", expected=64)
    _expect_bool(payload["ensurepip_available"], "ensurepip_available", False)
    if _expect_str(payload["executable_name"], "executable_name") != "python.exe":
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_runtime_executable_invalid", "Runtime result executable name is invalid.")
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)
    flags = _expect_object(payload["flags"], "flags")
    _expect_order(flags, _RESULT_FLAG_FIELDS, "runtime_result.flags")
    for field_name in ("dont_write_bytecode", "ignore_environment", "isolated", "no_user_site", "utf8_mode"):
        _expect_int(flags[field_name], f"flags.{field_name}", expected=1)
    _expect_bool(flags["safe_path"], "flags.safe_path", True)
    if _expect_str(payload["implementation"], "implementation") != "CPython":
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_runtime_implementation_invalid", "Runtime implementation is invalid.")
    if _expect_str(payload["machine"], "machine").upper() not in {"AMD64", "X86_64"}:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_runtime_machine_invalid", "Runtime machine identity is invalid.")
    _expect_bool(payload["pip_available"], "pip_available", False)
    if _expect_str(payload["probe_id"], "probe_id") != RUNTIME_ATTESTATION_PROBE_ID:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_probe_id_invalid", "Runtime probe identity is invalid.")
    env_keys = _expect_list(payload["python_environment_keys"], "python_environment_keys")
    if env_keys:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_environment_not_clean", "Runtime worker contains forbidden Python/PIP environment keys.")
    if _expect_str(payload["runtime_root_name"], "runtime_root_name") != RUNTIME_ATTESTATION_RUNTIME_ROOT.rsplit("\\", 1)[-1]:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_runtime_root_invalid", "Runtime root name is invalid.")
    _expect_bool(payload["runtime_root_write_blocked"], "runtime_root_write_blocked", True)
    _expect_str(payload["runtime_root_write_error"], "runtime_root_write_error")
    _expect_int(payload["schema_version"], "schema_version", expected=1)
    _expect_bool(payload["site_imported"], "site_imported", False)
    sys_path = _expect_list(payload["sys_path"], "sys_path")
    expected_sys_path = [RUNTIME_ATTESTATION_RUNTIME_ROOT + r"\python313.zip", RUNTIME_ATTESTATION_RUNTIME_ROOT]
    if sys_path != expected_sys_path:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_sys_path_invalid", "Runtime sys.path is not the exact runtime-local path list.", actual=repr(sys_path))
    version = _expect_list(payload["version_info"], "version_info")
    if version != [3, 13, 15]:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_runtime_version_invalid", "Runtime version is not CPython 3.13.15.", actual=repr(version))


def _validate_terminal(payload: dict[str, Any]) -> None:
    _expect_order(payload, _TERMINAL_FIELDS, "terminal")
    _validate_common_identity(payload)
    _expect_hex(payload["authorization_nonce"], "authorization_nonce", _HEX_64)
    for field_name in (
        "request_sha256", "ready_sha256", "authorize_sha256", "policy_sha256", "bootstrap_sha256",
        "controller_sha256", "native_helper_sha256", "wsb_sha256", "runtime_result_sha256", "public_key_sha256",
    ):
        _expect_sha256(payload[field_name], field_name)
    _expect_sha256(payload["runtime_bundle_fingerprint"], "runtime_bundle_fingerprint", RUNTIME_BUNDLE_FINGERPRINT)
    _expect_sha256(payload["runtime_tree_manifest_sha256"], "runtime_tree_manifest_sha256", RUNTIME_TREE_MANIFEST_SHA256)
    _expect_sha256(payload["runtime_manifest_sha256"], "runtime_manifest_sha256", RUNTIME_MANIFEST_SHA256)
    _expect_sha256(payload["python_executable_sha256"], "python_executable_sha256", RUNTIME_SOURCE_PYTHON_EXE_SHA256)
    _expect_sha256(payload["python_pth_sha256"], "python_pth_sha256", RUNTIME_LOCKED_PTH_SHA256)
    _expect_sha256(payload["runtime_probe_sha256"], "runtime_probe_sha256", RUNTIME_PROBE_SHA256)
    _expect_sha256(payload["runtime_runner_sha256"], "runtime_runner_sha256", RUNTIME_RUNNER_SHA256)
    _expect_sha256(payload["launch_contract_fingerprint"], "launch_contract_fingerprint", RUNTIME_LAUNCH_CONTRACT_FINGERPRINT)

    controller = _expect_object(payload["controller"], "controller")
    _expect_order(controller, _TERMINAL_CONTROLLER_FIELDS, "terminal.controller")
    if _expect_sid(controller["sid"], "controller.sid") != "S-1-5-18":
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_controller_identity_invalid", "Terminal controller SID is not LocalSystem.")
    _expect_str(controller["name"], "controller.name")
    _expect_bool(controller["is_system"], "controller.is_system", True)
    _expect_bool(controller["is_administrator"], "controller.is_administrator", True)
    _expect_int(controller["integrity_rid"], "controller.integrity_rid", minimum=0x4000)
    _expect_bool(controller["key_is_ephemeral"], "controller.key_is_ephemeral", True)
    _expect_bool(controller["key_name_empty"], "controller.key_name_empty", True)
    _expect_bool(controller["key_unique_name_empty"], "controller.key_unique_name_empty", True)

    worker = _expect_object(payload["worker"], "worker")
    _expect_order(worker, _TERMINAL_WORKER_FIELDS, "terminal.worker")
    _expect_bool(worker["account_created"], "worker.account_created", True)
    _expect_sid(worker["sid"], "worker.sid")
    _expect_bool(worker["created_suspended"], "worker.created_suspended", True)
    _expect_int(worker["resume_previous_count"], "worker.resume_previous_count", expected=1)
    _expect_bool(worker["assigned_before_resume"], "worker.assigned_before_resume", True)
    _expect_bool(worker["result_ok"], "worker.result_ok", True)
    _expect_int(worker["exit_code"], "worker.exit_code", expected=0)
    _expect_bool(worker["is_administrator"], "worker.is_administrator", False)
    _expect_int(worker["integrity_rid"], "worker.integrity_rid", expected=0x2000)
    _expect_bool(worker["worker_in_job"], "worker.worker_in_job", True)
    _expect_bool(worker["job_closed"], "worker.job_closed", True)
    _expect_bool(worker["sid_process_set_empty"], "worker.sid_process_set_empty", True)
    _expect_bool(worker["account_deleted"], "worker.account_deleted", True)

    controls = _expect_object(payload["controls"], "controls")
    _expect_order(controls, _TERMINAL_CONTROL_FIELDS, "terminal.controls")
    for field_name in ("input_write_blocked", "runtime_write_blocked", "control_write_blocked", "output_writable"):
        _expect_bool(controls[field_name], f"controls.{field_name}", True)
    for field_name in ("ipv4_default_route_present", "ipv4_external_tcp_reachable", "ipv6_default_route_present", "ipv6_external_tcp_reachable"):
        _expect_bool(controls[field_name], f"controls.{field_name}", False)

    runtime = _expect_object(payload["runtime"], "runtime")
    _expect_order(runtime, _TERMINAL_RUNTIME_FIELDS, "terminal.runtime")
    _expect_bool(runtime["result_ok"], "runtime.result_ok", True)
    if _expect_str(runtime["probe_id"], "runtime.probe_id") != RUNTIME_ATTESTATION_PROBE_ID:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_probe_id_invalid", "Terminal runtime probe identity is invalid.")
    if _expect_str(runtime["implementation"], "runtime.implementation") != "CPython":
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_runtime_implementation_invalid", "Terminal runtime implementation is invalid.")
    version = _expect_list(runtime["version"], "runtime.version")
    if version != [3, 13, 15]:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_runtime_version_invalid", "Terminal runtime version is invalid.")
    _expect_int(runtime["architecture_bits"], "runtime.architecture_bits", expected=64)
    if _expect_str(runtime["machine"], "runtime.machine").upper() not in {"AMD64", "X86_64"}:
        raise DeveloperTaskRuntimeAttestationContractError("runtime_attestation_runtime_machine_invalid", "Terminal runtime machine is invalid.")
    for field_name in ("runtime_root_write_blocked", "environment_clean", "pip_absent", "ensurepip_absent", "site_absent", "sys_path_exact"):
        _expect_bool(runtime[field_name], f"runtime.{field_name}", True)

    shutdown = _expect_object(payload["shutdown"], "shutdown")
    _expect_order(shutdown, _TERMINAL_SHUTDOWN_FIELDS, "terminal.shutdown")
    _expect_bool(shutdown["scheduled"], "shutdown.scheduled", True)
    _expect_int(shutdown["delay_seconds"], "shutdown.delay_seconds", minimum=1, maximum=60)
    _expect_utc(payload["completed_at_utc"], "completed_at_utc")
    _expect_bool(payload["overall_ok"], "overall_ok", True)
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def parse_runtime_attestation_request(data: bytes) -> DeveloperTaskRuntimeAttestationDocument:
    return _load_document(data, kind="request", max_bytes=RUNTIME_ATTESTATION_REQUEST_MAX_BYTES, validator=_validate_request)


def parse_runtime_attestation_ready(data: bytes) -> DeveloperTaskRuntimeAttestationDocument:
    return _load_document(data, kind="ready", max_bytes=RUNTIME_ATTESTATION_READY_MAX_BYTES, validator=_validate_ready)


def parse_runtime_attestation_authorize(data: bytes) -> DeveloperTaskRuntimeAttestationDocument:
    return _load_document(data, kind="authorize", max_bytes=RUNTIME_ATTESTATION_AUTHORIZE_MAX_BYTES, validator=_validate_authorize)


def parse_runtime_attestation_result(data: bytes) -> DeveloperTaskRuntimeAttestationDocument:
    return _load_document(data, kind="runtime_result", max_bytes=RUNTIME_ATTESTATION_RESULT_MAX_BYTES, validator=_validate_runtime_result, trailing_lf=True)


def parse_runtime_attestation_terminal(data: bytes) -> DeveloperTaskRuntimeAttestationDocument:
    return _load_document(data, kind="terminal", max_bytes=RUNTIME_ATTESTATION_TERMINAL_MAX_BYTES, validator=_validate_terminal)


def validate_runtime_attestation_signature_bytes(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("terminal_signature_bytes must be bytes")
    if len(data) != RUNTIME_ATTESTATION_SIGNATURE_BYTES:
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_signature_size_invalid",
            "ECDSA P-256 signature must be exactly 64 bytes.",
            actual=str(len(data)),
        )
    if not any(data):
        raise DeveloperTaskRuntimeAttestationContractError(
            "runtime_attestation_signature_invalid",
            "ECDSA P-256 signature must not be all zero bytes.",
        )
    return hashlib.sha256(data).hexdigest()
