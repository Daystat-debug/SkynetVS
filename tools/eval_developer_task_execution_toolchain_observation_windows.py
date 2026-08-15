from __future__ import annotations

import json
import subprocess
import sys

from pathlib import Path

from modules.developer.developer_task_execution_environment_inventory import (
    inventory_developer_task_execution_environment,
)
from modules.developer.developer_task_execution_toolchain_observation import (
    observe_developer_task_execution_host_toolchain,
)
from modules.developer.developer_task_execution_toolchain_observation_policy import (
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_preflight import DeveloperTaskRepositoryPreflightReport


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_CONTEXT_PYTHON_VERSION = "3.12.10"
EXPECTED_CONTEXT_PYTHON_SHA256 = "0b471133e110cfb53a061cad528ce8e517d7b9ac41a0a396c39ad795a487fc14"
EXPECTED_CONTEXT_PIP_VERSION = "25.3"
EXPECTED_CONTEXT_DISTRIBUTION_COUNT = 61
EXPECTED_CONTEXT_GIT_VERSION = "2.45.1.windows.1"
EXPECTED_CONTEXT_GIT_EXE_SHA256 = "4ab2b391de7fb5eb3afb34b5bd19ee7f71d0450bf7e4c207b201a0392e3825ae"
EXPECTED_CONTEXT_GIT_TREE_FILES = 6356
EXPECTED_CONTEXT_GIT_TREE_BYTES = 419125157
EXPECTED_CONTEXT_GIT_TREE_CANONICAL_SHA256 = "41f001b961349b0e0e2e89b2843671a2052d176c3472de83c447919058c082d6"
EXPECTED_CONTEXT_POWERSHELL_EDITION = "Desktop"
EXPECTED_CONTEXT_POWERSHELL_VERSION = "5.1.26100.9168"
EXPECTED_CONTEXT_POWERSHELL_SHA256 = "7600ffe12da441fe89d035b13801e8e91d064bc544a27b19a5cf49f6ab8b18f5"
EXPECTED_REQUIREMENT_SHA256 = {
    "requirements-train.txt": "65052d0da1b23c12505497325e0064568dcd9c25b368e1cfe1e5be5a12b81ced",
    "requirements-whisper.txt": "c5bc4d0891d158b7e8ec5c26b6b68dfcb0b60e8414c9f1ba3040993ea390129d",
    "requirements.txt": "9e283f2050b97e229b4600ca2b1339184b96d1cebc8f90730547a4fb790142b4",
}


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
        print("[SKIP] V1C0B1 Windows host toolchain observation smoke requires Windows.")
        return 0

    head = _git("rev-parse", "--verify", "HEAD^{commit}").casefold()
    repository_root = Path(_git("rev-parse", "--show-toplevel")).resolve(strict=True)
    repository_report = DeveloperTaskRepositoryPreflightReport(
        manifest_fingerprint="0" * 64,
        project_root=str(repository_root),
        repository_root=str(repository_root),
        head_commit=head,
        resolved_base_commit=head,
        dirty_categories=(),
        issues=(),
    )
    inventory = inventory_developer_task_execution_environment(repository_report, project_root=repository_root)
    report = observe_developer_task_execution_host_toolchain(inventory, project_root=repository_root)

    requirement_hashes = {item.path: item.sha256 for item in report.requirement_files}
    requirement_entries = [entry for file_item in report.requirement_files for entry in file_item.entries]
    unique_declared = {entry.normalized_name for entry in requirement_entries}
    installed = (
        {item.normalized_name for item in report.host_python.distributions}
        if report.host_python is not None
        else set()
    )
    mapped_distribution_roots = [item for item in report.import_distributions if item.category == "distribution"]

    actual = {
        "ok": report.ok,
        "issue_codes": list(report.issue_codes),
        "head_matches": report.head_commit == head,
        "policy_fingerprint": report.policy_fingerprint,
        "inventory_fingerprint_matches": report.inventory_fingerprint == inventory.inventory_fingerprint,
        "requirement_hashes": requirement_hashes,
        "requirement_entry_count": len(requirement_entries),
        "exact_pin_count": sum(1 for item in requirement_entries if item.exact_pin),
        "unique_declared_distribution_count": len(unique_declared),
        "installed_declared_distribution_count": len(unique_declared.intersection(installed)),
        "mapped_distribution_import_root_count": len(mapped_distribution_roots),
        "python_version": None if report.host_python is None else report.host_python.version,
        "python_sha256": None if report.host_python is None else report.host_python.executable_sha256,
        "python_venv_active": None if report.host_python is None else report.host_python.venv_active,
        "pip_version": None if report.host_python is None else report.host_python.pip_version,
        "distribution_count": None if report.host_python is None else report.host_python.distribution_count,
        "git_version": None if report.host_git is None else report.host_git.version,
        "git_executable_sha256": None if report.host_git is None else report.host_git.executable_sha256,
        "git_tree_file_count": None if report.host_git is None else report.host_git.install_tree_file_count,
        "git_tree_total_bytes": None if report.host_git is None else report.host_git.install_tree_total_bytes,
        "git_tree_manifest_sha256": None if report.host_git is None else report.host_git.install_tree_manifest_sha256,
        "git_is_authority": None if report.host_git is None else report.host_git.host_installation_is_authority,
        "powershell_edition": None if report.host_powershell is None else report.host_powershell.edition,
        "powershell_version": None if report.host_powershell is None else report.host_powershell.version,
        "powershell_sha256": None if report.host_powershell is None else report.host_powershell.executable_sha256,
        "powershell_portable_bundle_selected": None if report.host_powershell is None else report.host_powershell.portable_bundle_selected,
        "observation_fingerprint_length": len(report.observation_fingerprint),
        "source_authority_selected": report.source_authority_selected,
        "artifact_download_attempted": report.artifact_download_attempted,
        "dependency_install_attempted": report.dependency_install_attempted,
        "sandbox_launched": report.sandbox_launched,
        "candidate_interpreter_executed": report.candidate_interpreter_executed,
        "reusable_lease_issued": report.reusable_lease_issued,
        "execution_authorized": report.execution_authorized,
    }
    expected = {
        "ok": True,
        "issue_codes": [],
        "head_matches": True,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
        "inventory_fingerprint_matches": True,
        "requirement_hashes": EXPECTED_REQUIREMENT_SHA256,
        "requirement_entry_count": 15,
        "exact_pin_count": 1,
        "unique_declared_distribution_count": 12,
        "installed_declared_distribution_count": 12,
        "mapped_distribution_import_root_count_min": 11,
        "python_version": EXPECTED_CONTEXT_PYTHON_VERSION,
        "python_sha256": EXPECTED_CONTEXT_PYTHON_SHA256,
        "python_venv_active": True,
        "pip_version": EXPECTED_CONTEXT_PIP_VERSION,
        "distribution_count": EXPECTED_CONTEXT_DISTRIBUTION_COUNT,
        "git_version": EXPECTED_CONTEXT_GIT_VERSION,
        "git_executable_sha256": EXPECTED_CONTEXT_GIT_EXE_SHA256,
        "git_tree_file_count": EXPECTED_CONTEXT_GIT_TREE_FILES,
        "git_tree_total_bytes": EXPECTED_CONTEXT_GIT_TREE_BYTES,
        "git_tree_manifest_sha256": EXPECTED_CONTEXT_GIT_TREE_CANONICAL_SHA256,
        "git_is_authority": False,
        "powershell_edition": EXPECTED_CONTEXT_POWERSHELL_EDITION,
        "powershell_version": EXPECTED_CONTEXT_POWERSHELL_VERSION,
        "powershell_sha256": EXPECTED_CONTEXT_POWERSHELL_SHA256,
        "powershell_portable_bundle_selected": False,
        "observation_fingerprint_length": 64,
        "source_authority_selected": False,
        "artifact_download_attempted": False,
        "dependency_install_attempted": False,
        "sandbox_launched": False,
        "candidate_interpreter_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }
    ok = (
        actual["ok"] is True
        and actual["issue_codes"] == []
        and actual["head_matches"] is True
        and actual["policy_fingerprint"] == expected["policy_fingerprint"]
        and actual["inventory_fingerprint_matches"] is True
        and actual["requirement_hashes"] == expected["requirement_hashes"]
        and actual["requirement_entry_count"] == expected["requirement_entry_count"]
        and actual["exact_pin_count"] == expected["exact_pin_count"]
        and actual["unique_declared_distribution_count"] == expected["unique_declared_distribution_count"]
        and actual["installed_declared_distribution_count"] == expected["installed_declared_distribution_count"]
        and actual["mapped_distribution_import_root_count"] >= expected["mapped_distribution_import_root_count_min"]
        and actual["python_version"] == expected["python_version"]
        and actual["python_sha256"] == expected["python_sha256"]
        and actual["python_venv_active"] is True
        and actual["pip_version"] == expected["pip_version"]
        and actual["distribution_count"] == expected["distribution_count"]
        and actual["git_version"] == expected["git_version"]
        and actual["git_executable_sha256"] == expected["git_executable_sha256"]
        and actual["git_tree_file_count"] == expected["git_tree_file_count"]
        and actual["git_tree_total_bytes"] == expected["git_tree_total_bytes"]
        and actual["git_tree_manifest_sha256"] == expected["git_tree_manifest_sha256"]
        and actual["git_is_authority"] is False
        and actual["powershell_edition"] == expected["powershell_edition"]
        and actual["powershell_version"] == expected["powershell_version"]
        and actual["powershell_sha256"] == expected["powershell_sha256"]
        and actual["powershell_portable_bundle_selected"] is False
        and actual["observation_fingerprint_length"] == 64
        and actual["source_authority_selected"] is False
        and actual["artifact_download_attempted"] is False
        and actual["dependency_install_attempted"] is False
        and actual["sandbox_launched"] is False
        and actual["candidate_interpreter_executed"] is False
        and actual["reusable_lease_issued"] is False
        and actual["execution_authorized"] is False
    )

    print("=== V1C0B1 REAL WINDOWS CANONICAL HOST TOOLCHAIN OBSERVATION ===")
    print(json.dumps({"actual": actual, "expected": expected, "report": report.to_dict(), "ok": ok}, ensure_ascii=False, indent=2))
    if ok:
        print("[OK] V1C0B1 REAL WINDOWS CANONICAL HOST TOOLCHAIN OBSERVATION")
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": 1, "fail_count": 0}, indent=2))
        return 0

    print("[FAIL] V1C0B1 REAL WINDOWS CANONICAL HOST TOOLCHAIN OBSERVATION")
    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": 1, "fail_count": 1}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
