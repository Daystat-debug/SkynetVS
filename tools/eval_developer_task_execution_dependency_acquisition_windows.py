from __future__ import annotations

import ast
import json
import subprocess
import sys

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_dependency_acquisition import (
    build_developer_task_execution_dependency_acquisition_contract,
)
from modules.developer.developer_task_execution_dependency_acquisition_policy import (
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT,
    developer_task_execution_dependency_acquisition_architecture_policy_fingerprint,
)
from modules.developer.developer_task_execution_dependency_profile import (
    build_developer_task_execution_dependency_profile_contract,
)
from modules.developer.developer_task_execution_dependency_profile_policy import (
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY,
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


def _forbidden_import_roots(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.extend(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.append(node.module.split(".", 1)[0])
    forbidden = {
        "aiohttp",
        "httpx",
        "pip",
        "requests",
        "socket",
        "urllib",
        "webbrowser",
    }
    return sorted({item for item in roots if item in forbidden})


def main() -> int:
    if sys.platform != "win32":
        print("[FAIL] V1C3A1A Windows host-only smoke requires win32")
        return 1

    head_before = _git("rev-parse", "--verify", "HEAD^{commit}").casefold()
    status_before = _git("status", "--porcelain=v2", "--untracked-files=all")

    synthetic_preflight = DeveloperTaskRepositoryPreflightReport(
        manifest_fingerprint="0" * 64,
        project_root=str(PROJECT_ROOT),
        repository_root=str(PROJECT_ROOT),
        head_commit=head_before,
        resolved_base_commit=head_before,
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
    profile = build_developer_task_execution_dependency_profile_contract(
        toolchain,
        project_root=PROJECT_ROOT,
    )
    report = build_developer_task_execution_dependency_acquisition_contract(
        profile,
        project_root=PROJECT_ROOT,
    )

    head_after = _git("rev-parse", "--verify", "HEAD^{commit}").casefold()
    status_after = _git("status", "--porcelain=v2", "--untracked-files=all")

    declaration = next(
        item
        for item in DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.declarations
        if item.path == "requirements.txt"
    )

    production_sources = (
        PROJECT_ROOT
        / "modules"
        / "developer"
        / "developer_task_execution_dependency_acquisition.py",
        PROJECT_ROOT
        / "modules"
        / "developer"
        / "developer_task_execution_dependency_acquisition_policy.py",
    )

    actual = {
        "inventory_ok": inventory.ok,
        "toolchain_ok": toolchain.ok,
        "profile_ok": profile.ok,
        "report_ok": report.ok,
        "issue_codes": list(report.issue_codes),
        "head_matches": report.head_commit == head_before == head_after,
        "repository_status_unchanged": status_before == status_after,
        "policy_fingerprint": report.policy_fingerprint,
        "architecture_policy_fingerprint": (
            developer_task_execution_dependency_acquisition_architecture_policy_fingerprint()
        ),
        "architecture_decision_fingerprint": report.architecture_decision_fingerprint,
        "v1c0b2_decision_fingerprint": report.v1c0b2_decision_fingerprint,
        "v1c3a0_policy_fingerprint": report.dependency_profile_policy_fingerprint,
        "initial_profile_id": report.initial_profile_id,
        "declaration": report.declaration.to_dict() if report.declaration else None,
        "target": report.target.to_dict(),
        "contract_fingerprint_length": len(report.contract_fingerprint),
        "source_authority": report.source_authority.to_dict(),
        "bounds_count": len(report.bounds.items),
        "resolver_tool_wheel_bound": report.bounds.to_dict().get(
            "max_resolver_tool_wheel_bytes"
        ),
        "source_authority_bound": report.source_authority_bound,
        "active_acquisition_blocked": report.active_acquisition_blocked,
        "network_authority_opened": report.network_authority_opened,
        "resolver_selected": report.resolver_selected,
        "resolver_executed": report.resolver_executed,
        "resolver_tool_version_selected": report.resolver_tool_version_selected,
        "resolver_tool_imported": report.resolver_tool_imported,
        "source_authority_selected": report.source_authority_selected,
        "network_used": report.network_used,
        "metadata_downloaded": report.metadata_downloaded,
        "wheel_downloaded": report.wheel_downloaded,
        "artifact_download_attempted": report.artifact_download_attempted,
        "dependency_install_attempted": report.dependency_install_attempted,
        "dependency_executed": report.dependency_executed,
        "sandbox_launched": report.sandbox_launched,
        "candidate_interpreter_executed": report.candidate_interpreter_executed,
        "reusable_lease_issued": report.reusable_lease_issued,
        "execution_authorized": report.execution_authorized,
        "forbidden_import_roots": {
            path.name: _forbidden_import_roots(path)
            for path in production_sources
        },
    }

    expected = {
        "inventory_ok": True,
        "toolchain_ok": True,
        "profile_ok": True,
        "report_ok": True,
        "issue_codes": [],
        "head_matches": True,
        "repository_status_unchanged": True,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_FINGERPRINT,
        "architecture_policy_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT,
        "architecture_decision_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT,
        "v1c0b2_decision_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_FINGERPRINT,
        "v1c3a0_policy_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT,
        "initial_profile_id": "skynetvs-python-base-v1",
        "declaration": {
            "path": declaration.path,
            "git_mode": declaration.git_mode,
            "git_object_id": declaration.git_object_id,
            "size_bytes": declaration.size_bytes,
            "sha256": declaration.sha256,
            "requirements": [
                item.to_dict()
                for item in declaration.entries
            ],
        },
        "target": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.target.to_dict(),
        "contract_fingerprint_length": 64,
        "source_authority": {
            "simple_origin": "https://pypi.org",
            "simple_path_template": "/simple/<normalized-project>/",
            "simple_media_type": "application/vnd.pypi.simple.v1+json",
            "simple_supported_major": 1,
            "simple_minimum_minor": 4,
            "artifact_origin": "https://files.pythonhosted.org",
            "provenance_initial_origin": "https://pypi.org:443",
            "redirects": 0,
            "automatic_retries": 0,
            "wheel_only": True,
            "sha256_required": True,
            "yanked_allowed": False,
            "prerelease_allowed": False,
            "sdist_allowed": False,
            "local_build_allowed": False,
            "direct_url_allowed": False,
            "extra_index_allowed": False,
            "host_cache_authority_allowed": False,
            "resolver_output_authority": False,
        },
        "bounds_count": 54,
        "resolver_tool_wheel_bound": 67108864,
        "source_authority_bound": True,
        "active_acquisition_blocked": True,
        "network_authority_opened": False,
        "resolver_selected": False,
        "resolver_executed": False,
        "resolver_tool_version_selected": False,
        "resolver_tool_imported": False,
        "source_authority_selected": False,
        "network_used": False,
        "metadata_downloaded": False,
        "wheel_downloaded": False,
        "artifact_download_attempted": False,
        "dependency_install_attempted": False,
        "dependency_executed": False,
        "sandbox_launched": False,
        "candidate_interpreter_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
        "forbidden_import_roots": {
            "developer_task_execution_dependency_acquisition.py": [],
            "developer_task_execution_dependency_acquisition_policy.py": [],
        },
    }

    ok = actual == expected

    print("=== V1C3A1A REAL WINDOWS NON-NETWORK DEPENDENCY ACQUISITION CONTRACT ===")
    print(json.dumps(
        {
            "actual": actual,
            "expected": expected,
            "ok": ok,
        },
        ensure_ascii=False,
        indent=2,
    ))

    if ok:
        print("[OK] V1C3A1A REAL WINDOWS NON-NETWORK DEPENDENCY ACQUISITION CONTRACT")
        print()
        print("=== SUMMARY ===")
        print(json.dumps({"case_count": 1, "fail_count": 0}, indent=2))
        return 0

    print("[FAIL] V1C3A1A REAL WINDOWS NON-NETWORK DEPENDENCY ACQUISITION CONTRACT")
    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": 1, "fail_count": 1}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
