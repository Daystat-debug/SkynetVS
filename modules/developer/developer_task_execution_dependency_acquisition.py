from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

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
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_ID,
    developer_task_execution_dependency_acquisition_policy_fingerprint,
    validate_developer_task_execution_dependency_acquisition_policy,
)
from modules.developer.developer_task_execution_dependency_profile import (
    DeveloperTaskExecutionDependencyProfileReport,
    DeveloperTaskExecutionDependencyTargetContract,
)
from modules.developer.developer_task_execution_dependency_profile_policy import (
    DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY,
    DeveloperTaskExecutionDependencyDeclarationPolicy,
    DeveloperTaskExecutionDependencyProfilePolicyEntry,
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
class DeveloperTaskExecutionDependencyAcquisitionIssue:
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
class DeveloperTaskExecutionDependencyAcquisitionRequirementContract:
    name: str
    normalized_name: str
    specifier: str
    exact_pin: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "normalized_name": self.normalized_name,
            "specifier": self.specifier,
            "exact_pin": self.exact_pin,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyAcquisitionDeclarationContract:
    path: str
    git_mode: str
    git_object_id: str
    size_bytes: int
    sha256: str
    requirements: tuple[DeveloperTaskExecutionDependencyAcquisitionRequirementContract, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "git_mode": self.git_mode,
            "git_object_id": self.git_object_id,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "requirements": [item.to_dict() for item in self.requirements],
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyAcquisitionSourceAuthorityContract:
    simple_origin: str
    simple_path_template: str
    simple_media_type: str
    simple_supported_major: int
    simple_minimum_minor: int
    artifact_origin: str
    provenance_initial_origin: str
    redirects: int
    automatic_retries: int
    wheel_only: bool
    sha256_required: bool
    yanked_allowed: bool
    prerelease_allowed: bool
    sdist_allowed: bool
    local_build_allowed: bool
    direct_url_allowed: bool
    extra_index_allowed: bool
    host_cache_authority_allowed: bool
    resolver_output_authority: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "simple_origin": self.simple_origin,
            "simple_path_template": self.simple_path_template,
            "simple_media_type": self.simple_media_type,
            "simple_supported_major": self.simple_supported_major,
            "simple_minimum_minor": self.simple_minimum_minor,
            "artifact_origin": self.artifact_origin,
            "provenance_initial_origin": self.provenance_initial_origin,
            "redirects": self.redirects,
            "automatic_retries": self.automatic_retries,
            "wheel_only": self.wheel_only,
            "sha256_required": self.sha256_required,
            "yanked_allowed": self.yanked_allowed,
            "prerelease_allowed": self.prerelease_allowed,
            "sdist_allowed": self.sdist_allowed,
            "local_build_allowed": self.local_build_allowed,
            "direct_url_allowed": self.direct_url_allowed,
            "extra_index_allowed": self.extra_index_allowed,
            "host_cache_authority_allowed": self.host_cache_authority_allowed,
            "resolver_output_authority": self.resolver_output_authority,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyAcquisitionBoundsContract:
    items: tuple[tuple[str, int], ...]

    def to_dict(self) -> dict[str, int]:
        return {key: value for key, value in self.items}


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyAcquisitionReport:
    policy_id: str
    policy_fingerprint: str
    architecture_decision_id: str
    architecture_decision_fingerprint: str
    v1c0b2_decision_id: str
    v1c0b2_decision_fingerprint: str
    dependency_profile_policy_id: str
    dependency_profile_policy_fingerprint: str
    repository_root: str
    head_commit: str
    dependency_profile_contract_fingerprint: str
    initial_profile_id: str
    declaration: DeveloperTaskExecutionDependencyAcquisitionDeclarationContract | None
    target: DeveloperTaskExecutionDependencyTargetContract
    source_authority: DeveloperTaskExecutionDependencyAcquisitionSourceAuthorityContract
    bounds: DeveloperTaskExecutionDependencyAcquisitionBoundsContract
    contract_fingerprint: str
    issues: tuple[DeveloperTaskExecutionDependencyAcquisitionIssue, ...]
    source_authority_bound: bool = False
    active_acquisition_blocked: bool = True
    network_authority_opened: bool = False
    resolver_selected: bool = False
    resolver_executed: bool = False
    resolver_tool_version_selected: bool = False
    resolver_tool_imported: bool = False
    source_authority_selected: bool = False
    network_used: bool = False
    metadata_downloaded: bool = False
    wheel_downloaded: bool = False
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
            "architecture_decision_id": self.architecture_decision_id,
            "architecture_decision_fingerprint": self.architecture_decision_fingerprint,
            "v1c0b2_decision_id": self.v1c0b2_decision_id,
            "v1c0b2_decision_fingerprint": self.v1c0b2_decision_fingerprint,
            "dependency_profile_policy_id": self.dependency_profile_policy_id,
            "dependency_profile_policy_fingerprint": self.dependency_profile_policy_fingerprint,
            "repository_root": self.repository_root,
            "head_commit": self.head_commit,
            "dependency_profile_contract_fingerprint": self.dependency_profile_contract_fingerprint,
            "initial_profile_id": self.initial_profile_id,
            "declaration": self.declaration.to_dict() if self.declaration is not None else None,
            "target": self.target.to_dict(),
            "source_authority": self.source_authority.to_dict(),
            "bounds": self.bounds.to_dict(),
            "contract_fingerprint": self.contract_fingerprint,
            "issues": [item.to_dict() for item in self.issues],
            "source_authority_bound": self.source_authority_bound,
            "active_acquisition_blocked": self.active_acquisition_blocked,
            "network_authority_opened": self.network_authority_opened,
            "resolver_selected": self.resolver_selected,
            "resolver_executed": self.resolver_executed,
            "resolver_tool_version_selected": self.resolver_tool_version_selected,
            "resolver_tool_imported": self.resolver_tool_imported,
            "source_authority_selected": self.source_authority_selected,
            "network_used": self.network_used,
            "metadata_downloaded": self.metadata_downloaded,
            "wheel_downloaded": self.wheel_downloaded,
            "artifact_download_attempted": self.artifact_download_attempted,
            "dependency_install_attempted": self.dependency_install_attempted,
            "dependency_executed": self.dependency_executed,
            "sandbox_launched": self.sandbox_launched,
            "candidate_interpreter_executed": self.candidate_interpreter_executed,
            "reusable_lease_issued": self.reusable_lease_issued,
            "execution_authorized": self.execution_authorized,
        }


class _DependencyAcquisitionFailure(RuntimeError):
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


def _architecture_section(name: str) -> Mapping[str, Any]:
    value = DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_POLICY.get(name)
    if not isinstance(value, Mapping):
        raise RuntimeError(f"RC043 architecture policy section is invalid: {name}")
    return value

def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def _absolute_resolved_directory(path: Path) -> Path:
    if not isinstance(path, Path):
        raise TypeError("project_root must be pathlib.Path")
    try:
        resolved = Path(os.path.abspath(os.fspath(path.expanduser()))).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_project_root_invalid",
            "project_root",
            "Project root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if not resolved.is_dir():
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_project_root_invalid",
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
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_git_timeout",
            "git",
            "Git command timed out.",
            actual=" ".join(args),
        ) from exc
    except (FileNotFoundError, OSError) as exc:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_git_unavailable",
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
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_git_command_failed",
            check,
            "Git command failed.",
            actual=error,
        )
    try:
        return result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_git_output_invalid",
            check,
            "Git machine output is not strict UTF-8.",
            actual=str(exc),
        ) from exc


def _git_scalar(repository_root: Path, *args: str, check: str) -> str:
    return _decode_git_text(
        _run_git(repository_root, *args),
        check=check,
    ).strip()


def _read_committed_path(
    repository_root: Path,
    head_commit: str,
    path: str,
    *,
    check: str,
) -> tuple[str, str, str, bytes]:
    tree_text = _decode_git_text(
        _run_git(
            repository_root,
            "ls-tree",
            head_commit,
            "--",
            path,
        ),
        check=check,
    )
    lines = tuple(line for line in tree_text.splitlines() if line)
    if len(lines) != 1:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_committed_source_changed",
            check,
            "Committed source tree entry is missing or ambiguous.",
            expected=path,
            actual=str(len(lines)),
        )
    try:
        metadata, actual_path = lines[0].split("\t", 1)
        mode, object_type, object_id = metadata.split(" ", 2)
    except ValueError as exc:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_committed_source_changed",
            check,
            "Committed source tree entry is malformed.",
            actual=lines[0],
        ) from exc
    object_id = object_id.casefold()
    if actual_path != path or not _HEX_OBJECT_RE.fullmatch(object_id):
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_committed_source_changed",
            check,
            "Committed source identity is invalid.",
            expected=path,
            actual=f"{mode}:{object_type}:{object_id}:{actual_path}",
        )

    result = _run_git(repository_root, "cat-file", "blob", object_id)
    if result.returncode != 0:
        _decode_git_text(result, check=check)
    return mode, object_type, object_id, result.stdout


def _profile_contract_fingerprint_payload(
    report: DeveloperTaskExecutionDependencyProfileReport,
) -> dict[str, Any]:
    return {
        "schema_version": DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.schema_version,
        "policy_id": report.policy_id,
        "policy_fingerprint": report.policy_fingerprint,
        "head_commit": report.head_commit,
        "toolchain_policy_id": report.toolchain_policy_id,
        "toolchain_policy_fingerprint": report.toolchain_policy_fingerprint,
        "requirement_syntax": report.requirement_syntax,
        "initial_profile_id": report.initial_profile_id,
        "profiles": [item.to_dict() for item in report.profiles],
        "target": report.target.to_dict(),
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


def _expected_profile_report_fingerprint(
    report: DeveloperTaskExecutionDependencyProfileReport,
) -> str:
    return _sha256(
        _canonical_json(_profile_contract_fingerprint_payload(report)).encode("utf-8")
    )


def _expected_profile_dicts() -> list[dict[str, Any]]:
    declarations = {
        item.path: item
        for item in DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.declarations
    }
    result: list[dict[str, Any]] = []
    for profile in DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.profiles:
        result.append({
            "profile_id": profile.profile_id,
            "declaration_files": [
                {
                    "path": declarations[path].path,
                    "kind": declarations[path].kind,
                    "git_mode": declarations[path].git_mode,
                    "git_object_id": declarations[path].git_object_id,
                    "size_bytes": declarations[path].size_bytes,
                    "sha256": declarations[path].sha256,
                    "entries": [entry.to_dict() for entry in declarations[path].entries],
                }
                for path in profile.declaration_paths
            ],
            "composition": profile.composition,
            "base_profile_id": profile.base_profile_id,
            "optional_overlay": profile.optional_overlay,
            "default_enabled": profile.default_enabled,
            "initial_v1c3a_selected": profile.initial_v1c3a_selected,
            "initial_v1c3b_selected": profile.initial_v1c3b_selected,
            "requested_extras": list(profile.requested_extras),
        })
    return result


def _validate_profile_report(
    report: DeveloperTaskExecutionDependencyProfileReport,
    project_root: Path,
) -> tuple[Path, str, DeveloperTaskExecutionDependencyProfilePolicyEntry]:
    if not isinstance(report, DeveloperTaskExecutionDependencyProfileReport):
        raise TypeError(
            "dependency_profile_report must be DeveloperTaskExecutionDependencyProfileReport"
        )
    if not report.ok:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_dependency_profile_report_failed",
            "dependency_profile_report",
            "V1C3A0 dependency profile report is not successful.",
            actual=",".join(report.issue_codes),
        )
    if report.policy_id != DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_ID:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_dependency_profile_report_invalid",
            "dependency_profile_report",
            "V1C3A0 policy identifier changed.",
            expected=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_ID,
            actual=report.policy_id,
        )
    if report.policy_fingerprint != DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_dependency_profile_report_invalid",
            "dependency_profile_report",
            "V1C3A0 policy fingerprint changed.",
            expected=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT,
            actual=report.policy_fingerprint,
        )
    if not _HEX_OBJECT_RE.fullmatch(report.head_commit):
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_dependency_profile_report_invalid",
            "dependency_profile_report",
            "V1C3A0 HEAD identity is invalid.",
            actual=report.head_commit,
        )
    if not _HEX_SHA256_RE.fullmatch(report.contract_fingerprint):
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_dependency_profile_report_invalid",
            "dependency_profile_report",
            "V1C3A0 contract fingerprint is invalid.",
            actual=report.contract_fingerprint,
        )
    if any((
        report.source_authority_selected,
        report.network_used,
        report.artifact_download_attempted,
        report.dependency_install_attempted,
        report.dependency_executed,
        report.sandbox_launched,
        report.candidate_interpreter_executed,
        report.reusable_lease_issued,
        report.execution_authorized,
    )):
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_dependency_profile_report_invalid",
            "dependency_profile_report",
            "V1C3A0 report contains source, network or execution authority.",
        )

    policy = DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY
    if (
        report.toolchain_policy_id != policy.toolchain_policy_id
        or report.toolchain_policy_fingerprint != policy.toolchain_policy_fingerprint
        or report.requirement_syntax != policy.requirement_syntax
        or report.initial_profile_id != policy.initial_profile_id
    ):
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_dependency_profile_report_invalid",
            "dependency_profile_report",
            "V1C3A0 upstream toolchain/profile lineage changed.",
        )

    actual_profiles = [item.to_dict() for item in report.profiles]
    expected_profiles = _expected_profile_dicts()
    if actual_profiles != expected_profiles:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_profile_scope_changed",
            "dependency_profile_report",
            "V1C3A0 profile topology differs from the current pinned policy.",
            expected=_canonical_json(expected_profiles),
            actual=_canonical_json(actual_profiles),
        )

    expected_target = policy.target.to_dict()
    if report.target.to_dict() != expected_target:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_target_changed",
            "dependency_profile_report",
            "V1C3A0 fixed target differs from the current pinned policy.",
            expected=_canonical_json(expected_target),
            actual=_canonical_json(report.target.to_dict()),
        )

    expected_fingerprint = _expected_profile_report_fingerprint(report)
    if report.contract_fingerprint != expected_fingerprint:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_dependency_profile_report_invalid",
            "dependency_profile_report",
            "V1C3A0 contract fingerprint does not match nested contract evidence.",
            expected=expected_fingerprint,
            actual=report.contract_fingerprint,
        )

    root = _absolute_resolved_directory(project_root)
    try:
        report_root = Path(report.repository_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_dependency_profile_report_invalid",
            "dependency_profile_report",
            "V1C3A0 repository root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if _path_key(root) != _path_key(report_root):
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_repository_root_mismatch",
            "dependency_profile_report",
            "Project root does not match the V1C3A0 repository root.",
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
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_repository_changed",
            "head",
            "Repository HEAD changed relative to the V1C3A0 report.",
            expected=report.head_commit,
            actual=current_head,
        )

    selected = tuple(
        item
        for item in policy.profiles
        if item.profile_id == policy.initial_profile_id
    )
    if len(selected) != 1:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_profile_scope_changed",
            "initial_profile",
            "V1C3A0 initial profile is missing or ambiguous.",
        )
    return root, report.head_commit, selected[0]


def _verify_v1c3a0_source_lineage(
    repository_root: Path,
    head_commit: str,
) -> None:
    lineage = _architecture_section("upstream_lineage")
    v1c3a0 = lineage.get("v1c3a0_dependency_profile_target")
    if not isinstance(v1c3a0, Mapping):
        raise RuntimeError("V1C3A0 RC043 lineage is invalid")
    source = v1c3a0.get("source")
    if not isinstance(source, Mapping):
        raise RuntimeError("V1C3A0 RC043 source lineage is invalid")

    path = str(source["path"])
    mode, object_type, object_id, data = _read_committed_path(
        repository_root,
        head_commit,
        path,
        check="v1c3a0_policy_source",
    )
    actual_sha256 = _sha256(data)
    if (
        mode != source["mode"]
        or object_type != source["type"]
        or object_id != source["blob"]
        or len(data) != source["bytes"]
        or actual_sha256 != source["sha256"]
    ):
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_v1c3a0_source_lineage_changed",
            "v1c3a0_policy_source",
            "Committed V1C3A0 policy source identity changed.",
            expected=_canonical_json(dict(source)),
            actual=_canonical_json({
                "path": path,
                "mode": mode,
                "type": object_type,
                "blob": object_id,
                "bytes": len(data),
                "sha256": actual_sha256,
            }),
        )

    implementation_commit = str(v1c3a0["implementation_commit"])
    ancestor = _run_git(
        repository_root,
        "merge-base",
        "--is-ancestor",
        implementation_commit,
        head_commit,
    )
    if ancestor.returncode != 0:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_v1c3a0_commit_lineage_changed",
            "v1c3a0_implementation_commit",
            "V1C3A0 implementation commit is not an ancestor of current HEAD.",
            expected=implementation_commit,
            actual=str(ancestor.returncode),
        )

    actual_tree = _git_scalar(
        repository_root,
        "rev-parse",
        "--verify",
        f"{implementation_commit}^{{tree}}",
        check="v1c3a0_implementation_tree",
    ).casefold()
    if actual_tree != v1c3a0["implementation_tree"]:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_v1c3a0_commit_lineage_changed",
            "v1c3a0_implementation_tree",
            "V1C3A0 implementation tree identity changed.",
            expected=str(v1c3a0["implementation_tree"]),
            actual=actual_tree,
        )

def _verify_architecture_lineage(
    repository_root: Path,
    head_commit: str,
) -> None:
    lineage = _architecture_section("upstream_lineage")
    v1c0b2 = lineage.get("v1c0b2_external_source_authority")
    if not isinstance(v1c0b2, Mapping):
        raise RuntimeError("V1C0B2 RC043 lineage is invalid")

    entering = v1c0b2.get("rc043_entering_source_document")
    if not isinstance(entering, Mapping):
        raise RuntimeError("V1C0B2 entering-source lineage is invalid")

    entering_blob = str(entering["blob"])
    historical = _run_git(
        repository_root,
        "cat-file",
        "blob",
        entering_blob,
    )
    if historical.returncode != 0:
        _decode_git_text(historical, check="v1c0b2_entering_roadmap")
    historical_bytes = historical.stdout
    historical_sha256 = _sha256(historical_bytes)
    if (
        len(historical_bytes) != entering["bytes"]
        or historical_sha256 != entering["sha256"]
    ):
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_v1c0b2_lineage_changed",
            "v1c0b2_entering_roadmap",
            "RC043 entering V1C0B2 authority document identity changed.",
            expected=f"{entering_blob}:{entering['bytes']}:{entering['sha256']}",
            actual=f"{entering_blob}:{len(historical_bytes)}:{historical_sha256}",
        )

    roadmap_path = str(entering["path"])
    mode, object_type, _object_id, current_bytes = _read_committed_path(
        repository_root,
        head_commit,
        roadmap_path,
        check="architecture_roadmap",
    )
    if mode != "100644" or object_type != "blob":
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_rc043_lineage_changed",
            "architecture_roadmap",
            "RC043 roadmap source mode/type changed.",
            expected="100644:blob",
            actual=f"{mode}:{object_type}",
        )

    try:
        historical_text = historical_bytes.decode("utf-8", errors="strict")
        current_text = current_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_rc043_lineage_changed",
            "architecture_roadmap",
            "RC043 roadmap source is not strict UTF-8.",
            actual=str(exc),
        ) from exc

    decision_line = (
        "decision ID:          "
        + DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_ID
    )
    fingerprint_line = (
        "decision fingerprint: "
        + DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_FINGERPRINT
    )
    v1c0b2_block = decision_line + "\n" + fingerprint_line

    for label, text in (
        ("entering", historical_text),
        ("current", current_text),
    ):
        if (
            text.count(decision_line) != 1
            or text.count(fingerprint_line) != 1
            or text.count(v1c0b2_block) != 1
        ):
            raise _DependencyAcquisitionFailure(
                "dependency_acquisition_v1c0b2_lineage_changed",
                f"v1c0b2_{label}_roadmap_identity",
                "Committed V1C0B2 decision identity is missing, duplicated or changed.",
            )

    rc043_block = (
        "decision ID:\n"
        + DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_ID
        + "\n\npolicy fingerprint:\n"
        + DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT
    )
    if current_text.count(rc043_block) != 1:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_rc043_lineage_changed",
            "rc043_roadmap_identity",
            "Committed RC043 architecture identity is missing, duplicated or changed.",
        )

    transition = _architecture_section("transition_target")
    expected_policy_state = (
        "CURRENT / V1C3A1A NON-NETWORK CONTRACT ONLY / "
        "ACTIVE ACQUISITION BLOCKED"
    )
    if (
        transition.get("rc043") != "ARCHITECTURE LOCK RECORDED"
        or transition.get("v1c3a1") != expected_policy_state
        or transition.get("network_authority_opened") is not False
        or transition.get("resolver_selected") is not False
        or transition.get("resolver_executed") is not False
    ):
        raise RuntimeError("RC043 transition-target policy is invalid")

    expected_transition_block = (
        "RC043   ARCHITECTURE LOCK RECORDED\n"
        "V1C3A1  CURRENT / V1C3A1A NON-NETWORK CONTRACT ONLY\n"
        "         ACTIVE ACQUISITION BLOCKED"
    )
    transition_count = current_text.count(expected_transition_block)
    if transition_count != 1:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_rc043_lineage_changed",
            "rc043_transition_state",
            "Committed RC043 transition block is missing, duplicated or changed.",
            expected=expected_transition_block,
            actual=str(transition_count),
        )

def _declaration_contract(
    policy: DeveloperTaskExecutionDependencyDeclarationPolicy,
) -> DeveloperTaskExecutionDependencyAcquisitionDeclarationContract:
    return DeveloperTaskExecutionDependencyAcquisitionDeclarationContract(
        path=policy.path,
        git_mode=policy.git_mode,
        git_object_id=policy.git_object_id,
        size_bytes=policy.size_bytes,
        sha256=policy.sha256,
        requirements=tuple(
            DeveloperTaskExecutionDependencyAcquisitionRequirementContract(
                name=item.name,
                normalized_name=item.normalized_name,
                specifier=item.specifier,
                exact_pin=item.exact_pin,
            )
            for item in policy.entries
        ),
    )


def _verify_selected_declaration(
    repository_root: Path,
    head_commit: str,
    profile: DeveloperTaskExecutionDependencyProfilePolicyEntry,
) -> DeveloperTaskExecutionDependencyAcquisitionDeclarationContract:
    scope = _architecture_section("initial_scope")
    paths = scope.get("declaration_paths")
    if not isinstance(paths, tuple) or paths != ("requirements.txt",):
        raise RuntimeError("RC043 initial declaration-path contract is invalid")
    expected_path = paths[0]

    if (
        profile.profile_id != scope["profile_id"]
        or profile.declaration_paths != (expected_path,)
        or profile.requested_extras
    ):
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_profile_scope_changed",
            "initial_profile",
            "V1C3A0 initial acquisition profile differs from RC043.",
        )

    declarations = tuple(
        item
        for item in DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY.declarations
        if item.path == expected_path
    )
    if len(declarations) != 1:
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_declaration_identity_changed",
            "initial_declaration",
            "Initial dependency declaration is missing or ambiguous.",
        )
    declaration = declarations[0]

    mode, object_type, object_id, data = _read_committed_path(
        repository_root,
        head_commit,
        declaration.path,
        check="initial_declaration",
    )
    actual_sha256 = _sha256(data)
    if (
        mode != declaration.git_mode
        or object_type != "blob"
        or object_id != declaration.git_object_id
        or len(data) != declaration.size_bytes
        or actual_sha256 != declaration.sha256
    ):
        raise _DependencyAcquisitionFailure(
            "dependency_acquisition_declaration_identity_changed",
            "initial_declaration",
            "Committed initial dependency declaration identity changed.",
            expected=f"{declaration.git_mode}:blob:{declaration.git_object_id}:{declaration.size_bytes}:{declaration.sha256}",
            actual=f"{mode}:{object_type}:{object_id}:{len(data)}:{actual_sha256}",
        )
    return _declaration_contract(declaration)

def _source_authority_contract() -> DeveloperTaskExecutionDependencyAcquisitionSourceAuthorityContract:
    authority = _architecture_section("source_authority")
    network = _architecture_section("network_model")
    resolver_output = _architecture_section("resolver_output")

    simple = authority.get("simple_api")
    artifacts = authority.get("artifacts")
    upstream = network.get("upstream_origins")
    canonical_url = network.get("canonical_url_rules")
    broker = network.get("broker")
    if (
        not isinstance(simple, Mapping)
        or not isinstance(artifacts, Mapping)
        or not isinstance(upstream, Mapping)
        or not isinstance(canonical_url, Mapping)
        or not isinstance(broker, Mapping)
    ):
        raise RuntimeError("RC043 source/network authority policy is invalid")

    provenance_origins = upstream.get("provenance_initial")
    if not isinstance(provenance_origins, tuple) or provenance_origins != (
        "https://pypi.org:443",
    ):
        raise RuntimeError("RC043 provenance-origin policy is invalid")

    return DeveloperTaskExecutionDependencyAcquisitionSourceAuthorityContract(
        simple_origin=str(simple["origin"]),
        simple_path_template=str(canonical_url["simple_project_path"]),
        simple_media_type=str(simple["media_type"]),
        simple_supported_major=int(simple["supported_major"]),
        simple_minimum_minor=int(simple["minimum_minor"]),
        artifact_origin=str(artifacts["origin"]),
        provenance_initial_origin=provenance_origins[0],
        redirects=int(canonical_url["redirects_allowed"]),
        automatic_retries=int(broker["automatic_retries"]),
        wheel_only=bool(artifacts["wheel_only"]),
        sha256_required=bool(
            artifacts["filename_size_declared_sha256_actual_sha256_must_match"]
        ),
        yanked_allowed=bool(artifacts["yanked"]),
        prerelease_allowed=bool(artifacts["pre_release"]),
        sdist_allowed=bool(artifacts["sdist"]),
        local_build_allowed=bool(artifacts["local_build"]),
        direct_url_allowed=bool(artifacts["direct_url"]),
        extra_index_allowed=bool(artifacts["extra_index"]),
        host_cache_authority_allowed=bool(artifacts["host_cache"]),
        resolver_output_authority=bool(resolver_output["authority"]),
    )

def _bounds_contract() -> DeveloperTaskExecutionDependencyAcquisitionBoundsContract:
    bounds = _architecture_section("bounds")
    items: list[tuple[str, int]] = []
    for key, value in bounds.items():
        if isinstance(value, bool):
            raise RuntimeError(f"RC043 acquisition bound is boolean: {key}")
        if isinstance(value, int):
            if value <= 0:
                raise RuntimeError(f"RC043 acquisition bound is invalid: {key}={value!r}")
            items.append((str(key), value))
            continue
        if key != "integer_overflow_or_limit_exhaustion" or value != "fail closed":
            raise RuntimeError(f"RC043 acquisition bound semantic is invalid: {key}={value!r}")

    if not items:
        raise RuntimeError("RC043 acquisition numeric bounds are empty")

    return DeveloperTaskExecutionDependencyAcquisitionBoundsContract(
        items=tuple(sorted(items)),
    )

def _contract_fingerprint_payload(
    *,
    head_commit: str,
    dependency_profile_contract_fingerprint: str,
    initial_profile_id: str,
    declaration: DeveloperTaskExecutionDependencyAcquisitionDeclarationContract,
    target: DeveloperTaskExecutionDependencyTargetContract,
    source_authority: DeveloperTaskExecutionDependencyAcquisitionSourceAuthorityContract,
    bounds: DeveloperTaskExecutionDependencyAcquisitionBoundsContract,
) -> dict[str, Any]:
    return {
        "schema_version": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY["schema_version"],
        "policy_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_ID,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_FINGERPRINT,
        "architecture_decision_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_ID,
        "architecture_decision_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT,
        "v1c0b2_decision_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_ID,
        "v1c0b2_decision_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_FINGERPRINT,
        "dependency_profile_policy_id": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_ID,
        "dependency_profile_policy_fingerprint": DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT,
        "head_commit": head_commit,
        "dependency_profile_contract_fingerprint": dependency_profile_contract_fingerprint,
        "initial_profile_id": initial_profile_id,
        "declaration": declaration.to_dict(),
        "target": target.to_dict(),
        "source_authority": source_authority.to_dict(),
        "bounds": bounds.to_dict(),
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
    }


def _expected_target_contract() -> DeveloperTaskExecutionDependencyTargetContract:
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


def _build_failure_report(
    *,
    repository_root: Path,
    head_commit: str,
    dependency_profile_contract_fingerprint: str,
    failure: _DependencyAcquisitionFailure,
) -> DeveloperTaskExecutionDependencyAcquisitionReport:
    issue = DeveloperTaskExecutionDependencyAcquisitionIssue(
        code=failure.code,
        check=failure.check,
        message=str(failure),
        expected=failure.expected,
        actual=failure.actual,
    )
    return DeveloperTaskExecutionDependencyAcquisitionReport(
        policy_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_ID,
        policy_fingerprint=developer_task_execution_dependency_acquisition_policy_fingerprint(),
        architecture_decision_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_ID,
        architecture_decision_fingerprint=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT,
        v1c0b2_decision_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_ID,
        v1c0b2_decision_fingerprint=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_FINGERPRINT,
        dependency_profile_policy_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_ID,
        dependency_profile_policy_fingerprint=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT,
        repository_root=str(repository_root),
        head_commit=head_commit,
        dependency_profile_contract_fingerprint=dependency_profile_contract_fingerprint,
        initial_profile_id="skynetvs-python-base-v1",
        declaration=None,
        target=_expected_target_contract(),
        source_authority=_source_authority_contract(),
        bounds=_bounds_contract(),
        contract_fingerprint="",
        issues=(issue,),
        source_authority_bound=False,
    )


def build_developer_task_execution_dependency_acquisition_contract(
    dependency_profile_report: DeveloperTaskExecutionDependencyProfileReport,
    *,
    project_root: Path,
) -> DeveloperTaskExecutionDependencyAcquisitionReport:
    """Build the V1C3A1A non-network dependency acquisition policy/report contract."""

    policy_errors = validate_developer_task_execution_dependency_acquisition_policy()
    if policy_errors:
        raise RuntimeError(
            "Developer task execution dependency acquisition policy is invalid: "
            + ",".join(policy_errors)
        )

    repository_root = (
        Path(os.path.abspath(os.fspath(project_root)))
        if isinstance(project_root, Path)
        else Path(".")
    )
    head_commit = ""
    profile_contract_fingerprint = ""

    try:
        repository_root, head_commit, profile = _validate_profile_report(
            dependency_profile_report,
            project_root,
        )
        profile_contract_fingerprint = dependency_profile_report.contract_fingerprint
        _verify_v1c3a0_source_lineage(repository_root, head_commit)
        _verify_architecture_lineage(repository_root, head_commit)
        declaration = _verify_selected_declaration(
            repository_root,
            head_commit,
            profile,
        )
        authority = _source_authority_contract()
        bounds = _bounds_contract()
        target = _expected_target_contract()
        contract_fingerprint = _sha256(
            _canonical_json(
                _contract_fingerprint_payload(
                    head_commit=head_commit,
                    dependency_profile_contract_fingerprint=profile_contract_fingerprint,
                    initial_profile_id=profile.profile_id,
                    declaration=declaration,
                    target=target,
                    source_authority=authority,
                    bounds=bounds,
                )
            ).encode("utf-8")
        )
        return DeveloperTaskExecutionDependencyAcquisitionReport(
            policy_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_POLICY_ID,
            policy_fingerprint=developer_task_execution_dependency_acquisition_policy_fingerprint(),
            architecture_decision_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_ID,
            architecture_decision_fingerprint=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_ARCHITECTURE_DECISION_FINGERPRINT,
            v1c0b2_decision_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_ID,
            v1c0b2_decision_fingerprint=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C0B2_DECISION_FINGERPRINT,
            dependency_profile_policy_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_ID,
            dependency_profile_policy_fingerprint=DEVELOPER_TASK_EXECUTION_DEPENDENCY_ACQUISITION_V1C3A0_POLICY_FINGERPRINT,
            repository_root=str(repository_root),
            head_commit=head_commit,
            dependency_profile_contract_fingerprint=profile_contract_fingerprint,
            initial_profile_id=profile.profile_id,
            declaration=declaration,
            target=target,
            source_authority=authority,
            bounds=bounds,
            contract_fingerprint=contract_fingerprint,
            issues=(),
            source_authority_bound=True,
        )
    except _DependencyAcquisitionFailure as failure:
        return _build_failure_report(
            repository_root=repository_root,
            head_commit=head_commit,
            dependency_profile_contract_fingerprint=profile_contract_fingerprint,
            failure=failure,
        )
