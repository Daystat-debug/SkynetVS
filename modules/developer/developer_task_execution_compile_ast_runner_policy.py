from __future__ import annotations

"""V1C2A2 immutable policy for the fixed compile/AST guest runner bundle."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
)


DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_ID = (
    "skynetvs-v1c2a2-fixed-compile-ast-guest-runner-v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT = (
    "825af298ba972e6c12ac0f85572935c7a8bd34ed4ee215cfa2af6e39a7e659c4"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_ID = (
    "v1c2a2_fixed_compile_ast_guest_runner_bundle_v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME = (
    "SkynetVS_V1C2A2_runner.py"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME = (
    "compile_ast_payload.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME = (
    "compile_ast_contract_policy.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME = "request.json"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME = (
    "source_manifest.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME = "result.json"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_INPUT_ROOT = r"C:\SkynetVSInput"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_ROOT = r"C:\SkynetVSRuntime"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROL_ROOT = r"C:\SkynetVSControl"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT = r"C:\SkynetVSOutput"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE = (
    r"C:\SkynetVSRuntime\python.exe"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH = (
    r"C:\SkynetVSInput\SkynetVS_V1C2A2_runner.py"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_PATH = (
    r"C:\SkynetVSInput\compile_ast_payload.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_PATH = (
    r"C:\SkynetVSInput\compile_ast_contract_policy.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_PATH = (
    r"C:\SkynetVSInput\request.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_PATH = (
    r"C:\SkynetVSInput\source_manifest.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_PATH = (
    r"C:\SkynetVSOutput\result.json"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS = (
    "-I",
    "-S",
    "-B",
    "-E",
    "-s",
    "-P",
    "-X",
    "utf8",
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_MAX_BYTES = 128 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_MAX_BYTES = 64 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_WRITE_MODE = "exclusive_create_v1"


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstRunnerPolicy:
    schema_version: int
    policy_id: str
    fingerprint: str
    contract_policy_fingerprint: str
    backend_policy_fingerprint: str
    runtime_bundle_fingerprint: str
    operation: str
    bundle_id: str
    runner_file_name: str
    payload_file_name: str
    contract_policy_file_name: str
    request_file_name: str
    source_manifest_file_name: str
    result_file_name: str
    input_root: str
    source_root: str
    runtime_root: str
    control_root: str
    output_root: str
    runtime_executable: str
    runner_path: str
    payload_path: str
    contract_policy_path: str
    request_path: str
    source_manifest_path: str
    result_path: str
    runtime_flags: tuple[str, ...]
    working_directory: str
    shell: bool
    caller_arguments: bool
    caller_environment: bool
    runner_max_bytes: int
    payload_max_bytes: int
    result_write_mode: str
    runner_imports_project_modules: bool
    runner_accepts_cli_arguments: bool
    runner_uses_network: bool
    runner_installs_dependencies: bool
    runner_executes_code_object: bool
    runner_executes_imports: bool
    runner_executes_top_level: bool
    bytecode_writes: bool
    sandbox_launched_during_bundle_build: bool
    runtime_lease_input: bool
    candidate_interpreter_executed_during_bundle_build: bool
    changed_source_processed_during_bundle_build: bool
    execution_authorized: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "fingerprint": self.fingerprint,
            "contract_policy_fingerprint": self.contract_policy_fingerprint,
            "backend_policy_fingerprint": self.backend_policy_fingerprint,
            "runtime_bundle_fingerprint": self.runtime_bundle_fingerprint,
            "operation": self.operation,
            "bundle_id": self.bundle_id,
            "files": {
                "runner": self.runner_file_name,
                "payload": self.payload_file_name,
                "contract_policy": self.contract_policy_file_name,
                "request": self.request_file_name,
                "source_manifest": self.source_manifest_file_name,
                "result": self.result_file_name,
            },
            "guest_paths": {
                "input_root": self.input_root,
                "source_root": self.source_root,
                "runtime_root": self.runtime_root,
                "control_root": self.control_root,
                "output_root": self.output_root,
                "runtime_executable": self.runtime_executable,
                "runner": self.runner_path,
                "payload": self.payload_path,
                "contract_policy": self.contract_policy_path,
                "request": self.request_path,
                "source_manifest": self.source_manifest_path,
                "result": self.result_path,
            },
            "launch": {
                "runtime_flags": list(self.runtime_flags),
                "working_directory": self.working_directory,
                "shell": self.shell,
                "caller_arguments": self.caller_arguments,
                "caller_environment": self.caller_environment,
            },
            "limits": {
                "runner_max_bytes": self.runner_max_bytes,
                "payload_max_bytes": self.payload_max_bytes,
            },
            "runner_semantics": {
                "result_write_mode": self.result_write_mode,
                "imports_project_modules": self.runner_imports_project_modules,
                "accepts_cli_arguments": self.runner_accepts_cli_arguments,
                "uses_network": self.runner_uses_network,
                "installs_dependencies": self.runner_installs_dependencies,
                "executes_code_object": self.runner_executes_code_object,
                "executes_imports": self.runner_executes_imports,
                "executes_top_level": self.runner_executes_top_level,
                "bytecode_writes": self.bytecode_writes,
            },
            "build_boundary": {
                "sandbox_launched": self.sandbox_launched_during_bundle_build,
                "runtime_lease_input": self.runtime_lease_input,
                "candidate_interpreter_executed": self.candidate_interpreter_executed_during_bundle_build,
                "changed_source_processed": self.changed_source_processed_during_bundle_build,
                "execution_authorized": self.execution_authorized,
            },
        }


def canonical_developer_task_execution_compile_ast_runner_policy_json(
    policy: DeveloperTaskExecutionCompileAstRunnerPolicy,
) -> bytes:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstRunnerPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionCompileAstRunnerPolicy")
    payload = policy.to_dict()
    payload["fingerprint"] = ""
    return _canonical_json_bytes(payload)


def developer_task_execution_compile_ast_runner_policy_fingerprint(
    policy: DeveloperTaskExecutionCompileAstRunnerPolicy,
) -> str:
    return hashlib.sha256(
        canonical_developer_task_execution_compile_ast_runner_policy_json(policy)
    ).hexdigest()


DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_V1 = (
    DeveloperTaskExecutionCompileAstRunnerPolicy(
        schema_version=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_SCHEMA_VERSION,
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_ID,
        fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
        contract_policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        backend_policy_fingerprint=WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
        runtime_bundle_fingerprint=RUNTIME_BUNDLE_FINGERPRINT,
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        bundle_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_ID,
        runner_file_name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME,
        payload_file_name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME,
        contract_policy_file_name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME,
        request_file_name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME,
        source_manifest_file_name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME,
        result_file_name=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
        input_root=DEVELOPER_TASK_EXECUTION_COMPILE_AST_INPUT_ROOT,
        source_root=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
        runtime_root=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_ROOT,
        control_root=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROL_ROOT,
        output_root=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
        runtime_executable=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE,
        runner_path=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH,
        payload_path=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_PATH,
        contract_policy_path=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_PATH,
        request_path=DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_PATH,
        source_manifest_path=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_PATH,
        result_path=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_PATH,
        runtime_flags=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS,
        working_directory=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
        shell=False,
        caller_arguments=False,
        caller_environment=False,
        runner_max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_MAX_BYTES,
        payload_max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_MAX_BYTES,
        result_write_mode=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_WRITE_MODE,
        runner_imports_project_modules=False,
        runner_accepts_cli_arguments=False,
        runner_uses_network=False,
        runner_installs_dependencies=False,
        runner_executes_code_object=False,
        runner_executes_imports=False,
        runner_executes_top_level=False,
        bytecode_writes=False,
        sandbox_launched_during_bundle_build=False,
        runtime_lease_input=False,
        candidate_interpreter_executed_during_bundle_build=False,
        changed_source_processed_during_bundle_build=False,
        execution_authorized=False,
    )
)


def validate_developer_task_execution_compile_ast_runner_policy(
    policy: DeveloperTaskExecutionCompileAstRunnerPolicy = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_V1
    ),
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstRunnerPolicy):
        return ("policy_type_invalid",)
    errors: list[str] = []
    expected = DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_V1
    if policy.schema_version != 1 or policy.policy_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_ID:
        errors.append("policy_identity_invalid")
    if policy.contract_policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT:
        errors.append("contract_policy_invalid")
    if policy.backend_policy_fingerprint != WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint:
        errors.append("backend_policy_invalid")
    if policy.runtime_bundle_fingerprint != RUNTIME_BUNDLE_FINGERPRINT:
        errors.append("runtime_bundle_invalid")
    if policy.operation != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION:
        errors.append("operation_invalid")
    if (
        policy.runner_file_name != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME
        or policy.payload_file_name != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME
        or policy.contract_policy_file_name != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME
        or policy.request_file_name != DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME
        or policy.source_manifest_file_name != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME
        or policy.result_file_name != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME
    ):
        errors.append("file_names_invalid")
    if (
        policy.input_root != DEVELOPER_TASK_EXECUTION_COMPILE_AST_INPUT_ROOT
        or policy.source_root != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT
        or policy.runtime_root != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_ROOT
        or policy.control_root != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROL_ROOT
        or policy.output_root != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT
        or policy.runtime_executable != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE
        or policy.runner_path != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH
        or policy.payload_path != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_PATH
        or policy.contract_policy_path != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_PATH
        or policy.request_path != DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_PATH
        or policy.source_manifest_path != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_PATH
        or policy.result_path != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_PATH
    ):
        errors.append("guest_paths_invalid")
    if policy.runtime_flags != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS or policy.working_directory != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT:
        errors.append("launch_contract_invalid")
    if any((policy.shell, policy.caller_arguments, policy.caller_environment)):
        errors.append("caller_control_invalid")
    if policy.runner_max_bytes != 128 * 1024 or policy.payload_max_bytes != 64 * 1024:
        errors.append("limits_invalid")
    if policy.result_write_mode != "exclusive_create_v1":
        errors.append("result_write_mode_invalid")
    if any((
        policy.runner_imports_project_modules,
        policy.runner_accepts_cli_arguments,
        policy.runner_uses_network,
        policy.runner_installs_dependencies,
        policy.runner_executes_code_object,
        policy.runner_executes_imports,
        policy.runner_executes_top_level,
        policy.bytecode_writes,
        policy.sandbox_launched_during_bundle_build,
        policy.runtime_lease_input,
        policy.candidate_interpreter_executed_during_bundle_build,
        policy.changed_source_processed_during_bundle_build,
        policy.execution_authorized,
    )):
        errors.append("prohibitions_invalid")
    recomputed = developer_task_execution_compile_ast_runner_policy_fingerprint(policy)
    if recomputed != policy.fingerprint:
        errors.append("policy_fingerprint_mismatch")
    return tuple(errors)
