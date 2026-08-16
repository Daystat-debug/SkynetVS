from __future__ import annotations

"""Strict immutable JSON contracts for the V1C2 compile/AST transcript."""

import base64
import hashlib
import json
import re
import unicodedata

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZE_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_SCHEMA_VERSION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_TOTAL_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUIRED_MODE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_MACHINES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_VERSION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_FILE_PATTERN,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_STRATEGY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_STATUSES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SYNTAX_MESSAGE_MAX_CHARS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VIRTUAL_FILENAME_PREFIX,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
)
from modules.developer.developer_task_execution_compile_ast_plan import (
    DeveloperTaskExecutionCompileAstPlanReport,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
)


COMPILE_AST_TRUSTED_SCOPE = "compile_ast_changed_python_only_v1"
COMPILE_AST_PUBLIC_KEY_FORMAT = "EccPublicBlob"
COMPILE_AST_SIGNATURE_ALGORITHM = "ECDSA_P256_SHA256_P1363_64_BYTES"

_HEX_32 = re.compile(r"^[0-9a-f]{32}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_SID = re.compile(r"^S-1(?:-[0-9]+)+$")
_SAFE_PATH_SEGMENT = re.compile(r"^[^\x00-\x1f<>:\"\\|?*]+$")

_SOURCE_MANIFEST_FIELDS = (
    "schema_version",
    "contract_policy_id",
    "contract_policy_fingerprint",
    "operation",
    "request_id",
    "host_nonce",
    "plan_policy_fingerprint",
    "plan_fingerprint",
    "snapshot_fingerprint",
    "plan_source_manifest_sha256",
    "source_strategy",
    "source_root",
    "original_path_used_as_guest_filesystem_path",
    "read_only_mapping",
    "selected_file_count",
    "selected_total_bytes",
    "sources",
    "execution_authorized",
)
_SOURCE_FIELDS = (
    "ordinal",
    "guest_file_name",
    "original_path",
    "virtual_filename",
    "git_mode",
    "size_bytes",
    "sha256",
    "encoding",
    "line_endings",
)
_REQUEST_FIELDS = (
    "schema_version",
    "backend_id",
    "backend_policy_fingerprint",
    "contract_policy_id",
    "contract_policy_fingerprint",
    "operation",
    "request_id",
    "host_nonce",
    "created_at_utc",
    "ready_timeout_seconds",
    "authorization_timeout_seconds",
    "worker_timeout_seconds",
    "shutdown_grace_seconds",
    "policy_sha256",
    "bootstrap_sha256",
    "controller_sha256",
    "native_helper_sha256",
    "runner_sha256",
    "payload_sha256",
    "wsb_sha256",
    "runtime_attestation_policy_fingerprint",
    "runtime_bundle_fingerprint",
    "runtime_lease_policy_fingerprint",
    "runtime_lease_fingerprint",
    "plan_policy_fingerprint",
    "plan_fingerprint",
    "source_manifest_sha256",
    "selected_file_count",
    "selected_total_bytes",
    "trusted_scope",
    "execution_authorized",
)
_READY_FIELDS = (
    "schema_version",
    "backend_id",
    "backend_policy_fingerprint",
    "contract_policy_id",
    "contract_policy_fingerprint",
    "operation",
    "request_id",
    "host_nonce",
    "request_sha256",
    "source_manifest_sha256",
    "policy_sha256",
    "bootstrap_sha256",
    "controller_sha256",
    "native_helper_sha256",
    "runner_sha256",
    "payload_sha256",
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
    "runtime_attestation_policy_fingerprint",
    "runtime_bundle_fingerprint",
    "runtime_lease_policy_fingerprint",
    "runtime_lease_fingerprint",
    "plan_policy_fingerprint",
    "plan_fingerprint",
    "input_write_blocked",
    "source_write_blocked",
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
    "request_identity_verified",
    "source_manifest_verified",
    "runtime_identity_verified",
    "input_write_blocked",
    "source_write_blocked",
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
    "runtime_lease_fingerprint",
    "plan_fingerprint",
    "source_manifest_sha256",
    "authorization_nonce",
    "authorization_deadline_epoch",
    "allow_compile_ast",
    "execution_authorized",
)
_RESULT_FIELDS = (
    "schema_version",
    "contract_policy_id",
    "contract_policy_fingerprint",
    "operation",
    "request_id",
    "plan_fingerprint",
    "source_manifest_sha256",
    "runtime_bundle_fingerprint",
    "implementation",
    "version_info",
    "architecture_bits",
    "machine",
    "selected_file_count",
    "processed_file_count",
    "passed_file_count",
    "failed_file_count",
    "check_passed",
    "files",
    "trusted_interpreter_executed",
    "changed_source_processed",
    "changed_source_ast_parsed",
    "changed_source_compiled",
    "changed_code_executed",
    "imports_executed",
    "top_level_executed",
    "bytecode_written",
    "execution_authorized",
)
_RESULT_FILE_FIELDS = (
    "ordinal",
    "guest_file_name",
    "original_path",
    "virtual_filename",
    "git_mode",
    "size_bytes",
    "sha256",
    "decode_ok",
    "ast_parse_ok",
    "compile_ok",
    "error",
)
_ERROR_FIELDS = (
    "type",
    "message",
    "line",
    "offset",
    "end_line",
    "end_offset",
)
_TERMINAL_FIELDS = (
    "schema_version",
    "backend_id",
    "backend_policy_fingerprint",
    "contract_policy_id",
    "contract_policy_fingerprint",
    "operation",
    "request_id",
    "host_nonce",
    "authorization_nonce",
    "request_sha256",
    "ready_sha256",
    "authorize_sha256",
    "source_manifest_sha256",
    "result_sha256",
    "policy_sha256",
    "bootstrap_sha256",
    "controller_sha256",
    "native_helper_sha256",
    "runner_sha256",
    "payload_sha256",
    "wsb_sha256",
    "public_key_sha256",
    "runtime_attestation_policy_fingerprint",
    "runtime_bundle_fingerprint",
    "runtime_lease_policy_fingerprint",
    "runtime_lease_fingerprint",
    "plan_policy_fingerprint",
    "plan_fingerprint",
    "controller",
    "worker",
    "controls",
    "runtime",
    "check",
    "shutdown",
    "completed_at_utc",
    "status",
    "boundary_ok",
    "check_passed",
    "reusable_lease_issued",
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
    "result_received",
    "exit_code",
    "is_administrator",
    "integrity_rid",
    "worker_in_job",
    "active_process_limit",
    "process_memory_bytes",
    "job_memory_bytes",
    "job_closed",
    "sid_process_set_empty",
    "account_deleted",
)
_TERMINAL_CONTROL_FIELDS = (
    "input_write_blocked",
    "source_write_blocked",
    "runtime_write_blocked",
    "control_write_blocked",
    "output_writable",
    "ipv4_default_route_present",
    "ipv4_external_tcp_reachable",
    "ipv6_default_route_present",
    "ipv6_external_tcp_reachable",
)
_TERMINAL_RUNTIME_FIELDS = (
    "implementation",
    "version",
    "architecture_bits",
    "machine",
    "bundle_fingerprint",
    "environment_clean",
    "pip_absent",
    "ensurepip_absent",
    "site_absent",
    "sys_path_exact",
    "dont_write_bytecode",
)
_TERMINAL_CHECK_FIELDS = (
    "result_received",
    "result_sha256",
    "selected_file_count",
    "processed_file_count",
    "passed_file_count",
    "failed_file_count",
    "trusted_interpreter_executed",
    "changed_source_processed",
    "changed_source_ast_parsed",
    "changed_source_compiled",
    "changed_code_executed",
    "imports_executed",
    "top_level_executed",
    "bytecode_written",
)
_TERMINAL_SHUTDOWN_FIELDS = ("scheduled", "delay_seconds")


class DeveloperTaskExecutionCompileAstContractError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        field_name: str = "",
        actual: str = "",
    ) -> None:
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
class DeveloperTaskExecutionCompileAstDocument:
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
    raise DeveloperTaskExecutionCompileAstContractError(
        "compile_ast_json_number_invalid",
        "Floating-point JSON values are not allowed.",
        actual=value,
    )


def _reject_constant(value: str) -> None:
    raise DeveloperTaskExecutionCompileAstContractError(
        "compile_ast_json_constant_invalid",
        "Non-finite JSON values are not allowed.",
        actual=value,
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DeveloperTaskExecutionCompileAstContractError(
                "compile_ast_json_duplicate_field",
                "Duplicate JSON field is not allowed.",
                field_name=key,
            )
        result[key] = value
    return result


def _canonical_bytes(payload: dict[str, Any], *, trailing_lf: bool) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return data + (b"\n" if trailing_lf else b"")


def _load_document(
    data: bytes,
    *,
    kind: str,
    max_bytes: int,
    validator: Callable[[dict[str, Any]], None],
    trailing_lf: bool = False,
) -> DeveloperTaskExecutionCompileAstDocument:
    if not isinstance(data, bytes):
        raise TypeError(f"{kind}_bytes must be bytes")
    if not data:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_document_empty",
            "Compile/AST JSON document is empty.",
            actual=kind,
        )
    if len(data) > max_bytes:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_document_too_large",
            "Compile/AST JSON document exceeds its size limit.",
            actual=f"{kind}:{len(data)}>{max_bytes}",
        )
    if data.startswith(b"\xef\xbb\xbf"):
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_json_bom_forbidden",
            "Compile/AST JSON must not contain a UTF-8 BOM.",
            actual=kind,
        )
    body = data
    if trailing_lf:
        if not data.endswith(b"\n") or data.endswith(b"\r\n") or data.endswith(b"\n\n"):
            raise DeveloperTaskExecutionCompileAstContractError(
                "compile_ast_json_line_ending_invalid",
                "Compile/AST result must end with exactly one LF byte.",
                actual=kind,
            )
        body = data[:-1]
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_json_utf8_invalid",
            "Compile/AST JSON is not strict UTF-8.",
            actual=f"{kind}:{exc}",
        ) from exc
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except DeveloperTaskExecutionCompileAstContractError:
        raise
    except json.JSONDecodeError as exc:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_json_invalid",
            "Compile/AST JSON is invalid.",
            actual=f"{kind}:{exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_json_not_object",
            "Compile/AST JSON must be an object.",
            actual=kind,
        )
    try:
        canonical = _canonical_bytes(payload, trailing_lf=trailing_lf)
    except (UnicodeEncodeError, ValueError) as exc:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_json_unicode_invalid",
            "Compile/AST JSON contains an invalid Unicode scalar value.",
            actual=kind,
        ) from exc
    if canonical != data:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_json_not_canonical",
            "Compile/AST JSON bytes are not canonical.",
            actual=kind,
        )
    validator(payload)
    return DeveloperTaskExecutionCompileAstDocument(
        kind=kind,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        canonical_bytes=data,
        _payload=_freeze(payload),
    )


def _expect_order(payload: dict[str, Any], fields: tuple[str, ...], section: str) -> None:
    actual = tuple(payload.keys())
    if actual != fields:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_fields_invalid",
            "Compile/AST fields or field order are invalid.",
            field_name=section,
            actual=repr(actual),
        )


def _expect_object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_type_invalid",
            "Compile/AST field must be an object.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    return value


def _expect_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_type_invalid",
            "Compile/AST field must be an array.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    return value


def _expect_str(
    value: Any,
    field_name: str,
    *,
    nonempty: bool = True,
    max_chars: int | None = None,
) -> str:
    if type(value) is not str:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_type_invalid",
            "Compile/AST field must be a string.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    if nonempty and not value:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_value_invalid",
            "Compile/AST string field must not be empty.",
            field_name=field_name,
        )
    if max_chars is not None and len(value) > max_chars:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_value_invalid",
            "Compile/AST string field exceeds its limit.",
            field_name=field_name,
            actual=str(len(value)),
        )
    return value


def _expect_bool(value: Any, field_name: str, expected: bool | None = None) -> bool:
    if type(value) is not bool:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_type_invalid",
            "Compile/AST field must be a boolean.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    if expected is not None and value is not expected:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_value_invalid",
            "Compile/AST boolean field has an invalid value.",
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
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_type_invalid",
            "Compile/AST field must be an integer.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    if expected is not None and value != expected:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_value_invalid",
            "Compile/AST integer field has an invalid value.",
            field_name=field_name,
            actual=str(value),
        )
    if minimum is not None and value < minimum:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_value_invalid",
            "Compile/AST integer field is below its minimum.",
            field_name=field_name,
            actual=str(value),
        )
    if maximum is not None and value > maximum:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_field_value_invalid",
            "Compile/AST integer field exceeds its maximum.",
            field_name=field_name,
            actual=str(value),
        )
    return value


def _expect_optional_int(
    value: Any,
    field_name: str,
    *,
    minimum: int = 0,
) -> int | None:
    if value is None:
        return None
    return _expect_int(value, field_name, minimum=minimum)


def _expect_hex(value: Any, field_name: str, pattern: re.Pattern[str]) -> str:
    text = _expect_str(value, field_name)
    if not pattern.fullmatch(text):
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_hex_invalid",
            "Compile/AST hexadecimal field is invalid.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_sha256(value: Any, field_name: str, expected: str | None = None) -> str:
    text = _expect_hex(value, field_name, _HEX_64)
    if expected is not None and text != expected:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_identity_mismatch",
            "Compile/AST pinned identity does not match.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_optional_sha256(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _expect_sha256(value, field_name)


def _expect_sid(value: Any, field_name: str, *, allow_empty: bool = False) -> str:
    text = _expect_str(value, field_name, nonempty=not allow_empty)
    if allow_empty and not text:
        return text
    if not _SID.fullmatch(text):
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_sid_invalid",
            "Compile/AST SID field is invalid.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_utc(value: Any, field_name: str) -> str:
    text = _expect_str(value, field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_datetime_invalid",
            "Compile/AST timestamp is invalid.",
            field_name=field_name,
            actual=text,
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_datetime_invalid",
            "Compile/AST timestamp must be UTC.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_safe_original_path(value: Any, field_name: str) -> str:
    path = _expect_str(value, field_name, max_chars=240)
    if unicodedata.normalize("NFC", path) != path:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_source_path_not_normalized",
            "Compile/AST original path must use NFC normalization.",
            field_name=field_name,
            actual=path,
        )
    if path.startswith(("/", "\\")) or "\\" in path or ":" in path:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_source_path_invalid",
            "Compile/AST original path must be a safe relative POSIX path.",
            field_name=field_name,
            actual=path,
        )
    parts = path.split("/")
    if not parts or len(parts) > 32 or any(part in {"", ".", ".."} for part in parts):
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_source_path_invalid",
            "Compile/AST original path has invalid segments.",
            field_name=field_name,
            actual=path,
        )
    for part in parts:
        if len(part) > 120 or not _SAFE_PATH_SEGMENT.fullmatch(part) or part[-1] in {".", " "}:
            raise DeveloperTaskExecutionCompileAstContractError(
                "compile_ast_source_path_invalid",
                "Compile/AST original path contains a Windows-unsafe segment.",
                field_name=field_name,
                actual=path,
            )
        stem = part.split(".", 1)[0].upper()
        if stem in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(r"(?:COM|LPT)[1-9]", stem):
            raise DeveloperTaskExecutionCompileAstContractError(
                "compile_ast_source_path_invalid",
                "Compile/AST original path contains a reserved Windows segment.",
                field_name=field_name,
                actual=path,
            )
    if not path.endswith(".py"):
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_source_path_invalid",
            "Compile/AST source path must end with .py.",
            field_name=field_name,
            actual=path,
        )
    return path


def _expect_ecc_public_blob(value: Any, sha256_value: Any) -> bytes:
    encoded = _expect_str(value, "public_key_blob_base64")
    try:
        blob = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_public_key_base64_invalid",
            "Compile/AST public key is not strict base64.",
        ) from exc
    if len(blob) != 72 or blob[:4] != b"ECS1" or blob[4:8] != b"\x20\x00\x00\x00":
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_public_key_blob_invalid",
            "Compile/AST EccPublicBlob is invalid for P-256.",
            actual=f"size={len(blob)},header={blob[:8].hex()}",
        )
    expected_hash = _expect_sha256(sha256_value, "public_key_sha256")
    actual_hash = hashlib.sha256(blob).hexdigest()
    if actual_hash != expected_hash:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_public_key_hash_mismatch",
            "Compile/AST public key hash does not match its blob.",
            actual=actual_hash,
        )
    return blob


def _validate_common_policy(payload: dict[str, Any]) -> None:
    _expect_int(payload["schema_version"], "schema_version", expected=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_SCHEMA_VERSION)
    if _expect_str(payload["contract_policy_id"], "contract_policy_id") != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_policy_id_mismatch", "Unexpected compile/AST contract policy identity.")
    _expect_sha256(payload["contract_policy_fingerprint"], "contract_policy_fingerprint", DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT)
    if _expect_str(payload["operation"], "operation") != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_operation_mismatch", "Unexpected compile/AST operation.")


def _validate_backend_identity(payload: dict[str, Any]) -> None:
    if _expect_str(payload["backend_id"], "backend_id") != WINDOWS_SANDBOX_EXECUTION_POLICY_V1.backend_id:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_backend_mismatch", "Unexpected Windows Sandbox backend identity.")
    _expect_sha256(payload["backend_policy_fingerprint"], "backend_policy_fingerprint", WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint)


def _validate_source_manifest(payload: dict[str, Any]) -> None:
    _expect_order(payload, _SOURCE_MANIFEST_FIELDS, "source_manifest")
    _validate_common_policy(payload)
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_hex(payload["host_nonce"], "host_nonce", _HEX_64)
    _expect_sha256(payload["plan_policy_fingerprint"], "plan_policy_fingerprint", DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT)
    _expect_sha256(payload["plan_fingerprint"], "plan_fingerprint")
    _expect_sha256(payload["snapshot_fingerprint"], "snapshot_fingerprint")
    _expect_sha256(payload["plan_source_manifest_sha256"], "plan_source_manifest_sha256")
    if _expect_str(payload["source_strategy"], "source_strategy") != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_STRATEGY:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_source_strategy_invalid", "Unexpected source materialization strategy.")
    if _expect_str(payload["source_root"], "source_root") != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_source_root_invalid", "Unexpected guest source root.")
    _expect_bool(payload["original_path_used_as_guest_filesystem_path"], "original_path_used_as_guest_filesystem_path", False)
    _expect_bool(payload["read_only_mapping"], "read_only_mapping", True)
    selected_count = _expect_int(payload["selected_file_count"], "selected_file_count", minimum=1, maximum=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT)
    selected_total = _expect_int(payload["selected_total_bytes"], "selected_total_bytes", minimum=0, maximum=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_TOTAL_BYTES)
    sources = _expect_list(payload["sources"], "sources")
    if len(sources) != selected_count:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_source_count_mismatch", "Source manifest count does not match selected_file_count.")
    total = 0
    previous_path = ""
    seen_guest: set[str] = set()
    seen_path_keys: set[str] = set()
    for index, item_value in enumerate(sources, start=1):
        item = _expect_object(item_value, f"sources[{index - 1}]")
        _expect_order(item, _SOURCE_FIELDS, f"sources[{index - 1}]")
        ordinal = _expect_int(item["ordinal"], f"sources[{index - 1}].ordinal", expected=index)
        expected_guest = DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_FILE_PATTERN.format(ordinal=ordinal)
        guest_name = _expect_str(item["guest_file_name"], f"sources[{index - 1}].guest_file_name")
        if guest_name != expected_guest or guest_name in seen_guest:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_guest_file_name_invalid", "Guest source filename is not the fixed ordinal filename.", actual=guest_name)
        seen_guest.add(guest_name)
        original_path = _expect_safe_original_path(item["original_path"], f"sources[{index - 1}].original_path")
        if previous_path and original_path <= previous_path:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_source_order_invalid", "Sources must be strictly sorted by original path.", actual=original_path)
        previous_path = original_path
        path_key = original_path.casefold()
        if path_key in seen_path_keys:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_source_path_collision", "Source manifest contains a Windows case collision.", actual=original_path)
        seen_path_keys.add(path_key)
        virtual_filename = _expect_str(item["virtual_filename"], f"sources[{index - 1}].virtual_filename")
        if virtual_filename != DEVELOPER_TASK_EXECUTION_COMPILE_AST_VIRTUAL_FILENAME_PREFIX + original_path:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_virtual_filename_invalid", "Virtual filename does not match the original source path.", actual=virtual_filename)
        if _expect_str(item["git_mode"], f"sources[{index - 1}].git_mode") != DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUIRED_MODE:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_source_mode_invalid", "Compile/AST source mode must be 100644.")
        size_bytes = _expect_int(item["size_bytes"], f"sources[{index - 1}].size_bytes", minimum=0, maximum=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_BYTES)
        total += size_bytes
        _expect_sha256(item["sha256"], f"sources[{index - 1}].sha256")
        if _expect_str(item["encoding"], f"sources[{index - 1}].encoding") != "utf-8":
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_source_encoding_invalid", "Compile/AST source encoding must be UTF-8.")
        if _expect_str(item["line_endings"], f"sources[{index - 1}].line_endings") not in {"lf", "none"}:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_source_line_endings_invalid", "Compile/AST source line endings must be LF or none.")
    if total != selected_total:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_source_total_mismatch", "Source manifest byte total does not match selected_total_bytes.", actual=f"{total}!={selected_total}")
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_request(payload: dict[str, Any]) -> None:
    _expect_order(payload, _REQUEST_FIELDS, "request")
    _validate_backend_identity(payload)
    _validate_common_policy(payload)
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_hex(payload["host_nonce"], "host_nonce", _HEX_64)
    _expect_utc(payload["created_at_utc"], "created_at_utc")
    _expect_int(payload["ready_timeout_seconds"], "ready_timeout_seconds", expected=DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS)
    _expect_int(payload["authorization_timeout_seconds"], "authorization_timeout_seconds", expected=DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS)
    _expect_int(payload["worker_timeout_seconds"], "worker_timeout_seconds", expected=DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS)
    _expect_int(payload["shutdown_grace_seconds"], "shutdown_grace_seconds", expected=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS)
    for field_name in ("policy_sha256", "bootstrap_sha256", "controller_sha256", "native_helper_sha256", "runner_sha256", "payload_sha256", "wsb_sha256", "runtime_lease_fingerprint", "plan_fingerprint", "source_manifest_sha256"):
        _expect_sha256(payload[field_name], field_name)
    _expect_sha256(payload["runtime_attestation_policy_fingerprint"], "runtime_attestation_policy_fingerprint", RUNTIME_ATTESTATION_POLICY_FINGERPRINT)
    _expect_sha256(payload["runtime_bundle_fingerprint"], "runtime_bundle_fingerprint", RUNTIME_BUNDLE_FINGERPRINT)
    _expect_sha256(payload["runtime_lease_policy_fingerprint"], "runtime_lease_policy_fingerprint", RUNTIME_LEASE_POLICY_FINGERPRINT)
    _expect_sha256(payload["plan_policy_fingerprint"], "plan_policy_fingerprint", DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT)
    _expect_int(payload["selected_file_count"], "selected_file_count", minimum=1, maximum=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT)
    _expect_int(payload["selected_total_bytes"], "selected_total_bytes", minimum=0, maximum=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_TOTAL_BYTES)
    if _expect_str(payload["trusted_scope"], "trusted_scope") != COMPILE_AST_TRUSTED_SCOPE:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_trusted_scope_invalid", "Compile/AST trusted scope is invalid.")
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_ready(payload: dict[str, Any]) -> None:
    _expect_order(payload, _READY_FIELDS, "ready")
    _validate_backend_identity(payload)
    _validate_common_policy(payload)
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_hex(payload["host_nonce"], "host_nonce", _HEX_64)
    for field_name in ("request_sha256", "source_manifest_sha256", "policy_sha256", "bootstrap_sha256", "controller_sha256", "native_helper_sha256", "runner_sha256", "payload_sha256", "wsb_sha256", "runtime_lease_fingerprint", "plan_fingerprint"):
        _expect_sha256(payload[field_name], field_name)
    if _expect_sid(payload["controller_sid"], "controller_sid") != "S-1-5-18":
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_controller_identity_invalid",
            "Compile/AST ready controller SID is not LocalSystem.",
        )
    _expect_str(payload["controller_name"], "controller_name")
    _expect_bool(payload["controller_is_system"], "controller_is_system", True)
    _expect_bool(payload["controller_is_administrator"], "controller_is_administrator", True)
    _expect_int(payload["controller_integrity_rid"], "controller_integrity_rid", minimum=0x4000)
    _expect_bool(payload["key_is_ephemeral"], "key_is_ephemeral", True)
    _expect_bool(payload["key_name_empty"], "key_name_empty", True)
    _expect_bool(payload["key_unique_name_empty"], "key_unique_name_empty", True)
    if _expect_str(payload["public_key_format"], "public_key_format") != COMPILE_AST_PUBLIC_KEY_FORMAT:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_public_key_format_invalid", "Compile/AST public key format is invalid.")
    _expect_ecc_public_blob(payload["public_key_blob_base64"], payload["public_key_sha256"])
    _expect_sha256(payload["runtime_attestation_policy_fingerprint"], "runtime_attestation_policy_fingerprint", RUNTIME_ATTESTATION_POLICY_FINGERPRINT)
    _expect_sha256(payload["runtime_bundle_fingerprint"], "runtime_bundle_fingerprint", RUNTIME_BUNDLE_FINGERPRINT)
    _expect_sha256(payload["runtime_lease_policy_fingerprint"], "runtime_lease_policy_fingerprint", RUNTIME_LEASE_POLICY_FINGERPRINT)
    _expect_sha256(payload["plan_policy_fingerprint"], "plan_policy_fingerprint", DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT)
    for field_name in ("input_write_blocked", "source_write_blocked", "runtime_write_blocked", "control_write_blocked", "output_writable", "bootstrap_task_deleted"):
        _expect_bool(payload[field_name], field_name, True)
    ready_checks = _expect_object(payload["ready_checks"], "ready_checks")
    _expect_order(ready_checks, _READY_CHECK_FIELDS, "ready.ready_checks")
    for field_name in _READY_CHECK_FIELDS:
        _expect_bool(ready_checks[field_name], f"ready_checks.{field_name}", True)
    failed = _expect_list(payload["failed_ready_checks"], "failed_ready_checks")
    if failed:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_ready_checks_failed", "Compile/AST ready evidence contains failed checks.", actual=repr(failed))
    _expect_utc(payload["created_at_utc"], "created_at_utc")
    _expect_bool(payload["overall_ok"], "overall_ok", True)
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_authorize(payload: dict[str, Any]) -> None:
    _expect_order(payload, _AUTHORIZE_FIELDS, "authorize")
    _expect_int(payload["schema_version"], "schema_version", expected=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_SCHEMA_VERSION)
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_hex(payload["host_nonce"], "host_nonce", _HEX_64)
    for field_name in ("request_sha256", "ready_sha256", "public_key_sha256", "runtime_lease_fingerprint", "plan_fingerprint", "source_manifest_sha256"):
        _expect_sha256(payload[field_name], field_name)
    _expect_sha256(payload["runtime_bundle_fingerprint"], "runtime_bundle_fingerprint", RUNTIME_BUNDLE_FINGERPRINT)
    _expect_hex(payload["authorization_nonce"], "authorization_nonce", _HEX_64)
    _expect_int(payload["authorization_deadline_epoch"], "authorization_deadline_epoch", minimum=1)
    _expect_bool(payload["allow_compile_ast"], "allow_compile_ast", True)
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_result_error(value: Any, field_name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    error = _expect_object(value, field_name)
    _expect_order(error, _ERROR_FIELDS, field_name)
    _expect_str(error["type"], f"{field_name}.type", max_chars=128)
    message = _expect_str(error["message"], f"{field_name}.message", max_chars=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SYNTAX_MESSAGE_MAX_CHARS)
    if "\n" in message or "\r" in message:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_error_message_invalid", "Compile/AST error message must be one bounded line.", field_name=f"{field_name}.message")
    line = _expect_optional_int(error["line"], f"{field_name}.line", minimum=1)
    offset = _expect_optional_int(error["offset"], f"{field_name}.offset", minimum=0)
    end_line = _expect_optional_int(error["end_line"], f"{field_name}.end_line", minimum=1)
    end_offset = _expect_optional_int(error["end_offset"], f"{field_name}.end_offset", minimum=0)
    if (line is None) != (offset is None):
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_error_location_invalid", "Compile/AST error line and offset must be both present or both absent.", field_name=field_name)
    if end_line is not None and line is None:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_error_location_invalid", "Compile/AST end location requires a start location.", field_name=field_name)
    if end_offset is not None and end_line is None:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_error_location_invalid", "Compile/AST end offset requires an end line.", field_name=field_name)
    return error


def _validate_result(payload: dict[str, Any]) -> None:
    _expect_order(payload, _RESULT_FIELDS, "result")
    _validate_common_policy(payload)
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_sha256(payload["plan_fingerprint"], "plan_fingerprint")
    _expect_sha256(payload["source_manifest_sha256"], "source_manifest_sha256")
    _expect_sha256(payload["runtime_bundle_fingerprint"], "runtime_bundle_fingerprint", RUNTIME_BUNDLE_FINGERPRINT)
    if _expect_str(payload["implementation"], "implementation") != "CPython":
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_runtime_implementation_invalid", "Compile/AST result implementation must be CPython.")
    version = _expect_list(payload["version_info"], "version_info")
    if version != list(DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_VERSION):
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_runtime_version_invalid", "Compile/AST result runtime version is invalid.", actual=repr(version))
    _expect_int(payload["architecture_bits"], "architecture_bits", expected=64)
    if _expect_str(payload["machine"], "machine").upper() not in set(DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_MACHINES):
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_runtime_machine_invalid", "Compile/AST result machine identity is invalid.")
    selected = _expect_int(payload["selected_file_count"], "selected_file_count", minimum=1, maximum=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT)
    processed = _expect_int(payload["processed_file_count"], "processed_file_count", minimum=0, maximum=selected)
    passed = _expect_int(payload["passed_file_count"], "passed_file_count", minimum=0, maximum=selected)
    failed = _expect_int(payload["failed_file_count"], "failed_file_count", minimum=0, maximum=selected)
    check_passed = _expect_bool(payload["check_passed"], "check_passed")
    files = _expect_list(payload["files"], "files")
    if len(files) != selected or processed != selected or passed + failed != selected:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_result_counts_invalid", "Compile/AST result counts are inconsistent.")
    previous_path = ""
    computed_passed = 0
    all_ast = True
    all_compile = True
    for index, item_value in enumerate(files, start=1):
        item = _expect_object(item_value, f"files[{index - 1}]")
        _expect_order(item, _RESULT_FILE_FIELDS, f"files[{index - 1}]")
        ordinal = _expect_int(item["ordinal"], f"files[{index - 1}].ordinal", expected=index)
        expected_guest = DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_FILE_PATTERN.format(ordinal=ordinal)
        if _expect_str(item["guest_file_name"], f"files[{index - 1}].guest_file_name") != expected_guest:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_guest_file_name_invalid", "Compile/AST result guest filename is invalid.")
        original_path = _expect_safe_original_path(item["original_path"], f"files[{index - 1}].original_path")
        if previous_path and original_path <= previous_path:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_result_order_invalid", "Compile/AST result files must be sorted by original path.")
        previous_path = original_path
        if _expect_str(item["virtual_filename"], f"files[{index - 1}].virtual_filename") != DEVELOPER_TASK_EXECUTION_COMPILE_AST_VIRTUAL_FILENAME_PREFIX + original_path:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_virtual_filename_invalid", "Compile/AST result virtual filename is invalid.")
        if _expect_str(item["git_mode"], f"files[{index - 1}].git_mode") != DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUIRED_MODE:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_source_mode_invalid", "Compile/AST result mode must be 100644.")
        _expect_int(item["size_bytes"], f"files[{index - 1}].size_bytes", minimum=0, maximum=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_BYTES)
        _expect_sha256(item["sha256"], f"files[{index - 1}].sha256")
        decode_ok = _expect_bool(item["decode_ok"], f"files[{index - 1}].decode_ok")
        ast_ok = _expect_bool(item["ast_parse_ok"], f"files[{index - 1}].ast_parse_ok")
        compile_ok = _expect_bool(item["compile_ok"], f"files[{index - 1}].compile_ok")
        error = _validate_result_error(item["error"], f"files[{index - 1}].error")
        if compile_ok and (not decode_ok or not ast_ok):
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_result_state_invalid", "Compile success requires decode and AST success.")
        if ast_ok and not decode_ok:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_result_state_invalid", "AST success requires decode success.")
        if compile_ok:
            computed_passed += 1
            if error is not None:
                raise DeveloperTaskExecutionCompileAstContractError("compile_ast_result_error_invalid", "Passing source result must not contain an error.")
        elif error is None:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_result_error_missing", "Failing source result must contain bounded error evidence.")
        all_ast = all_ast and ast_ok
        all_compile = all_compile and compile_ok
    if computed_passed != passed or selected - computed_passed != failed:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_result_counts_invalid", "Compile/AST pass/fail counts do not match file results.")
    if check_passed != (failed == 0):
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_result_status_invalid", "Compile/AST check_passed does not match file outcomes.")
    _expect_bool(payload["trusted_interpreter_executed"], "trusted_interpreter_executed", True)
    _expect_bool(payload["changed_source_processed"], "changed_source_processed", True)
    if _expect_bool(payload["changed_source_ast_parsed"], "changed_source_ast_parsed") != all_ast:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_result_status_invalid", "Global AST status does not match file outcomes.")
    if _expect_bool(payload["changed_source_compiled"], "changed_source_compiled") != all_compile:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_result_status_invalid", "Global compile status does not match file outcomes.")
    _expect_bool(payload["changed_code_executed"], "changed_code_executed", False)
    _expect_bool(payload["imports_executed"], "imports_executed", False)
    _expect_bool(payload["top_level_executed"], "top_level_executed", False)
    _expect_bool(payload["bytecode_written"], "bytecode_written", False)
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_terminal(payload: dict[str, Any]) -> None:
    _expect_order(payload, _TERMINAL_FIELDS, "terminal")
    _validate_backend_identity(payload)
    _validate_common_policy(payload)
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_hex(payload["host_nonce"], "host_nonce", _HEX_64)
    _expect_hex(payload["authorization_nonce"], "authorization_nonce", _HEX_64)
    for field_name in ("request_sha256", "ready_sha256", "authorize_sha256", "source_manifest_sha256", "policy_sha256", "bootstrap_sha256", "controller_sha256", "native_helper_sha256", "runner_sha256", "payload_sha256", "wsb_sha256", "public_key_sha256", "runtime_lease_fingerprint", "plan_fingerprint"):
        _expect_sha256(payload[field_name], field_name)
    result_sha256 = _expect_optional_sha256(payload["result_sha256"], "result_sha256")
    _expect_sha256(payload["runtime_attestation_policy_fingerprint"], "runtime_attestation_policy_fingerprint", RUNTIME_ATTESTATION_POLICY_FINGERPRINT)
    _expect_sha256(payload["runtime_bundle_fingerprint"], "runtime_bundle_fingerprint", RUNTIME_BUNDLE_FINGERPRINT)
    _expect_sha256(payload["runtime_lease_policy_fingerprint"], "runtime_lease_policy_fingerprint", RUNTIME_LEASE_POLICY_FINGERPRINT)
    _expect_sha256(payload["plan_policy_fingerprint"], "plan_policy_fingerprint", DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT)

    controller = _expect_object(payload["controller"], "controller")
    _expect_order(controller, _TERMINAL_CONTROLLER_FIELDS, "terminal.controller")
    if _expect_sid(controller["sid"], "controller.sid") != "S-1-5-18":
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_controller_identity_invalid", "Compile/AST terminal controller SID is not LocalSystem.")
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
    result_received = _expect_bool(worker["result_received"], "worker.result_received")
    exit_code = _expect_int(worker["exit_code"], "worker.exit_code", minimum=0, maximum=0xFFFFFFFF)
    _expect_bool(worker["is_administrator"], "worker.is_administrator", False)
    _expect_int(worker["integrity_rid"], "worker.integrity_rid", expected=0x2000)
    _expect_bool(worker["worker_in_job"], "worker.worker_in_job", True)
    _expect_int(worker["active_process_limit"], "worker.active_process_limit", expected=DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT)
    _expect_int(worker["process_memory_bytes"], "worker.process_memory_bytes", expected=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES)
    _expect_int(worker["job_memory_bytes"], "worker.job_memory_bytes", expected=DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES)
    _expect_bool(worker["job_closed"], "worker.job_closed", True)
    _expect_bool(worker["sid_process_set_empty"], "worker.sid_process_set_empty", True)
    _expect_bool(worker["account_deleted"], "worker.account_deleted", True)

    controls = _expect_object(payload["controls"], "controls")
    _expect_order(controls, _TERMINAL_CONTROL_FIELDS, "terminal.controls")
    for field_name in ("input_write_blocked", "source_write_blocked", "runtime_write_blocked", "control_write_blocked", "output_writable"):
        _expect_bool(controls[field_name], f"controls.{field_name}", True)
    for field_name in ("ipv4_default_route_present", "ipv4_external_tcp_reachable", "ipv6_default_route_present", "ipv6_external_tcp_reachable"):
        _expect_bool(controls[field_name], f"controls.{field_name}", False)

    runtime = _expect_object(payload["runtime"], "runtime")
    _expect_order(runtime, _TERMINAL_RUNTIME_FIELDS, "terminal.runtime")
    if _expect_str(runtime["implementation"], "runtime.implementation") != "CPython":
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_runtime_implementation_invalid", "Compile/AST terminal runtime implementation is invalid.")
    if _expect_list(runtime["version"], "runtime.version") != list(DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_VERSION):
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_runtime_version_invalid", "Compile/AST terminal runtime version is invalid.")
    _expect_int(runtime["architecture_bits"], "runtime.architecture_bits", expected=64)
    if _expect_str(runtime["machine"], "runtime.machine").upper() not in set(DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_MACHINES):
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_runtime_machine_invalid", "Compile/AST terminal runtime machine is invalid.")
    _expect_sha256(runtime["bundle_fingerprint"], "runtime.bundle_fingerprint", RUNTIME_BUNDLE_FINGERPRINT)
    for field_name in ("environment_clean", "pip_absent", "ensurepip_absent", "site_absent", "sys_path_exact", "dont_write_bytecode"):
        _expect_bool(runtime[field_name], f"runtime.{field_name}", True)

    check = _expect_object(payload["check"], "check")
    _expect_order(check, _TERMINAL_CHECK_FIELDS, "terminal.check")
    check_result_received = _expect_bool(check["result_received"], "check.result_received")
    check_result_sha256 = _expect_optional_sha256(check["result_sha256"], "check.result_sha256")
    selected = _expect_int(check["selected_file_count"], "check.selected_file_count", minimum=1, maximum=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT)
    processed = _expect_int(check["processed_file_count"], "check.processed_file_count", minimum=0, maximum=selected)
    passed = _expect_int(check["passed_file_count"], "check.passed_file_count", minimum=0, maximum=selected)
    failed = _expect_int(check["failed_file_count"], "check.failed_file_count", minimum=0, maximum=selected)
    trusted_interpreter = _expect_bool(check["trusted_interpreter_executed"], "check.trusted_interpreter_executed")
    changed_processed = _expect_bool(check["changed_source_processed"], "check.changed_source_processed")
    ast_parsed = _expect_bool(check["changed_source_ast_parsed"], "check.changed_source_ast_parsed")
    compiled = _expect_bool(check["changed_source_compiled"], "check.changed_source_compiled")
    _expect_bool(check["changed_code_executed"], "check.changed_code_executed", False)
    _expect_bool(check["imports_executed"], "check.imports_executed", False)
    _expect_bool(check["top_level_executed"], "check.top_level_executed", False)
    _expect_bool(check["bytecode_written"], "check.bytecode_written", False)

    shutdown = _expect_object(payload["shutdown"], "shutdown")
    _expect_order(shutdown, _TERMINAL_SHUTDOWN_FIELDS, "terminal.shutdown")
    _expect_bool(shutdown["scheduled"], "shutdown.scheduled", True)
    _expect_int(shutdown["delay_seconds"], "shutdown.delay_seconds", minimum=1, maximum=60)
    _expect_utc(payload["completed_at_utc"], "completed_at_utc")
    status = _expect_str(payload["status"], "status")
    if status not in DEVELOPER_TASK_EXECUTION_COMPILE_AST_STATUSES:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_terminal_status_invalid", "Compile/AST terminal status is invalid.", actual=status)
    boundary_ok = _expect_bool(payload["boundary_ok"], "boundary_ok")
    check_passed = _expect_bool(payload["check_passed"], "check_passed")
    _expect_bool(payload["reusable_lease_issued"], "reusable_lease_issued", False)
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)

    if result_received != check_result_received:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_terminal_result_state_invalid", "Worker and check result-received states disagree.")
    if result_sha256 != check_result_sha256:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_terminal_result_hash_invalid", "Terminal result hashes disagree.")
    if status == "compile_ast_boundary_failed":
        if boundary_ok or check_passed or result_received or result_sha256 is not None:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_terminal_status_invalid", "Boundary-failed terminal cannot claim a trusted check result.")
        if any((processed, passed, failed, trusted_interpreter, changed_processed, ast_parsed, compiled)):
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_terminal_status_invalid", "Boundary-failed terminal contains impossible check success evidence.")
    else:
        if not boundary_ok or not result_received or result_sha256 is None:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_terminal_status_invalid", "Attested terminal requires a received result and an intact boundary.")
        if exit_code != 0:
            raise DeveloperTaskExecutionCompileAstContractError(
                "compile_ast_terminal_status_invalid",
                "Attested terminal requires a successful worker process exit.",
            )
        if processed != selected or passed + failed != selected or not trusted_interpreter or not changed_processed:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_terminal_status_invalid", "Attested terminal check counts or interpreter evidence are invalid.")
        expected_passed = status == "compile_ast_attested_passed"
        if check_passed != expected_passed or (failed == 0) != expected_passed:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_terminal_status_invalid", "Attested terminal status does not match check outcome.")
        if expected_passed and (not ast_parsed or not compiled):
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_terminal_status_invalid", "Passed terminal must prove AST parse and compile success.")


def parse_compile_ast_source_manifest(data: bytes) -> DeveloperTaskExecutionCompileAstDocument:
    return _load_document(data, kind="source_manifest", max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES, validator=_validate_source_manifest)


def parse_compile_ast_request(data: bytes) -> DeveloperTaskExecutionCompileAstDocument:
    return _load_document(data, kind="request", max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES, validator=_validate_request)


def parse_compile_ast_ready(data: bytes) -> DeveloperTaskExecutionCompileAstDocument:
    return _load_document(data, kind="ready", max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_MAX_BYTES, validator=_validate_ready)


def parse_compile_ast_authorize(data: bytes) -> DeveloperTaskExecutionCompileAstDocument:
    return _load_document(data, kind="authorize", max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZE_MAX_BYTES, validator=_validate_authorize)


def parse_compile_ast_result(data: bytes) -> DeveloperTaskExecutionCompileAstDocument:
    return _load_document(data, kind="result", max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_MAX_BYTES, validator=_validate_result, trailing_lf=True)


def parse_compile_ast_terminal(data: bytes) -> DeveloperTaskExecutionCompileAstDocument:
    return _load_document(data, kind="terminal", max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES, validator=_validate_terminal)


_PARSERS: dict[str, Callable[[bytes], DeveloperTaskExecutionCompileAstDocument]] = {
    "source_manifest": parse_compile_ast_source_manifest,
    "request": parse_compile_ast_request,
    "ready": parse_compile_ast_ready,
    "authorize": parse_compile_ast_authorize,
    "result": parse_compile_ast_result,
    "terminal": parse_compile_ast_terminal,
}


def encode_compile_ast_document(kind: str, payload: dict[str, Any]) -> bytes:
    """Encode and validate one exact canonical V1C2A1 document."""
    if type(kind) is not str:
        raise TypeError("kind must be str")
    if type(payload) is not dict:
        raise TypeError("payload must be dict")
    try:
        parser = _PARSERS[kind]
    except KeyError as exc:
        raise ValueError(f"unsupported compile/AST document kind: {kind}") from exc
    data = _canonical_bytes(payload, trailing_lf=(kind == "result"))
    return parser(data).canonical_bytes


def build_compile_ast_source_manifest(
    plan_report: DeveloperTaskExecutionCompileAstPlanReport,
    *,
    request_id: str,
    host_nonce: str,
) -> DeveloperTaskExecutionCompileAstDocument:
    """Build the flat fixed-name source manifest from one canonical V1C1B report."""
    if type(plan_report) is not DeveloperTaskExecutionCompileAstPlanReport:
        raise TypeError("plan_report must be DeveloperTaskExecutionCompileAstPlanReport")
    if not plan_report.ok:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_plan_report_invalid", "V1C1B plan report is not canonical and successful.")
    if plan_report.policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT:
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_plan_policy_mismatch", "V1C1B plan policy fingerprint does not match V1C2A1.")
    sources = []
    for ordinal, source in enumerate(sorted(plan_report.sources, key=lambda item: item.path), start=1):
        sources.append({
            "ordinal": ordinal,
            "guest_file_name": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_FILE_PATTERN.format(ordinal=ordinal),
            "original_path": source.path,
            "virtual_filename": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VIRTUAL_FILENAME_PREFIX + source.path,
            "git_mode": source.mode,
            "size_bytes": source.size_bytes,
            "sha256": source.sha256,
            "encoding": source.encoding,
            "line_endings": source.line_endings,
        })
    payload = {
        "schema_version": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_SCHEMA_VERSION,
        "contract_policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
        "contract_policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        "request_id": request_id,
        "host_nonce": host_nonce,
        "plan_policy_fingerprint": plan_report.policy_fingerprint,
        "plan_fingerprint": plan_report.plan_fingerprint,
        "snapshot_fingerprint": plan_report.snapshot_fingerprint,
        "plan_source_manifest_sha256": plan_report.source_manifest_sha256,
        "source_strategy": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_STRATEGY,
        "source_root": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
        "original_path_used_as_guest_filesystem_path": False,
        "read_only_mapping": True,
        "selected_file_count": plan_report.selected_file_count,
        "selected_total_bytes": plan_report.selected_total_bytes,
        "sources": sources,
        "execution_authorized": False,
    }
    return parse_compile_ast_source_manifest(_canonical_bytes(payload, trailing_lf=False))


def validate_compile_ast_signature_bytes(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("terminal_signature_bytes must be bytes")
    if len(data) != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_signature_size_invalid",
            "ECDSA P-256 signature must be exactly 64 bytes.",
            actual=str(len(data)),
        )
    if not any(data):
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_signature_invalid",
            "ECDSA P-256 signature must not be all zero bytes.",
        )
    return hashlib.sha256(data).hexdigest()


def _chain_mismatch(field_name: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise DeveloperTaskExecutionCompileAstContractError(
            "compile_ast_chain_mismatch",
            "Compile/AST transcript documents are not bound to the same run.",
            field_name=field_name,
            actual=f"{actual!r}!={expected!r}",
        )


def validate_compile_ast_document_chain(
    source_manifest: DeveloperTaskExecutionCompileAstDocument,
    request: DeveloperTaskExecutionCompileAstDocument,
    ready: DeveloperTaskExecutionCompileAstDocument,
    authorize: DeveloperTaskExecutionCompileAstDocument,
    result: DeveloperTaskExecutionCompileAstDocument | None,
    terminal: DeveloperTaskExecutionCompileAstDocument,
) -> None:
    """Validate all hash and identity bindings before signature verification."""
    expected_kinds = (
        (source_manifest, "source_manifest"),
        (request, "request"),
        (ready, "ready"),
        (authorize, "authorize"),
        (terminal, "terminal"),
    )
    for document, kind in expected_kinds:
        if type(document) is not DeveloperTaskExecutionCompileAstDocument or document.kind != kind:
            raise TypeError(f"{kind} must be a parsed DeveloperTaskExecutionCompileAstDocument")
    if result is not None and (type(result) is not DeveloperTaskExecutionCompileAstDocument or result.kind != "result"):
        raise TypeError("result must be None or a parsed result document")

    sm = source_manifest.to_dict()
    rq = request.to_dict()
    rd = ready.to_dict()
    az = authorize.to_dict()
    tm = terminal.to_dict()
    rs = result.to_dict() if result is not None else None

    for field_name in ("request_id", "host_nonce"):
        _chain_mismatch(f"source_manifest.{field_name}", sm[field_name], rq[field_name])
        _chain_mismatch(f"ready.{field_name}", rd[field_name], rq[field_name])
        _chain_mismatch(f"authorize.{field_name}", az[field_name], rq[field_name])
        _chain_mismatch(f"terminal.{field_name}", tm[field_name], rq[field_name])
    for field_name in ("plan_fingerprint",):
        _chain_mismatch(f"source_manifest.{field_name}", sm[field_name], rq[field_name])
        _chain_mismatch(f"ready.{field_name}", rd[field_name], rq[field_name])
        _chain_mismatch(f"authorize.{field_name}", az[field_name], rq[field_name])
        _chain_mismatch(f"terminal.{field_name}", tm[field_name], rq[field_name])
    _chain_mismatch("request.plan_policy_fingerprint", rq["plan_policy_fingerprint"], sm["plan_policy_fingerprint"])
    _chain_mismatch("request.source_manifest_sha256", rq["source_manifest_sha256"], source_manifest.sha256)
    _chain_mismatch("request.selected_file_count", rq["selected_file_count"], sm["selected_file_count"])
    _chain_mismatch("request.selected_total_bytes", rq["selected_total_bytes"], sm["selected_total_bytes"])
    _chain_mismatch("ready.request_sha256", rd["request_sha256"], request.sha256)
    _chain_mismatch("ready.source_manifest_sha256", rd["source_manifest_sha256"], source_manifest.sha256)
    _chain_mismatch("authorize.request_sha256", az["request_sha256"], request.sha256)
    _chain_mismatch("authorize.ready_sha256", az["ready_sha256"], ready.sha256)
    _chain_mismatch("authorize.public_key_sha256", az["public_key_sha256"], rd["public_key_sha256"])
    _chain_mismatch("authorize.source_manifest_sha256", az["source_manifest_sha256"], source_manifest.sha256)
    _chain_mismatch("authorize.runtime_lease_fingerprint", az["runtime_lease_fingerprint"], rq["runtime_lease_fingerprint"])
    _chain_mismatch("terminal.authorization_nonce", tm["authorization_nonce"], az["authorization_nonce"])
    _chain_mismatch("terminal.request_sha256", tm["request_sha256"], request.sha256)
    _chain_mismatch("terminal.ready_sha256", tm["ready_sha256"], ready.sha256)
    _chain_mismatch("terminal.authorize_sha256", tm["authorize_sha256"], authorize.sha256)
    _chain_mismatch("terminal.source_manifest_sha256", tm["source_manifest_sha256"], source_manifest.sha256)
    _chain_mismatch("terminal.public_key_sha256", tm["public_key_sha256"], rd["public_key_sha256"])
    _chain_mismatch(
        "terminal.check.selected_file_count",
        tm["check"]["selected_file_count"],
        sm["selected_file_count"],
    )

    artifact_fields = (
        "policy_sha256",
        "bootstrap_sha256",
        "controller_sha256",
        "native_helper_sha256",
        "runner_sha256",
        "payload_sha256",
        "wsb_sha256",
        "runtime_attestation_policy_fingerprint",
        "runtime_bundle_fingerprint",
        "runtime_lease_policy_fingerprint",
        "runtime_lease_fingerprint",
        "plan_policy_fingerprint",
        "plan_fingerprint",
    )
    for field_name in artifact_fields:
        _chain_mismatch(f"ready.{field_name}", rd[field_name], rq[field_name])
        _chain_mismatch(f"terminal.{field_name}", tm[field_name], rq[field_name])

    if rs is None:
        if tm["status"] != "compile_ast_boundary_failed" or tm["result_sha256"] is not None:
            raise DeveloperTaskExecutionCompileAstContractError("compile_ast_chain_result_missing", "Only a boundary-failed terminal may omit the compile/AST result.")
        return

    _chain_mismatch("result.request_id", rs["request_id"], rq["request_id"])
    _chain_mismatch("result.plan_fingerprint", rs["plan_fingerprint"], rq["plan_fingerprint"])
    _chain_mismatch("result.source_manifest_sha256", rs["source_manifest_sha256"], source_manifest.sha256)
    _chain_mismatch("result.runtime_bundle_fingerprint", rs["runtime_bundle_fingerprint"], rq["runtime_bundle_fingerprint"])
    _chain_mismatch("result.selected_file_count", rs["selected_file_count"], sm["selected_file_count"])
    _chain_mismatch("terminal.result_sha256", tm["result_sha256"], result.sha256)

    manifest_sources = sm["sources"]
    result_files = rs["files"]
    if len(manifest_sources) != len(result_files):
        raise DeveloperTaskExecutionCompileAstContractError("compile_ast_chain_source_mismatch", "Compile/AST result file set does not match the source manifest.")
    identity_fields = ("ordinal", "guest_file_name", "original_path", "virtual_filename", "git_mode", "size_bytes", "sha256")
    for index, (manifest_item, result_item) in enumerate(zip(manifest_sources, result_files)):
        for field_name in identity_fields:
            _chain_mismatch(f"result.files[{index}].{field_name}", result_item[field_name], manifest_item[field_name])

    check = tm["check"]
    for field_name in ("selected_file_count", "processed_file_count", "passed_file_count", "failed_file_count", "trusted_interpreter_executed", "changed_source_processed", "changed_source_ast_parsed", "changed_source_compiled"):
        source_field = field_name
        _chain_mismatch(f"terminal.check.{field_name}", check[field_name], rs[source_field])
    _chain_mismatch("terminal.check.result_sha256", check["result_sha256"], result.sha256)
    expected_status = "compile_ast_attested_passed" if rs["check_passed"] else "compile_ast_attested_failed"
    _chain_mismatch("terminal.status", tm["status"], expected_status)
    _chain_mismatch("terminal.check_passed", tm["check_passed"], rs["check_passed"])
