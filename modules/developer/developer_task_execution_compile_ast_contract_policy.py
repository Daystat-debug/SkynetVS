from __future__ import annotations

"""V1C2A1 immutable policy for the canonical compile/AST transcript contract."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
)


DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_SCHEMA_VERSION = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID = (
    "skynetvs-v1c2a1-compile-ast-contract-cpython-3.13.15-v1"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT = (
    "a3e7d50e92de8aa0799953874a71ce60b2d141e52791282e5fd38814aa9507bf"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION = "compile_ast_changed_python_v1"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_STRATEGY = "flat_sorted_ordinal_files_v1"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT = r"C:\SkynetVSInput\sources"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_FILE_PATTERN = "source-{ordinal:04d}.py"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_VIRTUAL_FILENAME_PREFIX = "skynetvs://changed/"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUIRED_MODE = "100644"
DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT = 20
DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_BYTES = 2 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_TOTAL_BYTES = 8 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES = 64 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_MAX_BYTES = 64 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZE_MAX_BYTES = 16 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES = 64 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_MAX_BYTES = 128 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES = 192 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES = 64
DEVELOPER_TASK_EXECUTION_COMPILE_AST_SYNTAX_MESSAGE_MAX_CHARS = 512
DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS = 120
DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS = 90
DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS = 60
DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS = 45
DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT = 1
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES = 512 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES = 768 * 1024 * 1024
DEVELOPER_TASK_EXECUTION_COMPILE_AST_STATUSES = (
    "compile_ast_attested_passed",
    "compile_ast_attested_failed",
    "compile_ast_boundary_failed",
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_VERSION = (3, 13, 15)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_MACHINES = ("AMD64", "X86_64")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstContractPolicy:
    schema_version: int
    policy_id: str
    fingerprint: str
    backend_policy_fingerprint: str
    parent_plan_policy_fingerprint: str
    runtime_attestation_policy_fingerprint: str
    runtime_bundle_fingerprint: str
    runtime_lease_policy_fingerprint: str
    operation: str
    canonical_encoding: str
    canonical_line_ending: str
    field_order: str
    json_duplicate_keys: str
    json_floats: str
    json_non_finite_numbers: str
    unknown_fields: str
    signature_algorithm: str
    signature_bytes: int
    request_max_bytes: int
    ready_max_bytes: int
    authorize_max_bytes: int
    source_manifest_max_bytes: int
    result_max_bytes: int
    terminal_max_bytes: int
    source_strategy: str
    source_root: str
    source_file_name_pattern: str
    virtual_filename_prefix: str
    original_path_used_as_guest_filesystem_path: bool
    read_only_mapping: bool
    source_encoding: str
    source_line_endings: tuple[str, ...]
    nul_bytes: str
    required_mode: str
    max_file_count: int
    max_file_bytes: int
    max_total_bytes: int
    runtime_implementation: str
    runtime_version: tuple[int, int, int]
    runtime_architecture_bits: int
    runtime_machines: tuple[str, ...]
    ast_mode: str
    ast_feature_version: tuple[int, int]
    ast_type_comments: bool
    ast_optimize: int
    compile_mode: str
    compile_flags: int
    compile_dont_inherit: bool
    compile_optimize: int
    source_import_statements_may_be_compiled: bool
    source_imports_executed: bool
    top_level_executed: bool
    code_object_executed: bool
    bytecode_writes: bool
    workspace_mapped: bool
    git_mapped: bool
    workspace_on_sys_path: bool
    raw_source_in_result: bool
    syntax_error_source_text_in_result: bool
    syntax_error_message_max_chars: int
    worker_timeout_seconds: int
    ready_timeout_seconds: int
    authorization_timeout_seconds: int
    shutdown_grace_seconds: int
    kill_on_job_close: bool
    active_process_limit: int
    process_memory_bytes: int
    job_memory_bytes: int
    wsb_networking: str
    ipv4_default_route: bool
    ipv6_default_route: bool
    external_tcp: bool
    statuses: tuple[str, ...]
    authentic_syntax_failure_is_valid_evidence: bool
    boundary_evidence_and_check_result_are_separate: bool
    check_passed_requires_all_selected_files: bool
    reusable_lease_issued: bool
    execution_authorized: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "fingerprint": self.fingerprint,
            "backend_policy_fingerprint": self.backend_policy_fingerprint,
            "parent_plan_policy_fingerprint": self.parent_plan_policy_fingerprint,
            "runtime_attestation_policy_fingerprint": self.runtime_attestation_policy_fingerprint,
            "runtime_bundle_fingerprint": self.runtime_bundle_fingerprint,
            "runtime_lease_policy_fingerprint": self.runtime_lease_policy_fingerprint,
            "operation": self.operation,
            "contract": {
                "canonical_encoding": self.canonical_encoding,
                "canonical_line_ending": self.canonical_line_ending,
                "field_order": self.field_order,
                "json_duplicate_keys": self.json_duplicate_keys,
                "json_floats": self.json_floats,
                "json_non_finite_numbers": self.json_non_finite_numbers,
                "unknown_fields": self.unknown_fields,
                "signature_algorithm": self.signature_algorithm,
                "signature_bytes": self.signature_bytes,
                "request_max_bytes": self.request_max_bytes,
                "ready_max_bytes": self.ready_max_bytes,
                "authorize_max_bytes": self.authorize_max_bytes,
                "source_manifest_max_bytes": self.source_manifest_max_bytes,
                "result_max_bytes": self.result_max_bytes,
                "terminal_max_bytes": self.terminal_max_bytes,
            },
            "source_materialization": {
                "strategy": self.source_strategy,
                "source_root": self.source_root,
                "file_name_pattern": self.source_file_name_pattern,
                "virtual_filename_prefix": self.virtual_filename_prefix,
                "original_path_used_as_guest_filesystem_path": self.original_path_used_as_guest_filesystem_path,
                "read_only_mapping": self.read_only_mapping,
                "encoding": self.source_encoding,
                "line_endings": list(self.source_line_endings),
                "nul_bytes": self.nul_bytes,
                "required_mode": self.required_mode,
                "max_file_count": self.max_file_count,
                "max_file_bytes": self.max_file_bytes,
                "max_total_bytes": self.max_total_bytes,
            },
            "runtime": {
                "implementation": self.runtime_implementation,
                "version": list(self.runtime_version),
                "architecture_bits": self.runtime_architecture_bits,
                "machine": list(self.runtime_machines),
            },
            "runner_semantics": {
                "order": [
                    "verify_request_and_manifest",
                    "rehash_exact_bytes",
                    "decode_utf8_strict",
                    "ast_parse",
                    "compile",
                    "write_result_exclusive",
                ],
                "ast": {
                    "mode": self.ast_mode,
                    "feature_version": list(self.ast_feature_version),
                    "type_comments": self.ast_type_comments,
                    "optimize": self.ast_optimize,
                },
                "compile": {
                    "mode": self.compile_mode,
                    "flags": self.compile_flags,
                    "dont_inherit": self.compile_dont_inherit,
                    "optimize": self.compile_optimize,
                },
                "source_import_statements_may_be_compiled": self.source_import_statements_may_be_compiled,
                "source_imports_executed": self.source_imports_executed,
                "top_level_executed": self.top_level_executed,
                "code_object_executed": self.code_object_executed,
                "bytecode_writes": self.bytecode_writes,
                "workspace_mapped": self.workspace_mapped,
                "git_mapped": self.git_mapped,
                "workspace_on_sys_path": self.workspace_on_sys_path,
                "raw_source_in_result": self.raw_source_in_result,
                "syntax_error_source_text_in_result": self.syntax_error_source_text_in_result,
                "syntax_error_message_max_chars": self.syntax_error_message_max_chars,
            },
            "timeouts_seconds": {
                "ready": self.ready_timeout_seconds,
                "authorization": self.authorization_timeout_seconds,
                "worker": self.worker_timeout_seconds,
                "shutdown_grace": self.shutdown_grace_seconds,
            },
            "job_limits": {
                "kill_on_job_close": self.kill_on_job_close,
                "active_process_limit": self.active_process_limit,
                "process_memory_bytes": self.process_memory_bytes,
                "job_memory_bytes": self.job_memory_bytes,
            },
            "network": {
                "wsb_networking": self.wsb_networking,
                "ipv4_default_route": self.ipv4_default_route,
                "ipv6_default_route": self.ipv6_default_route,
                "external_tcp": self.external_tcp,
            },
            "result_semantics": {
                "statuses": list(self.statuses),
                "authentic_syntax_failure_is_valid_evidence": self.authentic_syntax_failure_is_valid_evidence,
                "boundary_evidence_and_check_result_are_separate": self.boundary_evidence_and_check_result_are_separate,
                "check_passed_requires_all_selected_files": self.check_passed_requires_all_selected_files,
                "reusable_lease_issued": self.reusable_lease_issued,
                "execution_authorized": self.execution_authorized,
            },
        }


DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY = (
    DeveloperTaskExecutionCompileAstContractPolicy(
        schema_version=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_SCHEMA_VERSION,
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
        fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        backend_policy_fingerprint=WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
        parent_plan_policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
        runtime_attestation_policy_fingerprint=RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
        runtime_bundle_fingerprint=RUNTIME_BUNDLE_FINGERPRINT,
        runtime_lease_policy_fingerprint=RUNTIME_LEASE_POLICY_FINGERPRINT,
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        canonical_encoding="utf-8",
        canonical_line_ending="lf",
        field_order="exact",
        json_duplicate_keys="reject",
        json_floats="reject",
        json_non_finite_numbers="reject",
        unknown_fields="reject",
        signature_algorithm="ECDSA_P256_SHA256_P1363_64_BYTES",
        signature_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES,
        request_max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES,
        ready_max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_MAX_BYTES,
        authorize_max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZE_MAX_BYTES,
        source_manifest_max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES,
        result_max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_MAX_BYTES,
        terminal_max_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES,
        source_strategy=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_STRATEGY,
        source_root=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
        source_file_name_pattern=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_FILE_PATTERN,
        virtual_filename_prefix=DEVELOPER_TASK_EXECUTION_COMPILE_AST_VIRTUAL_FILENAME_PREFIX,
        original_path_used_as_guest_filesystem_path=False,
        read_only_mapping=True,
        source_encoding="utf-8",
        source_line_endings=("lf", "none"),
        nul_bytes="reject",
        required_mode=DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUIRED_MODE,
        max_file_count=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT,
        max_file_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_BYTES,
        max_total_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_TOTAL_BYTES,
        runtime_implementation="CPython",
        runtime_version=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_VERSION,
        runtime_architecture_bits=64,
        runtime_machines=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_MACHINES,
        ast_mode="exec",
        ast_feature_version=(3, 13),
        ast_type_comments=False,
        ast_optimize=0,
        compile_mode="exec",
        compile_flags=0,
        compile_dont_inherit=True,
        compile_optimize=0,
        source_import_statements_may_be_compiled=True,
        source_imports_executed=False,
        top_level_executed=False,
        code_object_executed=False,
        bytecode_writes=False,
        workspace_mapped=False,
        git_mapped=False,
        workspace_on_sys_path=False,
        raw_source_in_result=False,
        syntax_error_source_text_in_result=False,
        syntax_error_message_max_chars=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SYNTAX_MESSAGE_MAX_CHARS,
        worker_timeout_seconds=DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
        ready_timeout_seconds=DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS,
        authorization_timeout_seconds=DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS,
        shutdown_grace_seconds=DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS,
        kill_on_job_close=True,
        active_process_limit=DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT,
        process_memory_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES,
        job_memory_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES,
        wsb_networking="disable",
        ipv4_default_route=False,
        ipv6_default_route=False,
        external_tcp=False,
        statuses=DEVELOPER_TASK_EXECUTION_COMPILE_AST_STATUSES,
        authentic_syntax_failure_is_valid_evidence=True,
        boundary_evidence_and_check_result_are_separate=True,
        check_passed_requires_all_selected_files=True,
        reusable_lease_issued=False,
        execution_authorized=False,
    )
)


def canonical_developer_task_execution_compile_ast_contract_policy_json(
    policy: DeveloperTaskExecutionCompileAstContractPolicy = DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY,
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstContractPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionCompileAstContractPolicy")
    return _canonical_json_bytes(policy.to_dict()).decode("utf-8")


def developer_task_execution_compile_ast_contract_policy_fingerprint(
    policy: DeveloperTaskExecutionCompileAstContractPolicy = DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY,
) -> str:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstContractPolicy):
        raise TypeError("policy must be DeveloperTaskExecutionCompileAstContractPolicy")
    payload = policy.to_dict().copy()
    payload.pop("fingerprint")
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def validate_developer_task_execution_compile_ast_contract_policy(
    policy: DeveloperTaskExecutionCompileAstContractPolicy = DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY,
) -> tuple[str, ...]:
    if not isinstance(policy, DeveloperTaskExecutionCompileAstContractPolicy):
        return ("policy_type_invalid",)

    errors: list[str] = []
    expected = DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY
    if policy.schema_version != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_SCHEMA_VERSION:
        errors.append("policy_schema_invalid")
    if policy.policy_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID:
        errors.append("policy_id_invalid")
    if policy.backend_policy_fingerprint != WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint:
        errors.append("backend_policy_fingerprint_mismatch")
    if policy.parent_plan_policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT:
        errors.append("parent_plan_policy_fingerprint_mismatch")
    if policy.runtime_attestation_policy_fingerprint != RUNTIME_ATTESTATION_POLICY_FINGERPRINT:
        errors.append("runtime_attestation_policy_fingerprint_mismatch")
    if policy.runtime_bundle_fingerprint != RUNTIME_BUNDLE_FINGERPRINT:
        errors.append("runtime_bundle_fingerprint_mismatch")
    if policy.runtime_lease_policy_fingerprint != RUNTIME_LEASE_POLICY_FINGERPRINT:
        errors.append("runtime_lease_policy_fingerprint_mismatch")
    if policy.operation != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION:
        errors.append("operation_invalid")
    if policy.source_strategy != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_STRATEGY:
        errors.append("source_strategy_invalid")
    if policy.source_root != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT:
        errors.append("source_root_invalid")
    if policy.source_file_name_pattern != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_FILE_PATTERN:
        errors.append("source_file_pattern_invalid")
    if policy.virtual_filename_prefix != DEVELOPER_TASK_EXECUTION_COMPILE_AST_VIRTUAL_FILENAME_PREFIX:
        errors.append("virtual_filename_prefix_invalid")
    if policy.original_path_used_as_guest_filesystem_path or not policy.read_only_mapping:
        errors.append("source_mapping_invalid")
    if policy.source_encoding != "utf-8" or policy.source_line_endings != ("lf", "none"):
        errors.append("source_encoding_invalid")
    if policy.nul_bytes != "reject" or policy.required_mode != DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUIRED_MODE:
        errors.append("source_constraints_invalid")
    if (
        policy.max_file_count != DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT
        or policy.max_file_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_BYTES
        or policy.max_total_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_TOTAL_BYTES
    ):
        errors.append("source_limits_invalid")
    if (
        policy.canonical_encoding != "utf-8"
        or policy.canonical_line_ending != "lf"
        or policy.field_order != "exact"
        or policy.json_duplicate_keys != "reject"
        or policy.json_floats != "reject"
        or policy.json_non_finite_numbers != "reject"
        or policy.unknown_fields != "reject"
    ):
        errors.append("canonical_contract_invalid")
    if (
        policy.signature_algorithm != "ECDSA_P256_SHA256_P1363_64_BYTES"
        or policy.signature_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SIGNATURE_BYTES
    ):
        errors.append("signature_contract_invalid")
    if (
        policy.request_max_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES
        or policy.ready_max_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_MAX_BYTES
        or policy.authorize_max_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZE_MAX_BYTES
        or policy.source_manifest_max_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES
        or policy.result_max_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_MAX_BYTES
        or policy.terminal_max_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_TERMINAL_MAX_BYTES
    ):
        errors.append("document_limits_invalid")
    if (
        policy.runtime_implementation != "CPython"
        or policy.runtime_version != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_VERSION
        or policy.runtime_architecture_bits != 64
        or policy.runtime_machines != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_MACHINES
    ):
        errors.append("runtime_identity_invalid")
    if (
        policy.ast_mode != "exec"
        or policy.ast_feature_version != (3, 13)
        or policy.ast_type_comments
        or policy.ast_optimize != 0
        or policy.compile_mode != "exec"
        or policy.compile_flags != 0
        or not policy.compile_dont_inherit
        or policy.compile_optimize != 0
    ):
        errors.append("parse_compile_contract_invalid")
    if (
        not policy.source_import_statements_may_be_compiled
        or policy.source_imports_executed
        or policy.top_level_executed
        or policy.code_object_executed
        or policy.bytecode_writes
        or policy.workspace_mapped
        or policy.git_mapped
        or policy.workspace_on_sys_path
        or policy.raw_source_in_result
        or policy.syntax_error_source_text_in_result
        or policy.syntax_error_message_max_chars != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SYNTAX_MESSAGE_MAX_CHARS
    ):
        errors.append("runner_semantics_invalid")
    if (
        policy.ready_timeout_seconds != DEVELOPER_TASK_EXECUTION_COMPILE_AST_READY_TIMEOUT_SECONDS
        or policy.authorization_timeout_seconds != DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZATION_TIMEOUT_SECONDS
        or policy.worker_timeout_seconds != DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS
        or policy.shutdown_grace_seconds != DEVELOPER_TASK_EXECUTION_COMPILE_AST_SHUTDOWN_GRACE_SECONDS
    ):
        errors.append("timeouts_invalid")
    if (
        not policy.kill_on_job_close
        or policy.active_process_limit != DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT
        or policy.process_memory_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES
        or policy.job_memory_bytes != DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES
    ):
        errors.append("job_limits_invalid")
    if (
        policy.wsb_networking != "disable"
        or policy.ipv4_default_route
        or policy.ipv6_default_route
        or policy.external_tcp
    ):
        errors.append("network_policy_invalid")
    if (
        policy.statuses != DEVELOPER_TASK_EXECUTION_COMPILE_AST_STATUSES
        or not policy.authentic_syntax_failure_is_valid_evidence
        or not policy.boundary_evidence_and_check_result_are_separate
        or not policy.check_passed_requires_all_selected_files
        or policy.reusable_lease_issued
        or policy.execution_authorized
    ):
        errors.append("result_semantics_invalid")
    if policy != expected:
        errors.append("policy_values_changed")
    if developer_task_execution_compile_ast_contract_policy_fingerprint(policy) != policy.fingerprint:
        errors.append("policy_fingerprint_mismatch")
    if policy.fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT:
        errors.append("policy_fingerprint_unpinned")
    return tuple(dict.fromkeys(errors))
