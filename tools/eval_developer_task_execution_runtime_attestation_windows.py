from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_runtime_attestation import (
    build_developer_task_execution_runtime_attestation_payload,
)
from modules.developer.developer_task_execution_runtime_attestation_payload import (
    build_runtime_attestation_wsb_config,
)


_COMPILE_SCRIPT = r'''param(
    [Parameter(Mandatory = $true)][string]$NativeHelperPath,
    [Parameter(Mandatory = $true)][string]$BootstrapPath,
    [Parameter(Mandatory = $true)][string]$ControllerPath,
    [Parameter(Mandatory = $true)][string]$WsbPath
)

$ErrorActionPreference = "Stop"

$bootstrapText = [System.IO.File]::ReadAllText($BootstrapPath, [System.Text.UTF8Encoding]::new($false, $true))
$controllerText = [System.IO.File]::ReadAllText($ControllerPath, [System.Text.UTF8Encoding]::new($false, $true))
[ScriptBlock]::Create($bootstrapText) | Out-Null
[ScriptBlock]::Create($controllerText) | Out-Null

Add-Type `
    -Path $NativeHelperPath `
    -ErrorAction Stop

if ([V1B4CNative]::WORKER_INTEGRITY_RID -ne 8192) {
    throw "Compiled V1B4C native helper exposes an unexpected worker integrity RID."
}
if ([V1B4CNative]::RUNTIME_EXECUTABLE_FILE_NAME -cne "python.exe") {
    throw "Compiled V1B4C native helper exposes an unexpected runtime executable name."
}

[xml]$wsb = [System.IO.File]::ReadAllText($WsbPath, [System.Text.UTF8Encoding]::new($false, $true))
$mappedFolders = @($wsb.Configuration.MappedFolders.MappedFolder)
if ($mappedFolders.Count -ne 4) { throw "V1B4C WSB does not contain exactly four mappings." }
if (@($mappedFolders | Where-Object { [string]$_.ReadOnly -eq "true" }).Count -ne 3) { throw "V1B4C WSB read-only mapping count is invalid." }
if (@($mappedFolders | Where-Object { [string]$_.ReadOnly -eq "false" }).Count -ne 1) { throw "V1B4C WSB writable mapping count is invalid." }
if ([string]$wsb.Configuration.Networking -cne "Disable") { throw "V1B4C WSB networking is not disabled." }
if ([string]$wsb.Configuration.VGpu -cne "Disable") { throw "V1B4C WSB vGPU is not disabled." }
if ([string]$wsb.Configuration.ProtectedClient -cne "Enable") { throw "V1B4C WSB ProtectedClient is not enabled." }

[pscustomobject]@{
    native_helper_compiled = $true
    bootstrap_parsed = $true
    controller_parsed = $true
    wsb_parsed = $true
    mapped_folders = $mappedFolders.Count
    readonly_mappings = 3
    writable_mappings = 1
    sandbox_launched = $false
    interpreter_executed = $false
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
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2, default=str))
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    if sys.platform != "win32":
        print("[SKIP] V1B4C1 PowerShell/C# compile-only smoke requires win32.")
        return 0

    bundle = build_developer_task_execution_runtime_attestation_payload()
    wsb_bytes = build_runtime_attestation_wsb_config(
        input_host_path=r"C:\SkynetVSHost\Input",
        runtime_host_path=r"C:\SkynetVSHost\Runtime",
        control_host_path=r"C:\SkynetVSHost\Control",
        output_host_path=r"C:\SkynetVSHost\Output",
    )

    with tempfile.TemporaryDirectory(prefix="skynetvs-v1b4c1-compile-") as temp_dir:
        root = Path(temp_dir)
        native_path = root / bundle.native_helper.file_name
        bootstrap_path = root / bundle.bootstrap.file_name
        controller_path = root / bundle.controller.file_name
        wsb_path = root / bundle.wsb_template.file_name
        script_path = root / "compile_v1b4c1.ps1"

        native_path.write_bytes(bundle.native_helper.exact_bytes())
        bootstrap_path.write_bytes(bundle.bootstrap.exact_bytes())
        controller_path.write_bytes(bundle.controller.exact_bytes())
        wsb_path.write_bytes(wsb_bytes)
        script_path.write_text(_COMPILE_SCRIPT, encoding="utf-8", newline="\n")

        check(
            "EXACT V1B4C1 PAYLOAD BYTES ARE STAGED FOR COMPILE AND PARSE ONLY",
            {
                "native": _sha256(native_path.read_bytes()),
                "bootstrap": _sha256(bootstrap_path.read_bytes()),
                "controller": _sha256(controller_path.read_bytes()),
                "template": _sha256(bundle.wsb_template.exact_bytes()),
                "candidate_python_present": (root / "python.exe").exists(),
            },
            {
                "native": bundle.native_helper.sha256,
                "bootstrap": bundle.bootstrap.sha256,
                "controller": bundle.controller.sha256,
                "template": bundle.wsb_template.sha256,
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
                "-NativeHelperPath",
                str(native_path),
                "-BootstrapPath",
                str(bootstrap_path),
                "-ControllerPath",
                str(controller_path),
                "-WsbPath",
                str(wsb_path),
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
            "V1B4C1 NATIVE HELPER COMPILES AND POWERSHELL WSB PAYLOADS PARSE WITHOUT EXECUTION",
            {
                "returncode": completed.returncode,
                "native_helper_compiled": bool(last_json and last_json.get("native_helper_compiled")),
                "bootstrap_parsed": bool(last_json and last_json.get("bootstrap_parsed")),
                "controller_parsed": bool(last_json and last_json.get("controller_parsed")),
                "wsb_parsed": bool(last_json and last_json.get("wsb_parsed")),
                "mapped_folders": int(last_json.get("mapped_folders", 0)) if last_json else 0,
                "readonly_mappings": int(last_json.get("readonly_mappings", 0)) if last_json else 0,
                "writable_mappings": int(last_json.get("writable_mappings", 0)) if last_json else 0,
                "sandbox_launched": bool(last_json and last_json.get("sandbox_launched")),
                "interpreter_executed": bool(last_json and last_json.get("interpreter_executed")),
                "execution_authorized": bool(last_json and last_json.get("execution_authorized")),
                "stderr": completed.stderr.strip(),
            },
            {
                "returncode": 0,
                "native_helper_compiled": True,
                "bootstrap_parsed": True,
                "controller_parsed": True,
                "wsb_parsed": True,
                "mapped_folders": 4,
                "readonly_mappings": 3,
                "writable_mappings": 1,
                "sandbox_launched": False,
                "interpreter_executed": False,
                "execution_authorized": False,
                "stderr": "",
            },
        )

        check(
            "V1B4C1 WINDOWS COMPILE EVALUATOR HAS NO SANDBOX OR CANDIDATE PYTHON LAUNCH COMMAND",
            {
                "windows_sandbox": "WindowsSandbox.exe" in _COMPILE_SCRIPT,
                "candidate_python": "python.exe" in _COMPILE_SCRIPT and "RUNTIME_EXECUTABLE_FILE_NAME" not in _COMPILE_SCRIPT,
                "start_process": "Start-Process" in _COMPILE_SCRIPT,
                "invoke_expression": "Invoke-Expression" in _COMPILE_SCRIPT,
            },
            {
                "windows_sandbox": False,
                "candidate_python": False,
                "start_process": False,
                "invoke_expression": False,
            },
        )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
