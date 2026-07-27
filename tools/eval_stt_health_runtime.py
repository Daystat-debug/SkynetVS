from __future__ import annotations

import json

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from modules.operation_telemetry import (
    OUTCOME_SUCCESS,
    OperationTelemetrySnapshot,
)
from modules.runtime_service_health import (
    STATUS_DEGRADED,
    STATUS_READY,
    STATUS_UNKNOWN,
)
from modules.runtime_service_health_runtime import (
    collect_runtime_service_health,
)
from tools.stt_health_test_support import (
    FakeSTTService,
    build_stt_lifecycle_snapshot,
)


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


class FakeTTSService:
    health_ttl_sec = 30.0
    voice = "ru-RU-SvetlanaNeural"
    rate = "+0%"
    volume = "+20%"
    pitch = "+0Hz"

    def get_lifecycle_telemetry(self) -> Any:
        return SimpleNamespace(
            operation=OperationTelemetrySnapshot(
                last_outcome=OUTCOME_SUCCESS,
                last_attempt_at=995.0,
                last_success_at=995.0,
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


class FakeWeatherService:
    health_ttl_sec = 30.0

    def get_operation_telemetry(
        self,
    ) -> OperationTelemetrySnapshot:
        return OperationTelemetrySnapshot(
            last_outcome=OUTCOME_SUCCESS,
            last_attempt_at=995.0,
            last_success_at=995.0,
            last_failure_at=None,
            last_duration_ms=100,
            last_error="",
            consecutive_failures=0,
        )


def _collect_stt(
    stt: Any,
    *,
    now_value: float = 1000.0,
):
    def now_func() -> float:
        return now_value

    report = collect_runtime_service_health(
        stt=stt,
        stt_model_path="models/model_small",
        tts=FakeTTSService(),
        audio=object(),
        audio_output=FakeAudioOutput(),
        weather_service=FakeWeatherService(),
        timer_service=FakeStatusService(
            SimpleNamespace(
                active=False,
                remaining_seconds=0,
                token=1,
            )
        ),
        reminder_service=FakeStatusService(
            SimpleNamespace(
                count=0,
                scheduled_reminder_id="",
            )
        ),
        now_func=now_func,
    )

    stt_health = next(
        item
        for item in report.services
        if item.name == "stt"
    )

    return report, stt_health


def _active_snapshot(**overrides: Any):
    values: dict[str, Any] = {
        "stream_started": True,
        "stream_active": True,
        "stream_generation": 1,
        "stream_phase": "active",
        "paused": False,
        "last_stream_started_at": 900.0,
        "last_audio_block_at": 999.9,
        "audio_block_count": 100,
        "audio_bytes_total": 204800,
        "last_processed_audio_block_at": 999.95,
        "processed_audio_block_count": 90,
        "queue_size": 0,
        "last_phrase_at": 995.0,
        "phrase_count": 2,
    }
    values.update(overrides)

    return build_stt_lifecycle_snapshot(
        **values
    )


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(
        name: str,
        actual: Any,
        expected: Any,
    ) -> None:
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

    def check_health(
        name: str,
        stt: Any,
        *,
        status: str,
        report_status: str | None = None,
        error: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        report, item = _collect_stt(stt)
        detail_keys = details or {}

        check(
            name,
            {
                "report_status": report.status,
                "status": item.status,
                "error": item.error,
                "details": {
                    key: item.details.get(key)
                    for key in detail_keys
                },
            },
            {
                "report_status": (
                    report_status or status
                ),
                "status": status,
                "error": error,
                "details": detail_keys,
            },
        )

    check_health(
        "STT NOT STARTED IS UNKNOWN",
        FakeSTTService(
            build_stt_lifecycle_snapshot()
        ),
        status=STATUS_UNKNOWN,
        details={
            "reason": "not_started",
            "stream_phase": "not_started",
        },
    )

    check_health(
        "STT STARTING WITHIN GRACE IS UNKNOWN",
        FakeSTTService(
            build_stt_lifecycle_snapshot(
                stream_started=True,
                stream_generation=1,
                stream_phase="starting",
                last_stream_started_at=998.0,
            )
        ),
        status=STATUS_UNKNOWN,
        details={
            "reason": "starting",
            "stream_age_seconds": 2.0,
        },
    )

    check_health(
        "STT STARTUP TIMEOUT IS DEGRADED",
        FakeSTTService(
            build_stt_lifecycle_snapshot(
                stream_started=True,
                stream_generation=1,
                stream_phase="starting",
                last_stream_started_at=990.0,
            )
        ),
        status=STATUS_DEGRADED,
        error="STT stream startup timed out",
    )

    check_health(
        "ACTIVE STT WAITING FOR FIRST AUDIO IS UNKNOWN",
        FakeSTTService(
            _active_snapshot(
                last_stream_started_at=998.0,
                last_audio_block_at=None,
                audio_block_count=0,
                audio_bytes_total=0,
                last_processed_audio_block_at=None,
                processed_audio_block_count=0,
                last_phrase_at=None,
                phrase_count=0,
            )
        ),
        status=STATUS_UNKNOWN,
        details={
            "reason": "waiting_for_audio",
        },
    )

    check_health(
        "FRESH STT HEARTBEATS ARE READY",
        FakeSTTService(
            _active_snapshot()
        ),
        status=STATUS_READY,
        details={
            "last_audio_block_age_seconds": 0.1,
            "last_processed_audio_block_age_seconds": 0.05,
            "queue_backlog_seconds": 0.0,
            "model_path": "models/model_large",
        },
    )

    check_health(
        "PAUSED STT WITH LIVE AUDIO REMAINS READY",
        FakeSTTService(
            _active_snapshot(
                paused=True,
                last_processed_audio_block_at=910.0,
            )
        ),
        status=STATUS_READY,
        details={
            "paused": True,
            "last_processed_audio_block_age_seconds": 90.0,
        },
    )

    check_health(
        "PAUSED BEFORE PROCESSING IS UNKNOWN",
        FakeSTTService(
            _active_snapshot(
                paused=True,
                last_stream_started_at=998.0,
                last_processed_audio_block_at=None,
                processed_audio_block_count=0,
                last_phrase_at=None,
                phrase_count=0,
            )
        ),
        status=STATUS_UNKNOWN,
        details={
            "reason": "paused_before_processing",
        },
    )

    check_health(
        "RECENT RESUME GRACE PRESERVES READY",
        FakeSTTService(
            replace(
                _active_snapshot(
                    last_processed_audio_block_at=990.0,
                ),
                last_resumed_at=999.0,
                resume_pending=True,
            )
        ),
        status=STATUS_READY,
        details={
            "resume_pending": True,
            "last_resumed_age_seconds": 1.0,
            "resume_grace_active": True,
        },
    )

    check_health(
        "RESUME GRACE WITHOUT PRIOR PROCESSING IS UNKNOWN",
        FakeSTTService(
            replace(
                _active_snapshot(
                    last_processed_audio_block_at=None,
                    processed_audio_block_count=0,
                    last_phrase_at=None,
                    phrase_count=0,
                ),
                last_resumed_at=999.0,
                resume_pending=True,
            )
        ),
        status=STATUS_UNKNOWN,
        details={
            "reason": "waiting_for_processing_after_resume",
            "resume_pending": True,
        },
    )

    check_health(
        "RESUME PROCESSING TIMEOUT IS DEGRADED",
        FakeSTTService(
            replace(
                _active_snapshot(
                    last_processed_audio_block_at=990.0,
                ),
                last_resumed_at=995.0,
                resume_pending=True,
            )
        ),
        status=STATUS_DEGRADED,
        error="STT recognizer did not resume processing",
        details={
            "last_resumed_age_seconds": 5.0,
            "resume_pending": True,
        },
    )

    check_health(
        "PROCESSED BLOCK AFTER RESUME IS READY",
        FakeSTTService(
            replace(
                _active_snapshot(),
                last_resumed_at=999.0,
                resume_pending=False,
            )
        ),
        status=STATUS_READY,
        details={
            "resume_pending": False,
            "last_resumed_age_seconds": 1.0,
        },
    )

    check_health(
        "INCONSISTENT RESUME TELEMETRY IS DEGRADED",
        FakeSTTService(
            replace(
                _active_snapshot(),
                resume_pending=True,
            )
        ),
        status=STATUS_DEGRADED,
        error="STT resume telemetry is inconsistent",
    )

    check_health(
        "STALE AUDIO HEARTBEAT IS DEGRADED",
        FakeSTTService(
            _active_snapshot(
                last_audio_block_at=990.0,
            )
        ),
        status=STATUS_DEGRADED,
        error="STT audio heartbeat is stale",
        details={
            "last_audio_block_age_seconds": 10.0,
        },
    )

    check_health(
        "STALE RECOGNIZER HEARTBEAT IS DEGRADED",
        FakeSTTService(
            _active_snapshot(
                last_processed_audio_block_at=990.0,
            )
        ),
        status=STATUS_DEGRADED,
        error="STT recognizer heartbeat is stale",
        details={
            "last_processed_audio_block_age_seconds": 10.0,
        },
    )

    check_health(
        "LARGE STT QUEUE BACKLOG IS DEGRADED",
        FakeSTTService(
            _active_snapshot(
                queue_size=50,
            )
        ),
        status=STATUS_DEGRADED,
        error="STT audio queue backlog is too large",
        details={
            "queue_size": 50,
            "queue_backlog_seconds": 3.2,
        },
    )

    check_health(
        "CALLBACK WARNING DOES NOT DEGRADE STT",
        FakeSTTService(
            _active_snapshot(
                last_callback_status_at=999.5,
                last_callback_status=(
                    "input overflow"
                ),
                callback_status_count=1,
            )
        ),
        status=STATUS_READY,
        details={
            "callback_status_count": 1,
            "last_callback_status": (
                "input overflow"
            ),
        },
    )

    check_health(
        "FAILED STT STREAM IS DEGRADED",
        FakeSTTService(
            build_stt_lifecycle_snapshot(
                stream_started=True,
                stream_generation=1,
                stream_phase="failed",
                last_stream_started_at=990.0,
                last_stream_stopped_at=995.0,
                last_error_at=995.0,
                last_error="microphone open failed",
                failure_count=1,
                consecutive_failures=1,
            )
        ),
        status=STATUS_DEGRADED,
        error="microphone open failed",
        details={
            "stream_phase": "failed",
        },
    )

    check_health(
        "STOPPED STT STREAM IS DEGRADED",
        FakeSTTService(
            build_stt_lifecycle_snapshot(
                stream_started=True,
                stream_generation=1,
                stream_phase="stopped",
                last_stream_started_at=900.0,
                last_stream_stopped_at=999.0,
                last_audio_block_at=998.0,
                audio_block_count=10,
                audio_bytes_total=20480,
                last_processed_audio_block_at=998.0,
                processed_audio_block_count=10,
            )
        ),
        status=STATUS_DEGRADED,
        error="STT stream is stopped",
        details={
            "stream_phase": "stopped",
        },
    )

    check_health(
        "OLD GENERATION HEARTBEATS DO NOT PROVE NEW STREAM",
        FakeSTTService(
            _active_snapshot(
                last_stream_started_at=999.0,
                last_audio_block_at=998.0,
                last_processed_audio_block_at=998.0,
            )
        ),
        status=STATUS_UNKNOWN,
        details={
            "reason": "waiting_for_audio",
            "last_audio_block_age_seconds": None,
        },
    )

    check_health(
        "STT LIFECYCLE FAILURE IS DEGRADED",
        FakeSTTService(
            None,
            error=RuntimeError(
                "lifecycle probe failed"
            ),
        ),
        status=STATUS_DEGRADED,
        error="lifecycle probe failed",
    )

    check_health(
        "INCONSISTENT STT LIFECYCLE IS DEGRADED",
        FakeSTTService(
            _active_snapshot(
                stream_active=False,
            )
        ),
        status=STATUS_DEGRADED,
        error=(
            "STT lifecycle telemetry is inconsistent"
        ),
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