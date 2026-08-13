from __future__ import annotations

import base64
import hashlib
import inspect
import json
import re

from dataclasses import FrozenInstanceError, replace
from typing import Any, Callable

from modules.developer.developer_task_execution_boundary_policy import (
    SIGNED_BOUNDARY_FINGERPRINT,
    WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1,
)
from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_BOOTSTRAP_SHA256,
    RUNTIME_ATTESTATION_CONTROLLER_SHA256,
    RUNTIME_ATTESTATION_NATIVE_HELPER_SHA256,
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
    RUNTIME_ATTESTATION_POLICY_BYTES_SHA256,
    RUNTIME_ATTESTATION_WSB_TEMPLATE_SHA256,
    build_developer_task_execution_runtime_attestation_payload,
)
from modules.developer.developer_task_execution_runtime_attestation_contract import (
    DeveloperTaskRuntimeAttestationContractError,
    parse_runtime_attestation_authorize,
    parse_runtime_attestation_ready,
    parse_runtime_attestation_request,
    parse_runtime_attestation_result,
    parse_runtime_attestation_terminal,
    validate_runtime_attestation_signature_bytes,
)
from modules.developer.developer_task_execution_runtime_attestation_payload import (
    build_runtime_attestation_authorize,
    build_runtime_attestation_request,
    build_runtime_attestation_wsb_config,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_CONTROL_ROOT,
    RUNTIME_ATTESTATION_ID,
    RUNTIME_ATTESTATION_INPUT_ROOT,
    RUNTIME_ATTESTATION_OUTPUT_ROOT,
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
    RUNTIME_ATTESTATION_RUNTIME_ROOT,
    TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1,
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


_EXPECTED_POLICY_FINGERPRINT = "31c4f8de17e999db2d064a8aca4e95d3e2400f21a229317e83b1d5700d1e3c48"
_EXPECTED_PAYLOAD_FINGERPRINT = "47820f76e8fb0c5542592057c8a4258f968841b12aff6d1c3ee9d69a3e4c1e13"
_EXPECTED_BOOTSTRAP_SHA256 = "73b65b3731f94bc6b0042848e93721877fc2f0f8a70c861e08b17e4303a534bc"
_EXPECTED_NATIVE_SHA256 = "bb9e98675e742b8693da8fee270d045ef9bfa51d4440f461d19cc5b22ee4ca2e"
_EXPECTED_CONTROLLER_SHA256 = "3ccf95e6ace6c14bb9fb697592202655da4579e76bfaf9e3a704b83cc92b7b2e"
_EXPECTED_WSB_TEMPLATE_SHA256 = "81861905167211b29fbff7179878b6b671c31b731af482166913b5e20416375f"
_REQUEST_ID = "0123456789abcdef0123456789abcdef"
_HOST_NONCE = "11" * 32
_AUTH_NONCE = "22" * 32
_HASH_A = "33" * 32
_HASH_B = "44" * 32
_HASH_C = "55" * 32
_HASH_D = "66" * 32
_HASH_E = "77" * 32


def _canonical(payload: dict[str, Any], *, final_lf: bool = False) -> bytes:
    result = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return result + (b"\n" if final_lf else b"")


def _error_code(call: Callable[[], Any]) -> str:
    try:
        call()
    except DeveloperTaskRuntimeAttestationContractError as exc:
        return exc.code
    except Exception as exc:  # pragma: no cover - makes a failing case visible instead of hiding it
        return type(exc).__name__
    return ""


def _sample_request(bundle: Any) -> Any:
    return build_runtime_attestation_request(
        request_id=_REQUEST_ID,
        host_nonce=_HOST_NONCE,
        created_at_epoch_seconds=1786500000.0,
        policy_sha256=bundle.policy.sha256,
        bootstrap_sha256=bundle.bootstrap.sha256,
        controller_sha256=bundle.controller.sha256,
        native_helper_sha256=bundle.native_helper.sha256,
        wsb_sha256=_HASH_E,
    )


def _sample_ready(request: Any) -> Any:
    request_payload = request.to_dict()
    public_blob = b"ECS1" + b"\x20\x00\x00\x00" + bytes(range(64))
    public_hash = hashlib.sha256(public_blob).hexdigest()
    payload = {
        "schema_version": 1,
        "backend_id": request_payload["backend_id"],
        "backend_policy_fingerprint": request_payload["backend_policy_fingerprint"],
        "runtime_attestation_id": RUNTIME_ATTESTATION_ID,
        "runtime_attestation_policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
        "request_id": _REQUEST_ID,
        "host_nonce": _HOST_NONCE,
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
        "public_key_blob_base64": base64.b64encode(public_blob).decode("ascii"),
        "public_key_sha256": public_hash,
        "runtime_source_sha256": RUNTIME_SOURCE_SHA256,
        "runtime_source_fingerprint": RUNTIME_SOURCE_FINGERPRINT,
        "runtime_source_provenance_policy_fingerprint": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
        "runtime_bundle_policy_fingerprint": RUNTIME_BUNDLE_POLICY_FINGERPRINT,
        "runtime_tree_manifest_sha256": RUNTIME_TREE_MANIFEST_SHA256,
        "runtime_manifest_sha256": RUNTIME_MANIFEST_SHA256,
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        "runtime_file_count": RUNTIME_BUNDLE_FILE_COUNT,
        "runtime_total_bytes": RUNTIME_BUNDLE_TOTAL_BYTES,
        "python_executable_sha256": RUNTIME_SOURCE_PYTHON_EXE_SHA256,
        "python_dll_sha256": RUNTIME_SOURCE_PYTHON_DLL_SHA256,
        "python_pth_sha256": RUNTIME_LOCKED_PTH_SHA256,
        "stdlib_sha256": RUNTIME_SOURCE_STDLIB_SHA256,
        "runtime_probe_sha256": RUNTIME_PROBE_SHA256,
        "runtime_runner_sha256": RUNTIME_RUNNER_SHA256,
        "launch_contract_fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
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
        "created_at_utc": "2026-08-12T00:00:01.000000Z",
        "overall_ok": True,
        "execution_authorized": False,
    }
    return parse_runtime_attestation_ready(_canonical(payload))


def _sample_runtime_result() -> bytes:
    payload = {
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
    }
    return _canonical(payload, final_lf=True)


def _sample_terminal(request: Any, ready: Any, authorize: Any, runtime_result: Any) -> bytes:
    request_payload = request.to_dict()
    ready_payload = ready.to_dict()
    authorize_payload = authorize.to_dict()
    payload = {
        "schema_version": 1,
        "backend_id": request_payload["backend_id"],
        "backend_policy_fingerprint": request_payload["backend_policy_fingerprint"],
        "runtime_attestation_id": RUNTIME_ATTESTATION_ID,
        "runtime_attestation_policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
        "request_id": _REQUEST_ID,
        "host_nonce": _HOST_NONCE,
        "authorization_nonce": _AUTH_NONCE,
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
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        "runtime_tree_manifest_sha256": RUNTIME_TREE_MANIFEST_SHA256,
        "runtime_manifest_sha256": RUNTIME_MANIFEST_SHA256,
        "python_executable_sha256": RUNTIME_SOURCE_PYTHON_EXE_SHA256,
        "python_pth_sha256": RUNTIME_LOCKED_PTH_SHA256,
        "runtime_probe_sha256": RUNTIME_PROBE_SHA256,
        "runtime_runner_sha256": RUNTIME_RUNNER_SHA256,
        "launch_contract_fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
        "controller": {
            "sid": "S-1-5-18",
            "name": "NT AUTHORITY\\SYSTEM",
            "is_system": True,
            "is_administrator": True,
            "integrity_rid": 0x4000,
            "key_is_ephemeral": True,
            "key_name_empty": True,
            "key_unique_name_empty": True,
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
            "input_write_blocked": True,
            "runtime_write_blocked": True,
            "control_write_blocked": True,
            "output_writable": True,
            "ipv4_default_route_present": False,
            "ipv4_external_tcp_reachable": False,
            "ipv6_default_route_present": False,
            "ipv6_external_tcp_reachable": False,
        },
        "runtime": {
            "result_ok": True,
            "probe_id": "skynetvs-v1b4-runtime-probe-v1",
            "implementation": "CPython",
            "version": [3, 13, 15],
            "architecture_bits": 64,
            "machine": "AMD64",
            "runtime_root_write_blocked": True,
            "environment_clean": True,
            "pip_absent": True,
            "ensurepip_absent": True,
            "site_absent": True,
            "sys_path_exact": True,
        },
        "shutdown": {"scheduled": True, "delay_seconds": 8},
        "completed_at_utc": "2026-08-12T00:00:05.000000Z",
        "overall_ok": True,
        "execution_authorized": False,
    }
    if authorize_payload["authorization_nonce"] != _AUTH_NONCE:
        raise AssertionError("sample authorization nonce drift")
    return _canonical(payload)


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
    second = build_developer_task_execution_runtime_attestation_payload()
    policy_text = bundle.policy.exact_bytes().decode("utf-8")
    bootstrap_text = bundle.bootstrap.exact_bytes().decode("utf-8")
    native_text = bundle.native_helper.exact_bytes().decode("utf-8")
    controller_text = bundle.controller.exact_bytes().decode("utf-8")
    wsb_text = bundle.wsb_template.exact_bytes().decode("utf-8")

    check(
        "V1B4C1 PINNED ATTESTATION POLICY SELF CHECKS",
        {
            "ok": TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1.ok,
            "fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
            "expected_files": len(TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1.expected_runtime_files),
            "runtime_bundle": RUNTIME_BUNDLE_FINGERPRINT,
            "execution_authorized": TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1.to_dict()["execution_authorized"],
        },
        {
            "ok": True,
            "fingerprint": _EXPECTED_POLICY_FINGERPRINT,
            "expected_files": 37,
            "runtime_bundle": RUNTIME_BUNDLE_FINGERPRINT,
            "execution_authorized": False,
        },
    )

    check(
        "V1B4C1 HISTORICAL V1B3 SIGNED BOUNDARY IS UNCHANGED",
        {
            "ok": WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.ok,
            "fingerprint": WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.fingerprint,
        },
        {"ok": True, "fingerprint": SIGNED_BOUNDARY_FINGERPRINT},
    )

    check(
        "V1B4C1 PAYLOAD BUILDER ACCEPTS NO INPUTS",
        list(inspect.signature(build_developer_task_execution_runtime_attestation_payload).parameters),
        [],
    )

    check(
        "V1B4C1 PAYLOAD BUNDLE IS DETERMINISTIC AND FAIL CLOSED",
        {
            "ok": bundle.ok,
            "metadata": bundle.to_dict() == second.to_dict(),
            "exact_bytes": all(bundle.exact_bytes(name) == second.exact_bytes(name) for name in [item.file_name for item in bundle.files]),
            "sandbox_launched": bundle.sandbox_launched,
            "interpreter_executed": bundle.interpreter_executed,
            "execution_authorized": bundle.execution_authorized,
        },
        {
            "ok": True,
            "metadata": True,
            "exact_bytes": True,
            "sandbox_launched": False,
            "interpreter_executed": False,
            "execution_authorized": False,
        },
    )

    check(
        "V1B4C1 PAYLOAD HASHES AND FINGERPRINT ARE LOCKED",
        {
            "policy": RUNTIME_ATTESTATION_POLICY_BYTES_SHA256,
            "bootstrap": RUNTIME_ATTESTATION_BOOTSTRAP_SHA256,
            "native": RUNTIME_ATTESTATION_NATIVE_HELPER_SHA256,
            "controller": RUNTIME_ATTESTATION_CONTROLLER_SHA256,
            "wsb": RUNTIME_ATTESTATION_WSB_TEMPLATE_SHA256,
            "payload": RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
        },
        {
            "policy": _EXPECTED_POLICY_FINGERPRINT,
            "bootstrap": _EXPECTED_BOOTSTRAP_SHA256,
            "native": _EXPECTED_NATIVE_SHA256,
            "controller": _EXPECTED_CONTROLLER_SHA256,
            "wsb": _EXPECTED_WSB_TEMPLATE_SHA256,
            "payload": _EXPECTED_PAYLOAD_FINGERPRINT,
        },
    )

    check(
        "V1B4C1 PAYLOAD HASHES MATCH EXACT BYTES",
        {item.file_name: hashlib.sha256(item.exact_bytes()).hexdigest() == item.sha256 for item in bundle.files},
        {item.file_name: True for item in bundle.files},
    )

    check(
        "V1B4C1 TEXT PAYLOADS ARE CANONICAL UTF8 LF",
        {
            item.file_name: {
                "bom": item.exact_bytes().startswith(b"\xef\xbb\xbf"),
                "cr": b"\r" in item.exact_bytes(),
                "final_lf": item.exact_bytes().endswith(b"\n"),
            }
            for item in (bundle.bootstrap, bundle.native_helper, bundle.controller, bundle.wsb_template)
        },
        {
            item.file_name: {"bom": False, "cr": False, "final_lf": True}
            for item in (bundle.bootstrap, bundle.native_helper, bundle.controller, bundle.wsb_template)
        },
    )

    serialized_bundle = bundle.to_dict()
    serialized_keys = {
        key
        for item in serialized_bundle["files"]
        for key in item
    }
    check(
        "V1B4C1 SERIALIZATION HIDES EXACT PAYLOAD BYTES",
        {
            "bytes_field": "_bytes" in serialized_keys,
            "native_source_in_repr": "CreateProcessAsUserW" in repr(bundle),
            "controller_source_in_repr": "Set-StrictMode" in repr(bundle),
        },
        {"bytes_field": False, "native_source_in_repr": False, "controller_source_in_repr": False},
    )

    immutable = False
    try:
        bundle.bundle_id = "mutated"  # type: ignore[misc]
    except FrozenInstanceError:
        immutable = True
    check("V1B4C1 PAYLOAD BUNDLE IS IMMUTABLE", immutable, True)

    request = _sample_request(bundle)
    check(
        "V1B4C1 REQUEST IS CANONICAL AND BINDS THE COMPLETE RUNTIME IDENTITY",
        {
            "parsed": parse_runtime_attestation_request(request.canonical_bytes).sha256 == request.sha256,
            "policy": request.field("runtime_attestation_policy_fingerprint"),
            "source": request.field("runtime_source_fingerprint"),
            "tree": request.field("runtime_tree_manifest_sha256"),
            "bundle": request.field("runtime_bundle_fingerprint"),
            "python": request.field("python_executable_sha256"),
            "pth": request.field("python_pth_sha256"),
            "probe": request.field("runtime_probe_sha256"),
            "runner": request.field("runtime_runner_sha256"),
            "launch": request.field("launch_contract_fingerprint"),
            "execution_authorized": request.field("execution_authorized"),
        },
        {
            "parsed": True,
            "policy": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
            "source": RUNTIME_SOURCE_FINGERPRINT,
            "tree": RUNTIME_TREE_MANIFEST_SHA256,
            "bundle": RUNTIME_BUNDLE_FINGERPRINT,
            "python": RUNTIME_SOURCE_PYTHON_EXE_SHA256,
            "pth": RUNTIME_LOCKED_PTH_SHA256,
            "probe": RUNTIME_PROBE_SHA256,
            "runner": RUNTIME_RUNNER_SHA256,
            "launch": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
            "execution_authorized": False,
        },
    )

    check(
        "V1B4C1 REQUEST IDENTIFIERS ARE STRICT",
        {
            "bad_request": _error_code(lambda: build_runtime_attestation_request(
                request_id="A" * 32,
                host_nonce=_HOST_NONCE,
                created_at_epoch_seconds=1.0,
                policy_sha256=_HASH_A,
                bootstrap_sha256=_HASH_B,
                controller_sha256=_HASH_C,
                native_helper_sha256=_HASH_D,
                wsb_sha256=_HASH_E,
            )),
            "bad_nonce": _error_code(lambda: build_runtime_attestation_request(
                request_id=_REQUEST_ID,
                host_nonce="x",
                created_at_epoch_seconds=1.0,
                policy_sha256=_HASH_A,
                bootstrap_sha256=_HASH_B,
                controller_sha256=_HASH_C,
                native_helper_sha256=_HASH_D,
                wsb_sha256=_HASH_E,
            )),
        },
        {"bad_request": "DeveloperTaskRuntimeAttestationPayloadError", "bad_nonce": "DeveloperTaskRuntimeAttestationPayloadError"},
    )

    ready = _sample_ready(request)
    check(
        "V1B4C1 READY CONTRACT BINDS SYSTEM EPHEMERAL KEY AND FOUR MAPPING CONTROLS",
        {
            "kind": ready.kind,
            "system": ready.field("controller_is_system"),
            "integrity": ready.field("controller_integrity_rid"),
            "ephemeral": ready.field("key_is_ephemeral"),
            "input_ro": ready.field("input_write_blocked"),
            "runtime_ro": ready.field("runtime_write_blocked"),
            "control_ro": ready.field("control_write_blocked"),
            "output_rw": ready.field("output_writable"),
            "bootstrap_deleted": ready.field("bootstrap_task_deleted"),
            "execution_authorized": ready.field("execution_authorized"),
        },
        {
            "kind": "ready",
            "system": True,
            "integrity": 0x4000,
            "ephemeral": True,
            "input_ro": True,
            "runtime_ro": True,
            "control_ro": True,
            "output_rw": True,
            "bootstrap_deleted": True,
            "execution_authorized": False,
        },
    )

    authorize = build_runtime_attestation_authorize(
        request=request,
        ready=ready,
        authorization_nonce=_AUTH_NONCE,
        authorization_deadline_epoch=1786500100,
    )
    check(
        "V1B4C1 AUTHORIZATION BINDS READY AND ALLOWS ONLY THE BENIGN RUNTIME PROBE",
        {
            "request": authorize.field("request_sha256") == request.sha256,
            "ready": authorize.field("ready_sha256") == ready.sha256,
            "runtime": authorize.field("runtime_bundle_fingerprint"),
            "launch": authorize.field("launch_contract_fingerprint"),
            "allow_probe": authorize.field("allow_benign_runtime_probe"),
            "execution_authorized": authorize.field("execution_authorized"),
        },
        {
            "request": True,
            "ready": True,
            "runtime": RUNTIME_BUNDLE_FINGERPRINT,
            "launch": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
            "allow_probe": True,
            "execution_authorized": False,
        },
    )

    runtime_result_bytes = _sample_runtime_result()
    runtime_result = parse_runtime_attestation_result(runtime_result_bytes)
    check(
        "V1B4C1 RUNTIME RESULT CONTRACT ACCEPTS ONLY THE PINNED ISOLATED CPYTHON PROBE",
        {
            "kind": runtime_result.kind,
            "version": runtime_result.field("version_info"),
            "bits": runtime_result.field("architecture_bits"),
            "flags": runtime_result.field("flags"),
            "site": runtime_result.field("site_imported"),
            "env": runtime_result.field("python_environment_keys"),
            "pip": runtime_result.field("pip_available"),
            "ensurepip": runtime_result.field("ensurepip_available"),
            "root_write_blocked": runtime_result.field("runtime_root_write_blocked"),
            "sys_path": runtime_result.field("sys_path"),
            "execution_authorized": runtime_result.field("execution_authorized"),
        },
        {
            "kind": "runtime_result",
            "version": [3, 13, 15],
            "bits": 64,
            "flags": {
                "dont_write_bytecode": 1,
                "ignore_environment": 1,
                "isolated": 1,
                "no_user_site": 1,
                "safe_path": True,
                "utf8_mode": 1,
            },
            "site": False,
            "env": [],
            "pip": False,
            "ensurepip": False,
            "root_write_blocked": True,
            "sys_path": [r"C:\SkynetVSRuntime\python313.zip", r"C:\SkynetVSRuntime"],
            "execution_authorized": False,
        },
    )

    result_base = json.loads(runtime_result_bytes[:-1].decode("utf-8"))
    negative_result_cases: dict[str, str] = {}
    for name, mutation in (
        ("environment", lambda p: p.__setitem__("python_environment_keys", ["PYTHONPATH"])),
        ("site", lambda p: p.__setitem__("site_imported", True)),
        ("pip", lambda p: p.__setitem__("pip_available", True)),
        ("ensurepip", lambda p: p.__setitem__("ensurepip_available", True)),
        ("root_writable", lambda p: p.__setitem__("runtime_root_write_blocked", False)),
        ("sys_path", lambda p: p.__setitem__("sys_path", [r"C:\evil"])),
        ("version", lambda p: p.__setitem__("version_info", [3, 13, 14])),
        ("authorized", lambda p: p.__setitem__("execution_authorized", True)),
    ):
        changed = json.loads(json.dumps(result_base))
        mutation(changed)
        negative_result_cases[name] = _error_code(lambda changed=changed: parse_runtime_attestation_result(_canonical(changed, final_lf=True)))
    check(
        "V1B4C1 RUNTIME RESULT FAILS CLOSED ON ENV SITE PACKAGE WRITE PATH VERSION OR AUTHORIZATION DRIFT",
        {key: bool(value) for key, value in negative_result_cases.items()},
        {key: True for key in negative_result_cases},
    )

    terminal_bytes = _sample_terminal(request, ready, authorize, runtime_result)
    terminal = parse_runtime_attestation_terminal(terminal_bytes)
    check(
        "V1B4C1 TERMINAL CONTRACT BINDS WORKER CLEANUP NETWORK ISOLATION AND RUNTIME RESULT",
        {
            "kind": terminal.kind,
            "runtime_result": terminal.field("runtime_result_sha256") == runtime_result.sha256,
            "worker": terminal.field("worker"),
            "controls": terminal.field("controls"),
            "runtime": terminal.field("runtime"),
            "execution_authorized": terminal.field("execution_authorized"),
        },
        {
            "kind": "terminal",
            "runtime_result": True,
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
                "input_write_blocked": True,
                "runtime_write_blocked": True,
                "control_write_blocked": True,
                "output_writable": True,
                "ipv4_default_route_present": False,
                "ipv4_external_tcp_reachable": False,
                "ipv6_default_route_present": False,
                "ipv6_external_tcp_reachable": False,
            },
            "runtime": {
                "result_ok": True,
                "probe_id": "skynetvs-v1b4-runtime-probe-v1",
                "implementation": "CPython",
                "version": [3, 13, 15],
                "architecture_bits": 64,
                "machine": "AMD64",
                "runtime_root_write_blocked": True,
                "environment_clean": True,
                "pip_absent": True,
                "ensurepip_absent": True,
                "site_absent": True,
                "sys_path_exact": True,
            },
            "execution_authorized": False,
        },
    )

    check(
        "V1B4C1 SIGNATURE BYTES ARE STRICTLY 64 BYTES",
        {
            "valid": bool(validate_runtime_attestation_signature_bytes(bytes(range(64)))),
            "short": _error_code(lambda: validate_runtime_attestation_signature_bytes(b"x" * 63)),
        },
        {"valid": True, "short": "runtime_attestation_signature_size_invalid"},
    )

    duplicate = request.canonical_bytes[:-1] + b',"execution_authorized":false}'
    reordered_payload = request.to_dict()
    first = reordered_payload.pop("schema_version")
    reordered_payload["schema_version"] = first
    float_payload = request.canonical_bytes.replace(b'"runtime_file_count":37', b'"runtime_file_count":37.0')
    check(
        "V1B4C1 JSON CONTRACT REJECTS DUPLICATES BOM NONCANONICAL ORDER AND FLOATS",
        {
            "duplicate": _error_code(lambda: parse_runtime_attestation_request(duplicate)),
            "bom": _error_code(lambda: parse_runtime_attestation_request(b"\xef\xbb\xbf" + request.canonical_bytes)),
            "reorder": _error_code(lambda: parse_runtime_attestation_request(_canonical(reordered_payload))),
            "float": _error_code(lambda: parse_runtime_attestation_request(float_payload)),
        },
        {
            "duplicate": "runtime_attestation_json_duplicate_field",
            "bom": "runtime_attestation_json_bom_forbidden",
            "reorder": "runtime_attestation_fields_invalid",
            "float": "runtime_attestation_json_number_invalid",
        },
    )

    check(
        "V1B4C1 POLICY BINDS FOUR EXPLICIT SANDBOX MAPPINGS",
        TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1.to_dict()["mappings"],
        {
            "input": {"guest_root": RUNTIME_ATTESTATION_INPUT_ROOT, "mode": "read_only"},
            "runtime": {"guest_root": RUNTIME_ATTESTATION_RUNTIME_ROOT, "mode": "read_only"},
            "control": {"guest_root": RUNTIME_ATTESTATION_CONTROL_ROOT, "mode": "read_only"},
            "output": {"guest_root": RUNTIME_ATTESTATION_OUTPUT_ROOT, "mode": "writable_untrusted"},
        },
    )

    rendered_wsb = build_runtime_attestation_wsb_config(
        input_host_path=r"C:\Temp\Input&One",
        runtime_host_path=r"C:\Temp\Runtime",
        control_host_path=r"C:\Temp\Control",
        output_host_path=r"C:\Temp\Output",
    ).decode("utf-8")
    check(
        "V1B4C1 WSB RENDERER USES FOUR MAPPINGS EXACT SECURITY CONTROLS AND XML ESCAPING",
        {
            "mapped_folders": rendered_wsb.count("<MappedFolder>"),
            "read_only_true": rendered_wsb.count("<ReadOnly>true</ReadOnly>"),
            "read_only_false": rendered_wsb.count("<ReadOnly>false</ReadOnly>"),
            "network": "<Networking>Disable</Networking>" in rendered_wsb,
            "vgpu": "<VGpu>Disable</VGpu>" in rendered_wsb,
            "protected": "<ProtectedClient>Enable</ProtectedClient>" in rendered_wsb,
            "escaped": "Input&amp;One" in rendered_wsb and "Input&One" not in rendered_wsb,
            "bootstrap": r'C:\SkynetVSInput\bootstrap.ps1' in rendered_wsb,
        },
        {
            "mapped_folders": 4,
            "read_only_true": 3,
            "read_only_false": 1,
            "network": True,
            "vgpu": True,
            "protected": True,
            "escaped": True,
            "bootstrap": True,
        },
    )

    check(
        "V1B4C1 WSB HOST PATH VALIDATION FAILS CLOSED",
        {
            "relative": _error_code(lambda: build_runtime_attestation_wsb_config(
                input_host_path="relative",
                runtime_host_path=r"C:\Runtime",
                control_host_path=r"C:\Control",
                output_host_path=r"C:\Output",
            )),
            "drive_root": _error_code(lambda: build_runtime_attestation_wsb_config(
                input_host_path="C:\\",
                runtime_host_path=r"C:\Runtime",
                control_host_path=r"C:\Control",
                output_host_path=r"C:\Output",
            )),
        },
        {"relative": "DeveloperTaskRuntimeAttestationPayloadError", "drive_root": "DeveloperTaskRuntimeAttestationPayloadError"},
    )

    check(
        "V1B4C1 BOOTSTRAP CREATES ONLY THE FIXED ONE TIME SYSTEM CONTROLLER",
        {
            "wdag": "WDAGUtilityAccount" in bootstrap_text,
            "system": '$definition.Principal.UserId = "SYSTEM"' in bootstrap_text,
            "highest": "$definition.Principal.RunLevel = 1" in bootstrap_text,
            "controller": r'C:\SkynetVSInput\controller.ps1' in bootstrap_text,
            "fixed_powershell": r'System32\WindowsPowerShell\v1.0\powershell.exe' in bootstrap_text,
            "task_prefix": "SkynetVS-V1B4C-" in bootstrap_text,
            "execution_authorized_false": "execution_authorized = $false" in bootstrap_text,
        },
        {
            "wdag": True,
            "system": True,
            "highest": True,
            "controller": True,
            "fixed_powershell": True,
            "task_prefix": True,
            "execution_authorized_false": True,
        },
    )

    check(
        "V1B4C1 ECDSA SIGNING KEY USES A TRUE NULL CNG NAME THROUGH THE NATIVE HELPER",
        {
            "helper": "CreateEphemeralEcdsaP256SigningKey" in native_text,
            "null_string": "(string)null" in native_text,
            "no_export": "creation.ExportPolicy = CngExportPolicies.None;" in native_text,
            "signing_only": "creation.KeyUsage = CngKeyUsages.Signing;" in native_text,
            "controller_uses_helper": "$cngKey = [V1B4CNative]::CreateEphemeralEcdsaP256SigningKey()" in controller_text,
            "powershell_null_overload_absent": "[string]$null" not in controller_text,
            "direct_cng_create_absent": "[System.Security.Cryptography.CngKey]::Create" not in controller_text,
        },
        {
            "helper": True,
            "null_string": True,
            "no_export": True,
            "signing_only": True,
            "controller_uses_helper": True,
            "powershell_null_overload_absent": True,
            "direct_cng_create_absent": True,
        },
    )

    launch_body = native_text.split("public static WorkerLaunchState LaunchFixedRuntimeProbeSuspendedInJob", 1)[1].split("public static uint ResumeRuntimeWorker", 1)[0]
    check(
        "V1B4C1 NATIVE HELPER HAS A FIXED CREATEPROCESSASUSER RUNTIME LAUNCH SHAPE",
        {
            "fixed_root": r'const string runtimeRoot = @"C:\SkynetVSRuntime";' in native_text,
            "fixed_result": r'const string resultRoot = @"C:\ProgramData\SkynetVS\V1B4C\worker-result";' in native_text,
            "python": 'Path.Combine(runtimeRoot, "python.exe")' in native_text,
            "runner": 'Path.Combine(runtimeRoot, "skynetvs_runtime_runner.py")' in native_text,
            "flags": '" -I -S -B -E -s -P -X utf8 "' in native_text,
            "explicit_application": "runtimeExecutablePath," in launch_body,
            "inherit_handles_false": re.search(r"IntPtr.Zero,\s*IntPtr.Zero,\s*false,\s*creationFlags", launch_body, re.S) is not None,
            "create_suspended": "CREATE_SUSPENDED" in launch_body,
            "assign_job": launch_body.find("AssignProcessToJobObject") < launch_body.find("AssignedBeforeResume = true"),
            "resume_absent": "ResumeThread" not in launch_body,
        },
        {
            "fixed_root": True,
            "fixed_result": True,
            "python": True,
            "runner": True,
            "flags": True,
            "explicit_application": True,
            "inherit_handles_false": True,
            "create_suspended": True,
            "assign_job": True,
            "resume_absent": True,
        },
    )

    check(
        "V1B4C1 NATIVE HELPER SANITIZES THE WORKER ENVIRONMENT WITHOUT CALLER INPUT",
        {
            "create_environment_false": "CreateEnvironmentBlock(out originalEnvironment, token, false)" in native_text,
            "python": 'upper.StartsWith("PYTHON", StringComparison.Ordinal)' in native_text,
            "pip": 'upper.StartsWith("PIP_", StringComparison.Ordinal)' in native_text,
            "launcher": 'upper.StartsWith("PYLAUNCHER_", StringComparison.Ordinal)' in native_text,
            "venv": 'String.Equals(upper, "VIRTUAL_ENV", StringComparison.Ordinal)' in native_text,
            "zero": "ZeroAndFreeEnvironmentBlock" in native_text,
            "no_setenv": "SetEnvironmentVariable" not in native_text,
        },
        {
            "create_environment_false": True,
            "python": True,
            "pip": True,
            "launcher": True,
            "venv": True,
            "zero": True,
            "no_setenv": True,
        },
    )

    check(
        "V1B4C1 NATIVE HELPER PRESERVES STANDARD USER JOB AND SID CLEANUP CONTROLS",
        {
            "fresh_account": "CreateFreshStandardUserAndLogon" in native_text,
            "medium": "WORKER_INTEGRITY_RID = 0x2000" in native_text,
            "nonadmin": "Worker token is administrative." in native_text,
            "kill_on_close": "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in native_text,
            "no_breakaway": "CREATE_BREAKAWAY_FROM_JOB" not in native_text and "JOB_OBJECT_LIMIT_BREAKAWAY_OK" not in native_text,
            "sid_sweep": "WaitForWorkerSidQuiescence" in native_text,
            "exact_delete": "DeleteLocalUserExact" in native_text,
        },
        {
            "fresh_account": True,
            "medium": True,
            "nonadmin": True,
            "kill_on_close": True,
            "no_breakaway": True,
            "sid_sweep": True,
            "exact_delete": True,
        },
    )

    check(
        "V1B4C1 NATIVE HELPER HAS NO ALTERNATE EXECUTION SURFACE",
        {
            "shell_execute": "ShellExecute" in native_text,
            "create_process_with_logon": "CreateProcessWithLogon" in native_text,
            "process_start": "Process.Start" in native_text,
            "cmd": "cmd.exe" in native_text.lower(),
            "powershell": "powershell.exe" in native_text.lower(),
            "old_worker_launch": "LaunchFixedWorkerSuspendedInJob" in native_text or "BuildFixedWorkerCommandLine" in native_text,
        },
        {
            "shell_execute": False,
            "create_process_with_logon": False,
            "process_start": False,
            "cmd": False,
            "powershell": False,
            "old_worker_launch": False,
        },
    )

    check(
        "V1B4C1 CONTROLLER VERIFIES THE EXACT 37 FILE RUNTIME TREE BEFORE READY",
        {
            "expected_rows": controller_text.count('[ordered]@{ path = "'),
            "hashes": "Get-FileSha256 -Path $path" in controller_text,
            "sizes": "Runtime file size mismatch" in controller_text,
            "reparse": "Runtime tree contains a reparse point" in controller_text,
            "total": "Runtime total byte count mismatch" in controller_text,
            "identity_before_ready": controller_text.find("$runtimeIdentityVerified = Assert-RuntimeTree") < controller_text.find("Write-Utf8Atomic -Path $readyPath"),
        },
        {
            "expected_rows": 37,
            "hashes": True,
            "sizes": True,
            "reparse": True,
            "total": True,
            "identity_before_ready": True,
        },
    )

    check(
        "V1B4C1 CONTROLLER REQUIRES AUTHORIZATION DATA PLUS VERIFIED SHA256 COMMIT",
        {
            "commit": 'authorize.sha256' in controller_text,
            "strict_size": "$commitBytes.Length -ne 64" in controller_text,
            "lower_hex": '^[0-9a-f]{64}$' in controller_text,
            "data_hash": "Get-BytesSha256 -Bytes $candidateBytes" in controller_text,
            "match": "$candidateSha256 -cne $commitText" in controller_text,
            "parse_after_hash": controller_text.find("$candidateSha256 -cne $commitText") < controller_text.find("$authorize = $authorizeText | ConvertFrom-Json"),
        },
        {
            "commit": True,
            "strict_size": True,
            "lower_hex": True,
            "data_hash": True,
            "match": True,
            "parse_after_hash": True,
        },
    )

    check(
        "V1B4C1 CONTROLLER CLOSES JOB SWEEPS SID AND DELETES ACCOUNT BEFORE TERMINAL SIGNING",
        {
            "close_job": "$jobClosed = $true" in controller_text,
            "sweep": "WaitForWorkerSidQuiescence" in controller_text,
            "delete": "DeleteLocalUserExact" in controller_text,
            "close_before_sign": controller_text.find("$jobClosed = $true") < controller_text.find("$terminalPayload = [ordered]@{"),
            "sweep_before_sign": controller_text.find("$workerSidProcessSetEmpty =") < controller_text.find("$terminalPayload = [ordered]@{"),
            "delete_before_sign": controller_text.find("$workerAccountDeleted = $true") < controller_text.find("$terminalPayload = [ordered]@{"),
        },
        {
            "close_job": True,
            "sweep": True,
            "delete": True,
            "close_before_sign": True,
            "sweep_before_sign": True,
            "delete_before_sign": True,
        },
    )

    check(
        "V1B4C1 CONTROLLER BINDS BOTH NETWORK FAMILIES AND SIGNS THE TERMINAL TRANSCRIPT",
        {
            "ipv4_route": "Test-DefaultRoute -Family IPv4" in controller_text,
            "ipv6_route": "Test-DefaultRoute -Family IPv6" in controller_text,
            "ipv4_tcp": 'AddressFamily]::InterNetwork)' in controller_text,
            "ipv6_tcp": 'AddressFamily]::InterNetworkV6)' in controller_text,
            "ecdsa": "ECDsaP256" in native_text and "CreateEphemeralEcdsaP256SigningKey" in controller_text,
            "sign_hash": "$ecdsa.SignHash($terminalDigest)" in controller_text,
            "shutdown": "$shutdownScheduled = Schedule-Shutdown" in controller_text,
        },
        {
            "ipv4_route": True,
            "ipv6_route": True,
            "ipv4_tcp": True,
            "ipv6_tcp": True,
            "ecdsa": True,
            "sign_hash": True,
            "shutdown": True,
        },
    )

    combined_source = "\n".join((policy_text, bootstrap_text, controller_text))
    check(
        "V1B4C1 CONTRACT AND PAYLOAD HAVE NO PATCH WORKSPACE MODULE PIPELINE OR CALLER EXECUTION INPUT",
        {
            "patch": re.search(r"\bpatch\b", combined_source, re.I) is not None,
            "workspace": re.search(r"\bworkspace\b", combined_source, re.I) is not None,
            "python_module": "python_module" in combined_source,
            "pipeline": re.search(r"\bpipeline\b", combined_source, re.I) is not None,
            "caller_arguments": TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1.to_dict()["prohibitions"]["caller_arguments_allowed"],
            "caller_environment": TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1.to_dict()["prohibitions"]["caller_environment_allowed"],
            "execution_authorized_true": "execution_authorized = $true" in combined_source or '"execution_authorized":true' in combined_source,
        },
        {
            "patch": False,
            "workspace": False,
            "python_module": False,
            "pipeline": False,
            "caller_arguments": False,
            "caller_environment": False,
            "execution_authorized_true": False,
        },
    )

    attestation_source = inspect.getsource(build_developer_task_execution_runtime_attestation_payload)
    check(
        "V1B4C1 PRODUCTION PAYLOAD BUILDER NEVER LAUNCHES SANDBOX PYTHON OR A SUBPROCESS",
        {
            "subprocess": "subprocess" in attestation_source,
            "popen": "Popen" in attestation_source,
            "windows_sandbox": "WindowsSandbox" in attestation_source,
            "python_exe": "python.exe" in attestation_source,
            "shell": "shell=" in attestation_source,
        },
        {"subprocess": False, "popen": False, "windows_sandbox": False, "python_exe": False, "shell": False},
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
