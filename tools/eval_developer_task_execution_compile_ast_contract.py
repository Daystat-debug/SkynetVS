from __future__ import annotations

import ast
import base64
import copy
import hashlib
import inspect
import json

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_compile_ast_contract import (
    DeveloperTaskExecutionCompileAstContractError,
    DeveloperTaskExecutionCompileAstDocument,
    build_compile_ast_source_manifest,
    encode_compile_ast_document,
    parse_compile_ast_authorize,
    parse_compile_ast_ready,
    parse_compile_ast_request,
    parse_compile_ast_result,
    parse_compile_ast_source_manifest,
    parse_compile_ast_terminal,
    validate_compile_ast_document_chain,
    validate_compile_ast_signature_bytes,
)
from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_STATUSES,
    canonical_developer_task_execution_compile_ast_contract_policy_json,
    developer_task_execution_compile_ast_contract_policy_fingerprint,
    validate_developer_task_execution_compile_ast_contract_policy,
)
from modules.developer.developer_task_execution_compile_ast_plan import (
    DeveloperTaskExecutionCompileAstPlanReport,
    DeveloperTaskExecutionCompileAstPlanSource,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SNAPSHOT_POLICY_FINGERPRINT,
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


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = PROJECT_ROOT / "modules" / "developer" / "developer_task_execution_compile_ast_contract.py"
POLICY_PATH = PROJECT_ROOT / "modules" / "developer" / "developer_task_execution_compile_ast_contract_policy.py"


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _canonical(payload: dict[str, Any], *, trailing_lf: bool = False) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return data + (b"\n" if trailing_lf else b"")


def _make_plan_report() -> DeveloperTaskExecutionCompileAstPlanReport:
    sources = (
        DeveloperTaskExecutionCompileAstPlanSource(
            path="a.py",
            mode="100644",
            size_bytes=10,
            sha256=_sha("a.py:value=1"),
            encoding="utf-8",
            line_endings="lf",
        ),
        DeveloperTaskExecutionCompileAstPlanSource(
            path="pkg/b.py",
            mode="100644",
            size_bytes=20,
            sha256=_sha("pkg/b.py:value=2"),
            encoding="utf-8",
            line_endings="lf",
        ),
    )
    return DeveloperTaskExecutionCompileAstPlanReport(
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
        snapshot_policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SNAPSHOT_POLICY_FINGERPRINT,
        snapshot_fingerprint=_sha("snapshot"),
        manifest_fingerprint=_sha("manifest"),
        workspace_id="workspace-v1c2a1-eval",
        base_commit="1" * 40,
        patch_sha256=_sha("patch"),
        result_tree="2" * 40,
        changed_files=("a.py", "deleted.py", "notes.txt", "pkg/b.py"),
        selected_python_files=("a.py", "pkg/b.py"),
        deleted_python_files=("deleted.py",),
        changed_non_python_files=("notes.txt",),
        selected_file_count=2,
        selected_total_bytes=30,
        sources=sources,
        source_manifest_sha256=_sha("v1c1b-source-manifest"),
        plan_fingerprint=_sha("plan"),
        snapshot_consumed=True,
    )


def _public_key() -> tuple[str, str]:
    blob = b"ECS1" + b"\x20\x00\x00\x00" + bytes(range(64))
    return base64.b64encode(blob).decode("ascii"), hashlib.sha256(blob).hexdigest()


def build_valid_payloads(
    *,
    check_passed: bool = True,
    boundary_failed: bool = False,
) -> tuple[dict[str, Any], ...]:
    request_id = "a" * 32
    host_nonce = "b" * 64
    auth_nonce = "c" * 64
    manifest_doc = build_compile_ast_source_manifest(
        _make_plan_report(),
        request_id=request_id,
        host_nonce=host_nonce,
    )
    manifest = manifest_doc.to_dict()
    artifacts = {
        "policy_sha256": _sha("policy"),
        "bootstrap_sha256": _sha("bootstrap"),
        "controller_sha256": _sha("controller"),
        "native_helper_sha256": _sha("native-helper"),
        "runner_sha256": _sha("runner"),
        "payload_sha256": _sha("payload"),
        "wsb_sha256": _sha("wsb"),
    }
    runtime_lease_fingerprint = _sha("runtime-lease-instance")
    request = {
        "schema_version": 1,
        "backend_id": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.backend_id,
        "backend_policy_fingerprint": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
        "contract_policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
        "contract_policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        "request_id": request_id,
        "host_nonce": host_nonce,
        "created_at_utc": "2026-08-15T16:00:00Z",
        "ready_timeout_seconds": 120,
        "authorization_timeout_seconds": 90,
        "worker_timeout_seconds": 60,
        "shutdown_grace_seconds": 45,
        **artifacts,
        "runtime_attestation_policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        "runtime_lease_policy_fingerprint": RUNTIME_LEASE_POLICY_FINGERPRINT,
        "runtime_lease_fingerprint": runtime_lease_fingerprint,
        "plan_policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
        "plan_fingerprint": manifest["plan_fingerprint"],
        "source_manifest_sha256": manifest_doc.sha256,
        "selected_file_count": manifest["selected_file_count"],
        "selected_total_bytes": manifest["selected_total_bytes"],
        "trusted_scope": "compile_ast_changed_python_only_v1",
        "execution_authorized": False,
    }
    request_doc = parse_compile_ast_request(_canonical(request))
    public_key_blob, public_key_hash = _public_key()
    ready_checks = {
        "controller_is_system": True,
        "controller_is_administrator": True,
        "controller_integrity_is_system": True,
        "key_is_ephemeral": True,
        "key_name_empty": True,
        "key_unique_name_empty": True,
        "request_identity_verified": True,
        "source_manifest_verified": True,
        "runtime_identity_verified": True,
        "input_write_blocked": True,
        "source_write_blocked": True,
        "runtime_write_blocked": True,
        "control_write_blocked": True,
        "output_writable": True,
    }
    ready = {
        "schema_version": 1,
        "backend_id": request["backend_id"],
        "backend_policy_fingerprint": request["backend_policy_fingerprint"],
        "contract_policy_id": request["contract_policy_id"],
        "contract_policy_fingerprint": request["contract_policy_fingerprint"],
        "operation": request["operation"],
        "request_id": request_id,
        "host_nonce": host_nonce,
        "request_sha256": request_doc.sha256,
        "source_manifest_sha256": manifest_doc.sha256,
        **artifacts,
        "controller_sid": "S-1-5-18",
        "controller_name": "NT AUTHORITY\\SYSTEM",
        "controller_is_system": True,
        "controller_is_administrator": True,
        "controller_integrity_rid": 0x4000,
        "key_is_ephemeral": True,
        "key_name_empty": True,
        "key_unique_name_empty": True,
        "public_key_format": "EccPublicBlob",
        "public_key_blob_base64": public_key_blob,
        "public_key_sha256": public_key_hash,
        "runtime_attestation_policy_fingerprint": request["runtime_attestation_policy_fingerprint"],
        "runtime_bundle_fingerprint": request["runtime_bundle_fingerprint"],
        "runtime_lease_policy_fingerprint": request["runtime_lease_policy_fingerprint"],
        "runtime_lease_fingerprint": runtime_lease_fingerprint,
        "plan_policy_fingerprint": request["plan_policy_fingerprint"],
        "plan_fingerprint": request["plan_fingerprint"],
        "input_write_blocked": True,
        "source_write_blocked": True,
        "runtime_write_blocked": True,
        "control_write_blocked": True,
        "output_writable": True,
        "bootstrap_task_deleted": True,
        "ready_checks": ready_checks,
        "failed_ready_checks": [],
        "created_at_utc": "2026-08-15T16:00:05Z",
        "overall_ok": True,
        "execution_authorized": False,
    }
    ready_doc = parse_compile_ast_ready(_canonical(ready))
    authorize = {
        "schema_version": 1,
        "request_id": request_id,
        "host_nonce": host_nonce,
        "request_sha256": request_doc.sha256,
        "ready_sha256": ready_doc.sha256,
        "public_key_sha256": public_key_hash,
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        "runtime_lease_fingerprint": runtime_lease_fingerprint,
        "plan_fingerprint": request["plan_fingerprint"],
        "source_manifest_sha256": manifest_doc.sha256,
        "authorization_nonce": auth_nonce,
        "authorization_deadline_epoch": 1786809690,
        "allow_compile_ast": True,
        "execution_authorized": False,
    }
    authorize_doc = parse_compile_ast_authorize(_canonical(authorize))

    files: list[dict[str, Any]] = []
    for item in manifest["sources"]:
        file_result = {
            "ordinal": item["ordinal"],
            "guest_file_name": item["guest_file_name"],
            "original_path": item["original_path"],
            "virtual_filename": item["virtual_filename"],
            "git_mode": item["git_mode"],
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
            "decode_ok": True,
            "ast_parse_ok": True,
            "compile_ok": True,
            "error": None,
        }
        files.append(file_result)
    if not check_passed:
        files[1]["ast_parse_ok"] = False
        files[1]["compile_ok"] = False
        files[1]["error"] = {
            "type": "SyntaxError",
            "message": "invalid syntax",
            "line": 1,
            "offset": 5,
            "end_line": 1,
            "end_offset": 6,
        }
    passed_count = sum(1 for item in files if item["compile_ok"])
    result = {
        "schema_version": 1,
        "contract_policy_id": request["contract_policy_id"],
        "contract_policy_fingerprint": request["contract_policy_fingerprint"],
        "operation": request["operation"],
        "request_id": request_id,
        "plan_fingerprint": request["plan_fingerprint"],
        "source_manifest_sha256": manifest_doc.sha256,
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        "implementation": "CPython",
        "version_info": [3, 13, 15],
        "architecture_bits": 64,
        "machine": "AMD64",
        "selected_file_count": len(files),
        "processed_file_count": len(files),
        "passed_file_count": passed_count,
        "failed_file_count": len(files) - passed_count,
        "check_passed": check_passed,
        "files": files,
        "trusted_interpreter_executed": True,
        "changed_source_processed": True,
        "changed_source_ast_parsed": check_passed,
        "changed_source_compiled": check_passed,
        "changed_code_executed": False,
        "imports_executed": False,
        "top_level_executed": False,
        "bytecode_written": False,
        "execution_authorized": False,
    }
    result_doc = None if boundary_failed else parse_compile_ast_result(_canonical(result, trailing_lf=True))

    result_received = not boundary_failed
    processed = 0 if boundary_failed else result["processed_file_count"]
    passed = 0 if boundary_failed else result["passed_file_count"]
    failed = 0 if boundary_failed else result["failed_file_count"]
    status = (
        "compile_ast_boundary_failed"
        if boundary_failed
        else "compile_ast_attested_passed"
        if check_passed
        else "compile_ast_attested_failed"
    )
    terminal = {
        "schema_version": 1,
        "backend_id": request["backend_id"],
        "backend_policy_fingerprint": request["backend_policy_fingerprint"],
        "contract_policy_id": request["contract_policy_id"],
        "contract_policy_fingerprint": request["contract_policy_fingerprint"],
        "operation": request["operation"],
        "request_id": request_id,
        "host_nonce": host_nonce,
        "authorization_nonce": auth_nonce,
        "request_sha256": request_doc.sha256,
        "ready_sha256": ready_doc.sha256,
        "authorize_sha256": authorize_doc.sha256,
        "source_manifest_sha256": manifest_doc.sha256,
        "result_sha256": None if result_doc is None else result_doc.sha256,
        **artifacts,
        "public_key_sha256": public_key_hash,
        "runtime_attestation_policy_fingerprint": request["runtime_attestation_policy_fingerprint"],
        "runtime_bundle_fingerprint": request["runtime_bundle_fingerprint"],
        "runtime_lease_policy_fingerprint": request["runtime_lease_policy_fingerprint"],
        "runtime_lease_fingerprint": runtime_lease_fingerprint,
        "plan_policy_fingerprint": request["plan_policy_fingerprint"],
        "plan_fingerprint": request["plan_fingerprint"],
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
            "result_received": result_received,
            "exit_code": 1 if boundary_failed else 0,
            "is_administrator": False,
            "integrity_rid": 0x2000,
            "worker_in_job": True,
            "active_process_limit": 1,
            "process_memory_bytes": 536870912,
            "job_memory_bytes": 805306368,
            "job_closed": True,
            "sid_process_set_empty": True,
            "account_deleted": True,
        },
        "controls": {
            "input_write_blocked": True,
            "source_write_blocked": True,
            "runtime_write_blocked": True,
            "control_write_blocked": True,
            "output_writable": True,
            "ipv4_default_route_present": False,
            "ipv4_external_tcp_reachable": False,
            "ipv6_default_route_present": False,
            "ipv6_external_tcp_reachable": False,
        },
        "runtime": {
            "implementation": "CPython",
            "version": [3, 13, 15],
            "architecture_bits": 64,
            "machine": "AMD64",
            "bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
            "environment_clean": True,
            "pip_absent": True,
            "ensurepip_absent": True,
            "site_absent": True,
            "sys_path_exact": True,
            "dont_write_bytecode": True,
        },
        "check": {
            "result_received": result_received,
            "result_sha256": None if result_doc is None else result_doc.sha256,
            "selected_file_count": len(files),
            "processed_file_count": processed,
            "passed_file_count": passed,
            "failed_file_count": failed,
            "trusted_interpreter_executed": result_received,
            "changed_source_processed": result_received,
            "changed_source_ast_parsed": False if boundary_failed else result["changed_source_ast_parsed"],
            "changed_source_compiled": False if boundary_failed else result["changed_source_compiled"],
            "changed_code_executed": False,
            "imports_executed": False,
            "top_level_executed": False,
            "bytecode_written": False,
        },
        "shutdown": {
            "scheduled": True,
            "delay_seconds": 2,
        },
        "completed_at_utc": "2026-08-15T16:00:20Z",
        "status": status,
        "boundary_ok": not boundary_failed,
        "check_passed": False if boundary_failed else check_passed,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    return manifest, request, ready, authorize, result, terminal


def parse_valid_documents(
    *,
    check_passed: bool = True,
    boundary_failed: bool = False,
) -> tuple[DeveloperTaskExecutionCompileAstDocument, ...]:
    manifest, request, ready, authorize, result, terminal = build_valid_payloads(
        check_passed=check_passed,
        boundary_failed=boundary_failed,
    )
    documents: list[DeveloperTaskExecutionCompileAstDocument] = [
        parse_compile_ast_source_manifest(_canonical(manifest)),
        parse_compile_ast_request(_canonical(request)),
        parse_compile_ast_ready(_canonical(ready)),
        parse_compile_ast_authorize(_canonical(authorize)),
    ]
    if not boundary_failed:
        documents.append(parse_compile_ast_result(_canonical(result, trailing_lf=True)))
    documents.append(parse_compile_ast_terminal(_canonical(terminal)))
    return tuple(documents)


def _error_code(fn: Callable[[], Any]) -> str:
    try:
        fn()
    except DeveloperTaskExecutionCompileAstContractError as exc:
        return exc.code
    except Exception as exc:
        return type(exc).__name__
    return ""


def _case(name: str, actual: Any, expected: Any) -> bool:
    ok = actual == expected
    print(f"\n=== {name} ===")
    print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2))
    print(f"[{'OK' if ok else 'FAIL'}] {name}")
    return ok


def main() -> int:
    results: list[bool] = []
    policy_errors = list(validate_developer_task_execution_compile_ast_contract_policy())
    results.append(_case(
        "V1C2A1 PINNED CONTRACT POLICY SELF CHECKS",
        {
            "errors": policy_errors,
            "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY.policy_id,
            "fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY.fingerprint,
            "recomputed": developer_task_execution_compile_ast_contract_policy_fingerprint(),
            "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY.operation,
            "statuses": list(DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY.statuses),
            "execution_authorized": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY.execution_authorized,
        },
        {
            "errors": [],
            "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
            "fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
            "recomputed": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
            "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
            "statuses": list(DEVELOPER_TASK_EXECUTION_COMPILE_AST_STATUSES),
            "execution_authorized": False,
        },
    ))
    policy_json = canonical_developer_task_execution_compile_ast_contract_policy_json()
    results.append(_case(
        "V1C2A1 POLICY JSON IS CANONICAL AND PINNED",
        {
            "roundtrip": json.loads(policy_json)["fingerprint"],
            "sorted": policy_json == json.dumps(json.loads(policy_json), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        },
        {"roundtrip": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT, "sorted": True},
    ))
    signature = inspect.signature(build_compile_ast_source_manifest)
    results.append(_case(
        "V1C2A1 SOURCE MANIFEST API ACCEPTS ONLY TYPED PLAN AND RUN IDS",
        {
            name: {"kind": parameter.kind.name, "default": None if parameter.default is inspect.Parameter.empty else parameter.default}
            for name, parameter in signature.parameters.items()
        },
        {
            "plan_report": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "request_id": {"kind": "KEYWORD_ONLY", "default": None},
            "host_nonce": {"kind": "KEYWORD_ONLY", "default": None},
        },
    ))

    manifest_doc = build_compile_ast_source_manifest(_make_plan_report(), request_id="a" * 32, host_nonce="b" * 64)
    manifest = manifest_doc.to_dict()
    results.append(_case(
        "V1C2A1 PLAN REPORT DERIVES FLAT SORTED FIXED SOURCE MANIFEST",
        {
            "kind": manifest_doc.kind,
            "paths": [item["original_path"] for item in manifest["sources"]],
            "guest": [item["guest_file_name"] for item in manifest["sources"]],
            "virtual": [item["virtual_filename"] for item in manifest["sources"]],
            "source_root": manifest["source_root"],
            "path_used_as_fs": manifest["original_path_used_as_guest_filesystem_path"],
            "read_only": manifest["read_only_mapping"],
            "authorized": manifest["execution_authorized"],
        },
        {
            "kind": "source_manifest",
            "paths": ["a.py", "pkg/b.py"],
            "guest": ["source-0001.py", "source-0002.py"],
            "virtual": ["skynetvs://changed/a.py", "skynetvs://changed/pkg/b.py"],
            "source_root": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
            "path_used_as_fs": False,
            "read_only": True,
            "authorized": False,
        },
    ))

    encoded_manifest = encode_compile_ast_document("source_manifest", manifest)
    results.append(_case(
        "V1C2A1 CANONICAL ENCODER REVALIDATES DOCUMENT BY KIND",
        {
            "same_bytes": encoded_manifest == manifest_doc.canonical_bytes,
            "same_sha256": parse_compile_ast_source_manifest(encoded_manifest).sha256 == manifest_doc.sha256,
            "unsupported": _error_code(lambda: encode_compile_ast_document("unknown", manifest)),
        },
        {"same_bytes": True, "same_sha256": True, "unsupported": "ValueError"},
    ))

    pass_docs = parse_valid_documents(check_passed=True)
    validate_compile_ast_document_chain(*pass_docs)
    results.append(_case(
        "V1C2A1 CANONICAL PASSED TRANSCRIPT ROUNDTRIPS AND BINDS",
        {
            "kinds": [item.kind for item in pass_docs],
            "hashes": all(len(item.sha256) == 64 for item in pass_docs),
            "status": pass_docs[-1].field("status"),
            "check_passed": pass_docs[-1].field("check_passed"),
        },
        {
            "kinds": ["source_manifest", "request", "ready", "authorize", "result", "terminal"],
            "hashes": True,
            "status": "compile_ast_attested_passed",
            "check_passed": True,
        },
    ))
    failed_docs = parse_valid_documents(check_passed=False)
    validate_compile_ast_document_chain(*failed_docs)
    failed_result = failed_docs[-2].to_dict()
    results.append(_case(
        "V1C2A1 AUTHENTIC SYNTAX FAILURE IS VALID BOUNDED EVIDENCE",
        {
            "status": failed_docs[-1].field("status"),
            "boundary_ok": failed_docs[-1].field("boundary_ok"),
            "check_passed": failed_result["check_passed"],
            "error": failed_result["files"][1]["error"],
            "raw_source_field_absent": "text" not in failed_result["files"][1]["error"],
            "execution_authorized": failed_result["execution_authorized"],
        },
        {
            "status": "compile_ast_attested_failed",
            "boundary_ok": True,
            "check_passed": False,
            "error": {
                "type": "SyntaxError",
                "message": "invalid syntax",
                "line": 1,
                "offset": 5,
                "end_line": 1,
                "end_offset": 6,
            },
            "raw_source_field_absent": True,
            "execution_authorized": False,
        },
    ))
    boundary_docs = parse_valid_documents(boundary_failed=True)
    validate_compile_ast_document_chain(
        boundary_docs[0], boundary_docs[1], boundary_docs[2], boundary_docs[3], None, boundary_docs[4]
    )
    results.append(_case(
        "V1C2A1 BOUNDARY FAILURE MAY OMIT UNTRUSTED RESULT",
        {
            "status": boundary_docs[-1].field("status"),
            "result_sha256": boundary_docs[-1].field("result_sha256"),
            "boundary_ok": boundary_docs[-1].field("boundary_ok"),
            "check_passed": boundary_docs[-1].field("check_passed"),
        },
        {
            "status": "compile_ast_boundary_failed",
            "result_sha256": None,
            "boundary_ok": False,
            "check_passed": False,
        },
    ))

    results.append(_case(
        "V1C2A1 DOCUMENTS ARE IMMUTABLE HASHED SNAPSHOTS",
        {
            "dataclass_frozen": _error_code(lambda: setattr(pass_docs[0], "kind", "x")) == "FrozenInstanceError",
            "bytes_private": "canonical_bytes" not in pass_docs[0].to_dict(),
            "json": json.dumps(pass_docs[0].to_dict(), ensure_ascii=False) != "",
        },
        {"dataclass_frozen": True, "bytes_private": True, "json": True},
    ))

    manifest_payloads = build_valid_payloads()[0]
    duplicate = _canonical(manifest_payloads).replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1', 1)
    results.append(_case("V1C2A1 DUPLICATE JSON FIELD FAILS CLOSED", _error_code(lambda: parse_compile_ast_source_manifest(duplicate)), "compile_ast_json_duplicate_field"))
    request_payload = build_valid_payloads()[1]
    float_bytes = _canonical(request_payload).replace(b'"ready_timeout_seconds":120', b'"ready_timeout_seconds":120.0')
    results.append(_case("V1C2A1 FLOAT JSON NUMBER FAILS CLOSED", _error_code(lambda: parse_compile_ast_request(float_bytes)), "compile_ast_json_number_invalid"))
    nonfinite = _canonical(request_payload).replace(b'"ready_timeout_seconds":120', b'"ready_timeout_seconds":NaN')
    results.append(_case("V1C2A1 NON FINITE JSON NUMBER FAILS CLOSED", _error_code(lambda: parse_compile_ast_request(nonfinite)), "compile_ast_json_constant_invalid"))
    results.append(_case("V1C2A1 UTF8 BOM FAILS CLOSED", _error_code(lambda: parse_compile_ast_request(b"\xef\xbb\xbf" + _canonical(request_payload))), "compile_ast_json_bom_forbidden"))
    surrogate = _canonical(request_payload).replace(b'"trusted_scope":"compile_ast_changed_python_only_v1"', b'"trusted_scope":"\\ud800"')
    results.append(_case("V1C2A1 LONE SURROGATE FAILS CLOSED", _error_code(lambda: parse_compile_ast_request(surrogate)), "compile_ast_json_unicode_invalid"))
    pretty = json.dumps(request_payload, ensure_ascii=False, indent=2).encode("utf-8")
    results.append(_case("V1C2A1 NONCANONICAL JSON WHITESPACE FAILS CLOSED", _error_code(lambda: parse_compile_ast_request(pretty)), "compile_ast_json_not_canonical"))

    result_payload = build_valid_payloads()[4]
    result_body = _canonical(result_payload, trailing_lf=True)
    results.append(_case("V1C2A1 RESULT REQUIRES EXACT SINGLE LF", {
        "missing": _error_code(lambda: parse_compile_ast_result(result_body[:-1])),
        "crlf": _error_code(lambda: parse_compile_ast_result(result_body[:-1] + b"\r\n")),
        "double": _error_code(lambda: parse_compile_ast_result(result_body + b"\n")),
    }, {
        "missing": "compile_ast_json_line_ending_invalid",
        "crlf": "compile_ast_json_line_ending_invalid",
        "double": "compile_ast_json_line_ending_invalid",
    }))

    unknown = copy.deepcopy(request_payload)
    unknown["unknown"] = False
    results.append(_case("V1C2A1 UNKNOWN FIELD FAILS CLOSED", _error_code(lambda: parse_compile_ast_request(_canonical(unknown))), "compile_ast_fields_invalid"))
    reordered = {"backend_id": request_payload["backend_id"], "schema_version": 1, **{k: v for k, v in request_payload.items() if k not in {"backend_id", "schema_version"}}}
    results.append(_case("V1C2A1 FIELD ORDER IS EXACT", _error_code(lambda: parse_compile_ast_request(_canonical(reordered))), "compile_ast_fields_invalid"))

    unsafe_manifest = copy.deepcopy(manifest_payloads)
    unsafe_manifest["sources"][0]["original_path"] = "../escape.py"
    unsafe_manifest["sources"][0]["virtual_filename"] = "skynetvs://changed/../escape.py"
    results.append(_case("V1C2A1 ORIGINAL PATH TRAVERSAL FAILS CLOSED", _error_code(lambda: parse_compile_ast_source_manifest(_canonical(unsafe_manifest))), "compile_ast_source_path_invalid"))
    collision = copy.deepcopy(manifest_payloads)
    collision["sources"][0]["original_path"] = "A.py"
    collision["sources"][0]["virtual_filename"] = "skynetvs://changed/A.py"
    collision["sources"][1]["original_path"] = "a.py"
    collision["sources"][1]["virtual_filename"] = "skynetvs://changed/a.py"
    results.append(_case("V1C2A1 WINDOWS CASE COLLISION FAILS CLOSED", _error_code(lambda: parse_compile_ast_source_manifest(_canonical(collision))), "compile_ast_source_path_collision"))
    unsorted = copy.deepcopy(manifest_payloads)
    unsorted["sources"] = list(reversed(unsorted["sources"]))
    for index, item in enumerate(unsorted["sources"], start=1):
        item["ordinal"] = index
        item["guest_file_name"] = f"source-{index:04d}.py"
    results.append(_case("V1C2A1 SOURCE ORDER IS CANONICAL", _error_code(lambda: parse_compile_ast_source_manifest(_canonical(unsorted))), "compile_ast_source_order_invalid"))
    bad_guest = copy.deepcopy(manifest_payloads)
    bad_guest["sources"][0]["guest_file_name"] = "a.py"
    results.append(_case("V1C2A1 ORIGINAL PATH CANNOT BECOME GUEST FILENAME", _error_code(lambda: parse_compile_ast_source_manifest(_canonical(bad_guest))), "compile_ast_guest_file_name_invalid"))
    bad_virtual = copy.deepcopy(manifest_payloads)
    bad_virtual["sources"][0]["virtual_filename"] = "C:/host/a.py"
    results.append(_case("V1C2A1 DIAGNOSTIC FILENAME IS FIXED VIRTUAL URI", _error_code(lambda: parse_compile_ast_source_manifest(_canonical(bad_virtual))), "compile_ast_virtual_filename_invalid"))
    bad_count = copy.deepcopy(manifest_payloads)
    bad_count["selected_file_count"] = 1
    results.append(_case("V1C2A1 SOURCE COUNT MISMATCH FAILS CLOSED", _error_code(lambda: parse_compile_ast_source_manifest(_canonical(bad_count))), "compile_ast_source_count_mismatch"))
    bad_total = copy.deepcopy(manifest_payloads)
    bad_total["selected_total_bytes"] += 1
    results.append(_case("V1C2A1 SOURCE TOTAL MISMATCH FAILS CLOSED", _error_code(lambda: parse_compile_ast_source_manifest(_canonical(bad_total))), "compile_ast_source_total_mismatch"))

    bad_request = copy.deepcopy(request_payload)
    bad_request["worker_timeout_seconds"] = 61
    results.append(_case("V1C2A1 REQUEST TIMEOUTS ARE PINNED", _error_code(lambda: parse_compile_ast_request(_canonical(bad_request))), "compile_ast_field_value_invalid"))
    bad_runtime = copy.deepcopy(request_payload)
    bad_runtime["runtime_bundle_fingerprint"] = _sha("other-runtime")
    results.append(_case("V1C2A1 REQUEST RUNTIME IDENTITY IS PINNED", _error_code(lambda: parse_compile_ast_request(_canonical(bad_runtime))), "compile_ast_identity_mismatch"))

    ready_payload = build_valid_payloads()[2]
    bad_key = copy.deepcopy(ready_payload)
    bad_key["public_key_sha256"] = _sha("wrong-key")
    results.append(_case("V1C2A1 READY PUBLIC KEY HASH IS BOUND", _error_code(lambda: parse_compile_ast_ready(_canonical(bad_key))), "compile_ast_public_key_hash_mismatch"))
    bad_controller = copy.deepcopy(ready_payload)
    bad_controller["controller_sid"] = "S-1-5-19"
    results.append(_case("V1C2A1 READY REQUIRES LOCALSYSTEM CONTROLLER", _error_code(lambda: parse_compile_ast_ready(_canonical(bad_controller))), "compile_ast_controller_identity_invalid"))
    bad_ready_checks = copy.deepcopy(ready_payload)
    bad_ready_checks["ready_checks"]["source_manifest_verified"] = False
    bad_ready_checks["failed_ready_checks"] = ["source_manifest_verified"]
    results.append(_case("V1C2A1 FAILED READY CHECKS FAIL CLOSED", _error_code(lambda: parse_compile_ast_ready(_canonical(bad_ready_checks))), "compile_ast_field_value_invalid"))

    authorize_payload = build_valid_payloads()[3]
    bad_authorize = copy.deepcopy(authorize_payload)
    bad_authorize["allow_compile_ast"] = False
    results.append(_case("V1C2A1 AUTHORIZE CAN ONLY ALLOW FIXED COMPILE AST", _error_code(lambda: parse_compile_ast_authorize(_canonical(bad_authorize))), "compile_ast_field_value_invalid"))

    raw_source_result = copy.deepcopy(result_payload)
    raw_source_result["files"][0]["error"] = {
        "type": "SyntaxError", "message": "bad", "line": 1, "offset": 1, "end_line": 1, "end_offset": 2, "text": "secret source"
    }
    raw_source_result["files"][0]["compile_ok"] = False
    raw_source_result["files"][0]["ast_parse_ok"] = False
    raw_source_result["check_passed"] = False
    raw_source_result["passed_file_count"] = 1
    raw_source_result["failed_file_count"] = 1
    raw_source_result["changed_source_ast_parsed"] = False
    raw_source_result["changed_source_compiled"] = False
    results.append(_case("V1C2A1 RAW SOURCE TEXT FIELD IS REJECTED", _error_code(lambda: parse_compile_ast_result(_canonical(raw_source_result, trailing_lf=True))), "compile_ast_fields_invalid"))
    long_error = copy.deepcopy(raw_source_result)
    long_error["files"][0]["error"].pop("text")
    long_error["files"][0]["error"]["message"] = "x" * 513
    results.append(_case("V1C2A1 SYNTAX MESSAGE IS BOUNDED", _error_code(lambda: parse_compile_ast_result(_canonical(long_error, trailing_lf=True))), "compile_ast_field_value_invalid"))
    newline_error = copy.deepcopy(long_error)
    newline_error["files"][0]["error"]["message"] = "line1\nsource text"
    results.append(_case("V1C2A1 SYNTAX MESSAGE CANNOT EMBED SOURCE LINES", _error_code(lambda: parse_compile_ast_result(_canonical(newline_error, trailing_lf=True))), "compile_ast_error_message_invalid"))
    pass_with_error = copy.deepcopy(result_payload)
    pass_with_error["files"][0]["error"] = {"type": "SyntaxError", "message": "bad", "line": 1, "offset": 1, "end_line": 1, "end_offset": 2}
    results.append(_case("V1C2A1 PASSING FILE CANNOT CARRY ERROR", _error_code(lambda: parse_compile_ast_result(_canonical(pass_with_error, trailing_lf=True))), "compile_ast_result_error_invalid"))
    global_mismatch = copy.deepcopy(result_payload)
    global_mismatch["changed_source_compiled"] = False
    results.append(_case("V1C2A1 GLOBAL RESULT FLAGS MUST MATCH FILES", _error_code(lambda: parse_compile_ast_result(_canonical(global_mismatch, trailing_lf=True))), "compile_ast_result_status_invalid"))

    terminal_payload = build_valid_payloads()[5]
    bad_terminal_status = copy.deepcopy(terminal_payload)
    bad_terminal_status["status"] = "compile_ast_attested_failed"
    results.append(_case("V1C2A1 TERMINAL STATUS MUST MATCH CHECK OUTCOME", _error_code(lambda: parse_compile_ast_terminal(_canonical(bad_terminal_status))), "compile_ast_terminal_status_invalid"))
    bad_exit = copy.deepcopy(terminal_payload)
    bad_exit["worker"]["exit_code"] = 1
    results.append(_case("V1C2A1 ATTESTED TERMINAL REQUIRES ZERO WORKER EXIT", _error_code(lambda: parse_compile_ast_terminal(_canonical(bad_exit))), "compile_ast_terminal_status_invalid"))
    bad_boundary_terminal = copy.deepcopy(build_valid_payloads(boundary_failed=True)[5])
    bad_boundary_terminal["result_sha256"] = _sha("forged-result")
    bad_boundary_terminal["worker"]["result_received"] = True
    bad_boundary_terminal["check"]["result_received"] = True
    bad_boundary_terminal["check"]["result_sha256"] = bad_boundary_terminal["result_sha256"]
    results.append(_case("V1C2A1 BOUNDARY FAILURE CANNOT CLAIM RESULT", _error_code(lambda: parse_compile_ast_terminal(_canonical(bad_boundary_terminal))), "compile_ast_terminal_status_invalid"))

    chain_docs = list(parse_valid_documents())
    request_tampered = chain_docs[1].to_dict()
    request_tampered["source_manifest_sha256"] = _sha("other-manifest")
    chain_docs[1] = parse_compile_ast_request(_canonical(request_tampered))
    results.append(_case("V1C2A1 CROSS DOCUMENT HASH TAMPER FAILS CLOSED", _error_code(lambda: validate_compile_ast_document_chain(*chain_docs)), "compile_ast_chain_mismatch"))

    chain_docs = list(parse_valid_documents())
    result_tampered = chain_docs[-2].to_dict()
    result_tampered["files"][0]["sha256"] = _sha("different-source")
    chain_docs[-2] = parse_compile_ast_result(_canonical(result_tampered, trailing_lf=True))
    terminal = chain_docs[-1].to_dict()
    terminal["result_sha256"] = chain_docs[-2].sha256
    terminal["check"]["result_sha256"] = chain_docs[-2].sha256
    chain_docs[-1] = parse_compile_ast_terminal(_canonical(terminal))
    results.append(_case("V1C2A1 RESULT SOURCE IDENTITY TAMPER FAILS CHAIN", _error_code(lambda: validate_compile_ast_document_chain(*chain_docs)), "compile_ast_chain_mismatch"))

    results.append(_case("V1C2A1 SIGNATURE BYTES ARE STRICT", {
        "valid_len": len(validate_compile_ast_signature_bytes(bytes(range(1, 65)))),
        "short": _error_code(lambda: validate_compile_ast_signature_bytes(b"x" * 63)),
        "zero": _error_code(lambda: validate_compile_ast_signature_bytes(b"\x00" * 64)),
    }, {
        "valid_len": 64,
        "short": "compile_ast_signature_size_invalid",
        "zero": "compile_ast_signature_invalid",
    }))

    oversized = _canonical(request_payload) + b" " * (65536 - len(_canonical(request_payload)) + 1)
    results.append(_case("V1C2A1 DOCUMENT SIZE LIMIT FAILS CLOSED", _error_code(lambda: parse_compile_ast_request(oversized)), "compile_ast_document_too_large"))

    mutated = replace(DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY, max_file_count=21)
    results.append(_case("V1C2A1 POLICY MUTATION INVALIDATES FINGERPRINT", {
        "fingerprint_changed": developer_task_execution_compile_ast_contract_policy_fingerprint(mutated) != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        "errors": list(validate_developer_task_execution_compile_ast_contract_policy(mutated)),
    }, {
        "fingerprint_changed": True,
        "errors": ["source_limits_invalid", "policy_values_changed", "policy_fingerprint_mismatch"],
    }))

    source = CONTRACT_PATH.read_text(encoding="utf-8")
    policy_source = POLICY_PATH.read_text(encoding="utf-8")
    forbidden = (
        "WindowsSandbox.exe",
        "subprocess",
        "importlib",
        "runpy",
        "pip install",
        "files.pythonhosted.org",
        "requests.get",
        "urllib.request",
        "shell=True",
        "os.system(",
    )
    tree = ast.parse(source + "\n" + policy_source)
    active_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in {"compile", "exec", "eval"}:
            active_calls.append(node.func.id)
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "ast"
            and node.func.attr == "parse"
        ):
            active_calls.append("ast.parse")
    actual_surfaces = {token: token in source or token in policy_source for token in forbidden}
    actual_surfaces["active_parse_compile_exec_eval_calls"] = active_calls
    expected_surfaces = {token: False for token in forbidden}
    expected_surfaces["active_parse_compile_exec_eval_calls"] = []
    results.append(_case(
        "V1C2A1 CONTRACT HAS NO ACTIVE RUNNER SANDBOX NETWORK OR SHELL SURFACE",
        actual_surfaces,
        expected_surfaces,
    ))

    summary = {"case_count": len(results), "fail_count": sum(not item for item in results)}
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["fail_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
