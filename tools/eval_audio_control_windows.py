from __future__ import annotations

import json
import os
import subprocess
import sys

from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if os.name != "nt":
        print("[SKIP] AudioControl Windows smoke requires Windows.")
        return 0

    child_code = """
import gc
import json

from modules.audio_control import AudioControl

devices = []

for _ in range(25):
    audio = AudioControl()
    probe = audio.probe()
    devices.append(
        {
            "id": probe.device_id,
            "name": probe.device_name,
            "volume": probe.volume,
            "muted": probe.muted,
        }
    )
    del audio
    gc.collect()

print(json.dumps(
    {
        "iterations": len(devices),
        "last": devices[-1],
    },
    ensure_ascii=False,
))
"""

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-X",
                "faulthandler",
                "-c",
                child_code,
            ],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as e:
        completed = None
        timed_out = True
        stdout = str(e.stdout or "")
        stderr = str(e.stderr or "")
    else:
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()

    if completed is None:
        returncode = None
        returncode_hex = ""
    else:
        returncode = completed.returncode
        returncode_hex = f"0x{completed.returncode & 0xFFFFFFFF:08X}"

    actual: dict[str, Any] = {
        "timed_out": timed_out,
        "returncode": returncode,
        "returncode_hex": returncode_hex,
        "stdout": stdout,
        "stderr": stderr,
    }
    ok = not timed_out and returncode == 0

    print("=== AUDIO CONTROL WINDOWS SMOKE ===")
    print(json.dumps(
        {
            "actual": actual,
            "expected": {
                "timed_out": False,
                "returncode": 0,
            },
            "ok": ok,
        },
        ensure_ascii=False,
        indent=2,
    ))

    if ok:
        print("[OK] AudioControl Windows smoke")
        return 0

    print("[FAIL] AudioControl Windows smoke")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())