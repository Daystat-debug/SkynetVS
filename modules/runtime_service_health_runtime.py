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


_TTS_ACTIVE_MODES = {
    "blocking",
    "interruptible",
}

_TTS_ACTIVE_PHASES = {
    "synthesizing",
    "playing",
    "stopping",
    "stop_failed",
    "watch_failed",
    "poll_failed",
    "unmonitored",
}

_TTS_UNHEALTHY_PHASES = {
    "stop_failed",
    "watch_failed",
    "poll_failed",
    "unmonitored",
}


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


def _add_tts_health(
    health: RuntimeServiceHealth,
    tts: Any,
    *,
    now_func: Callable[[], float],
) -> None:
    if tts is None:
        health.disabled("tts", error="TTS service unavailable")
        return

    base_details = {
        "engine": _engine(tts),
        "voice": str(getattr(tts, "voice", "") or ""),
        "rate": str(getattr(tts, "rate", "") or ""),
        "volume": str(getattr(tts, "volume", "") or ""),
        "pitch": str(getattr(tts, "pitch", "") or ""),
    }

    try:
        lifecycle_func = getattr(tts, "get_lifecycle_telemetry", None)

        if not callable(lifecycle_func):
            raise RuntimeError("TTS service does not expose lifecycle telemetry")

        lifecycle = lifecycle_func()

        if lifecycle is None:
            raise RuntimeError("TTS lifecycle telemetry is unavailable")

        operation = getattr(lifecycle, "operation", None)

        if operation is None:
            raise RuntimeError("TTS operation telemetry is unavailable")

        ttl_seconds = _finite_float(getattr(tts, "health_ttl_sec", None))

        if ttl_seconds is None or ttl_seconds <= 0:
            raise RuntimeError("TTS health TTL is invalid")

        now_value = _finite_float(now_func())

        if now_value is None:
            raise RuntimeError("Current health timestamp is invalid")

        active = bool(getattr(lifecycle, "active", False))
        active_operation_id_raw = getattr(lifecycle, "active_operation_id", None)
        active_mode = str(getattr(lifecycle, "active_mode", "") or "").strip()
        active_phase = str(getattr(lifecycle, "active_phase", "") or "").strip()

        details: dict[str, Any] = {
            **base_details,
            "active": active,
            "ttl_seconds": round(ttl_seconds, 1),
        }

        if active:
            if isinstance(active_operation_id_raw, bool):
                raise RuntimeError("TTS active operation id is invalid")

            try:
                active_operation_id = int(active_operation_id_raw)
            except (TypeError, ValueError) as e:
                raise RuntimeError("TTS active operation id is invalid") from e

            if active_operation_id <= 0:
                raise RuntimeError("TTS active operation id is invalid")

            if active_mode not in _TTS_ACTIVE_MODES:
                raise RuntimeError("TTS active mode is invalid")

            if active_phase not in _TTS_ACTIVE_PHASES:
                raise RuntimeError("TTS active phase is invalid")

            details.update(
                {
                    "active_operation_id": active_operation_id,
                    "active_mode": active_mode,
                    "active_phase": active_phase,
                }
            )
        elif active_operation_id_raw is not None or active_mode or active_phase:
            raise RuntimeError("TTS lifecycle telemetry is inconsistent")

        cancellation_count_raw = getattr(lifecycle, "cancellation_count", 0)

        if isinstance(cancellation_count_raw, bool):
            raise RuntimeError("TTS cancellation counter is invalid")

        try:
            cancellation_count = int(cancellation_count_raw)
        except (TypeError, ValueError) as e:
            raise RuntimeError("TTS cancellation counter is invalid") from e

        if cancellation_count < 0:
            raise RuntimeError("TTS cancellation counter is invalid")

        last_cancelled_at = _finite_float(getattr(lifecycle, "last_cancelled_at", None))
        last_cancel_reason = str(getattr(lifecycle, "last_cancel_reason", "") or "").strip()
        last_cancelled_duration_raw = getattr(lifecycle, "last_cancelled_duration_ms", None)

        if cancellation_count:
            if last_cancelled_at is None or not last_cancel_reason:
                raise RuntimeError("TTS cancellation telemetry is inconsistent")

            if isinstance(last_cancelled_duration_raw, bool):
                raise RuntimeError("TTS cancellation duration is invalid")

            last_cancelled_duration_ms = _finite_float(last_cancelled_duration_raw)

            if last_cancelled_duration_ms is None or last_cancelled_duration_ms < 0:
                raise RuntimeError("TTS cancellation duration is invalid")

            details.update(
                {
                    "cancellation_count": cancellation_count,
                    "last_cancel_reason": last_cancel_reason,
                    "last_cancel_age_seconds": round(max(0.0, now_value - last_cancelled_at), 1),
                    "last_cancelled_duration_ms": int(round(last_cancelled_duration_ms)),
                }
            )
        elif (
            last_cancelled_at is not None
            or last_cancel_reason
            or last_cancelled_duration_raw is not None
        ):
            raise RuntimeError("TTS cancellation telemetry is inconsistent")

        last_attempt_at = _finite_float(getattr(operation, "last_attempt_at", None))
        reported_has_attempt = getattr(operation, "has_attempt", None)

        if reported_has_attempt is not None:
            has_attempt = bool(reported_has_attempt)

            if has_attempt != (last_attempt_at is not None):
                raise RuntimeError("TTS operation telemetry is inconsistent")
        else:
            has_attempt = last_attempt_at is not None

        outcome = str(getattr(operation, "last_outcome", "") or "").strip().lower()
        last_error = str(getattr(operation, "last_error", "") or "").strip()
        consecutive_failures_raw = getattr(operation, "consecutive_failures", 0)

        if isinstance(consecutive_failures_raw, bool):
            raise RuntimeError("TTS failure counter is invalid")

        try:
            consecutive_failures = int(consecutive_failures_raw)
        except (TypeError, ValueError) as e:
            raise RuntimeError("TTS failure counter is invalid") from e

        if consecutive_failures < 0:
            raise RuntimeError("TTS failure counter is invalid")

        duration_raw = getattr(operation, "last_duration_ms", None)
        duration_ms: int | None = None

        if duration_raw is not None:
            if isinstance(duration_raw, bool):
                raise RuntimeError("TTS operation duration is invalid")

            duration_value = _finite_float(duration_raw)

            if duration_value is None or duration_value < 0:
                raise RuntimeError("TTS operation duration is invalid")

            duration_ms = int(round(duration_value))

        if not has_attempt:
            if outcome or last_error or consecutive_failures or duration_ms is not None:
                raise RuntimeError("TTS operation telemetry is inconsistent")

            if active and active_phase in _TTS_UNHEALTHY_PHASES:
                health.degraded(
                    "tts",
                    details=details,
                    error=f"TTS lifecycle is unhealthy: {active_phase}",
                )
                return

            details["reason"] = "operation_in_progress" if active else "not_checked"
            health.unknown("tts", details=details)
            return

        if outcome == OUTCOME_SUCCESS and consecutive_failures != 0:
            raise RuntimeError("TTS success telemetry contains active failures")

        if outcome == OUTCOME_SUCCESS and last_error:
            raise RuntimeError("TTS success telemetry contains an active error")

        if outcome == OUTCOME_FAILURE and consecutive_failures <= 0:
            raise RuntimeError("TTS failure telemetry has no failure count")

        if not outcome and (last_error or consecutive_failures):
            raise RuntimeError("TTS operation telemetry is inconsistent")

        age_seconds = max(0.0, now_value - last_attempt_at)

        details.update(
            {
                "last_outcome": outcome or "unknown",
                "age_seconds": round(age_seconds, 1),
                "consecutive_failures": consecutive_failures,
            }
        )

        if duration_ms is not None:
            details["last_duration_ms"] = duration_ms

        if active and active_phase in _TTS_UNHEALTHY_PHASES:
            if last_error:
                details["last_error"] = last_error

            health.degraded(
                "tts",
                details=details,
                error=last_error or f"TTS lifecycle is unhealthy: {active_phase}",
            )
            return

        if age_seconds > ttl_seconds:
            details["stale"] = True

            if last_error:
                details["last_error"] = last_error

            health.unknown("tts", details=details)
            return

        if outcome == OUTCOME_SUCCESS:
            health.ready("tts", details=details)
            return

        if outcome == OUTCOME_FAILURE:
            health.degraded(
                "tts",
                details=details,
                error=last_error or "TTS operation failed",
            )
            return

        details["reason"] = "unknown_outcome"

        if last_error:
            details["last_error"] = last_error

        health.unknown("tts", details=details)
    except Exception as e:
        health.degraded(
            "tts",
            details=base_details,
            error=str(e),
        )


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

    _add_tts_health(
        health,
        tts,
        now_func=now_func,
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