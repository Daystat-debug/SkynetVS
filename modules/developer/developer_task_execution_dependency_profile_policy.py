from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_toolchain_observation_policy import (
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT as _CURRENT_TOOLCHAIN_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID as _CURRENT_TOOLCHAIN_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_REQUIREMENT_SYNTAX as _CURRENT_TOOLCHAIN_REQUIREMENT_SYNTAX,
)


DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_ID = (
    "skynetvs-v1c3a0-dependency-profile-target-contract-v1"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_SOURCE_KIND = (
    "verified_v1c0b1_requirement_evidence_v1"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_REQUIREMENT_SYNTAX = (
    "strict_simple_requirements_v1"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_TOOLCHAIN_POLICY_ID = (
    "skynetvs-v1c0b1-canonical-host-toolchain-observation-v1"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_TOOLCHAIN_POLICY_FINGERPRINT = (
    "24a50de152d12ee0fd76cdd7e13a0a031531945688bd1b3eddb7ec6a82fc8fb4"
)
DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_FINGERPRINT = "370e5d2c246be240b9d1a47fdebcc1250302155ea0e6128b6580079d5691748a"


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyRequirementPolicyEntry:
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
class DeveloperTaskExecutionDependencyDeclarationPolicy:
    path: str
    kind: str
    git_mode: str
    git_object_id: str
    size_bytes: int
    sha256: str
    entries: tuple[DeveloperTaskExecutionDependencyRequirementPolicyEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "git_mode": self.git_mode,
            "git_object_id": self.git_object_id,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "entries": [item.to_dict() for item in self.entries],
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyProfilePolicyEntry:
    profile_id: str
    declaration_paths: tuple[str, ...]
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
            "declaration_paths": list(self.declaration_paths),
            "composition": self.composition,
            "base_profile_id": self.base_profile_id,
            "optional_overlay": self.optional_overlay,
            "default_enabled": self.default_enabled,
            "initial_v1c3a_selected": self.initial_v1c3a_selected,
            "initial_v1c3b_selected": self.initial_v1c3b_selected,
            "requested_extras": list(self.requested_extras),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionDependencyTargetPolicy:
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
class DeveloperTaskExecutionDependencyProfilePolicy:
    schema_version: int
    policy_id: str
    source_kind: str
    toolchain_policy_id: str
    toolchain_policy_fingerprint: str
    requirement_syntax: str
    declarations: tuple[DeveloperTaskExecutionDependencyDeclarationPolicy, ...]
    profiles: tuple[DeveloperTaskExecutionDependencyProfilePolicyEntry, ...]
    initial_profile_id: str
    target: DeveloperTaskExecutionDependencyTargetPolicy
    source_authority_selected: bool
    network_used: bool
    artifact_download_attempted: bool
    dependency_install_attempted: bool
    dependency_executed: bool
    sandbox_launched: bool
    candidate_interpreter_executed: bool
    reusable_lease_issued: bool
    execution_authorized: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "source_kind": self.source_kind,
            "toolchain_policy_id": self.toolchain_policy_id,
            "toolchain_policy_fingerprint": self.toolchain_policy_fingerprint,
            "requirement_syntax": self.requirement_syntax,
            "declarations": [item.to_dict() for item in self.declarations],
            "profiles": [item.to_dict() for item in self.profiles],
            "initial_profile_id": self.initial_profile_id,
            "target": self.target.to_dict(),
            "prohibitions": {
                "caller_profile_id_allowed": False,
                "caller_declaration_paths_allowed": False,
                "caller_profile_composition_allowed": False,
                "caller_target_allowed": False,
                "caller_requested_extras_allowed": False,
                "caller_resolver_allowed": False,
                "caller_source_url_allowed": False,
                "caller_artifact_url_allowed": False,
                "caller_version_selection_allowed": False,
                "caller_environment_additions_allowed": False,
                "caller_execution_plan_allowed": False,
                "resolver_allowed": False,
                "source_authority_allowed": False,
                "network_allowed": False,
                "artifact_download_allowed": False,
                "dependency_install_allowed": False,
                "dependency_execution_allowed": False,
                "sandbox_launch_allowed": False,
                "candidate_interpreter_execution_allowed": False,
                "reusable_lease_allowed": False,
                "execution_authority_allowed": False,
            },
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


def _entry(
    name: str,
    normalized_name: str,
    specifier: str,
    exact_pin: bool = False,
) -> DeveloperTaskExecutionDependencyRequirementPolicyEntry:
    return DeveloperTaskExecutionDependencyRequirementPolicyEntry(
        name=name,
        normalized_name=normalized_name,
        specifier=specifier,
        exact_pin=exact_pin,
    )


DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY = (
    DeveloperTaskExecutionDependencyProfilePolicy(
        schema_version=DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_SCHEMA_VERSION,
        policy_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_ID,
        source_kind=DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_SOURCE_KIND,
        toolchain_policy_id=DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_TOOLCHAIN_POLICY_ID,
        toolchain_policy_fingerprint=(
            DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_TOOLCHAIN_POLICY_FINGERPRINT
        ),
        requirement_syntax=DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_REQUIREMENT_SYNTAX,
        declarations=(
            DeveloperTaskExecutionDependencyDeclarationPolicy(
                path="requirements.txt",
                kind="requirements",
                git_mode="100644",
                git_object_id="884e9c45de1edd580457bc9fa21ed54e3926a1a7",
                size_bytes=196,
                sha256="9e283f2050b97e229b4600ca2b1339184b96d1cebc8f90730547a4fb790142b4",
                entries=(
                    _entry("vosk", "vosk", ">=0.3.45"),
                    _entry("sounddevice", "sounddevice", ">=0.4.6"),
                    _entry("numpy", "numpy", ">=1.24"),
                    _entry("colorama", "colorama", ">=0.4.6"),
                    _entry("edge-tts", "edge-tts", ">=6.1.12"),
                    _entry("pydub", "pydub", ">=0.25.1"),
                    _entry("scikit-learn", "scikit-learn", ">=1.3.0"),
                    _entry("joblib", "joblib", ">=1.3.0"),
                    _entry("pycaw", "pycaw", ">=20240210"),
                    _entry("comtypes", "comtypes", ">=1.4.0"),
                    _entry("python-dotenv", "python-dotenv", ">=1.0.1"),
                ),
            ),
            DeveloperTaskExecutionDependencyDeclarationPolicy(
                path="requirements-train.txt",
                kind="requirements",
                git_mode="100644",
                git_object_id="eb115e8b083b522dcb895a53a401b7dff6da98de",
                size_bytes=46,
                sha256="65052d0da1b23c12505497325e0064568dcd9c25b368e1cfe1e5be5a12b81ced",
                entries=(
                    _entry("scikit-learn", "scikit-learn", ">=1.3.0"),
                    _entry("joblib", "joblib", ">=1.3.2"),
                    _entry("numpy", "numpy", ">=1.24"),
                ),
            ),
            DeveloperTaskExecutionDependencyDeclarationPolicy(
                path="requirements-whisper.txt",
                kind="requirements",
                git_mode="100644",
                git_object_id="db1d8d463b95d4230ee60abeb9e9eb63ba8cf8ae",
                size_bytes=127,
                sha256="c5bc4d0891d158b7e8ec5c26b6b68dfcb0b60e8414c9f1ba3040993ea390129d",
                entries=(
                    _entry("faster-whisper", "faster-whisper", "==1.2.1", True),
                ),
            ),
        ),
        profiles=(
            DeveloperTaskExecutionDependencyProfilePolicyEntry(
                profile_id="skynetvs-python-base-v1",
                declaration_paths=("requirements.txt",),
                composition="standalone",
                base_profile_id="",
                optional_overlay=False,
                default_enabled=True,
                initial_v1c3a_selected=True,
                initial_v1c3b_selected=True,
                requested_extras=(),
            ),
            DeveloperTaskExecutionDependencyProfilePolicyEntry(
                profile_id="skynetvs-nlu-training-minimal-v1",
                declaration_paths=("requirements-train.txt",),
                composition="standalone_minimal",
                base_profile_id="",
                optional_overlay=False,
                default_enabled=False,
                initial_v1c3a_selected=False,
                initial_v1c3b_selected=False,
                requested_extras=(),
            ),
            DeveloperTaskExecutionDependencyProfilePolicyEntry(
                profile_id="skynetvs-python-base-whisper-v1",
                declaration_paths=("requirements.txt", "requirements-whisper.txt"),
                composition="base_plus_optional_overlay",
                base_profile_id="skynetvs-python-base-v1",
                optional_overlay=True,
                default_enabled=False,
                initial_v1c3a_selected=False,
                initial_v1c3b_selected=False,
                requested_extras=(),
            ),
        ),
        initial_profile_id="skynetvs-python-base-v1",
        target=DeveloperTaskExecutionDependencyTargetPolicy(
            implementation_name="cpython",
            implementation_version="3.13.15",
            python_version="3.13",
            python_full_version="3.13.15",
            os_name="nt",
            sys_platform="win32",
            platform_system="Windows",
            platform_machine="AMD64",
            platform_python_implementation="CPython",
            requested_extras=(),
        ),
        source_authority_selected=False,
        network_used=False,
        artifact_download_attempted=False,
        dependency_install_attempted=False,
        dependency_executed=False,
        sandbox_launched=False,
        candidate_interpreter_executed=False,
        reusable_lease_issued=False,
        execution_authorized=False,
    )
)


def canonical_developer_task_execution_dependency_profile_policy_json(
    policy: DeveloperTaskExecutionDependencyProfilePolicy = (
        DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY
    ),
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionDependencyProfilePolicy):
        raise TypeError("policy must be DeveloperTaskExecutionDependencyProfilePolicy")
    return json.dumps(
        policy.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def developer_task_execution_dependency_profile_policy_fingerprint(
    policy: DeveloperTaskExecutionDependencyProfilePolicy = (
        DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY
    ),
) -> str:
    canonical = canonical_developer_task_execution_dependency_profile_policy_json(policy)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_developer_task_execution_dependency_profile_policy(
    policy: DeveloperTaskExecutionDependencyProfilePolicy = (
        DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY
    ),
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionDependencyProfilePolicy):
        return ("policy_type_invalid",)

    errors: list[str] = []

    if policy.schema_version != DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_SCHEMA_VERSION:
        errors.append("policy_schema_invalid")
    if policy.policy_id != DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_ID:
        errors.append("policy_id_invalid")
    if policy.source_kind != DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_SOURCE_KIND:
        errors.append("policy_source_kind_invalid")
    if policy.toolchain_policy_id != DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_TOOLCHAIN_POLICY_ID:
        errors.append("policy_toolchain_id_invalid")
    if (
        policy.toolchain_policy_fingerprint
        != DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_TOOLCHAIN_POLICY_FINGERPRINT
    ):
        errors.append("policy_toolchain_fingerprint_invalid")
    if policy.requirement_syntax != DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_REQUIREMENT_SYNTAX:
        errors.append("policy_requirement_syntax_invalid")

    # V1C3A0 pins the exact verified V1C0B1 policy lineage.  A later
    # upstream policy/parser change must not silently become contract authority.
    if _CURRENT_TOOLCHAIN_POLICY_ID != DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_TOOLCHAIN_POLICY_ID:
        errors.append("policy_toolchain_id_lineage_changed")
    if (
        _CURRENT_TOOLCHAIN_POLICY_FINGERPRINT
        != DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_TOOLCHAIN_POLICY_FINGERPRINT
    ):
        errors.append("policy_toolchain_fingerprint_lineage_changed")
    if (
        _CURRENT_TOOLCHAIN_REQUIREMENT_SYNTAX
        != DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_REQUIREMENT_SYNTAX
    ):
        errors.append("policy_requirement_syntax_lineage_changed")

    declaration_paths = tuple(item.path for item in policy.declarations)
    if declaration_paths != (
        "requirements.txt",
        "requirements-train.txt",
        "requirements-whisper.txt",
    ):
        errors.append("policy_declaration_order_invalid")
    if len(set(declaration_paths)) != len(declaration_paths):
        errors.append("policy_declaration_duplicate")
    for declaration in policy.declarations:
        if (
            declaration.kind != "requirements"
            or declaration.git_mode != "100644"
            or len(declaration.git_object_id) != 40
            or len(declaration.sha256) != 64
            or declaration.size_bytes <= 0
            or not declaration.entries
        ):
            errors.append("policy_declaration_identity_invalid")
            break
        names = tuple(item.normalized_name for item in declaration.entries)
        if len(set(names)) != len(names):
            errors.append("policy_declaration_entry_duplicate")
            break

    profile_ids = tuple(item.profile_id for item in policy.profiles)
    if profile_ids != (
        "skynetvs-python-base-v1",
        "skynetvs-nlu-training-minimal-v1",
        "skynetvs-python-base-whisper-v1",
    ):
        errors.append("policy_profile_order_invalid")
    if len(set(profile_ids)) != len(profile_ids):
        errors.append("policy_profile_duplicate")
    declaration_set = set(declaration_paths)
    for profile in policy.profiles:
        if not profile.declaration_paths or not set(profile.declaration_paths).issubset(declaration_set):
            errors.append("policy_profile_declaration_invalid")
            break
        if profile.requested_extras:
            errors.append("policy_profile_extras_invalid")
            break

    selected_a = tuple(item.profile_id for item in policy.profiles if item.initial_v1c3a_selected)
    selected_b = tuple(item.profile_id for item in policy.profiles if item.initial_v1c3b_selected)
    if selected_a != (policy.initial_profile_id,) or selected_b != (policy.initial_profile_id,):
        errors.append("policy_initial_profile_invalid")
    if policy.initial_profile_id != "skynetvs-python-base-v1":
        errors.append("policy_initial_profile_invalid")

    target = policy.target
    if target.to_dict() != {
        "implementation_name": "cpython",
        "implementation_version": "3.13.15",
        "python_version": "3.13",
        "python_full_version": "3.13.15",
        "os_name": "nt",
        "sys_platform": "win32",
        "platform_system": "Windows",
        "platform_machine": "AMD64",
        "platform_python_implementation": "CPython",
        "requested_extras": [],
    }:
        errors.append("policy_target_invalid")

    if any(
        (
            policy.source_authority_selected,
            policy.network_used,
            policy.artifact_download_attempted,
            policy.dependency_install_attempted,
            policy.dependency_executed,
            policy.sandbox_launched,
            policy.candidate_interpreter_executed,
            policy.reusable_lease_issued,
            policy.execution_authorized,
        )
    ):
        errors.append("policy_non_authorizing_flags_invalid")

    if (
        developer_task_execution_dependency_profile_policy_fingerprint(policy)
        != DEVELOPER_TASK_EXECUTION_DEPENDENCY_PROFILE_POLICY_FINGERPRINT
    ):
        errors.append("policy_fingerprint_invalid")

    return tuple(errors)
