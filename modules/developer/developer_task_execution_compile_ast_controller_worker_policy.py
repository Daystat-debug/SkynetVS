from __future__ import annotations

"""V1C2C1 immutable policy for the fixed compile/AST controller-worker bundle.

The Roadmap Change 016 value is retained as an immutable architecture-slice
identity.  The production policy has a separate, reproducible SHA-256 over its
exact canonical semantic payload so the implementation never pretends that an
unavailable historical preimage was verified.
"""

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_compile_ast_claim_transaction_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID,
)
from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
)
from modules.developer.developer_task_execution_compile_ast_runner_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROL_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_INPUT_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_ROOT,
)
from modules.developer.developer_task_execution_compile_ast_verifier_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_ID,
)
from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
    RUNTIME_ATTESTATION_POLICY_ID,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
    RUNTIME_LEASE_POLICY_ID,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
)


DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID = (
    "skynetvs-v1c2c1-fixed-system-controller-standard-user-worker-bundle-v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT = (
    "0a559e9a9bcac241a18b0e3cbe31263f4f01a5a94eaf70ee7d65382297a62baf"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256 = (
    "1d9b1c66bf3971a3fdedfb077ef8deb08467e29acbc4f725d7050e3ae1342091"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID = (
    "skynetvs-v1c2c-active-compile-ast-composition-split-v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT = (
    "56bfd2ca196ca2b6d8f6ad426ea06141fe1535a28a281f0d7661bc8e32ee8ff6"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE = "V1C2C1"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY = (
    "db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec"
)

DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_ID = (
    "v1c2c1_fixed_system_controller_standard_user_worker_payload_bundle_v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME = (
    "compile_ast_controller_worker_policy.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME = "bootstrap.ps1"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME = (
    "SkynetVS_V1C2C1_native_helper.cs"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME = (
    "controller.ps1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME = (
    "SkynetVS_V1C2C1.wsb"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_TASK_PREFIX = "SkynetVS-V1C2C1-"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_USERNAME_PREFIX = "svc2c1"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_SYSTEM_SID = "S-1-5-18"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_MEDIUM_INTEGRITY_RID = 0x2000
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_SYSTEM_INTEGRITY_RID = 0x4000
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_MEMORY_MB = 4096
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ENVIRONMENT_PREFIXES = (
    "PYTHON",
    "PIP_",
    "PYLAUNCHER_",
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ENVIRONMENT_EXACT = (
    "VIRTUAL_ENV",
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_LOCAL_STAGE_ROOT = (
    r"C:\ProgramData\SkynetVS\V1C2C1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_INPUT_TOKEN = (
    "@@SKYNETVS_INPUT_HOST@@"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_RUNTIME_TOKEN = (
    "@@SKYNETVS_RUNTIME_HOST@@"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_CONTROL_TOKEN = (
    "@@SKYNETVS_CONTROL_HOST@@"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_OUTPUT_TOKEN = (
    "@@SKYNETVS_OUTPUT_HOST@@"
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
class DeveloperTaskExecutionCompileAstControllerWorkerPolicy:
    schema_version: int
    policy_id: str
    policy_fingerprint: str
    architecture_decision_id: str
    architecture_decision_fingerprint: str
    architecture_slice: str
    architecture_slice_identity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "architecture_lock": {
                "decision_id": self.architecture_decision_id,
                "decision_fingerprint": self.architecture_decision_fingerprint,
                "slice": self.architecture_slice,
                "slice_identity": self.architecture_slice_identity,
            },
            "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
            "dependencies": {
                "backend": {
                    "backend_id": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.backend_id,
                    "policy_fingerprint": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
                },
                "compile_ast_contract": {
                    "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
                    "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
                },
                "compile_ast_runner": {
                    "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_ID,
                    "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
                    "bundle_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_ID,
                    "bundle_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
                    "runner_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
                    "payload_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
                },
                "compile_ast_verifier": {
                    "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_ID,
                    "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
                },
                "claim_transaction": {
                    "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID,
                    "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
                },
                "runtime": {
                    "bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
                    "launch_contract_fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
                    "attestation_policy_id": RUNTIME_ATTESTATION_POLICY_ID,
                    "attestation_policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
                    "attestation_payload_fingerprint": RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
                    "lease_policy_id": RUNTIME_LEASE_POLICY_ID,
                    "lease_policy_fingerprint": RUNTIME_LEASE_POLICY_FINGERPRINT,
                },
            },
            "payload": {
                "bundle_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_ID,
                "files": [
                    {
                        "file_name": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME,
                        "kind": "policy",
                    },
                    {
                        "file_name": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME,
                        "kind": "trusted_bootstrap",
                    },
                    {
                        "file_name": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME,
                        "kind": "trusted_native_helper",
                    },
                    {
                        "file_name": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME,
                        "kind": "trusted_system_controller",
                    },
                    {
                        "file_name": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME,
                        "kind": "windows_sandbox_template",
                    },
                ],
                "canonical_text": "utf8_lf_no_bom_v1",
                "deterministic": True,
                "caller_parameters_allowed": False,
            },
            "bootstrap": {
                "logon_identity": "WDAGUtilityAccount_administrator",
                "system_controller_sid": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_SYSTEM_SID,
                "mechanism": "one_time_scheduled_task_v1",
                "task_prefix": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_TASK_PREFIX,
                "task_deleted_before_ready": True,
            },
            "mappings": {
                "input": {
                    "guest_root": DEVELOPER_TASK_EXECUTION_COMPILE_AST_INPUT_ROOT,
                    "mode": "read_only",
                },
                "runtime": {
                    "guest_root": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_ROOT,
                    "mode": "read_only",
                },
                "control": {
                    "guest_root": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROL_ROOT,
                    "mode": "read_only",
                },
                "output": {
                    "guest_root": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
                    "mode": "writable_untrusted",
                },
            },
            "worker": {
                "account": "fresh_local_standard_user",
                "username_prefix": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_USERNAME_PREFIX,
                "administrator": False,
                "integrity_rid": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_MEDIUM_INTEGRITY_RID,
                "token_type": "primary",
                "logon": "LogonUserW_LOGON32_LOGON_INTERACTIVE",
                "environment": {
                    "source": "CreateEnvironmentBlock_false",
                    "inherit_controller_environment": False,
                    "scrub_prefixes": list(
                        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ENVIRONMENT_PREFIXES
                    ),
                    "scrub_exact": list(
                        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ENVIRONMENT_EXACT
                    ),
                },
                "launch": {
                    "api": "CreateProcessAsUserW",
                    "application_path": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE,
                    "arguments": [
                        *DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS,
                        DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH,
                    ],
                    "working_directory": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
                    "inherit_handles": False,
                    "create_suspended": True,
                    "assign_to_job_before_resume": True,
                    "is_process_in_job_verified_before_resume": True,
                    "resume_thread_count": 1,
                    "shell_resolution": False,
                },
                "job": {
                    "unnamed": True,
                    "kill_on_close": True,
                    "breakaway_allowed": False,
                    "silent_breakaway_allowed": False,
                    "active_process_limit": DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT,
                    "process_memory_bytes": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES,
                    "job_memory_bytes": DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES,
                },
                "worker_timeout_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
                "sid_process_sweep": "WTSEnumerateProcessesEx_primary_token_sid_v1",
                "quiescence_required": True,
                "exact_account_deletion_required": True,
            },
            "sandbox": {
                "template": "traditional_wsb_logoncommand_v1",
                "memory_mb": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_MEMORY_MB,
                "vgpu": "Disable",
                "networking": "Disable",
                "audio_input": "Disable",
                "video_input": "Disable",
                "protected_client": "Enable",
                "printer_redirection": "Disable",
                "clipboard_redirection": "Disable",
            },
            "timeouts": {
                "ready_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS,
                "authorization_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS,
                "worker_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
                "shutdown_grace_seconds": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS,
            },
            "prohibitions": {
                "claim_transaction_consumption_allowed": False,
                "runtime_lease_claim_allowed": False,
                "source_materialization_allowed": False,
                "runtime_materialization_allowed": False,
                "sandbox_launch_allowed": False,
                "interpreter_execution_allowed": False,
                "changed_source_processing_allowed": False,
                "changed_source_ast_parse_allowed": False,
                "changed_source_compile_allowed": False,
                "changed_code_execution_allowed": False,
                "network_allowed": False,
                "dependency_installation_allowed": False,
                "arbitrary_shell_allowed": False,
                "caller_executable_allowed": False,
                "caller_arguments_allowed": False,
                "caller_environment_allowed": False,
                "caller_worker_identity_allowed": False,
                "caller_job_limits_allowed": False,
                "caller_guest_paths_allowed": False,
                "caller_runner_path_allowed": False,
                "caller_wsb_settings_allowed": False,
                "host_fallback_allowed": False,
            },
            "effects": {
                "sandbox_launched": False,
                "runtime_lease_claimed": False,
                "candidate_interpreter_executed": False,
                "changed_source_processed": False,
                "changed_source_ast_parsed": False,
                "changed_source_compiled": False,
                "changed_code_executed": False,
                "reusable_lease_issued": False,
                "execution_authorized": False,
            },
        }


DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1 = (
    DeveloperTaskExecutionCompileAstControllerWorkerPolicy(
        schema_version=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_SCHEMA_VERSION,
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
        architecture_decision_id=(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID
        ),
        architecture_decision_fingerprint=(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT
        ),
        architecture_slice=(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE
        ),
        architecture_slice_identity=(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY
        ),
    )
)


def canonical_developer_task_execution_compile_ast_controller_worker_policy_json(
    policy: DeveloperTaskExecutionCompileAstControllerWorkerPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1
    ),
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstControllerWorkerPolicy):
        raise TypeError(
            "policy must be DeveloperTaskExecutionCompileAstControllerWorkerPolicy"
        )
    return _canonical_json_bytes(policy.to_dict()).decode("utf-8")


def developer_task_execution_compile_ast_controller_worker_policy_fingerprint(
    policy: DeveloperTaskExecutionCompileAstControllerWorkerPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1
    ),
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstControllerWorkerPolicy):
        raise TypeError(
            "policy must be DeveloperTaskExecutionCompileAstControllerWorkerPolicy"
        )
    payload = policy.to_dict().copy()
    payload.pop("policy_fingerprint")
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def developer_task_execution_compile_ast_controller_worker_policy_bytes(
    policy: DeveloperTaskExecutionCompileAstControllerWorkerPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1
    ),
) -> bytes:
    return (
        canonical_developer_task_execution_compile_ast_controller_worker_policy_json(
            policy
        ).encode("utf-8")
        + b"\n"
    )


def validate_developer_task_execution_compile_ast_controller_worker_policy(
    policy: DeveloperTaskExecutionCompileAstControllerWorkerPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1
    ),
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstControllerWorkerPolicy):
        return ("policy_type_invalid",)

    errors: list[str] = []
    if (
        policy.schema_version
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_SCHEMA_VERSION
        or policy.policy_id
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID
        or policy.architecture_decision_id
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID
        or policy.architecture_decision_fingerprint
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT
        or policy.architecture_slice
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE
        or policy.architecture_slice_identity
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY
    ):
        errors.append("policy_identity_invalid")

    actual_fingerprint = (
        developer_task_execution_compile_ast_controller_worker_policy_fingerprint(
            policy
        )
    )
    if (
        policy.policy_fingerprint
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT
        or actual_fingerprint
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT
    ):
        errors.append("policy_fingerprint_invalid")

    policy_bytes = developer_task_execution_compile_ast_controller_worker_policy_bytes(
        policy
    )
    if (
        hashlib.sha256(policy_bytes).hexdigest()
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256
    ):
        errors.append("policy_bytes_invalid")

    payload = policy.to_dict()
    if payload["operation"] != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION:
        errors.append("operation_invalid")
    if payload["worker"]["job"] != {
        "unnamed": True,
        "kill_on_close": True,
        "breakaway_allowed": False,
        "silent_breakaway_allowed": False,
        "active_process_limit": 1,
        "process_memory_bytes": 512 * 1024 * 1024,
        "job_memory_bytes": 768 * 1024 * 1024,
    }:
        errors.append("job_limits_invalid")
    if payload["worker"]["launch"]["inherit_handles"] is not False:
        errors.append("handle_inheritance_invalid")
    if payload["worker"]["launch"]["create_suspended"] is not True:
        errors.append("suspended_launch_invalid")
    if payload["worker"]["launch"]["assign_to_job_before_resume"] is not True:
        errors.append("job_assignment_invalid")
    if payload["worker"]["environment"] != {
        "source": "CreateEnvironmentBlock_false",
        "inherit_controller_environment": False,
        "scrub_prefixes": ["PYTHON", "PIP_", "PYLAUNCHER_"],
        "scrub_exact": ["VIRTUAL_ENV"],
    }:
        errors.append("environment_policy_invalid")
    if any(payload["prohibitions"].values()):
        errors.append("prohibitions_invalid")
    if any(payload["effects"].values()):
        errors.append("effects_invalid")
    return tuple(errors)



if validate_developer_task_execution_compile_ast_controller_worker_policy():
    raise RuntimeError("V1C2C1 controller-worker policy self-check failed.")
