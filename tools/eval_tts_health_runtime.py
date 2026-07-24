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
from modules.tts_edge import TTSLifecycleSnapshot
from tools.stt_health_test_support import healthy_stt_service


class FakeAudioOutput:
    def current(self) -> Any:
        return SimpleNamespace(id="device-1", name="Наушники")


class FakeStatusService:
    def __init__(self, snapshot: Any):
        self._snapshot = snapshot

    def status(self) -> Any:
        return self._snapshot


class FakeWeatherService:
    health_ttl_sec = 30.0

    def get_operation_telemetry(self) -> OperationTelemetrySnapshot:
        return OperationTelemetrySnapshot(
            last_outcome=OUTCOME_SUCCESS,
            last_attempt_at=995.0,
            last_success_at=995.0,
            last_failure_at=None,
            last_duration_ms=100,
            last_error="",
            consecutive_failures=0,
        )


class FakeTTSService:
    def __init__(
        self,
        lifecycle: TTSLifecycleSnapshot | None,
        *,
        ttl_seconds: float = 30.0,
        error: Exception | None = None,
    ):
        self._lifecycle = lifecycle
        self._error = error
        self.health_ttl_sec = float(ttl_seconds)
        self.voice = "ru-RU-SvetlanaNeural"
        self.rate = "+0%"
        self.volume = "+20%"
        self.pitch = "+0Hz"

    def get_lifecycle_telemetry(self) -> TTSLifecycleSnapshot:
        if self._error is not None:
            raise self._error

        if self._lifecycle is None:
            raise RuntimeError("missing fake TTS lifecycle")

        return self._lifecycle


def _operation(
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


def _lifecycle(
    operation: OperationTelemetrySnapshot,
    *,
    active: bool = False,
    operation_id: int | None = None,
    mode: str = "",
    phase: str = "",
    last_cancelled_at: float | None = None,
    last_cancelled_duration_ms: int | None = None,
    last_cancel_reason: str = "",
    cancellation_count: int = 0,
) -> TTSLifecycleSnapshot:
    return TTSLifecycleSnapshot(
        operation=operation,
        active_operation_id=operation_id,
        active=active,
        active_mode=mode,
        active_phase=phase,
        last_cancelled_at=last_cancelled_at,
        last_cancelled_duration_ms=last_cancelled_duration_ms,
        last_cancel_reason=last_cancel_reason,
        cancellation_count=cancellation_count,
    )


def _collect_tts(
    tts: Any,
    *,
    now_value: float = 1000.0,
):
    def now_func() -> float:
        return now_value

    report = collect_runtime_service_health(
        stt=healthy_stt_service(now_value),
        stt_model_path="models/model_small",
        tts=tts,
        audio=object(),
        audio_output=FakeAudioOutput(),
        weather_service=FakeWeatherService(),
        timer_service=FakeStatusService(
            SimpleNamespace(active=False, remaining_seconds=0, token=1)
        ),
        reminder_service=FakeStatusService(
            SimpleNamespace(count=0, scheduled_reminder_id="")
        ),
        now_func=now_func,
    )

    tts_health = next(
        item
        for item in report.services
        if item.name == "tts"
    )

    return report, tts_health


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

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(_operation())
        )
    )

    check(
        "TTS NOT CHECKED IS UNKNOWN",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "reason": tts_health.details.get("reason"),
            "active": tts_health.details.get("active"),
            "error": tts_health.error,
        },
        {
            "report_status": STATUS_UNKNOWN,
            "status": STATUS_UNKNOWN,
            "reason": "not_checked",
            "active": False,
            "error": "",
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(
                _operation(
                    outcome=OUTCOME_SUCCESS,
                    attempt_at=995.0,
                    success_at=995.0,
                    duration_ms=120,
                )
            )
        )
    )

    check(
        "RECENT TTS SUCCESS IS READY",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "last_outcome": tts_health.details.get("last_outcome"),
            "age_seconds": tts_health.details.get("age_seconds"),
            "duration_ms": tts_health.details.get("last_duration_ms"),
            "failures": tts_health.details.get("consecutive_failures"),
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

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(
                _operation(
                    outcome=OUTCOME_FAILURE,
                    attempt_at=995.0,
                    failure_at=995.0,
                    duration_ms=250,
                    error="fake synthesis failure",
                    consecutive_failures=1,
                )
            )
        )
    )

    check(
        "RECENT TTS FAILURE IS DEGRADED",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "last_outcome": tts_health.details.get("last_outcome"),
            "failures": tts_health.details.get("consecutive_failures"),
            "error": tts_health.error,
        },
        {
            "report_status": STATUS_DEGRADED,
            "status": STATUS_DEGRADED,
            "last_outcome": OUTCOME_FAILURE,
            "failures": 1,
            "error": "fake synthesis failure",
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(
                _operation(
                    outcome=OUTCOME_SUCCESS,
                    attempt_at=960.0,
                    success_at=960.0,
                    duration_ms=100,
                )
            )
        )
    )

    check(
        "STALE TTS SUCCESS IS UNKNOWN",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "last_outcome": tts_health.details.get("last_outcome"),
            "age_seconds": tts_health.details.get("age_seconds"),
            "stale": tts_health.details.get("stale"),
        },
        {
            "report_status": STATUS_UNKNOWN,
            "status": STATUS_UNKNOWN,
            "last_outcome": OUTCOME_SUCCESS,
            "age_seconds": 40.0,
            "stale": True,
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(
                _operation(
                    outcome=OUTCOME_FAILURE,
                    attempt_at=960.0,
                    failure_at=960.0,
                    duration_ms=200,
                    error="old TTS failure",
                    consecutive_failures=1,
                )
            )
        )
    )

    check(
        "STALE TTS FAILURE IS UNKNOWN",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "stale": tts_health.details.get("stale"),
            "last_error": tts_health.details.get("last_error"),
            "error": tts_health.error,
        },
        {
            "report_status": STATUS_UNKNOWN,
            "status": STATUS_UNKNOWN,
            "stale": True,
            "last_error": "old TTS failure",
            "error": "",
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(
                _operation(),
                active=True,
                operation_id=7,
                mode="interruptible",
                phase="playing",
            )
        )
    )

    check(
        "FIRST ACTIVE TTS OPERATION IS UNKNOWN",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "reason": tts_health.details.get("reason"),
            "active": tts_health.details.get("active"),
            "operation_id": tts_health.details.get("active_operation_id"),
            "mode": tts_health.details.get("active_mode"),
            "phase": tts_health.details.get("active_phase"),
        },
        {
            "report_status": STATUS_UNKNOWN,
            "status": STATUS_UNKNOWN,
            "reason": "operation_in_progress",
            "active": True,
            "operation_id": 7,
            "mode": "interruptible",
            "phase": "playing",
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(
                _operation(),
                last_cancelled_at=996.0,
                last_cancelled_duration_ms=250,
                last_cancel_reason="requested",
                cancellation_count=1,
            )
        )
    )

    check(
        "CANCELLATION WITHOUT COMPLETED OPERATION STAYS UNKNOWN",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "reason": tts_health.details.get("reason"),
            "cancellation_count": tts_health.details.get("cancellation_count"),
            "cancel_reason": tts_health.details.get("last_cancel_reason"),
            "cancel_age": tts_health.details.get("last_cancel_age_seconds"),
            "error": tts_health.error,
        },
        {
            "report_status": STATUS_UNKNOWN,
            "status": STATUS_UNKNOWN,
            "reason": "not_checked",
            "cancellation_count": 1,
            "cancel_reason": "requested",
            "cancel_age": 4.0,
            "error": "",
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(
                _operation(
                    outcome=OUTCOME_SUCCESS,
                    attempt_at=990.0,
                    success_at=990.0,
                    duration_ms=300,
                ),
                last_cancelled_at=996.0,
                last_cancelled_duration_ms=150,
                last_cancel_reason="requested",
                cancellation_count=1,
            )
        )
    )

    check(
        "CANCELLATION PRESERVES RECENT SUCCESS",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "last_outcome": tts_health.details.get("last_outcome"),
            "cancellation_count": tts_health.details.get("cancellation_count"),
            "cancel_reason": tts_health.details.get("last_cancel_reason"),
            "error": tts_health.error,
        },
        {
            "report_status": STATUS_READY,
            "status": STATUS_READY,
            "last_outcome": OUTCOME_SUCCESS,
            "cancellation_count": 1,
            "cancel_reason": "requested",
            "error": "",
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(
                _operation(
                    outcome=OUTCOME_SUCCESS,
                    attempt_at=995.0,
                    success_at=995.0,
                    duration_ms=100,
                ),
                active=True,
                operation_id=8,
                mode="blocking",
                phase="synthesizing",
            )
        )
    )

    check(
        "ACTIVE TTS WITH RECENT SUCCESS REMAINS READY",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "active": tts_health.details.get("active"),
            "mode": tts_health.details.get("active_mode"),
            "phase": tts_health.details.get("active_phase"),
        },
        {
            "report_status": STATUS_READY,
            "status": STATUS_READY,
            "active": True,
            "mode": "blocking",
            "phase": "synthesizing",
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(
                _operation(
                    outcome=OUTCOME_FAILURE,
                    attempt_at=995.0,
                    failure_at=995.0,
                    duration_ms=200,
                    error="Не удалось остановить TTS-плеер.",
                    consecutive_failures=1,
                ),
                active=True,
                operation_id=9,
                mode="interruptible",
                phase="stop_failed",
            )
        )
    )

    check(
        "ACTIVE TTS FAILURE PHASE IS DEGRADED",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "active": tts_health.details.get("active"),
            "phase": tts_health.details.get("active_phase"),
            "error": tts_health.error,
        },
        {
            "report_status": STATUS_DEGRADED,
            "status": STATUS_DEGRADED,
            "active": True,
            "phase": "stop_failed",
            "error": "Не удалось остановить TTS-плеер.",
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            None,
            error=RuntimeError("lifecycle probe failed"),
        )
    )

    check(
        "TTS LIFECYCLE FAILURE IS DEGRADED",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "error": tts_health.error,
        },
        {
            "report_status": STATUS_DEGRADED,
            "status": STATUS_DEGRADED,
            "error": "lifecycle probe failed",
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(_operation()),
            ttl_seconds=0.0,
        )
    )

    check(
        "INVALID TTS TTL IS DEGRADED",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "error": tts_health.error,
        },
        {
            "report_status": STATUS_DEGRADED,
            "status": STATUS_DEGRADED,
            "error": "TTS health TTL is invalid",
        },
    )

    report, tts_health = _collect_tts(
        FakeTTSService(
            _lifecycle(
                _operation(),
                active=False,
                phase="playing",
            )
        )
    )

    check(
        "INCONSISTENT TTS LIFECYCLE IS DEGRADED",
        {
            "report_status": report.status,
            "status": tts_health.status,
            "error": tts_health.error,
        },
        {
            "report_status": STATUS_DEGRADED,
            "status": STATUS_DEGRADED,
            "error": "TTS lifecycle telemetry is inconsistent",
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