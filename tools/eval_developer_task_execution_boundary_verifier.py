from __future__ import annotations

import base64
import hashlib
import json

from dataclasses import FrozenInstanceError, replace
from typing import Any

from modules.developer.developer_task_execution_boundary_contract import (
    DeveloperTaskExecutionBoundaryContractError,
    parse_boundary_authorize,
    parse_boundary_ready,
    parse_boundary_request,
    parse_boundary_terminal_payload,
    parse_boundary_worker_result,
)
from modules.developer.developer_task_execution_boundary_crypto import (
    DeveloperTaskExecutionBoundaryCryptoError,
    validate_ecdsa_p256_public_blob,
    validate_ecdsa_p256_signature,
    verify_ecdsa_p256_sha256_cng,
)
from modules.developer.developer_task_execution_boundary_policy import (
    SIGNED_BOUNDARY_FINGERPRINT,
    WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1,
    validate_execution_boundary_policy,
)
from modules.developer.developer_task_execution_boundary_verifier import (
    SIGNED_TRANSCRIPT_STATUS_VERIFIED,
    pin_developer_task_execution_signed_transcript,
    verify_developer_task_execution_signed_transcript,
)


_REQUEST_ID = "0123456789abcdef0123456789abcdef"
_HOST_NONCE = "1" * 64
_AUTHORIZATION_NONCE = "2" * 64
_PUBLIC_BLOB = base64.b64decode(
    "RUNTMSAAAABrF9Hy4SxCR/i85uVjpEDydwN9gS3rM6D0oTlF2JjClk/jQuL+Gn+bjufrSnwPnhYrzjNXazFezsu2QGg3v1H1"
)


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture() -> dict[str, bytes]:
    policy = WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1
    policy_bytes = policy.canonical_bytes()
    bootstrap_bytes = b"trusted-bootstrap-v1"
    controller_bytes = b"trusted-controller-v1"
    worker_source_bytes = b"trusted-worker-source-v1"
    wsb_bytes = b"trusted-wsb-v1"
    request = {
        "schema_version": 1,
        "backend_id": policy.backend_id,
        "base_policy_fingerprint": policy.base_policy_fingerprint,
        "boundary_id": policy.boundary_id,
        "boundary_fingerprint": policy.fingerprint,
        "request_id": _REQUEST_ID,
        "host_nonce": _HOST_NONCE,
        "task_name": "SkynetVS-V1B3B-contract-eval",
        "created_at_utc": "2026-08-06T13:22:10.0000000Z",
        "ready_timeout_seconds": 120,
        "authorization_timeout_seconds": 90,
        "worker_timeout_seconds": 60,
        "shutdown_grace_seconds": 45,
        "policy_sha256": _sha256(policy_bytes),
        "bootstrap_sha256": _sha256(bootstrap_bytes),
        "controller_sha256": _sha256(controller_bytes),
        "worker_source_sha256": _sha256(worker_source_bytes),
        "wsb_sha256": _sha256(wsb_bytes),
        "trusted_scope": "benign_system_controller_worker_probe_only",
        "execution_authorized": False,
    }
    request_bytes = _canonical(request)
    public_key_sha256 = _sha256(_PUBLIC_BLOB)
    ready = {
        "schema_version": 1,
        "backend_id": policy.backend_id,
        "base_policy_fingerprint": policy.base_policy_fingerprint,
        "boundary_id": policy.boundary_id,
        "boundary_fingerprint": policy.fingerprint,
        "request_id": _REQUEST_ID,
        "host_nonce": _HOST_NONCE,
        "request_sha256": _sha256(request_bytes),
        "policy_sha256": _sha256(policy_bytes),
        "bootstrap_sha256": _sha256(bootstrap_bytes),
        "controller_sha256": _sha256(controller_bytes),
        "worker_source_sha256": _sha256(worker_source_bytes),
        "wsb_sha256": _sha256(wsb_bytes),
        "controller_sid": "S-1-5-18",
        "controller_name": r"NT AUTHORITY\SYSTEM",
        "controller_is_system": True,
        "controller_is_administrator": True,
        "controller_integrity_rid": 0x4000,
        "key_is_ephemeral": True,
        "key_name_empty": True,
        "key_unique_name_empty": True,
        "public_key_format": "EccPublicBlob",
        "public_key_blob_base64": base64.b64encode(_PUBLIC_BLOB).decode("ascii"),
        "public_key_sha256": public_key_sha256,
        "input_write_blocked": True,
        "control_write_blocked": True,
        "output_writable": True,
        "bootstrap_task_deleted": True,
        "ready_checks": {
            "controller_is_system": True,
            "controller_is_administrator": True,
            "controller_integrity_is_system": True,
            "key_is_ephemeral": True,
            "key_name_empty": True,
            "key_unique_name_empty": True,
            "input_write_blocked": True,
            "control_write_blocked": True,
            "output_writable": True,
        },
        "failed_ready_checks": [],
        "created_at_utc": "2026-08-06T13:22:23.0000000Z",
        "overall_ok": True,
        "execution_authorized": False,
    }
    ready_bytes = _canonical(ready)
    authorize = {
        "schema_version": 1,
        "request_id": _REQUEST_ID,
        "host_nonce": _HOST_NONCE,
        "request_sha256": _sha256(request_bytes),
        "ready_sha256": _sha256(ready_bytes),
        "public_key_sha256": public_key_sha256,
        "worker_source_sha256": _sha256(worker_source_bytes),
        "authorization_nonce": _AUTHORIZATION_NONCE,
        "authorization_deadline_epoch": 1786022633,
        "allow_benign_worker": True,
        "execution_authorized": False,
    }
    authorize_bytes = _canonical(authorize)
    worker_result = {
        "schema_version": 1,
        "request_id": _REQUEST_ID,
        "worker_sid": "S-1-5-21-1-2-3-1000",
        "worker_name": r"TEST\svb3worker",
        "worker_is_administrator": False,
        "worker_integrity_rid": 0x2000,
        "controller_secret_absent": True,
        "sentinel_handle_inherited": False,
        "controller_vm_read_blocked": True,
        "input_write_blocked": True,
        "control_write_blocked": True,
        "output_writable": True,
        "worker_in_job": True,
        "child_pid": 1234,
        "child_in_job": True,
        "overall_ok": True,
    }
    worker_result_bytes = _canonical(worker_result)
    terminal = {
        "schema_version": 1,
        "backend_id": policy.backend_id,
        "base_policy_fingerprint": policy.base_policy_fingerprint,
        "boundary_id": policy.boundary_id,
        "boundary_fingerprint": policy.fingerprint,
        "request_id": _REQUEST_ID,
        "host_nonce": _HOST_NONCE,
        "authorization_nonce": _AUTHORIZATION_NONCE,
        "request_sha256": _sha256(request_bytes),
        "ready_sha256": _sha256(ready_bytes),
        "authorize_sha256": _sha256(authorize_bytes),
        "policy_sha256": _sha256(policy_bytes),
        "bootstrap_sha256": _sha256(bootstrap_bytes),
        "controller_sha256": _sha256(controller_bytes),
        "worker_source_sha256": _sha256(worker_source_bytes),
        "wsb_sha256": _sha256(wsb_bytes),
        "worker_result_sha256": _sha256(worker_result_bytes),
        "public_key_sha256": public_key_sha256,
        "controller": {
            "sid": "S-1-5-18",
            "name": r"NT AUTHORITY\SYSTEM",
            "is_system": True,
            "is_administrator": True,
            "integrity_rid": 0x4000,
            "key_is_ephemeral": True,
            "key_name_empty": True,
            "key_unique_name_empty": True,
        },
        "worker": {
            "account_created": True,
            "sid": "S-1-5-21-1-2-3-1000",
            "created_suspended": True,
            "resume_previous_count": 1,
            "assigned_before_resume": True,
            "result_ok": True,
            "exit_code": 0,
            "is_administrator": False,
            "integrity_rid": 0x2000,
            "controller_secret_absent": True,
            "sentinel_handle_inherited": False,
            "controller_vm_read_blocked": True,
            "worker_in_job": True,
            "child_pid": 1234,
            "child_in_job": True,
            "child_in_specific_job": True,
            "job_closed": True,
            "child_killed_by_job_close": True,
            "sid_process_set_empty": True,
            "account_deleted": True,
        },
        "controls": {
            "input_write_blocked": True,
            "control_write_blocked": True,
            "output_writable": True,
            "ipv4_default_route_present": False,
            "ipv4_external_tcp_reachable": False,
            "ipv6_default_route_present": False,
            "ipv6_external_tcp_reachable": False,
        },
        "shutdown": {"scheduled": True, "delay_seconds": 8},
        "completed_at_utc": "2026-08-06T13:22:33.0000000Z",
        "overall_ok": True,
        "execution_authorized": False,
    }
    return {
        "policy_bytes": policy_bytes,
        "bootstrap_bytes": bootstrap_bytes,
        "controller_bytes": controller_bytes,
        "worker_source_bytes": worker_source_bytes,
        "wsb_bytes": wsb_bytes,
        "request_bytes": request_bytes,
        "ready_bytes": ready_bytes,
        "authorize_bytes": authorize_bytes,
        "worker_result_bytes": worker_result_bytes,
        "terminal_payload_bytes": _canonical(terminal),
        "terminal_signature_bytes": b"\x01" * 64,
    }


def _pin(fixture: dict[str, bytes], **kwargs: Any):
    return pin_developer_task_execution_signed_transcript(
        policy=WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1,
        expected_request_id=kwargs.get("expected_request_id", _REQUEST_ID),
        expected_host_nonce=kwargs.get("expected_host_nonce", _HOST_NONCE),
        expected_request_sha256=kwargs.get(
            "expected_request_sha256", _sha256(fixture["request_bytes"])
        ),
        policy_bytes=fixture["policy_bytes"],
        bootstrap_bytes=fixture["bootstrap_bytes"],
        controller_bytes=fixture["controller_bytes"],
        worker_source_bytes=fixture["worker_source_bytes"],
        wsb_bytes=fixture["wsb_bytes"],
        request_bytes=fixture["request_bytes"],
        ready_bytes=fixture["ready_bytes"],
        authorize_bytes=fixture["authorize_bytes"],
        authorization_observed_epoch=kwargs.get("authorization_observed_epoch"),
    )


def _verify(fixture: dict[str, bytes], pin_report: Any, verifier: Any = None):
    return verify_developer_task_execution_signed_transcript(
        pin_report,
        policy_bytes=fixture["policy_bytes"],
        bootstrap_bytes=fixture["bootstrap_bytes"],
        controller_bytes=fixture["controller_bytes"],
        worker_source_bytes=fixture["worker_source_bytes"],
        wsb_bytes=fixture["wsb_bytes"],
        request_bytes=fixture["request_bytes"],
        ready_bytes=fixture["ready_bytes"],
        authorize_bytes=fixture["authorize_bytes"],
        worker_result_bytes=fixture["worker_result_bytes"],
        terminal_payload_bytes=fixture["terminal_payload_bytes"],
        terminal_signature_bytes=fixture["terminal_signature_bytes"],
        signature_verifier=verifier or (lambda *_args: True),
    )


def _mutate(data: bytes, path: tuple[str, ...], value: Any) -> bytes:
    payload = json.loads(data)
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return _canonical(payload)




class _FakeCngRuntime:
    def __init__(self, *, open_status: int = 0, import_status: int = 0, verify_status: int = 0) -> None:
        self.open_status = open_status
        self.import_status = import_status
        self.verify_status = verify_status
        self.destroy_calls = 0
        self.close_calls = 0

    def open_algorithm(self):
        return self.open_status, (object() if self.open_status == 0 else None)

    def import_public_key(self, _algorithm: Any, _blob: bytes):
        return self.import_status, (object() if self.import_status == 0 else None)

    def verify(self, _key: Any, digest: bytes, signature: bytes) -> int:
        if len(digest) != 32 or len(signature) != 64:
            raise AssertionError("unexpected CNG verification input")
        return self.verify_status

    def destroy_key(self, _handle: Any) -> int:
        self.destroy_calls += 1
        return 0

    def close_algorithm(self, _handle: Any) -> int:
        self.close_calls += 1
        return 0

def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        print()
        print(f"=== {name} ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")
        if not ok:
            fail_count += 1

    fixture = _fixture()
    policy = WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1
    check("CANONICAL BOUNDARY POLICY MATCHES ATTESTED FINGERPRINT", {"ok": policy.ok, "fingerprint": policy.fingerprint, "bytes": len(policy.canonical_bytes())}, {"ok": True, "fingerprint": SIGNED_BOUNDARY_FINGERPRINT, "bytes": 1021})
    check("BOUNDARY POLICY IS IMMUTABLE", _is_frozen(policy), True)
    check("INVALID BOUNDARY POLICY IS REJECTED", _raises(lambda: validate_execution_boundary_policy(replace(policy, host_fallback_allowed=True))), True)

    documents = [
        parse_boundary_request(fixture["request_bytes"]),
        parse_boundary_ready(fixture["ready_bytes"]),
        parse_boundary_authorize(fixture["authorize_bytes"]),
        parse_boundary_worker_result(fixture["worker_result_bytes"]),
        parse_boundary_terminal_payload(fixture["terminal_payload_bytes"]),
    ]
    check("ALL CANONICAL TRANSCRIPT DOCUMENTS PASS STRICT CONTRACTS", [item.kind for item in documents], ["request", "ready", "authorize", "worker_result", "terminal_payload"])
    check("PARSED DOCUMENTS ARE IMMUTABLE SNAPSHOTS", all(_is_frozen(item) for item in documents), True)
    check("DOCUMENT SERIALIZATION RETURNS A COPY", _serialization_is_copy(documents[0]), True)

    pin = _pin(fixture)
    check("VALID READY AND AUTHORIZATION TRANSCRIPT IS PINNED", {"ok": pin.ok, "status": pin.status, "issues": list(pin.issue_codes)}, {"ok": True, "status": "transcript_pinned", "issues": []})
    check("PIN REPORT HIDES NONCES AND PUBLIC KEY BYTES", {"repr": _secrets_absent(repr(pin)), "serialized": _secrets_absent(json.dumps(pin.to_dict()))}, {"repr": True, "serialized": True})
    report = _verify(fixture, pin)
    check("VALID SIGNED TRANSCRIPT PASSES WITH PINNED EVIDENCE", {"ok": report.ok, "status": report.status, "signature": report.signature_valid, "issues": list(report.issue_codes)}, {"ok": True, "status": SIGNED_TRANSCRIPT_STATUS_VERIFIED, "signature": True, "issues": []})
    check("SUCCESS REPORT NEVER AUTHORIZES EXECUTION", report.to_dict()["execution_authorized"], False)
    check("SIGNED TRANSCRIPT REPORT IS IMMUTABLE", _is_frozen(report), True)

    duplicate_request = fixture["request_bytes"].replace(b'{"schema_version":1,', b'{"schema_version":1,"schema_version":1,', 1)
    check("DUPLICATE JSON FIELD IS REJECTED", _contract_code(lambda: parse_boundary_request(duplicate_request)), "boundary_json_duplicate_field")
    unknown_request = fixture["request_bytes"][:-1] + b',"unexpected":true}'
    check("UNKNOWN JSON FIELD IS REJECTED", _contract_code(lambda: parse_boundary_request(unknown_request)), "boundary_fields_invalid")
    noncanonical_request = fixture["request_bytes"].replace(b',"backend_id"', b', "backend_id"', 1)
    check("NONCANONICAL JSON BYTES ARE REJECTED", _contract_code(lambda: parse_boundary_request(noncanonical_request)), "boundary_json_not_canonical")
    check("UTF8 BOM IS REJECTED", _contract_code(lambda: parse_boundary_request(b"\xef\xbb\xbf" + fixture["request_bytes"])), "boundary_json_bom_forbidden")
    reordered = json.loads(fixture["request_bytes"])
    reordered = {"backend_id": reordered.pop("backend_id"), **reordered}
    check("REORDERED FIELDS ARE REJECTED", _contract_code(lambda: parse_boundary_request(_canonical(reordered))), "boundary_fields_invalid")
    check("FLOAT JSON VALUE IS REJECTED", _contract_code(lambda: parse_boundary_request(fixture["request_bytes"].replace(b'"ready_timeout_seconds":120', b'"ready_timeout_seconds":120.0'))), "boundary_json_number_invalid")

    bad_ready = dict(fixture)
    bad_ready["ready_bytes"] = _mutate(bad_ready["ready_bytes"], ("public_key_sha256",), "0" * 64)
    check("PUBLIC KEY HASH SUBSTITUTION IS REJECTED", _pin(bad_ready).issue_codes[0], "boundary_public_key_hash_mismatch")
    bad_point = bytearray(_PUBLIC_BLOB)
    bad_point[-1] ^= 1
    check("OFF-CURVE PUBLIC KEY IS REJECTED", _crypto_code(lambda: validate_ecdsa_p256_public_blob(bytes(bad_point))), "boundary_public_key_point_invalid")
    check("OUT-OF-RANGE SIGNATURE IS REJECTED", _crypto_code(lambda: validate_ecdsa_p256_signature(b"\x00" * 64)), "boundary_signature_scalar_invalid")
    cng_runtime = _FakeCngRuntime()
    check("CNG RUNTIME VERIFIES AND CLOSES HANDLES", {"verified": verify_ecdsa_p256_sha256_cng(_PUBLIC_BLOB, b"message", b"\x01" * 64, _runtime=cng_runtime), "destroy": cng_runtime.destroy_calls, "close": cng_runtime.close_calls}, {"verified": True, "destroy": 1, "close": 1})
    check("CNG INVALID SIGNATURE STATUS FAILS CLOSED", verify_ecdsa_p256_sha256_cng(_PUBLIC_BLOB, b"message", b"\x01" * 64, _runtime=_FakeCngRuntime(verify_status=-1)), False)
    check("CNG PROVIDER FAILURE IS STRUCTURED", _crypto_code(lambda: verify_ecdsa_p256_sha256_cng(_PUBLIC_BLOB, b"message", b"\x01" * 64, _runtime=_FakeCngRuntime(open_status=-1))), "boundary_crypto_open_failed")
    check("CNG PUBLIC KEY IMPORT FAILURE IS STRUCTURED", _crypto_code(lambda: verify_ecdsa_p256_sha256_cng(_PUBLIC_BLOB, b"message", b"\x01" * 64, _runtime=_FakeCngRuntime(import_status=-1))), "boundary_public_key_import_failed")

    check("REQUEST ID REPLAY IS REJECTED", "boundary_transcript_mismatch" in _pin(fixture, expected_request_id="f" * 32).issue_codes, True)
    check("HOST NONCE SUBSTITUTION IS REJECTED", "boundary_transcript_mismatch" in _pin(fixture, expected_host_nonce="f" * 64).issue_codes, True)
    check("REQUEST BYTE SUBSTITUTION IS REJECTED", "boundary_request_replay_or_substitution" in _pin(fixture, expected_request_sha256="f" * 64).issue_codes, True)
    changed_bootstrap = dict(fixture)
    changed_bootstrap["bootstrap_bytes"] += b"changed"
    check("TRUSTED INPUT HASH SUBSTITUTION IS REJECTED", "boundary_artifact_hash_mismatch" in _pin(changed_bootstrap).issue_codes, True)
    bad_authorize = dict(fixture)
    bad_authorize["authorize_bytes"] = _mutate(bad_authorize["authorize_bytes"], ("ready_sha256",), "f" * 64)
    check("AUTHORIZE READY HASH SUBSTITUTION IS REJECTED", "boundary_transcript_mismatch" in _pin(bad_authorize).issue_codes, True)
    late_ready = dict(fixture)
    late_ready["ready_bytes"] = _mutate(late_ready["ready_bytes"], ("created_at_utc",), "2026-08-06T13:25:00.0000000Z")
    late_ready_payload = json.loads(late_ready["ready_bytes"])
    late_authorize_payload = json.loads(late_ready["authorize_bytes"])
    late_authorize_payload["ready_sha256"] = _sha256(late_ready["ready_bytes"])
    late_authorize_payload["authorization_deadline_epoch"] = 1786022790
    late_ready["authorize_bytes"] = _canonical(late_authorize_payload)
    check("READY WINDOW IS BOUNDED", "boundary_ready_window_invalid" in _pin(late_ready).issue_codes, True)
    bad_deadline = dict(fixture)
    bad_deadline["authorize_bytes"] = _mutate(bad_deadline["authorize_bytes"], ("authorization_deadline_epoch",), 1786029999)
    check("AUTHORIZATION WINDOW IS BOUNDED", "boundary_authorization_window_invalid" in _pin(bad_deadline).issue_codes, True)
    check("EXPIRED AUTHORIZATION IS REJECTED", "boundary_authorization_expired" in _pin(fixture, authorization_observed_epoch=1786022634).issue_codes, True)

    post_exit_ready = dict(fixture)
    post_exit_ready["ready_bytes"] = _mutate(post_exit_ready["ready_bytes"], ("controller_name",), r"NT AUTHORITY\SYSTEM-CHANGED")
    check("POST-PIN READY MUTATION IS REJECTED", "boundary_pinned_artifact_changed" in _verify(post_exit_ready, pin).issue_codes, True)
    post_exit_policy = dict(fixture)
    post_exit_policy["policy_bytes"] += b"\n"
    check("POST-PIN POLICY MUTATION IS REJECTED", "boundary_pinned_artifact_changed" in _verify(post_exit_policy, pin).issue_codes, True)
    bad_worker = dict(fixture)
    bad_worker["worker_result_bytes"] = _mutate(bad_worker["worker_result_bytes"], ("worker_is_administrator",), True)
    check("ADMINISTRATIVE WORKER RESULT IS REJECTED", "boundary_field_value_invalid" in _verify(bad_worker, pin).issue_codes, True)
    bad_terminal = dict(fixture)
    bad_terminal["terminal_payload_bytes"] = _mutate(bad_terminal["terminal_payload_bytes"], ("request_sha256",), "f" * 64)
    check("TERMINAL HASH-CHAIN SUBSTITUTION IS REJECTED", "boundary_transcript_mismatch" in _verify(bad_terminal, pin).issue_codes, True)
    mismatch_worker = dict(fixture)
    mismatch_worker["terminal_payload_bytes"] = _mutate(mismatch_worker["terminal_payload_bytes"], ("worker", "sid"), "S-1-5-21-1-2-3-1001")
    check("WORKER EVIDENCE MISMATCH IS REJECTED", "boundary_transcript_mismatch" in _verify(mismatch_worker, pin).issue_codes, True)
    late_terminal = dict(fixture)
    late_terminal["terminal_payload_bytes"] = _mutate(late_terminal["terminal_payload_bytes"], ("completed_at_utc",), "2026-08-06T13:24:00.0000000Z")
    check("LATE TERMINAL RESULT IS REJECTED", "boundary_terminal_late" in _verify(late_terminal, pin).issue_codes, True)
    early_terminal = dict(fixture)
    early_terminal["terminal_payload_bytes"] = _mutate(early_terminal["terminal_payload_bytes"], ("completed_at_utc",), "2026-08-06T13:22:22.0000000Z")
    check("EARLY TERMINAL RESULT IS REJECTED", "boundary_terminal_timing_invalid" in _verify(early_terminal, pin).issue_codes, True)
    short_signature = dict(fixture)
    short_signature["terminal_signature_bytes"] = b"x" * 63
    check("SHORT SIGNATURE IS REJECTED", "boundary_signature_size_invalid" in _verify(short_signature, pin).issue_codes, True)
    check("INVALID ECDSA SIGNATURE IS REJECTED", _verify(fixture, pin, lambda *_args: False).issue_codes, ("boundary_signature_invalid",))
    check("SIGNATURE VERIFIER FAILURE IS STRUCTURED", _verify(fixture, pin, lambda *_args: (_ for _ in ()).throw(RuntimeError("fake verifier failure"))).issue_codes, ("boundary_signature_verifier_failed",))
    check("NONBOOLEAN SIGNATURE VERIFIER RESULT IS REJECTED", _verify(fixture, pin, lambda *_args: 1).issue_codes, ("boundary_signature_verifier_result_invalid",))

    failed_pin = _pin(fixture, expected_request_id="f" * 32)
    check("FAILED PIN REPORT BLOCKS FINAL VERIFICATION", _verify(fixture, failed_pin).issue_codes[0], "boundary_pin_report_failed")
    check("RAW PIN REPORT IS REJECTED", _raises(lambda: verify_developer_task_execution_signed_transcript({}, policy_bytes=b"", bootstrap_bytes=b"", controller_bytes=b"", worker_source_bytes=b"", wsb_bytes=b"", request_bytes=b"", ready_bytes=b"", authorize_bytes=b"", worker_result_bytes=b"", terminal_payload_bytes=b"", terminal_signature_bytes=b"")), True)

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


def _is_frozen(value: Any) -> bool:
    try:
        setattr(value, "status", "changed")
    except (FrozenInstanceError, AttributeError):
        return True
    return False


def _serialization_is_copy(document: Any) -> bool:
    first = document.to_dict()
    first["schema_version"] = 999
    return document.to_dict()["schema_version"] == 1


def _secrets_absent(text: str) -> bool:
    return _HOST_NONCE not in text and _AUTHORIZATION_NONCE not in text and base64.b64encode(_PUBLIC_BLOB).decode("ascii") not in text


def _raises(callable_: Any) -> bool:
    try:
        callable_()
    except Exception:
        return True
    return False


def _contract_code(callable_: Any) -> str:
    try:
        callable_()
    except DeveloperTaskExecutionBoundaryContractError as exc:
        return exc.code
    return ""


def _crypto_code(callable_: Any) -> str:
    try:
        callable_()
    except DeveloperTaskExecutionBoundaryCryptoError as exc:
        return exc.code
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
