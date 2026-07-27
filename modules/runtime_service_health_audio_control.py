from __future__ import annotations

import math

from typing import Any

from modules.audio_control import AudioControlError
from modules.runtime_service_health import RuntimeServiceHealth


def _error_text(value: BaseException | str, fallback: str) -> str:
    text = str(value or "").strip()
    return text or fallback


def _probe_volume(value: Any) -> int:
    if isinstance(value, bool):
        raise RuntimeError("Audio control probe volume is invalid")

    try:
        number = float(value)
    except (TypeError, ValueError) as e:
        raise RuntimeError("Audio control probe volume is invalid") from e

    if not math.isfinite(number) or not number.is_integer() or number < 0 or number > 100:
        raise RuntimeError("Audio control probe volume is invalid")

    return int(number)


def add_audio_control_health(
    health: RuntimeServiceHealth,
    audio: Any,
    *,
    audio_error: str = "",
) -> None:
    if audio is None:
        health.disabled(
            "audio_control",
            error=_error_text(audio_error, "Audio control unavailable"),
        )
        return

    base_details = {
        "engine": type(audio).__name__,
    }

    try:
        probe_func = getattr(audio, "probe", None)

        if not callable(probe_func):
            raise RuntimeError("Audio control service does not expose probe")

        probe = probe_func()

        if probe is None:
            raise RuntimeError("Audio control probe is unavailable")

        volume = _probe_volume(getattr(probe, "volume", None))
        muted = getattr(probe, "muted", None)

        if not isinstance(muted, bool):
            raise RuntimeError("Audio control probe muted state is invalid")

        health.ready(
            "audio_control",
            details={
                **base_details,
                "device_id": str(getattr(probe, "device_id", "") or ""),
                "device_name": str(getattr(probe, "device_name", "") or ""),
                "volume": volume,
                "muted": muted,
            },
        )
    except AudioControlError as e:
        health.degraded(
            "audio_control",
            details={
                **base_details,
                "operation": e.operation,
                "retry_attempted": e.retry_attempted,
                "error_type": type(e).__name__,
            },
            error=_error_text(e, "Audio control probe failed"),
        )
    except Exception as e:
        health.degraded(
            "audio_control",
            details={
                **base_details,
                "error_type": type(e).__name__,
            },
            error=_error_text(e, "Audio control probe failed"),
        )