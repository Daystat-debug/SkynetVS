from __future__ import annotations

"""Strict immutable JSON contracts for the V1B3 signed-result transcript."""

import base64
import hashlib
import json
import re

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


BOUNDARY_SCHEMA_VERSION = 1
BOUNDARY_REQUEST_MAX_BYTES = 16 * 1024
BOUNDARY_READY_MAX_BYTES = 32 * 1024
BOUNDARY_AUTHORIZE_MAX_BYTES = 16 * 1024
BOUNDARY_WORKER_RESULT_MAX_BYTES = 16 * 1024
BOUNDARY_TERMINAL_PAYLOAD_MAX_BYTES = 64 * 1024
BOUNDARY_SIGNATURE_BYTES = 64

_HEX_32 = re.compile(r"^[0-9a-f]{32}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_SID = re.compile(r"^S-1(?:-[0-9]+)+$")

_REQUEST_FIELDS = (
    "schema_version",
    "backend_id",
    "base_policy_fingerprint",
    "boundary_id",
    "boundary_fingerprint",
    "request_id",
    "host_nonce",
    "task_name",
    "created_at_utc",
    "ready_timeout_seconds",
    "authorization_timeout_seconds",
    "worker_timeout_seconds",
    "shutdown_grace_seconds",
    "policy_sha256",
    "bootstrap_sha256",
    "controller_sha256",
    "worker_source_sha256",
    "wsb_sha256",
    "trusted_scope",
    "execution_authorized",
)
_READY_FIELDS = (
    "schema_version",
    "backend_id",
    "base_policy_fingerprint",
    "boundary_id",
    "boundary_fingerprint",
    "request_id",
    "host_nonce",
    "request_sha256",
    "policy_sha256",
    "bootstrap_sha256",
    "controller_sha256",
    "worker_source_sha256",
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
    "input_write_blocked",
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
    "input_write_blocked",
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
    "worker_source_sha256",
    "authorization_nonce",
    "authorization_deadline_epoch",
    "allow_benign_worker",
    "execution_authorized",
)
_WORKER_RESULT_FIELDS = (
    "schema_version",
    "request_id",
    "worker_sid",
    "worker_name",
    "worker_is_administrator",
    "worker_integrity_rid",
    "controller_secret_absent",
    "sentinel_handle_inherited",
    "controller_vm_read_blocked",
    "input_write_blocked",
    "control_write_blocked",
    "output_writable",
    "worker_in_job",
    "child_pid",
    "child_in_job",
    "overall_ok",
)
_TERMINAL_FIELDS = (
    "schema_version",
    "backend_id",
    "base_policy_fingerprint",
    "boundary_id",
    "boundary_fingerprint",
    "request_id",
    "host_nonce",
    "authorization_nonce",
    "request_sha256",
    "ready_sha256",
    "authorize_sha256",
    "policy_sha256",
    "bootstrap_sha256",
    "controller_sha256",
    "worker_source_sha256",
    "wsb_sha256",
    "worker_result_sha256",
    "public_key_sha256",
    "controller",
    "worker",
    "controls",
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
    "controller_secret_absent",
    "sentinel_handle_inherited",
    "controller_vm_read_blocked",
    "worker_in_job",
    "child_pid",
    "child_in_job",
    "child_in_specific_job",
    "job_closed",
    "child_killed_by_job_close",
    "sid_process_set_empty",
    "account_deleted",
)
_TERMINAL_CONTROL_FIELDS = (
    "input_write_blocked",
    "control_write_blocked",
    "output_writable",
    "ipv4_default_route_present",
    "ipv4_external_tcp_reachable",
    "ipv6_default_route_present",
    "ipv6_external_tcp_reachable",
)
_TERMINAL_SHUTDOWN_FIELDS = ("scheduled", "delay_seconds")


class DeveloperTaskExecutionBoundaryContractError(ValueError):
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
class DeveloperTaskExecutionBoundaryDocument:
    kind: str
    size_bytes: int
    sha256: str
    canonical_bytes: bytes = field(repr=False)
    _payload: tuple[tuple[str, Any], ...] = field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self._payload)

    def field(self, name: str) -> Any:
        return self.to_dict()[name]


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple((key, _freeze(item)) for key, item in value.items())
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, tuple):
        if all(
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], str)
            for item in value
        ):
            return {key: _thaw(item) for key, item in value}
        return [_thaw(item) for item in value]
    return value


def _reject_float(value: str) -> None:
    raise DeveloperTaskExecutionBoundaryContractError(
        "boundary_json_number_invalid",
        "Floating-point JSON values are not allowed.",
        actual=value,
    )


def _reject_constant(value: str) -> None:
    raise DeveloperTaskExecutionBoundaryContractError(
        "boundary_json_constant_invalid",
        "Non-finite JSON values are not allowed.",
        actual=value,
    )


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DeveloperTaskExecutionBoundaryContractError(
                "boundary_json_duplicate_field",
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
) -> DeveloperTaskExecutionBoundaryDocument:
    if not isinstance(data, bytes):
        raise TypeError(f"{kind}_bytes must be bytes")
    if not data:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_document_empty",
            "Signed-boundary JSON document is empty.",
            actual=kind,
        )
    if len(data) > max_bytes:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_document_too_large",
            "Signed-boundary JSON document exceeds its size limit.",
            actual=f"{kind}:{len(data)}>{max_bytes}",
        )
    if data.startswith(b"\xef\xbb\xbf"):
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_json_bom_forbidden",
            "Signed-boundary JSON must not contain a UTF-8 BOM.",
            actual=kind,
        )
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_json_utf8_invalid",
            "Signed-boundary JSON is not strict UTF-8.",
            actual=f"{kind}:{exc}",
        ) from exc
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except DeveloperTaskExecutionBoundaryContractError:
        raise
    except json.JSONDecodeError as exc:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_json_invalid",
            "Signed-boundary JSON is invalid.",
            actual=f"{kind}:{exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_json_not_object",
            "Signed-boundary JSON must be an object.",
            actual=kind,
        )
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if canonical != data:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_json_not_canonical",
            "Signed-boundary JSON bytes are not canonical.",
            actual=kind,
        )
    validator(payload)
    return DeveloperTaskExecutionBoundaryDocument(
        kind=kind,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        canonical_bytes=data,
        _payload=_freeze(payload),
    )


def _expect_order(payload: dict[str, Any], fields: tuple[str, ...], section: str) -> None:
    actual = tuple(payload.keys())
    if actual != fields:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_fields_invalid",
            "Signed-boundary fields or field order are invalid.",
            field_name=section,
            actual=repr(actual),
        )


def _expect_object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_field_type_invalid",
            "Signed-boundary field must be an object.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    return value


def _expect_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_field_type_invalid",
            "Signed-boundary field must be an array.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    return value


def _expect_str(value: Any, field_name: str, *, nonempty: bool = True) -> str:
    if type(value) is not str:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_field_type_invalid",
            "Signed-boundary field must be a string.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    if nonempty and not value:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_field_value_invalid",
            "Signed-boundary string field must not be empty.",
            field_name=field_name,
        )
    return value


def _expect_bool(value: Any, field_name: str, expected: bool | None = None) -> bool:
    if type(value) is not bool:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_field_type_invalid",
            "Signed-boundary field must be a boolean.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    if expected is not None and value is not expected:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_field_value_invalid",
            "Signed-boundary boolean field has an invalid value.",
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
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_field_type_invalid",
            "Signed-boundary field must be an integer.",
            field_name=field_name,
            actual=type(value).__name__,
        )
    if expected is not None and value != expected:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_field_value_invalid",
            "Signed-boundary integer field has an invalid value.",
            field_name=field_name,
            actual=str(value),
        )
    if minimum is not None and value < minimum:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_field_value_invalid",
            "Signed-boundary integer field is below its minimum.",
            field_name=field_name,
            actual=str(value),
        )
    if maximum is not None and value > maximum:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_field_value_invalid",
            "Signed-boundary integer field exceeds its maximum.",
            field_name=field_name,
            actual=str(value),
        )
    return value


def _expect_hex(value: Any, field_name: str, pattern: re.Pattern[str]) -> str:
    text = _expect_str(value, field_name)
    if not pattern.fullmatch(text):
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_hex_invalid",
            "Signed-boundary hexadecimal field is invalid.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_sha256(value: Any, field_name: str) -> str:
    return _expect_hex(value, field_name, _HEX_64)


def _expect_sid(value: Any, field_name: str) -> str:
    text = _expect_str(value, field_name)
    if not _SID.fullmatch(text):
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_sid_invalid",
            "Signed-boundary SID field is invalid.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_utc(value: Any, field_name: str) -> str:
    text = _expect_str(value, field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_datetime_invalid",
            "Signed-boundary timestamp is invalid.",
            field_name=field_name,
            actual=text,
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_datetime_invalid",
            "Signed-boundary timestamp must be UTC.",
            field_name=field_name,
            actual=text,
        )
    return text


def _expect_ecc_public_blob(value: Any, sha256_value: Any) -> bytes:
    encoded = _expect_str(value, "public_key_blob_base64")
    try:
        blob = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_public_key_base64_invalid",
            "Signed-boundary public key is not strict base64.",
        ) from exc
    if len(blob) != 72 or blob[:4] != b"ECS1" or blob[4:8] != b"\x20\x00\x00\x00":
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_public_key_blob_invalid",
            "Signed-boundary EccPublicBlob is invalid for P-256.",
            actual=f"size={len(blob)},header={blob[:8].hex()}",
        )
    expected_hash = _expect_sha256(sha256_value, "public_key_sha256")
    actual_hash = hashlib.sha256(blob).hexdigest()
    if actual_hash != expected_hash:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_public_key_hash_mismatch",
            "Signed-boundary public key hash does not match its blob.",
            actual=actual_hash,
        )
    return blob


def _validate_common_identity(payload: dict[str, Any]) -> None:
    _expect_int(payload["schema_version"], "schema_version", expected=BOUNDARY_SCHEMA_VERSION)
    _expect_str(payload["backend_id"], "backend_id")
    _expect_sha256(payload["base_policy_fingerprint"], "base_policy_fingerprint")
    _expect_str(payload["boundary_id"], "boundary_id")
    _expect_sha256(payload["boundary_fingerprint"], "boundary_fingerprint")
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_hex(payload["host_nonce"], "host_nonce", _HEX_64)


def _validate_request(payload: dict[str, Any]) -> None:
    _expect_order(payload, _REQUEST_FIELDS, "request")
    _validate_common_identity(payload)
    _expect_str(payload["task_name"], "task_name")
    _expect_utc(payload["created_at_utc"], "created_at_utc")
    _expect_int(payload["ready_timeout_seconds"], "ready_timeout_seconds", minimum=1, maximum=600)
    _expect_int(payload["authorization_timeout_seconds"], "authorization_timeout_seconds", minimum=1, maximum=600)
    _expect_int(payload["worker_timeout_seconds"], "worker_timeout_seconds", minimum=1, maximum=600)
    _expect_int(payload["shutdown_grace_seconds"], "shutdown_grace_seconds", minimum=1, maximum=300)
    for field_name in (
        "policy_sha256",
        "bootstrap_sha256",
        "controller_sha256",
        "worker_source_sha256",
        "wsb_sha256",
    ):
        _expect_sha256(payload[field_name], field_name)
    if _expect_str(payload["trusted_scope"], "trusted_scope") != "benign_system_controller_worker_probe_only":
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_scope_invalid",
            "Signed-boundary request scope is invalid.",
            field_name="trusted_scope",
            actual=str(payload["trusted_scope"]),
        )
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_ready(payload: dict[str, Any]) -> None:
    _expect_order(payload, _READY_FIELDS, "ready")
    _validate_common_identity(payload)
    for field_name in (
        "request_sha256",
        "policy_sha256",
        "bootstrap_sha256",
        "controller_sha256",
        "worker_source_sha256",
        "wsb_sha256",
        "public_key_sha256",
    ):
        _expect_sha256(payload[field_name], field_name)
    if _expect_sid(payload["controller_sid"], "controller_sid") != "S-1-5-18":
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_controller_identity_invalid",
            "Signed-boundary controller SID is not LocalSystem.",
            field_name="controller_sid",
            actual=str(payload["controller_sid"]),
        )
    _expect_str(payload["controller_name"], "controller_name")
    _expect_bool(payload["controller_is_system"], "controller_is_system", True)
    _expect_bool(payload["controller_is_administrator"], "controller_is_administrator", True)
    _expect_int(payload["controller_integrity_rid"], "controller_integrity_rid", minimum=0x4000)
    _expect_bool(payload["key_is_ephemeral"], "key_is_ephemeral", True)
    _expect_bool(payload["key_name_empty"], "key_name_empty", True)
    _expect_bool(payload["key_unique_name_empty"], "key_unique_name_empty", True)
    if _expect_str(payload["public_key_format"], "public_key_format") != "EccPublicBlob":
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_public_key_format_invalid",
            "Signed-boundary public key format is invalid.",
            actual=str(payload["public_key_format"]),
        )
    _expect_ecc_public_blob(payload["public_key_blob_base64"], payload["public_key_sha256"])
    for field_name in (
        "input_write_blocked",
        "control_write_blocked",
        "output_writable",
        "bootstrap_task_deleted",
    ):
        _expect_bool(payload[field_name], field_name, True)
    checks = _expect_object(payload["ready_checks"], "ready_checks")
    _expect_order(checks, _READY_CHECK_FIELDS, "ready_checks")
    for field_name in _READY_CHECK_FIELDS:
        _expect_bool(checks[field_name], f"ready_checks.{field_name}", True)
    failed = _expect_list(payload["failed_ready_checks"], "failed_ready_checks")
    if failed:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_ready_checks_failed",
            "Signed-boundary ready evidence contains failed checks.",
            actual=repr(failed),
        )
    _expect_utc(payload["created_at_utc"], "created_at_utc")
    _expect_bool(payload["overall_ok"], "overall_ok", True)
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_authorize(payload: dict[str, Any]) -> None:
    _expect_order(payload, _AUTHORIZE_FIELDS, "authorize")
    _expect_int(payload["schema_version"], "schema_version", expected=BOUNDARY_SCHEMA_VERSION)
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_hex(payload["host_nonce"], "host_nonce", _HEX_64)
    for field_name in (
        "request_sha256",
        "ready_sha256",
        "public_key_sha256",
        "worker_source_sha256",
    ):
        _expect_sha256(payload[field_name], field_name)
    _expect_hex(payload["authorization_nonce"], "authorization_nonce", _HEX_64)
    _expect_int(payload["authorization_deadline_epoch"], "authorization_deadline_epoch", minimum=1)
    _expect_bool(payload["allow_benign_worker"], "allow_benign_worker", True)
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def _validate_worker_result(payload: dict[str, Any]) -> None:
    _expect_order(payload, _WORKER_RESULT_FIELDS, "worker_result")
    _expect_int(payload["schema_version"], "schema_version", expected=BOUNDARY_SCHEMA_VERSION)
    _expect_hex(payload["request_id"], "request_id", _HEX_32)
    _expect_sid(payload["worker_sid"], "worker_sid")
    _expect_str(payload["worker_name"], "worker_name")
    _expect_bool(payload["worker_is_administrator"], "worker_is_administrator", False)
    _expect_int(payload["worker_integrity_rid"], "worker_integrity_rid", expected=0x2000)
    _expect_bool(payload["controller_secret_absent"], "controller_secret_absent", True)
    _expect_bool(payload["sentinel_handle_inherited"], "sentinel_handle_inherited", False)
    _expect_bool(payload["controller_vm_read_blocked"], "controller_vm_read_blocked", True)
    _expect_bool(payload["input_write_blocked"], "input_write_blocked", True)
    _expect_bool(payload["control_write_blocked"], "control_write_blocked", True)
    _expect_bool(payload["output_writable"], "output_writable", True)
    _expect_bool(payload["worker_in_job"], "worker_in_job", True)
    _expect_int(payload["child_pid"], "child_pid", minimum=1)
    _expect_bool(payload["child_in_job"], "child_in_job", True)
    _expect_bool(payload["overall_ok"], "overall_ok", True)


def _validate_terminal(payload: dict[str, Any]) -> None:
    _expect_order(payload, _TERMINAL_FIELDS, "terminal_payload")
    _validate_common_identity(payload)
    _expect_hex(payload["authorization_nonce"], "authorization_nonce", _HEX_64)
    for field_name in (
        "request_sha256",
        "ready_sha256",
        "authorize_sha256",
        "policy_sha256",
        "bootstrap_sha256",
        "controller_sha256",
        "worker_source_sha256",
        "wsb_sha256",
        "worker_result_sha256",
        "public_key_sha256",
    ):
        _expect_sha256(payload[field_name], field_name)

    controller = _expect_object(payload["controller"], "controller")
    _expect_order(controller, _TERMINAL_CONTROLLER_FIELDS, "terminal.controller")
    if _expect_sid(controller["sid"], "controller.sid") != "S-1-5-18":
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_controller_identity_invalid",
            "Terminal controller SID is not LocalSystem.",
            actual=str(controller["sid"]),
        )
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
    _expect_bool(worker["controller_secret_absent"], "worker.controller_secret_absent", True)
    _expect_bool(worker["sentinel_handle_inherited"], "worker.sentinel_handle_inherited", False)
    _expect_bool(worker["controller_vm_read_blocked"], "worker.controller_vm_read_blocked", True)
    _expect_bool(worker["worker_in_job"], "worker.worker_in_job", True)
    _expect_int(worker["child_pid"], "worker.child_pid", minimum=1)
    _expect_bool(worker["child_in_job"], "worker.child_in_job", True)
    _expect_bool(worker["child_in_specific_job"], "worker.child_in_specific_job", True)
    _expect_bool(worker["job_closed"], "worker.job_closed", True)
    _expect_bool(worker["child_killed_by_job_close"], "worker.child_killed_by_job_close", True)
    _expect_bool(worker["sid_process_set_empty"], "worker.sid_process_set_empty", True)
    _expect_bool(worker["account_deleted"], "worker.account_deleted", True)

    controls = _expect_object(payload["controls"], "controls")
    _expect_order(controls, _TERMINAL_CONTROL_FIELDS, "terminal.controls")
    _expect_bool(controls["input_write_blocked"], "controls.input_write_blocked", True)
    _expect_bool(controls["control_write_blocked"], "controls.control_write_blocked", True)
    _expect_bool(controls["output_writable"], "controls.output_writable", True)
    _expect_bool(controls["ipv4_default_route_present"], "controls.ipv4_default_route_present", False)
    _expect_bool(controls["ipv4_external_tcp_reachable"], "controls.ipv4_external_tcp_reachable", False)
    _expect_bool(controls["ipv6_default_route_present"], "controls.ipv6_default_route_present", False)
    _expect_bool(controls["ipv6_external_tcp_reachable"], "controls.ipv6_external_tcp_reachable", False)

    shutdown = _expect_object(payload["shutdown"], "shutdown")
    _expect_order(shutdown, _TERMINAL_SHUTDOWN_FIELDS, "terminal.shutdown")
    _expect_bool(shutdown["scheduled"], "shutdown.scheduled", True)
    _expect_int(shutdown["delay_seconds"], "shutdown.delay_seconds", minimum=1, maximum=60)
    _expect_utc(payload["completed_at_utc"], "completed_at_utc")
    _expect_bool(payload["overall_ok"], "overall_ok", True)
    _expect_bool(payload["execution_authorized"], "execution_authorized", False)


def parse_boundary_request(data: bytes) -> DeveloperTaskExecutionBoundaryDocument:
    return _load_document(
        data,
        kind="request",
        max_bytes=BOUNDARY_REQUEST_MAX_BYTES,
        validator=_validate_request,
    )


def parse_boundary_ready(data: bytes) -> DeveloperTaskExecutionBoundaryDocument:
    return _load_document(
        data,
        kind="ready",
        max_bytes=BOUNDARY_READY_MAX_BYTES,
        validator=_validate_ready,
    )


def parse_boundary_authorize(data: bytes) -> DeveloperTaskExecutionBoundaryDocument:
    return _load_document(
        data,
        kind="authorize",
        max_bytes=BOUNDARY_AUTHORIZE_MAX_BYTES,
        validator=_validate_authorize,
    )


def parse_boundary_worker_result(data: bytes) -> DeveloperTaskExecutionBoundaryDocument:
    return _load_document(
        data,
        kind="worker_result",
        max_bytes=BOUNDARY_WORKER_RESULT_MAX_BYTES,
        validator=_validate_worker_result,
    )


def parse_boundary_terminal_payload(data: bytes) -> DeveloperTaskExecutionBoundaryDocument:
    return _load_document(
        data,
        kind="terminal_payload",
        max_bytes=BOUNDARY_TERMINAL_PAYLOAD_MAX_BYTES,
        validator=_validate_terminal,
    )


def validate_boundary_signature_bytes(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("terminal_signature_bytes must be bytes")
    if len(data) != BOUNDARY_SIGNATURE_BYTES:
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_signature_size_invalid",
            "ECDSA P-256 signature must be exactly 64 bytes.",
            actual=str(len(data)),
        )
    if not any(data):
        raise DeveloperTaskExecutionBoundaryContractError(
            "boundary_signature_invalid",
            "ECDSA P-256 signature must not be all zero bytes.",
        )
    return hashlib.sha256(data).hexdigest()
