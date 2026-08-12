from __future__ import annotations

import base64
import hashlib
import inspect
import json

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
    build_developer_task_execution_runtime_attestation_payload,
)
from modules.developer.developer_task_execution_runtime_attestation_contract import (
    DeveloperTaskRuntimeAttestationContractError,
    parse_runtime_attestation_authorize,
    parse_runtime_attestation_ready,
    parse_runtime_attestation_request,
    parse_runtime_attestation_result,
    parse_runtime_attestation_terminal,
)
from modules.developer.developer_task_execution_runtime_attestation_payload import (
    build_runtime_attestation_authorize,
    build_runtime_attestation_request,
    build_runtime_attestation_wsb_config,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_ID,
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_verifier import (
    RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_PINNED,
    DeveloperTaskRuntimeAttestationTranscriptPinReport,
    pin_developer_task_execution_runtime_attestation_transcript,
    verify_developer_task_execution_runtime_attestation_transcript,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REQUEST_ID = "0123456789abcdef0123456789abcdef"
_HOST_NONCE = "11" * 32
_AUTH_NONCE = "22" * 32
_REQUEST_EPOCH = 1786500000
_READY_EPOCH = _REQUEST_EPOCH + 1
_AUTH_OBSERVED_EPOCH = _REQUEST_EPOCH + 2
_AUTH_DEADLINE_EPOCH = _REQUEST_EPOCH + 61
_PUBLIC_KEY = base64.b64decode(
    "RUNTMSAAAABrF9Hy4SxCR/i85uVjpEDydwN9gS3rM6D0oTlF2JjClk/jQuL+Gn+bjufrSnwPnhYrzjNXazFezsu2QGg3v1H1"
)
_SIGNATURE = base64.b64decode(
    "RpWlqdIzvEUPAvSVAsbO2KPK5jA/+tfOfqJN3y0QLW2sglwPmUs4TpAyIZtd5sqjd9JKCOQIsP/jBX7hIaRO1w=="
)
_GX = int("7CF27B188D034F7E8A52380304B51AC3C08969E277F21B35A60B48FC47669978", 16)
_GY = int("07775510DB8ED040293D9AC69F7430DBBA7DADE63CE982299E04B79D227873D1", 16)
_SECOND_PUBLIC_KEY = b"ECS1" + b"\x20\x00\x00\x00" + _GX.to_bytes(32, "big") + _GY.to_bytes(32, "big")


def _canonical(payload: dict[str, Any], *, final_lf: bool = False) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return raw + (b"\n" if final_lf else b"")


def _utc(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _mutate_document(data: bytes, key: str, value: Any, *, final_lf: bool = False) -> bytes:
    body = data[:-1] if final_lf else data
    payload = json.loads(body.decode("utf-8"))
    payload[key] = value
    return _canonical(payload, final_lf=final_lf)


def _mutate_nested(data: bytes, section: str, key: str, value: Any) -> bytes:
    payload = json.loads(data.decode("utf-8"))
    payload[section][key] = value
    return _canonical(payload)


def _issue_code(call: Callable[[], Any]) -> str:
    try:
        call()
    except DeveloperTaskRuntimeAttestationContractError as exc:
        return exc.code
    except Exception as exc:
        return type(exc).__name__
    return ""


def _sample_wsb() -> bytes:
    return build_runtime_attestation_wsb_config(
        input_host_path=r"C:\SkynetVSTest\Input",
        runtime_host_path=r"C:\SkynetVSTest\Runtime",
        control_host_path=r"C:\SkynetVSTest\Control",
        output_host_path=r"C:\SkynetVSTest\Output",
    )


def _sample_request(bundle: Any, wsb_bytes: bytes) -> Any:
    return build_runtime_attestation_request(
        request_id=_REQUEST_ID,
        host_nonce=_HOST_NONCE,
        created_at_epoch_seconds=float(_REQUEST_EPOCH),
        policy_sha256=bundle.policy.sha256,
        bootstrap_sha256=bundle.bootstrap.sha256,
        controller_sha256=bundle.controller.sha256,
        native_helper_sha256=bundle.native_helper.sha256,
        wsb_sha256=hashlib.sha256(wsb_bytes).hexdigest(),
    )


def _sample_ready(request: Any, *, public_key: bytes = _PUBLIC_KEY, ready_epoch: int = _READY_EPOCH) -> Any:
    request_payload = request.to_dict()
    public_hash = hashlib.sha256(public_key).hexdigest()
    payload = {
        "schema_version": 1,
        "backend_id": request_payload["backend_id"],
        "backend_policy_fingerprint": request_payload["backend_policy_fingerprint"],
        "runtime_attestation_id": request_payload["runtime_attestation_id"],
        "runtime_attestation_policy_fingerprint": request_payload["runtime_attestation_policy_fingerprint"],
        "request_id": request_payload["request_id"],
        "host_nonce": request_payload["host_nonce"],
        "request_sha256": request.sha256,
        "policy_sha256": request_payload["policy_sha256"],
        "bootstrap_sha256": request_payload["bootstrap_sha256"],
        "controller_sha256": request_payload["controller_sha256"],
        "native_helper_sha256": request_payload["native_helper_sha256"],
        "wsb_sha256": request_payload["wsb_sha256"],
        "controller_sid": "S-1-5-18",
        "controller_name": "NT AUTHORITY\\SYSTEM",
        "controller_is_system": True,
        "controller_is_administrator": True,
        "controller_integrity_rid": 0x4000,
        "key_is_ephemeral": True,
        "key_name_empty": True,
        "key_unique_name_empty": True,
        "public_key_format": "EccPublicBlob",
        "public_key_blob_base64": base64.b64encode(public_key).decode("ascii"),
        "public_key_sha256": public_hash,
        "runtime_source_sha256": request_payload["runtime_source_sha256"],
        "runtime_source_fingerprint": request_payload["runtime_source_fingerprint"],
        "runtime_source_provenance_policy_fingerprint": request_payload["runtime_source_provenance_policy_fingerprint"],
        "runtime_bundle_policy_fingerprint": request_payload["runtime_bundle_policy_fingerprint"],
        "runtime_tree_manifest_sha256": request_payload["runtime_tree_manifest_sha256"],
        "runtime_manifest_sha256": request_payload["runtime_manifest_sha256"],
        "runtime_bundle_fingerprint": request_payload["runtime_bundle_fingerprint"],
        "runtime_file_count": request_payload["runtime_file_count"],
        "runtime_total_bytes": request_payload["runtime_total_bytes"],
        "python_executable_sha256": request_payload["python_executable_sha256"],
        "python_dll_sha256": request_payload["python_dll_sha256"],
        "python_pth_sha256": request_payload["python_pth_sha256"],
        "stdlib_sha256": request_payload["stdlib_sha256"],
        "runtime_probe_sha256": request_payload["runtime_probe_sha256"],
        "runtime_runner_sha256": request_payload["runtime_runner_sha256"],
        "launch_contract_fingerprint": request_payload["launch_contract_fingerprint"],
        "input_write_blocked": True,
        "runtime_write_blocked": True,
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
            "runtime_identity_verified": True,
            "input_write_blocked": True,
            "runtime_write_blocked": True,
            "control_write_blocked": True,
            "output_writable": True,
        },
        "failed_ready_checks": [],
        "created_at_utc": _utc(ready_epoch),
        "overall_ok": True,
        "execution_authorized": False,
    }
    return parse_runtime_attestation_ready(_canonical(payload))


def _sample_authorize(request: Any, ready: Any, *, nonce: str = _AUTH_NONCE, deadline: int = _AUTH_DEADLINE_EPOCH) -> Any:
    return build_runtime_attestation_authorize(
        request=request,
        ready=ready,
        authorization_nonce=nonce,
        authorization_deadline_epoch=deadline,
    )


def _sample_runtime_result() -> bytes:
    return _canonical(
        {
            "architecture_bits": 64,
            "ensurepip_available": False,
            "executable_name": "python.exe",
            "execution_authorized": False,
            "flags": {
                "dont_write_bytecode": 1,
                "ignore_environment": 1,
                "isolated": 1,
                "no_user_site": 1,
                "safe_path": True,
                "utf8_mode": 1,
            },
            "implementation": "CPython",
            "machine": "AMD64",
            "pip_available": False,
            "probe_id": "skynetvs-v1b4-runtime-probe-v1",
            "python_environment_keys": [],
            "runtime_root_name": "SkynetVSRuntime",
            "runtime_root_write_blocked": True,
            "runtime_root_write_error": "PermissionError:5:13",
            "schema_version": 1,
            "site_imported": False,
            "sys_path": [r"C:\SkynetVSRuntime\python313.zip", r"C:\SkynetVSRuntime"],
            "version_info": [3, 13, 15],
        },
        final_lf=True,
    )


def _sample_terminal(request: Any, ready: Any, authorize: Any, runtime_result: Any, *, completed_epoch: int = _REQUEST_EPOCH + 10) -> bytes:
    request_payload = request.to_dict()
    ready_payload = ready.to_dict()
    authorize_payload = authorize.to_dict()
    runtime_payload = runtime_result.to_dict()
    payload = {
        "schema_version": 1,
        "backend_id": request_payload["backend_id"],
        "backend_policy_fingerprint": request_payload["backend_policy_fingerprint"],
        "runtime_attestation_id": request_payload["runtime_attestation_id"],
        "runtime_attestation_policy_fingerprint": request_payload["runtime_attestation_policy_fingerprint"],
        "request_id": request_payload["request_id"],
        "host_nonce": request_payload["host_nonce"],
        "authorization_nonce": authorize_payload["authorization_nonce"],
        "request_sha256": request.sha256,
        "ready_sha256": ready.sha256,
        "authorize_sha256": authorize.sha256,
        "policy_sha256": request_payload["policy_sha256"],
        "bootstrap_sha256": request_payload["bootstrap_sha256"],
        "controller_sha256": request_payload["controller_sha256"],
        "native_helper_sha256": request_payload["native_helper_sha256"],
        "wsb_sha256": request_payload["wsb_sha256"],
        "runtime_result_sha256": runtime_result.sha256,
        "public_key_sha256": ready_payload["public_key_sha256"],
        "runtime_bundle_fingerprint": request_payload["runtime_bundle_fingerprint"],
        "runtime_tree_manifest_sha256": request_payload["runtime_tree_manifest_sha256"],
        "runtime_manifest_sha256": request_payload["runtime_manifest_sha256"],
        "python_executable_sha256": request_payload["python_executable_sha256"],
        "python_pth_sha256": request_payload["python_pth_sha256"],
        "runtime_probe_sha256": request_payload["runtime_probe_sha256"],
        "runtime_runner_sha256": request_payload["runtime_runner_sha256"],
        "launch_contract_fingerprint": request_payload["launch_contract_fingerprint"],
        "controller": {
            "sid": ready_payload["controller_sid"],
            "name": ready_payload["controller_name"],
            "is_system": ready_payload["controller_is_system"],
            "is_administrator": ready_payload["controller_is_administrator"],
            "integrity_rid": ready_payload["controller_integrity_rid"],
            "key_is_ephemeral": ready_payload["key_is_ephemeral"],
            "key_name_empty": ready_payload["key_name_empty"],
            "key_unique_name_empty": ready_payload["key_unique_name_empty"],
        },
        "worker": {
            "account_created": True,
            "sid": "S-1-5-21-1-2-3-1001",
            "created_suspended": True,
            "resume_previous_count": 1,
            "assigned_before_resume": True,
            "result_ok": True,
            "exit_code": 0,
            "is_administrator": False,
            "integrity_rid": 0x2000,
            "worker_in_job": True,
            "job_closed": True,
            "sid_process_set_empty": True,
            "account_deleted": True,
        },
        "controls": {
            "input_write_blocked": ready_payload["input_write_blocked"],
            "runtime_write_blocked": ready_payload["runtime_write_blocked"],
            "control_write_blocked": ready_payload["control_write_blocked"],
            "output_writable": ready_payload["output_writable"],
            "ipv4_default_route_present": False,
            "ipv4_external_tcp_reachable": False,
            "ipv6_default_route_present": False,
            "ipv6_external_tcp_reachable": False,
        },
        "runtime": {
            "result_ok": True,
            "probe_id": runtime_payload["probe_id"],
            "implementation": runtime_payload["implementation"],
            "version": runtime_payload["version_info"],
            "architecture_bits": runtime_payload["architecture_bits"],
            "machine": runtime_payload["machine"],
            "runtime_root_write_blocked": runtime_payload["runtime_root_write_blocked"],
            "environment_clean": not runtime_payload["python_environment_keys"],
            "pip_absent": not runtime_payload["pip_available"],
            "ensurepip_absent": not runtime_payload["ensurepip_available"],
            "site_absent": not runtime_payload["site_imported"],
            "sys_path_exact": True,
        },
        "shutdown": {"scheduled": True, "delay_seconds": 8},
        "completed_at_utc": _utc(completed_epoch),
        "overall_ok": True,
        "execution_authorized": False,
    }
    return _canonical(payload)


def _pin(*, request: Any, ready: Any, authorize: Any, wsb_bytes: bytes, **overrides: Any) -> Any:
    arguments = {
        "expected_request_id": _REQUEST_ID,
        "expected_host_nonce": _HOST_NONCE,
        "expected_authorization_nonce": _AUTH_NONCE,
        "expected_request_sha256": request.sha256,
        "authorization_observed_epoch": _AUTH_OBSERVED_EPOCH,
        "wsb_bytes": wsb_bytes,
        "request_bytes": request.canonical_bytes,
        "ready_bytes": ready.canonical_bytes,
        "authorize_bytes": authorize.canonical_bytes,
    }
    arguments.update(overrides)
    return pin_developer_task_execution_runtime_attestation_transcript(**arguments)


def _verify(pin: Any, *, wsb_bytes: bytes, request: Any, ready: Any, authorize: Any, runtime_result_bytes: bytes, terminal_bytes: bytes, signature: bytes = _SIGNATURE, verifier: Callable[[bytes, bytes, bytes], bool] | None = None) -> Any:
    return verify_developer_task_execution_runtime_attestation_transcript(
        pin,
        wsb_bytes=wsb_bytes,
        request_bytes=request.canonical_bytes,
        ready_bytes=ready.canonical_bytes,
        authorize_bytes=authorize.canonical_bytes,
        runtime_result_bytes=runtime_result_bytes,
        terminal_payload_bytes=terminal_bytes,
        terminal_signature_bytes=signature,
        signature_verifier=verifier,
    )


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        if not ok:
            fail_count += 1
        print()
        print(f"=== {name} ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2, default=str))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    bundle = build_developer_task_execution_runtime_attestation_payload()
    wsb_bytes = _sample_wsb()
    request = _sample_request(bundle, wsb_bytes)
    ready = _sample_ready(request)
    authorize = _sample_authorize(request, ready)
    runtime_result_bytes = _sample_runtime_result()
    runtime_result = parse_runtime_attestation_result(runtime_result_bytes)
    terminal_bytes = _sample_terminal(request, ready, authorize, runtime_result)

    check(
        "V1B4C2A REUSES THE EXACT VERIFIED V1B4C1 PAYLOAD",
        {
            "payload": bundle.payload_fingerprint,
            "attestation_policy": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
            "request_runtime_bundle": request.field("runtime_bundle_fingerprint"),
            "execution_authorized": request.field("execution_authorized"),
        },
        {
            "payload": RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
            "attestation_policy": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
            "request_runtime_bundle": request.field("runtime_bundle_fingerprint"),
            "execution_authorized": False,
        },
    )

    pin_signature = inspect.signature(pin_developer_task_execution_runtime_attestation_transcript)
    verify_signature = inspect.signature(verify_developer_task_execution_runtime_attestation_transcript)
    check(
        "V1B4C2A PUBLIC APIS HAVE NO FILESYSTEM PROCESS SANDBOX OR EXECUTION INPUT",
        {
            "pin": list(pin_signature.parameters),
            "verify": list(verify_signature.parameters),
        },
        {
            "pin": [
                "expected_request_id", "expected_host_nonce", "expected_authorization_nonce", "expected_request_sha256",
                "authorization_observed_epoch", "wsb_bytes", "request_bytes", "ready_bytes", "authorize_bytes",
            ],
            "verify": [
                "pin_report", "wsb_bytes", "request_bytes", "ready_bytes", "authorize_bytes", "runtime_result_bytes",
                "terminal_payload_bytes", "terminal_signature_bytes", "signature_verifier",
            ],
        },
    )

    pin = _pin(request=request, ready=ready, authorize=authorize, wsb_bytes=wsb_bytes)
    check(
        "V1B4C2A VALID CANONICAL REQUEST READY AND AUTHORIZATION ARE PINNED",
        {
            "ok": pin.ok,
            "status": pin.status,
            "issues": list(pin.issue_codes),
            "request": pin.to_dict()["request_sha256"],
            "ready": pin.to_dict()["ready_sha256"],
            "authorize": pin.to_dict()["authorize_sha256"],
            "execution_authorized": pin.to_dict()["execution_authorized"],
        },
        {
            "ok": True,
            "status": RUNTIME_ATTESTATION_TRANSCRIPT_STATUS_PINNED,
            "issues": [],
            "request": request.sha256,
            "ready": ready.sha256,
            "authorize": authorize.sha256,
            "execution_authorized": False,
        },
    )

    pin_json = json.dumps(pin.to_dict(), ensure_ascii=False, sort_keys=True)
    check(
        "V1B4C2A PIN REPORT IS IMMUTABLE SERIALIZABLE AND REDACTED",
        {
            "immutable": _issue_code(lambda: setattr(pin, "status", "forged")) == "FrozenInstanceError",
            "json": bool(json.loads(pin_json)),
            "host_nonce_hidden": _HOST_NONCE not in pin_json and _HOST_NONCE not in repr(pin),
            "authorization_nonce_hidden": _AUTH_NONCE not in pin_json and _AUTH_NONCE not in repr(pin),
            "public_key_hidden": base64.b64encode(_PUBLIC_KEY).decode("ascii") not in pin_json and base64.b64encode(_PUBLIC_KEY).decode("ascii") not in repr(pin),
        },
        {
            "immutable": True,
            "json": True,
            "host_nonce_hidden": True,
            "authorization_nonce_hidden": True,
            "public_key_hidden": True,
        },
    )

    request_replay = _pin(
        request=request,
        ready=ready,
        authorize=authorize,
        wsb_bytes=wsb_bytes,
        expected_request_id="ff" * 16,
    )
    check("V1B4C2A REQUEST ID REPLAY IS REJECTED", "runtime_attestation_request_replay_or_substitution" in request_replay.issue_codes, True)

    nonce_replay = _pin(
        request=request,
        ready=ready,
        authorize=authorize,
        wsb_bytes=wsb_bytes,
        expected_host_nonce="33" * 32,
    )
    check("V1B4C2A HOST NONCE SUBSTITUTION IS REJECTED", "runtime_attestation_request_replay_or_substitution" in nonce_replay.issue_codes, True)

    request_hash_replay = _pin(
        request=request,
        ready=ready,
        authorize=authorize,
        wsb_bytes=wsb_bytes,
        expected_request_sha256="44" * 32,
    )
    check("V1B4C2A REQUEST BYTE SUBSTITUTION IS REJECTED", "runtime_attestation_request_replay_or_substitution" in request_hash_replay.issue_codes, True)

    auth_nonce_replay = _pin(
        request=request,
        ready=ready,
        authorize=authorize,
        wsb_bytes=wsb_bytes,
        expected_authorization_nonce="55" * 32,
    )
    check("V1B4C2A AUTHORIZATION NONCE SUBSTITUTION IS REJECTED", "runtime_attestation_authorization_nonce_mismatch" in auth_nonce_replay.issue_codes, True)

    wsb_replay = _pin(request=request, ready=ready, authorize=authorize, wsb_bytes=wsb_bytes + b" ")
    check("V1B4C2A WSB PAYLOAD SUBSTITUTION IS REJECTED", "runtime_attestation_payload_hash_mismatch" in wsb_replay.issue_codes, True)

    mutated_request_payload = request.to_dict()
    mutated_request_payload["policy_sha256"] = "66" * 32
    mutated_request_bytes = _canonical(mutated_request_payload)
    mutated_request = parse_runtime_attestation_request(mutated_request_bytes)
    payload_drift = pin_developer_task_execution_runtime_attestation_transcript(
        expected_request_id=_REQUEST_ID,
        expected_host_nonce=_HOST_NONCE,
        expected_authorization_nonce=_AUTH_NONCE,
        expected_request_sha256=mutated_request.sha256,
        authorization_observed_epoch=_AUTH_OBSERVED_EPOCH,
        wsb_bytes=wsb_bytes,
        request_bytes=mutated_request.canonical_bytes,
        ready_bytes=ready.canonical_bytes,
        authorize_bytes=authorize.canonical_bytes,
    )
    check("V1B4C2A CANONICAL PAYLOAD HASH SUBSTITUTION IS REJECTED", "runtime_attestation_payload_hash_mismatch" in payload_drift.issue_codes, True)

    runtime_identity_drift = _mutate_document(request.canonical_bytes, "runtime_bundle_fingerprint", "77" * 32)
    runtime_identity_pin = pin_developer_task_execution_runtime_attestation_transcript(
        expected_request_id=_REQUEST_ID,
        expected_host_nonce=_HOST_NONCE,
        expected_authorization_nonce=_AUTH_NONCE,
        expected_request_sha256=hashlib.sha256(runtime_identity_drift).hexdigest(),
        authorization_observed_epoch=_AUTH_OBSERVED_EPOCH,
        wsb_bytes=wsb_bytes,
        request_bytes=runtime_identity_drift,
        ready_bytes=ready.canonical_bytes,
        authorize_bytes=authorize.canonical_bytes,
    )
    check("V1B4C2A RUNTIME IDENTITY SUBSTITUTION IS REJECTED", "runtime_attestation_identity_mismatch" in runtime_identity_pin.issue_codes, True)

    bad_key_ready = _sample_ready(request, public_key=b"ECS1" + b"\x20\x00\x00\x00" + bytes(range(64)))
    bad_key_authorize = _sample_authorize(request, bad_key_ready)
    bad_key_pin = _pin(request=request, ready=bad_key_ready, authorize=bad_key_authorize, wsb_bytes=wsb_bytes)
    check("V1B4C2A OFF CURVE PUBLIC KEY IS REJECTED", "boundary_public_key_point_invalid" in bad_key_pin.issue_codes, True)

    early_ready = _sample_ready(request, ready_epoch=_REQUEST_EPOCH)
    early_authorize = _sample_authorize(request, early_ready)
    early_ready_pin = _pin(request=request, ready=early_ready, authorize=early_authorize, wsb_bytes=wsb_bytes)
    check("V1B4C2A READY TEMPORAL INVERSION IS REJECTED", "runtime_attestation_ready_window_invalid" in early_ready_pin.issue_codes, True)

    late_ready = _sample_ready(request, ready_epoch=_REQUEST_EPOCH + 122)
    late_authorize = _sample_authorize(request, late_ready, deadline=_REQUEST_EPOCH + 180)
    late_ready_pin = _pin(request=request, ready=late_ready, authorize=late_authorize, wsb_bytes=wsb_bytes, authorization_observed_epoch=_REQUEST_EPOCH + 123)
    check("V1B4C2A LATE READY IS REJECTED", "runtime_attestation_ready_window_invalid" in late_ready_pin.issue_codes, True)

    inverted_authorize = _sample_authorize(request, ready, deadline=_REQUEST_EPOCH)
    inverted_auth_pin = _pin(request=request, ready=ready, authorize=inverted_authorize, wsb_bytes=wsb_bytes, authorization_observed_epoch=_REQUEST_EPOCH + 1)
    check("V1B4C2A AUTHORIZATION TEMPORAL INVERSION IS REJECTED", "runtime_attestation_authorization_window_invalid" in inverted_auth_pin.issue_codes, True)

    too_late_authorize = _sample_authorize(request, ready, deadline=_REQUEST_EPOCH + 100)
    too_late_auth_pin = _pin(request=request, ready=ready, authorize=too_late_authorize, wsb_bytes=wsb_bytes)
    check("V1B4C2A AUTHORIZATION WINDOW IS BOUNDED", "runtime_attestation_authorization_window_invalid" in too_late_auth_pin.issue_codes, True)

    observed_before_ready = _pin(request=request, ready=ready, authorize=authorize, wsb_bytes=wsb_bytes, authorization_observed_epoch=_REQUEST_EPOCH)
    check("V1B4C2A AUTHORIZATION HOST TIMING INVERSION IS REJECTED", "runtime_attestation_authorization_temporal_inversion" in observed_before_ready.issue_codes, True)

    expired_authorize = _pin(request=request, ready=ready, authorize=authorize, wsb_bytes=wsb_bytes, authorization_observed_epoch=_AUTH_DEADLINE_EPOCH + 1)
    check("V1B4C2A EXPIRED AUTHORIZATION IS REJECTED", "runtime_attestation_authorization_expired" in expired_authorize.issue_codes, True)

    good_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_bytes,
        verifier=lambda public_key, message, signature: public_key == _PUBLIC_KEY and message == terminal_bytes and signature == _SIGNATURE,
    )
    check(
        "V1B4C2A VALID SIGNED RUNTIME TRANSCRIPT PASSES WITH INJECTED CRYPTO",
        {
            "ok": good_report.ok,
            "status": good_report.status,
            "signature": good_report.signature_valid,
            "runtime": good_report.runtime_result_verified,
            "terminal": good_report.terminal_verified,
            "issues": list(good_report.issue_codes),
            "execution_authorized": good_report.to_dict()["execution_authorized"],
        },
        {
            "ok": True,
            "status": "runtime_attestation_transcript_verified",
            "signature": True,
            "runtime": True,
            "terminal": True,
            "issues": [],
            "execution_authorized": False,
        },
    )

    report_json = json.dumps(good_report.to_dict(), ensure_ascii=False, sort_keys=True)
    check(
        "V1B4C2A FINAL REPORT IS IMMUTABLE SERIALIZABLE AND REDACTED",
        {
            "immutable": _issue_code(lambda: setattr(good_report, "status", "forged")) == "FrozenInstanceError",
            "json": bool(json.loads(report_json)),
            "host_nonce_hidden": _HOST_NONCE not in report_json and _HOST_NONCE not in repr(good_report),
            "authorization_nonce_hidden": _AUTH_NONCE not in report_json and _AUTH_NONCE not in repr(good_report),
            "public_key_hidden": base64.b64encode(_PUBLIC_KEY).decode("ascii") not in report_json and base64.b64encode(_PUBLIC_KEY).decode("ascii") not in repr(good_report),
        },
        {
            "immutable": True,
            "json": True,
            "host_nonce_hidden": True,
            "authorization_nonce_hidden": True,
            "public_key_hidden": True,
        },
    )

    request_changed_report = verify_developer_task_execution_runtime_attestation_transcript(
        pin,
        wsb_bytes=wsb_bytes,
        request_bytes=request.canonical_bytes + b" ",
        ready_bytes=ready.canonical_bytes,
        authorize_bytes=authorize.canonical_bytes,
        runtime_result_bytes=runtime_result_bytes,
        terminal_payload_bytes=terminal_bytes,
        terminal_signature_bytes=_SIGNATURE,
        signature_verifier=lambda *_: True,
    )
    check("V1B4C2A POST PIN REQUEST MUTATION IS REJECTED", "runtime_attestation_pinned_artifact_changed" in request_changed_report.issue_codes, True)

    second_ready = _sample_ready(request, public_key=_SECOND_PUBLIC_KEY)
    second_authorize = _sample_authorize(request, second_ready)
    ready_changed_report = verify_developer_task_execution_runtime_attestation_transcript(
        pin,
        wsb_bytes=wsb_bytes,
        request_bytes=request.canonical_bytes,
        ready_bytes=second_ready.canonical_bytes,
        authorize_bytes=second_authorize.canonical_bytes,
        runtime_result_bytes=runtime_result_bytes,
        terminal_payload_bytes=terminal_bytes,
        terminal_signature_bytes=_SIGNATURE,
        signature_verifier=lambda *_: True,
    )
    check("V1B4C2A POST PIN PUBLIC KEY READY MUTATION IS REJECTED", "runtime_attestation_pinned_artifact_changed" in ready_changed_report.issue_codes, True)

    changed_authorize = _sample_authorize(request, ready, nonce="88" * 32)
    authorize_changed_report = verify_developer_task_execution_runtime_attestation_transcript(
        pin,
        wsb_bytes=wsb_bytes,
        request_bytes=request.canonical_bytes,
        ready_bytes=ready.canonical_bytes,
        authorize_bytes=changed_authorize.canonical_bytes,
        runtime_result_bytes=runtime_result_bytes,
        terminal_payload_bytes=terminal_bytes,
        terminal_signature_bytes=_SIGNATURE,
        signature_verifier=lambda *_: True,
    )
    check("V1B4C2A POST PIN AUTHORIZATION MUTATION IS REJECTED", "runtime_attestation_pinned_artifact_changed" in authorize_changed_report.issue_codes, True)

    wsb_changed_report = _verify(
        pin,
        wsb_bytes=wsb_bytes + b" ",
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_bytes,
        verifier=lambda *_: True,
    )
    check("V1B4C2A POST PIN WSB MUTATION IS REJECTED", "runtime_attestation_pinned_artifact_changed" in wsb_changed_report.issue_codes, True)

    runtime_changed_bytes = _mutate_document(runtime_result_bytes, "machine", "X86_64", final_lf=True)
    runtime_changed_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_changed_bytes,
        terminal_bytes=terminal_bytes,
        verifier=lambda *_: True,
    )
    check("V1B4C2A RUNTIME RESULT SUBSTITUTION IS REJECTED", "runtime_attestation_transcript_mismatch" in runtime_changed_report.issue_codes, True)

    terminal_hash_changed = _mutate_document(terminal_bytes, "runtime_result_sha256", "99" * 32)
    terminal_hash_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_hash_changed,
        verifier=lambda *_: True,
    )
    check("V1B4C2A TERMINAL RUNTIME RESULT HASH SUBSTITUTION IS REJECTED", "runtime_attestation_transcript_mismatch" in terminal_hash_report.issue_codes, True)

    terminal_controller_changed = _mutate_nested(terminal_bytes, "controller", "name", "SYSTEM-OTHER")
    terminal_controller_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_controller_changed,
        verifier=lambda *_: True,
    )
    check("V1B4C2A TERMINAL CONTROLLER READY MISMATCH IS REJECTED", "runtime_attestation_transcript_mismatch" in terminal_controller_report.issue_codes, True)

    terminal_runtime_changed = _mutate_nested(terminal_bytes, "runtime", "machine", "X86_64")
    terminal_runtime_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_runtime_changed,
        verifier=lambda *_: True,
    )
    check("V1B4C2A TERMINAL RUNTIME SUMMARY MISMATCH IS REJECTED", "runtime_attestation_transcript_mismatch" in terminal_runtime_report.issue_codes, True)

    early_terminal = _sample_terminal(request, ready, authorize, runtime_result, completed_epoch=_AUTH_OBSERVED_EPOCH)
    early_terminal_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=early_terminal,
        verifier=lambda *_: True,
    )
    check("V1B4C2A TERMINAL TEMPORAL INVERSION IS REJECTED", "runtime_attestation_terminal_timing_invalid" in early_terminal_report.issue_codes, True)

    late_terminal = _sample_terminal(request, ready, authorize, runtime_result, completed_epoch=_AUTH_DEADLINE_EPOCH + 60 + 45 + 2)
    late_terminal_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=late_terminal,
        verifier=lambda *_: True,
    )
    check("V1B4C2A TERMINAL WINDOW IS BOUNDED", "runtime_attestation_terminal_window_invalid" in late_terminal_report.issue_codes, True)

    short_signature_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_bytes,
        signature=b"x" * 63,
        verifier=lambda *_: True,
    )
    check("V1B4C2A SHORT SIGNATURE IS REJECTED", "runtime_attestation_signature_size_invalid" in short_signature_report.issue_codes, True)

    zero_signature_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_bytes,
        signature=b"\x00" * 64,
        verifier=lambda *_: True,
    )
    check("V1B4C2A ZERO SIGNATURE IS REJECTED", "runtime_attestation_signature_invalid" in zero_signature_report.issue_codes, True)

    scalar_signature = b"\x00" * 32 + (1).to_bytes(32, "big")
    scalar_signature_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_bytes,
        signature=scalar_signature,
        verifier=lambda *_: True,
    )
    check("V1B4C2A OUT OF RANGE SIGNATURE SCALAR IS REJECTED", "boundary_signature_scalar_invalid" in scalar_signature_report.issue_codes, True)

    invalid_signature_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_bytes,
        verifier=lambda *_: False,
    )
    check("V1B4C2A INVALID ECDSA SIGNATURE IS REJECTED", list(invalid_signature_report.issue_codes), ["runtime_attestation_signature_invalid"])

    verifier_failure_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_bytes,
        verifier=lambda *_: (_ for _ in ()).throw(RuntimeError("fake verifier failure")),
    )
    check("V1B4C2A SIGNATURE VERIFIER FAILURE IS STRUCTURED", list(verifier_failure_report.issue_codes), ["runtime_attestation_signature_verifier_failed"])

    nonbool_report = _verify(
        pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_bytes,
        verifier=lambda *_: 1,
    )
    check("V1B4C2A NONBOOLEAN SIGNATURE VERIFIER RESULT IS REJECTED", list(nonbool_report.issue_codes), ["runtime_attestation_signature_verifier_result_invalid"])

    failed_pin = _pin(request=request, ready=ready, authorize=authorize, wsb_bytes=wsb_bytes, expected_request_id="aa" * 16)
    failed_pin_report = _verify(
        failed_pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_bytes,
        verifier=lambda *_: True,
    )
    check("V1B4C2A FAILED PIN REPORT BLOCKS FINAL VERIFICATION", "runtime_attestation_pin_report_failed" in failed_pin_report.issue_codes, True)

    forged_pin = replace(pin)
    forged_pin_report = _verify(
        forged_pin,
        wsb_bytes=wsb_bytes,
        request=request,
        ready=ready,
        authorize=authorize,
        runtime_result_bytes=runtime_result_bytes,
        terminal_bytes=terminal_bytes,
        verifier=lambda *_: True,
    )
    check("V1B4C2A FORGED DATACLASS PIN REPORT IS REJECTED", "runtime_attestation_pin_report_failed" in forged_pin_report.issue_codes, True)

    raw_pin_rejected = False
    try:
        verify_developer_task_execution_runtime_attestation_transcript(
            {},
            wsb_bytes=wsb_bytes,
            request_bytes=request.canonical_bytes,
            ready_bytes=ready.canonical_bytes,
            authorize_bytes=authorize.canonical_bytes,
            runtime_result_bytes=runtime_result_bytes,
            terminal_payload_bytes=terminal_bytes,
            terminal_signature_bytes=_SIGNATURE,
        )
    except TypeError:
        raw_pin_rejected = True
    check("V1B4C2A RAW PIN REPORT IS REJECTED", raw_pin_rejected, True)

    noncanonical_request = request.canonical_bytes + b" "
    noncanonical_pin = pin_developer_task_execution_runtime_attestation_transcript(
        expected_request_id=_REQUEST_ID,
        expected_host_nonce=_HOST_NONCE,
        expected_authorization_nonce=_AUTH_NONCE,
        expected_request_sha256=hashlib.sha256(noncanonical_request).hexdigest(),
        authorization_observed_epoch=_AUTH_OBSERVED_EPOCH,
        wsb_bytes=wsb_bytes,
        request_bytes=noncanonical_request,
        ready_bytes=ready.canonical_bytes,
        authorize_bytes=authorize.canonical_bytes,
    )
    check("V1B4C2A NONCANONICAL JSON REMAINS REJECTED BY V1B4C1 CONTRACT", "runtime_attestation_json_not_canonical" in noncanonical_pin.issue_codes, True)

    duplicate_request = request.canonical_bytes.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1', 1)
    duplicate_pin = pin_developer_task_execution_runtime_attestation_transcript(
        expected_request_id=_REQUEST_ID,
        expected_host_nonce=_HOST_NONCE,
        expected_authorization_nonce=_AUTH_NONCE,
        expected_request_sha256=hashlib.sha256(duplicate_request).hexdigest(),
        authorization_observed_epoch=_AUTH_OBSERVED_EPOCH,
        wsb_bytes=wsb_bytes,
        request_bytes=duplicate_request,
        ready_bytes=ready.canonical_bytes,
        authorize_bytes=authorize.canonical_bytes,
    )
    check("V1B4C2A DUPLICATE JSON FIELD REMAINS REJECTED BY V1B4C1 CONTRACT", "runtime_attestation_json_duplicate_field" in duplicate_pin.issue_codes, True)

    verifier_source = (PROJECT_ROOT / "modules" / "developer" / "developer_task_execution_runtime_attestation_verifier.py").read_text(encoding="utf-8")
    check(
        "V1B4C2A VERIFIER HAS NO FILESYSTEM PROCESS SANDBOX OR CANDIDATE PYTHON LAUNCH SURFACE",
        {
            "pathlib": "pathlib" in verifier_source,
            "subprocess": "subprocess" in verifier_source,
            "popen": "Popen(" in verifier_source,
            "system": "os.system" in verifier_source,
            "windows_sandbox": "WindowsSandbox" in verifier_source,
            "runtime_builder": "build_developer_task_execution_runtime_bundle" in verifier_source,
            "workspace": "developer_task_workspace" in verifier_source,
            "execution_true": "execution_authorized\": True" in verifier_source,
        },
        {
            "pathlib": False,
            "subprocess": False,
            "popen": False,
            "system": False,
            "windows_sandbox": False,
            "runtime_builder": False,
            "workspace": False,
            "execution_true": False,
        },
    )

    check(
        "V1B4C2A CNG VERIFICATION IS THE DEFAULT FINAL CRYPTO PATH",
        "verify_ecdsa_p256_sha256_cng" in verifier_source and "signature_verifier or verify_ecdsa_p256_sha256_cng" in verifier_source,
        True,
    )

    check(
        "V1B4C2A REPORTS NEVER AUTHORIZE DEVELOPER EXECUTION",
        {
            "pin": pin.to_dict()["execution_authorized"],
            "final": good_report.to_dict()["execution_authorized"],
        },
        {"pin": False, "final": False},
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
