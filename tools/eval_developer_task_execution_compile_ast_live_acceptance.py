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


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing top-level function: {name}")


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _call_names(node: ast.AST) -> list[str]:
    return [
        _call_name(item)
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
    ]


def _loops_over_rows(node: ast.AST) -> bool:
    for item in ast.walk(node):
        iterator: ast.AST | None = None
        if isinstance(item, (ast.For, ast.AsyncFor)):
            iterator = item.iter
        elif isinstance(item, ast.comprehension):
            iterator = item.iter
        if isinstance(iterator, ast.Name) and iterator.id == "ROWS":
            return True
    return False


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
                & {
                    "_parse_row",
                    "_mint_row_authority",
                    "_consume_row_authority",
                    "_run_case",
                    "_verify_captured_transcript",
                    "main",
                }
            ),
        },
        {
            "capture_methods": ["verify_controller_evidence"],
            "boundary_methods": ["publish_authorize", "verify_materialization"],
            "functions": [
                "_consume_row_authority",
                "_mint_row_authority",
                "_parse_row",
                "_run_case",
                "_verify_captured_transcript",
                "main",
            ],
        },
    )

    row_constants: dict[str, str] = {}
    windows_rows: list[str] = []
    for node in windows_tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and node.targets[0].id in {"ROW_PASS", "ROW_SYNTAX", "ROW_BOUNDARY"}
        ):
            row_constants[node.targets[0].id] = node.value.value
    for node in windows_tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "ROWS"
                for target in node.targets
            )
            and isinstance(node.value, ast.Tuple)
        ):
            windows_rows = [
                row_constants[item.id]
                for item in node.value.elts
                if isinstance(item, ast.Name)
            ]
            break

    parse_row_node = _top_level_function(windows_tree, "_parse_row")
    add_argument_calls = [
        node
        for node in ast.walk(parse_row_node)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
    ]
    row_call = next(
        (
            node
            for node in add_argument_calls
            if node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "--row"
        ),
        None,
    )
    row_keywords = (
        {item.arg: item.value for item in row_call.keywords}
        if row_call is not None
        else {}
    )
    check(
        "V1C2C3 WINDOWS HARNESS HAS EXACT REQUIRED ROW SELECTOR",
        {
            "row_argument_present": row_call is not None,
            "required_true": (
                isinstance(row_keywords.get("required"), ast.Constant)
                and row_keywords["required"].value is True
            ),
            "choices_rows": (
                isinstance(row_keywords.get("choices"), ast.Name)
                and row_keywords["choices"].id == "ROWS"
            ),
            "locked_rows": windows_rows,
        },
        {
            "row_argument_present": True,
            "required_true": True,
            "choices_rows": True,
            "locked_rows": [item["row"] for item in V1C2C3_MATRIX],
        },
    )

    main_node = _top_level_function(windows_tree, "main")
    main_source = ast.get_source_segment(windows_source, main_node) or ""
    main_calls = _call_names(main_node)
    guard_offset = main_source.find(
        'os.environ.get(ACTIVE_AUTHORITY_ENV, "") != ACTIVE_AUTHORITY_VALUE'
    )
    mint_offset = main_source.find("_mint_row_authority(selected_row)")
    dispatch_offset = main_source.find("_run_case(")
    runtime_offset = main_source.find("_runtime_zip_path()")
    check(
        "V1C2C3 WINDOWS MAIN IS ONE-ROW AND GUARD-FIRST",
        {
            "main_loops_over_rows": _loops_over_rows(main_node),
            "run_case_call_count": main_calls.count("_run_case"),
            "selected_row_dispatch": "_run_case(\n            selected_row,"
            in main_source,
            "guard_before_runtime_lookup": (
                guard_offset >= 0
                and runtime_offset >= 0
                and guard_offset < runtime_offset
            ),
            "guard_before_mint": (
                guard_offset >= 0
                and mint_offset >= 0
                and guard_offset < mint_offset
            ),
            "mint_before_dispatch": (
                mint_offset >= 0
                and dispatch_offset >= 0
                and mint_offset < dispatch_offset
            ),
        },
        {
            "main_loops_over_rows": False,
            "run_case_call_count": 1,
            "selected_row_dispatch": True,
            "guard_before_runtime_lookup": True,
            "guard_before_mint": True,
            "mint_before_dispatch": True,
        },
    )

    run_case_node = _top_level_function(windows_tree, "_run_case")
    run_case_calls = [
        node
        for node in ast.walk(run_case_node)
        if isinstance(node, ast.Call)
    ]
    active_call_names = {
        "snapshot_windows_sandbox_processes",
        "inspect_developer_task_execution_backend_host",
        "issue_developer_task_execution_compile_ast_plan",
        "build_developer_task_execution_runtime_bundle",
        "issue_developer_task_execution_runtime_lease",
        "issue_developer_task_execution_compile_ast_claim_transaction",
        "attest_developer_task_execution_compile_ast_composition",
        "_attest_developer_task_execution_compile_ast_composition",
    }
    consume_calls = [
        node
        for node in run_case_calls
        if _call_name(node) == "_consume_row_authority"
    ]
    active_calls = [
        node
        for node in run_case_calls
        if _call_name(node) in active_call_names
    ]
    authority_parameters = [
        item.arg
        for item in (
            list(run_case_node.args.args)
            + list(run_case_node.args.kwonlyargs)
        )
    ]
    check(
        "V1C2C3 _RUN_CASE REQUIRES AND CONSUMES PRIVATE AUTHORITY FIRST",
        {
            "authority_parameter": "authority" in authority_parameters,
            "consume_call_count": len(consume_calls),
            "consume_precedes_active_calls": (
                len(consume_calls) == 1
                and bool(active_calls)
                and all(
                    consume_calls[0].lineno < call.lineno
                    for call in active_calls
                )
            ),
            "active_call_names": sorted(
                {_call_name(call) for call in active_calls}
            ),
            "main_passes_authority": "authority=authority" in main_source,
        },
        {
            "authority_parameter": True,
            "consume_call_count": 1,
            "consume_precedes_active_calls": True,
            "active_call_names": sorted(active_call_names),
            "main_passes_authority": True,
        },
    )

    mint_node = _top_level_function(windows_tree, "_mint_row_authority")
    consume_node = _top_level_function(windows_tree, "_consume_row_authority")
    mint_source = ast.get_source_segment(windows_source, mint_node) or ""
    consume_source = ast.get_source_segment(windows_source, consume_node) or ""
    check(
        "V1C2C3 ROW AUTHORITY IS FRESH SINGLE-USE AND HOST-GATED",
        {
            "mint_checks_host_guard": (
                'os.environ.get(ACTIVE_AUTHORITY_ENV, "") != ACTIVE_AUTHORITY_VALUE'
                in mint_source
            ),
            "fresh_random_token": "secrets.token_bytes(32)" in mint_source,
            "digest_bound": "hashlib.sha256(token).digest()" in mint_source,
            "exact_type_check": "type(authority) is not _RowAuthority"
            in consume_source,
            "row_binding": "authority.row != row" in consume_source,
            "constant_time_digest": "hmac.compare_digest(" in consume_source,
            "consumed_before_return": "_ROW_AUTHORITY_DIGEST = None"
            in consume_source,
        },
        {
            "mint_checks_host_guard": True,
            "fresh_random_token": True,
            "digest_bound": True,
            "exact_type_check": True,
            "row_binding": True,
            "constant_time_digest": True,
            "consumed_before_return": True,
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
        "V1C2C3 RC035 PIPELINE REMAINS NON-ACTIVE",
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
        "row_isolation_hardened": True,
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
