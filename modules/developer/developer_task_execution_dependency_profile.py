from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_dependency_profile_policy import (
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_ID,
    DeveloperTaskExecutionDependencyDeclarationPolicy,
    DeveloperTaskExecutionDependencyProfilePolicyEntry,
    developer_task_execution_dependency_profile_policy_fingerprint,
    validate_developer_task_execution_dependency_profile_policy,
)
from modules.developer.developer_task_execution_toolchain_observation import (
    DeveloperTaskExecutionHostToolchainReport,
    DeveloperTaskExecutionRequirementFileEvidence,
)
from modules.developer.developer_task_execution_toolchain_observation_policy import (
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIREMENT_SYNTAX,
)


_HEX_OBJECT_RE = re.compile(r"^[0-9a-f]{40,64}$")
_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_ENVIRONMENT_KEYS_TO_CLEAR = frozenset({
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_ASKPASS",
    "GIT_CEILING_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_SYSTEM",
    "GIT_DIR",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_EXEC_PATH",
    "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE",
    "GIT_NAMESPACE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_OPTIONAL_LOCKS",
    "GIT_PREFIX",
    "GIT_QUARANTINE_PATH",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_SSH",
    "GIT_SSH_COMMAND",
    "GIT_SUPER_PREFIX",
    "GIT_WORK_TREE",
})
_GIT_ENVIRONMENT_PREFIXES_TO_CLEAR = (
    "GIT_CONFIG_KEY_",
    "GIT_CONFIG_VALUE_",
    "GIT_TRACE",
)


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyProfileIssue:
    code: str
    check: str
    message: str
    expected: str = ""
    actual: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "check": self.check,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyProfileContract:
    profile_id: str
    declaration_files: tuple[DeveloperTaskExecutionRequirementFileEvidence, ...]
    composition: str
    base_profile_id: str
    optional_overlay: bool
    default_enabled: bool
    initial_v1c3a_selected: bool
    initial_v1c3b_selected: bool
    requested_extras: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "declaration_files": [item.to_dict() for item in self.declaration_files],
            "composition": self.composition,
            "base_profile_id": self.base_profile_id,
            "optional_overlay": self.optional_overlay,
            "default_enabled": self.default_enabled,
            "initial_v1c3a_selected": self.initial_v1c3a_selected,
            "initial_v1c3b_selected": self.initial_v1c3b_selected,
            "requested_extras": list(self.requested_extras),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyTargetContract:
    implementation_name: str
    implementation_version: str
    python_version: str
    python_full_version: str
    os_name: str
    sys_platform: str
    platform_system: str
    platform_machine: str
    platform_python_implementation: str
    requested_extras: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "implementation_name": self.implementation_name,
            "implementation_version": self.implementation_version,
            "python_version": self.python_version,
            "python_full_version": self.python_full_version,
            "os_name": self.os_name,
            "sys_platform": self.sys_platform,
            "platform_system": self.platform_system,
            "platform_machine": self.platform_machine,
            "platform_python_implementation": self.platform_python_implementation,
            "requested_extras": list(self.requested_extras),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyProfileReport:
    policy_id: str
    policy_fingerprint: str
    repository_root: str
    head_commit: str
    toolchain_policy_id: str
    toolchain_policy_fingerprint: str
    toolchain_observation_fingerprint: str
    requirement_syntax: str
    initial_profile_id: str
    profiles: tuple[DeveloperTaskExecutionDependencyProfileContract, ...]
    target: DeveloperTaskExecutionDependencyTargetContract
    contract_fingerprint: str
    issues: tuple[DeveloperTaskExecutionDependencyProfileIssue, ...]
    source_authority_selected: bool = False
    network_used: bool = False
    artifact_download_attempted: bool = False
    dependency_install_attempted: bool = False
    dependency_executed: bool = False
    sandbox_launched: bool = False
    candidate_interpreter_executed: bool = False
    reusable_lease_issued: bool = False
    execution_authorized: bool = False

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "repository_root": self.repository_root,
            "head_commit": self.head_commit,
            "toolchain_policy_id": self.toolchain_policy_id,
            "toolchain_policy_fingerprint": self.toolchain_policy_fingerprint,
            "toolchain_observation_fingerprint": self.toolchain_observation_fingerprint,
            "requirement_syntax": self.requirement_syntax,
            "initial_profile_id": self.initial_profile_id,
            "profiles": [item.to_dict() for item in self.profiles],
            "target": self.target.to_dict(),
            "contract_fingerprint": self.contract_fingerprint,
            "issues": [item.to_dict() for item in self.issues],
            "source_authority_selected": self.source_authority_selected,
            "network_used": self.network_used,
            "artifact_download_attempted": self.artifact_download_attempted,
            "dependency_install_attempted": self.dependency_install_attempted,
            "dependency_executed": self.dependency_executed,
            "sandbox_launched": self.sandbox_launched,
            "candidate_interpreter_executed": self.candidate_interpreter_executed,
            "reusable_lease_issued": self.reusable_lease_issued,
            "execution_authorized": self.execution_authorized,
        }


class _DependencyProfileFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        check: str,
        message: str,
        *,
        expected: str = "",
        actual: str = "",
    ) -> None:
        self.code = code
        self.check = check
        self.expected = expected
        self.actual = actual
        super().__init__(message)


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


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def _absolute_resolved_directory(path: Path) -> Path:
    if not isinstance(path, Path):
        raise TypeError("project_root must be pathlib.Path")
    try:
        resolved = Path(os.path.abspath(os.fspath(path.expanduser()))).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _DependencyProfileFailure(
            "dependency_profile_project_root_invalid",
            "project_root",
            "Project root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if not resolved.is_dir():
        raise _DependencyProfileFailure(
            "dependency_profile_project_root_invalid",
            "project_root",
            "Project root must be a directory.",
            actual=str(resolved),
        )
    return resolved


def _build_git_environment() -> dict[str, str]:
    env = dict(os.environ)
    for key in tuple(env):
        if key in _GIT_ENVIRONMENT_KEYS_TO_CLEAR or key.startswith(_GIT_ENVIRONMENT_PREFIXES_TO_CLEAR):
            env.pop(key, None)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_COUNT"] = "0"
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_PAGER"] = "cat"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _run_git(
    repository_root: Path,
    *args: str,
    timeout_seconds: float = 20.0,
) -> subprocess.CompletedProcess[bytes]:
    command = [
        "git",
        "--no-optional-locks",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(repository_root),
        *args,
    ]
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=False,
            env=_build_git_environment(),
        )
    except subprocess.TimeoutExpired as exc:
        raise _DependencyProfileFailure(
            "dependency_profile_git_timeout",
            "git",
            "Git command timed out.",
            actual=" ".join(args),
        ) from exc
    except (FileNotFoundError, OSError) as exc:
        raise _DependencyProfileFailure(
            "dependency_profile_git_unavailable",
            "git",
            "Git command could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc


def _decode_git_text(
    result: subprocess.CompletedProcess[bytes],
    *,
    check: str,
) -> str:
    if result.returncode != 0:
        error = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        if len(error) > 800:
            error = error[:797] + "..."
        raise _DependencyProfileFailure(
            "dependency_profile_git_command_failed",
            check,
            "Git command failed.",
            actual=error,
        )
    try:
        return result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _DependencyProfileFailure(
            "dependency_profile_git_output_invalid",
            check,
            "Git machine output is not strict UTF-8.",
            actual=str(exc),
        ) from exc


def _git_scalar(repository_root: Path, *args: str, check: str) -> str:
    return _decode_git_text(
        _run_git(repository_root, *args),
        check=check,
    ).strip()


def _toolchain_observation_fingerprint_payload(
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


def _expected_toolchain_observation_fingerprint(
    report: DeveloperTaskExecutionHostToolchainReport,
) -> str:
    return _sha256(
        _canonical_json(_toolchain_observation_fingerprint_payload(report)).encode("utf-8")
    )


def _validate_toolchain_report(
    report: DeveloperTaskExecutionHostToolchainReport,
    project_root: Path,
) -> tuple[Path, str]:
    if not isinstance(report, DeveloperTaskExecutionHostToolchainReport):
        raise TypeError(
            "toolchain_report must be DeveloperTaskExecutionHostToolchainReport"
        )
    if not report.ok:
        raise _DependencyProfileFailure(
            "dependency_profile_toolchain_report_failed",
            "toolchain_report",
            "V1C0B1 host toolchain report is not successful.",
            actual=",".join(report.issue_codes),
        )
    if report.policy_id != DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID:
        raise _DependencyProfileFailure(
            "dependency_profile_toolchain_report_invalid",
            "toolchain_report",
            "V1C0B1 policy identifier changed.",
            expected=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
            actual=report.policy_id,
        )
    if report.policy_fingerprint != DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT:
        raise _DependencyProfileFailure(
            "dependency_profile_toolchain_report_invalid",
            "toolchain_report",
            "V1C0B1 policy fingerprint changed.",
            expected=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
            actual=report.policy_fingerprint,
        )
    if not _HEX_OBJECT_RE.fullmatch(report.head_commit):
        raise _DependencyProfileFailure(
            "dependency_profile_toolchain_report_invalid",
            "toolchain_report",
            "V1C0B1 HEAD identity is invalid.",
            actual=report.head_commit,
        )
    if not _HEX_SHA256_RE.fullmatch(report.observation_fingerprint):
        raise _DependencyProfileFailure(
            "dependency_profile_toolchain_report_invalid",
            "toolchain_report",
            "V1C0B1 observation fingerprint is invalid.",
            actual=report.observation_fingerprint,
        )
    if any(
        (
            report.source_authority_selected,
            report.artifact_download_attempted,
            report.dependency_install_attempted,
            report.sandbox_launched,
            report.candidate_interpreter_executed,
            report.reusable_lease_issued,
            report.execution_authorized,
        )
    ):
        raise _DependencyProfileFailure(
            "dependency_profile_toolchain_report_invalid",
            "toolchain_report",
            "V1C0B1 report contains source or execution authority.",
        )

    expected_observation = _expected_toolchain_observation_fingerprint(report)
    if report.observation_fingerprint != expected_observation:
        raise _DependencyProfileFailure(
            "dependency_profile_toolchain_report_invalid",
            "toolchain_report",
            "V1C0B1 observation fingerprint does not match nested evidence.",
            expected=expected_observation,
            actual=report.observation_fingerprint,
        )

    root = _absolute_resolved_directory(project_root)
    try:
        report_root = Path(report.repository_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _DependencyProfileFailure(
            "dependency_profile_toolchain_report_invalid",
            "toolchain_report",
            "V1C0B1 repository root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if _path_key(root) != _path_key(report_root):
        raise _DependencyProfileFailure(
            "dependency_profile_repository_root_mismatch",
            "toolchain_report",
            "Project root does not match V1C0B1 repository root.",
            expected=str(root),
            actual=str(report_root),
        )

    current_head = _git_scalar(
        root,
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
        check="head",
    ).casefold()
    if current_head != report.head_commit:
        raise _DependencyProfileFailure(
            "dependency_profile_repository_changed",
            "head",
            "Repository HEAD changed relative to the V1C0B1 report.",
            expected=report.head_commit,
            actual=current_head,
        )
    return root, report.head_commit


def _entry_dicts(
    evidence: DeveloperTaskExecutionRequirementFileEvidence,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in evidence.entries:
        if (
            not entry.name
            or not entry.normalized_name
            or not entry.specifier
            or entry.normalized_name != _normalize_distribution_name(entry.name)
        ):
            raise _DependencyProfileFailure(
                "dependency_profile_requirement_entry_invalid",
                "requirement_evidence",
                "V1C0B1 requirement entry is structurally invalid.",
                actual=f"{evidence.path}:{entry.name}:{entry.specifier}",
            )
        if entry.normalized_name in seen:
            raise _DependencyProfileFailure(
                "dependency_profile_requirement_entry_duplicate",
                "requirement_evidence",
                "V1C0B1 requirement entry is duplicated.",
                actual=f"{evidence.path}:{entry.normalized_name}",
            )
        seen.add(entry.normalized_name)
        result.append(entry.to_dict())
    return result


def _verify_committed_declaration(
    repository_root: Path,
    head_commit: str,
    policy: DeveloperTaskExecutionDependencyDeclarationPolicy,
) -> None:
    tree_text = _decode_git_text(
        _run_git(
            repository_root,
            "ls-tree",
            head_commit,
            "--",
            policy.path,
        ),
        check="dependency_tree",
    )
    tree_lines = tuple(line for line in tree_text.splitlines() if line)
    if len(tree_lines) != 1:
        raise _DependencyProfileFailure(
            "dependency_profile_declaration_identity_changed",
            "dependency_tree",
            "Committed dependency declaration tree entry is missing or ambiguous.",
            expected=policy.path,
            actual=str(len(tree_lines)),
        )

    try:
        metadata, tree_path = tree_lines[0].split("\t", 1)
        git_mode, object_type, object_id = metadata.split(" ", 2)
    except ValueError as exc:
        raise _DependencyProfileFailure(
            "dependency_profile_declaration_identity_changed",
            "dependency_tree",
            "Committed dependency declaration tree entry is malformed.",
            expected=f"{policy.git_mode}:blob:{policy.git_object_id}:{policy.path}",
            actual=tree_lines[0],
        ) from exc

    object_id = object_id.casefold()
    if (
        tree_path != policy.path
        or git_mode != policy.git_mode
        or object_type != "blob"
        or object_id != policy.git_object_id
    ):
        raise _DependencyProfileFailure(
            "dependency_profile_declaration_identity_changed",
            "dependency_tree",
            "Committed dependency declaration tree identity changed.",
            expected=f"{policy.git_mode}:blob:{policy.git_object_id}:{policy.path}",
            actual=f"{git_mode}:{object_type}:{object_id}:{tree_path}",
        )

    result = _run_git(repository_root, "cat-file", "blob", object_id)
    if result.returncode != 0:
        _decode_git_text(result, check="dependency_blob")
    data = result.stdout
    actual_sha256 = _sha256(data)
    if len(data) != policy.size_bytes or actual_sha256 != policy.sha256:
        raise _DependencyProfileFailure(
            "dependency_profile_declaration_identity_changed",
            "dependency_blob",
            "Committed dependency declaration bytes changed.",
            expected=f"{policy.path}:{policy.size_bytes}:{policy.sha256}",
            actual=f"{policy.path}:{len(data)}:{actual_sha256}",
        )


def _validate_requirement_files(
    report: DeveloperTaskExecutionHostToolchainReport,
    repository_root: Path,
    head_commit: str,
) -> dict[str, DeveloperTaskExecutionRequirementFileEvidence]:
    policy_files = DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.declarations
    expected_paths = tuple(item.path for item in policy_files)
    actual_paths = tuple(item.path for item in report.requirement_files)
    if (
        len(actual_paths) != len(set(actual_paths))
        or tuple(sorted(actual_paths)) != tuple(sorted(expected_paths))
    ):
        raise _DependencyProfileFailure(
            "dependency_profile_declaration_set_changed",
            "requirement_evidence",
            "V1C0B1 dependency declaration set differs from the V1C3A0 lock.",
            expected=",".join(sorted(expected_paths)),
            actual=",".join(sorted(actual_paths)),
        )

    evidence_by_path = {item.path: item for item in report.requirement_files}
    result: dict[str, DeveloperTaskExecutionRequirementFileEvidence] = {}
    for policy_item in policy_files:
        evidence = evidence_by_path[policy_item.path]
        _verify_committed_declaration(repository_root, head_commit, policy_item)
        if (
            evidence.path != policy_item.path
            or evidence.kind != policy_item.kind
            or evidence.git_mode != policy_item.git_mode
            or evidence.git_object_id != policy_item.git_object_id
            or evidence.size_bytes != policy_item.size_bytes
            or evidence.sha256 != policy_item.sha256
        ):
            raise _DependencyProfileFailure(
                "dependency_profile_declaration_evidence_changed",
                "requirement_evidence",
                "V1C0B1 declaration evidence differs from the pinned V1C3A0 identity.",
                expected=policy_item.path,
                actual=evidence.path,
            )
        actual_entries = _entry_dicts(evidence)
        expected_entries = [item.to_dict() for item in policy_item.entries]
        if actual_entries != expected_entries:
            raise _DependencyProfileFailure(
                "dependency_profile_requirement_semantics_changed",
                "requirement_evidence",
                "V1C0B1 parsed requirement semantics differ from the pinned V1C3A0 evidence.",
                expected=_canonical_json(expected_entries),
                actual=_canonical_json(actual_entries),
            )
        result[evidence.path] = evidence
    return result


def _profile_contract(
    profile: DeveloperTaskExecutionDependencyProfilePolicyEntry,
    evidence: dict[str, DeveloperTaskExecutionRequirementFileEvidence],
) -> DeveloperTaskExecutionDependencyProfileContract:
    return DeveloperTaskExecutionDependencyProfileContract(
        profile_id=profile.profile_id,
        declaration_files=tuple(evidence[path] for path in profile.declaration_paths),
        composition=profile.composition,
        base_profile_id=profile.base_profile_id,
        optional_overlay=profile.optional_overlay,
        default_enabled=profile.default_enabled,
        initial_v1c3a_selected=profile.initial_v1c3a_selected,
        initial_v1c3b_selected=profile.initial_v1c3b_selected,
        requested_extras=profile.requested_extras,
    )


def _target_contract() -> DeveloperTaskExecutionDependencyTargetContract:
    target = DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.target
    return DeveloperTaskExecutionDependencyTargetContract(
        implementation_name=target.implementation_name,
        implementation_version=target.implementation_version,
        python_version=target.python_version,
        python_full_version=target.python_full_version,
        os_name=target.os_name,
        sys_platform=target.sys_platform,
        platform_system=target.platform_system,
        platform_machine=target.platform_machine,
        platform_python_implementation=target.platform_python_implementation,
        requested_extras=target.requested_extras,
    )


def _contract_fingerprint_payload(
    *,
    head_commit: str,
    profiles: tuple[DeveloperTaskExecutionDependencyProfileContract, ...],
    target: DeveloperTaskExecutionDependencyTargetContract,
) -> dict[str, Any]:
    return {
        "schema_version": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.schema_version,
        "policy_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_ID,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_FINGERPRINT,
        "head_commit": head_commit,
        "toolchain_policy_id": DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
        "toolchain_policy_fingerprint": DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
        "requirement_syntax": DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIREMENT_SYNTAX,
        "initial_profile_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.initial_profile_id,
        "profiles": [item.to_dict() for item in profiles],
        "target": target.to_dict(),
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


def _build_success_report(
    *,
    repository_root: Path,
    head_commit: str,
    toolchain_observation_fingerprint: str,
    profiles: tuple[DeveloperTaskExecutionDependencyProfileContract, ...],
    target: DeveloperTaskExecutionDependencyTargetContract,
) -> DeveloperTaskExecutionDependencyProfileReport:
    contract_fingerprint = _sha256(
        _canonical_json(
            _contract_fingerprint_payload(
                head_commit=head_commit,
                profiles=profiles,
                target=target,
            )
        ).encode("utf-8")
    )
    return DeveloperTaskExecutionDependencyProfileReport(
        policy_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_ID,
        policy_fingerprint=developer_task_execution_dependency_profile_policy_fingerprint(),
        repository_root=str(repository_root),
        head_commit=head_commit,
        toolchain_policy_id=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
        toolchain_policy_fingerprint=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
        toolchain_observation_fingerprint=toolchain_observation_fingerprint,
        requirement_syntax=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIREMENT_SYNTAX,
        initial_profile_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.initial_profile_id,
        profiles=profiles,
        target=target,
        contract_fingerprint=contract_fingerprint,
        issues=(),
    )


def _build_failure_report(
    *,
    repository_root: Path,
    head_commit: str,
    observation_fingerprint: str,
    failure: _DependencyProfileFailure,
) -> DeveloperTaskExecutionDependencyProfileReport:
    issue = DeveloperTaskExecutionDependencyProfileIssue(
        code=failure.code,
        check=failure.check,
        message=str(failure),
        expected=failure.expected,
        actual=failure.actual,
    )
    return DeveloperTaskExecutionDependencyProfileReport(
        policy_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_ID,
        policy_fingerprint=developer_task_execution_dependency_profile_policy_fingerprint(),
        repository_root=str(repository_root),
        head_commit=head_commit,
        toolchain_policy_id=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
        toolchain_policy_fingerprint=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
        toolchain_observation_fingerprint=observation_fingerprint,
        requirement_syntax=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIREMENT_SYNTAX,
        initial_profile_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.initial_profile_id,
        profiles=(),
        target=_target_contract(),
        contract_fingerprint="",
        issues=(issue,),
    )


def build_developer_task_execution_dependency_profile_contract(
    toolchain_report: DeveloperTaskExecutionHostToolchainReport,
    *,
    project_root: Path,
) -> DeveloperTaskExecutionDependencyProfileReport:
    """Build the V1C3A0 non-network dependency-profile and fixed-target contract."""

    policy_errors = validate_developer_task_execution_dependency_profile_policy()
    if policy_errors:
        raise RuntimeError(
            "Developer task execution dependency profile policy is invalid: "
            + ",".join(policy_errors)
        )

    repository_root = Path(os.path.abspath(os.fspath(project_root))) if isinstance(project_root, Path) else Path(".")
    head_commit = ""
    observation_fingerprint = ""

    try:
        repository_root, head_commit = _validate_toolchain_report(
            toolchain_report,
            project_root,
        )
        observation_fingerprint = toolchain_report.observation_fingerprint
        evidence = _validate_requirement_files(
            toolchain_report,
            repository_root,
            head_commit,
        )
        profiles = tuple(
            _profile_contract(profile, evidence)
            for profile in DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.profiles
        )
        target = _target_contract()
        return _build_success_report(
            repository_root=repository_root,
            head_commit=head_commit,
            toolchain_observation_fingerprint=observation_fingerprint,
            profiles=profiles,
            target=target,
        )
    except _DependencyProfileFailure as failure:
        return _build_failure_report(
            repository_root=repository_root,
            head_commit=head_commit,
            observation_fingerprint=observation_fingerprint,
            failure=failure,
        )
