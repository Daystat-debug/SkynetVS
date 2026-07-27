from __future__ import annotations

import ast
import json

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from modules.audio_control import (
    AudioControlProbe,
    AudioControlUnavailableError,
)
from modules.runtime_service_health import (
    RuntimeServiceHealth,
    STATUS_DEGRADED,
    STATUS_DISABLED,
    STATUS_READY,
)
from modules.runtime_service_health_audio_control import add_audio_control_health
from tools.audio_control_health_test_support import (
    FakeAudioControl,
    healthy_audio_control_service,
)


def _audio_health(
    audio: Any,
    *,
    audio_error: str = "",
):
    health = RuntimeServiceHealth()
    add_audio_control_health(
        health,
        audio,
        audio_error=audio_error,
    )
    return health.build().services[0]


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count

        case_count += 1
        ok = actual == expected

        print()
        print(f"=== {name} ===")
        print(json.dumps(
            {
                "actual": actual,
                "expected": expected,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ))

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    item = _audio_health(
        None,
        audio_error="audio initialization failed",
    )

    check(
        "MISSING AUDIO CONTROL IS DISABLED",
        {
            "status": item.status,
            "error": item.error,
        },
        {
            "status": STATUS_DISABLED,
            "error": "audio initialization failed",
        },
    )

    audio = healthy_audio_control_service(
        device_id="device-headphones",
        device_name="Наушники",
        volume=42,
        muted=True,
    )
    item = _audio_health(audio)

    check(
        "HEALTHY AUDIO CONTROL PROBE IS READY",
        {
            "status": item.status,
            "device_id": item.details.get("device_id"),
            "device_name": item.details.get("device_name"),
            "volume": item.details.get("volume"),
            "muted": item.details.get("muted"),
            "calls": audio.calls,
            "error": item.error,
        },
        {
            "status": STATUS_READY,
            "device_id": "device-headphones",
            "device_name": "Наушники",
            "volume": 42,
            "muted": True,
            "calls": 1,
            "error": "",
        },
    )

    audio = FakeAudioControl(
        AudioControlProbe(
            device_id="",
            device_name="",
            volume=0,
            muted=False,
        ),
        error=AudioControlUnavailableError(
            "probe",
            "Current default audio endpoint is unavailable",
            retry_attempted=True,
        ),
    )
    item = _audio_health(audio)

    check(
        "UNAVAILABLE AUDIO ENDPOINT IS DEGRADED",
        {
            "status": item.status,
            "operation": item.details.get("operation"),
            "retry_attempted": item.details.get("retry_attempted"),
            "error_type": item.details.get("error_type"),
            "error": item.error,
        },
        {
            "status": STATUS_DEGRADED,
            "operation": "probe",
            "retry_attempted": True,
            "error_type": "AudioControlUnavailableError",
            "error": "Audio control probe failed after endpoint refresh: Current default audio endpoint is unavailable",
        },
    )

    item = _audio_health(
        FakeAudioControl(
            None,
            error=RuntimeError("fake probe failure"),
        )
    )

    check(
        "UNEXPECTED PROBE FAILURE IS DEGRADED",
        {
            "status": item.status,
            "error_type": item.details.get("error_type"),
            "error": item.error,
        },
        {
            "status": STATUS_DEGRADED,
            "error_type": "RuntimeError",
            "error": "fake probe failure",
        },
    )

    item = _audio_health(object())

    check(
        "MISSING PROBE CONTRACT IS DEGRADED",
        {
            "status": item.status,
            "error": item.error,
        },
        {
            "status": STATUS_DEGRADED,
            "error": "Audio control service does not expose probe",
        },
    )

    item = _audio_health(FakeAudioControl(None))

    check(
        "EMPTY PROBE RESULT IS DEGRADED",
        {
            "status": item.status,
            "error": item.error,
        },
        {
            "status": STATUS_DEGRADED,
            "error": "Audio control probe is unavailable",
        },
    )

    invalid_volume_errors = []

    for volume in (True, -1, 101, 50.5, float("nan")):
        item = _audio_health(
            FakeAudioControl(
                SimpleNamespace(
                    device_id="device-1",
                    device_name="Наушники",
                    volume=volume,
                    muted=False,
                )
            )
        )
        invalid_volume_errors.append(
            {
                "status": item.status,
                "error": item.error,
            }
        )

    check(
        "INVALID PROBE VOLUMES ARE DEGRADED",
        invalid_volume_errors,
        [
            {
                "status": STATUS_DEGRADED,
                "error": "Audio control probe volume is invalid",
            }
            for _ in range(5)
        ],
    )

    invalid_mute_errors = []

    for muted in (0, 1, "false", None):
        item = _audio_health(
            FakeAudioControl(
                SimpleNamespace(
                    device_id="device-1",
                    device_name="Наушники",
                    volume=50,
                    muted=muted,
                )
            )
        )
        invalid_mute_errors.append(
            {
                "status": item.status,
                "error": item.error,
            }
        )

    check(
        "INVALID PROBE MUTE VALUES ARE DEGRADED",
        invalid_mute_errors,
        [
            {
                "status": STATUS_DEGRADED,
                "error": "Audio control probe muted state is invalid",
            }
            for _ in range(4)
        ],
    )

    item = _audio_health(
        FakeAudioControl(
            SimpleNamespace(
                device_id=None,
                device_name=None,
                volume=50,
                muted=False,
            )
        )
    )

    check(
        "MISSING OPTIONAL DEVICE METADATA DOES NOT BREAK PROBE",
        {
            "status": item.status,
            "device_id": item.details.get("device_id"),
            "device_name": item.details.get("device_name"),
            "volume": item.details.get("volume"),
        },
        {
            "status": STATUS_READY,
            "device_id": "",
            "device_name": "",
            "volume": 50,
        },
    )

    main_tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
    runtime_tree = ast.parse(
        Path("modules/runtime_service_health_runtime.py").read_text(encoding="utf-8")
    )
    recoverable_audio_init = False
    health_adapter_called = False

    for node in ast.walk(main_tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name) and node.func.id == "AudioControl":
            for keyword in node.keywords:
                if (
                    keyword.arg == "validate_on_init"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is False
                ):
                    recoverable_audio_init = True

    for node in ast.walk(runtime_tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "add_audio_control_health":
                health_adapter_called = True

    check(
        "MAIN AND COLLECTOR WIRING",
        {
            "recoverable_audio_init": recoverable_audio_init,
            "health_adapter_called": health_adapter_called,
        },
        {
            "recoverable_audio_init": True,
            "health_adapter_called": True,
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps(
        {
            "case_count": case_count,
            "fail_count": fail_count,
        },
        ensure_ascii=False,
        indent=2,
    ))

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())