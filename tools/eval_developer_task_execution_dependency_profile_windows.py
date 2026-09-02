from __future__ import annotations

import json
import subprocess
import sys

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_dependency_profile import (
    build_developer_task_execution_dependency_profile_contract,
)
from modules.developer.developer_task_execution_dependency_profile_policy import (
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_environment_inventory import (
    inventory_developer_task_execution_environment,
)
from modules.developer.developer_task_execution_toolchain_observation import (
    observe_developer_task_execution_host_toolchain,
)
from modules.developer.developer_task_preflight import (
    DeveloperTaskRepositoryPreflightReport,
)


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
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return completed.stdout.strip()


def main() -> int:
    if sys.platform != "win32":
        print("[FAIL] V1C3A0 Windows host-only smoke requires win32")
        return 1

    head = _git("rev-parse", "--verify", "HEAD^{commit}").casefold()

    synthetic_preflight = DeveloperTaskRepositoryPreflightReport(
        manifest_fingerprint="0" * 64,
        project_root=str(PROJECT_ROOT),
        repository_root=str(PROJECT_ROOT),
        head_commit=head,
        resolved_base_commit=head,
        dirty_categories=(),
        issues=(),
    )

    inventory = inventory_developer_task_execution_environment(
        synthetic_preflight,
        project_root=PROJECT_ROOT,
    )
    toolchain = observe_developer_task_execution_host_toolchain(
        inventory,
        project_root=PROJECT_ROOT,
    )
    report = build_developer_task_execution_dependency_profile_contract(
        toolchain,
        project_root=PROJECT_ROOT,
    )

    actual = {
        "inventory_ok": inventory.ok,
        "toolchain_ok": toolchain.ok,
        "report_ok": report.ok,
        "issue_codes": list(report.issue_codes),
        "head_matches": report.head_commit == head,
        "policy_fingerprint": report.policy_fingerprint,
        "initial_profile_id": report.initial_profile_id,
        "profile_ids": [item.profile_id for item in report.profiles],
        "profile_declarations": {
            item.profile_id: [file.path for file in item.declaration_files]
            for item in report.profiles
        },
        "target": report.target.to_dict(),
        "contract_fingerprint_length": len(report.contract_fingerprint),
        "source_authority_selected": report.source_authority_selected,
        "network_used": report.network_used,
        "artifact_download_attempted": report.artifact_download_attempted,
        "dependency_install_attempted": report.dependency_install_attempted,
        "dependency_executed": report.dependency_executed,
        "sandbox_launched": report.sandbox_launched,
        "candidate_interpreter_executed": report.candidate_interpreter_executed,
        "reusable_lease_issued": report.reusable_lease_issued,
        "execution_authorized": report.execution_authorized,
    }

    expected = {
        "inventory_ok": True,
        "toolchain_ok": True,
        "report_ok": True,
        "issue_codes": [],
        "head_matches": True,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_FINGERPRINT,
        "initial_profile_id": "skynetvs-python-base-v1",
        "profile_ids": [
            "skynetvs-python-base-v1",
            "skynetvs-nlu-training-minimal-v1",
            "skynetvs-python-base-whisper-v1",
        ],
        "profile_declarations": {
            "skynetvs-python-base-v1": ["requirements.txt"],
            "skynetvs-nlu-training-minimal-v1": ["requirements-train.txt"],
            "skynetvs-python-base-whisper-v1": [
                "requirements.txt",
                "requirements-whisper.txt",
            ],
        },
        "target": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.target.to_dict(),
        "contract_fingerprint_length": 64,
        "source_authority_selected": False,
        "network_used": False,
        "artifact_download_attempted": False,
        "dependency_install_attempted": False,
        "dependency_executed": False,
        "sandbox_launched": False,
        "candidate_interpreter_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }

    production_sources = {
        "profile": (
            PROJECT_ROOT
            / "modules"
            / "developer"
            / "developer_task_execution_dependency_profile.py"
        ).read_text(encoding="utf-8"),
        "policy": (
            PROJECT_ROOT
            / "modules"
            / "developer"
            / "developer_task_execution_dependency_profile_policy.py"
        ).read_text(encoding="utf-8"),
    }
    combined = "\n".join(production_sources.values()).casefold()
    forbidden = {
        "urllib": "urllib" in combined,
        "requests": "requests" in combined,
        "http_literal": "http://" in combined or "https://" in combined,
        "pip_install": "pip install" in combined,
        "windows_sandbox": "windowssandbox" in combined,
        "socket_import": "import socket" in combined or "from socket" in combined,
    }

    expected_forbidden = {
        "urllib": False,
        "requests": False,
        "http_literal": False,
        "pip_install": False,
        "windows_sandbox": False,
        "socket_import": False,
    }

    ok = actual == expected and forbidden == expected_forbidden

    print("=== V1C3A0 REAL WINDOWS DEPENDENCY PROFILE TARGET CONTRACT ===")
    print(
        json.dumps(
            {
                "actual": actual,
                "expected": expected,
                "forbidden_surface": forbidden,
                "expected_forbidden_surface": expected_forbidden,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if ok:
        print("[OK] V1C3A0 REAL WINDOWS DEPENDENCY PROFILE TARGET CONTRACT")
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": 1, "fail_count": 0}, indent=2))
        return 0

    print("[FAIL] V1C3A0 REAL WINDOWS DEPENDENCY PROFILE TARGET CONTRACT")
    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": 1, "fail_count": 1}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
