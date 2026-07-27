from __future__ import annotations

import math

from dataclasses import dataclass
from typing import Any, Callable

from modules.runtime_service_health import RuntimeServiceHealth


_STT_PHASES = {
    "not_started",
    "starting",
    "active",
    "stopped",
    "failed",
}


@dataclass(frozen=True)
class STTHealthPolicy:
    startup_grace_sec: float = 5.0
    resume_grace_sec: float = 2.0
    audio_heartbeat_timeout_sec: float = 3.0
    processing_heartbeat_timeout_sec: float = 3.0
    max_queue_backlog_sec: float = 3.0


DEFAULT_STT_HEALTH_POLICY = STTHealthPolicy()


def _finite_float(
    value: Any,
    field: str,
    *,
    allow_none: bool = True,
) -> float | None:
    if value is None:
        if allow_none:
            return None

        raise RuntimeError(f"{field} is unavailable")

    if isinstance(value, bool):
        raise RuntimeError(f"{field} is invalid")

    try:
        result = float(value)
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"{field} is invalid") from e

    if not math.isfinite(result):
        raise RuntimeError(f"{field} is invalid")

    return result


def _positive_float(value: Any, field: str) -> float:
    result = _finite_float(
        value,
        field,
        allow_none=False,
    )

    if result is None or result <= 0:
        raise RuntimeError(f"{field} is invalid")

    return result


def _required_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimeError(f"{field} is invalid")

    return value


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise RuntimeError(f"{field} is invalid")

    try:
        number = float(value)
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"{field} is invalid") from e

    if not math.isfinite(number) or not number.is_integer() or number < 0:
        raise RuntimeError(f"{field} is invalid")

    return int(number)


def _positive_int(value: Any, field: str) -> int:
    result = _non_negative_int(value, field)

    if result <= 0:
        raise RuntimeError(f"{field} is invalid")

    return result


def _age_seconds(
    now_value: float,
    timestamp: float | None,
) -> float | None:
    if timestamp is None:
        return None

    return max(0.0, now_value - timestamp)


def _current_generation_timestamp(
    timestamp: float | None,
    stream_started_at: float,
) -> float | None:
    if timestamp is None or timestamp < stream_started_at:
        return None

    return timestamp


def add_stt_health(
    health: RuntimeServiceHealth,
    stt: Any,
    *,
    stt_model_path: str,
    now_func: Callable[[], float],
    policy: STTHealthPolicy = DEFAULT_STT_HEALTH_POLICY,
) -> None:
    if stt is None:
        health.disabled(
            "stt",
            error="STT service unavailable",
        )
        return

    device_value = getattr(stt, "device", None)
    active_model_path = str(
        getattr(stt, "active_model_path", "")
        or stt_model_path
        or ""
    )
    base_details = {
        "engine": type(stt).__name__,
        "model_path": active_model_path,
        "samplerate": getattr(stt, "samplerate", 0),
        "blocksize": getattr(stt, "blocksize", 0),
        "device": "" if device_value is None else str(device_value),
    }

    try:
        lifecycle_func = getattr(
            stt,
            "get_lifecycle_telemetry",
            None,
        )

        if not callable(lifecycle_func):
            raise RuntimeError(
                "STT service does not expose lifecycle telemetry"
            )

        snapshot = lifecycle_func()

        if snapshot is None:
            raise RuntimeError(
                "STT lifecycle telemetry is unavailable"
            )

        now_value = _finite_float(
            now_func(),
            "Current health timestamp",
            allow_none=False,
        )

        if now_value is None:
            raise RuntimeError(
                "Current health timestamp is unavailable"
            )

        samplerate = _positive_int(
            getattr(stt, "samplerate", 0),
            "STT samplerate",
        )
        blocksize = _positive_int(
            getattr(stt, "blocksize", 0),
            "STT blocksize",
        )
        startup_grace_sec = _positive_float(
            policy.startup_grace_sec,
            "STT startup grace",
        )
        resume_grace_sec = _positive_float(
            policy.resume_grace_sec,
            "STT resume grace",
        )
        audio_timeout_sec = _positive_float(
            policy.audio_heartbeat_timeout_sec,
            "STT audio heartbeat timeout",
        )
        processing_timeout_sec = _positive_float(
            policy.processing_heartbeat_timeout_sec,
            "STT processing heartbeat timeout",
        )
        max_queue_backlog_sec = _positive_float(
            policy.max_queue_backlog_sec,
            "STT queue backlog limit",
        )

        stream_started = _required_bool(
            getattr(snapshot, "stream_started", None),
            "STT stream_started",
        )
        stream_active = _required_bool(
            getattr(snapshot, "stream_active", None),
            "STT stream_active",
        )
        paused = _required_bool(
            getattr(snapshot, "paused", None),
            "STT paused",
        )
        stream_generation = _non_negative_int(
            getattr(snapshot, "stream_generation", None),
            "STT stream generation",
        )
        stream_phase = str(
            getattr(snapshot, "stream_phase", "")
            or ""
        ).strip()

        if stream_phase not in _STT_PHASES:
            raise RuntimeError(
                "STT stream phase is invalid"
            )

        stream_started_at = _finite_float(
            getattr(snapshot, "last_stream_started_at", None),
            "STT stream start timestamp",
        )
        stream_stopped_at = _finite_float(
            getattr(snapshot, "last_stream_stopped_at", None),
            "STT stream stop timestamp",
        )
        last_audio_block_at = _finite_float(
            getattr(snapshot, "last_audio_block_at", None),
            "STT audio heartbeat timestamp",
        )
        last_processed_audio_block_at = _finite_float(
            getattr(
                snapshot,
                "last_processed_audio_block_at",
                None,
            ),
            "STT processing heartbeat timestamp",
        )
        last_resumed_at = _finite_float(
            getattr(snapshot, "last_resumed_at", None),
            "STT resume timestamp",
        )
        resume_pending = _required_bool(
            getattr(snapshot, "resume_pending", None),
            "STT resume_pending",
        )
        last_callback_status_at = _finite_float(
            getattr(
                snapshot,
                "last_callback_status_at",
                None,
            ),
            "STT callback status timestamp",
        )
        last_error_at = _finite_float(
            getattr(snapshot, "last_error_at", None),
            "STT error timestamp",
        )

        audio_block_count = _non_negative_int(
            getattr(snapshot, "audio_block_count", None),
            "STT audio block counter",
        )
        audio_bytes_total = _non_negative_int(
            getattr(snapshot, "audio_bytes_total", None),
            "STT audio byte counter",
        )
        processed_audio_block_count = _non_negative_int(
            getattr(
                snapshot,
                "processed_audio_block_count",
                None,
            ),
            "STT processed block counter",
        )
        queue_size = _non_negative_int(
            getattr(snapshot, "queue_size", None),
            "STT queue size",
        )
        phrase_count = _non_negative_int(
            getattr(snapshot, "phrase_count", None),
            "STT phrase counter",
        )
        callback_status_count = _non_negative_int(
            getattr(
                snapshot,
                "callback_status_count",
                None,
            ),
            "STT callback status counter",
        )
        failure_count = _non_negative_int(
            getattr(snapshot, "failure_count", None),
            "STT failure counter",
        )
        consecutive_failures = _non_negative_int(
            getattr(
                snapshot,
                "consecutive_failures",
                None,
            ),
            "STT consecutive failure counter",
        )
        last_callback_status = str(
            getattr(snapshot, "last_callback_status", "")
            or ""
        ).strip()
        last_error = str(
            getattr(snapshot, "last_error", "")
            or ""
        ).strip()

        if stream_started != (stream_generation > 0):
            raise RuntimeError(
                "STT lifecycle telemetry is inconsistent"
            )

        if stream_started and stream_started_at is None:
            raise RuntimeError(
                "STT lifecycle telemetry is inconsistent"
            )

        if not stream_started and (
            stream_phase != "not_started"
            or stream_active
            or stream_started_at is not None
        ):
            raise RuntimeError(
                "STT lifecycle telemetry is inconsistent"
            )

        if stream_active != (stream_phase == "active"):
            raise RuntimeError(
                "STT lifecycle telemetry is inconsistent"
            )

        if resume_pending and (
            stream_phase != "active"
            or last_resumed_at is None
        ):
            raise RuntimeError(
                "STT resume telemetry is inconsistent"
            )

        if last_resumed_at is not None and (
            not stream_started
            or (
                stream_started_at is not None
                and last_resumed_at < stream_started_at
            )
        ):
            raise RuntimeError(
                "STT resume telemetry is inconsistent"
            )

        if (
            stream_phase
            in {
                "starting",
                "active",
                "stopped",
                "failed",
            }
            and not stream_started
        ):
            raise RuntimeError(
                "STT lifecycle telemetry is inconsistent"
            )

        if (
            stream_phase in {"stopped", "failed"}
            and stream_stopped_at is None
        ):
            raise RuntimeError(
                "STT lifecycle telemetry is inconsistent"
            )

        if processed_audio_block_count > audio_block_count:
            raise RuntimeError(
                "STT processed block counter is inconsistent"
            )

        if phrase_count > processed_audio_block_count:
            raise RuntimeError(
                "STT phrase counter is inconsistent"
            )

        if (
            audio_block_count == 0
            and last_audio_block_at is not None
        ):
            raise RuntimeError(
                "STT audio telemetry is inconsistent"
            )

        if (
            processed_audio_block_count == 0
            and last_processed_audio_block_at is not None
        ):
            raise RuntimeError(
                "STT processing telemetry is inconsistent"
            )

        if callback_status_count == 0 and (
            last_callback_status_at is not None
            or last_callback_status
        ):
            raise RuntimeError(
                "STT callback status telemetry is inconsistent"
            )

        if callback_status_count > 0 and (
            last_callback_status_at is None
            or not last_callback_status
        ):
            raise RuntimeError(
                "STT callback status telemetry is inconsistent"
            )

        if consecutive_failures > failure_count:
            raise RuntimeError(
                "STT failure telemetry is inconsistent"
            )

        if failure_count == 0 and (
            last_error_at is not None
            or last_error
        ):
            raise RuntimeError(
                "STT failure telemetry is inconsistent"
            )

        if failure_count > 0 and (
            last_error_at is None
            or not last_error
        ):
            raise RuntimeError(
                "STT failure telemetry is inconsistent"
            )

        if (
            stream_phase == "failed"
            and consecutive_failures <= 0
        ):
            raise RuntimeError(
                "STT failure telemetry is inconsistent"
            )

        if (
            stream_phase == "active"
            and consecutive_failures != 0
        ):
            raise RuntimeError(
                "STT active telemetry contains current failures"
            )

        queue_backlog_seconds = (
            queue_size
            * blocksize
            / samplerate
        )
        details: dict[str, Any] = {
            **base_details,
            "stream_started": stream_started,
            "stream_active": stream_active,
            "stream_generation": stream_generation,
            "stream_phase": stream_phase,
            "paused": paused,
            "resume_pending": resume_pending,
            "audio_block_count": audio_block_count,
            "audio_bytes_total": audio_bytes_total,
            "processed_audio_block_count": (
                processed_audio_block_count
            ),
            "queue_size": queue_size,
            "queue_backlog_seconds": round(
                queue_backlog_seconds,
                3,
            ),
            "phrase_count": phrase_count,
            "callback_status_count": (
                callback_status_count
            ),
            "failure_count": failure_count,
            "consecutive_failures": (
                consecutive_failures
            ),
            "startup_grace_seconds": round(
                startup_grace_sec,
                1,
            ),
            "resume_grace_seconds": round(
                resume_grace_sec,
                1,
            ),
            "audio_timeout_seconds": round(
                audio_timeout_sec,
                1,
            ),
            "processing_timeout_seconds": round(
                processing_timeout_sec,
                1,
            ),
            "max_queue_backlog_seconds": round(
                max_queue_backlog_sec,
                1,
            ),
        }

        if stream_started_at is not None:
            stream_age_seconds = _age_seconds(
                now_value,
                stream_started_at,
            )
            details["stream_age_seconds"] = round(
                stream_age_seconds or 0.0,
                1,
            )
        else:
            stream_age_seconds = None

        if last_resumed_at is not None:
            resume_age_seconds = _age_seconds(
                now_value,
                last_resumed_at,
            )
            details["last_resumed_age_seconds"] = round(
                resume_age_seconds or 0.0,
                3,
            )
        else:
            resume_age_seconds = None

        if last_callback_status_at is not None:
            details["last_callback_status"] = (
                last_callback_status
            )
            details[
                "last_callback_status_age_seconds"
            ] = round(
                _age_seconds(
                    now_value,
                    last_callback_status_at,
                )
                or 0.0,
                1,
            )

        if stream_phase == "not_started":
            details["reason"] = "not_started"
            health.unknown(
                "stt",
                details=details,
            )
            return

        if stream_phase == "failed":
            details[
                "last_error_age_seconds"
            ] = round(
                _age_seconds(
                    now_value,
                    last_error_at,
                )
                or 0.0,
                1,
            )
            health.degraded(
                "stt",
                details=details,
                error=last_error or "STT stream failed",
            )
            return

        if stream_phase == "stopped":
            health.degraded(
                "stt",
                details=details,
                error="STT stream is stopped",
            )
            return

        if (
            stream_started_at is None
            or stream_age_seconds is None
        ):
            raise RuntimeError(
                "STT lifecycle telemetry is inconsistent"
            )

        if stream_phase == "starting":
            if stream_age_seconds <= startup_grace_sec:
                details["reason"] = "starting"
                health.unknown(
                    "stt",
                    details=details,
                )
            else:
                health.degraded(
                    "stt",
                    details=details,
                    error=(
                        "STT stream startup timed out"
                    ),
                )

            return

        current_audio_block_at = (
            _current_generation_timestamp(
                last_audio_block_at,
                stream_started_at,
            )
        )
        current_processed_audio_block_at = (
            _current_generation_timestamp(
                last_processed_audio_block_at,
                stream_started_at,
            )
        )
        audio_age_seconds = _age_seconds(
            now_value,
            current_audio_block_at,
        )
        processed_age_seconds = _age_seconds(
            now_value,
            current_processed_audio_block_at,
        )

        if audio_age_seconds is not None:
            details[
                "last_audio_block_age_seconds"
            ] = round(
                audio_age_seconds,
                3,
            )

        if processed_age_seconds is not None:
            details[
                "last_processed_audio_block_age_seconds"
            ] = round(
                processed_age_seconds,
                3,
            )

        if current_audio_block_at is None:
            if stream_age_seconds <= startup_grace_sec:
                details["reason"] = "waiting_for_audio"
                health.unknown(
                    "stt",
                    details=details,
                )
            else:
                health.degraded(
                    "stt",
                    details=details,
                    error=(
                        "STT audio heartbeat is unavailable"
                    ),
                )

            return

        if (
            audio_age_seconds is None
            or audio_age_seconds > audio_timeout_sec
        ):
            health.degraded(
                "stt",
                details=details,
                error="STT audio heartbeat is stale",
            )
            return

        if paused:
            if current_processed_audio_block_at is None:
                details["reason"] = "paused_before_processing"
                health.unknown(
                    "stt",
                    details=details,
                )
            else:
                health.ready(
                    "stt",
                    details=details,
                )

            return

        if queue_backlog_seconds > max_queue_backlog_sec:
            health.degraded(
                "stt",
                details=details,
                error="STT audio queue backlog is too large",
            )
            return

        if resume_pending:
            if resume_age_seconds is None:
                raise RuntimeError(
                    "STT resume telemetry is inconsistent"
                )

            if resume_age_seconds <= resume_grace_sec:
                if current_processed_audio_block_at is None:
                    details["reason"] = "waiting_for_processing_after_resume"
                    health.unknown(
                        "stt",
                        details=details,
                    )
                else:
                    details["resume_grace_active"] = True
                    health.ready(
                        "stt",
                        details=details,
                    )

                return

            health.degraded(
                "stt",
                details=details,
                error="STT recognizer did not resume processing",
            )
            return

        if current_processed_audio_block_at is None:
            if stream_age_seconds <= startup_grace_sec:
                details["reason"] = "waiting_for_processing"
                health.unknown(
                    "stt",
                    details=details,
                )
            else:
                health.degraded(
                    "stt",
                    details=details,
                    error="STT recognizer has not processed audio",
                )

            return

        if (
            processed_age_seconds is None
            or processed_age_seconds > processing_timeout_sec
        ):
            health.degraded(
                "stt",
                details=details,
                error="STT recognizer heartbeat is stale",
            )
            return

        health.ready(
            "stt",
            details=details,
        )
    except Exception as e:
        health.degraded(
            "stt",
            details=base_details,
            error=str(e),
        )