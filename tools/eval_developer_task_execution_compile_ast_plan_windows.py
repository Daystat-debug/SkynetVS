from __future__ import annotations

import hashlib
import json
import os
import tempfile

from pathlib import Path

from modules.developer.developer_task_execution_compile_ast_plan import (
    issue_developer_task_execution_compile_ast_plan,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
)
from tools.eval_developer_task_execution_workspace_snapshot import _capture, _git, _prepare


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
        result[relative] = (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
    return result


def main() -> int:
    if os.name != "nt":
        print("=== V1C1B REAL WINDOWS TYPED COMPILE AST PLAN ===")
        print(json.dumps({"skipped": True, "reason": "windows_only"}, indent=2))
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": 0, "fail_count": 0}, indent=2))
        return 0

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        fixture = _prepare(
            Path(temp_dir),
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
            task_id="v1c1b-windows-smoke",
        )
        repo, _, _, _, _, workspace, _, _ = fixture
        workspace_repo = Path(workspace.repository_root)

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

        snapshot = _capture(fixture)
        plan = issue_developer_task_execution_compile_ast_plan(snapshot)
        issued_state = plan.status().state
        report = plan.report

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

        material = plan.claim_for_compile_ast_gate()
        actual = {
            "ok": report.ok,
            "policy_fingerprint": report.policy_fingerprint,
            "operation": report.operation,
            "selected_python_files": list(report.selected_python_files),
            "deleted_python_files": list(report.deleted_python_files),
            "changed_non_python_files": list(report.changed_non_python_files),
            "selected_file_count": report.selected_file_count,
            "selected_total_bytes": report.selected_total_bytes,
            "source_manifest_fingerprint_length": len(report.source_manifest_sha256),
            "plan_fingerprint_length": len(report.plan_fingerprint),
            "snapshot_state": snapshot.status().state,
            "issued_state": issued_state,
            "claimed_state": plan.status().state,
            "exact_module_bytes": material.exact_source_bytes("module.py").decode("utf-8"),
            "only_selected_materialized": list(material.paths) == ["module.py"],
            "source_index_unchanged": source_after["index"] == source_before["index"],
            "source_status_unchanged": source_after["status"] == source_before["status"],
            "source_objects_unchanged": source_after["objects"] == source_before["objects"],
            "workspace_index_unchanged": workspace_after["index"] == workspace_before["index"],
            "workspace_status_unchanged": workspace_after["status"] == workspace_before["status"],
            "workspace_objects_unchanged": workspace_after["objects"] == workspace_before["objects"],
            "repository_mutated": report.repository_mutated,
            "network_attempted": report.network_attempted,
            "artifact_download_attempted": report.artifact_download_attempted,
            "dependency_install_attempted": report.dependency_install_attempted,
            "sandbox_launched": report.sandbox_launched,
            "runtime_lease_issued": report.runtime_lease_issued,
            "runtime_lease_claimed": report.runtime_lease_claimed,
            "candidate_interpreter_executed": report.candidate_interpreter_executed,
            "changed_code_executed": report.changed_code_executed,
            "reusable_lease_issued": report.reusable_lease_issued,
            "execution_authorized": report.execution_authorized,
        }
        expected = {
            "ok": True,
            "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
            "operation": "compile_ast_changed_python_v1",
            "selected_python_files": ["module.py"],
            "deleted_python_files": ["delete.py"],
            "changed_non_python_files": ["notes.txt"],
            "selected_file_count": 1,
            "selected_total_bytes": len(b"value = 2\n"),
            "source_manifest_fingerprint_length": 64,
            "plan_fingerprint_length": 64,
            "snapshot_state": "claimed_for_plan",
            "issued_state": "issued",
            "claimed_state": "claimed_for_compile_ast_gate",
            "exact_module_bytes": "value = 2\n",
            "only_selected_materialized": True,
            "source_index_unchanged": True,
            "source_status_unchanged": True,
            "source_objects_unchanged": True,
            "workspace_index_unchanged": True,
            "workspace_status_unchanged": True,
            "workspace_objects_unchanged": True,
            "repository_mutated": False,
            "network_attempted": False,
            "artifact_download_attempted": False,
            "dependency_install_attempted": False,
            "sandbox_launched": False,
            "runtime_lease_issued": False,
            "runtime_lease_claimed": False,
            "candidate_interpreter_executed": False,
            "changed_code_executed": False,
            "reusable_lease_issued": False,
            "execution_authorized": False,
        }
        ok = actual == expected
        print("=== V1C1B REAL WINDOWS TYPED COMPILE AST PLAN ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2))
        print("[OK] V1C1B REAL WINDOWS TYPED COMPILE AST PLAN" if ok else "[FAIL] V1C1B REAL WINDOWS TYPED COMPILE AST PLAN")
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": 1, "fail_count": 0 if ok else 1}, indent=2))
        return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
