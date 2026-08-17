from __future__ import annotations

import hashlib
import json
import os
import tempfile

from pathlib import Path

from modules.developer.developer_task_execution_backend_host import (
    inspect_developer_task_execution_backend_host,
)
from modules.developer.developer_task_execution_compile_ast_claim_transaction import (
    COMPILE_AST_CLAIM_TRANSACTION_STATE_CLAIMED,
    COMPILE_AST_CLAIM_TRANSACTION_STATE_ISSUED,
    issue_developer_task_execution_compile_ast_claim_transaction,
)
from modules.developer.developer_task_execution_compile_ast_claim_transaction_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_compile_ast_plan import (
    COMPILE_AST_PLAN_STATE_CLAIMED_FOR_GATE,
    COMPILE_AST_PLAN_STATE_ISSUED,
    issue_developer_task_execution_compile_ast_plan,
)
from modules.developer.developer_task_execution_runtime_bundle import (
    build_developer_task_execution_runtime_bundle,
)
from modules.developer.developer_task_execution_runtime_lease import (
    LEASE_STATE_CLAIMED,
    LEASE_STATE_ISSUED,
    issue_developer_task_execution_runtime_lease,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_SOURCE_FILE_NAME,
)
from tools.eval_developer_task_execution_workspace_snapshot import _capture, _git, _prepare


def _runtime_zip_path() -> Path:
    explicit = os.environ.get("SKYNETVS_TRUSTED_RUNTIME_ZIP", "").strip()
    if explicit:
        return Path(explicit)
    return (
        Path.home()
        / "Downloads"
        / "SkynetVS_V1B4A_Runtime_Source_3_13_15"
        / RUNTIME_SOURCE_FILE_NAME
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_bytes(root: Path, *args: str) -> bytes:
    return bytes(_git(root, *args, binary=True).stdout)


def _index_path(root: Path) -> Path:
    raw = _git(root, "rev-parse", "--git-path", "index").stdout.strip()
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _object_snapshot(root: Path) -> dict[str, tuple[int, str]]:
    git_dir = Path(_git(root, "rev-parse", "--absolute-git-dir").stdout.strip())
    objects = git_dir / "objects"
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(objects.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(objects).as_posix()
        result[relative] = (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    return result


def main() -> int:
    if os.name != "nt":
        print("=== V1C2C0 REAL WINDOWS PLAN RUNTIME CLAIM TRANSACTION ===")
        print(json.dumps({"skipped": True, "reason": "windows_only"}, indent=2))
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": 0, "fail_count": 0}, indent=2))
        return 0

    runtime_zip = _runtime_zip_path()
    host_before = inspect_developer_task_execution_backend_host()
    prerequisites_ok = (
        host_before.ok
        and not host_before.running_sandbox_processes
        and runtime_zip.is_file()
        and runtime_zip.name == RUNTIME_SOURCE_FILE_NAME
    )
    if not prerequisites_ok:
        actual = {
            "host_ok": host_before.ok,
            "issue_codes": list(host_before.issue_codes),
            "running_processes": list(host_before.running_sandbox_processes),
            "runtime_name": runtime_zip.name,
            "runtime_exists": runtime_zip.is_file(),
        }
        expected = {
            "host_ok": True,
            "issue_codes": [],
            "running_processes": [],
            "runtime_name": RUNTIME_SOURCE_FILE_NAME,
            "runtime_exists": True,
        }
        print("=== V1C2C0 REAL WINDOWS PLAN RUNTIME CLAIM TRANSACTION ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": False}, ensure_ascii=False, indent=2))
        print("[FAIL] V1C2C0 REAL WINDOWS PLAN RUNTIME CLAIM TRANSACTION")
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": 1, "fail_count": 1}, indent=2))
        return 1

    with tempfile.TemporaryDirectory(
        prefix="skynetvs-v1c2c0-windows-",
        ignore_cleanup_errors=True,
    ) as temp_dir:
        root = Path(temp_dir)
        fixture = _prepare(
            root / "plan-fixture",
            baseline={
                "module.py": b"value = 1\n",
                "delete.py": b"delete = True\n",
                "notes.txt": b"old\n",
                "keep.py": b"keep = True\n",
            },
            changes={
                "module.py": b"value = 2\n",
                "delete.py": None,
                "notes.txt": b"new\n",
            },
            task_id="v1c2c0-windows-smoke",
        )
        repo, _, _, _, _, workspace, _, _ = fixture
        workspace_repo = Path(workspace.repository_root)

        snapshot = _capture(fixture)
        plan = issue_developer_task_execution_compile_ast_plan(snapshot)

        artifact_parent = root / "runtime-artifacts"
        artifact_parent.mkdir()
        bundle = build_developer_task_execution_runtime_bundle(
            runtime_zip,
            artifact_parent=artifact_parent,
        )
        lease = issue_developer_task_execution_runtime_lease(host_before, bundle)

        source_index = _index_path(repo)
        workspace_index = _index_path(workspace_repo)
        source_before = {
            "index": _sha256_file(source_index),
            "status": _git_bytes(repo, "status", "--porcelain=v2", "-z"),
            "objects": _object_snapshot(repo),
        }
        workspace_before = {
            "index": _sha256_file(workspace_index),
            "status": _git_bytes(workspace_repo, "status", "--porcelain=v2", "-z"),
            "objects": _object_snapshot(workspace_repo),
        }

        transaction = issue_developer_task_execution_compile_ast_claim_transaction(
            plan,
            lease,
        )
        issued_state = transaction.status().state
        plan_state_before_claim = plan.status().state
        lease_state_before_claim = lease.status().state
        report = transaction.report

        material = transaction.claim()
        host_after = inspect_developer_task_execution_backend_host()

        source_after = {
            "index": _sha256_file(source_index),
            "status": _git_bytes(repo, "status", "--porcelain=v2", "-z"),
            "objects": _object_snapshot(repo),
        }
        workspace_after = {
            "index": _sha256_file(workspace_index),
            "status": _git_bytes(workspace_repo, "status", "--porcelain=v2", "-z"),
            "objects": _object_snapshot(workspace_repo),
        }

        actual = {
            "ok": report.ok,
            "policy_fingerprint": report.policy_fingerprint,
            "operation": report.operation,
            "runtime_lease_fingerprint_length": len(report.runtime_lease_fingerprint),
            "runtime_bundle_fingerprint": report.runtime_bundle_fingerprint,
            "issued_state": issued_state,
            "plan_state_before_claim": plan_state_before_claim,
            "lease_state_before_claim": lease_state_before_claim,
            "claimed_state": transaction.status().state,
            "plan_state_after_claim": plan.status().state,
            "lease_state_after_claim": lease.status().state,
            "same_plan_report": material.plan_material.report is plan.report,
            "exact_module_bytes": material.plan_material.exact_source_bytes("module.py").decode("utf-8"),
            "only_selected_materialized": list(material.plan_material.paths) == ["module.py"],
            "same_runtime_bundle": material.runtime_bundle is bundle,
            "same_runtime_lease_fingerprint": (
                material.runtime_lease_fingerprint
                == report.runtime_lease_fingerprint
            ),
            "source_index_unchanged": source_after["index"] == source_before["index"],
            "source_status_unchanged": source_after["status"] == source_before["status"],
            "source_objects_unchanged": source_after["objects"] == source_before["objects"],
            "workspace_index_unchanged": workspace_after["index"] == workspace_before["index"],
            "workspace_status_unchanged": workspace_after["status"] == workspace_before["status"],
            "workspace_objects_unchanged": workspace_after["objects"] == workspace_before["objects"],
            "host_ok_after": host_after.ok,
            "host_issue_codes_after": list(host_after.issue_codes),
            "running_processes_after": list(host_after.running_sandbox_processes),
            "artifact_parent_empty": list(artifact_parent.iterdir()) == [],
            "repository_mutated": report.repository_mutated,
            "network_attempted": report.network_attempted,
            "artifact_download_attempted": report.artifact_download_attempted,
            "dependency_install_attempted": report.dependency_install_attempted,
            "sandbox_launched": report.sandbox_launched,
            "candidate_interpreter_executed": report.candidate_interpreter_executed,
            "changed_source_processed": report.changed_source_processed,
            "changed_code_executed": report.changed_code_executed,
            "reusable_lease_issued": report.reusable_lease_issued,
            "execution_authorized": report.execution_authorized,
        }
        expected = {
            "ok": True,
            "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
            "operation": "compile_ast_changed_python_v1",
            "runtime_lease_fingerprint_length": 64,
            "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
            "issued_state": COMPILE_AST_CLAIM_TRANSACTION_STATE_ISSUED,
            "plan_state_before_claim": COMPILE_AST_PLAN_STATE_ISSUED,
            "lease_state_before_claim": LEASE_STATE_ISSUED,
            "claimed_state": COMPILE_AST_CLAIM_TRANSACTION_STATE_CLAIMED,
            "plan_state_after_claim": COMPILE_AST_PLAN_STATE_CLAIMED_FOR_GATE,
            "lease_state_after_claim": LEASE_STATE_CLAIMED,
            "same_plan_report": True,
            "exact_module_bytes": "value = 2\n",
            "only_selected_materialized": True,
            "same_runtime_bundle": True,
            "same_runtime_lease_fingerprint": True,
            "source_index_unchanged": True,
            "source_status_unchanged": True,
            "source_objects_unchanged": True,
            "workspace_index_unchanged": True,
            "workspace_status_unchanged": True,
            "workspace_objects_unchanged": True,
            "host_ok_after": True,
            "host_issue_codes_after": [],
            "running_processes_after": [],
            "artifact_parent_empty": True,
            "repository_mutated": False,
            "network_attempted": False,
            "artifact_download_attempted": False,
            "dependency_install_attempted": False,
            "sandbox_launched": False,
            "candidate_interpreter_executed": False,
            "changed_source_processed": False,
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
        }
        ok = actual == expected

    print("=== V1C2C0 REAL WINDOWS PLAN RUNTIME CLAIM TRANSACTION ===")
    print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2))
    print("[OK] V1C2C0 REAL WINDOWS PLAN RUNTIME CLAIM TRANSACTION" if ok else "[FAIL] V1C2C0 REAL WINDOWS PLAN RUNTIME CLAIM TRANSACTION")
    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": 1, "fail_count": 0 if ok else 1}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
