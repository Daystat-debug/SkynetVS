from __future__ import annotations

"""Locked V1C1A policy for exact patched-workspace snapshots."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any


DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_ID = (
    "skynetvs-v1c1a-canonical-patched-workspace-snapshot-v1"
)
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_FORMAT = "exact_git_result_tree_snapshot_v1"
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SOURCE_AUTHORITY = (
    "developer_task_patch_apply_result_tree"
)
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TREE_MANIFEST_ALGORITHM = (
    "sha256_canonical_sorted_entry_manifest_v1"
)
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_ENTRY_HASH_ALGORITHM = "sha256"
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_ALLOWED_FILE_MODES = ("100644",)
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_FILE_COUNT = 4096
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SINGLE_BLOB_BYTES = 8 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_TOTAL_BYTES = 16 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_PATH_LENGTH = 240
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SEGMENT_LENGTH = 120
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_PATH_DEPTH = 32
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_PATH_UNICODE_NORMALIZATION = "NFC"
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TTL_SECONDS = 300
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SECRET_BYTES = 32
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_CLOCK_ID = "time.monotonic_ns"
DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_FINGERPRINT = (
    "601c727e9b725f1f868a144fa7b975bbb7a35a878c74c2d25bda0a7677a6cd55"
)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class DeveloperTaskExecutionWorkspaceSnapshotPolicy:
    schema_version: int
    policy_id: str
    snapshot_format: str
    source_authority: str
    git_role: str
    entry_object_type: str
    allowed_file_modes: tuple[str, ...]
    tree_manifest_algorithm: str
    entry_hash_algorithm: str
    max_file_count: int
    max_single_blob_bytes: int
    max_total_bytes: int
    max_manifest_bytes: int
    max_path_length: int
    max_segment_length: int
    max_path_depth: int
    path_unicode_normalization: str
    symlinks: str
    gitlinks: str
    non_blob_entries: str
    windows_case_collisions: str
    directory_file_collisions: str
    binary_blob_policy: str
    ttl_seconds: int
    secret_bytes: int
    clock: str
    process_local: bool
    single_use: bool
    serializable: bool
    copyable: bool
    pickleable: bool
    private_exact_bytes: bool
    runtime_lease_input: bool
    network_allowed: bool
    sandbox_launched: bool
    candidate_interpreter_executed: bool
    changed_code_executed: bool
    reusable_lease_issued: bool
    execution_authorized: bool
    absolute_host_paths_are_authority: bool

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.to_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "snapshot_format": self.snapshot_format,
            "source_authority": self.source_authority,
            "git_role": self.git_role,
            "entry_object_type": self.entry_object_type,
            "allowed_file_modes": list(self.allowed_file_modes),
            "tree_manifest_algorithm": self.tree_manifest_algorithm,
            "entry_hash_algorithm": self.entry_hash_algorithm,
            "max_file_count": self.max_file_count,
            "max_single_blob_bytes": self.max_single_blob_bytes,
            "max_total_bytes": self.max_total_bytes,
            "max_manifest_bytes": self.max_manifest_bytes,
            "max_path_length": self.max_path_length,
            "max_segment_length": self.max_segment_length,
            "max_path_depth": self.max_path_depth,
            "path_unicode_normalization": self.path_unicode_normalization,
            "symlinks": self.symlinks,
            "gitlinks": self.gitlinks,
            "non_blob_entries": self.non_blob_entries,
            "windows_case_collisions": self.windows_case_collisions,
            "directory_file_collisions": self.directory_file_collisions,
            "binary_blob_policy": self.binary_blob_policy,
            "ttl_seconds": self.ttl_seconds,
            "secret_bytes": self.secret_bytes,
            "clock": self.clock,
            "process_local": self.process_local,
            "single_use": self.single_use,
            "serializable": self.serializable,
            "copyable": self.copyable,
            "pickleable": self.pickleable,
            "private_exact_bytes": self.private_exact_bytes,
            "runtime_lease_input": self.runtime_lease_input,
            "network_allowed": self.network_allowed,
            "sandbox_launched": self.sandbox_launched,
            "candidate_interpreter_executed": self.candidate_interpreter_executed,
            "changed_code_executed": self.changed_code_executed,
            "reusable_lease_issued": self.reusable_lease_issued,
            "execution_authorized": self.execution_authorized,
            "absolute_host_paths_are_authority": self.absolute_host_paths_are_authority,
        }


DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY = DeveloperTaskExecutionWorkspaceSnapshotPolicy(
    schema_version=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SCHEMA_VERSION,
    policy_id=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_ID,
    snapshot_format=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_FORMAT,
    source_authority=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SOURCE_AUTHORITY,
    git_role="bounded_transport_not_byte_authority",
    entry_object_type="blob",
    allowed_file_modes=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_ALLOWED_FILE_MODES,
    tree_manifest_algorithm=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TREE_MANIFEST_ALGORITHM,
    entry_hash_algorithm=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_ENTRY_HASH_ALGORITHM,
    max_file_count=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_FILE_COUNT,
    max_single_blob_bytes=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SINGLE_BLOB_BYTES,
    max_total_bytes=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_TOTAL_BYTES,
    max_manifest_bytes=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_MANIFEST_BYTES,
    max_path_length=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_PATH_LENGTH,
    max_segment_length=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SEGMENT_LENGTH,
    max_path_depth=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_PATH_DEPTH,
    path_unicode_normalization=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_PATH_UNICODE_NORMALIZATION,
    symlinks="reject",
    gitlinks="reject",
    non_blob_entries="reject",
    windows_case_collisions="reject",
    directory_file_collisions="reject",
    binary_blob_policy="allowed_but_never_selected_by_compile_ast_plan",
    ttl_seconds=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TTL_SECONDS,
    secret_bytes=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SECRET_BYTES,
    clock=DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_CLOCK_ID,
    process_local=True,
    single_use=True,
    serializable=False,
    copyable=False,
    pickleable=False,
    private_exact_bytes=True,
    runtime_lease_input=False,
    network_allowed=False,
    sandbox_launched=False,
    candidate_interpreter_executed=False,
    changed_code_executed=False,
    reusable_lease_issued=False,
    execution_authorized=False,
    absolute_host_paths_are_authority=False,
)


def canonical_developer_task_execution_workspace_snapshot_policy_json(
    policy: DeveloperTaskExecutionWorkspaceSnapshotPolicy = DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY,
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionWorkspaceSnapshotPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionWorkspaceSnapshotPolicy")
    return _canonical_json_bytes(policy.to_dict()).decode("utf-8")


def developer_task_execution_workspace_snapshot_policy_fingerprint(
    policy: DeveloperTaskExecutionWorkspaceSnapshotPolicy = DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY,
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionWorkspaceSnapshotPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionWorkspaceSnapshotPolicy")
    return policy.fingerprint


def validate_developer_task_execution_workspace_snapshot_policy(
    policy: DeveloperTaskExecutionWorkspaceSnapshotPolicy = DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY,
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionWorkspaceSnapshotPolicy):
        return ("policy_type_invalid",)

    errors: list[str] = []
    if policy.schema_version != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SCHEMA_VERSION:
        errors.append("policy_schema_invalid")
    if policy.policy_id != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_ID:
        errors.append("policy_id_invalid")
    if policy.snapshot_format != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_FORMAT:
        errors.append("policy_snapshot_format_invalid")
    if policy.source_authority != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SOURCE_AUTHORITY:
        errors.append("policy_source_authority_invalid")
    if policy.entry_object_type != "blob":
        errors.append("policy_object_type_invalid")
    if policy.allowed_file_modes != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_ALLOWED_FILE_MODES:
        errors.append("policy_modes_invalid")
    if policy.tree_manifest_algorithm != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TREE_MANIFEST_ALGORITHM:
        errors.append("policy_tree_manifest_algorithm_invalid")
    if policy.entry_hash_algorithm != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_ENTRY_HASH_ALGORITHM:
        errors.append("policy_entry_hash_algorithm_invalid")
    if (
        policy.max_file_count != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_FILE_COUNT
        or policy.max_single_blob_bytes != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SINGLE_BLOB_BYTES
        or policy.max_total_bytes != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_TOTAL_BYTES
        or policy.max_manifest_bytes != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_MANIFEST_BYTES
        or policy.max_path_length != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_PATH_LENGTH
        or policy.max_segment_length != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_SEGMENT_LENGTH
        or policy.max_path_depth != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_MAX_PATH_DEPTH
    ):
        errors.append("policy_limits_invalid")
    if policy.max_single_blob_bytes > policy.max_total_bytes:
        errors.append("policy_limits_invalid")
    if policy.path_unicode_normalization != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_PATH_UNICODE_NORMALIZATION:
        errors.append("policy_unicode_normalization_invalid")
    if policy.ttl_seconds != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_TTL_SECONDS:
        errors.append("policy_ttl_invalid")
    if policy.secret_bytes != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_SECRET_BYTES:
        errors.append("policy_secret_size_invalid")
    if policy.clock != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_CLOCK_ID:
        errors.append("policy_clock_invalid")
    if not policy.process_local or not policy.single_use or not policy.private_exact_bytes:
        errors.append("policy_capability_invalid")
    if policy.serializable or policy.copyable or policy.pickleable:
        errors.append("policy_capability_invalid")
    if any((
        policy.runtime_lease_input,
        policy.network_allowed,
        policy.sandbox_launched,
        policy.candidate_interpreter_executed,
        policy.changed_code_executed,
        policy.reusable_lease_issued,
        policy.execution_authorized,
        policy.absolute_host_paths_are_authority,
    )):
        errors.append("policy_authority_flags_invalid")
    if policy.fingerprint != DEVELOPER_TASK_EXECUTION_WORKSPACE_SNAPSHOT_POLICY_FINGERPRINT:
        errors.append("policy_fingerprint_mismatch")
    return tuple(errors)
