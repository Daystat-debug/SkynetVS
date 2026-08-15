from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from typing import Any


DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID = (
    "skynetvs-v1c0b1-canonical-host-toolchain-observation-v1"
)
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_SOURCE_KIND = "canonical_host_toolchain_observation_v1"
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT = "24a50de152d12ee0fd76cdd7e13a0a031531945688bd1b3eddb7ec6a82fc8fb4"
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIRED_PLATFORM = "win32"
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIREMENT_SYNTAX = "strict_simple_requirements_v1"
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_PROJECT_IMPORT_ROOTS = (
    "modules",
    "tools",
    "train",
)
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_REQUIREMENT_FILES = 128
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_REQUIREMENTS_PER_FILE = 512
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_DISTRIBUTIONS = 512
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_WHEEL_TAGS_PER_DISTRIBUTION = 64
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_GIT_TREE_FILES = 20_000
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_GIT_TREE_TOTAL_BYTES = 1024 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_GIT_FILE_BYTES = 64 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_PROCESS_TIMEOUT_SECONDS = 30.0
DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_ALLOWED_DEPENDENCY_KINDS = (
    "constraints",
    "lock",
    "package_archive",
    "requirements",
)


@dataclass(frozen=True)
class DeveloperTaskExecutionToolchainObservationPolicy:
    schema_version: int
    policy_id: str
    source_kind: str
    required_platform: str
    requirement_syntax: str
    project_import_roots: tuple[str, ...]
    max_requirement_files: int
    max_requirements_per_file: int
    max_distributions: int
    max_wheel_tags_per_distribution: int
    max_git_tree_files: int
    max_git_tree_total_bytes: int
    max_git_file_bytes: int
    process_timeout_seconds: float
    allowed_dependency_kinds: tuple[str, ...]
    source_authority_selected: bool
    artifact_download_attempted: bool
    dependency_install_attempted: bool
    sandbox_launched: bool
    candidate_interpreter_executed: bool
    reusable_lease_issued: bool
    execution_authorized: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "source_kind": self.source_kind,
            "required_platform": self.required_platform,
            "requirement_syntax": self.requirement_syntax,
            "project_import_roots": list(self.project_import_roots),
            "limits": {
                "max_requirement_files": self.max_requirement_files,
                "max_requirements_per_file": self.max_requirements_per_file,
                "max_distributions": self.max_distributions,
                "max_wheel_tags_per_distribution": self.max_wheel_tags_per_distribution,
                "max_git_tree_files": self.max_git_tree_files,
                "max_git_tree_total_bytes": self.max_git_tree_total_bytes,
                "max_git_file_bytes": self.max_git_file_bytes,
                "process_timeout_seconds": self.process_timeout_seconds,
            },
            "allowed_dependency_kinds": list(self.allowed_dependency_kinds),
            "prohibitions": {
                "caller_python_executable_allowed": False,
                "caller_pip_executable_allowed": False,
                "caller_git_executable_allowed": False,
                "caller_git_root_allowed": False,
                "caller_powershell_executable_allowed": False,
                "caller_argv_allowed": False,
                "caller_environment_additions_allowed": False,
                "caller_requirement_list_allowed": False,
                "caller_package_mapping_allowed": False,
                "caller_source_url_allowed": False,
                "caller_source_authority_allowed": False,
                "caller_classification_override_allowed": False,
                "runtime_network_allowed": False,
                "dependency_install_allowed": False,
                "sandbox_launch_allowed": False,
                "candidate_python_execution_allowed": False,
                "host_toolchain_authority_allowed": False,
            },
            "source_authority_selected": self.source_authority_selected,
            "artifact_download_attempted": self.artifact_download_attempted,
            "dependency_install_attempted": self.dependency_install_attempted,
            "sandbox_launched": self.sandbox_launched,
            "candidate_interpreter_executed": self.candidate_interpreter_executed,
            "reusable_lease_issued": self.reusable_lease_issued,
            "execution_authorized": self.execution_authorized,
        }


DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY = DeveloperTaskExecutionToolchainObservationPolicy(
    schema_version=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_SCHEMA_VERSION,
    policy_id=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
    source_kind=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_SOURCE_KIND,
    required_platform=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIRED_PLATFORM,
    requirement_syntax=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIREMENT_SYNTAX,
    project_import_roots=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_PROJECT_IMPORT_ROOTS,
    max_requirement_files=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_REQUIREMENT_FILES,
    max_requirements_per_file=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_REQUIREMENTS_PER_FILE,
    max_distributions=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_DISTRIBUTIONS,
    max_wheel_tags_per_distribution=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_WHEEL_TAGS_PER_DISTRIBUTION,
    max_git_tree_files=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_GIT_TREE_FILES,
    max_git_tree_total_bytes=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_GIT_TREE_TOTAL_BYTES,
    max_git_file_bytes=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_MAX_GIT_FILE_BYTES,
    process_timeout_seconds=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_PROCESS_TIMEOUT_SECONDS,
    allowed_dependency_kinds=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_ALLOWED_DEPENDENCY_KINDS,
    source_authority_selected=False,
    artifact_download_attempted=False,
    dependency_install_attempted=False,
    sandbox_launched=False,
    candidate_interpreter_executed=False,
    reusable_lease_issued=False,
    execution_authorized=False,
)


def canonical_developer_task_execution_toolchain_observation_policy_json(
    policy: DeveloperTaskExecutionToolchainObservationPolicy = DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY,
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionToolchainObservationPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionToolchainObservationPolicy")
    return json.dumps(policy.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def developer_task_execution_toolchain_observation_policy_fingerprint(
    policy: DeveloperTaskExecutionToolchainObservationPolicy = DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY,
) -> str:
    canonical = canonical_developer_task_execution_toolchain_observation_policy_json(policy)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_developer_task_execution_toolchain_observation_policy(
    policy: DeveloperTaskExecutionToolchainObservationPolicy = DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY,
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionToolchainObservationPolicy):
        return ("policy_type_invalid",)

    errors: list[str] = []
    if policy.schema_version != DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_SCHEMA_VERSION:
        errors.append("policy_schema_invalid")
    if policy.policy_id != DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID:
        errors.append("policy_id_invalid")
    if policy.source_kind != DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_SOURCE_KIND:
        errors.append("policy_source_kind_invalid")
    if policy.required_platform != DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIRED_PLATFORM:
        errors.append("policy_platform_invalid")
    if policy.requirement_syntax != DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIREMENT_SYNTAX:
        errors.append("policy_requirement_syntax_invalid")
    if tuple(sorted(set(policy.project_import_roots))) != tuple(sorted(policy.project_import_roots)):
        errors.append("policy_project_import_roots_invalid")
    if policy.max_requirement_files <= 0 or policy.max_requirements_per_file <= 0:
        errors.append("policy_requirement_limits_invalid")
    if policy.max_distributions <= 0 or policy.max_wheel_tags_per_distribution <= 0:
        errors.append("policy_distribution_limits_invalid")
    if policy.max_git_tree_files <= 0 or policy.max_git_tree_total_bytes <= 0 or policy.max_git_file_bytes <= 0:
        errors.append("policy_git_limits_invalid")
    if policy.max_git_file_bytes > policy.max_git_tree_total_bytes:
        errors.append("policy_git_limits_invalid")
    if policy.process_timeout_seconds <= 0:
        errors.append("policy_timeout_invalid")
    if tuple(sorted(set(policy.allowed_dependency_kinds))) != tuple(sorted(policy.allowed_dependency_kinds)):
        errors.append("policy_dependency_kinds_invalid")
    if any(
        (
            policy.source_authority_selected,
            policy.artifact_download_attempted,
            policy.dependency_install_attempted,
            policy.sandbox_launched,
            policy.candidate_interpreter_executed,
            policy.reusable_lease_issued,
            policy.execution_authorized,
        )
    ):
        errors.append("policy_non_authorizing_flags_invalid")
    if developer_task_execution_toolchain_observation_policy_fingerprint(policy) != DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT:
        errors.append("policy_fingerprint_invalid")
    return tuple(errors)
