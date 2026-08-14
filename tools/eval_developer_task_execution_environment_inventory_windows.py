from __future__ import annotations

import json
import subprocess
import sys

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_environment_inventory import (
    inventory_developer_task_execution_environment,
)
from modules.developer.developer_task_execution_environment_inventory_policy import (
    DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_preflight import DeveloperTaskRepositoryPreflightReport


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def main() -> int:
    if sys.platform != "win32":
        print("[SKIP] V1C0A Windows host-only inventory smoke requires Windows.")
        return 0

    head = _git("rev-parse", "--verify", "HEAD^{commit}").casefold()
    repository_root = Path(_git("rev-parse", "--show-toplevel")).resolve(strict=True)
    report = DeveloperTaskRepositoryPreflightReport(
        manifest_fingerprint="0" * 64,
        project_root=str(repository_root),
        repository_root=str(repository_root),
        head_commit=head,
        resolved_base_commit=head,
        dirty_categories=(),
        issues=(),
    )
    inventory = inventory_developer_task_execution_environment(report, project_root=repository_root)
    payload = inventory.to_dict()
    dependency_paths = [item.path for item in inventory.dependency_files]
    check_steps = [item for item in inventory.pipeline_steps if item.flow == "check"]

    actual = {
        "ok": inventory.ok,
        "issue_codes": list(inventory.issue_codes),
        "head_matches": inventory.head_commit == head,
        "policy_fingerprint": inventory.policy_fingerprint,
        "tracked_file_count": inventory.tracked_file_count,
        "tracked_python_file_count": inventory.tracked_python_file_count,
        "requirements_txt": "requirements.txt" in dependency_paths,
        "requirements_train_txt": "requirements-train.txt" in dependency_paths,
        "requirements_whisper_txt": "requirements-whisper.txt" in dependency_paths,
        "pipeline_flow_count": inventory.pipeline_flow_count,
        "pipeline_check_step_count": len(check_steps),
        "process_call_count": len(inventory.process_calls),
        "host_sensitive_file_count": len(inventory.host_sensitive_files),
        "inventory_fingerprint_length": len(inventory.inventory_fingerprint),
        "sandbox_launched": inventory.sandbox_launched,
        "candidate_interpreter_executed": inventory.candidate_interpreter_executed,
        "dependency_install_attempted": inventory.dependency_install_attempted,
        "reusable_lease_issued": inventory.reusable_lease_issued,
        "execution_authorized": inventory.execution_authorized,
    }
    expected = {
        "ok": True,
        "issue_codes": [],
        "head_matches": True,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_FINGERPRINT,
        "tracked_file_count_min": 244,
        "tracked_python_file_count_min": 226,
        "requirements_txt": True,
        "requirements_train_txt": True,
        "requirements_whisper_txt": True,
        "pipeline_flow_count_min": 89,
        "pipeline_check_step_count_min": 84,
        "process_call_count_min": 32,
        "host_sensitive_file_count_min": 1,
        "inventory_fingerprint_length": 64,
        "sandbox_launched": False,
        "candidate_interpreter_executed": False,
        "dependency_install_attempted": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    ok = (
        actual["ok"] is True
        and actual["issue_codes"] == []
        and actual["head_matches"] is True
        and actual["policy_fingerprint"] == expected["policy_fingerprint"]
        and actual["tracked_file_count"] >= expected["tracked_file_count_min"]
        and actual["tracked_python_file_count"] >= expected["tracked_python_file_count_min"]
        and actual["requirements_txt"] is True
        and actual["requirements_train_txt"] is True
        and actual["requirements_whisper_txt"] is True
        and actual["pipeline_flow_count"] >= expected["pipeline_flow_count_min"]
        and actual["pipeline_check_step_count"] >= expected["pipeline_check_step_count_min"]
        and actual["process_call_count"] >= expected["process_call_count_min"]
        and actual["host_sensitive_file_count"] >= expected["host_sensitive_file_count_min"]
        and actual["inventory_fingerprint_length"] == 64
        and actual["sandbox_launched"] is False
        and actual["candidate_interpreter_executed"] is False
        and actual["dependency_install_attempted"] is False
        and actual["reusable_lease_issued"] is False
        and actual["execution_authorized"] is False
    )

    print("=== V1C0A REAL WINDOWS COMMIT-TREE EXECUTION ENVIRONMENT INVENTORY ===")
    print(json.dumps({"actual": actual, "expected": expected, "inventory": payload, "ok": ok}, ensure_ascii=False, indent=2))
    if ok:
        print("[OK] V1C0A REAL WINDOWS COMMIT-TREE EXECUTION ENVIRONMENT INVENTORY")
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": 1, "fail_count": 0}, indent=2))
        return 0

    print("[FAIL] V1C0A REAL WINDOWS COMMIT-TREE EXECUTION ENVIRONMENT INVENTORY")
    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": 1, "fail_count": 1}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
