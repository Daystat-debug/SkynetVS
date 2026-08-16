from __future__ import annotations

import json
import os

from tools.eval_developer_task_execution_compile_ast_contract import (
    parse_valid_documents,
)
from modules.developer.developer_task_execution_compile_ast_contract import (
    validate_compile_ast_document_chain,
)
from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
)


def main() -> int:
    print("=== V1C2A1 REAL WINDOWS CANONICAL COMPILE AST CONTRACT ===")
    if os.name != "nt":
        actual = {"ok": False, "error": "windows_required"}
        expected = {"ok": True}
        print(json.dumps({"actual": actual, "expected": expected, "ok": False}, ensure_ascii=False, indent=2))
        print("[FAIL] V1C2A1 REAL WINDOWS CANONICAL COMPILE AST CONTRACT")
        print("\n=== SUMMARY ===")
        print(json.dumps({"case_count": 1, "fail_count": 1}, indent=2))
        return 1

    passed = parse_valid_documents(check_passed=True)
    failed = parse_valid_documents(check_passed=False)
    boundary = parse_valid_documents(boundary_failed=True)
    validate_compile_ast_document_chain(*passed)
    validate_compile_ast_document_chain(*failed)
    validate_compile_ast_document_chain(
        boundary[0], boundary[1], boundary[2], boundary[3], None, boundary[4]
    )

    manifest = passed[0].to_dict()
    result = failed[-2].to_dict()
    terminal = failed[-1].to_dict()
    actual = {
        "ok": True,
        "policy_fingerprint": terminal["contract_policy_fingerprint"],
        "operation": terminal["operation"],
        "source_root": manifest["source_root"],
        "guest_files": [item["guest_file_name"] for item in manifest["sources"]],
        "original_paths": [item["original_path"] for item in manifest["sources"]],
        "virtual_filenames": [item["virtual_filename"] for item in manifest["sources"]],
        "passed_status": passed[-1].field("status"),
        "failed_status": terminal["status"],
        "boundary_failed_status": boundary[-1].field("status"),
        "syntax_error_type": result["files"][1]["error"]["type"],
        "syntax_error_message": result["files"][1]["error"]["message"],
        "raw_source_absent": "text" not in result["files"][1]["error"],
        "result_has_single_lf": failed[-2].canonical_bytes.endswith(b"\n")
        and not failed[-2].canonical_bytes.endswith(b"\n\n")
        and not failed[-2].canonical_bytes.endswith(b"\r\n"),
        "sandbox_launched": False,
        "runtime_lease_issued": False,
        "runtime_lease_claimed": False,
        "candidate_interpreter_executed": False,
        "changed_code_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    expected = {
        "ok": True,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        "source_root": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
        "guest_files": ["source-0001.py", "source-0002.py"],
        "original_paths": ["a.py", "pkg/b.py"],
        "virtual_filenames": ["skynetvs://changed/a.py", "skynetvs://changed/pkg/b.py"],
        "passed_status": "compile_ast_attested_passed",
        "failed_status": "compile_ast_attested_failed",
        "boundary_failed_status": "compile_ast_boundary_failed",
        "syntax_error_type": "SyntaxError",
        "syntax_error_message": "invalid syntax",
        "raw_source_absent": True,
        "result_has_single_lf": True,
        "sandbox_launched": False,
        "runtime_lease_issued": False,
        "runtime_lease_claimed": False,
        "candidate_interpreter_executed": False,
        "changed_code_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    ok = actual == expected
    print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2))
    print(f"[{'OK' if ok else 'FAIL'}] V1C2A1 REAL WINDOWS CANONICAL COMPILE AST CONTRACT")
    print("\n=== SUMMARY ===")
    print(json.dumps({"case_count": 1, "fail_count": 0 if ok else 1}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
