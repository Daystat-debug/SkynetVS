from __future__ import annotations

"""Canonical policy for the SkynetVS Windows Sandbox execution backend."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any


EXECUTION_BACKEND_POLICY_SCHEMA_VERSION = 1
WINDOWS_SANDBOX_BACKEND_ID = "traditional_wsb_logoncommand_v1"
WINDOWS_SANDBOX_EXECUTABLE_NAME = "WindowsSandbox.exe"


@dataclass(frozen=True)
class DeveloperTaskExecutionBackendPolicy:
    """Immutable policy that future executable checks must satisfy exactly."""

    schema_version: int
    backend_id: str
    minimum_windows_build: int
    minimum_sandbox_executable_build: int
    supported_architectures: tuple[str, ...]
    required_process_bitness: int
    sandbox_executable_name: str
    wsb_cli_required: bool
    single_instance_required: bool
    vgpu: str
    networking: str
    audio_input: str
    video_input: str
    protected_client: str
    printer_redirection: str
    clipboard_redirection: str
    memory_mb: int
    input_sandbox_path: str
    output_sandbox_path: str
    input_read_only: bool
    output_read_only: bool
    ipv4_probe_required: bool
    ipv6_probe_required: bool
    host_fallback_allowed: bool
    arbitrary_shell_allowed: bool
    dependency_install_allowed: bool
    patched_code_allowed_during_capability_gate: bool
    result_authentication: str
    worker_isolation: str
    python_runtime_strategy: str
    attestation_ttl_seconds: int
    max_result_bytes: int
    launch_timeout_seconds: int
    shutdown_grace_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "backend_id": self.backend_id,
            "minimum_windows_build": self.minimum_windows_build,
            "minimum_sandbox_executable_build": (
                self.minimum_sandbox_executable_build
            ),
            "supported_architectures": list(self.supported_architectures),
            "required_process_bitness": self.required_process_bitness,
            "sandbox_executable_name": self.sandbox_executable_name,
            "wsb_cli_required": self.wsb_cli_required,
            "single_instance_required": self.single_instance_required,
            "wsb_controls": {
                "vgpu": self.vgpu,
                "networking": self.networking,
                "audio_input": self.audio_input,
                "video_input": self.video_input,
                "protected_client": self.protected_client,
                "printer_redirection": self.printer_redirection,
                "clipboard_redirection": self.clipboard_redirection,
                "memory_mb": self.memory_mb,
            },
            "mappings": {
                "input_sandbox_path": self.input_sandbox_path,
                "output_sandbox_path": self.output_sandbox_path,
                "input_read_only": self.input_read_only,
                "output_read_only": self.output_read_only,
            },
            "network_evidence": {
                "ipv4_probe_required": self.ipv4_probe_required,
                "ipv6_probe_required": self.ipv6_probe_required,
            },
            "prohibitions": {
                "host_fallback_allowed": self.host_fallback_allowed,
                "arbitrary_shell_allowed": self.arbitrary_shell_allowed,
                "dependency_install_allowed": self.dependency_install_allowed,
                "patched_code_allowed_during_capability_gate": (
                    self.patched_code_allowed_during_capability_gate
                ),
            },
            "future_execution_boundary": {
                "result_authentication": self.result_authentication,
                "worker_isolation": self.worker_isolation,
                "python_runtime_strategy": self.python_runtime_strategy,
            },
            "limits": {
                "attestation_ttl_seconds": self.attestation_ttl_seconds,
                "max_result_bytes": self.max_result_bytes,
                "launch_timeout_seconds": self.launch_timeout_seconds,
                "shutdown_grace_seconds": self.shutdown_grace_seconds,
            },
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


WINDOWS_SANDBOX_EXECUTION_POLICY_V1 = DeveloperTaskExecutionBackendPolicy(
    schema_version=EXECUTION_BACKEND_POLICY_SCHEMA_VERSION,
    backend_id=WINDOWS_SANDBOX_BACKEND_ID,
    minimum_windows_build=26100,
    minimum_sandbox_executable_build=26100,
    supported_architectures=("AMD64", "X86_64"),
    required_process_bitness=64,
    sandbox_executable_name=WINDOWS_SANDBOX_EXECUTABLE_NAME,
    wsb_cli_required=False,
    single_instance_required=True,
    vgpu="Disable",
    networking="Disable",
    audio_input="Disable",
    video_input="Disable",
    protected_client="Enable",
    printer_redirection="Disable",
    clipboard_redirection="Disable",
    memory_mb=4096,
    input_sandbox_path=r"C:\SkynetVS\Input",
    output_sandbox_path=r"C:\SkynetVS\Output",
    input_read_only=True,
    output_read_only=False,
    ipv4_probe_required=True,
    ipv6_probe_required=True,
    host_fallback_allowed=False,
    arbitrary_shell_allowed=False,
    dependency_install_allowed=False,
    patched_code_allowed_during_capability_gate=False,
    result_authentication="ecdsa_p256_two_phase_v1",
    worker_isolation="system_controller_standard_user_job_v1",
    python_runtime_strategy="pinned_read_only_runtime_bundle_v1",
    attestation_ttl_seconds=300,
    max_result_bytes=65536,
    launch_timeout_seconds=180,
    shutdown_grace_seconds=30,
)


def validate_execution_backend_policy(
    policy: DeveloperTaskExecutionBackendPolicy,
) -> tuple[str, ...]:
    """Return deterministic policy errors without mutating host state."""

    errors: list[str] = []

    if not isinstance(policy, DeveloperTaskExecutionBackendPolicy):
        return ("policy_type_invalid",)

    if policy.schema_version != EXECUTION_BACKEND_POLICY_SCHEMA_VERSION:
        errors.append("policy_schema_invalid")
    if policy.backend_id != WINDOWS_SANDBOX_BACKEND_ID:
        errors.append("policy_backend_invalid")
    if policy.minimum_windows_build < 26100:
        errors.append("policy_windows_build_invalid")
    if policy.minimum_sandbox_executable_build < 26100:
        errors.append("policy_executable_build_invalid")
    if policy.supported_architectures != ("AMD64", "X86_64"):
        errors.append("policy_architectures_invalid")
    if policy.required_process_bitness != 64:
        errors.append("policy_process_bitness_invalid")
    if policy.sandbox_executable_name != WINDOWS_SANDBOX_EXECUTABLE_NAME:
        errors.append("policy_executable_name_invalid")
    if policy.wsb_cli_required:
        errors.append("policy_wsb_cli_invalid")
    if not policy.single_instance_required:
        errors.append("policy_single_instance_invalid")

    expected_controls = (
        policy.vgpu,
        policy.networking,
        policy.audio_input,
        policy.video_input,
        policy.protected_client,
        policy.printer_redirection,
        policy.clipboard_redirection,
    )
    if expected_controls != (
        "Disable",
        "Disable",
        "Disable",
        "Disable",
        "Enable",
        "Disable",
        "Disable",
    ):
        errors.append("policy_wsb_controls_invalid")

    if policy.memory_mb != 4096:
        errors.append("policy_memory_invalid")
    if policy.input_sandbox_path != r"C:\SkynetVS\Input":
        errors.append("policy_input_path_invalid")
    if policy.output_sandbox_path != r"C:\SkynetVS\Output":
        errors.append("policy_output_path_invalid")
    if not policy.input_read_only or policy.output_read_only:
        errors.append("policy_mapping_permissions_invalid")
    if not policy.ipv4_probe_required or not policy.ipv6_probe_required:
        errors.append("policy_network_evidence_invalid")

    if any((
        policy.host_fallback_allowed,
        policy.arbitrary_shell_allowed,
        policy.dependency_install_allowed,
        policy.patched_code_allowed_during_capability_gate,
    )):
        errors.append("policy_prohibitions_invalid")

    if policy.result_authentication != "ecdsa_p256_two_phase_v1":
        errors.append("policy_result_authentication_invalid")
    if policy.worker_isolation != "system_controller_standard_user_job_v1":
        errors.append("policy_worker_isolation_invalid")
    if policy.python_runtime_strategy != "pinned_read_only_runtime_bundle_v1":
        errors.append("policy_python_runtime_invalid")

    if policy.attestation_ttl_seconds != 300:
        errors.append("policy_attestation_ttl_invalid")
    if policy.max_result_bytes != 65536:
        errors.append("policy_result_limit_invalid")
    if policy.launch_timeout_seconds != 180:
        errors.append("policy_launch_timeout_invalid")
    if policy.shutdown_grace_seconds != 30:
        errors.append("policy_shutdown_grace_invalid")

    return tuple(errors)
