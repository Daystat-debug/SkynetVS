# modules/audio_control.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AudioState:
    volume: int   # 0..100
    muted: bool


class AudioControl:
    """
    Управление системной громкостью Windows через CoreAudio (pycaw).
    - volume: 0..100
    - mute/unmute: реальный mute (не установка громкости в 0)
    """

    def __init__(self):
        self._endpoint = None
        self._init_endpoint()

    def _init_endpoint(self) -> None:
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            dev = AudioUtilities.GetSpeakers()
            # В разных версиях pycaw GetSpeakers() может вернуть:
            # - IMMDevice (есть .Activate)
            # - AudioDevice-обёртку (Activate может быть на .device / ._device)
            imm = dev
            if not hasattr(imm, "Activate"):
                for attr in ("device", "_device", "_dev", "_endpoint"):
                    cand = getattr(dev, attr, None)
                    if cand is not None and hasattr(cand, "Activate"):
                        imm = cand
                        break

            if hasattr(imm, "Activate"):
                interface = imm.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._endpoint = cast(interface, POINTER(IAudioEndpointVolume))
            else:
                # Последний шанс: иногда interface уже IAudioEndpointVolume
                # или доступен через QueryInterface
                if hasattr(dev, "QueryInterface"):
                    self._endpoint = cast(dev.QueryInterface(IAudioEndpointVolume),POINTER(IAudioEndpointVolume))
                else:
                    raise AttributeError("No Activate/QueryInterface on audio device object")
        except Exception as e:
            raise RuntimeError(f"AudioControl init failed: {e}")

    def _clamp01(self, v: float) -> float:
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v

    def get_state(self) -> AudioState:
        ep = self._endpoint
        if ep is None:
            return AudioState(volume=0, muted=False)
        vol01 = float(ep.GetMasterVolumeLevelScalar())
        muted = bool(ep.GetMute())
        return AudioState(volume=int(round(vol01 * 100)), muted=muted)

    def set_volume(self, value_0_100: int) -> AudioState:
        ep = self._endpoint
        if ep is None:
            return self.get_state()
        v = int(value_0_100)
        if v < 0:
            v = 0
        if v > 100:
            v = 100
        ep.SetMasterVolumeLevelScalar(self._clamp01(v / 100.0), None)
        return self.get_state()

    def change_volume(self, delta_0_100: int) -> AudioState:
        st = self.get_state()
        return self.set_volume(st.volume + int(delta_0_100))

    def mute(self) -> AudioState:
        ep = self._endpoint
        if ep is not None:
            ep.SetMute(1, None)
        return self.get_state()

    def unmute(self) -> AudioState:
        ep = self._endpoint
        if ep is not None:
            ep.SetMute(0, None)
        return self.get_state()
