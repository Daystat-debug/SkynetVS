from __future__ import annotations

"""V1C1B immutable policy for the typed compile/AST plan capability."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any


DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID = (
    "skynetvs-v1c1b-typed-compile-ast-plan-capability-v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION = "compile_ast_changed_python_v1"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SNAPSHOT_POLICY_FINGERPRINT = (
    "601c727e9b725f1f868a144fa7b975bbb7a35a878c74c2d25bda0a7677a6cd55"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_COUNT = 20
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_BYTES = 2 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_TOTAL_BYTES = 8 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_REQUIRED_FILE_MODE = "100644"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_ACCEPTED_ENCODINGS = ("utf-8",)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_ACCEPTED_LINE_ENDINGS = ("lf", "none")
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_COMPILE_MODE = "exec"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_AST_MODE = "exec"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_TTL_SECONDS = 300
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SECRET_BYTES = 32
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_CLOCK_ID = "time.monotonic_ns"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT = (
    "f017f401254647002347802c5deba6397bdddf27eaa08d02640dc8389fe80865"
)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstPlanPolicy:
    schema_version: int
    policy_id: str
    fingerprint: str
    operation: str
    snapshot_policy_fingerprint: str
    selection: str
    min_selected_file_count: int
    max_selected_file_count: int
    max_selected_file_bytes: int
    max_selected_total_bytes: int
    required_file_mode: str
    accepted_source_encodings: tuple[str, ...]
    accepted_line_endings: tuple[str, ...]
    nul_bytes: str
    compile_mode: str
    compile_dont_inherit: bool
    compile_optimize: int
    ast_mode: str
    imports_allowed: bool
    top_level_execution_allowed: bool
    bytecode_writes_allowed: bool
    workspace_on_sys_path: bool
    deleted_python_paths: str
    changed_non_python_paths: str
    ttl_seconds: int
    secret_bytes: int
    clock: str
    process_local: bool
    single_use: bool
    serializable: bool
    copyable: bool
    pickleable: bool
    private_selected_exact_bytes: bool
    runtime_lease_input: bool
    network_allowed: bool
    caller_controlled_executable: bool
    caller_controlled_argv: bool
    caller_controlled_paths: bool
    caller_controlled_environment: bool
    caller_controlled_encoding: bool
    caller_controlled_limits: bool
    caller_controlled_runner: bool
    sandbox_launched: bool
    candidate_interpreter_executed: bool
    changed_code_executed: bool
    reusable_lease_issued: bool
    execution_authorized: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "fingerprint": self.fingerprint,
            "operation": self.operation,
            "snapshot_policy_fingerprint": self.snapshot_policy_fingerprint,
            "selection": self.selection,
            "min_selected_file_count": self.min_selected_file_count,
            "max_selected_file_count": self.max_selected_file_count,
            "max_selected_file_bytes": self.max_selected_file_bytes,
            "max_selected_total_bytes": self.max_selected_total_bytes,
            "required_file_mode": self.required_file_mode,
            "accepted_source_encodings": list(self.accepted_source_encodings),
            "accepted_line_endings": list(self.accepted_line_endings),
            "nul_bytes": self.nul_bytes,
            "compile_mode": self.compile_mode,
            "compile_dont_inherit": self.compile_dont_inherit,
            "compile_optimize": self.compile_optimize,
            "ast_mode": self.ast_mode,
            "imports_allowed": self.imports_allowed,
            "top_level_execution_allowed": self.top_level_execution_allowed,
            "bytecode_writes_allowed": self.bytecode_writes_allowed,
            "workspace_on_sys_path": self.workspace_on_sys_path,
            "deleted_python_paths": self.deleted_python_paths,
            "changed_non_python_paths": self.changed_non_python_paths,
            "ttl_seconds": self.ttl_seconds,
            "secret_bytes": self.secret_bytes,
            "clock": self.clock,
            "process_local": self.process_local,
            "single_use": self.single_use,
            "serializable": self.serializable,
            "copyable": self.copyable,
            "pickleable": self.pickleable,
            "private_selected_exact_bytes": self.private_selected_exact_bytes,
            "runtime_lease_input": self.runtime_lease_input,
            "network_allowed": self.network_allowed,
            "caller_controlled_executable": self.caller_controlled_executable,
            "caller_controlled_argv": self.caller_controlled_argv,
            "caller_controlled_paths": self.caller_controlled_paths,
            "caller_controlled_environment": self.caller_controlled_environment,
            "caller_controlled_encoding": self.caller_controlled_encoding,
            "caller_controlled_limits": self.caller_controlled_limits,
            "caller_controlled_runner": self.caller_controlled_runner,
            "sandbox_launched": self.sandbox_launched,
            "candidate_interpreter_executed": self.candidate_interpreter_executed,
            "changed_code_executed": self.changed_code_executed,
            "reusable_lease_issued": self.reusable_lease_issued,
            "execution_authorized": self.execution_authorized,
        }


DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY = DeveloperTaskExecutionCompileAstPlanPolicy(
    schema_version=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SCHEMA_VERSION,
    policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
    fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
    operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
    snapshot_policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SNAPSHOT_POLICY_FINGERPRINT,
    selection="changed_python_paths_present_in_result_tree_only",
    min_selected_file_count=1,
    max_selected_file_count=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_COUNT,
    max_selected_file_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_BYTES,
    max_selected_total_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_TOTAL_BYTES,
    required_file_mode=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_REQUIRED_FILE_MODE,
    accepted_source_encodings=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_ACCEPTED_ENCODINGS,
    accepted_line_endings=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_ACCEPTED_LINE_ENDINGS,
    nul_bytes="reject",
    compile_mode=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_COMPILE_MODE,
    compile_dont_inherit=True,
    compile_optimize=0,
    ast_mode=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_AST_MODE,
    imports_allowed=False,
    top_level_execution_allowed=False,
    bytecode_writes_allowed=False,
    workspace_on_sys_path=False,
    deleted_python_paths="record_only_not_selected",
    changed_non_python_paths="record_only_not_selected",
    ttl_seconds=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_TTL_SECONDS,
    secret_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SECRET_BYTES,
    clock=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_CLOCK_ID,
    process_local=True,
    single_use=True,
    serializable=False,
    copyable=False,
    pickleable=False,
    private_selected_exact_bytes=True,
    runtime_lease_input=False,
    network_allowed=False,
    caller_controlled_executable=False,
    caller_controlled_argv=False,
    caller_controlled_paths=False,
    caller_controlled_environment=False,
    caller_controlled_encoding=False,
    caller_controlled_limits=False,
    caller_controlled_runner=False,
    sandbox_launched=False,
    candidate_interpreter_executed=False,
    changed_code_executed=False,
    reusable_lease_issued=False,
    execution_authorized=False,
)


def canonical_developer_task_execution_compile_ast_plan_policy_json(
    policy: DeveloperTaskExecutionCompileAstPlanPolicy = DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY,
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstPlanPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionCompileAstPlanPolicy")
    return _canonical_json_bytes(policy.to_dict()).decode("utf-8")


def developer_task_execution_compile_ast_plan_policy_fingerprint(
    policy: DeveloperTaskExecutionCompileAstPlanPolicy = DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY,
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstPlanPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionCompileAstPlanPolicy")
    payload = policy.to_dict().copy()
    payload.pop("fingerprint")
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def validate_developer_task_execution_compile_ast_plan_policy(
    policy: DeveloperTaskExecutionCompileAstPlanPolicy = DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY,
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstPlanPolicy):
        return ("policy_type_invalid",)

    errors: list[str] = []
    if policy.schema_version != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SCHEMA_VERSION:
        errors.append("policy_schema_invalid")
    if policy.policy_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID:
        errors.append("policy_id_invalid")
    if policy.fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT:
        errors.append("policy_fingerprint_constant_invalid")
    if policy.operation != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION:
        errors.append("policy_operation_invalid")
    if policy.snapshot_policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SNAPSHOT_POLICY_FINGERPRINT:
        errors.append("policy_snapshot_binding_invalid")
    if (
        policy.min_selected_file_count != 1
        or policy.max_selected_file_count != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_COUNT
        or policy.max_selected_file_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_FILE_BYTES
        or policy.max_selected_total_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_MAX_SELECTED_TOTAL_BYTES
        or policy.max_selected_file_bytes > policy.max_selected_total_bytes
    ):
        errors.append("policy_limits_invalid")
    if policy.required_file_mode != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_REQUIRED_FILE_MODE:
        errors.append("policy_mode_invalid")
    if policy.accepted_source_encodings != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_ACCEPTED_ENCODINGS:
        errors.append("policy_encoding_invalid")
    if policy.accepted_line_endings != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_ACCEPTED_LINE_ENDINGS:
        errors.append("policy_line_endings_invalid")
    if policy.nul_bytes != "reject":
        errors.append("policy_nul_invalid")
    if (
        policy.compile_mode != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_COMPILE_MODE
        or not policy.compile_dont_inherit
        or policy.compile_optimize != 0
        or policy.ast_mode != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_AST_MODE
    ):
        errors.append("policy_compile_contract_invalid")
    if any((
        policy.imports_allowed,
        policy.top_level_execution_allowed,
        policy.bytecode_writes_allowed,
        policy.workspace_on_sys_path,
    )):
        errors.append("policy_execution_surface_invalid")
    if policy.deleted_python_paths != "record_only_not_selected":
        errors.append("policy_selection_invalid")
    if policy.changed_non_python_paths != "record_only_not_selected":
        errors.append("policy_selection_invalid")
    if policy.ttl_seconds != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_TTL_SECONDS:
        errors.append("policy_ttl_invalid")
    if policy.secret_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_SECRET_BYTES:
        errors.append("policy_secret_size_invalid")
    if policy.clock != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_CLOCK_ID:
        errors.append("policy_clock_invalid")
    if not policy.process_local or not policy.single_use or not policy.private_selected_exact_bytes:
        errors.append("policy_capability_invalid")
    if policy.serializable or policy.copyable or policy.pickleable:
        errors.append("policy_capability_invalid")
    if any((
        policy.runtime_lease_input,
        policy.network_allowed,
        policy.caller_controlled_executable,
        policy.caller_controlled_argv,
        policy.caller_controlled_paths,
        policy.caller_controlled_environment,
        policy.caller_controlled_encoding,
        policy.caller_controlled_limits,
        policy.caller_controlled_runner,
        policy.sandbox_launched,
        policy.candidate_interpreter_executed,
        policy.changed_code_executed,
        policy.reusable_lease_issued,
        policy.execution_authorized,
    )):
        errors.append("policy_authority_flags_invalid")
    if developer_task_execution_compile_ast_plan_policy_fingerprint(policy) != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT:
        errors.append("policy_fingerprint_mismatch")
    return tuple(errors)
