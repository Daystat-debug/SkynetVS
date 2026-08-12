from __future__ import annotations

"""Pinned V1B4C1 trusted-runtime attestation policy and exact runtime identity."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
    validate_execution_backend_policy,
)
from modules.developer.developer_task_execution_boundary_policy import (
    WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_ID,
    RUNTIME_BUNDLE_POLICY_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
    RUNTIME_LOCKED_PTH_BYTES,
    RUNTIME_LOCKED_PTH_FILE_NAME,
    RUNTIME_LOCKED_PTH_SHA256,
    RUNTIME_MANIFEST_FILE_NAME,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_PROBE_BYTES,
    RUNTIME_PROBE_FILE_NAME,
    RUNTIME_PROBE_SHA256,
    RUNTIME_RUNNER_BYTES,
    RUNTIME_RUNNER_FILE_NAME,
    RUNTIME_RUNNER_SHA256,
    RUNTIME_SOURCE_ARCHITECTURE,
    RUNTIME_SOURCE_FILES,
    RUNTIME_SOURCE_FINGERPRINT,
    RUNTIME_SOURCE_ID,
    RUNTIME_SOURCE_PYTHON_DLL_SHA256,
    RUNTIME_SOURCE_PYTHON_EXE_SHA256,
    RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
    RUNTIME_SOURCE_SHA256,
    RUNTIME_SOURCE_STDLIB_SHA256,
    RUNTIME_SOURCE_VERSION,
    RUNTIME_TREE_MANIFEST_SHA256,
)


RUNTIME_ATTESTATION_POLICY_SCHEMA_VERSION = 1
RUNTIME_ATTESTATION_POLICY_ID = "skynetvs-v1b4c1-runtime-attestation-contract-payload-cpython-3.13.15-v1"
RUNTIME_ATTESTATION_ID = "v1b4c_trusted_python_runtime_attestation_v1"
RUNTIME_ATTESTATION_POLICY_FINGERPRINT = "31c4f8de17e999db2d064a8aca4e95d3e2400f21a229317e83b1d5700d1e3c48"
RUNTIME_ATTESTATION_PARENT_BOUNDARY_FINGERPRINT = WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.fingerprint
RUNTIME_ATTESTATION_TRUSTED_SCOPE = "benign_trusted_runtime_probe_only"

RUNTIME_ATTESTATION_INPUT_ROOT = r"C:\SkynetVSInput"
RUNTIME_ATTESTATION_RUNTIME_ROOT = r"C:\SkynetVSRuntime"
RUNTIME_ATTESTATION_CONTROL_ROOT = r"C:\SkynetVSControl"
RUNTIME_ATTESTATION_OUTPUT_ROOT = r"C:\SkynetVSOutput"
RUNTIME_ATTESTATION_WORKER_RESULT_ROOT = r"C:\ProgramData\SkynetVS\V1B4C\worker-result"
RUNTIME_ATTESTATION_WORKER_RESULT_FILE = "skynetvs_runtime_probe_result.json"

RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS = 120
RUNTIME_ATTESTATION_AUTHORIZATION_TIMEOUT_SECONDS = 90
RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS = 60
RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS = 45


@dataclass(frozen=True)
class DeveloperTaskRuntimeAttestationExpectedFile:
    path: str
    kind: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskRuntimeAttestationPolicy:
    schema_version: int
    policy_id: str
    attestation_id: str
    expected_runtime_files: tuple[DeveloperTaskRuntimeAttestationExpectedFile, ...]

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.to_dict())).hexdigest()

    @property
    def ok(self) -> bool:
        return (
            self.schema_version == RUNTIME_ATTESTATION_POLICY_SCHEMA_VERSION
            and self.policy_id == RUNTIME_ATTESTATION_POLICY_ID
            and self.attestation_id == RUNTIME_ATTESTATION_ID
            and not validate_execution_backend_policy(WINDOWS_SANDBOX_EXECUTION_POLICY_V1)
            and WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.ok
            and RUNTIME_ATTESTATION_PARENT_BOUNDARY_FINGERPRINT
            == WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.fingerprint
            and len(self.expected_runtime_files) == RUNTIME_BUNDLE_FILE_COUNT
            and tuple(item.path for item in self.expected_runtime_files)
            == tuple(sorted(item.path for item in self.expected_runtime_files))
            and len({item.path.casefold() for item in self.expected_runtime_files})
            == len(self.expected_runtime_files)
            and sum(item.size_bytes for item in self.expected_runtime_files)
            == RUNTIME_BUNDLE_TOTAL_BYTES
            and _runtime_tree_manifest_sha256(self.expected_runtime_files)
            == RUNTIME_TREE_MANIFEST_SHA256
            and self.fingerprint == RUNTIME_ATTESTATION_POLICY_FINGERPRINT
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "attestation_id": self.attestation_id,
            "parent": {
                "backend_id": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.backend_id,
                "backend_policy_fingerprint": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
                "historical_signed_boundary_fingerprint": RUNTIME_ATTESTATION_PARENT_BOUNDARY_FINGERPRINT,
            },
            "runtime": {
                "source_id": RUNTIME_SOURCE_ID,
                "version": RUNTIME_SOURCE_VERSION,
                "architecture": RUNTIME_SOURCE_ARCHITECTURE,
                "source_sha256": RUNTIME_SOURCE_SHA256,
                "source_fingerprint": RUNTIME_SOURCE_FINGERPRINT,
                "source_provenance_policy_fingerprint": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
                "bundle_id": RUNTIME_BUNDLE_ID,
                "bundle_policy_fingerprint": RUNTIME_BUNDLE_POLICY_FINGERPRINT,
                "tree_manifest_sha256": RUNTIME_TREE_MANIFEST_SHA256,
                "runtime_manifest_sha256": RUNTIME_MANIFEST_SHA256,
                "bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
                "bundle_file_count": RUNTIME_BUNDLE_FILE_COUNT,
                "bundle_total_bytes": RUNTIME_BUNDLE_TOTAL_BYTES,
                "python_executable_sha256": RUNTIME_SOURCE_PYTHON_EXE_SHA256,
                "python_dll_sha256": RUNTIME_SOURCE_PYTHON_DLL_SHA256,
                "python_pth_sha256": RUNTIME_LOCKED_PTH_SHA256,
                "stdlib_sha256": RUNTIME_SOURCE_STDLIB_SHA256,
                "runtime_probe_sha256": RUNTIME_PROBE_SHA256,
                "runtime_runner_sha256": RUNTIME_RUNNER_SHA256,
                "launch_contract_fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
                "files": [item.to_dict() for item in self.expected_runtime_files],
            },
            "crypto": {
                "algorithm": "ECDSA_P256_SHA256_CNG",
                "key_storage": "ephemeral_handle_lifetime_only",
                "public_key_format": "EccPublicBlob",
            },
            "handshake": "runtime_ready_authorize_terminal_v1",
            "mappings": {
                "input": {"guest_root": RUNTIME_ATTESTATION_INPUT_ROOT, "mode": "read_only"},
                "runtime": {"guest_root": RUNTIME_ATTESTATION_RUNTIME_ROOT, "mode": "read_only"},
                "control": {"guest_root": RUNTIME_ATTESTATION_CONTROL_ROOT, "mode": "read_only"},
                "output": {"guest_root": RUNTIME_ATTESTATION_OUTPUT_ROOT, "mode": "writable_untrusted"},
            },
            "worker": {
                "account": "fresh_local_standard_user",
                "environment": "createenvironmentblock_false_then_scrub_python_pip_launcher_v1",
                "handles_inherit": False,
                "job": "kill_on_close_no_breakaway",
                "launch": "fixed_python_createprocessasuser_suspended_v1",
                "sid_process_sweep": True,
                "runtime_result_root": RUNTIME_ATTESTATION_WORKER_RESULT_ROOT,
            },
            "timeouts": {
                "ready_seconds": RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS,
                "authorization_seconds": RUNTIME_ATTESTATION_AUTHORIZATION_TIMEOUT_SECONDS,
                "runtime_seconds": RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS,
                "shutdown_grace_seconds": RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS,
            },
            "prohibitions": {
                "arbitrary_shell_allowed": False,
                "caller_arguments_allowed": False,
                "caller_environment_allowed": False,
                "dependency_installation_allowed": False,
                "host_fallback_allowed": False,
                "patched_code_execution_allowed": False,
                "workspace_execution_allowed": False,
            },
            "trusted_scope": RUNTIME_ATTESTATION_TRUSTED_SCOPE,
            "execution_authorized": False,
        }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_runtime_manifest_bytes(
    payload_files: tuple[DeveloperTaskRuntimeAttestationExpectedFile, ...],
) -> bytes:
    payload = {
        "schema_version": 1,
        "bundle_id": RUNTIME_BUNDLE_ID,
        "source_id": RUNTIME_SOURCE_ID,
        "source_sha256": RUNTIME_SOURCE_SHA256,
        "source_fingerprint": RUNTIME_SOURCE_FINGERPRINT,
        "source_policy_fingerprint": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
        "bundle_policy_fingerprint": RUNTIME_BUNDLE_POLICY_FINGERPRINT,
        "launch_contract_fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
        "payload_files": [item.to_dict() for item in payload_files],
        "execution_authorized": False,
    }
    return _canonical_json_bytes(payload) + b"\n"


def _build_expected_runtime_files() -> tuple[DeveloperTaskRuntimeAttestationExpectedFile, ...]:
    items: list[DeveloperTaskRuntimeAttestationExpectedFile] = []
    for source in RUNTIME_SOURCE_FILES:
        if source.path == RUNTIME_LOCKED_PTH_FILE_NAME:
            continue
        items.append(
            DeveloperTaskRuntimeAttestationExpectedFile(
                path=source.path,
                kind="source",
                size_bytes=source.size_bytes,
                sha256=source.sha256,
            )
        )

    items.extend(
        (
            DeveloperTaskRuntimeAttestationExpectedFile(
                path=RUNTIME_LOCKED_PTH_FILE_NAME,
                kind="locked_runtime_path",
                size_bytes=len(RUNTIME_LOCKED_PTH_BYTES),
                sha256=RUNTIME_LOCKED_PTH_SHA256,
            ),
            DeveloperTaskRuntimeAttestationExpectedFile(
                path=RUNTIME_PROBE_FILE_NAME,
                kind="trusted_probe",
                size_bytes=len(RUNTIME_PROBE_BYTES),
                sha256=RUNTIME_PROBE_SHA256,
            ),
            DeveloperTaskRuntimeAttestationExpectedFile(
                path=RUNTIME_RUNNER_FILE_NAME,
                kind="trusted_runner",
                size_bytes=len(RUNTIME_RUNNER_BYTES),
                sha256=RUNTIME_RUNNER_SHA256,
            ),
        )
    )
    items.sort(key=lambda item: item.path)

    runtime_manifest = _build_runtime_manifest_bytes(tuple(items))
    if _sha256(runtime_manifest) != RUNTIME_MANIFEST_SHA256:
        raise RuntimeError("Pinned V1B4B runtime manifest bytes changed unexpectedly.")
    items.append(
        DeveloperTaskRuntimeAttestationExpectedFile(
            path=RUNTIME_MANIFEST_FILE_NAME,
            kind="runtime_manifest",
            size_bytes=len(runtime_manifest),
            sha256=RUNTIME_MANIFEST_SHA256,
        )
    )
    return tuple(sorted(items, key=lambda item: item.path))


def _runtime_tree_manifest_sha256(
    files: tuple[DeveloperTaskRuntimeAttestationExpectedFile, ...],
) -> str:
    payload = [
        {"path": item.path, "size_bytes": item.size_bytes, "sha256": item.sha256}
        for item in files
    ]
    return _sha256(_canonical_json_bytes(payload))


RUNTIME_ATTESTATION_EXPECTED_RUNTIME_FILES = _build_expected_runtime_files()

TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1 = DeveloperTaskRuntimeAttestationPolicy(
    schema_version=RUNTIME_ATTESTATION_POLICY_SCHEMA_VERSION,
    policy_id=RUNTIME_ATTESTATION_POLICY_ID,
    attestation_id=RUNTIME_ATTESTATION_ID,
    expected_runtime_files=RUNTIME_ATTESTATION_EXPECTED_RUNTIME_FILES,
)


class DeveloperTaskRuntimeAttestationPolicyError(ValueError):
    pass


def validate_trusted_python_runtime_attestation_policy(
    policy: DeveloperTaskRuntimeAttestationPolicy = TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1,
) -> DeveloperTaskRuntimeAttestationPolicy:
    if policy is not TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1:
        raise DeveloperTaskRuntimeAttestationPolicyError(
            "Only the pinned V1B4C1 runtime-attestation policy is accepted."
        )
    if not policy.ok:
        raise DeveloperTaskRuntimeAttestationPolicyError(
            "Trusted Python runtime-attestation policy failed its canonical self-check."
        )
    return policy
