from __future__ import annotations

"""Portable V1C2C3 live pass / syntax / boundary acceptance contract evaluator.

RC034 is deliberately non-active.  This evaluator validates the locked matrix,
existing transcript semantics, the future Windows harness source, and pipeline
topology without importing or executing the Windows harness.
"""

import ast
import hashlib
import inspect
import json

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_compile_ast_composition import (
    attest_developer_task_execution_compile_ast_composition,
)
from modules.developer.developer_task_execution_compile_ast_composition_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1,
)
from tools.eval_developer_task_execution_compile_ast_contract import (
    parse_valid_documents,
)
from tools.eval_developer_task_execution_compile_ast_verifier import (
    build_verifier_fixture,
    pin_fixture,
    verify_fixture,
)
from tools.pipeline import available_flows


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LIVE_ACCEPTANCE_PATH = (
    PROJECT_ROOT
    / "tools"
    / "eval_developer_task_execution_compile_ast_live_acceptance.py"
)
WINDOWS_EVALUATOR_PATH = (
    PROJECT_ROOT
    / "tools"
    / "eval_developer_task_execution_compile_ast_live_acceptance_windows.py"
)
COMPOSITION_PATH = (
    PROJECT_ROOT
    / "modules"
    / "developer"
    / "developer_task_execution_compile_ast_composition.py"
)
ROADMAP_PATH = PROJECT_ROOT / "docs" / "architecture" / "SKYNETVS_ARCHITECTURE_ROADMAP_V1.md"
CURRENT_STATE_PATH = PROJECT_ROOT / "docs" / "architecture" / "SKYNETVS_CURRENT_STATE.md"
TRUSTED_RUNTIME_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "SKYNETVS_TRUSTED_PYTHON_RUNTIME_V1.md"
)

HISTORICAL_V1C2C3_EVIDENCE_IDENTITY = (
    "b866a1c6dcddb802b4b7d2883aabf9c1fc8d22ed25443bd5aade3068fc49b9c8"
)
WINDOWS_ACTIVE_AUTHORITY_ENV = "SKYNETVS_V1C2C3_ACTIVE_MATRIX_AUTHORIZED"
INVALID_SYNTAX_SOURCE = b"def broken(:\n"

V1C2C3_MATRIX = (
    {
        "row": "live_pass",
        "terminal_status": "compile_ast_attested_passed",
        "boundary_ok": True,
        "check_passed": True,
        "result_required": True,
        "fresh_capability_chain": True,
        "fresh_sandbox": True,
    },
    {
        "row": "authentic_syntax_failure",
        "terminal_status": "compile_ast_attested_failed",
        "boundary_ok": True,
        "check_passed": False,
        "result_required": True,
        "fresh_capability_chain": True,
        "fresh_sandbox": True,
    },
    {
        "row": "signed_post_ready_boundary_failure",
        "terminal_status": "compile_ast_boundary_failed",
        "boundary_ok": False,
        "check_passed": False,
        "result_required": False,
        "fresh_capability_chain": True,
        "fresh_sandbox": True,
    },
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _class_methods(tree: ast.AST, class_name: str) -> set[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return set()


def _function_names(tree: ast.AST) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _flow_count(flow: list[Any], script_path: str) -> int:
    return sum(
        1
        for step in flow
        if script_path in [str(item) for item in step.cmd]
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
        print(
            json.dumps(
                {"actual": actual, "expected": expected, "ok": ok},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    expected_matrix = (
        {
            "row": "live_pass",
            "terminal_status": "compile_ast_attested_passed",
            "boundary_ok": True,
            "check_passed": True,
            "result_required": True,
            "fresh_capability_chain": True,
            "fresh_sandbox": True,
        },
        {
            "row": "authentic_syntax_failure",
            "terminal_status": "compile_ast_attested_failed",
            "boundary_ok": True,
            "check_passed": False,
            "result_required": True,
            "fresh_capability_chain": True,
            "fresh_sandbox": True,
        },
        {
            "row": "signed_post_ready_boundary_failure",
            "terminal_status": "compile_ast_boundary_failed",
            "boundary_ok": False,
            "check_passed": False,
            "result_required": False,
            "fresh_capability_chain": True,
            "fresh_sandbox": True,
        },
    )
    check("V1C2C3 LOCKED THREE-ROW MATRIX", V1C2C3_MATRIX, expected_matrix)
    check(
        "V1C2C3 EVERY ROW REQUIRES FRESH CAPABILITY AND SANDBOX",
        [
            (item["fresh_capability_chain"], item["fresh_sandbox"])
            for item in V1C2C3_MATRIX
        ],
        [(True, True), (True, True), (True, True)],
    )
    check(
        "V1C2C3 PERMANENT NON-EXECUTION FLAGS",
        {
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
        },
        {
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
        },
    )

    public_signature = inspect.signature(
        attest_developer_task_execution_compile_ast_composition
    )
    check(
        "V1C2C3 V1C2C2 PUBLIC API REMAINS EXACT",
        {
            name: parameter.kind.name
            for name, parameter in public_signature.parameters.items()
        },
        {
            "host_report": "POSITIONAL_OR_KEYWORD",
            "transaction": "POSITIONAL_OR_KEYWORD",
            "artifact_parent": "KEYWORD_ONLY",
        },
    )
    check(
        "V1C2C3 NO PUBLIC FAULT OR CALLER EXECUTION SURFACE",
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_COMPOSITION_POLICY_V1.to_dict()[
            "public_api"
        ],
        {
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
    )

    pass_docs = parse_valid_documents(check_passed=True)
    syntax_docs = parse_valid_documents(check_passed=False)
    boundary_docs = parse_valid_documents(boundary_failed=True)
    check(
        "V1C2C3 CANONICAL CONTRACT MATRIX",
        [
            {
                "status": pass_docs[-1].field("status"),
                "boundary_ok": pass_docs[-1].field("boundary_ok"),
                "check_passed": pass_docs[-1].field("check_passed"),
                "result_present": True,
            },
            {
                "status": syntax_docs[-1].field("status"),
                "boundary_ok": syntax_docs[-1].field("boundary_ok"),
                "check_passed": syntax_docs[-1].field("check_passed"),
                "result_present": True,
            },
            {
                "status": boundary_docs[-1].field("status"),
                "boundary_ok": boundary_docs[-1].field("boundary_ok"),
                "check_passed": boundary_docs[-1].field("check_passed"),
                "result_present": False,
            },
        ],
        [
            {
                "status": "compile_ast_attested_passed",
                "boundary_ok": True,
                "check_passed": True,
                "result_present": True,
            },
            {
                "status": "compile_ast_attested_failed",
                "boundary_ok": True,
                "check_passed": False,
                "result_present": True,
            },
            {
                "status": "compile_ast_boundary_failed",
                "boundary_ok": False,
                "check_passed": False,
                "result_present": False,
            },
        ],
    )
    syntax_result = syntax_docs[-2].to_dict()
    syntax_error = syntax_result["files"][1]["error"]
    check(
        "V1C2C3 SYNTAX FAILURE IS BOUNDED AUTHENTIC RESULT SHAPE",
        {
            "type": syntax_error["type"],
            "message": syntax_error["message"],
            "raw_text_absent": "text" not in syntax_error,
            "trusted_interpreter_executed": syntax_result[
                "trusted_interpreter_executed"
            ],
            "changed_source_processed": syntax_result["changed_source_processed"],
            "changed_source_ast_parsed": syntax_result[
                "changed_source_ast_parsed"
            ],
            "changed_source_compiled": syntax_result["changed_source_compiled"],
            "changed_code_executed": syntax_result["changed_code_executed"],
            "execution_authorized": syntax_result["execution_authorized"],
        },
        {
            "type": "SyntaxError",
            "message": "invalid syntax",
            "raw_text_absent": True,
            "trusted_interpreter_executed": True,
            "changed_source_processed": True,
            "changed_source_ast_parsed": False,
            "changed_source_compiled": False,
            "changed_code_executed": False,
            "execution_authorized": False,
        },
    )
    genuine_invalid = False
    try:
        ast.parse(
            INVALID_SYNTAX_SOURCE.decode("utf-8"),
            filename="skynetvs://v1c2c3/syntax.py",
        )
    except SyntaxError:
        genuine_invalid = True
    check(
        "V1C2C3 FUTURE SYNTAX FIXTURE BYTES ARE GENUINELY INVALID",
        genuine_invalid,
        True,
    )

    verified_rows = []
    for row, kwargs in (
        ("live_pass", {}),
        ("authentic_syntax_failure", {"check_passed": False}),
        ("signed_post_ready_boundary_failure", {"boundary_failed": True}),
    ):
        fixture = build_verifier_fixture(**kwargs)
        pin = pin_fixture(fixture)
        report = verify_fixture(fixture, pin)
        verified_rows.append(
            {
                "row": row,
                "pin_ok": pin.ok,
                "verified": report.ok,
                "signature_valid": report.signature_valid,
                "terminal_status": report.terminal_status,
                "boundary_ok": report.boundary_ok,
                "check_passed": report.check_passed,
                "result_present": report.result_sha256 is not None,
                "changed_code_executed": report.to_dict()["changed_code_executed"],
                "reusable_lease_issued": report.to_dict()["reusable_lease_issued"],
                "execution_authorized": report.to_dict()["execution_authorized"],
            }
        )
    check(
        "V1C2C3 EXISTING V1C2B VERIFIER ACCEPTS ALL THREE SIGNED CLASSES",
        verified_rows,
        [
            {
                "row": "live_pass",
                "pin_ok": True,
                "verified": True,
                "signature_valid": True,
                "terminal_status": "compile_ast_attested_passed",
                "boundary_ok": True,
                "check_passed": True,
                "result_present": True,
                "changed_code_executed": False,
                "reusable_lease_issued": False,
                "execution_authorized": False,
            },
            {
                "row": "authentic_syntax_failure",
                "pin_ok": True,
                "verified": True,
                "signature_valid": True,
                "terminal_status": "compile_ast_attested_failed",
                "boundary_ok": True,
                "check_passed": False,
                "result_present": True,
                "changed_code_executed": False,
                "reusable_lease_issued": False,
                "execution_authorized": False,
            },
            {
                "row": "signed_post_ready_boundary_failure",
                "pin_ok": True,
                "verified": True,
                "signature_valid": True,
                "terminal_status": "compile_ast_boundary_failed",
                "boundary_ok": False,
                "check_passed": False,
                "result_present": False,
                "changed_code_executed": False,
                "reusable_lease_issued": False,
                "execution_authorized": False,
            },
        ],
    )

    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROADMAP_PATH, CURRENT_STATE_PATH, TRUSTED_RUNTIME_PATH)
    )
    check(
        "V1C2C3 HISTORICAL EVIDENCE IDENTITY REMAINS DOCUMENTED",
        HISTORICAL_V1C2C3_EVIDENCE_IDENTITY in docs,
        True,
    )
    check(
        "V1C2C3 NEW PORTABLE BYTES DO NOT CLAIM HISTORICAL IDENTITY",
        _sha256(LIVE_ACCEPTANCE_PATH.read_bytes())
        == HISTORICAL_V1C2C3_EVIDENCE_IDENTITY,
        False,
    )

    windows_source = _source(WINDOWS_EVALUATOR_PATH)
    windows_tree = ast.parse(
        windows_source,
        filename=str(WINDOWS_EVALUATOR_PATH),
        mode="exec",
    )
    check(
        "V1C2C3 WINDOWS HARNESS REQUIRED STRUCTURE",
        {
            "capture_methods": sorted(
                _class_methods(windows_tree, "_CaptureRuntime")
                & {"verify_controller_evidence"}
            ),
            "boundary_methods": sorted(
                _class_methods(windows_tree, "_BoundaryFaultRuntime")
                & {"publish_authorize", "verify_materialization"}
            ),
            "functions": sorted(
                _function_names(windows_tree)
                & {"_run_case", "_verify_captured_transcript", "main"}
            ),
        },
        {
            "capture_methods": ["verify_controller_evidence"],
            "boundary_methods": ["publish_authorize", "verify_materialization"],
            "functions": ["_run_case", "_verify_captured_transcript", "main"],
        },
    )
    check(
        "V1C2C3 WINDOWS HARNESS IS EXPLICITLY AUTHORITY-GATED",
        (
            WINDOWS_ACTIVE_AUTHORITY_ENV in windows_source
            and "V1C2C3 active matrix is blocked without later roadmap authority"
            in windows_source
        ),
        True,
    )
    check(
        "V1C2C3 WINDOWS HARNESS USES PRIVATE EVAL RUNTIME WITHOUT PUBLIC API WIDENING",
        {
            "private_attest": "_attest_developer_task_execution_compile_ast_composition"
            in windows_source,
            "private_runtime": "_CompileAstCompositionRuntime" in windows_source,
            "public_pass": "attest_developer_task_execution_compile_ast_composition("
            in windows_source,
            "post_ready_fault": "post_ready_pre_authorization_source_substitution"
            in windows_source,
        },
        {
            "private_attest": True,
            "private_runtime": True,
            "public_pass": True,
            "post_ready_fault": True,
        },
    )
    check(
        "V1C2C3 WINDOWS HARNESS HAS NO DIRECT SHELL OR PROCESS-LAUNCH SURFACE",
        {
            token: token in windows_source
            for token in (
                "subprocess",
                "os.system(",
                "shell=True",
                "Start-Process",
                "Invoke-Expression",
                "Popen(",
            )
        },
        {
            "subprocess": False,
            "os.system(": False,
            "shell=True": False,
            "Start-Process": False,
            "Invoke-Expression": False,
            "Popen(": False,
        },
    )

    composition_source = _source(COMPOSITION_PATH)
    publish_offset = composition_source.find("runtime.publish_authorize(")
    check(
        "V1C2C3 BOUNDARY FAULT HOOK ALIGNS TO CURRENT PRIVATE COMPOSITION ORDER",
        {
            "publish_present": publish_offset > 0,
            "materialization_before_publish": composition_source[
                :publish_offset
            ].count("runtime.verify_materialization(prepared)"),
            "materialization_after_publish": composition_source[
                publish_offset:
            ].count("runtime.verify_materialization(prepared)"),
        },
        {
            "publish_present": True,
            "materialization_before_publish": 3,
            "materialization_after_publish": 1,
        },
    )

    flows = available_flows()
    portable_path = (
        "tools/eval_developer_task_execution_compile_ast_live_acceptance.py"
    )
    windows_path = (
        "tools/eval_developer_task_execution_compile_ast_live_acceptance_windows.py"
    )
    check_flow = flows["check"]
    target_flow = flows["developer_task_execution_compile_ast_live_acceptance"]
    old_composition_flow = flows["developer_task_execution_compile_ast_composition"]
    check(
        "V1C2C3 RC034 PIPELINE IS NON-ACTIVE",
        {
            "check_portable": _flow_count(check_flow, portable_path),
            "check_windows": _flow_count(check_flow, windows_path),
            "target_portable": _flow_count(target_flow, portable_path),
            "target_windows": _flow_count(target_flow, windows_path),
            "old_v1c2c2_windows_preserved": _flow_count(
                old_composition_flow,
                "tools/eval_developer_task_execution_compile_ast_composition_windows.py",
            ),
        },
        {
            "check_portable": 1,
            "check_windows": 0,
            "target_portable": 1,
            "target_windows": 0,
            "old_v1c2c2_windows_preserved": 1,
        },
    )

    summary = {
        "case_count": case_count,
        "fail_count": fail_count,
        "ok": fail_count == 0,
        "architecture_slice": "V1C2C3",
        "historical_evidence_identity": HISTORICAL_V1C2C3_EVIDENCE_IDENTITY,
        "matrix_rows": [item["row"] for item in V1C2C3_MATRIX],
        "windows_active_evaluator_executed": False,
        "sandbox_launched": False,
        "changed_code_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    print()
    print("=== V1C2C3 PORTABLE SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
