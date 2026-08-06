from __future__ import annotations

"""Immutable V1B3C trusted worker-isolation bundle."""

import hashlib
import json

from dataclasses import dataclass, field
from typing import Any

from modules.developer.developer_task_execution_boundary_policy import (
    SIGNED_BOUNDARY_ID,
    WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1,
    validate_execution_boundary_policy,
)
from modules.developer.developer_task_execution_boundary_worker_payload import (
    WORKER_NATIVE_HELPER_BYTES,
    WORKER_NATIVE_HELPER_FILE_NAME,
    WORKER_NATIVE_HELPER_SHA256,
    WORKER_PAYLOAD_ENCODING,
    WORKER_PROBE_EXECUTABLE_FILE_NAME,
    WORKER_PROBE_SOURCE_BYTES,
    WORKER_PROBE_SOURCE_FILE_NAME,
    WORKER_PROBE_SOURCE_SHA256,
)


WORKER_BUNDLE_SCHEMA_VERSION = 1
WORKER_BUNDLE_ID = "v1b3c_standard_user_worker_isolation_bundle_v1"
WORKER_ACCOUNT_STRATEGY = "fresh_local_standard_user_exact_sid_v1"
WORKER_TOKEN_STRATEGY = "primary_non_admin_medium_integrity_v1"
WORKER_ENVIRONMENT_STRATEGY = "create_environment_block_no_inherit_v1"
WORKER_HANDLE_STRATEGY = "create_process_as_user_no_handle_inherit_v1"
WORKER_JOB_STRATEGY = "create_suspended_assign_before_resume_kill_on_close_v1"
WORKER_PROCESS_SWEEP_STRATEGY = "wts_primary_token_sid_bounded_quiescence_v1"
WORKER_SECRET_STRATEGY = "unmanaged_memory_zero_after_logon_v1"
WORKER_ACL_STRATEGY = "protected_system_owner_least_privilege_worker_dirs_v1"
WORKER_PAYLOAD_SCOPE = "fixed_benign_self_child_probe_only"
WORKER_BUNDLE_FINGERPRINT = "a15433a891aade5647f4ae9f5cad41a2fce72e4c6ccd3ba4c86a2794604b81a0"


@dataclass(frozen=True)
class DeveloperTaskExecutionBoundaryWorkerPayload:
    kind: str
    file_name: str
    size_bytes: int
    sha256: str
    encoding: str
    _bytes: bytes = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "file_name": self.file_name,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "encoding": self.encoding,
        }

    def exact_bytes(self) -> bytes:
        return self._bytes


@dataclass(frozen=True)
class DeveloperTaskExecutionBoundaryWorkerBundle:
    schema_version: int
    bundle_id: str
    boundary_id: str
    boundary_fingerprint: str
    account_strategy: str
    token_strategy: str
    environment_strategy: str
    handle_strategy: str
    job_strategy: str
    process_sweep_strategy: str
    secret_strategy: str
    acl_strategy: str
    payload_scope: str
    native_helper: DeveloperTaskExecutionBoundaryWorkerPayload
    worker_probe: DeveloperTaskExecutionBoundaryWorkerPayload
    worker_executable_file_name: str
    bundle_fingerprint: str
    execution_authorized: bool = False

    @property
    def ok(self) -> bool:
        expected_fingerprint = _bundle_fingerprint(
            _bundle_payload(
                schema_version=self.schema_version,
                bundle_id=self.bundle_id,
                boundary_id=self.boundary_id,
                boundary_fingerprint=self.boundary_fingerprint,
                account_strategy=self.account_strategy,
                token_strategy=self.token_strategy,
                environment_strategy=self.environment_strategy,
                handle_strategy=self.handle_strategy,
                job_strategy=self.job_strategy,
                process_sweep_strategy=self.process_sweep_strategy,
                secret_strategy=self.secret_strategy,
                acl_strategy=self.acl_strategy,
                payload_scope=self.payload_scope,
                native_helper=self.native_helper,
                worker_probe=self.worker_probe,
                worker_executable_file_name=self.worker_executable_file_name,
                execution_authorized=self.execution_authorized,
            )
        )
        return (
            self.schema_version == WORKER_BUNDLE_SCHEMA_VERSION
            and self.bundle_id == WORKER_BUNDLE_ID
            and self.boundary_id == SIGNED_BOUNDARY_ID
            and self.boundary_fingerprint
            == WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.fingerprint
            and self.account_strategy == WORKER_ACCOUNT_STRATEGY
            and self.token_strategy == WORKER_TOKEN_STRATEGY
            and self.environment_strategy == WORKER_ENVIRONMENT_STRATEGY
            and self.handle_strategy == WORKER_HANDLE_STRATEGY
            and self.job_strategy == WORKER_JOB_STRATEGY
            and self.process_sweep_strategy == WORKER_PROCESS_SWEEP_STRATEGY
            and self.secret_strategy == WORKER_SECRET_STRATEGY
            and self.acl_strategy == WORKER_ACL_STRATEGY
            and self.payload_scope == WORKER_PAYLOAD_SCOPE
            and self.native_helper.sha256 == WORKER_NATIVE_HELPER_SHA256
            and self.native_helper.exact_bytes() == WORKER_NATIVE_HELPER_BYTES
            and self.worker_probe.sha256 == WORKER_PROBE_SOURCE_SHA256
            and self.worker_probe.exact_bytes() == WORKER_PROBE_SOURCE_BYTES
            and self.worker_executable_file_name == WORKER_PROBE_EXECUTABLE_FILE_NAME
            and self.bundle_fingerprint == expected_fingerprint
            and self.bundle_fingerprint == WORKER_BUNDLE_FINGERPRINT
            and not self.execution_authorized
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "boundary_id": self.boundary_id,
            "boundary_fingerprint": self.boundary_fingerprint,
            "account_strategy": self.account_strategy,
            "token_strategy": self.token_strategy,
            "environment_strategy": self.environment_strategy,
            "handle_strategy": self.handle_strategy,
            "job_strategy": self.job_strategy,
            "process_sweep_strategy": self.process_sweep_strategy,
            "secret_strategy": self.secret_strategy,
            "acl_strategy": self.acl_strategy,
            "payload_scope": self.payload_scope,
            "native_helper": self.native_helper.to_dict(),
            "worker_probe": self.worker_probe.to_dict(),
            "worker_executable_file_name": self.worker_executable_file_name,
            "bundle_fingerprint": self.bundle_fingerprint,
            "execution_authorized": self.execution_authorized,
        }


class DeveloperTaskExecutionBoundaryWorkerError(ValueError):
    pass


def _payload(kind: str, file_name: str, content: bytes, sha256: str) -> DeveloperTaskExecutionBoundaryWorkerPayload:
    return DeveloperTaskExecutionBoundaryWorkerPayload(
        kind=kind,
        file_name=file_name,
        size_bytes=len(content),
        sha256=sha256,
        encoding=WORKER_PAYLOAD_ENCODING,
        _bytes=content,
    )


def _bundle_payload(
    *,
    schema_version: int,
    bundle_id: str,
    boundary_id: str,
    boundary_fingerprint: str,
    account_strategy: str,
    token_strategy: str,
    environment_strategy: str,
    handle_strategy: str,
    job_strategy: str,
    process_sweep_strategy: str,
    secret_strategy: str,
    acl_strategy: str,
    payload_scope: str,
    native_helper: DeveloperTaskExecutionBoundaryWorkerPayload,
    worker_probe: DeveloperTaskExecutionBoundaryWorkerPayload,
    worker_executable_file_name: str,
    execution_authorized: bool,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "bundle_id": bundle_id,
        "boundary_id": boundary_id,
        "boundary_fingerprint": boundary_fingerprint,
        "account_strategy": account_strategy,
        "token_strategy": token_strategy,
        "environment_strategy": environment_strategy,
        "handle_strategy": handle_strategy,
        "job_strategy": job_strategy,
        "process_sweep_strategy": process_sweep_strategy,
        "secret_strategy": secret_strategy,
        "acl_strategy": acl_strategy,
        "payload_scope": payload_scope,
        "native_helper": native_helper.to_dict(),
        "worker_probe": worker_probe.to_dict(),
        "worker_executable_file_name": worker_executable_file_name,
        "execution_authorized": execution_authorized,
    }


def _bundle_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_developer_task_execution_boundary_worker_bundle() -> DeveloperTaskExecutionBoundaryWorkerBundle:
    validate_execution_boundary_policy(WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1)

    native_helper = _payload(
        "native_helper_csharp",
        WORKER_NATIVE_HELPER_FILE_NAME,
        WORKER_NATIVE_HELPER_BYTES,
        WORKER_NATIVE_HELPER_SHA256,
    )
    worker_probe = _payload(
        "benign_worker_probe_csharp",
        WORKER_PROBE_SOURCE_FILE_NAME,
        WORKER_PROBE_SOURCE_BYTES,
        WORKER_PROBE_SOURCE_SHA256,
    )
    payload = _bundle_payload(
        schema_version=WORKER_BUNDLE_SCHEMA_VERSION,
        bundle_id=WORKER_BUNDLE_ID,
        boundary_id=SIGNED_BOUNDARY_ID,
        boundary_fingerprint=WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.fingerprint,
        account_strategy=WORKER_ACCOUNT_STRATEGY,
        token_strategy=WORKER_TOKEN_STRATEGY,
        environment_strategy=WORKER_ENVIRONMENT_STRATEGY,
        handle_strategy=WORKER_HANDLE_STRATEGY,
        job_strategy=WORKER_JOB_STRATEGY,
        process_sweep_strategy=WORKER_PROCESS_SWEEP_STRATEGY,
        secret_strategy=WORKER_SECRET_STRATEGY,
        acl_strategy=WORKER_ACL_STRATEGY,
        payload_scope=WORKER_PAYLOAD_SCOPE,
        native_helper=native_helper,
        worker_probe=worker_probe,
        worker_executable_file_name=WORKER_PROBE_EXECUTABLE_FILE_NAME,
        execution_authorized=False,
    )
    fingerprint = _bundle_fingerprint(payload)
    if fingerprint != WORKER_BUNDLE_FINGERPRINT:
        raise DeveloperTaskExecutionBoundaryWorkerError(
            "V1B3C worker-isolation bundle fingerprint changed unexpectedly."
        )
    bundle = DeveloperTaskExecutionBoundaryWorkerBundle(
        schema_version=WORKER_BUNDLE_SCHEMA_VERSION,
        bundle_id=WORKER_BUNDLE_ID,
        boundary_id=SIGNED_BOUNDARY_ID,
        boundary_fingerprint=WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.fingerprint,
        account_strategy=WORKER_ACCOUNT_STRATEGY,
        token_strategy=WORKER_TOKEN_STRATEGY,
        environment_strategy=WORKER_ENVIRONMENT_STRATEGY,
        handle_strategy=WORKER_HANDLE_STRATEGY,
        job_strategy=WORKER_JOB_STRATEGY,
        process_sweep_strategy=WORKER_PROCESS_SWEEP_STRATEGY,
        secret_strategy=WORKER_SECRET_STRATEGY,
        acl_strategy=WORKER_ACL_STRATEGY,
        payload_scope=WORKER_PAYLOAD_SCOPE,
        native_helper=native_helper,
        worker_probe=worker_probe,
        worker_executable_file_name=WORKER_PROBE_EXECUTABLE_FILE_NAME,
        bundle_fingerprint=fingerprint,
        execution_authorized=False,
    )
    if not bundle.ok:
        raise DeveloperTaskExecutionBoundaryWorkerError(
            "V1B3C worker-isolation bundle failed its canonical self-check."
        )
    return bundle
