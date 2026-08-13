from __future__ import annotations

"""V1B4D process-local same-run trusted runtime lease policy."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_ID,
    RUNTIME_BUNDLE_POLICY_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
    RUNTIME_LOCKED_PTH_SHA256,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_PROBE_SHA256,
    RUNTIME_RUNNER_SHA256,
    RUNTIME_SOURCE_ARCHITECTURE,
    RUNTIME_SOURCE_FINGERPRINT,
    RUNTIME_SOURCE_ID,
    RUNTIME_SOURCE_OUTER_MANIFEST_SHA256,
    RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
    RUNTIME_SOURCE_PYTHON_DLL_SHA256,
    RUNTIME_SOURCE_PYTHON_EXE_SHA256,
    RUNTIME_SOURCE_SHA256,
    RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256,
    RUNTIME_SOURCE_STDLIB_SHA256,
    RUNTIME_SOURCE_VERSION,
    RUNTIME_TREE_MANIFEST_SHA256,
)


RUNTIME_LEASE_POLICY_SCHEMA_VERSION = 1
RUNTIME_LEASE_POLICY_ID = "skynetvs-v1b4d-same-run-runtime-capability-lease-v1"
RUNTIME_LEASE_TTL_SECONDS = 300
RUNTIME_LEASE_SECRET_BYTES = 32
RUNTIME_LEASE_HOST_BOOT_EPOCH_TOLERANCE_SECONDS = 1
RUNTIME_LEASE_CLOCK_ID = "time.monotonic_ns"
RUNTIME_LEASE_POLICY_FINGERPRINT = "76ceaaf139af10814a403d24fca7455a61db78f095e80d390b360417354e8c18"


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class DeveloperTaskExecutionRuntimeLeasePolicy:
    schema_version: int
    policy_id: str
    ttl_seconds: int
    secret_bytes: int
    host_boot_epoch_tolerance_seconds: int
    clock_id: str
    backend_policy_fingerprint: str
    runtime_source_sha256: str
    runtime_source_fingerprint: str
    runtime_source_policy_fingerprint: str
    runtime_bundle_id: str
    runtime_bundle_policy_fingerprint: str
    runtime_bundle_fingerprint: str
    runtime_tree_manifest_sha256: str
    runtime_manifest_sha256: str
    runtime_file_count: int
    runtime_total_bytes: int
    python_executable_sha256: str
    python_dll_sha256: str
    python_pth_sha256: str
    stdlib_sha256: str
    source_outer_manifest_sha256: str
    source_stdlib_manifest_sha256: str
    runtime_probe_sha256: str
    runtime_runner_sha256: str
    launch_contract_fingerprint: str
    runtime_attestation_policy_fingerprint: str
    runtime_attestation_payload_fingerprint: str

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.to_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "ttl_seconds": self.ttl_seconds,
            "secret_bytes": self.secret_bytes,
            "host_boot_epoch_tolerance_seconds": self.host_boot_epoch_tolerance_seconds,
            "clock_id": self.clock_id,
            "backend_policy_fingerprint": self.backend_policy_fingerprint,
            "runtime": {
                "source_id": RUNTIME_SOURCE_ID,
                "source_version": RUNTIME_SOURCE_VERSION,
                "source_architecture": RUNTIME_SOURCE_ARCHITECTURE,
                "source_sha256": self.runtime_source_sha256,
                "source_fingerprint": self.runtime_source_fingerprint,
                "source_policy_fingerprint": self.runtime_source_policy_fingerprint,
                "source_outer_manifest_sha256": self.source_outer_manifest_sha256,
                "source_stdlib_manifest_sha256": self.source_stdlib_manifest_sha256,
                "bundle_id": self.runtime_bundle_id,
                "bundle_policy_fingerprint": self.runtime_bundle_policy_fingerprint,
                "bundle_fingerprint": self.runtime_bundle_fingerprint,
                "tree_manifest_sha256": self.runtime_tree_manifest_sha256,
                "runtime_manifest_sha256": self.runtime_manifest_sha256,
                "file_count": self.runtime_file_count,
                "total_bytes": self.runtime_total_bytes,
                "python_executable_sha256": self.python_executable_sha256,
                "python_dll_sha256": self.python_dll_sha256,
                "python_pth_sha256": self.python_pth_sha256,
                "stdlib_sha256": self.stdlib_sha256,
                "runtime_probe_sha256": self.runtime_probe_sha256,
                "runtime_runner_sha256": self.runtime_runner_sha256,
                "launch_contract_fingerprint": self.launch_contract_fingerprint,
            },
            "runtime_attestation": {
                "policy_fingerprint": self.runtime_attestation_policy_fingerprint,
                "payload_fingerprint": self.runtime_attestation_payload_fingerprint,
            },
            "capability": {
                "process_local": True,
                "single_use": True,
                "thread_safe_claim": True,
                "serializable": False,
                "copyable": False,
                "caller_ttl_override": False,
                "caller_clock_override": False,
                "changed_code_authorized": False,
                "execution_authorized": False,
            },
        }


TRUSTED_PYTHON_RUNTIME_LEASE_POLICY_V1 = DeveloperTaskExecutionRuntimeLeasePolicy(
    schema_version=RUNTIME_LEASE_POLICY_SCHEMA_VERSION,
    policy_id=RUNTIME_LEASE_POLICY_ID,
    ttl_seconds=RUNTIME_LEASE_TTL_SECONDS,
    secret_bytes=RUNTIME_LEASE_SECRET_BYTES,
    host_boot_epoch_tolerance_seconds=RUNTIME_LEASE_HOST_BOOT_EPOCH_TOLERANCE_SECONDS,
    clock_id=RUNTIME_LEASE_CLOCK_ID,
    backend_policy_fingerprint=WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
    runtime_source_sha256=RUNTIME_SOURCE_SHA256,
    runtime_source_fingerprint=RUNTIME_SOURCE_FINGERPRINT,
    runtime_source_policy_fingerprint=RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
    runtime_bundle_id=RUNTIME_BUNDLE_ID,
    runtime_bundle_policy_fingerprint=RUNTIME_BUNDLE_POLICY_FINGERPRINT,
    runtime_bundle_fingerprint=RUNTIME_BUNDLE_FINGERPRINT,
    runtime_tree_manifest_sha256=RUNTIME_TREE_MANIFEST_SHA256,
    runtime_manifest_sha256=RUNTIME_MANIFEST_SHA256,
    runtime_file_count=RUNTIME_BUNDLE_FILE_COUNT,
    runtime_total_bytes=RUNTIME_BUNDLE_TOTAL_BYTES,
    python_executable_sha256=RUNTIME_SOURCE_PYTHON_EXE_SHA256,
    python_dll_sha256=RUNTIME_SOURCE_PYTHON_DLL_SHA256,
    python_pth_sha256=RUNTIME_LOCKED_PTH_SHA256,
    stdlib_sha256=RUNTIME_SOURCE_STDLIB_SHA256,
    source_outer_manifest_sha256=RUNTIME_SOURCE_OUTER_MANIFEST_SHA256,
    source_stdlib_manifest_sha256=RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256,
    runtime_probe_sha256=RUNTIME_PROBE_SHA256,
    runtime_runner_sha256=RUNTIME_RUNNER_SHA256,
    launch_contract_fingerprint=RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
    runtime_attestation_policy_fingerprint=RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
    runtime_attestation_payload_fingerprint=RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
)


def validate_execution_runtime_lease_policy(
    policy: DeveloperTaskExecutionRuntimeLeasePolicy,
) -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(policy, DeveloperTaskExecutionRuntimeLeasePolicy):
        return ("policy_type_invalid",)
    if policy.schema_version != RUNTIME_LEASE_POLICY_SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    if policy.policy_id != RUNTIME_LEASE_POLICY_ID:
        errors.append("policy_id_mismatch")
    if policy.ttl_seconds != RUNTIME_LEASE_TTL_SECONDS:
        errors.append("ttl_mismatch")
    if policy.secret_bytes != RUNTIME_LEASE_SECRET_BYTES:
        errors.append("secret_size_mismatch")
    if policy.host_boot_epoch_tolerance_seconds != RUNTIME_LEASE_HOST_BOOT_EPOCH_TOLERANCE_SECONDS:
        errors.append("boot_tolerance_mismatch")
    if policy.clock_id != RUNTIME_LEASE_CLOCK_ID:
        errors.append("clock_id_mismatch")
    if policy.backend_policy_fingerprint != WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint:
        errors.append("backend_policy_fingerprint_mismatch")
    expected_runtime_values = (
        (policy.runtime_source_sha256, RUNTIME_SOURCE_SHA256, "runtime_source_sha256_mismatch"),
        (policy.runtime_source_fingerprint, RUNTIME_SOURCE_FINGERPRINT, "runtime_source_fingerprint_mismatch"),
        (policy.runtime_source_policy_fingerprint, RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT, "runtime_source_policy_mismatch"),
        (policy.runtime_bundle_id, RUNTIME_BUNDLE_ID, "runtime_bundle_id_mismatch"),
        (policy.runtime_bundle_policy_fingerprint, RUNTIME_BUNDLE_POLICY_FINGERPRINT, "runtime_bundle_policy_mismatch"),
        (policy.runtime_bundle_fingerprint, RUNTIME_BUNDLE_FINGERPRINT, "runtime_bundle_fingerprint_mismatch"),
        (policy.runtime_tree_manifest_sha256, RUNTIME_TREE_MANIFEST_SHA256, "runtime_tree_manifest_mismatch"),
        (policy.runtime_manifest_sha256, RUNTIME_MANIFEST_SHA256, "runtime_manifest_mismatch"),
        (policy.runtime_file_count, RUNTIME_BUNDLE_FILE_COUNT, "runtime_file_count_mismatch"),
        (policy.runtime_total_bytes, RUNTIME_BUNDLE_TOTAL_BYTES, "runtime_total_bytes_mismatch"),
        (policy.python_executable_sha256, RUNTIME_SOURCE_PYTHON_EXE_SHA256, "python_executable_mismatch"),
        (policy.python_dll_sha256, RUNTIME_SOURCE_PYTHON_DLL_SHA256, "python_dll_mismatch"),
        (policy.python_pth_sha256, RUNTIME_LOCKED_PTH_SHA256, "python_pth_mismatch"),
        (policy.stdlib_sha256, RUNTIME_SOURCE_STDLIB_SHA256, "stdlib_mismatch"),
        (policy.source_outer_manifest_sha256, RUNTIME_SOURCE_OUTER_MANIFEST_SHA256, "outer_manifest_mismatch"),
        (policy.source_stdlib_manifest_sha256, RUNTIME_SOURCE_STDLIB_MANIFEST_SHA256, "stdlib_manifest_mismatch"),
        (policy.runtime_probe_sha256, RUNTIME_PROBE_SHA256, "runtime_probe_mismatch"),
        (policy.runtime_runner_sha256, RUNTIME_RUNNER_SHA256, "runtime_runner_mismatch"),
        (policy.launch_contract_fingerprint, RUNTIME_LAUNCH_CONTRACT_FINGERPRINT, "launch_contract_mismatch"),
        (policy.runtime_attestation_policy_fingerprint, RUNTIME_ATTESTATION_POLICY_FINGERPRINT, "attestation_policy_mismatch"),
        (policy.runtime_attestation_payload_fingerprint, RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT, "attestation_payload_mismatch"),
    )
    for actual, expected, code in expected_runtime_values:
        if actual != expected:
            errors.append(code)
    if policy.fingerprint != RUNTIME_LEASE_POLICY_FINGERPRINT:
        errors.append("policy_fingerprint_mismatch")
    return tuple(errors)
