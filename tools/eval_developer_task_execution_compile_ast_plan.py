from __future__ import annotations

import copy
import hashlib
import inspect
import json
import pickle
import tempfile

from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_execution_compile_ast_plan as plan_module

from modules.developer.developer_task_execution_compile_ast_plan import (
    COMPILE_AST_PLAN_STATE_CLAIMED_FOR_GATE,
    COMPILE_AST_PLAN_STATE_EXPIRED,
    COMPILE_AST_PLAN_STATE_INVALIDATED,
    DeveloperTaskExecutionCompileAstPlanError,
    issue_developer_task_execution_compile_ast_plan,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
    developer_task_execution_compile_ast_plan_policy_fingerprint,
    validate_developer_task_execution_compile_ast_plan_policy,
)
from modules.developer.developer_task_execution_workspace_snapshot import (
    DeveloperTaskExecutionWorkspaceSnapshotEntry,
    DeveloperTaskExecutionWorkspaceSnapshotMaterial,
)
from tools.eval_developer_task_execution_workspace_snapshot import _capture, _prepare


def _error_code(callback) -> str:
    try:
        callback()
    except DeveloperTaskExecutionCompileAstPlanError as exc:
        return exc.code
    return ""


def _raises_type_error(callback) -> bool:
    try:
        callback()
    except TypeError:
        return True
    return False


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        print()
        print(f"=== {name} ===")
        print(json.dumps(
            {"actual": actual, "expected": expected, "ok": ok},
            ensure_ascii=False,
            indent=2,
            default=str,
        ))
        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    suite_temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    suite_root = Path(suite_temp.name)
    try:
        standard_fixture = _prepare(
            suite_root / "standard",
            baseline={
                "module.py": b"value = 1\n",
                "deleted.py": b"old = 1\n",
                "notes.txt": b"old\n",
                "keep.py": b"unchanged = True\n",
            },
            changes={
                "module.py": b"value = 2\n",
                "deleted.py": None,
                "notes.txt": b"new\n",
            },
            task_id="v1c1b-standard-fixture",
        )
        two_python_fixture = _prepare(
            suite_root / "two-python",
            baseline={"a.py": b"x=1\n", "b.py": b"y=1\n"},
            changes={"a.py": b"x=22\n", "b.py": b"y=22\n"},
            task_id="v1c1b-two-python-fixture",
        )
        no_python_fixture = _prepare(
            suite_root / "no-python",
            baseline={"notes.txt": b"old\n"},
            changes={"notes.txt": b"new\n"},
            task_id="v1c1b-no-python-fixture",
        )
        deleted_only_fixture = _prepare(
            suite_root / "deleted-only",
            baseline={"gone.py": b"old = 1\n", "keep.txt": b"x\n"},
            changes={"gone.py": None},
            task_id="v1c1b-deleted-only-fixture",
        )

        def standard_snapshot():
            return _capture(standard_fixture)

        def two_python_snapshot():
            return _capture(two_python_fixture)

        check(
            "V1C1B PINNED COMPILE AST PLAN POLICY SELF CHECKS",
            {
                "errors": list(validate_developer_task_execution_compile_ast_plan_policy()),
                "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.policy_id,
                "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.operation,
                "fingerprint": developer_task_execution_compile_ast_plan_policy_fingerprint(),
                "expected_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
                "network": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.network_allowed,
                "runtime_lease_input": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.runtime_lease_input,
                "authorized": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.execution_authorized,
            },
            {
                "errors": [],
                "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
                "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
                "fingerprint": "f017f401254647002347802c5deba6397bdddf27eaa08d02640dc8389fe80865",
                "expected_fingerprint": "f017f401254647002347802c5deba6397bdddf27eaa08d02640dc8389fe80865",
                "network": False,
                "runtime_lease_input": False,
                "authorized": False,
            },
        )

        signature = inspect.signature(issue_developer_task_execution_compile_ast_plan)
        check(
            "V1C1B PUBLIC API ACCEPTS ONLY ONE TYPED SNAPSHOT",
            {
                name: {
                    "kind": parameter.kind.name,
                    "default": None if parameter.default is inspect.Parameter.empty else parameter.default,
                }
                for name, parameter in signature.parameters.items()
            },
            {"snapshot": {"kind": "POSITIONAL_OR_KEYWORD", "default": None}},
        )

        snapshot = standard_snapshot()
        plan = issue_developer_task_execution_compile_ast_plan(snapshot)
        report = plan.report
        check(
            "V1C1B VERIFIED PATCH FACTS DERIVE NON AUTHORIZING PLAN",
            {
                "ok": report.ok,
                "operation": report.operation,
                "selected": list(report.selected_python_files),
                "deleted_python": list(report.deleted_python_files),
                "non_python": list(report.changed_non_python_files),
                "selected_count": report.selected_file_count,
                "selected_bytes": report.selected_total_bytes,
                "snapshot_state": snapshot.status().state,
                "plan_state": plan.status().state,
                "snapshot_consumed": report.snapshot_consumed,
                "network": report.network_attempted,
                "sandbox": report.sandbox_launched,
                "lease_issued": report.runtime_lease_issued,
                "lease_claimed": report.runtime_lease_claimed,
                "candidate": report.candidate_interpreter_executed,
                "changed_exec": report.changed_code_executed,
                "authorized": report.execution_authorized,
            },
            {
                "ok": True,
                "operation": "compile_ast_changed_python_v1",
                "selected": ["module.py"],
                "deleted_python": ["deleted.py"],
                "non_python": ["notes.txt"],
                "selected_count": 1,
                "selected_bytes": len(b"value = 2\n"),
                "snapshot_state": "claimed_for_plan",
                "plan_state": "issued",
                "snapshot_consumed": True,
                "network": False,
                "sandbox": False,
                "lease_issued": False,
                "lease_claimed": False,
                "candidate": False,
                "changed_exec": False,
                "authorized": False,
            },
        )

        serialized = json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True)
        check(
            "V1C1B DURABLE REPORT EXPOSES HASHES BUT NO SOURCE BYTES OR HOST PATHS",
            {
                "json": bool(serialized),
                "source_bytes_absent": "value = 2" not in serialized,
                "source_root_absent": str(suite_root) not in serialized,
                "source_sha_present": report.sources[0].sha256 in serialized,
                "plan_sha_present": report.plan_fingerprint in serialized,
            },
            {
                "json": True,
                "source_bytes_absent": True,
                "source_root_absent": True,
                "source_sha_present": True,
                "plan_sha_present": True,
            },
        )
        check(
            "V1C1B REPORT AND SOURCE IDENTITIES ARE IMMUTABLE",
            {
                "report": _raises_frozen(lambda: setattr(report, "operation", "other")),
                "source": _raises_frozen(lambda: setattr(report.sources[0], "path", "other.py")),
            },
            {"report": True, "source": True},
        )
        check(
            "V1C1B PLAN CAPABILITY IS NON COPYABLE AND NON SERIALIZABLE",
            {
                "copy": _raises_type_error(lambda: copy.copy(plan)),
                "deepcopy": _raises_type_error(lambda: copy.deepcopy(plan)),
                "pickle": _raises_type_error(lambda: pickle.dumps(plan)),
            },
            {"copy": True, "deepcopy": True, "pickle": True},
        )
        material = plan.claim_for_compile_ast_gate()
        check(
            "V1C1B SINGLE CLAIM RETURNS ONLY SELECTED EXACT SOURCE BYTES",
            {
                "state": plan.status().state,
                "paths": list(material.paths),
                "operation": material.operation,
                "module": material.exact_source_bytes("module.py").decode("utf-8"),
                "deleted_absent": "deleted.py" not in material.paths,
                "non_python_absent": "notes.txt" not in material.paths,
            },
            {
                "state": COMPILE_AST_PLAN_STATE_CLAIMED_FOR_GATE,
                "paths": ["module.py"],
                "operation": "compile_ast_changed_python_v1",
                "module": "value = 2\n",
                "deleted_absent": True,
                "non_python_absent": True,
            },
        )
        check(
            "V1C1B CLAIMED MATERIAL IS NON COPYABLE AND NON SERIALIZABLE",
            {
                "copy": _raises_type_error(lambda: copy.copy(material)),
                "deepcopy": _raises_type_error(lambda: copy.deepcopy(material)),
                "pickle": _raises_type_error(lambda: pickle.dumps(material)),
            },
            {"copy": True, "deepcopy": True, "pickle": True},
        )
        check(
            "V1C1B CLAIM REPLAY FAILS CLOSED",
            _error_code(plan.claim_for_compile_ast_gate),
            "compile_ast_plan_already_claimed",
        )

        first = issue_developer_task_execution_compile_ast_plan(standard_snapshot())
        second = issue_developer_task_execution_compile_ast_plan(standard_snapshot())
        check(
            "V1C1B REPEATED EXACT SNAPSHOT PLAN IS DETERMINISTIC",
            {
                "same_sources": [item.to_dict() for item in first.report.sources] == [item.to_dict() for item in second.report.sources],
                "same_source_manifest": first.report.source_manifest_sha256 == second.report.source_manifest_sha256,
                "same_plan": first.report.plan_fingerprint == second.report.plan_fingerprint,
            },
            {"same_sources": True, "same_source_manifest": True, "same_plan": True},
        )

        plan = issue_developer_task_execution_compile_ast_plan(standard_snapshot())
        state = plan_module._REGISTRY[plan]
        with state.lock:
            state.expires_at_ns = 0
        check("V1C1B EXPIRED CAPABILITY BECOMES TERMINAL", plan.status().state, COMPILE_AST_PLAN_STATE_EXPIRED)
        check("V1C1B EXPIRED CAPABILITY CANNOT BE CLAIMED", _error_code(plan.claim_for_compile_ast_gate), "compile_ast_plan_expired")

        plan = issue_developer_task_execution_compile_ast_plan(standard_snapshot())
        with patch.object(plan_module, "_SERVICES", replace(plan_module._SERVICES, monotonic_ns=lambda: -1)):
            check("V1C1B INVALID CLOCK INVALIDATES CAPABILITY", plan.status().state, COMPILE_AST_PLAN_STATE_INVALIDATED)

        check("V1C1B RAW PUBLIC INPUT TYPE IS REJECTED", _raises_type_error(lambda: issue_developer_task_execution_compile_ast_plan({})), True)

        snapshot = _capture(no_python_fixture)
        check(
            "V1C1B NON PYTHON CHANGE ISSUES NO COMPILE AST CAPABILITY",
            _error_code(lambda: issue_developer_task_execution_compile_ast_plan(snapshot)),
            "compile_ast_plan_no_changed_python",
        )
        check("V1C1B FAILED NO PYTHON ISSUANCE STILL CONSUMES SNAPSHOT", snapshot.status().state, "claimed_for_plan")

        snapshot = _capture(deleted_only_fixture)
        check(
            "V1C1B DELETED ONLY PYTHON CHANGE ISSUES NO CAPABILITY",
            _error_code(lambda: issue_developer_task_execution_compile_ast_plan(snapshot)),
            "compile_ast_plan_no_changed_python",
        )

        original_entry = DeveloperTaskExecutionWorkspaceSnapshotMaterial.entry
        original_bytes = DeveloperTaskExecutionWorkspaceSnapshotMaterial.exact_file_bytes
        for name, payload, code in (
            ("V1C1B STRICT UTF8 RECHECK REJECTS INVALID SOURCE", b"value = \xff\n", "compile_ast_plan_encoding_rejected"),
            ("V1C1B NUL SOURCE RECHECK FAILS CLOSED", b"value = 1\x00\n", "compile_ast_plan_nul_rejected"),
            ("V1C1B CRLF SOURCE RECHECK FAILS CLOSED", b"value = 2\r\n", "compile_ast_plan_line_endings_rejected"),
        ):
            snapshot = standard_snapshot()

            def forged_entry(self, path: str, *, _payload=payload):
                item = original_entry(self, path)
                if path == "module.py":
                    return DeveloperTaskExecutionWorkspaceSnapshotEntry(
                        path=item.path,
                        mode=item.mode,
                        object_id=item.object_id,
                        size_bytes=len(_payload),
                        sha256=hashlib.sha256(_payload).hexdigest(),
                    )
                return item

            def forged_bytes(self, path: str, *, _payload=payload):
                if path == "module.py":
                    return _payload
                return original_bytes(self, path)

            with patch.object(DeveloperTaskExecutionWorkspaceSnapshotMaterial, "entry", forged_entry), patch.object(DeveloperTaskExecutionWorkspaceSnapshotMaterial, "exact_file_bytes", forged_bytes):
                check(name, _error_code(lambda: issue_developer_task_execution_compile_ast_plan(snapshot)), code)

        snapshot = standard_snapshot()
        with patch.object(DeveloperTaskExecutionWorkspaceSnapshotMaterial, "exact_file_bytes", lambda self, path: b"tampered\n" if path == "module.py" else original_bytes(self, path)):
            check(
                "V1C1B SELECTED SOURCE IDENTITY IS RECHECKED",
                _error_code(lambda: issue_developer_task_execution_compile_ast_plan(snapshot)),
                "compile_ast_plan_source_identity_mismatch",
            )

        snapshot = standard_snapshot()
        with patch.object(plan_module, "DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_BYTES", 3):
            check(
                "V1C1B PER FILE SIZE LIMIT FAILS CLOSED",
                _error_code(lambda: issue_developer_task_execution_compile_ast_plan(snapshot)),
                "compile_ast_plan_file_too_large",
            )

        snapshot = two_python_snapshot()
        with patch.object(plan_module, "DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_TOTAL_BYTES", 8):
            check(
                "V1C1B SELECTED TOTAL SIZE LIMIT FAILS CLOSED",
                _error_code(lambda: issue_developer_task_execution_compile_ast_plan(snapshot)),
                "compile_ast_plan_total_bytes_exceeded",
            )

        snapshot = two_python_snapshot()
        with patch.object(plan_module, "DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_COUNT", 1):
            check(
                "V1C1B SELECTED FILE COUNT LIMIT FAILS CLOSED",
                _error_code(lambda: issue_developer_task_execution_compile_ast_plan(snapshot)),
                "compile_ast_plan_file_count_exceeded",
            )

        snapshot = standard_snapshot()
        def bad_mode_entry(self, path: str):
            item = original_entry(self, path)
            if path == "module.py":
                return DeveloperTaskExecutionWorkspaceSnapshotEntry(
                    path=item.path,
                    mode="100755",
                    object_id=item.object_id,
                    size_bytes=item.size_bytes,
                    sha256=item.sha256,
                )
            return item
        with patch.object(DeveloperTaskExecutionWorkspaceSnapshotMaterial, "entry", bad_mode_entry):
            check(
                "V1C1B SELECTED SOURCE MODE IS RECHECKED",
                _error_code(lambda: issue_developer_task_execution_compile_ast_plan(snapshot)),
                "compile_ast_plan_mode_rejected",
            )

        snapshot = standard_snapshot()
        with patch.object(plan_module, "_SERVICES", replace(plan_module._SERVICES, token_bytes=lambda _: b"short")):
            check(
                "V1C1B INVALID SECRET GENERATOR FAILS CLOSED",
                _error_code(lambda: issue_developer_task_execution_compile_ast_plan(snapshot)),
                "compile_ast_plan_secret_generation_failed",
            )
        check("V1C1B SECRET FAILURE CONSUMES SNAPSHOT", snapshot.status().state, "claimed_for_plan")

        plan = issue_developer_task_execution_compile_ast_plan(standard_snapshot())
        state = plan_module._REGISTRY[plan]
        assert state.exact_sources is not None
        state.exact_sources["module.py"] = b"tampered\n"
        check("V1C1B PRIVATE SOURCE MUTATION BEFORE CLAIM FAILS CLOSED", _error_code(plan.claim_for_compile_ast_gate), "compile_ast_plan_material_invalid")
        check("V1C1B MATERIAL MUTATION INVALIDATES CAPABILITY", plan.status().state, COMPILE_AST_PLAN_STATE_INVALIDATED)

        plan = issue_developer_task_execution_compile_ast_plan(standard_snapshot())
        plan._guard = b"0" * 32
        check("V1C1B ISSUER GUARD TAMPER FAILS CLOSED", _error_code(plan.claim_for_compile_ast_gate), "compile_ast_plan_issuer_binding_invalid")

        plan = issue_developer_task_execution_compile_ast_plan(standard_snapshot())
        with patch.object(plan_module, "validate_developer_task_execution_compile_ast_plan_policy", return_value=("forced",)):
            check("V1C1B POLICY CHANGE BEFORE CLAIM FAILS CLOSED", _error_code(plan.claim_for_compile_ast_gate), "compile_ast_plan_policy_invalid")
        check("V1C1B POLICY CHANGE INVALIDATES CAPABILITY", plan.status().state, COMPILE_AST_PLAN_STATE_INVALIDATED)

        mutated_policy = replace(DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY, max_selected_file_count=19)
        check(
            "V1C1B POLICY MUTATION INVALIDATES FINGERPRINT",
            {
                "fingerprint_changed": developer_task_execution_compile_ast_plan_policy_fingerprint(mutated_policy) != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
                "errors": list(validate_developer_task_execution_compile_ast_plan_policy(mutated_policy)),
            },
            {
                "fingerprint_changed": True,
                "errors": ["policy_limits_invalid", "policy_fingerprint_mismatch"],
            },
        )

        source_text = Path(plan_module.__file__).read_text(encoding="utf-8")
        forbidden = (
            "WindowsSandbox.exe",
            "python.exe",
            "subprocess",
            "importlib",
            "runpy",
            "ast.parse",
            "compile(",
            "exec(",
            "eval(",
            "pip install",
            "files.pythonhosted.org",
            "pypi.org",
            "urllib.request",
            "requests.get",
            "shell=True",
            "os.system(",
        )
        check(
            "V1C1B PRODUCTION PLAN HAS NO SANDBOX PYTHON PARSE COMPILE IMPORT NETWORK OR SHELL SURFACE",
            {token: token in source_text for token in forbidden},
            {token: False for token in forbidden},
        )

        check(
            "V1C1B POLICY LOCKS PROCESS LOCAL SINGLE USE NON AUTHORIZING CAPABILITY",
            {
                "process_local": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.process_local,
                "single_use": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.single_use,
                "private_bytes": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.private_selected_exact_bytes,
                "runtime_lease_input_false": not DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.runtime_lease_input,
                "caller_paths_false": not DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.caller_controlled_paths,
                "network_false": not DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.network_allowed,
                "execution_false": not DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.execution_authorized,
                "ttl_300": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.ttl_seconds == 300,
                "secret_32": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY.secret_bytes == 32,
            },
            {
                "process_local": True,
                "single_use": True,
                "private_bytes": True,
                "runtime_lease_input_false": True,
                "caller_paths_false": True,
                "network_false": True,
                "execution_false": True,
                "ttl_300": True,
                "secret_32": True,
            },
        )

    finally:
        suite_temp.cleanup()

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, indent=2))
    return 0 if fail_count == 0 else 1


def _raises_frozen(callback) -> bool:
    try:
        callback()
    except Exception as exc:
        return exc.__class__.__name__ == "FrozenInstanceError"
    return False


if __name__ == "__main__":
    raise SystemExit(main())
