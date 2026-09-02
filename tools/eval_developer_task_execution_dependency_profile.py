from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import tempfile

from dataclasses import fields, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.developer.developer_task_execution_dependency_profile import (
    DeveloperTaskExecutionDependencyProfileContract,
    DeveloperTaskExecutionDependencyProfileReport,
    DeveloperTaskExecutionDependencyTargetContract,
    build_developer_task_execution_dependency_profile_contract,
)
from modules.developer.developer_task_execution_dependency_profile_policy import (
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_ID,
    DeveloperTaskExecutionDependencyDeclarationPolicy,
    DeveloperTaskExecutionDependencyProfilePolicy,
    developer_task_execution_dependency_profile_policy_fingerprint,
    validate_developer_task_execution_dependency_profile_policy,
)
from modules.developer.developer_task_execution_toolchain_observation import (
    DeveloperTaskExecutionHostToolchainReport,
    DeveloperTaskExecutionImportDistributionEvidence,
    DeveloperTaskExecutionRequirementEntryEvidence,
    DeveloperTaskExecutionRequirementFileEvidence,
)
from modules.developer.developer_task_execution_toolchain_observation_policy import (
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
)


REQUIREMENT_BYTES = {
    "requirements.txt": (
        b"# requirements.txt\n"
        b"vosk>=0.3.45\n"
        b"sounddevice>=0.4.6\n"
        b"numpy>=1.24\n"
        b"colorama>=0.4.6\n"
        b"edge-tts>=6.1.12\n"
        b"pydub>=0.25.1\n"
        b"scikit-learn>=1.3.0\n"
        b"joblib>=1.3.0\n"
        b"pycaw>=20240210\n"
        b"comtypes>=1.4.0\n"
        b"python-dotenv>=1.0.1"
    ),
    "requirements-train.txt": (
        b"scikit-learn>=1.3.0\n"
        b"joblib>=1.3.2\n"
        b"numpy>=1.24\n"
    ),
    "requirements-whisper.txt": (
        b"# Optional Whisper refinement dependencies.\n"
        b"# Main project can run without this file if WHISPER_ENABLE=0.\n"
        b"faster-whisper==1.2.1"
    ),
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
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


def _write_exact(root: Path) -> None:
    for relative, data in REQUIREMENT_BYTES.items():
        (root / relative).write_bytes(data)
    (root / "README.md").write_text("v1c3a0 test\n", encoding="utf-8", newline="\n")


def _create_repository(root: Path) -> str:
    _git(root, "init")
    _git(root, "config", "user.email", "v1c3a0@example.invalid")
    _git(root, "config", "user.name", "V1C3A0 Eval")
    _write_exact(root)
    _git(root, "add", "--", "requirements.txt", "requirements-train.txt", "requirements-whisper.txt", "README.md")
    _git(root, "commit", "-m", "fixture")
    return _git(root, "rev-parse", "--verify", "HEAD^{commit}").casefold()


def _requirement_evidence(
    policy: DeveloperTaskExecutionDependencyDeclarationPolicy,
) -> DeveloperTaskExecutionRequirementFileEvidence:
    entries = tuple(
        DeveloperTaskExecutionRequirementEntryEvidence(
            name=item.name,
            normalized_name=item.normalized_name,
            specifier=item.specifier,
            exact_pin=item.exact_pin,
        )
        for item in policy.entries
    )
    return DeveloperTaskExecutionRequirementFileEvidence(
        path=policy.path,
        kind=policy.kind,
        git_mode=policy.git_mode,
        git_object_id=policy.git_object_id,
        size_bytes=policy.size_bytes,
        sha256=policy.sha256,
        entries=entries,
    )


def _observation_payload(
    report: DeveloperTaskExecutionHostToolchainReport,
) -> dict[str, Any]:
    return {
        "policy_id": report.policy_id,
        "policy_fingerprint": report.policy_fingerprint,
        "repository_root": report.repository_root,
        "head_commit": report.head_commit,
        "inventory_policy_fingerprint": report.inventory_policy_fingerprint,
        "inventory_fingerprint": report.inventory_fingerprint,
        "requirement_files": [item.to_dict() for item in report.requirement_files],
        "host_python": report.host_python.to_dict() if report.host_python is not None else None,
        "import_distributions": [item.to_dict() for item in report.import_distributions],
        "host_git": report.host_git.to_dict() if report.host_git is not None else None,
        "host_powershell": report.host_powershell.to_dict() if report.host_powershell is not None else None,
        "issues": [item.to_dict() for item in report.issues],
        "source_authority_selected": False,
        "artifact_download_attempted": False,
        "dependency_install_attempted": False,
        "sandbox_launched": False,
        "candidate_interpreter_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }


def _seal_report(
    report: DeveloperTaskExecutionHostToolchainReport,
) -> DeveloperTaskExecutionHostToolchainReport:
    fingerprint = _sha256(_canonical_json(_observation_payload(report)).encode("utf-8"))
    return replace(report, observation_fingerprint=fingerprint)


def _toolchain_report(
    root: Path,
    head: str,
    *,
    import_variant: bool = False,
) -> DeveloperTaskExecutionHostToolchainReport:
    imports = ()
    if import_variant:
        imports = (
            DeveloperTaskExecutionImportDistributionEvidence(
                root="host-only-variant",
                category="unresolved",
                distributions=(),
            ),
        )
    report = DeveloperTaskExecutionHostToolchainReport(
        policy_id=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
        repository_root=str(root.resolve(strict=True)),
        head_commit=head,
        inventory_policy_fingerprint="7" * 64,
        inventory_fingerprint="8" * 64,
        requirement_files=tuple(
            _requirement_evidence(item)
            for item in DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.declarations
        ),
        host_python=None,
        import_distributions=imports,
        host_git=None,
        host_powershell=None,
        observation_fingerprint="",
        issues=(),
    )
    return _seal_report(report)


def _mutation_blocked(value: Any) -> bool:
    try:
        field = fields(value)[0]
        setattr(value, field.name, getattr(value, field.name))
    except (AttributeError, TypeError):
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
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2))
        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    check(
        "V1C3A0 PINNED POLICY SELF CHECK",
        {
            "errors": list(validate_developer_task_execution_dependency_profile_policy()),
            "policy_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.policy_id,
            "fingerprint": developer_task_execution_dependency_profile_policy_fingerprint(),
        },
        {
            "errors": [],
            "policy_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_ID,
            "fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_FINGERPRINT,
        },
    )

    with patch(
        "modules.developer.developer_task_execution_dependency_profile_policy._CURRENT_TOOLCHAIN_POLICY_FINGERPRINT",
        "0" * 64,
    ):
        lineage_errors = list(validate_developer_task_execution_dependency_profile_policy())
    check(
        "V1C3A0 PINNED V1C0B1 POLICY LINEAGE DRIFT FAILS CLOSED",
        lineage_errors,
        ["policy_toolchain_fingerprint_lineage_changed"],
    )

    signature = inspect.signature(build_developer_task_execution_dependency_profile_contract)
    check(
        "V1C3A0 PUBLIC API HAS NO CALLER CONTROLLED PROFILE TARGET OR RESOLVER SURFACE",
        {
            name: {
                "kind": parameter.kind.name,
                "default": None if parameter.default is inspect.Parameter.empty else repr(parameter.default),
            }
            for name, parameter in signature.parameters.items()
        },
        {
            "toolchain_report": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "project_root": {"kind": "KEYWORD_ONLY", "default": None},
        },
    )

    with tempfile.TemporaryDirectory(prefix="skynetvs-v1c3a0-eval-") as temp:
        root = Path(temp)
        head = _create_repository(root)
        toolchain = _toolchain_report(root, head)
        report = build_developer_task_execution_dependency_profile_contract(
            toolchain,
            project_root=root,
        )

        check(
            "V1C3A0 EXACT PROFILE TOPOLOGY AND FIXED TARGET",
            {
                "ok": report.ok,
                "issues": list(report.issue_codes),
                "policy": report.policy_fingerprint,
                "initial_profile": report.initial_profile_id,
                "profiles": [
                    {
                        "id": item.profile_id,
                        "paths": [file.path for file in item.declaration_files],
                        "composition": item.composition,
                        "base": item.base_profile_id,
                        "overlay": item.optional_overlay,
                        "default": item.default_enabled,
                        "v1c3a": item.initial_v1c3a_selected,
                        "v1c3b": item.initial_v1c3b_selected,
                        "extras": list(item.requested_extras),
                    }
                    for item in report.profiles
                ],
                "target": report.target.to_dict(),
                "contract_fingerprint_length": len(report.contract_fingerprint),
            },
            {
                "ok": True,
                "issues": [],
                "policy": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_FINGERPRINT,
                "initial_profile": "skynetvs-python-base-v1",
                "profiles": [
                    {
                        "id": "skynetvs-python-base-v1",
                        "paths": ["requirements.txt"],
                        "composition": "standalone",
                        "base": "",
                        "overlay": False,
                        "default": True,
                        "v1c3a": True,
                        "v1c3b": True,
                        "extras": [],
                    },
                    {
                        "id": "skynetvs-nlu-training-minimal-v1",
                        "paths": ["requirements-train.txt"],
                        "composition": "standalone_minimal",
                        "base": "",
                        "overlay": False,
                        "default": False,
                        "v1c3a": False,
                        "v1c3b": False,
                        "extras": [],
                    },
                    {
                        "id": "skynetvs-python-base-whisper-v1",
                        "paths": ["requirements.txt", "requirements-whisper.txt"],
                        "composition": "base_plus_optional_overlay",
                        "base": "skynetvs-python-base-v1",
                        "overlay": True,
                        "default": False,
                        "v1c3a": False,
                        "v1c3b": False,
                        "extras": [],
                    },
                ],
                "target": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.target.to_dict(),
                "contract_fingerprint_length": 64,
            },
        )

        variant = build_developer_task_execution_dependency_profile_contract(
            _toolchain_report(root, head, import_variant=True),
            project_root=root,
        )
        check(
            "V1C3A0 HOST OBSERVATION PROVENANCE DOES NOT BECOME CONTRACT AUTHORITY",
            {
                "base_ok": report.ok,
                "variant_ok": variant.ok,
                "observation_changed": (
                    report.toolchain_observation_fingerprint
                    != variant.toolchain_observation_fingerprint
                ),
                "contract_same": report.contract_fingerprint == variant.contract_fingerprint,
            },
            {
                "base_ok": True,
                "variant_ok": True,
                "observation_changed": True,
                "contract_same": True,
            },
        )

        tampered_fingerprint = replace(toolchain, observation_fingerprint="0" * 64)
        tampered_report = build_developer_task_execution_dependency_profile_contract(
            tampered_fingerprint,
            project_root=root,
        )
        check(
            "V1C3A0 TAMPERED V1C0B1 FINGERPRINT FAILS CLOSED",
            {
                "ok": tampered_report.ok,
                "issues": list(tampered_report.issue_codes),
            },
            {
                "ok": False,
                "issues": ["dependency_profile_toolchain_report_invalid"],
            },
        )

        requirement_files = list(toolchain.requirement_files)
        requirement_files[0] = replace(requirement_files[0], sha256="0" * 64)
        changed = replace(toolchain, requirement_files=tuple(requirement_files), observation_fingerprint="")
        changed = _seal_report(changed)
        changed_report = build_developer_task_execution_dependency_profile_contract(
            changed,
            project_root=root,
        )
        check(
            "V1C3A0 CHANGED DECLARATION EVIDENCE FAILS CLOSED",
            {
                "ok": changed_report.ok,
                "issues": list(changed_report.issue_codes),
            },
            {
                "ok": False,
                "issues": ["dependency_profile_declaration_evidence_changed"],
            },
        )

        check(
            "V1C3A0 REMAINS NON AUTHORIZING",
            {
                "source_authority_selected": report.source_authority_selected,
                "network_used": report.network_used,
                "artifact_download_attempted": report.artifact_download_attempted,
                "dependency_install_attempted": report.dependency_install_attempted,
                "dependency_executed": report.dependency_executed,
                "sandbox_launched": report.sandbox_launched,
                "candidate_interpreter_executed": report.candidate_interpreter_executed,
                "reusable_lease_issued": report.reusable_lease_issued,
                "execution_authorized": report.execution_authorized,
            },
            {
                "source_authority_selected": False,
                "network_used": False,
                "artifact_download_attempted": False,
                "dependency_install_attempted": False,
                "dependency_executed": False,
                "sandbox_launched": False,
                "candidate_interpreter_executed": False,
                "reusable_lease_issued": False,
                "execution_authorized": False,
            },
        )

        check(
            "V1C3A0 CONTRACT VALUES ARE IMMUTABLE",
            {
                "policy": _mutation_blocked(DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY),
                "report": _mutation_blocked(report),
                "profile": _mutation_blocked(report.profiles[0]),
                "target": _mutation_blocked(report.target),
            },
            {
                "policy": True,
                "report": True,
                "profile": True,
                "target": True,
            },
        )

    with tempfile.TemporaryDirectory(prefix="skynetvs-v1c3a0-mode-eval-") as temp:
        mode_root = Path(temp)
        _create_repository(mode_root)
        requirements_policy = DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.declarations[0]
        _git(
            mode_root,
            "update-index",
            "--cacheinfo",
            "120000",
            requirements_policy.git_object_id,
            requirements_policy.path,
        )
        _git(mode_root, "commit", "-m", "mode drift")
        mode_head = _git(mode_root, "rev-parse", "--verify", "HEAD^{commit}").casefold()
        mode_report = build_developer_task_execution_dependency_profile_contract(
            _toolchain_report(mode_root, mode_head),
            project_root=mode_root,
        )
        check(
            "V1C3A0 COMMITTED DECLARATION TREE MODE DRIFT FAILS CLOSED",
            {
                "ok": mode_report.ok,
                "issues": list(mode_report.issue_codes),
            },
            {
                "ok": False,
                "issues": ["dependency_profile_declaration_identity_changed"],
            },
        )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, indent=2))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
