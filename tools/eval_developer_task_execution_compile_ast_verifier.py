from __future__ import annotations

import base64
import copy
import hashlib
import inspect
import json

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from modules.developer.developer_task_execution_compile_ast_contract import (
    parse_compile_ast_authorize,
    parse_compile_ast_ready,
    parse_compile_ast_request,
    parse_compile_ast_result,
    parse_compile_ast_source_manifest,
    parse_compile_ast_terminal,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    build_developer_task_execution_compile_ast_runner_bundle,
)
from modules.developer.developer_task_execution_compile_ast_verifier import (
    DeveloperTaskExecutionCompileAstTranscriptPinReport,
    pin_developer_task_execution_compile_ast_transcript,
    verify_developer_task_execution_compile_ast_transcript,
)
from modules.developer.developer_task_execution_compile_ast_verifier_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_V1,
    developer_task_execution_compile_ast_verifier_policy_fingerprint,
    validate_developer_task_execution_compile_ast_verifier_policy,
)
from tools.eval_developer_task_execution_compile_ast_contract import build_valid_payloads


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERIFIER_PATH = PROJECT_ROOT / "modules" / "developer" / "developer_task_execution_compile_ast_verifier.py"
POLICY_PATH = PROJECT_ROOT / "modules" / "developer" / "developer_task_execution_compile_ast_verifier_policy.py"
_REQUEST_ID = "a" * 32
_HOST_NONCE = "b" * 64
_AUTH_NONCE = "c" * 64
_AUTH_OBSERVED_EPOCH = 1786809606.0
_SIGNATURE = (1).to_bytes(32, "big") + (1).to_bytes(32, "big")
_GX = int("6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296", 16)
_GY = int("4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5", 16)
_PUBLIC_KEY = b"ECS1" + b"\x20\x00\x00\x00" + _GX.to_bytes(32, "big") + _GY.to_bytes(32, "big")


def _canonical(payload: dict[str, Any], *, final_lf: bool = False) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return raw + (b"\n" if final_lf else b"")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _valid_public_key(blob: bytes = _PUBLIC_KEY) -> tuple[str, str]:
    return base64.b64encode(blob).decode("ascii"), _sha256(blob)


def build_verifier_fixture(
    *,
    check_passed: bool = True,
    boundary_failed: bool = False,
    public_key_blob: bytes = _PUBLIC_KEY,
) -> dict[str, Any]:
    manifest, request, ready, authorize, result, terminal = build_valid_payloads(
        check_passed=check_passed,
        boundary_failed=boundary_failed,
    )
    bundle = build_developer_task_execution_compile_ast_runner_bundle()
    manifest_bytes = _canonical(manifest)
    manifest_doc = parse_compile_ast_source_manifest(manifest_bytes)
    request = copy.deepcopy(request)
    request["policy_sha256"] = bundle.contract_policy.sha256
    request["runner_sha256"] = bundle.runner.sha256
    request["payload_sha256"] = bundle.payload_manifest.sha256
    request["source_manifest_sha256"] = manifest_doc.sha256
    request_bytes = _canonical(request)
    request_doc = parse_compile_ast_request(request_bytes)

    public_key_b64, public_key_sha256 = _valid_public_key(public_key_blob)
    ready = copy.deepcopy(ready)
    for field_name in (
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
    ):
        ready[field_name] = request[field_name]
    ready["request_sha256"] = request_doc.sha256
    ready["source_manifest_sha256"] = manifest_doc.sha256
    ready["public_key_blob_base64"] = public_key_b64
    ready["public_key_sha256"] = public_key_sha256
    ready_bytes = _canonical(ready)
    ready_doc = parse_compile_ast_ready(ready_bytes)

    authorize = copy.deepcopy(authorize)
    authorize["request_sha256"] = request_doc.sha256
    authorize["ready_sha256"] = ready_doc.sha256
    authorize["public_key_sha256"] = public_key_sha256
    authorize["runtime_bundle_fingerprint"] = request["runtime_bundle_fingerprint"]
    authorize["runtime_lease_fingerprint"] = request["runtime_lease_fingerprint"]
    authorize["plan_fingerprint"] = request["plan_fingerprint"]
    authorize["source_manifest_sha256"] = manifest_doc.sha256
    authorize_bytes = _canonical(authorize)
    authorize_doc = parse_compile_ast_authorize(authorize_bytes)

    result_bytes: bytes | None = None
    result_doc = None
    if not boundary_failed:
        result = copy.deepcopy(result)
        result["source_manifest_sha256"] = manifest_doc.sha256
        result_bytes = _canonical(result, final_lf=True)
        result_doc = parse_compile_ast_result(result_bytes)

    terminal = copy.deepcopy(terminal)
    terminal["request_sha256"] = request_doc.sha256
    terminal["ready_sha256"] = ready_doc.sha256
    terminal["authorize_sha256"] = authorize_doc.sha256
    terminal["source_manifest_sha256"] = manifest_doc.sha256
    terminal["result_sha256"] = None if result_doc is None else result_doc.sha256
    terminal["public_key_sha256"] = public_key_sha256
    for field_name in (
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
    ):
        terminal[field_name] = request[field_name]
    terminal["check"]["result_sha256"] = None if result_doc is None else result_doc.sha256
    terminal_bytes = _canonical(terminal)
    parse_compile_ast_terminal(terminal_bytes)
    return {
        "manifest": manifest,
        "request": request,
        "ready": ready,
        "authorize": authorize,
        "result": result if not boundary_failed else None,
        "terminal": terminal,
        "source_manifest_bytes": manifest_bytes,
        "request_bytes": request_bytes,
        "ready_bytes": ready_bytes,
        "authorize_bytes": authorize_bytes,
        "result_bytes": result_bytes,
        "terminal_bytes": terminal_bytes,
        "signature": _SIGNATURE,
        "public_key": public_key_blob,
    }


def pin_fixture(fixture: dict[str, Any], **overrides: Any) -> Any:
    kwargs = {
        "expected_request_id": _REQUEST_ID,
        "expected_host_nonce": _HOST_NONCE,
        "expected_authorization_nonce": _AUTH_NONCE,
        "expected_source_manifest_sha256": _sha256(fixture["source_manifest_bytes"]),
        "expected_request_sha256": _sha256(fixture["request_bytes"]),
        "expected_plan_fingerprint": fixture["request"]["plan_fingerprint"],
        "expected_runtime_lease_fingerprint": fixture["request"]["runtime_lease_fingerprint"],
        "authorization_observed_epoch": _AUTH_OBSERVED_EPOCH,
        "source_manifest_bytes": fixture["source_manifest_bytes"],
        "request_bytes": fixture["request_bytes"],
        "ready_bytes": fixture["ready_bytes"],
        "authorize_bytes": fixture["authorize_bytes"],
    }
    kwargs.update(overrides)
    return pin_developer_task_execution_compile_ast_transcript(**kwargs)


def verify_fixture(
    fixture: dict[str, Any],
    pin_report: Any,
    *,
    verifier: Callable[[bytes, bytes, bytes], bool] | None = lambda *_: True,
    **overrides: Any,
) -> Any:
    kwargs = {
        "source_manifest_bytes": fixture["source_manifest_bytes"],
        "request_bytes": fixture["request_bytes"],
        "ready_bytes": fixture["ready_bytes"],
        "authorize_bytes": fixture["authorize_bytes"],
        "result_bytes": fixture["result_bytes"],
        "terminal_payload_bytes": fixture["terminal_bytes"],
        "terminal_signature_bytes": fixture["signature"],
        "signature_verifier": verifier,
    }
    kwargs.update(overrides)
    return verify_developer_task_execution_compile_ast_transcript(pin_report, **kwargs)


def _mutate(data: bytes, path: tuple[str, ...], value: Any, *, final_lf: bool = False) -> bytes:
    payload = json.loads(data)
    target: Any = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return _canonical(payload, final_lf=final_lf)


def _case(name: str, actual: Any, expected: Any) -> bool:
    ok = actual == expected
    print(f"\n=== {name} ===")
    print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2))
    print(f"[{'OK' if ok else 'FAIL'}] {name}")
    return ok


def main() -> int:
    results: list[bool] = []
    add = lambda name, actual, expected: results.append(_case(name, actual, expected))

    policy_errors = list(validate_developer_task_execution_compile_ast_verifier_policy())
    add(
        "V1C2B PINNED VERIFIER POLICY SELF CHECKS",
        {
            "errors": policy_errors,
            "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_V1.policy_id,
            "fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_V1.fingerprint,
            "recomputed": developer_task_execution_compile_ast_verifier_policy_fingerprint(DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_V1),
            "authorized": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_V1.verifier_authorizes_execution,
        },
        {
            "errors": [],
            "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_ID,
            "fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
            "recomputed": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
            "authorized": False,
        },
    )

    pin_signature = inspect.signature(pin_developer_task_execution_compile_ast_transcript)
    verify_signature = inspect.signature(verify_developer_task_execution_compile_ast_transcript)
    add(
        "V1C2B PUBLIC APIS EXPOSE ONLY TYPED TRANSCRIPT EVIDENCE",
        {
            "pin": list(pin_signature.parameters),
            "verify": list(verify_signature.parameters),
            "forbidden_pin": any(name in pin_signature.parameters for name in ("executable", "argv", "environment", "runner", "wsb_bytes", "bootstrap_bytes", "controller_bytes")),
        },
        {
            "pin": [
                "expected_request_id", "expected_host_nonce", "expected_authorization_nonce",
                "expected_source_manifest_sha256", "expected_request_sha256", "expected_plan_fingerprint",
                "expected_runtime_lease_fingerprint", "authorization_observed_epoch", "source_manifest_bytes",
                "request_bytes", "ready_bytes", "authorize_bytes",
            ],
            "verify": [
                "pin_report", "source_manifest_bytes", "request_bytes", "ready_bytes", "authorize_bytes",
                "result_bytes", "terminal_payload_bytes", "terminal_signature_bytes", "signature_verifier",
            ],
            "forbidden_pin": False,
        },
    )

    passing = build_verifier_fixture()
    passing_pin = pin_fixture(passing)
    add("V1C2B VALID PASS TRANSCRIPT PINS", {"ok": passing_pin.ok, "issues": list(passing_pin.issue_codes)}, {"ok": True, "issues": []})
    passing_report = verify_fixture(passing, passing_pin)
    add(
        "V1C2B VALID PASS TRANSCRIPT VERIFIES",
        {
            "ok": passing_report.ok,
            "status": passing_report.terminal_status,
            "boundary_ok": passing_report.boundary_ok,
            "check_passed": passing_report.check_passed,
            "signature": passing_report.signature_valid,
        },
        {"ok": True, "status": "compile_ast_attested_passed", "boundary_ok": True, "check_passed": True, "signature": True},
    )

    syntax = build_verifier_fixture(check_passed=False)
    syntax_pin = pin_fixture(syntax)
    syntax_report = verify_fixture(syntax, syntax_pin)
    add(
        "V1C2B AUTHENTIC SYNTAX FAILURE IS VERIFIED EVIDENCE",
        {"ok": syntax_report.ok, "status": syntax_report.terminal_status, "boundary_ok": syntax_report.boundary_ok, "check_passed": syntax_report.check_passed},
        {"ok": True, "status": "compile_ast_attested_failed", "boundary_ok": True, "check_passed": False},
    )

    boundary = build_verifier_fixture(boundary_failed=True)
    boundary_pin = pin_fixture(boundary)
    boundary_report = verify_fixture(boundary, boundary_pin)
    add(
        "V1C2B AUTHENTIC BOUNDARY FAILURE WITHOUT RESULT IS VERIFIED EVIDENCE",
        {"ok": boundary_report.ok, "status": boundary_report.terminal_status, "boundary_ok": boundary_report.boundary_ok, "check_passed": boundary_report.check_passed, "result": boundary_report.result_sha256},
        {"ok": True, "status": "compile_ast_boundary_failed", "boundary_ok": False, "check_passed": False, "result": None},
    )

    pin_json = json.dumps(passing_pin.to_dict(), ensure_ascii=False)
    add(
        "V1C2B PIN REPORT IS REDACTED",
        {
            "host_nonce_hidden": _HOST_NONCE not in pin_json and _HOST_NONCE not in repr(passing_pin),
            "auth_nonce_hidden": _AUTH_NONCE not in pin_json and _AUTH_NONCE not in repr(passing_pin),
            "public_key_hidden": base64.b64encode(_PUBLIC_KEY).decode("ascii") not in pin_json and base64.b64encode(_PUBLIC_KEY).decode("ascii") not in repr(passing_pin),
        },
        {"host_nonce_hidden": True, "auth_nonce_hidden": True, "public_key_hidden": True},
    )

    forged = DeveloperTaskExecutionCompileAstTranscriptPinReport(
        status=passing_pin.status,
        expectation=passing_pin.expectation,
        source_manifest=passing_pin.source_manifest,
        request=passing_pin.request,
        ready=passing_pin.ready,
        authorize=passing_pin.authorize,
        issues=(),
    )
    forged_report = verify_fixture(passing, forged)
    add("V1C2B FORGED DATACLASS PIN REPORT IS REJECTED", "compile_ast_verifier_pin_report_failed" in forged_report.issue_codes, True)

    failed_pin = pin_fixture(passing, expected_request_id="0" * 32)
    failed_pin_report = verify_fixture(passing, failed_pin)
    add("V1C2B FAILED PIN REPORT BLOCKS FINAL VERIFICATION", "compile_ast_verifier_pin_report_failed" in failed_pin_report.issue_codes, True)

    mismatch_tests = (
        ("REQUEST ID", {"expected_request_id": "0" * 32}, "compile_ast_verifier_run_identity_mismatch"),
        ("HOST NONCE", {"expected_host_nonce": "0" * 64}, "compile_ast_verifier_run_identity_mismatch"),
        ("AUTH NONCE", {"expected_authorization_nonce": "0" * 64}, "compile_ast_verifier_authorization_identity_mismatch"),
        ("SOURCE MANIFEST", {"expected_source_manifest_sha256": "0" * 64}, "compile_ast_verifier_source_manifest_substitution"),
        ("REQUEST HASH", {"expected_request_sha256": "0" * 64}, "compile_ast_verifier_request_replay_or_substitution"),
        ("PLAN", {"expected_plan_fingerprint": "0" * 64}, "compile_ast_verifier_plan_identity_mismatch"),
        ("RUNTIME LEASE", {"expected_runtime_lease_fingerprint": "0" * 64}, "compile_ast_verifier_runtime_lease_identity_mismatch"),
    )
    for label, kwargs, code in mismatch_tests:
        report = pin_fixture(passing, **kwargs)
        add(f"V1C2B {label} MISMATCH FAILS CLOSED", code in report.issue_codes, True)

    bundle = build_developer_task_execution_compile_ast_runner_bundle()
    for field_name in ("policy_sha256", "runner_sha256", "payload_sha256"):
        mutated = build_verifier_fixture()
        mutated_request = _mutate(mutated["request_bytes"], (field_name,), "0" * 64)
        report = pin_fixture(mutated, request_bytes=mutated_request, expected_request_sha256=_sha256(mutated_request))
        add(f"V1C2B TRUSTED {field_name.upper()} MISMATCH FAILS CLOSED", "compile_ast_verifier_runner_bundle_identity_mismatch" in report.issue_codes, True)

    early_ready = build_verifier_fixture()
    early_ready_bytes = _mutate(early_ready["ready_bytes"], ("created_at_utc",), "2026-08-15T15:59:59Z")
    early_pin = pin_fixture(early_ready, ready_bytes=early_ready_bytes)
    add("V1C2B READY BEFORE REQUEST FAILS CLOSED", "compile_ast_verifier_ready_window_invalid" in early_pin.issue_codes, True)

    add(
        "V1C2B AUTHORIZATION OBSERVED BEFORE READY FAILS CLOSED",
        "compile_ast_verifier_authorization_temporal_inversion" in pin_fixture(passing, authorization_observed_epoch=1786809604.0).issue_codes,
        True,
    )
    add(
        "V1C2B AUTHORIZATION OBSERVED AFTER DEADLINE FAILS CLOSED",
        "compile_ast_verifier_authorization_expired" in pin_fixture(passing, authorization_observed_epoch=1786809691.0).issue_codes,
        True,
    )

    bad_key = build_verifier_fixture(public_key_blob=b"ECS1" + b"\x20\x00\x00\x00" + bytes(range(64)))
    bad_key_pin = pin_fixture(bad_key)
    add("V1C2B OFF CURVE PUBLIC KEY FAILS CLOSED", "boundary_public_key_point_invalid" in bad_key_pin.issue_codes, True)

    substitutions = (
        ("SOURCE MANIFEST", "source_manifest_bytes", _mutate(passing["source_manifest_bytes"], ("snapshot_fingerprint",), "0" * 64), "compile_ast_verifier_pinned_artifact_changed"),
        ("REQUEST", "request_bytes", _mutate(passing["request_bytes"], ("bootstrap_sha256",), "0" * 64), "compile_ast_verifier_pinned_artifact_changed"),
        ("READY", "ready_bytes", _mutate(passing["ready_bytes"], ("controller_name",), "SYSTEM-OTHER"), "compile_ast_verifier_pinned_artifact_changed"),
        ("AUTHORIZE", "authorize_bytes", _mutate(passing["authorize_bytes"], ("authorization_nonce",), "0" * 64), "compile_ast_verifier_pinned_artifact_changed"),
    )
    for label, key, value, code in substitutions:
        report = verify_fixture(passing, passing_pin, **{key: value})
        add(f"V1C2B POST PIN {label} SUBSTITUTION FAILS CLOSED", code in report.issue_codes, True)

    tampered_result = _mutate(passing["result_bytes"], ("files",), [], final_lf=True)
    result_report = verify_fixture(passing, passing_pin, result_bytes=tampered_result)
    add("V1C2B RESULT TAMPER FAILS CLOSED", result_report.ok, False)

    terminal_name_tamper = _mutate(passing["terminal_bytes"], ("controller", "name"), "LOCAL SYSTEM OTHER")
    terminal_name_report = verify_fixture(passing, passing_pin, terminal_payload_bytes=terminal_name_tamper)
    add("V1C2B READY TERMINAL CONTROLLER MISMATCH FAILS CLOSED", any(issue.check == "terminal.controller.name" for issue in terminal_name_report.issues), True)

    missing_result_report = verify_fixture(passing, passing_pin, result_bytes=None)
    add("V1C2B ATTESTED TERMINAL CANNOT OMIT RESULT", "compile_ast_chain_result_missing" in missing_result_report.issue_codes, True)

    boundary_with_result_report = verify_fixture(boundary, boundary_pin, result_bytes=_canonical(build_valid_payloads()[4], final_lf=True))
    add("V1C2B BOUNDARY FAILED TERMINAL CANNOT CLAIM RESULT", boundary_with_result_report.ok, False)

    noncanonical_request_report = verify_fixture(passing, passing_pin, request_bytes=passing["request_bytes"] + b" ")
    add("V1C2B NONCANONICAL POST PIN REQUEST FAILS CLOSED", "compile_ast_json_not_canonical" in noncanonical_request_report.issue_codes, True)

    short_signature_report = verify_fixture(passing, passing_pin, terminal_signature_bytes=b"x" * 63)
    add("V1C2B SHORT SIGNATURE IS REJECTED", "compile_ast_signature_size_invalid" in short_signature_report.issue_codes, True)
    zero_signature_report = verify_fixture(passing, passing_pin, terminal_signature_bytes=b"\x00" * 64)
    add("V1C2B ZERO SIGNATURE IS REJECTED", "compile_ast_signature_invalid" in zero_signature_report.issue_codes, True)
    scalar_signature = b"\x00" * 32 + (1).to_bytes(32, "big")
    scalar_report = verify_fixture(passing, passing_pin, terminal_signature_bytes=scalar_signature)
    add("V1C2B OUT OF RANGE SIGNATURE SCALAR IS REJECTED", "boundary_signature_scalar_invalid" in scalar_report.issue_codes, True)

    invalid_sig_report = verify_fixture(passing, passing_pin, verifier=lambda *_: False)
    add("V1C2B INVALID ECDSA SIGNATURE IS REJECTED", list(invalid_sig_report.issue_codes), ["compile_ast_verifier_signature_invalid"])
    verifier_failure_report = verify_fixture(passing, passing_pin, verifier=lambda *_: (_ for _ in ()).throw(RuntimeError("crypto boom")))
    add("V1C2B SIGNATURE VERIFIER FAILURE IS STRUCTURED", list(verifier_failure_report.issue_codes), ["compile_ast_verifier_signature_verifier_failed"])
    nonbool_report = verify_fixture(passing, passing_pin, verifier=lambda *_: 1)
    add("V1C2B NONBOOLEAN SIGNATURE VERIFIER RESULT IS REJECTED", list(nonbool_report.issue_codes), ["compile_ast_verifier_signature_verifier_result_invalid"])

    early_terminal = _mutate(passing["terminal_bytes"], ("completed_at_utc",), "2026-08-15T16:00:05Z")
    early_terminal_report = verify_fixture(passing, passing_pin, terminal_payload_bytes=early_terminal)
    add("V1C2B TERMINAL BEFORE AUTHORIZATION FAILS CLOSED", "compile_ast_verifier_terminal_timing_invalid" in early_terminal_report.issue_codes, True)
    late_terminal = _mutate(passing["terminal_bytes"], ("completed_at_utc",), "2026-08-15T16:03:30Z")
    late_terminal_report = verify_fixture(passing, passing_pin, terminal_payload_bytes=late_terminal)
    add("V1C2B TERMINAL AFTER BOUNDED WINDOW FAILS CLOSED", "compile_ast_verifier_terminal_window_invalid" in late_terminal_report.issue_codes, True)

    mutated_policy = replace(DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_V1, signature_bytes=63)
    add(
        "V1C2B POLICY MUTATION INVALIDATES FINGERPRINT",
        {
            "changed": developer_task_execution_compile_ast_verifier_policy_fingerprint(mutated_policy) != DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
            "errors": list(validate_developer_task_execution_compile_ast_verifier_policy(mutated_policy)),
        },
        {"changed": True, "errors": ["crypto_invalid", "policy_values_changed", "policy_fingerprint_mismatch"]},
    )

    verifier_source = VERIFIER_PATH.read_text(encoding="utf-8")
    add(
        "V1C2B VERIFIER HAS NO ACTIVE SANDBOX RUNNER NETWORK OR SOURCE PROCESSING SURFACE",
        {
            "pathlib": "pathlib" in verifier_source,
            "open_call": "open(" in verifier_source,
            "subprocess": "subprocess" in verifier_source,
            "WindowsSandbox.exe": "WindowsSandbox.exe" in verifier_source,
            "socket": "socket" in verifier_source,
            "urllib": "urllib" in verifier_source,
            "requests": "requests" in verifier_source,
            "ast.parse": "ast.parse" in verifier_source,
            "compile(": "compile(" in verifier_source,
            "exec(": "exec(" in verifier_source,
            "eval(": "eval(" in verifier_source,
        },
        {
            "pathlib": False, "open_call": False, "subprocess": False, "WindowsSandbox.exe": False,
            "socket": False, "urllib": False, "requests": False, "ast.parse": False,
            "compile(": False, "exec(": False, "eval(": False,
        },
    )
    add(
        "V1C2B WINDOWS CNG IS DEFAULT FINAL CRYPTO PATH",
        "signature_verifier or verify_ecdsa_p256_sha256_cng" in verifier_source,
        True,
    )
    add(
        "V1C2B VERIFIED REPORT NEVER AUTHORIZES CHANGED CODE",
        {
            "changed_code_executed": passing_report.to_dict()["changed_code_executed"],
            "execution_authorized": passing_report.to_dict()["execution_authorized"],
            "reusable_lease_issued": passing_report.to_dict()["reusable_lease_issued"],
        },
        {"changed_code_executed": False, "execution_authorized": False, "reusable_lease_issued": False},
    )

    fail_count = sum(not result for result in results)
    print("\n=== SUMMARY ===")
    print(json.dumps({"case_count": len(results), "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
