from __future__ import annotations

import math
import time

from typing import Any, Callable

from modules.operation_telemetry import OUTCOME_FAILURE, OUTCOME_SUCCESS
from modules.runtime_service_health import (
    RuntimeServiceHealth,
    RuntimeServiceHealthReport,
    format_runtime_service_health_lines,
    runtime_service_health_payload,
)


EventFunc = Callable[[str, dict[str, Any]], None]
PrintFunc = Callable[[str], None]


def _engine(value: Any) -> str:
    return type(value).__name__ if value is not None else ""


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _error_text(value: str, fallback: str) -> str:
    return str(value or "").strip() or fallback


def _finite_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def _add_weather_health(
    health: RuntimeServiceHealth,
    weather_service: Any,
    *,
    now_func: Callable[[], float],
) -> None:
    if weather_service is None:
        health.disabled("weather", error="Weather service unavailable")
        return

    base_details = {
        "engine": _engine(weather_service),
    }

    try:
        telemetry_func = getattr(weather_service, "get_operation_telemetry", None)

        if not callable(telemetry_func):
            raise RuntimeError("Weather service does not expose operation telemetry")

        snapshot = telemetry_func()

        if snapshot is None:
            raise RuntimeError("Weather operation telemetry is unavailable")

        ttl_seconds = _finite_float(getattr(weather_service, "health_ttl_sec", None))

        if ttl_seconds is None or ttl_seconds <= 0:
            raise RuntimeError("Weather health TTL is invalid")

        last_attempt_at = _finite_float(getattr(snapshot, "last_attempt_at", None))
        reported_has_attempt = getattr(snapshot, "has_attempt", None)

        if reported_has_attempt is not None:
            has_attempt = bool(reported_has_attempt)

            if has_attempt != (last_attempt_at is not None):
                raise RuntimeError("Weather operation telemetry is inconsistent")
        else:
            has_attempt = last_attempt_at is not None

        if not has_attempt:
            health.unknown(
                "weather",
                details={
                    **base_details,
                    "reason": "not_checked",
                    "ttl_seconds": round(ttl_seconds, 1),
                },
            )
            return

        now_value = _finite_float(now_func())

        if now_value is None:
            raise RuntimeError("Current health timestamp is invalid")

        age_seconds = max(0.0, now_value - last_attempt_at)
        outcome = str(getattr(snapshot, "last_outcome", "") or "").strip().lower()
        last_error = str(getattr(snapshot, "last_error", "") or "").strip()

        try:
            consecutive_failures = int(getattr(snapshot, "consecutive_failures", 0))
        except (TypeError, ValueError) as e:
            raise RuntimeError("Weather failure counter is invalid") from e

        if consecutive_failures < 0:
            raise RuntimeError("Weather failure counter is invalid")

        if outcome == OUTCOME_SUCCESS and consecutive_failures != 0:
            raise RuntimeError("Weather success telemetry contains active failures")

        if outcome == OUTCOME_SUCCESS and last_error:
            raise RuntimeError("Weather success telemetry contains an active error")

        if outcome == OUTCOME_FAILURE and consecutive_failures <= 0:
            raise RuntimeError("Weather failure telemetry has no failure count")

        details: dict[str, Any] = {
            **base_details,
            "last_outcome": outcome or "unknown",
            "age_seconds": round(age_seconds, 1),
            "ttl_seconds": round(ttl_seconds, 1),
            "consecutive_failures": consecutive_failures,
        }

        duration_value = getattr(snapshot, "last_duration_ms", None)

        if duration_value is not None:
            duration_ms = _finite_float(duration_value)

            if duration_ms is None or duration_ms < 0:
                raise RuntimeError("Weather operation duration is invalid")

            details["last_duration_ms"] = int(round(duration_ms))

        if age_seconds > ttl_seconds:
            details["stale"] = True

            if last_error:
                details["last_error"] = last_error

            health.unknown("weather", details=details)
            return

        if outcome == OUTCOME_SUCCESS:
            health.ready("weather", details=details)
            return

        if outcome == OUTCOME_FAILURE:
            health.degraded(
                "weather",
                details=details,
                error=last_error or "Weather operation failed",
            )
            return

        details["reason"] = "unknown_outcome"

        if last_error:
            details["last_error"] = last_error

        health.unknown("weather", details=details)
    except Exception as e:
        health.degraded(
            "weather",
            details=base_details,
            error=str(e),
        )


def collect_runtime_service_health(
    *,
    stt: Any,
    stt_model_path: str,
    tts: Any,
    audio: Any,
    audio_output: Any,
    weather_service: Any,
    timer_service: Any,
    reminder_service: Any,
    audio_error: str = "",
    audio_output_error: str = "",
    reminder_error: str = "",
    reminder_path: str = "",
    now_func: Callable[[], float] = time.time,
) -> RuntimeServiceHealthReport:
    health = RuntimeServiceHealth()

    if stt is None:
        health.disabled("stt", error="STT service unavailable")
    else:
        health.ready(
            "stt",
            details={
                "engine": _engine(stt),
                "model_path": str(stt_model_path or ""),
                "samplerate": _int_value(getattr(stt, "samplerate", 0)),
                "device": str(getattr(stt, "device", "") or ""),
            },
        )

    if tts is None:
        health.disabled("tts", error="TTS service unavailable")
    else:
        health.ready(
            "tts",
            details={
                "engine": _engine(tts),
                "voice": str(getattr(tts, "voice", "") or ""),
                "rate": str(getattr(tts, "rate", "") or ""),
                "volume": str(getattr(tts, "volume", "") or ""),
                "pitch": str(getattr(tts, "pitch", "") or ""),
            },
        )

    if audio is None:
        health.disabled(
            "audio_control",
            error=_error_text(audio_error, "Audio control unavailable"),
        )
    else:
        health.ready("audio_control", details={"engine": _engine(audio)})

    if audio_output is None:
        health.disabled(
            "audio_output",
            error=_error_text(audio_output_error, "Audio output unavailable"),
        )
    else:
        try:
            current = audio_output.current()

            if current is None:
                health.degraded(
                    "audio_output",
                    details={"engine": _engine(audio_output)},
                    error="Current audio output device unavailable",
                )
            else:
                health.ready(
                    "audio_output",
                    details={
                        "engine": _engine(audio_output),
                        "current_name": str(getattr(current, "name", "") or ""),
                        "current_id": str(getattr(current, "id", "") or ""),
                    },
                )
        except Exception as e:
            health.degraded(
                "audio_output",
                details={"engine": _engine(audio_output)},
                error=str(e),
            )

    _add_weather_health(
        health,
        weather_service,
        now_func=now_func,
    )

    if timer_service is None:
        health.disabled("timer", error="Timer service unavailable")
    else:
        try:
            snapshot = timer_service.status()
            health.ready(
                "timer",
                details={
                    "engine": _engine(timer_service),
                    "active": bool(getattr(snapshot, "active", False)),
                    "remaining_seconds": _int_value(getattr(snapshot, "remaining_seconds", 0)),
                    "token": _int_value(getattr(snapshot, "token", 0)),
                },
            )
        except Exception as e:
            health.degraded(
                "timer",
                details={"engine": _engine(timer_service)},
                error=str(e),
            )

    if reminder_service is None:
        health.disabled(
            "reminders",
            details={"path": str(reminder_path or "")},
            error=_error_text(reminder_error, "Reminder service unavailable"),
        )
    else:
        try:
            snapshot = reminder_service.status()
            health.ready(
                "reminders",
                details={
                    "engine": _engine(reminder_service),
                    "path": str(reminder_path or ""),
                    "active_count": _int_value(getattr(snapshot, "count", 0)),
                    "scheduled_reminder_id": str(
                        getattr(snapshot, "scheduled_reminder_id", "") or ""
                    ),
                },
            )
        except Exception as e:
            health.degraded(
                "reminders",
                details={
                    "engine": _engine(reminder_service),
                    "path": str(reminder_path or ""),
                },
                error=str(e),
            )

    return health.build()


def publish_runtime_service_health(
    report: RuntimeServiceHealthReport,
    *,
    event_func: EventFunc | None = None,
    print_func: PrintFunc | None = print,
) -> dict[str, Any]:
    payload = runtime_service_health_payload(report)

    if print_func is not None:
        for line in format_runtime_service_health_lines(report):
            print_func(line)

    if event_func is not None:
        try:
            event_func("runtime_service_health", payload)
        except Exception as e:
            if print_func is not None:
                print_func(f"[HEALTH] log failed: {e}")

    return payload