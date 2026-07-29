from __future__ import annotations

import ast
import json

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from modules.runtime_service_health import STATUS_DEGRADED, STATUS_DISABLED, STATUS_READY
from modules.runtime_service_health_runtime import (
    collect_runtime_service_health,
    publish_runtime_service_health,
)
from modules.core.operation_telemetry import OUTCOME_SUCCESS, OperationTelemetrySnapshot
from modules.tts_edge import TTSLifecycleSnapshot
from tools.audio_control_health_test_support import healthy_audio_control_service
from tools.stt_health_test_support import healthy_stt_service


class FakeAudioOutput:
    def __init__(self, current_value: Any = None, error: Exception | None = None):
        self.current_value = current_value
        self.error = error

    def current(self) -> Any:
        if self.error is not None:
            raise self.error
        return self.current_value


class FakeStatusService:
    def __init__(self, snapshot: Any = None, error: Exception | None = None):
        self.snapshot = snapshot
        self.error = error

    def status(self) -> Any:
        if self.error is not None:
            raise self.error
        return self.snapshot


class FakeWeatherService:
    def __init__(
        self,
        snapshot: OperationTelemetrySnapshot,
        *,
        ttl_seconds: float = 1800.0,
    ):
        self._snapshot = snapshot
        self.health_ttl_sec = float(ttl_seconds)

    def get_operation_telemetry(self) -> OperationTelemetrySnapshot:
        return self._snapshot


class FakeTTSService:
    def __init__(
        self,
        lifecycle: TTSLifecycleSnapshot,
        *,
        ttl_seconds: float = 1800.0,
    ):
        self._lifecycle = lifecycle
        self.health_ttl_sec = float(ttl_seconds)
        self.voice = "ru-RU-SvetlanaNeural"
        self.rate = "+0%"
        self.volume = "+20%"
        self.pitch = "+0Hz"

    def get_lifecycle_telemetry(self) -> TTSLifecycleSnapshot:
        return self._lifecycle


def _service_map(report: Any) -> dict[str, Any]:
    return {item.name: item for item in report.services}


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

    stt = healthy_stt_service()
    audio = healthy_audio_control_service(
        device_id="device-1",
        device_name="Наушники",
        volume=35,
        muted=False,
    )
    tts = FakeTTSService(
        TTSLifecycleSnapshot(
            operation=OperationTelemetrySnapshot(
                last_outcome=OUTCOME_SUCCESS,
                last_attempt_at=990.0,
                last_success_at=990.0,
                last_failure_at=None,
                last_duration_ms=150,
                last_error="",
                consecutive_failures=0,
            ),
            active_operation_id=None,
            active=False,
            active_mode="",
            active_phase="",
            last_cancelled_at=None,
            last_cancelled_duration_ms=None,
            last_cancel_reason="",
            cancellation_count=0,
        )
    )
    current_device = SimpleNamespace(id="device-1", name="Наушники")
    timer_snapshot = SimpleNamespace(active=False, remaining_seconds=0, token=3)
    reminder_snapshot = SimpleNamespace(count=2, scheduled_reminder_id="r2")

    now_value = 1000.0

    def now_func() -> float:
        return now_value

    weather_service = FakeWeatherService(
        OperationTelemetrySnapshot(
            last_outcome=OUTCOME_SUCCESS,
            last_attempt_at=990.0,
            last_success_at=990.0,
            last_failure_at=None,
            last_duration_ms=120,
            last_error="",
            consecutive_failures=0,
        )
    )

    ready_report = collect_runtime_service_health(
        stt=stt,
        stt_model_path="models/model_small",
        tts=tts,
        audio=audio,
        audio_output=FakeAudioOutput(current_device),
        weather_service=weather_service,
        timer_service=FakeStatusService(timer_snapshot),
        reminder_service=FakeStatusService(reminder_snapshot),
        reminder_path="data/reminders.json",
        now_func=now_func,
    )
    ready_services = _service_map(ready_report)

    check(
        "ALL SERVICES READY",
        {
            "status": ready_report.status,
            "names": [item.name for item in ready_report.services],
            "statuses": {name: item.status for name, item in ready_services.items()},
            "current_name": ready_services["audio_output"].details["current_name"],
            "audio_volume": ready_services["audio_control"].details["volume"],
            "audio_muted": ready_services["audio_control"].details["muted"],
            "reminder_count": ready_services["reminders"].details["active_count"],
            "total": ready_report.total_count,
        },
        {
            "status": STATUS_READY,
            "names": [
                "stt",
                "tts",
                "audio_control",
                "audio_output",
                "weather",
                "timer",
                "reminders",
            ],
            "statuses": {
                "stt": STATUS_READY,
                "tts": STATUS_READY,
                "audio_control": STATUS_READY,
                "audio_output": STATUS_READY,
                "weather": STATUS_READY,
                "timer": STATUS_READY,
                "reminders": STATUS_READY,
            },
            "current_name": "Наушники",
            "audio_volume": 35,
            "audio_muted": False,
            "reminder_count": 2,
            "total": 7,
        },
    )

    disabled_report = collect_runtime_service_health(
        stt=stt,
        stt_model_path="models/model_small",
        tts=tts,
        audio=None,
        audio_output=None,
        weather_service=weather_service,
        timer_service=FakeStatusService(timer_snapshot),
        reminder_service=None,
        audio_error="audio failed",
        audio_output_error="output failed",
        reminder_error="repository failed",
        reminder_path="data/reminders.json",
        now_func=now_func,
    )
    disabled_services = _service_map(disabled_report)

    check(
        "FAILED INITIALIZATION IS DISABLED",
        {
            "status": disabled_report.status,
            "audio": {
                "status": disabled_services["audio_control"].status,
                "error": disabled_services["audio_control"].error,
            },
            "audio_output": {
                "status": disabled_services["audio_output"].status,
                "error": disabled_services["audio_output"].error,
            },
            "reminders": {
                "status": disabled_services["reminders"].status,
                "error": disabled_services["reminders"].error,
            },
        },
        {
            "status": STATUS_DEGRADED,
            "audio": {
                "status": STATUS_DISABLED,
                "error": "audio failed",
            },
            "audio_output": {
                "status": STATUS_DISABLED,
                "error": "output failed",
            },
            "reminders": {
                "status": STATUS_DISABLED,
                "error": "repository failed",
            },
        },
    )

    unavailable_report = collect_runtime_service_health(
        stt=stt,
        stt_model_path="models/model_small",
        tts=tts,
        audio=audio,
        audio_output=FakeAudioOutput(None),
        weather_service=weather_service,
        timer_service=FakeStatusService(timer_snapshot),
        reminder_service=FakeStatusService(reminder_snapshot),
        now_func=now_func,
    )
    unavailable_audio = _service_map(unavailable_report)["audio_output"]

    check(
        "CURRENT AUDIO OUTPUT UNAVAILABLE",
        {
            "status": unavailable_audio.status,
            "error": unavailable_audio.error,
        },
        {
            "status": STATUS_DEGRADED,
            "error": "Current audio output device unavailable",
        },
    )

    probe_report = collect_runtime_service_health(
        stt=stt,
        stt_model_path="models/model_small",
        tts=tts,
        audio=audio,
        audio_output=FakeAudioOutput(error=RuntimeError("output probe failed")),
        weather_service=weather_service,
        timer_service=FakeStatusService(error=RuntimeError("timer probe failed")),
        reminder_service=FakeStatusService(error=RuntimeError("reminder probe failed")),
        now_func=now_func,
    )
    probe_services = _service_map(probe_report)

    check(
        "PROBE FAILURES ARE DEGRADED",
        {
            name: {
                "status": probe_services[name].status,
                "error": probe_services[name].error,
            }
            for name in ("audio_output", "timer", "reminders")
        },
        {
            "audio_output": {
                "status": STATUS_DEGRADED,
                "error": "output probe failed",
            },
            "timer": {
                "status": STATUS_DEGRADED,
                "error": "timer probe failed",
            },
            "reminders": {
                "status": STATUS_DEGRADED,
                "error": "reminder probe failed",
            },
        },
    )

    lines: list[str] = []
    events: list[dict[str, Any]] = []

    payload = publish_runtime_service_health(
        ready_report,
        event_func=lambda name, body: events.append({"name": name, "payload": body}),
        print_func=lines.append,
    )

    check(
        "REPORT IS PRINTED AND LOGGED",
        {
            "first_line": lines[0],
            "last_line": lines[-1],
            "event_name": events[0]["name"],
            "event_status": events[0]["payload"]["status"],
            "payload_status": payload["status"],
            "ready_count": payload["summary"]["ready_count"],
        },
        {
            "first_line": "[HEALTH] Runtime services",
            "last_line": "[HEALTH] summary: status=ready ready=7 degraded=0 disabled=0 unknown=0 total=7",
            "event_name": "runtime_service_health",
            "event_status": STATUS_READY,
            "payload_status": STATUS_READY,
            "ready_count": 7,
        },
    )

    failure_lines: list[str] = []

    def broken_event(name: str, payload: dict[str, Any]) -> None:
        _ = name
        _ = payload
        raise RuntimeError("fake logger failure")

    raised = False

    try:
        publish_runtime_service_health(
            ready_report,
            event_func=broken_event,
            print_func=failure_lines.append,
        )
    except Exception:
        raised = True

    check(
        "LOGGER FAILURE DOES NOT BREAK BOOT",
        {
            "raised": raised,
            "last_line": failure_lines[-1],
        },
        {
            "raised": False,
            "last_line": "[HEALTH] log failed: fake logger failure",
        },
    )

    main_tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
    imported_names: set[str] = set()
    called_names: set[str] = set()
    assigned_names: set[str] = set()

    for node in ast.walk(main_tree):
        if isinstance(node, ast.ImportFrom) and node.module == "modules.runtime_service_health_runtime":
            imported_names.update(alias.name for alias in node.names)

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)

        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned_names.add(node.target.id)

    check(
        "MAIN WIRING",
        {
            "imports": {
                "collect": "collect_runtime_service_health" in imported_names,
                "publish": "publish_runtime_service_health" in imported_names,
            },
            "calls": {
                "collect": "collect_runtime_service_health" in called_names,
                "publish": "publish_runtime_service_health" in called_names,
            },
            "errors": {
                "audio_error": "audio_error" in assigned_names,
                "audio_output_error": "audio_output_error" in assigned_names,
                "reminder_error": "reminder_error" in assigned_names,
            },
        },
        {
            "imports": {
                "collect": True,
                "publish": True,
            },
            "calls": {
                "collect": True,
                "publish": True,
            },
            "errors": {
                "audio_error": True,
                "audio_output_error": True,
                "reminder_error": True,
            },
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