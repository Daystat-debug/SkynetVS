from __future__ import annotations

import hashlib
import inspect
import json

from dataclasses import FrozenInstanceError, replace
from typing import Any

from modules.developer.developer_task_execution_boundary_policy import (
    SIGNED_BOUNDARY_FINGERPRINT,
    WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1,
)
from modules.developer.developer_task_execution_boundary_worker import (
    WORKER_BUNDLE_FINGERPRINT,
    WORKER_BUNDLE_ID,
    build_developer_task_execution_boundary_worker_bundle,
)
from modules.developer.developer_task_execution_boundary_worker_payload import (
    WORKER_NATIVE_HELPER_BYTES,
    WORKER_NATIVE_HELPER_SHA256,
    WORKER_PROBE_EXECUTABLE_FILE_NAME,
    WORKER_PROBE_SOURCE_BYTES,
    WORKER_PROBE_SOURCE_SHA256,
)


_EXPECTED_NATIVE_SHA256 = "3ae43302a5ac85bde9dfd70ce0e17267e7db1b04d5729554a1416b1c2e9adc7d"
_EXPECTED_WORKER_SHA256 = "9aadbaa68fd2728b138a6f85f7ac03477910d970854572cf8fe506139a75777b"
_EXPECTED_BUNDLE_FINGERPRINT = "a15433a891aade5647f4ae9f5cad41a2fce72e4c6ccd3ba4c86a2794604b81a0"


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
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2, default=str))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    bundle = build_developer_task_execution_boundary_worker_bundle()
    second = build_developer_task_execution_boundary_worker_bundle()
    native_text = WORKER_NATIVE_HELPER_BYTES.decode("utf-8")
    worker_text = WORKER_PROBE_SOURCE_BYTES.decode("utf-8")

    check(
        "CANONICAL WORKER BUNDLE BUILDS FAIL CLOSED",
        {
            "ok": bundle.ok,
            "bundle_id": bundle.bundle_id,
            "boundary": bundle.boundary_fingerprint,
            "execution_authorized": bundle.execution_authorized,
        },
        {
            "ok": True,
            "bundle_id": WORKER_BUNDLE_ID,
            "boundary": SIGNED_BOUNDARY_FINGERPRINT,
            "execution_authorized": False,
        },
    )

    check(
        "WORKER BUNDLE BUILDER ACCEPTS NO INPUTS",
        list(inspect.signature(build_developer_task_execution_boundary_worker_bundle).parameters),
        [],
    )

    check(
        "WORKER BUNDLE IS DETERMINISTIC",
        {
            "metadata": bundle.to_dict() == second.to_dict(),
            "native": bundle.native_helper.exact_bytes() == second.native_helper.exact_bytes(),
            "worker": bundle.worker_probe.exact_bytes() == second.worker_probe.exact_bytes(),
        },
        {"metadata": True, "native": True, "worker": True},
    )

    check(
        "WORKER PAYLOAD HASHES ARE LOCKED",
        {
            "native": WORKER_NATIVE_HELPER_SHA256,
            "worker": WORKER_PROBE_SOURCE_SHA256,
            "bundle": WORKER_BUNDLE_FINGERPRINT,
        },
        {
            "native": _EXPECTED_NATIVE_SHA256,
            "worker": _EXPECTED_WORKER_SHA256,
            "bundle": _EXPECTED_BUNDLE_FINGERPRINT,
        },
    )

    check(
        "WORKER PAYLOAD HASHES MATCH EXACT BYTES",
        {
            "native": hashlib.sha256(bundle.native_helper.exact_bytes()).hexdigest(),
            "worker": hashlib.sha256(bundle.worker_probe.exact_bytes()).hexdigest(),
        },
        {
            "native": bundle.native_helper.sha256,
            "worker": bundle.worker_probe.sha256,
        },
    )

    check(
        "WORKER PAYLOADS USE CANONICAL UTF8 LF BYTES",
        {
            "native_bom": bundle.native_helper.exact_bytes().startswith(b"\xef\xbb\xbf"),
            "worker_bom": bundle.worker_probe.exact_bytes().startswith(b"\xef\xbb\xbf"),
            "native_cr": b"\r" in bundle.native_helper.exact_bytes(),
            "worker_cr": b"\r" in bundle.worker_probe.exact_bytes(),
            "native_final_lf": bundle.native_helper.exact_bytes().endswith(b"\n"),
            "worker_final_lf": bundle.worker_probe.exact_bytes().endswith(b"\n"),
        },
        {
            "native_bom": False,
            "worker_bom": False,
            "native_cr": False,
            "worker_cr": False,
            "native_final_lf": True,
            "worker_final_lf": True,
        },
    )

    check(
        "WORKER BUNDLE SERIALIZATION HIDES EXACT SOURCE BYTES",
        {
            "native_source_in_repr": "using System;" in repr(bundle),
            "worker_source_in_repr": "SkynetVSWorkerProbe" in repr(bundle),
            "native_bytes_serialized": "_bytes" in bundle.to_dict()["native_helper"],
            "worker_bytes_serialized": "_bytes" in bundle.to_dict()["worker_probe"],
            "source_field_serialized": "source" in bundle.to_dict()["native_helper"],
        },
        {
            "native_source_in_repr": False,
            "worker_source_in_repr": False,
            "native_bytes_serialized": False,
            "worker_bytes_serialized": False,
            "source_field_serialized": False,
        },
    )

    immutable = False
    try:
        bundle.bundle_id = "mutated"  # type: ignore[misc]
    except FrozenInstanceError:
        immutable = True
    check("WORKER BUNDLE IS IMMUTABLE", immutable, True)

    check(
        "WORKER BUNDLE BINDS THE VERIFIED V1B3 POLICY",
        {
            "policy_ok": WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.ok,
            "boundary_match": bundle.boundary_fingerprint == WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.fingerprint,
            "execution_authorized": bundle.to_dict()["execution_authorized"],
        },
        {"policy_ok": True, "boundary_match": True, "execution_authorized": False},
    )

    forged = replace(bundle, execution_authorized=True)
    check("FORGED EXECUTION AUTHORIZATION INVALIDATES BUNDLE", forged.ok, False)

    check(
        "FRESH ACCOUNT CREATION HAS COLLISION AND EXACT SID GUARDS",
        {
            "name_from_request": "BuildWorkerUserName" in native_text,
            "precheck": "ResolveLocalAccountSidOrNull(username) != null" in native_text,
            "user_exists": "NERR_USER_EXISTS" in native_text,
            "created_sid": "createdSid = ResolveLocalAccountSidOrNull(username)" in native_text,
            "delete_exact": "DeleteLocalUserExact" in native_text,
            "sid_changed": "Worker account SID changed before deletion." in native_text,
            "post_delete": "Worker account still resolves after deletion." in native_text,
        },
        {
            "name_from_request": True,
            "precheck": True,
            "user_exists": True,
            "created_sid": True,
            "delete_exact": True,
            "sid_changed": True,
            "post_delete": True,
        },
    )

    check(
        "PASSWORD SECRET IS MEMORY ONLY AND ZEROED",
        {
            "secret_type": "WorkerPasswordSecret : IDisposable" in native_text,
            "unmanaged": "Marshal.AllocHGlobal" in native_text,
            "array_clear": native_text.count("Array.Clear(") >= 2,
            "zero_write": "Marshal.WriteInt16(buffer, index * 2, 0)" in native_text,
            "using_secret": "using (WorkerPasswordSecret password = WorkerPasswordSecret.CreateRandom())" in native_text,
            "no_env_set": "SetEnvironmentVariable" not in native_text,
            "no_password_argument": "--password" not in native_text,
        },
        {
            "secret_type": True,
            "unmanaged": True,
            "array_clear": True,
            "zero_write": True,
            "using_secret": True,
            "no_env_set": True,
            "no_password_argument": True,
        },
    )

    check(
        "LOGON TOKEN IS EXACT PRIMARY NONADMIN MEDIUM TOKEN",
        {
            "logon": "LogonUserW" in native_text,
            "token_sid": "GetTokenUserSid(token)" in native_text,
            "sid_match": "Worker token SID does not match the created account SID." in native_text,
            "primary": "tokenType != TokenPrimary" in native_text,
            "non_admin": "if (administrator)" in native_text,
            "medium": "integrityRid != WORKER_INTEGRITY_RID" in native_text,
            "medium_rid": "WORKER_INTEGRITY_RID = 0x2000" in native_text,
        },
        {
            "logon": True,
            "token_sid": True,
            "sid_match": True,
            "primary": True,
            "non_admin": True,
            "medium": True,
            "medium_rid": True,
        },
    )

    check(
        "WORKER ENVIRONMENT AND HANDLES ARE NOT INHERITED",
        {
            "environment": "CreateEnvironmentBlock(out environment, token, false)" in native_text,
            "destroy": "DestroyEnvironmentBlock(environment)" in native_text,
            "unicode": "CREATE_UNICODE_ENVIRONMENT" in native_text,
            "inherit_handles_false": "false,\n                creationFlags," in native_text,
        },
        {
            "environment": True,
            "destroy": True,
            "unicode": True,
            "inherit_handles_false": True,
        },
    )

    launch_body = native_text.split("public static WorkerLaunchState LaunchFixedWorkerSuspendedInJob", 1)[1].split("public static uint ResumeWorker", 1)[0]
    check(
        "WORKER IS ASSIGNED TO JOB BEFORE RESUME",
        {
            "create_suspended": "CREATE_SUSPENDED" in launch_body,
            "assign": "AssignProcessToJobObject" in launch_body,
            "verify": "IsProcessInJob" in launch_body,
            "resume_absent": "ResumeThread" not in launch_body,
            "assigned_before_resume": "AssignedBeforeResume = true" in launch_body,
        },
        {
            "create_suspended": True,
            "assign": True,
            "verify": True,
            "resume_absent": True,
            "assigned_before_resume": True,
        },
    )

    check(
        "JOB POLICY IS KILL ON CLOSE WITH NO BREAKAWAY",
        {
            "kill_on_close": "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in native_text,
            "create_breakaway": "CREATE_BREAKAWAY_FROM_JOB" in native_text,
            "breakaway_ok": "JOB_OBJECT_LIMIT_BREAKAWAY_OK" in native_text,
            "silent_breakaway": "JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK" in native_text,
        },
        {
            "kill_on_close": True,
            "create_breakaway": False,
            "breakaway_ok": False,
            "silent_breakaway": False,
        },
    )

    check(
        "FAILED SUSPENDED LAUNCH IS TERMINATED BEFORE HANDLE RELEASE",
        {
            "terminate": "TerminateProcess(processInformation.hProcess, 0xEE)" in launch_body,
            "wait": "WaitForSingleObject(processInformation.hProcess, 5000)" in launch_body,
            "close_thread": "CloseHandle(processInformation.hThread)" in launch_body,
            "close_process": "CloseHandle(processInformation.hProcess)" in launch_body,
        },
        {"terminate": True, "wait": True, "close_thread": True, "close_process": True},
    )

    check(
        "WORKER APPLICATION AND COMMAND SHAPE ARE FIXED",
        {
            "fixed_exe": WORKER_PROBE_EXECUTABLE_FILE_NAME in native_text,
            "explicit_application": "workerExecutablePath,\n                commandLine," in launch_body,
            "fixed_builder": "BuildFixedWorkerCommandLine" in launch_body,
            "no_shell_execute": "ShellExecute" not in native_text,
            "no_cmd": "cmd.exe" not in native_text.lower(),
            "no_powershell": "powershell.exe" not in native_text.lower(),
        },
        {
            "fixed_exe": True,
            "explicit_application": True,
            "fixed_builder": True,
            "no_shell_execute": True,
            "no_cmd": True,
            "no_powershell": True,
        },
    )

    check(
        "STAGING ACLS ARE PROTECTED AND LEAST PRIVILEGE",
        {
            "protected": "SetAccessRuleProtection(true, false)" in native_text,
            "system_owner": "WellKnownSidType.LocalSystemSid" in native_text,
            "system_full": "FileSystemRights.FullControl" in native_text,
            "read_execute": "PrepareWorkerReadExecuteDirectory" in native_text,
            "result_write": "PrepareWorkerResultDirectory" in native_text,
            "private": "ProtectControllerPrivateDirectory" in native_text,
        },
        {
            "protected": True,
            "system_owner": True,
            "system_full": True,
            "read_execute": True,
            "result_write": True,
            "private": True,
        },
    )

    check(
        "PROCESS SWEEP USES WTS PRIMARY TOKEN SIDS",
        {
            "enumerate": "WTSEnumerateProcessesExW" in native_text,
            "level": "uint level = 1" in native_text,
            "all_sessions": "WTS_ANY_SESSION" in native_text,
            "user_sid": "pUserSid" in native_text,
            "free": "WTSFreeMemoryExW" in native_text,
            "no_process_get_processes": "Process.GetProcesses" not in native_text,
        },
        {
            "enumerate": True,
            "level": True,
            "all_sessions": True,
            "user_sid": True,
            "free": True,
            "no_process_get_processes": True,
        },
    )

    check(
        "PROCESS SWEEP REQUIRES BOUNDED CONSECUTIVE EMPTY SCANS",
        {
            "max_attempts": "WORKER_SWEEP_MAX_ATTEMPTS = 8" in native_text,
            "delay": "WORKER_SWEEP_DELAY_MS = 250" in native_text,
            "empty_scans": "WORKER_SWEEP_REQUIRED_EMPTY_SCANS = 3" in native_text,
            "fail_closed": "did not become quiescent within the bounded sweep window" in native_text,
        },
        {"max_attempts": True, "delay": True, "empty_scans": True, "fail_closed": True},
    )

    check(
        "FORBIDDEN ALTERNATE LAUNCH SURFACES ARE ABSENT",
        {
            "create_process_with_logon": "CreateProcessWithLogon" in native_text,
            "win32_process": "Win32_Process" in native_text,
            "process_start": "Process.Start" in native_text,
            "system_diagnostics_process": "System.Diagnostics.Process" in native_text,
        },
        {
            "create_process_with_logon": False,
            "win32_process": False,
            "process_start": False,
            "system_diagnostics_process": False,
        },
    )

    expected_worker_fields = [
        "schema_version",
        "request_id",
        "worker_sid",
        "worker_name",
        "worker_is_administrator",
        "worker_integrity_rid",
        "controller_secret_absent",
        "sentinel_handle_inherited",
        "controller_vm_read_blocked",
        "input_write_blocked",
        "control_write_blocked",
        "output_writable",
        "worker_in_job",
        "child_pid",
        "child_in_job",
        "overall_ok",
    ]
    check(
        "BENIGN WORKER EMITS THE V1B3B WORKER RESULT CONTRACT",
        [field for field in expected_worker_fields if ('\\"' + field + '\\"') in worker_text],
        expected_worker_fields,
    )

    check(
        "BENIGN WORKER PROVES NONADMIN MEDIUM PRIVILEGE",
        {
            "admin_probe": "IsAdministrator()" in worker_text,
            "medium_exact": "integrityRid == 0x2000" in worker_text,
            "controller_secret": "SKYNETVS_CONTROLLER_SECRET" in worker_text,
            "controller_vm_read": "PROCESS_VM_READ" in worker_text,
            "sentinel": "GetHandleInformation" in worker_text,
        },
        {
            "admin_probe": True,
            "medium_exact": True,
            "controller_secret": True,
            "controller_vm_read": True,
            "sentinel": True,
        },
    )

    check(
        "BENIGN WORKER SELF CHILD DOES NOT USE SHELL",
        {
            "self_executable": "Assembly.GetExecutingAssembly().Location" in worker_text,
            "child": "--child" in worker_text,
            "use_shell_false": "UseShellExecute = false" in worker_text,
            "child_job": "childJobQuery = IsProcessInJob" in worker_text,
            "sleep": "Thread.Sleep(120000)" in worker_text,
        },
        {
            "self_executable": True,
            "child": True,
            "use_shell_false": True,
            "child_job": True,
            "sleep": True,
        },
    )

    production_source = inspect.getsource(build_developer_task_execution_boundary_worker_bundle)
    check(
        "PRODUCTION BUILDER HAS NO TASK OR EXECUTION INPUT SURFACE",
        {
            "manifest": "manifest" in production_source,
            "workspace": "workspace" in production_source,
            "patch": "patch" in production_source,
            "command": "command_line" in production_source,
            "executable_input": "executable_path" in production_source,
            "execution_true": "execution_authorized=True" in production_source,
        },
        {
            "manifest": False,
            "workspace": False,
            "patch": False,
            "command": False,
            "executable_input": False,
            "execution_true": False,
        },
    )

    check(
        "V1B3C PYTHON BUNDLE BUILDER NEVER LAUNCHES CODE",
        {
            "subprocess": "subprocess" in production_source,
            "popen": "Popen" in production_source,
            "system": "os.system" in production_source,
            "sandbox": "WindowsSandbox" in production_source,
        },
        {"subprocess": False, "popen": False, "system": False, "sandbox": False},
    )

    check(
        "WORKER PAYLOAD FILE NAMES ARE FIXED",
        {
            "native": bundle.native_helper.file_name,
            "worker_source": bundle.worker_probe.file_name,
            "worker_executable": bundle.worker_executable_file_name,
        },
        {
            "native": "SkynetVS_V1B3C_native_helper.cs",
            "worker_source": "SkynetVS_V1B3C_worker_probe.cs",
            "worker_executable": "SkynetVS_V1B3C_worker_probe.exe",
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
