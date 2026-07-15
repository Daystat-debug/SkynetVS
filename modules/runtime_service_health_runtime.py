from __future__ import annotations

from typing import Any, Callable

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

    if weather_service is None:
        health.disabled("weather", error="Weather service unavailable")
    else:
        health.ready("weather", details={"engine": _engine(weather_service)})

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