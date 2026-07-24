from __future__ import annotations

import json

from types import SimpleNamespace
from typing import Any

from modules.operation_telemetry import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    OperationTelemetrySnapshot,
)
from modules.runtime_service_health import (
    STATUS_DEGRADED,
    STATUS_READY,
    STATUS_UNKNOWN,
)
from modules.runtime_service_health_runtime import collect_runtime_service_health
from tools.stt_health_test_support import healthy_stt_service


class FakeAudioOutput:
    def current(self) -> Any:
        return SimpleNamespace(
            id="device-1",
            name="Наушники",
        )


class FakeStatusService:
    def __init__(self, snapshot: Any):
        self._snapshot = snapshot

    def status(self) -> Any:
        return self._snapshot


class FakeWeatherService:
    def __init__(
        self,
        snapshot: OperationTelemetrySnapshot | None,
        *,
        ttl_seconds: float = 30.0,
        error: Exception | None = None,
    ):
        self._snapshot = snapshot
        self._error = error
        self.health_ttl_sec = float(ttl_seconds)

    def get_operation_telemetry(self) -> OperationTelemetrySnapshot:
        if self._error is not None:
            raise self._error

        if self._snapshot is None:
            raise RuntimeError("missing fake weather telemetry")

        return self._snapshot


class FakeTTSService:
    def __init__(
        self,
        *,
        attempt_at: float,
        ttl_seconds: float = 30.0,
    ):
        self._attempt_at = float(attempt_at)
        self.health_ttl_sec = float(ttl_seconds)
        self.voice = "ru-RU-SvetlanaNeural"
        self.rate = "+0%"
        self.volume = "+20%"
        self.pitch = "+0Hz"

    def get_lifecycle_telemetry(self) -> Any:
        return SimpleNamespace(
            operation=OperationTelemetrySnapshot(
                last_outcome=OUTCOME_SUCCESS,
                last_attempt_at=self._attempt_at,
                last_success_at=self._attempt_at,
                last_failure_at=None,
                last_duration_ms=120,
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


def _snapshot(
    *,
    outcome: str = "",
    attempt_at: float | None = None,
    success_at: float | None = None,
    failure_at: float | None = None,
    duration_ms: int | None = None,
    error: str = "",
    consecutive_failures: int = 0,
) -> OperationTelemetrySnapshot:
    return OperationTelemetrySnapshot(
        last_outcome=outcome,
        last_attempt_at=attempt_at,
        last_success_at=success_at,
        last_failure_at=failure_at,
        last_duration_ms=duration_ms,
        last_error=error,
        consecutive_failures=consecutive_failures,
    )


def _collect_weather(
    weather_service: Any,
    *,
    now_value: float = 1000.0,
):
    def now_func() -> float:
        return now_value

    report = collect_runtime_service_health(
        stt=healthy_stt_service(now_value),
        stt_model_path="models/model_small",
        tts=FakeTTSService(
            attempt_at=now_value - 5.0,
        ),
        audio=object(),
        audio_output=FakeAudioOutput(),
        weather_service=weather_service,
        timer_service=FakeStatusService(
            SimpleNamespace(active=False, remaining_seconds=0, token=1)
        ),
        reminder_service=FakeStatusService(
            SimpleNamespace(count=0, scheduled_reminder_id="")
        ),
        now_func=now_func,
    )

    weather = next(
        item
        for item in report.services
        if item.name == "weather"
    )

    return report, weather


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

    report, weather = _collect_weather(
        FakeWeatherService(
            _snapshot()
        )
    )

    check(
        "WEATHER NOT CHECKED IS UNKNOWN",
        {
            "report_status": report.status,
            "status": weather.status,
            "reason": weather.details.get("reason"),
            "stale": weather.details.get("stale"),
            "error": weather.error,
        },
        {
            "report_status": STATUS_UNKNOWN,
            "status": STATUS_UNKNOWN,
            "reason": "not_checked",
            "stale": None,
            "error": "",
        },
    )

    report, weather = _collect_weather(
        FakeWeatherService(
            _snapshot(
                outcome=OUTCOME_SUCCESS,
                attempt_at=995.0,
                success_at=995.0,
                duration_ms=120,
            )
        )
    )

    check(
        "RECENT WEATHER SUCCESS IS READY",
        {
            "report_status": report.status,
            "status": weather.status,
            "last_outcome": weather.details.get("last_outcome"),
            "age_seconds": weather.details.get("age_seconds"),
            "duration_ms": weather.details.get("last_duration_ms"),
            "failures": weather.details.get("consecutive_failures"),
        },
        {
            "report_status": STATUS_READY,
            "status": STATUS_READY,
            "last_outcome": OUTCOME_SUCCESS,
            "age_seconds": 5.0,
            "duration_ms": 120,
            "failures": 0,
        },
    )

    report, weather = _collect_weather(
        FakeWeatherService(
            _snapshot(
                outcome=OUTCOME_FAILURE,
                attempt_at=995.0,
                failure_at=995.0,
                duration_ms=250,
                error="weather timeout",
                consecutive_failures=2,
            )
        )
    )

    check(
        "RECENT WEATHER FAILURE IS DEGRADED",
        {
            "report_status": report.status,
            "status": weather.status,
            "last_outcome": weather.details.get("last_outcome"),
            "age_seconds": weather.details.get("age_seconds"),
            "failures": weather.details.get("consecutive_failures"),
            "error": weather.error,
        },
        {
            "report_status": STATUS_DEGRADED,
            "status": STATUS_DEGRADED,
            "last_outcome": OUTCOME_FAILURE,
            "age_seconds": 5.0,
            "failures": 2,
            "error": "weather timeout",
        },
    )

    report, weather = _collect_weather(
        FakeWeatherService(
            _snapshot(
                outcome=OUTCOME_SUCCESS,
                attempt_at=960.0,
                success_at=960.0,
                duration_ms=100,
            )
        )
    )

    check(
        "STALE WEATHER SUCCESS IS UNKNOWN",
        {
            "report_status": report.status,
            "status": weather.status,
            "last_outcome": weather.details.get("last_outcome"),
            "age_seconds": weather.details.get("age_seconds"),
            "stale": weather.details.get("stale"),
        },
        {
            "report_status": STATUS_UNKNOWN,
            "status": STATUS_UNKNOWN,
            "last_outcome": OUTCOME_SUCCESS,
            "age_seconds": 40.0,
            "stale": True,
        },
    )

    report, weather = _collect_weather(
        FakeWeatherService(
            _snapshot(
                outcome=OUTCOME_FAILURE,
                attempt_at=960.0,
                failure_at=960.0,
                duration_ms=250,
                error="old weather timeout",
                consecutive_failures=1,
            )
        )
    )

    check(
        "STALE WEATHER FAILURE IS UNKNOWN",
        {
            "report_status": report.status,
            "status": weather.status,
            "last_outcome": weather.details.get("last_outcome"),
            "stale": weather.details.get("stale"),
            "last_error": weather.details.get("last_error"),
            "error": weather.error,
        },
        {
            "report_status": STATUS_UNKNOWN,
            "status": STATUS_UNKNOWN,
            "last_outcome": OUTCOME_FAILURE,
            "stale": True,
            "last_error": "old weather timeout",
            "error": "",
        },
    )

    report, weather = _collect_weather(
        FakeWeatherService(
            None,
            error=RuntimeError("telemetry failed"),
        )
    )

    check(
        "WEATHER TELEMETRY FAILURE IS DEGRADED",
        {
            "report_status": report.status,
            "status": weather.status,
            "error": weather.error,
        },
        {
            "report_status": STATUS_DEGRADED,
            "status": STATUS_DEGRADED,
            "error": "telemetry failed",
        },
    )

    report, weather = _collect_weather(
        FakeWeatherService(
            _snapshot(),
            ttl_seconds=0.0,
        )
    )

    check(
        "INVALID WEATHER TTL IS DEGRADED",
        {
            "report_status": report.status,
            "status": weather.status,
            "error": weather.error,
        },
        {
            "report_status": STATUS_DEGRADED,
            "status": STATUS_DEGRADED,
            "error": "Weather health TTL is invalid",
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