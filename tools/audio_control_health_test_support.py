from __future__ import annotations

from typing import Any

from modules.audio_control import AudioControlProbe


class FakeAudioControl:
    def __init__(
        self,
        probe_value: Any,
        *,
        error: Exception | None = None,
    ):
        self._probe_value = probe_value
        self._error = error
        self.calls = 0

    def probe(self) -> Any:
        self.calls += 1

        if self._error is not None:
            raise self._error

        return self._probe_value


def healthy_audio_control_service(
    *,
    device_id: str = "device-1",
    device_name: str = "Наушники",
    volume: int = 35,
    muted: bool = False,
) -> FakeAudioControl:
    return FakeAudioControl(
        AudioControlProbe(
            device_id=device_id,
            device_name=device_name,
            volume=volume,
            muted=muted,
        )
    )