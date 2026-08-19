from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_compile_ast_controller_worker import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_SHA256,
    build_developer_task_execution_compile_ast_controller_worker_bundle,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
)


_COMPILE_SCRIPT = r'''param(
    [Parameter(Mandatory = $true)][string]$PolicyPath,
    [Parameter(Mandatory = $true)][string]$NativeHelperPath,
    [Parameter(Mandatory = $true)][string]$BootstrapPath,
    [Parameter(Mandatory = $true)][string]$ControllerPath,
    [Parameter(Mandatory = $true)][string]$WsbPath
)

$ErrorActionPreference = "Stop"

$strictUtf8 = [System.Text.UTF8Encoding]::new($false, $true)
$policyText = [System.IO.File]::ReadAllText($PolicyPath, $strictUtf8)
$bootstrapText = [System.IO.File]::ReadAllText($BootstrapPath, $strictUtf8)
$controllerText = [System.IO.File]::ReadAllText($ControllerPath, $strictUtf8)
$wsbText = [System.IO.File]::ReadAllText($WsbPath, $strictUtf8)

$policy = $policyText | ConvertFrom-Json
[ScriptBlock]::Create($bootstrapText) | Out-Null
[ScriptBlock]::Create($controllerText) | Out-Null

Add-Type `
    -Path $NativeHelperPath `
    -ErrorAction Stop

if ([V1C2C1Native]::WORKER_INTEGRITY_RID -ne 8192) {
    throw "Compiled V1C2C1 helper exposes an unexpected worker integrity RID."
}
if ([V1C2C1Native]::JOB_OBJECT_LIMIT_ACTIVE_PROCESS -ne 0x00000008) {
    throw "Compiled V1C2C1 helper exposes an unexpected active-process flag."
}
if ([V1C2C1Native]::JOB_OBJECT_LIMIT_PROCESS_MEMORY -ne 0x00000100) {
    throw "Compiled V1C2C1 helper exposes an unexpected process-memory flag."
}
if ([V1C2C1Native]::JOB_OBJECT_LIMIT_JOB_MEMORY -ne 0x00000200) {
    throw "Compiled V1C2C1 helper exposes an unexpected Job-memory flag."
}
if ([V1C2C1Native]::JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE -ne 0x00002000) {
    throw "Compiled V1C2C1 helper exposes an unexpected kill-on-close flag."
}
if ([V1C2C1Native]::COMPILE_AST_ACTIVE_PROCESS_LIMIT -ne 1) {
    throw "Compiled V1C2C1 helper exposes an unexpected active-process limit."
}
if ([uint64][V1C2C1Native]::COMPILE_AST_PROCESS_MEMORY_BYTES -ne 536870912) {
    throw "Compiled V1C2C1 helper exposes an unexpected process-memory limit."
}
if ([uint64][V1C2C1Native]::COMPILE_AST_JOB_MEMORY_BYTES -ne 805306368) {
    throw "Compiled V1C2C1 helper exposes an unexpected Job-memory limit."
}
if ([V1C2C1Native]::RUNTIME_EXECUTABLE_FILE_NAME -cne "python.exe") {
    throw "Compiled V1C2C1 helper exposes an unexpected runtime executable name."
}

if ([string]$policy.architecture_lock.slice -cne "V1C2C1") {
    throw "V1C2C1 policy architecture slice is invalid."
}
if ([string]$policy.worker.account -cne "fresh_local_standard_user") {
    throw "V1C2C1 policy worker account type is invalid."
}
if ([bool]$policy.worker.administrator) {
    throw "V1C2C1 policy unexpectedly allows an administrative worker."
}
if ([int]$policy.worker.integrity_rid -ne 8192) {
    throw "V1C2C1 policy worker integrity is invalid."
}
if ([string]$policy.worker.launch.api -cne "CreateProcessAsUserW") {
    throw "V1C2C1 policy launch API is invalid."
}
if ([bool]$policy.worker.launch.inherit_handles) {
    throw "V1C2C1 policy unexpectedly allows inherited handles."
}
if (-not [bool]$policy.worker.launch.create_suspended) {
    throw "V1C2C1 policy does not require CREATE_SUSPENDED."
}
if (-not [bool]$policy.worker.launch.assign_to_job_before_resume) {
    throw "V1C2C1 policy does not require assign-before-resume."
}
if ([int]$policy.worker.job.active_process_limit -ne 1) {
    throw "V1C2C1 policy active-process limit is invalid."
}
if ([int64]$policy.worker.job.process_memory_bytes -ne 536870912) {
    throw "V1C2C1 policy process-memory limit is invalid."
}
if ([int64]$policy.worker.job.job_memory_bytes -ne 805306368) {
    throw "V1C2C1 policy Job-memory limit is invalid."
}
if (-not [bool]$policy.worker.job.kill_on_close) {
    throw "V1C2C1 policy does not require kill-on-close."
}
if ([bool]$policy.worker.job.breakaway_allowed -or [bool]$policy.worker.job.silent_breakaway_allowed) {
    throw "V1C2C1 policy unexpectedly allows Job breakaway."
}

[xml]$wsb = $wsbText
$mappedFolders = @($wsb.Configuration.MappedFolders.MappedFolder)
if ($mappedFolders.Count -ne 4) { throw "V1C2C1 WSB does not contain exactly four mappings." }
if (@($mappedFolders | Where-Object { [string]$_.ReadOnly -eq "true" }).Count -ne 3) { throw "V1C2C1 WSB read-only mapping count is invalid." }
if (@($mappedFolders | Where-Object { [string]$_.ReadOnly -eq "false" }).Count -ne 1) { throw "V1C2C1 WSB writable mapping count is invalid." }
if ([string]$wsb.Configuration.Networking -cne "Disable") { throw "V1C2C1 WSB networking is not disabled." }
if ([string]$wsb.Configuration.VGpu -cne "Disable") { throw "V1C2C1 WSB vGPU is not disabled." }
if ([string]$wsb.Configuration.AudioInput -cne "Disable") { throw "V1C2C1 WSB audio input is not disabled." }
if ([string]$wsb.Configuration.VideoInput -cne "Disable") { throw "V1C2C1 WSB video input is not disabled." }
if ([string]$wsb.Configuration.PrinterRedirection -cne "Disable") { throw "V1C2C1 WSB printer redirection is not disabled." }
if ([string]$wsb.Configuration.ClipboardRedirection -cne "Disable") { throw "V1C2C1 WSB clipboard redirection is not disabled." }
if ([string]$wsb.Configuration.ProtectedClient -cne "Enable") { throw "V1C2C1 WSB ProtectedClient is not enabled." }
if ([int]$wsb.Configuration.MemoryInMB -ne 4096) { throw "V1C2C1 WSB memory setting is invalid." }

[pscustomobject]@{
    native_helper_compiled = $true
    bootstrap_parsed = $true
    controller_parsed = $true
    policy_parsed = $true
    wsb_parsed = $true
    architecture_slice = [string]$policy.architecture_lock.slice
    worker_integrity_rid = [int][V1C2C1Native]::WORKER_INTEGRITY_RID
    active_process_limit = [uint32][V1C2C1Native]::COMPILE_AST_ACTIVE_PROCESS_LIMIT
    process_memory_bytes = [uint64][V1C2C1Native]::COMPILE_AST_PROCESS_MEMORY_BYTES
    job_memory_bytes = [uint64][V1C2C1Native]::COMPILE_AST_JOB_MEMORY_BYTES
    mapped_folders = $mappedFolders.Count
    readonly_mappings = 3
    writable_mappings = 1
    networking_disabled = $true
    inherited_handles = $false
    create_suspended = $true
    assign_before_resume = $true
    sandbox_launched = $false
    claim_transaction_consumed = $false
    runtime_lease_claimed = $false
    interpreter_executed = $false
    changed_source_processed = $false
    execution_authorized = $false
} | ConvertTo-Json -Compress
'''


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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

    if sys.platform != "win32":
        print("[SKIP] V1C2C1 PowerShell/C# compile-only smoke requires win32.")
        return 0

    bundle = build_developer_task_execution_compile_ast_controller_worker_bundle()

    with tempfile.TemporaryDirectory(prefix="skynetvs-v1c2c1-compile-") as temp_dir:
        root = Path(temp_dir)
        paths: dict[str, Path] = {}
        for payload in bundle.payloads:
            path = root / payload.file_name
            path.write_bytes(payload.exact_bytes())
            paths[payload.kind] = path
        script_path = root / "compile_v1c2c1.ps1"
        script_path.write_text(_COMPILE_SCRIPT, encoding="utf-8", newline="\n")

        check(
            "EXACT V1C2C1 PAYLOAD BYTES ARE STAGED FOR COMPILE AND PARSE ONLY",
            {
                "policy": _sha256(paths["compile_ast_controller_worker_policy"].read_bytes()),
                "bootstrap": _sha256(paths["trusted_bootstrap"].read_bytes()),
                "native": _sha256(paths["trusted_native_helper"].read_bytes()),
                "controller": _sha256(paths["trusted_system_controller"].read_bytes()),
                "wsb": _sha256(paths["windows_sandbox_template"].read_bytes()),
                "bundle_fingerprint": bundle.bundle_fingerprint,
                "candidate_python_present": (root / "python.exe").exists(),
            },
            {
                "policy": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
                "bootstrap": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_SHA256,
                "native": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_SHA256,
                "controller": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_SHA256,
                "wsb": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_SHA256,
                "bundle_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_FINGERPRINT,
                "candidate_python_present": False,
            },
        )

        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-PolicyPath",
                str(paths["compile_ast_controller_worker_policy"]),
                "-NativeHelperPath",
                str(paths["trusted_native_helper"]),
                "-BootstrapPath",
                str(paths["trusted_bootstrap"]),
                "-ControllerPath",
                str(paths["trusted_system_controller"]),
                "-WsbPath",
                str(paths["windows_sandbox_template"]),
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=90.0,
            check=False,
        )

        last_json: dict[str, Any] | None = None
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                last_json = parsed

        check(
            "V1C2C1 NATIVE HELPER COMPILES AND FIXED POWERSHELL POLICY WSB PAYLOADS PARSE WITHOUT EXECUTION",
            {
                "returncode": completed.returncode,
                "native_helper_compiled": bool(last_json and last_json.get("native_helper_compiled")),
                "bootstrap_parsed": bool(last_json and last_json.get("bootstrap_parsed")),
                "controller_parsed": bool(last_json and last_json.get("controller_parsed")),
                "policy_parsed": bool(last_json and last_json.get("policy_parsed")),
                "wsb_parsed": bool(last_json and last_json.get("wsb_parsed")),
                "architecture_slice": str(last_json.get("architecture_slice", "")) if last_json else "",
                "worker_integrity_rid": int(last_json.get("worker_integrity_rid", 0)) if last_json else 0,
                "active_process_limit": int(last_json.get("active_process_limit", 0)) if last_json else 0,
                "process_memory_bytes": int(last_json.get("process_memory_bytes", 0)) if last_json else 0,
                "job_memory_bytes": int(last_json.get("job_memory_bytes", 0)) if last_json else 0,
                "mapped_folders": int(last_json.get("mapped_folders", 0)) if last_json else 0,
                "readonly_mappings": int(last_json.get("readonly_mappings", 0)) if last_json else 0,
                "writable_mappings": int(last_json.get("writable_mappings", 0)) if last_json else 0,
                "networking_disabled": bool(last_json and last_json.get("networking_disabled")),
                "inherited_handles": bool(last_json and last_json.get("inherited_handles")),
                "create_suspended": bool(last_json and last_json.get("create_suspended")),
                "assign_before_resume": bool(last_json and last_json.get("assign_before_resume")),
                "sandbox_launched": bool(last_json and last_json.get("sandbox_launched")),
                "claim_transaction_consumed": bool(last_json and last_json.get("claim_transaction_consumed")),
                "runtime_lease_claimed": bool(last_json and last_json.get("runtime_lease_claimed")),
                "interpreter_executed": bool(last_json and last_json.get("interpreter_executed")),
                "changed_source_processed": bool(last_json and last_json.get("changed_source_processed")),
                "execution_authorized": bool(last_json and last_json.get("execution_authorized")),
                "stderr": completed.stderr.strip(),
            },
            {
                "returncode": 0,
                "native_helper_compiled": True,
                "bootstrap_parsed": True,
                "controller_parsed": True,
                "policy_parsed": True,
                "wsb_parsed": True,
                "architecture_slice": "V1C2C1",
                "worker_integrity_rid": 8192,
                "active_process_limit": 1,
                "process_memory_bytes": 536870912,
                "job_memory_bytes": 805306368,
                "mapped_folders": 4,
                "readonly_mappings": 3,
                "writable_mappings": 1,
                "networking_disabled": True,
                "inherited_handles": False,
                "create_suspended": True,
                "assign_before_resume": True,
                "sandbox_launched": False,
                "claim_transaction_consumed": False,
                "runtime_lease_claimed": False,
                "interpreter_executed": False,
                "changed_source_processed": False,
                "execution_authorized": False,
                "stderr": "",
            },
        )

        check(
            "V1C2C1 WINDOWS COMPILE EVALUATOR HAS NO SANDBOX OR CANDIDATE PYTHON LAUNCH COMMAND",
            {
                "windows_sandbox": "WindowsSandbox.exe" in _COMPILE_SCRIPT,
                "start_process": "Start-Process" in _COMPILE_SCRIPT,
                "invoke_expression": "Invoke-Expression" in _COMPILE_SCRIPT,
                "process_start": "System.Diagnostics.Process" in _COMPILE_SCRIPT,
                "runtime_executable_call": "C:\\SkynetVSRuntime\\python.exe" in _COMPILE_SCRIPT,
                "architecture_lock": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY,
                "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
            },
            {
                "windows_sandbox": False,
                "start_process": False,
                "invoke_expression": False,
                "process_start": False,
                "runtime_executable_call": False,
                "architecture_lock": "db0624732f29c5b8d62850567c8e6de75482e65d334175ab04d5a4926242c4ec",
                "policy_fingerprint": "0a559e9a9bcac241a18b0e3cbe31263f4f01a5a94eaf70ee7d65382297a62baf",
            },
        )

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {"case_count": case_count, "fail_count": fail_count},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
