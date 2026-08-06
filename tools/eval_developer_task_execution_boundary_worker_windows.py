from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile

from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_boundary_worker import (
    build_developer_task_execution_boundary_worker_bundle,
)


_COMPILE_SCRIPT = r'''param(
    [Parameter(Mandatory = $true)][string]$NativeHelperPath,
    [Parameter(Mandatory = $true)][string]$WorkerSourcePath,
    [Parameter(Mandatory = $true)][string]$WorkerOutputPath
)

$ErrorActionPreference = "Stop"

Add-Type `
    -Path $NativeHelperPath `
    -ErrorAction Stop

if ([V1B3CNative]::WORKER_INTEGRITY_RID -ne 8192) {
    throw "Compiled V1B3C native helper exposes an unexpected worker integrity RID."
}

Add-Type `
    -Path $WorkerSourcePath `
    -OutputAssembly $WorkerOutputPath `
    -OutputType ConsoleApplication `
    -ErrorAction Stop

if (-not (Test-Path -LiteralPath $WorkerOutputPath -PathType Leaf)) {
    throw "V1B3C worker compile did not produce an executable."
}

[pscustomobject]@{
    native_helper_compiled = $true
    worker_probe_compiled = $true
    worker_executable_exists = $true
    worker_executed = $false
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
        print("[SKIP] V1B3C exact C# compile smoke requires win32.")
        return 0

    bundle = build_developer_task_execution_boundary_worker_bundle()
    with tempfile.TemporaryDirectory(prefix="skynetvs-v1b3c-compile-") as temp_dir:
        root = Path(temp_dir)
        native_path = root / bundle.native_helper.file_name
        worker_path = root / bundle.worker_probe.file_name
        worker_output_path = root / bundle.worker_executable_file_name
        script_path = root / "compile_v1b3c.ps1"

        native_path.write_bytes(bundle.native_helper.exact_bytes())
        worker_path.write_bytes(bundle.worker_probe.exact_bytes())
        script_path.write_text(_COMPILE_SCRIPT, encoding="utf-8")

        check(
            "EXACT V1B3C PAYLOAD BYTES ARE STAGED FOR COMPILATION",
            {
                "native": _sha256(native_path.read_bytes()),
                "worker": _sha256(worker_path.read_bytes()),
            },
            {
                "native": bundle.native_helper.sha256,
                "worker": bundle.worker_probe.sha256,
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
                "-WorkerSourcePath",
                str(worker_path),
                "-WorkerOutputPath",
                str(worker_output_path),
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60.0,
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
            "EXACT V1B3C NATIVE HELPER AND WORKER COMPILE WITHOUT EXECUTION",
            {
                "returncode": completed.returncode,
                "native_helper_compiled": bool(last_json and last_json.get("native_helper_compiled")),
                "worker_probe_compiled": bool(last_json and last_json.get("worker_probe_compiled")),
                "worker_executable_exists": worker_output_path.is_file(),
                "worker_executed": bool(last_json and last_json.get("worker_executed")),
                "stderr": completed.stderr.strip(),
            },
            {
                "returncode": 0,
                "native_helper_compiled": True,
                "worker_probe_compiled": True,
                "worker_executable_exists": True,
                "worker_executed": False,
                "stderr": "",
            },
        )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, ensure_ascii=False, indent=2))
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
