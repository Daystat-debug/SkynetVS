from __future__ import annotations

import ast
import hashlib
import inspect
import json

from dataclasses import fields, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_execution_dependency_acquisition as acquisition_module
from modules.developer.developer_task_execution_dependency_acquisition import (
    DeveloperTaskExecutionDependencyAcquisitionReport,
    build_developer_task_execution_dependency_acquisition_contract,
)
from modules.developer.developer_task_execution_dependency_acquisition_policy import (
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_ID,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_POLICY,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_ID,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT,
    developer_task_execution_dependency_acquisition_architecture_policy_fingerprint,
    developer_task_execution_dependency_acquisition_policy_fingerprint,
    validate_developer_task_execution_dependency_acquisition_policy,
)
from modules.developer.developer_task_execution_dependency_profile import (
    DeveloperTaskExecutionDependencyProfileReport,
    build_developer_task_execution_dependency_profile_contract,
)
from modules.developer.developer_task_execution_dependency_profile_policy import (
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY,
    DeveloperTaskExecutionDependencyDeclarationPolicy,
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


PROJECT_ROOT = Path(__file__).resolve().parent.parent


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


def _git_head() -> str:
    return acquisition_module._git_scalar(
        PROJECT_ROOT,
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
        check="eval_head",
    ).casefold()


def _requirement_evidence(
    policy: DeveloperTaskExecutionDependencyDeclarationPolicy,
) -> DeveloperTaskExecutionRequirementFileEvidence:
    return DeveloperTaskExecutionRequirementFileEvidence(
        path=policy.path,
        kind=policy.kind,
        git_mode=policy.git_mode,
        git_object_id=policy.git_object_id,
        size_bytes=policy.size_bytes,
        sha256=policy.sha256,
        entries=tuple(
            DeveloperTaskExecutionRequirementEntryEvidence(
                name=item.name,
                normalized_name=item.normalized_name,
                specifier=item.specifier,
                exact_pin=item.exact_pin,
            )
            for item in policy.entries
        ),
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


def _seal_toolchain(
    report: DeveloperTaskExecutionHostToolchainReport,
) -> DeveloperTaskExecutionHostToolchainReport:
    fingerprint = _sha256(
        _canonical_json(_observation_payload(report)).encode("utf-8")
    )
    return replace(report, observation_fingerprint=fingerprint)


def _toolchain_report(
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
        repository_root=str(PROJECT_ROOT.resolve(strict=True)),
        head_commit=_git_head(),
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
    return _seal_toolchain(report)


def _profile_report(
    *,
    import_variant: bool = False,
) -> DeveloperTaskExecutionDependencyProfileReport:
    return build_developer_task_execution_dependency_profile_contract(
        _toolchain_report(import_variant=import_variant),
        project_root=PROJECT_ROOT,
    )


def _mutation_blocked(value: Any) -> bool:
    try:
        first = fields(value)[0]
        setattr(value, first.name, getattr(value, first.name))
    except (AttributeError, TypeError):
        return True
    return False


def _network_import_roots(path: Path) -> list[str]:
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

    check(
        "V1C3A1A PINNED POLICY SELF CHECK",
        {
            "errors": list(
                validate_developer_task_execution_dependency_acquisition_policy()
            ),
            "policy_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_ID,
            "fingerprint": (
                developer_task_execution_dependency_acquisition_policy_fingerprint()
            ),
        },
        {
            "errors": [],
            "policy_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_ID,
            "fingerprint": (
                DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_FINGERPRINT
            ),
        },
    )

    architecture = DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_POLICY
    check(
        "V1C3A1A FULL RC043 ARCHITECTURE POLICY IS CANONICALLY BOUND",
        {
            "fingerprint": (
                developer_task_execution_dependency_acquisition_architecture_policy_fingerprint()
            ),
            "decision_id": architecture["decision_id"],
            "required_sections_present": sorted(
                section
                for section in ['active_component_identity', 'active_worker_confinement', 'bounds', 'candidate_manifest', 'environment', 'evidence_layers', 'extras_contract', 'failure_and_storage', 'fixed_target', 'gates', 'initial_scope', 'internal_sequence', 'marker_contract', 'network_model', 'resolver_capsule', 'resolver_invocation', 'resolver_output', 'resolver_tool_acceptance', 'resolver_tool_candidate', 'source_authority', 'strict_parsing', 'transition_target', 'upstream_lineage']
                if section in architecture
            ),
            "network_closed": architecture["network_model"]["resolver_external_network"] is False,
            "broker_only_external_actor": (
                architecture["network_model"]["broker"]["only_external_network_actor"]
                is True
            ),
            "strict_simple_duplicate_keys": (
                architecture["strict_parsing"]["simple_json"]["duplicate_object_keys"]
            ),
            "worker_children_denied": (
                architecture["active_worker_confinement"]["child_process_creation_denied"]
                is True
            ),
            "attempt_raw_not_closure": (
                architecture["evidence_layers"]["attempt_run_envelope"][
                    "eligible_for_deterministic_closure_fingerprint"
                ]
                is False
            ),
            "resolver_tool_first_use_blocked": (
                architecture["resolver_tool_candidate"]["first_use_blocked"]
                is True
            ),
            "resolver_tool_record_contract_bound": (
                architecture["resolver_tool_acceptance"]["record_contract"][
                    "regular_file_member_set_equals_record_path_set"
                ]
                is True
            ),
            "resolver_tool_license_contract_bound": (
                architecture["resolver_tool_acceptance"]["license_contract"][
                    "manual_explicit_license_evidence_acceptance_required"
                ]
                is True
            ),
            "candidate_v1c3b_eligible": (
                architecture["candidate_manifest"]["eligible_for_v1c3b"]
            ),
        },
        {
            "fingerprint": (
                DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT
            ),
            "decision_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_ID,
            "required_sections_present": ['active_component_identity', 'active_worker_confinement', 'bounds', 'candidate_manifest', 'environment', 'evidence_layers', 'extras_contract', 'failure_and_storage', 'fixed_target', 'gates', 'initial_scope', 'internal_sequence', 'marker_contract', 'network_model', 'resolver_capsule', 'resolver_invocation', 'resolver_output', 'resolver_tool_acceptance', 'resolver_tool_candidate', 'source_authority', 'strict_parsing', 'transition_target', 'upstream_lineage'],
            "network_closed": True,
            "broker_only_external_actor": True,
            "strict_simple_duplicate_keys": "reject",
            "worker_children_denied": True,
            "attempt_raw_not_closure": True,
            "resolver_tool_first_use_blocked": True,
            "resolver_tool_record_contract_bound": True,
            "resolver_tool_license_contract_bound": True,
            "candidate_v1c3b_eligible": False,
        },
    )

    with patch(
        "modules.developer.developer_task_execution_dependency_acquisition_policy._CURRENT_DEPENDENCY_PROFILE_POLICY_FINGERPRINT",
        "0" * 64,
    ):
        lineage_errors = list(
            validate_developer_task_execution_dependency_acquisition_policy()
        )
    check(
        "V1C3A1A PINNED V1C3A0 POLICY LINEAGE DRIFT FAILS CLOSED",
        lineage_errors,
        ["policy_v1c3a0_policy_fingerprint_lineage_changed"],
    )

    tampered_architecture_policy = dict(
        acquisition_module.DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY
    )
    tampered_architecture = dict(
        tampered_architecture_policy["architecture_policy"]
    )
    tampered_network = dict(tampered_architecture["network_model"])
    tampered_network["resolver_external_network"] = True
    tampered_architecture["network_model"] = tampered_network
    tampered_architecture_policy["architecture_policy"] = tampered_architecture
    architecture_tamper_errors = list(
        validate_developer_task_execution_dependency_acquisition_policy(
            tampered_architecture_policy
        )
    )
    check(
        "V1C3A1A RC043 ARCHITECTURE TAMPER FAILS CLOSED",
        {
            "architecture_fingerprint_invalid": (
                "policy_architecture_fingerprint_invalid"
                in architecture_tamper_errors
            ),
            "policy_fingerprint_invalid": (
                "policy_fingerprint_invalid"
                in architecture_tamper_errors
            ),
        },
        {
            "architecture_fingerprint_invalid": True,
            "policy_fingerprint_invalid": True,
        },
    )

    signature = inspect.signature(
        build_developer_task_execution_dependency_acquisition_contract
    )
    check(
        "V1C3A1A PUBLIC API HAS NO CALLER CONTROLLED ACQUISITION SURFACE",
        {
            name: {
                "kind": parameter.kind.name,
                "default": (
                    None
                    if parameter.default is inspect.Parameter.empty
                    else repr(parameter.default)
                ),
            }
            for name, parameter in signature.parameters.items()
        },
        {
            "dependency_profile_report": {
                "kind": "POSITIONAL_OR_KEYWORD",
                "default": None,
            },
            "project_root": {
                "kind": "KEYWORD_ONLY",
                "default": None,
            },
        },
    )

    production_paths = (
        PROJECT_ROOT
        / "modules"
        / "developer"
        / "developer_task_execution_dependency_acquisition.py",
        PROJECT_ROOT
        / "modules"
        / "developer"
        / "developer_task_execution_dependency_acquisition_policy.py",
    )
    check(
        "V1C3A1A PRODUCTION MODULES HAVE NO NETWORK OR PIP IMPORT ROOT",
        {
            path.name: _network_import_roots(path)
            for path in production_paths
        },
        {
            "developer_task_execution_dependency_acquisition.py": [],
            "developer_task_execution_dependency_acquisition_policy.py": [],
        },
    )

    profile = _profile_report()
    report = build_developer_task_execution_dependency_acquisition_contract(
        profile,
        project_root=PROJECT_ROOT,
    )

    expected_declaration = next(
        item
        for item in DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.declarations
        if item.path == "requirements.txt"
    )
    check(
        "V1C3A1A EXACT INITIAL SCOPE SOURCE AUTHORITY AND TARGET CONTRACT",
        {
            "profile_ok": profile.ok,
            "report_ok": report.ok,
            "issues": list(report.issue_codes),
            "head_matches": report.head_commit == _git_head(),
            "policy": report.policy_fingerprint,
            "architecture": {
                "id": report.architecture_decision_id,
                "fingerprint": report.architecture_decision_fingerprint,
            },
            "v1c0b2": {
                "id": report.v1c0b2_decision_id,
                "fingerprint": report.v1c0b2_decision_fingerprint,
            },
            "v1c3a0": {
                "id": report.dependency_profile_policy_id,
                "fingerprint": report.dependency_profile_policy_fingerprint,
            },
            "initial_profile": report.initial_profile_id,
            "declaration": report.declaration.to_dict() if report.declaration else None,
            "target": report.target.to_dict(),
            "source_authority": report.source_authority.to_dict(),
            "bounds_count": len(report.bounds.items),
            "resolver_tool_wheel_bound": report.bounds.to_dict().get(
                "max_resolver_tool_wheel_bytes"
            ),
            "source_authority_bound": report.source_authority_bound,
            "active_acquisition_blocked": report.active_acquisition_blocked,
            "contract_fingerprint_length": len(report.contract_fingerprint),
        },
        {
            "profile_ok": True,
            "report_ok": True,
            "issues": [],
            "head_matches": True,
            "policy": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_FINGERPRINT,
            "architecture": {
                "id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_ID,
                "fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT,
            },
            "v1c0b2": {
                "id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_ID,
                "fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_FINGERPRINT,
            },
            "v1c3a0": {
                "id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.policy_id,
                "fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT,
            },
            "initial_profile": "skynetvs-python-base-v1",
            "declaration": {
                "path": expected_declaration.path,
                "git_mode": expected_declaration.git_mode,
                "git_object_id": expected_declaration.git_object_id,
                "size_bytes": expected_declaration.size_bytes,
                "sha256": expected_declaration.sha256,
                "requirements": [
                    item.to_dict()
                    for item in expected_declaration.entries
                ],
            },
            "target": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.target.to_dict(),
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
            "contract_fingerprint_length": 64,
        },
    )

    variant_profile = _profile_report(import_variant=True)
    variant = build_developer_task_execution_dependency_acquisition_contract(
        variant_profile,
        project_root=PROJECT_ROOT,
    )
    check(
        "V1C3A1A HOST OBSERVATION PROVENANCE DOES NOT BECOME CONTRACT AUTHORITY",
        {
            "base_ok": report.ok,
            "variant_ok": variant.ok,
            "observation_changed": (
                profile.toolchain_observation_fingerprint
                != variant_profile.toolchain_observation_fingerprint
            ),
            "profile_contract_same": (
                profile.contract_fingerprint
                == variant_profile.contract_fingerprint
            ),
            "acquisition_contract_same": (
                report.contract_fingerprint
                == variant.contract_fingerprint
            ),
        },
        {
            "base_ok": True,
            "variant_ok": True,
            "observation_changed": True,
            "profile_contract_same": True,
            "acquisition_contract_same": True,
        },
    )

    tampered_policy = replace(
        profile,
        policy_fingerprint="0" * 64,
    )
    tampered_policy_report = (
        build_developer_task_execution_dependency_acquisition_contract(
            tampered_policy,
            project_root=PROJECT_ROOT,
        )
    )
    check(
        "V1C3A1A TAMPERED V1C3A0 POLICY IDENTITY FAILS CLOSED",
        {
            "ok": tampered_policy_report.ok,
            "issues": list(tampered_policy_report.issue_codes),
        },
        {
            "ok": False,
            "issues": [
                "dependency_acquisition_dependency_profile_report_invalid"
            ],
        },
    )

    changed_target = replace(
        profile.target,
        python_full_version="3.13.14",
    )
    changed_target_profile = replace(
        profile,
        target=changed_target,
    )
    changed_target_report = (
        build_developer_task_execution_dependency_acquisition_contract(
            changed_target_profile,
            project_root=PROJECT_ROOT,
        )
    )
    check(
        "V1C3A1A CHANGED FIXED TARGET FAILS CLOSED",
        {
            "ok": changed_target_report.ok,
            "issues": list(changed_target_report.issue_codes),
        },
        {
            "ok": False,
            "issues": ["dependency_acquisition_target_changed"],
        },
    )

    tampered_contract = replace(
        profile,
        contract_fingerprint="0" * 64,
    )
    tampered_contract_report = (
        build_developer_task_execution_dependency_acquisition_contract(
            tampered_contract,
            project_root=PROJECT_ROOT,
        )
    )
    check(
        "V1C3A1A TAMPERED V1C3A0 CONTRACT FINGERPRINT FAILS CLOSED",
        {
            "ok": tampered_contract_report.ok,
            "issues": list(tampered_contract_report.issue_codes),
        },
        {
            "ok": False,
            "issues": [
                "dependency_acquisition_dependency_profile_report_invalid"
            ],
        },
    )

    original_read = acquisition_module._read_committed_path

    def missing_v1c0b2(
        repository_root: Path,
        head_commit: str,
        path: str,
        *,
        check: str,
    ) -> tuple[str, str, str, bytes]:
        row = original_read(
            repository_root,
            head_commit,
            path,
            check=check,
        )
        if check != "architecture_roadmap":
            return row
        mode, object_type, object_id, data = row
        needle = (
            "decision ID:          "
            + DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_ID
        ).encode("utf-8")
        return mode, object_type, object_id, data.replace(
            needle,
            b"decision ID:          removed-v1c0b2",
            1,
        )

    with patch.object(
        acquisition_module,
        "_read_committed_path",
        missing_v1c0b2,
    ):
        missing = build_developer_task_execution_dependency_acquisition_contract(
            profile,
            project_root=PROJECT_ROOT,
        )
    check(
        "V1C3A1A MISSING V1C0B2 COMMITTED IDENTITY FAILS CLOSED",
        {
            "ok": missing.ok,
            "issues": list(missing.issue_codes),
        },
        {
            "ok": False,
            "issues": ["dependency_acquisition_v1c0b2_lineage_changed"],
        },
    )

    def duplicate_v1c0b2(
        repository_root: Path,
        head_commit: str,
        path: str,
        *,
        check: str,
    ) -> tuple[str, str, str, bytes]:
        row = original_read(
            repository_root,
            head_commit,
            path,
            check=check,
        )
        if check != "architecture_roadmap":
            return row
        mode, object_type, object_id, data = row
        block = (
            "decision ID:          "
            + DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_ID
            + "\n"
            + "decision fingerprint: "
            + DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_FINGERPRINT
        ).encode("utf-8")
        return mode, object_type, object_id, data + b"\n" + block + b"\n"

    with patch.object(
        acquisition_module,
        "_read_committed_path",
        duplicate_v1c0b2,
    ):
        duplicate = build_developer_task_execution_dependency_acquisition_contract(
            profile,
            project_root=PROJECT_ROOT,
        )
    check(
        "V1C3A1A DUPLICATE V1C0B2 COMMITTED IDENTITY FAILS CLOSED",
        {
            "ok": duplicate.ok,
            "issues": list(duplicate.issue_codes),
        },
        {
            "ok": False,
            "issues": ["dependency_acquisition_v1c0b2_lineage_changed"],
        },
    )

    transition_block = (
        b"RC043   ARCHITECTURE LOCK RECORDED\n"
        b"V1C3A1  CURRENT / V1C3A1A NON-NETWORK CONTRACT ONLY\n"
        b"         ACTIVE ACQUISITION BLOCKED"
    )
    flattened_transition_block = (
        b"RC043   ARCHITECTURE LOCK RECORDED\n"
        b"V1C3A1  CURRENT / V1C3A1A NON-NETWORK CONTRACT ONLY / "
        b"ACTIVE ACQUISITION BLOCKED"
    )

    def flattened_rc043_transition(
        repository_root: Path,
        head_commit: str,
        path: str,
        *,
        check: str,
    ) -> tuple[str, str, str, bytes]:
        row = original_read(
            repository_root,
            head_commit,
            path,
            check=check,
        )
        if check != "architecture_roadmap":
            return row
        mode, object_type, object_id, data = row
        if data.count(transition_block) != 1:
            raise RuntimeError(
                "V1C3A1A transition regression fixture is missing or ambiguous"
            )
        return (
            mode,
            object_type,
            object_id,
            data.replace(
                transition_block,
                flattened_transition_block,
                1,
            ),
        )

    with patch.object(
        acquisition_module,
        "_read_committed_path",
        flattened_rc043_transition,
    ):
        flattened_transition = (
            build_developer_task_execution_dependency_acquisition_contract(
                profile,
                project_root=PROJECT_ROOT,
            )
        )
    check(
        "V1C3A1A FLATTENED RC043 TRANSITION LAYOUT FAILS CLOSED",
        {
            "ok": flattened_transition.ok,
            "issues": list(flattened_transition.issue_codes),
        },
        {
            "ok": False,
            "issues": ["dependency_acquisition_rc043_lineage_changed"],
        },
    )

    def mode_drift(
        repository_root: Path,
        head_commit: str,
        path: str,
        *,
        check: str,
    ) -> tuple[str, str, str, bytes]:
        row = original_read(
            repository_root,
            head_commit,
            path,
            check=check,
        )
        if check == "v1c3a0_policy_source":
            _mode, object_type, object_id, data = row
            return "120000", object_type, object_id, data
        return row

    with patch.object(
        acquisition_module,
        "_read_committed_path",
        mode_drift,
    ):
        drift = build_developer_task_execution_dependency_acquisition_contract(
            profile,
            project_root=PROJECT_ROOT,
        )
    check(
        "V1C3A1A COMMITTED V1C3A0 POLICY MODE DRIFT FAILS CLOSED",
        {
            "ok": drift.ok,
            "issues": list(drift.issue_codes),
        },
        {
            "ok": False,
            "issues": [
                "dependency_acquisition_v1c3a0_source_lineage_changed"
            ],
        },
    )

    active_fields = {
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
    }
    check(
        "V1C3A1A REMAINS NON NETWORK NON RESOLVING AND NON AUTHORIZING",
        {
            "source_authority_bound": report.source_authority_bound,
            "active_acquisition_blocked": report.active_acquisition_blocked,
            "active_fields": active_fields,
        },
        {
            "source_authority_bound": True,
            "active_acquisition_blocked": True,
            "active_fields": {
                key: False
                for key in active_fields
            },
        },
    )

    policy_mutation_blocked = False
    try:
        DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY["policy_id"] = "changed"
    except TypeError:
        policy_mutation_blocked = True

    check(
        "V1C3A1A CONTRACT VALUES ARE IMMUTABLE",
        {
            "policy": policy_mutation_blocked,
            "report": _mutation_blocked(report),
            "declaration": _mutation_blocked(report.declaration),
            "target": _mutation_blocked(report.target),
            "source_authority": _mutation_blocked(report.source_authority),
            "bounds": _mutation_blocked(report.bounds),
        },
        {
            "policy": True,
            "report": True,
            "declaration": True,
            "target": True,
            "source_authority": True,
            "bounds": True,
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps(
        {"case_count": case_count, "fail_count": fail_count},
        indent=2,
    ))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
