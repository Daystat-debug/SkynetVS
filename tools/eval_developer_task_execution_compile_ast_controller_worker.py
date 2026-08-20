from __future__ import annotations

import ast
import hashlib
import inspect
import json

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_compile_ast_contract import (
    _READY_CHECK_FIELDS,
    _READY_FIELDS,
    _TERMINAL_CHECK_FIELDS,
    _TERMINAL_CONTROLLER_FIELDS,
    _TERMINAL_CONTROL_FIELDS,
    _TERMINAL_FIELDS,
    _TERMINAL_RUNTIME_FIELDS,
    _TERMINAL_SHUTDOWN_FIELDS,
    _TERMINAL_WORKER_FIELDS,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_SHA256,
    build_developer_task_execution_compile_ast_controller_worker_bundle,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1,
    developer_task_execution_compile_ast_controller_worker_policy_bytes,
    developer_task_execution_compile_ast_controller_worker_policy_fingerprint,
    validate_developer_task_execution_compile_ast_controller_worker_policy,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
)
from modules.developer.developer_task_execution_compile_ast_verifier_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_compile_ast_claim_transaction_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
)


def _powershell_ordered_block_keys(source: str, marker: str) -> tuple[str, ...]:
    start = source.index(marker)
    lines = source[start:].splitlines()
    depth = 0
    keys: list[str] = []
    started = False
    for line in lines:
        if not started:
            if "[ordered]@{" not in line:
                continue
            started = True
            depth = 1
            continue
        stripped = line.strip()
        if depth == 1 and "=" in stripped:
            candidate = stripped.split("=", 1)[0].strip()
            if candidate.replace("_", "").isalnum():
                keys.append(candidate)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            return tuple(keys)
    raise AssertionError(f"unterminated ordered PowerShell block: {marker}")


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        if not ok:
            fail_count += 1
        print()
        print(f"=== {name} ===")
        print(
            json.dumps(
                {"actual": actual, "expected": expected, "ok": ok},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    policy = DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1
    bundle = build_developer_task_execution_compile_ast_controller_worker_bundle()
    second = build_developer_task_execution_compile_ast_controller_worker_bundle()
    policy_bytes = bundle.policy.exact_bytes()
    bootstrap_bytes = bundle.bootstrap.exact_bytes()
    native_bytes = bundle.native_helper.exact_bytes()
    controller_bytes = bundle.controller.exact_bytes()
    wsb_bytes = bundle.wsb_template.exact_bytes()
    native_text = native_bytes.decode("utf-8", errors="strict")
    controller_text = controller_bytes.decode("utf-8", errors="strict")
    bootstrap_text = bootstrap_bytes.decode("utf-8", errors="strict")
    wsb_text = wsb_bytes.decode("utf-8", errors="strict")
    module_path = Path(__file__).resolve().parents[1] / "modules/developer/developer_task_execution_compile_ast_controller_worker.py"
    module_text = module_path.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text, filename=str(module_path), mode="exec")
    windows_eval_path = Path(__file__).resolve().parent / "eval_developer_task_execution_compile_ast_controller_worker_windows.py"
    windows_eval_text = windows_eval_path.read_text(encoding="utf-8")
    imports = sorted(
        {
            alias.name.split(".")[0]
            for node in ast.walk(module_tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        | {
            (node.module or "").split(".")[0]
            for node in ast.walk(module_tree)
            if isinstance(node, ast.ImportFrom)
        }
    )

    check(
        "V1C2C1 POLICY SELF CHECKS WITH SEPARATE ARCHITECTURE IDENTITY",
        {
            "errors": list(validate_developer_task_execution_compile_ast_controller_worker_policy()),
            "policy_id": policy.policy_id,
            "policy_fingerprint": policy.policy_fingerprint,
            "recomputed": developer_task_execution_compile_ast_controller_worker_policy_fingerprint(policy),
            "policy_bytes_sha256": hashlib.sha256(developer_task_execution_compile_ast_controller_worker_policy_bytes()).hexdigest(),
            "decision": policy.architecture_decision_fingerprint,
            "slice_identity": policy.architecture_slice_identity,
        },
        {
            "errors": [],
            "policy_id": "skynetvs-v1c2c1r2-fixed-system-controller-standard-user-worker-bundle-v3",
            "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
            "recomputed": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
            "policy_bytes_sha256": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
            "decision": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT,
            "slice_identity": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY,
        },
    )

    check(
        "V1C2C1R1 TRANSCRIPT POLICY HASH BINDS CONTRACT POLICY WHILE CONTROLLER POLICY SELF VERIFIES",
        policy.to_dict()["transcript_artifact_binding"],
        {
            "request_policy_sha256_role": "v1c2a1_contract_policy_file",
            "ready_terminal_policy_sha256": "echo_request_contract_policy_sha256",
            "controller_worker_policy_verified_by": "controller_embedded_exact_sha256",
        },
    )

    check(
        "V1C2C1R2 SHARED OUTPUT ACL POLICY PRESERVES HOST OBSERVABILITY",
        policy.to_dict()["shared_output_acl"],
        {
            "path": r"C:\SkynetVSOutput",
            "mode": "preserve_existing_add_exact_worker_write_ace_v1",
            "preserve_owner": True,
            "preserve_access_rule_protection": True,
            "preserve_preexisting_access_rules": True,
            "fresh_worker_sid_required": True,
            "worker_rights": [
                "Write",
                "ReadAttributes",
                "ReadPermissions",
                "Synchronize",
            ],
            "inheritance_flags": ["ContainerInherit", "ObjectInherit"],
            "propagation_flags": "None",
            "access_control_type": "Allow",
            "exact_single_worker_rule_required": True,
            "post_write_reread_required": True,
            "set_access_rule_protection_allowed": False,
            "owner_replacement_allowed": False,
            "dacl_replacement_allowed": False,
        },
    )

    check(
        "V1C2C1 BUNDLE BUILDER ACCEPTS NO CALLER INPUT",
        list(inspect.signature(build_developer_task_execution_compile_ast_controller_worker_bundle).parameters),
        [],
    )

    check(
        "V1C2C1 HOST ONLY BUNDLE BUILDS NON AUTHORIZING",
        {
            "ok": bundle.ok,
            "sandbox": bundle.sandbox_launched,
            "transaction": bundle.claim_transaction_consumed,
            "lease": bundle.runtime_lease_claimed,
            "candidate": bundle.candidate_interpreter_executed,
            "processed": bundle.changed_source_processed,
            "ast": bundle.changed_source_ast_parsed,
            "compiled": bundle.changed_source_compiled,
            "changed_exec": bundle.changed_code_executed,
            "reusable": bundle.reusable_lease_issued,
            "authorized": bundle.execution_authorized,
        },
        {
            "ok": True,
            "sandbox": False,
            "transaction": False,
            "lease": False,
            "candidate": False,
            "processed": False,
            "ast": False,
            "compiled": False,
            "changed_exec": False,
            "reusable": False,
            "authorized": False,
        },
    )

    check(
        "V1C2C1 BUNDLE IS DETERMINISTIC",
        {
            "metadata": bundle.to_dict() == second.to_dict(),
            "payloads": [payload.exact_bytes() for payload in bundle.payloads]
            == [payload.exact_bytes() for payload in second.payloads],
        },
        {"metadata": True, "payloads": True},
    )

    check(
        "V1C2C1 EXACT PAYLOAD HASHES AND BUNDLE IDENTITY ARE PINNED",
        {
            "policy": bundle.policy.sha256,
            "bootstrap": bundle.bootstrap.sha256,
            "native": bundle.native_helper.sha256,
            "controller": bundle.controller.sha256,
            "wsb": bundle.wsb_template.sha256,
            "bundle": bundle.bundle_fingerprint,
        },
        {
            "policy": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
            "bootstrap": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_SHA256,
            "native": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_SHA256,
            "controller": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_SHA256,
            "wsb": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_SHA256,
            "bundle": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_FINGERPRINT,
        },
    )

    check(
        "V1C2C1 PAYLOAD HASHES MATCH EXACT IMMUTABLE BYTES",
        [hashlib.sha256(payload.exact_bytes()).hexdigest() for payload in bundle.payloads],
        [payload.sha256 for payload in bundle.payloads],
    )

    check(
        "V1C2C1 PAYLOAD FILE SET IS EXACT",
        [(payload.kind, payload.file_name) for payload in bundle.payloads],
        [
            ("compile_ast_controller_worker_policy", "compile_ast_controller_worker_policy.json"),
            ("trusted_bootstrap", "bootstrap.ps1"),
            ("trusted_native_helper", "SkynetVS_V1C2C1_native_helper.cs"),
            ("trusted_system_controller", "controller.ps1"),
            ("windows_sandbox_template", "SkynetVS_V1C2C1.wsb"),
        ],
    )

    check(
        "V1C2C1 ALL PAYLOAD TEXT IS STRICT UTF8 LF WITHOUT BOM",
        [
            {
                "bom": payload.exact_bytes().startswith(b"\xef\xbb\xbf"),
                "cr": b"\r" in payload.exact_bytes(),
                "final_lf": payload.exact_bytes().endswith(b"\n"),
                "strict": payload.exact_bytes().decode("utf-8", errors="strict") is not None,
            }
            for payload in bundle.payloads
        ],
        [
            {"bom": False, "cr": False, "final_lf": True, "strict": True}
            for _ in bundle.payloads
        ],
    )

    check(
        "V1C2C1 PUBLIC SERIALIZATION HIDES EXACT PAYLOAD BYTES",
        {
            "private_in_payload_dict": any("_bytes" in payload.to_dict() for payload in bundle.payloads),
            "controller_source_in_repr": "Set-StrictMode" in repr(bundle),
            "native_source_in_repr": "CreateProcessAsUserW" in repr(bundle),
        },
        {
            "private_in_payload_dict": False,
            "controller_source_in_repr": False,
            "native_source_in_repr": False,
        },
    )

    dependencies = policy.to_dict()["dependencies"]
    check(
        "V1C2C1 BINDS VERIFIED A2 B C0 AND RUNTIME IDENTITIES",
        {
            "runner_bundle": dependencies["compile_ast_runner"]["bundle_fingerprint"],
            "runner": dependencies["compile_ast_runner"]["runner_sha256"],
            "payload": dependencies["compile_ast_runner"]["payload_sha256"],
            "verifier": dependencies["compile_ast_verifier"]["policy_fingerprint"],
            "claim": dependencies["claim_transaction"]["policy_fingerprint"],
            "runtime": dependencies["runtime"]["bundle_fingerprint"],
        },
        {
            "runner_bundle": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
            "runner": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
            "payload": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
            "verifier": DEVELOPER_TASK_EXECUTION_COMPILE_AST_VERIFIER_POLICY_FINGERPRINT,
            "claim": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
            "runtime": RUNTIME_BUNDLE_FINGERPRINT,
        },
    )

    check(
        "V1C2C1 NATIVE HELPER DEFINES FRESH STANDARD USER",
        {
            "prefix": 'return "svc2c1" + requestId.Substring(0, 12);' in native_text,
            "net_user_add": "NetUserAdd" in native_text,
            "logon_user": "LogonUserW" in native_text,
            "primary_token": "TokenPrimary" in native_text,
            "non_admin": "Worker token is administrative." in native_text,
            "medium": "WORKER_INTEGRITY_RID = 0x2000" in native_text,
            "exact_delete": "DeleteLocalUserExact" in native_text,
        },
        {
            "prefix": True,
            "net_user_add": True,
            "logon_user": True,
            "primary_token": True,
            "non_admin": True,
            "medium": True,
            "exact_delete": True,
        },
    )

    password_section = native_text[
        native_text.index("public sealed class WorkerPasswordSecret"):
        native_text.index("public static class V1C2C1Native")
    ]
    launch_section_start = native_text.index(
        "public static WorkerLaunchState LaunchFixedCompileAstWorkerSuspendedInJob"
    )
    launch_section_end = native_text.index(
        "public static uint ResumeCompileAstWorker",
        launch_section_start,
    )
    launch_section = native_text[launch_section_start:launch_section_end]
    environment_section_start = native_text.index(
        "private static IntPtr BuildSanitizedEnvironmentBlock"
    )
    environment_section_end = native_text.index(
        "private static void ZeroAndFreeEnvironmentBlock",
        environment_section_start,
    )
    environment_section = native_text[
        environment_section_start:environment_section_end
    ]

    check(
        "V1C2C1 PASSWORD REMAINS MEMORY ONLY AND IS CLEARED",
        {
            "random": "WorkerPasswordSecret.CreateRandom" in native_text,
            "dispose": (
                "Marshal.WriteInt16(buffer, index * 2, 0)" in password_section
                and "Marshal.FreeHGlobal(buffer)" in password_section
                and "Array.Clear(chars, 0, chars.Length)" in password_section
                and "Array.Clear(random, 0, random.Length)" in password_section
            ),
            "command_line_password": "password.Pointer" in launch_section,
            "environment_password": "password.Pointer" in environment_section,
        },
        {
            "random": True,
            "dispose": True,
            "command_line_password": False,
            "environment_password": False,
        },
    )

    shared_acl_start = native_text.index(
        "public static void PrepareSharedWorkerOutputDirectory"
    )
    shared_acl_end = native_text.index(
        "public static IntPtr CreateInheritableSentinelEvent",
        shared_acl_start,
    )
    shared_acl_section = native_text[shared_acl_start:shared_acl_end]

    check(
        "V1C2C1R2 SHARED OUTPUT ACL PRESERVES OWNER PROTECTION AND PREEXISTING RULES",
        {
            "read_before": "Directory.GetAccessControl(path, AccessControlSections.Access | AccessControlSections.Owner)" in shared_acl_section,
            "owner_before": "ownerBefore" in shared_acl_section,
            "protection_before": "protectionBefore" in shared_acl_section,
            "preexisting_multiset": "rulesBefore" in shared_acl_section,
            "fresh_sid": "Fresh worker SID already has shared-output ACL entries." in shared_acl_section,
            "add_only": "before.AddAccessRule(workerRule);" in shared_acl_section,
            "write": "Directory.SetAccessControl(path, before);" in shared_acl_section,
            "reread": "DirectorySecurity after = Directory.GetAccessControl" in shared_acl_section,
            "owner_check": "Shared-output owner changed." in shared_acl_section,
            "protection_check": "Shared-output access-rule protection changed." in shared_acl_section,
            "preexisting_check": "Pre-existing shared-output ACL rules changed." in shared_acl_section,
            "exact_worker": "Shared-output worker SID must have exactly one ACL entry." in shared_acl_section,
        },
        {
            "read_before": True,
            "owner_before": True,
            "protection_before": True,
            "preexisting_multiset": True,
            "fresh_sid": True,
            "add_only": True,
            "write": True,
            "reread": True,
            "owner_check": True,
            "protection_check": True,
            "preexisting_check": True,
            "exact_worker": True,
        },
    )

    check(
        "V1C2C1R2 SHARED OUTPUT ACL DOES NOT PROTECT REPLACE OR REOWNER THE MAPPING",
        {
            "set_protection": "SetAccessRuleProtection" in shared_acl_section,
            "set_owner": "SetOwner" in shared_acl_section,
            "new_directory_security": "new DirectorySecurity" in shared_acl_section,
            "system_only_dacl": "WellKnownSidType.LocalSystemSid" in shared_acl_section,
        },
        {
            "set_protection": False,
            "set_owner": False,
            "new_directory_security": False,
            "system_only_dacl": False,
        },
    )

    check(
        "V1C2C1R2 CONTROLLER USES SHARED OUTPUT ACL PATH ONLY",
        {
            "shared_call": "PrepareSharedWorkerOutputDirectory($outputRoot, $workerSid)" in controller_text,
            "private_call": "PrepareWorkerResultDirectory($outputRoot, $workerSid)" in controller_text,
            "shared_before_launch": controller_text.index("PrepareSharedWorkerOutputDirectory") < controller_text.index("LaunchFixedCompileAstWorkerSuspendedInJob"),
        },
        {
            "shared_call": True,
            "private_call": False,
            "shared_before_launch": True,
        },
    )

    check(
        "V1C2C1 ENVIRONMENT IS CREATED FRESH AND SANITIZED",
        {
            "create_environment_false": "CreateEnvironmentBlock(out originalEnvironment, token, false)" in native_text,
            "python": 'upper.StartsWith("PYTHON", StringComparison.Ordinal)' in native_text,
            "pip": 'upper.StartsWith("PIP_", StringComparison.Ordinal)' in native_text,
            "launcher": 'upper.StartsWith("PYLAUNCHER_", StringComparison.Ordinal)' in native_text,
            "venv": 'String.Equals(upper, "VIRTUAL_ENV", StringComparison.Ordinal)' in native_text,
            "zero_free": "ZeroAndFreeEnvironmentBlock" in native_text,
        },
        {
            "create_environment_false": True,
            "python": True,
            "pip": True,
            "launcher": True,
            "venv": True,
            "zero_free": True,
        },
    )

    check(
        "V1C2C1 FIXED CREATEPROCESSASUSER CONTRACT HAS NO HANDLE INHERITANCE",
        {
            "api": "CreateProcessAsUserW" in native_text,
            "fixed_runtime": 'const string runtimeExecutablePath = @"C:\\SkynetVSRuntime\\python.exe";' in native_text,
            "fixed_runner": 'const string runnerPath = @"C:\\SkynetVSInput\\SkynetVS_V1C2A2_runner.py";' in native_text,
            "fixed_workdir": 'const string resultRoot = @"C:\\SkynetVSOutput";' in native_text,
            "inherit_false": "const bool inheritHandles = false;" in native_text,
            "inherit_argument": "                inheritHandles," in native_text,
        },
        {
            "api": True,
            "fixed_runtime": True,
            "fixed_runner": True,
            "fixed_workdir": True,
            "inherit_false": True,
            "inherit_argument": True,
        },
    )

    check(
        "V1C2C1 WORKER IS CREATED SUSPENDED ASSIGNED CHECKED THEN RESUMED",
        {
            "suspended": "CREATE_SUSPENDED" in native_text,
            "assign": native_text.index("AssignProcessToJobObject(job, processInformation.hProcess)"),
            "in_job": native_text.index("IsProcessInJob(processInformation.hProcess, job, out inJob)"),
            "return_state": native_text.index("return state;", native_text.index("LaunchFixedCompileAstWorkerSuspendedInJob")),
            "resume_method": native_text.index("ResumeCompileAstWorker"),
            "controller_launch": controller_text.index("LaunchFixedCompileAstWorkerSuspendedInJob"),
            "controller_resume": controller_text.index("ResumeCompileAstWorker"),
        },
        {
            "suspended": True,
            "assign": native_text.index("AssignProcessToJobObject(job, processInformation.hProcess)"),
            "in_job": native_text.index("IsProcessInJob(processInformation.hProcess, job, out inJob)"),
            "return_state": native_text.index("return state;", native_text.index("LaunchFixedCompileAstWorkerSuspendedInJob")),
            "resume_method": native_text.index("ResumeCompileAstWorker"),
            "controller_launch": controller_text.index("LaunchFixedCompileAstWorkerSuspendedInJob"),
            "controller_resume": controller_text.index("ResumeCompileAstWorker"),
        },
    )
    check(
        "V1C2C1 ASSIGN AND MEMBERSHIP PROOF PRECEDE RESUME",
        (
            native_text.index("AssignProcessToJobObject(job, processInformation.hProcess)")
            < native_text.index("IsProcessInJob(processInformation.hProcess, job, out inJob)")
            < controller_text.index("ResumeCompileAstWorker")
        ),
        True,
    )

    check(
        "V1C2C1 JOB LIMIT FLAGS ARE EXACTLY REQUIRED SECURITY FLAGS",
        {
            "active": "JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008" in native_text,
            "process_memory": "JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100" in native_text,
            "job_memory": "JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200" in native_text,
            "kill": "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000" in native_text,
            "active_value": "COMPILE_AST_ACTIVE_PROCESS_LIMIT = 1" in native_text,
            "process_value": "COMPILE_AST_PROCESS_MEMORY_BYTES = 536870912UL" in native_text,
            "job_value": "COMPILE_AST_JOB_MEMORY_BYTES = 805306368UL" in native_text,
            "breakaway": "BREAKAWAY" in native_text,
        },
        {
            "active": True,
            "process_memory": True,
            "job_memory": True,
            "kill": True,
            "active_value": True,
            "process_value": True,
            "job_value": True,
            "breakaway": False,
        },
    )

    create_process_position = launch_section.index("if (!CreateProcessAsUserW(")
    check(
        "V1C2C1 JOB LIMIT VALUES ARE SET BEFORE PROCESS CREATION",
        {
            "flags_before_create": (
                launch_section.index("limits.BasicLimitInformation.LimitFlags")
                < create_process_position
            ),
            "active_before_create": (
                launch_section.index(
                    "limits.BasicLimitInformation.ActiveProcessLimit"
                )
                < create_process_position
            ),
            "process_before_create": (
                launch_section.index("limits.ProcessMemoryLimit")
                < create_process_position
            ),
            "job_before_create": (
                launch_section.index("limits.JobMemoryLimit")
                < create_process_position
            ),
            "set_before_create": (
                launch_section.index("SetInformationJobObject(job")
                < create_process_position
            ),
        },
        {
            "flags_before_create": True,
            "active_before_create": True,
            "process_before_create": True,
            "job_before_create": True,
            "set_before_create": True,
        },
    )

    check(
        "V1C2C1 CONTROLLER REVALIDATES REQUEST PAYLOAD SOURCE AND RUNTIME",
        {
            "request": "request_validation" in controller_text,
            "static_payload": controller_text.count("Assert-CompileAstStaticPayload") >= 3,
            "source_manifest": "Assert-SourceManifestAndTree" in controller_text,
            "runtime_tree": controller_text.count("Assert-RuntimeTree") >= 3,
            "source_hash": "Source file hash mismatch." in controller_text,
            "post_auth": "post_authorization_revalidation" in controller_text,
        },
        {
            "request": True,
            "static_payload": True,
            "source_manifest": True,
            "runtime_tree": True,
            "source_hash": True,
            "post_auth": True,
        },
    )

    check(
        "V1C2C1R1 CONTROLLER TRANSCRIPT POLICY HASH MATCHES V1C2A2 AND V1C2B",
        {
            "request_contract_policy": (
                '$ExpectedContractPolicySha256 -cne [string]$Request.policy_sha256'
                in controller_text
            ),
            "request_controller_policy_absent": (
                '$ExpectedControllerWorkerPolicySha256 -cne [string]$Request.policy_sha256'
                not in controller_text
            ),
            "controller_policy_self_verified": (
                'Get-FileSha256 -Path $controllerWorkerPolicyPath' in controller_text
                and 'Controller-worker policy hash mismatch.' in controller_text
            ),
            "ready_terminal_contract_policy": (
                controller_text.count(
                    'policy_sha256 = Get-FileSha256 -Path $contractPolicyPath'
                ) == 2
            ),
        },
        {
            "request_contract_policy": True,
            "request_controller_policy_absent": True,
            "controller_policy_self_verified": True,
            "ready_terminal_contract_policy": True,
        },
    )

    check(
        "V1C2C1 READY BINDS LOCALSYSTEM EPHEMERAL KEY AND READONLY CONTROLS",
        {
            "system_sid": '$controllerIsSystem = ($controllerSid -eq "S-1-5-18")' in controller_text,
            "system_integrity": "controller_integrity_is_system" in controller_text,
            "ephemeral": "CreateEphemeralEcdsaP256SigningKey" in controller_text,
            "source_readonly": "source_write_blocked" in controller_text,
            "runtime_readonly": "runtime_write_blocked" in controller_text,
            "control_readonly": "control_write_blocked" in controller_text,
            "output": "output_writable" in controller_text,
            "task_deleted": "bootstrap_task_deleted" in controller_text,
            "ready_field_order": _powershell_ordered_block_keys(
                controller_text, "$ready = [ordered]@{"
            ) == _READY_FIELDS,
            "ready_check_field_order": _powershell_ordered_block_keys(
                controller_text, "$readyChecks = [ordered]@{"
            ) == _READY_CHECK_FIELDS,
        },
        {
            "system_sid": True,
            "system_integrity": True,
            "ephemeral": True,
            "source_readonly": True,
            "runtime_readonly": True,
            "control_readonly": True,
            "output": True,
            "task_deleted": True,
            "ready_field_order": True,
            "ready_check_field_order": True,
        },
    )

    check(
        "V1C2C1 AUTHORIZATION IS HASH COMMITTED BEFORE WORKER RESUME",
        {
            "commit": "authorize.sha256" in controller_text,
            "hash_match": "Authorization commit hash mismatch." in controller_text,
            "ready_hash": "Authorization ready hash mismatch." in controller_text,
            "scope": "allow_compile_ast" in controller_text,
            "auth_pos": controller_text.index("Authorization scope is invalid."),
            "launch_pos": controller_text.index("LaunchFixedCompileAstWorkerSuspendedInJob"),
        },
        {
            "commit": True,
            "hash_match": True,
            "ready_hash": True,
            "scope": True,
            "auth_pos": controller_text.index("Authorization scope is invalid."),
            "launch_pos": controller_text.index("LaunchFixedCompileAstWorkerSuspendedInJob"),
        },
    )
    check(
        "V1C2C1 AUTHORIZATION VALIDATION PRECEDES WORKER LAUNCH",
        controller_text.index("Authorization scope is invalid.")
        < controller_text.index("LaunchFixedCompileAstWorkerSuspendedInJob"),
        True,
    )

    check(
        "V1C2C1 WORKER TIMEOUT IS BOUNDED AND JOB CLOSE IS FAILURE CLEANUP",
        {
            "timeout_ms": "WaitForSingleObject($launchState.ProcessHandle, [uint32](60 * 1000))" in controller_text,
            "timeout": "WAIT_TIMEOUT" in controller_text,
            "job_close": "CloseHandle($launchState.JobHandle)" in controller_text,
            "quiescence": "WaitForWorkerSidQuiescence" in controller_text,
            "account_delete": "DeleteLocalUserExact" in controller_text,
        },
        {
            "timeout_ms": True,
            "timeout": True,
            "job_close": True,
            "quiescence": True,
            "account_delete": True,
        },
    )

    check(
        "V1C2C1 SIGNED TERMINAL DISTINGUISHES PASS SYNTAX FAILURE AND BOUNDARY FAILURE",
        {
            "passed": "compile_ast_attested_passed" in controller_text,
            "syntax": "compile_ast_attested_failed" in controller_text,
            "boundary": "compile_ast_boundary_failed" in controller_text,
            "no_result_boundary": '$resultSha256 = if ($resultReceived)' in controller_text,
            "sign": "$ecdsa.SignHash($terminalDigest)" in controller_text,
            "changed_exec_false": "changed_code_executed = $false" in controller_text,
            "reusable_false": "reusable_lease_issued = $false" in controller_text,
            "authorized_false": "execution_authorized = $false" in controller_text,
            "terminal_field_order": _powershell_ordered_block_keys(
                controller_text, "$terminalPayload = [ordered]@{"
            ) == _TERMINAL_FIELDS,
            "controller_field_order": _powershell_ordered_block_keys(
                controller_text, "controller = [ordered]@{"
            ) == _TERMINAL_CONTROLLER_FIELDS,
            "worker_field_order": _powershell_ordered_block_keys(
                controller_text, "worker = [ordered]@{"
            ) == _TERMINAL_WORKER_FIELDS,
            "controls_field_order": _powershell_ordered_block_keys(
                controller_text, "controls = [ordered]@{"
            ) == _TERMINAL_CONTROL_FIELDS,
            "runtime_field_order": _powershell_ordered_block_keys(
                controller_text, "runtime = [ordered]@{"
            ) == _TERMINAL_RUNTIME_FIELDS,
            "check_field_order": _powershell_ordered_block_keys(
                controller_text, "check = [ordered]@{"
            ) == _TERMINAL_CHECK_FIELDS,
            "shutdown_field_order": _powershell_ordered_block_keys(
                controller_text, "shutdown = [ordered]@{"
            ) == _TERMINAL_SHUTDOWN_FIELDS,
        },
        {
            "passed": True,
            "syntax": True,
            "boundary": True,
            "no_result_boundary": True,
            "sign": True,
            "changed_exec_false": True,
            "reusable_false": True,
            "authorized_false": True,
            "terminal_field_order": True,
            "controller_field_order": True,
            "worker_field_order": True,
            "controls_field_order": True,
            "runtime_field_order": True,
            "check_field_order": True,
            "shutdown_field_order": True,
        },
    )

    check(
        "V1C2C1 POST READY SOURCE SUBSTITUTION IS LEFT TO FIXED RUNNER BOUNDARY",
        {
            "comment": "Source changes after ready are deliberately left for the fixed runner" in controller_text,
            "runner_validates": "Read-TrustedCompileAstResult" in controller_text,
            "result_optional": "if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) { return $null }" in controller_text,
            "boundary_status": 'if (-not $boundaryOk) { "compile_ast_boundary_failed" }' in controller_text,
        },
        {
            "comment": True,
            "runner_validates": True,
            "result_optional": True,
            "boundary_status": True,
        },
    )

    check(
        "V1C2C1 CONTROLLER PROVES NETWORK ISOLATION AND SELF SHUTDOWN",
        {
            "ipv4_route": "Test-DefaultRoute -Family IPv4" in controller_text,
            "ipv6_route": "Test-DefaultRoute -Family IPv6" in controller_text,
            "ipv4_tcp": 'Address "1.1.1.1"' in controller_text,
            "ipv6_tcp": 'Address "2606:4700:4700::1111"' in controller_text,
            "shutdown": "Schedule-Shutdown" in controller_text,
        },
        {
            "ipv4_route": True,
            "ipv6_route": True,
            "ipv4_tcp": True,
            "ipv6_tcp": True,
            "shutdown": True,
        },
    )

    check(
        "V1C2C1 BOOTSTRAP IS FIXED WDAG TO ONE TIME SYSTEM CONTROLLER",
        {
            "wdag": "WDAGUtilityAccount" in bootstrap_text,
            "admin": "WDAG bootstrap is not administrator." in bootstrap_text,
            "system": '$definition.Principal.UserId = "SYSTEM"' in bootstrap_text,
            "one_time": "SkynetVS V1C2C1 one-time SYSTEM compile AST controller" in bootstrap_text,
            "fixed_controller": '-File "C:\\SkynetVSInput\\controller.ps1"' in bootstrap_text,
            "task_prefix": "SkynetVS-V1C2C1-" in bootstrap_text,
        },
        {
            "wdag": True,
            "admin": True,
            "system": True,
            "one_time": True,
            "fixed_controller": True,
            "task_prefix": True,
        },
    )

    check(
        "V1C2C1 WSB TEMPLATE HAS EXACT FOUR FOLDERS AND DISABLED REDIRECTIONS",
        {
            "mapped": wsb_text.count("<MappedFolder>"),
            "readonly": wsb_text.count("<ReadOnly>true</ReadOnly>"),
            "writable": wsb_text.count("<ReadOnly>false</ReadOnly>"),
            "network": "<Networking>Disable</Networking>" in wsb_text,
            "vgpu": "<VGpu>Disable</VGpu>" in wsb_text,
            "audio": "<AudioInput>Disable</AudioInput>" in wsb_text,
            "video": "<VideoInput>Disable</VideoInput>" in wsb_text,
            "clipboard": "<ClipboardRedirection>Disable</ClipboardRedirection>" in wsb_text,
            "printer": "<PrinterRedirection>Disable</PrinterRedirection>" in wsb_text,
            "protected": "<ProtectedClient>Enable</ProtectedClient>" in wsb_text,
        },
        {
            "mapped": 4,
            "readonly": 3,
            "writable": 1,
            "network": True,
            "vgpu": True,
            "audio": True,
            "video": True,
            "clipboard": True,
            "printer": True,
            "protected": True,
        },
    )

    check(
        "V1C2C1 PYTHON BUILDER HAS NO PROCESS NETWORK OR FILE MATERIALIZATION SURFACE",
        {
            "imports": sorted(set(imports).intersection({"subprocess", "socket", "urllib", "requests", "tempfile", "pathlib", "os"})),
            "subprocess_run": "subprocess.run" in module_text,
            "popen": "Popen(" in module_text,
            "open_write": "write_bytes(" in module_text or "write_text(" in module_text,
            "sandbox_launch": 'Start-Process -FilePath "WindowsSandbox.exe"' in module_text,
        },
        {
            "imports": [],
            "subprocess_run": False,
            "popen": False,
            "open_write": False,
            "sandbox_launch": False,
        },
    )

    check(
        "V1C2C1 CONTROLLER ACCEPTS NO CALLER EXECUTABLE ARGV ENV IDENTITY LIMITS OR PATH SETTINGS",
        {
            "caller_executable": "caller_executable" in policy.to_dict()["prohibitions"] and policy.to_dict()["prohibitions"]["caller_executable_allowed"],
            "caller_arguments": policy.to_dict()["prohibitions"]["caller_arguments_allowed"],
            "caller_environment": policy.to_dict()["prohibitions"]["caller_environment_allowed"],
            "caller_identity": policy.to_dict()["prohibitions"]["caller_worker_identity_allowed"],
            "caller_limits": policy.to_dict()["prohibitions"]["caller_job_limits_allowed"],
            "caller_paths": policy.to_dict()["prohibitions"]["caller_guest_paths_allowed"],
            "caller_runner": policy.to_dict()["prohibitions"]["caller_runner_path_allowed"],
            "caller_wsb": policy.to_dict()["prohibitions"]["caller_wsb_settings_allowed"],
        },
        {
            "caller_executable": False,
            "caller_arguments": False,
            "caller_environment": False,
            "caller_identity": False,
            "caller_limits": False,
            "caller_paths": False,
            "caller_runner": False,
            "caller_wsb": False,
        },
    )

    check(
        "V1C2C1 WINDOWS EVALUATOR CAPTURES LOCALIZED CHILD OUTPUT AS BYTES",
        {
            "byte_mode": "text=False" in windows_eval_text,
            "decode_helper": "def _decode_windows_process_output" in windows_eval_text,
            "ascii_json": 'line.decode("ascii", errors="strict")' in windows_eval_text,
            "unsafe_text_mode": "text=True" in windows_eval_text,
            "unsafe_stderr_strip": "completed.stderr.strip()" in windows_eval_text,
        },
        {
            "byte_mode": True,
            "decode_helper": True,
            "ascii_json": True,
            "unsafe_text_mode": False,
            "unsafe_stderr_strip": False,
        },
    )

    check(
        "V1C2C1R2 WINDOWS EVALUATOR USES LITERAL CONTROLLER NEEDLES AND CURRENT POLICY FINGERPRINT",
        {
            "shared_literal": "$controllerText.Contains('PrepareSharedWorkerOutputDirectory($outputRoot, $workerSid)')" in windows_eval_text,
            "private_literal": "$controllerText.Contains('PrepareWorkerResultDirectory($outputRoot, $workerSid)')" in windows_eval_text,
            "unsafe_shared_interpolation": '$controllerText.Contains("PrepareSharedWorkerOutputDirectory($outputRoot, $workerSid)")' in windows_eval_text,
            "unsafe_private_interpolation": '$controllerText.Contains("PrepareWorkerResultDirectory($outputRoot, $workerSid)")' in windows_eval_text,
            "current_policy_fingerprint": '"policy_fingerprint": "65d0dbdd1cf03095f35f3bd322b3ef8a1f0e9139c163266fefd1664218e21a0a"' in windows_eval_text,
            "stale_policy_fingerprint": '"policy_fingerprint": "a1c9e95421ffe9755acc13028b05c3b45b960ad5d2ee750685bf56db1d44d03a"' in windows_eval_text,
        },
        {
            "shared_literal": True,
            "private_literal": True,
            "unsafe_shared_interpolation": False,
            "unsafe_private_interpolation": False,
            "current_policy_fingerprint": True,
            "stale_policy_fingerprint": False,
        },
    )

    check(
        "V1C2C1 FROZEN BUNDLE METADATA REJECTS MUTATION",
        _mutation_blocked(bundle),
        True,
    )

    mutated_policy = replace(policy, architecture_slice_identity="0" * 64)
    check(
        "V1C2C1 POLICY MUTATION INVALIDATES LOCK AND FINGERPRINT",
        {
            "fingerprint_changed": developer_task_execution_compile_ast_controller_worker_policy_fingerprint(mutated_policy) != policy.policy_fingerprint,
            "errors": list(validate_developer_task_execution_compile_ast_controller_worker_policy(mutated_policy)),
        },
        {
            "fingerprint_changed": True,
            "errors": ["policy_identity_invalid", "policy_fingerprint_invalid", "policy_bytes_invalid"],
        },
    )

    check(
        "V1C2C1 PYTHON MODULE REMAINS SYNTACTICALLY VALID HOST DATA",
        {"nodes": len(module_tree.body) > 0, "main_guard": '__name__ == "__main__"' in module_text},
        {"nodes": True, "main_guard": False},
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


def _mutation_blocked(bundle: Any) -> bool:
    try:
        bundle.bundle_id = "mutated"
    except FrozenInstanceError:
        return True
    except Exception:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
