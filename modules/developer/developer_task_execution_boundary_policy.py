from __future__ import annotations

"""Canonical policy for the V1B3 signed execution-result boundary."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any


SIGNED_BOUNDARY_POLICY_SCHEMA_VERSION = 1
SIGNED_BOUNDARY_ID = "v1b3a_system_controller_signed_boundary_experiment_v1"
SIGNED_BOUNDARY_FINGERPRINT = "9eb7a1373d1814eea37c8213dfeaeb4f4e7d40e7fdb5d8ec40f91f3e2fd8db72"


@dataclass(frozen=True)
class DeveloperTaskExecutionBoundaryPolicy:
    schema_version: int
    backend_id: str
    base_policy_fingerprint: str
    boundary_id: str
    controller_bootstrap: str
    controller_identity_sid: str
    crypto_algorithm: str
    crypto_key_storage: str
    crypto_public_key_format: str
    handshake: str
    input_mapping: str
    control_mapping: str
    output_mapping: str
    ipv4_probe_required: bool
    ipv6_probe_required: bool
    arbitrary_shell_allowed: bool
    dependency_installation_allowed: bool
    host_fallback_allowed: bool
    patched_code_execution_allowed: bool
    worker_account: str
    worker_environment_inherit: bool
    worker_handles_inherit: bool
    worker_job: str
    worker_launch: str
    worker_sid_process_sweep: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "backend_id": self.backend_id,
            "base_policy_fingerprint": self.base_policy_fingerprint,
            "boundary_id": self.boundary_id,
            "controller_bootstrap": self.controller_bootstrap,
            "controller_identity_sid": self.controller_identity_sid,
            "crypto": {
                "algorithm": self.crypto_algorithm,
                "key_storage": self.crypto_key_storage,
                "public_key_format": self.crypto_public_key_format,
            },
            "handshake": self.handshake,
            "mappings": {
                "input": self.input_mapping,
                "control": self.control_mapping,
                "output": self.output_mapping,
            },
            "network": {
                "ipv4_probe_required": self.ipv4_probe_required,
                "ipv6_probe_required": self.ipv6_probe_required,
            },
            "prohibitions": {
                "arbitrary_shell_allowed": self.arbitrary_shell_allowed,
                "dependency_installation_allowed": self.dependency_installation_allowed,
                "host_fallback_allowed": self.host_fallback_allowed,
                "patched_code_execution_allowed": self.patched_code_execution_allowed,
            },
            "worker": {
                "account": self.worker_account,
                "environment_inherit": self.worker_environment_inherit,
                "handles_inherit": self.worker_handles_inherit,
                "job": self.worker_job,
                "launch": self.worker_launch,
                "sid_process_sweep": self.worker_sid_process_sweep,
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

    @property
    def ok(self) -> bool:
        return (
            self.schema_version == SIGNED_BOUNDARY_POLICY_SCHEMA_VERSION
            and self.backend_id == "traditional_wsb_logoncommand_v1"
            and len(self.base_policy_fingerprint) == 64
            and self.boundary_id == SIGNED_BOUNDARY_ID
            and self.controller_bootstrap == "wdag_admin_scheduled_task_system_v1"
            and self.controller_identity_sid == "S-1-5-18"
            and self.crypto_algorithm == "ECDSA_P256_SHA256_CNG"
            and self.crypto_key_storage == "ephemeral_handle_lifetime_only"
            and self.crypto_public_key_format == "EccPublicBlob"
            and self.handshake == "ready_authorize_terminal_v1"
            and self.input_mapping == "read_only"
            and self.control_mapping == "read_only"
            and self.output_mapping == "writable_untrusted"
            and self.ipv4_probe_required
            and self.ipv6_probe_required
            and not self.arbitrary_shell_allowed
            and not self.dependency_installation_allowed
            and not self.host_fallback_allowed
            and not self.patched_code_execution_allowed
            and self.worker_account == "fresh_local_standard_user"
            and not self.worker_environment_inherit
            and not self.worker_handles_inherit
            and self.worker_job == "kill_on_close_no_breakaway"
            and self.worker_launch == "logonuser_createprocessasuser_suspended"
            and self.worker_sid_process_sweep
            and self.fingerprint == SIGNED_BOUNDARY_FINGERPRINT
        )


WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1 = DeveloperTaskExecutionBoundaryPolicy(
    schema_version=SIGNED_BOUNDARY_POLICY_SCHEMA_VERSION,
    backend_id="traditional_wsb_logoncommand_v1",
    base_policy_fingerprint="5c731d5f246929aa1b59f614d2a01371b086244cc09f2c5846d93531b194af21",
    boundary_id=SIGNED_BOUNDARY_ID,
    controller_bootstrap="wdag_admin_scheduled_task_system_v1",
    controller_identity_sid="S-1-5-18",
    crypto_algorithm="ECDSA_P256_SHA256_CNG",
    crypto_key_storage="ephemeral_handle_lifetime_only",
    crypto_public_key_format="EccPublicBlob",
    handshake="ready_authorize_terminal_v1",
    input_mapping="read_only",
    control_mapping="read_only",
    output_mapping="writable_untrusted",
    ipv4_probe_required=True,
    ipv6_probe_required=True,
    arbitrary_shell_allowed=False,
    dependency_installation_allowed=False,
    host_fallback_allowed=False,
    patched_code_execution_allowed=False,
    worker_account="fresh_local_standard_user",
    worker_environment_inherit=False,
    worker_handles_inherit=False,
    worker_job="kill_on_close_no_breakaway",
    worker_launch="logonuser_createprocessasuser_suspended",
    worker_sid_process_sweep=True,
)


class DeveloperTaskExecutionBoundaryPolicyError(ValueError):
    pass


def validate_execution_boundary_policy(
    policy: DeveloperTaskExecutionBoundaryPolicy,
) -> DeveloperTaskExecutionBoundaryPolicy:
    if not isinstance(policy, DeveloperTaskExecutionBoundaryPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionBoundaryPolicy")
    if not policy.ok:
        raise DeveloperTaskExecutionBoundaryPolicyError(
            "Signed execution-boundary policy is invalid."
        )
    return policy
