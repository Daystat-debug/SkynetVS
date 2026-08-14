from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from typing import Any


DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_ID = (
    "skynetvs-v1c0a-canonical-executable-check-inventory-v1"
)
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_SOURCE_KIND = "exact_git_commit_tree_v1"
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_FINGERPRINT = "727cab58c54ba7605b8d25e727140d3a884ccff16e8ced53b4220b0974b3e0e3"
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_PIPELINE_PATH = "tools/pipeline.py"
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_MAX_TRACKED_FILES = 20_000
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_MAX_PYTHON_FILE_BYTES = 2 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_MAX_PYTHON_TOTAL_BYTES = 96 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_MAX_DEPENDENCY_FILE_BYTES = 8 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_MAX_BATCH_BYTES = 128 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_GIT_TIMEOUT_SECONDS = 30.0
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_ALLOWED_REGULAR_MODES = (
    "100644",
    "100755",
)
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_PROCESS_CALLS = (
    "os.popen",
    "os.system",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.run",
)
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_HOST_SENSITIVE_IMPORT_ROOTS = (
    "comtypes",
    "ctypes",
    "pyaudio",
    "pycaw",
    "sounddevice",
    "winreg",
)
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_HOST_SENSITIVE_TEXT_MARKERS = (
    "WindowsSandbox.exe",
    "Get-WindowsOptionalFeature",
    "CoreAudio",
    "IAudioEndpointVolume",
)
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_LOCK_FILE_NAMES = (
    "pipfile.lock",
    "pdm.lock",
    "poetry.lock",
    "pylock.toml",
    "uv.lock",
)
DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_ARCHIVE_SUFFIXES = (
    ".tar.gz",
    ".tgz",
    ".whl",
)


@dataclass(frozen=True)
class DeveloperTaskExecutionEnvironmentInventoryPolicy:
    schema_version: int
    policy_id: str
    source_kind: str
    pipeline_path: str
    max_tracked_files: int
    max_python_file_bytes: int
    max_python_total_bytes: int
    max_dependency_file_bytes: int
    max_batch_bytes: int
    git_timeout_seconds: float
    allowed_regular_modes: tuple[str, ...]
    process_calls: tuple[str, ...]
    host_sensitive_import_roots: tuple[str, ...]
    host_sensitive_text_markers: tuple[str, ...]
    lock_file_names: tuple[str, ...]
    archive_suffixes: tuple[str, ...]
    execution_authorized: bool
    reusable_lease_issued: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "source_kind": self.source_kind,
            "pipeline_path": self.pipeline_path,
            "limits": {
                "max_tracked_files": self.max_tracked_files,
                "max_python_file_bytes": self.max_python_file_bytes,
                "max_python_total_bytes": self.max_python_total_bytes,
                "max_dependency_file_bytes": self.max_dependency_file_bytes,
                "max_batch_bytes": self.max_batch_bytes,
                "git_timeout_seconds": self.git_timeout_seconds,
            },
            "allowed_regular_modes": list(self.allowed_regular_modes),
            "process_calls": list(self.process_calls),
            "host_sensitive_import_roots": list(self.host_sensitive_import_roots),
            "host_sensitive_text_markers": list(self.host_sensitive_text_markers),
            "lock_file_names": list(self.lock_file_names),
            "archive_suffixes": list(self.archive_suffixes),
            "prohibitions": {
                "execution_authorized": self.execution_authorized,
                "reusable_lease_issued": self.reusable_lease_issued,
                "sandbox_launch_allowed": False,
                "candidate_python_execution_allowed": False,
                "dependency_install_allowed": False,
                "host_fallback_allowed": False,
                "caller_file_list_allowed": False,
                "caller_execution_plan_allowed": False,
                "caller_classification_override_allowed": False,
            },
        }


DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY = (
    DeveloperTaskExecutionEnvironmentInventoryPolicy(
        schema_version=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_SCHEMA_VERSION,
        policy_id=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_ID,
        source_kind=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_SOURCE_KIND,
        pipeline_path=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_PIPELINE_PATH,
        max_tracked_files=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_MAX_TRACKED_FILES,
        max_python_file_bytes=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_MAX_PYTHON_FILE_BYTES,
        max_python_total_bytes=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_MAX_PYTHON_TOTAL_BYTES,
        max_dependency_file_bytes=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_MAX_DEPENDENCY_FILE_BYTES,
        max_batch_bytes=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_MAX_BATCH_BYTES,
        git_timeout_seconds=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_GIT_TIMEOUT_SECONDS,
        allowed_regular_modes=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_ALLOWED_REGULAR_MODES,
        process_calls=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_PROCESS_CALLS,
        host_sensitive_import_roots=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_HOST_SENSITIVE_IMPORT_ROOTS,
        host_sensitive_text_markers=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_HOST_SENSITIVE_TEXT_MARKERS,
        lock_file_names=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_LOCK_FILE_NAMES,
        archive_suffixes=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_ARCHIVE_SUFFIXES,
        execution_authorized=False,
        reusable_lease_issued=False,
    )
)


def canonical_developer_task_execution_environment_inventory_policy_json(
    policy: DeveloperTaskExecutionEnvironmentInventoryPolicy = DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY,
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionEnvironmentInventoryPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionEnvironmentInventoryPolicy")

    return json.dumps(
        policy.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def developer_task_execution_environment_inventory_policy_fingerprint(
    policy: DeveloperTaskExecutionEnvironmentInventoryPolicy = DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY,
) -> str:
    canonical = canonical_developer_task_execution_environment_inventory_policy_json(policy)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_developer_task_execution_environment_inventory_policy(
    policy: DeveloperTaskExecutionEnvironmentInventoryPolicy = DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY,
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionEnvironmentInventoryPolicy):
        return ("policy_type_invalid",)

    errors: list[str] = []

    if policy.schema_version != DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_SCHEMA_VERSION:
        errors.append("policy_schema_invalid")
    if policy.policy_id != DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_ID:
        errors.append("policy_id_invalid")
    if policy.source_kind != DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_SOURCE_KIND:
        errors.append("policy_source_kind_invalid")
    if policy.pipeline_path != DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_PIPELINE_PATH:
        errors.append("policy_pipeline_path_invalid")
    if policy.max_tracked_files <= 0:
        errors.append("policy_tracked_file_limit_invalid")
    if policy.max_python_file_bytes <= 0 or policy.max_python_total_bytes < policy.max_python_file_bytes:
        errors.append("policy_python_limits_invalid")
    if policy.max_dependency_file_bytes <= 0:
        errors.append("policy_dependency_limit_invalid")
    if policy.max_batch_bytes < policy.max_python_total_bytes:
        errors.append("policy_batch_limit_invalid")
    if policy.git_timeout_seconds <= 0:
        errors.append("policy_git_timeout_invalid")
    if tuple(sorted(set(policy.allowed_regular_modes))) != tuple(sorted(policy.allowed_regular_modes)):
        errors.append("policy_regular_modes_invalid")
    if tuple(sorted(set(policy.process_calls))) != tuple(sorted(policy.process_calls)):
        errors.append("policy_process_calls_invalid")
    if policy.execution_authorized:
        errors.append("policy_execution_authorization_invalid")
    if policy.reusable_lease_issued:
        errors.append("policy_reusable_lease_invalid")
    if developer_task_execution_environment_inventory_policy_fingerprint(policy) != DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_FINGERPRINT:
        errors.append("policy_fingerprint_invalid")

    return tuple(errors)
