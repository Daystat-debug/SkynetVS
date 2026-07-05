# modules/media_control.py

from __future__ import annotations

import sys


class MediaControl:
    """
    Управление медиаклавишами Windows:
    - Play/Pause
    - Next
    - Previous
    - Stop
    Работает даже когда игра в фуллскрине (не требует фокуса окна).
    """

    # Virtual-Key codes
    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_MEDIA_STOP = 0xB2
    VK_MEDIA_PLAY_PAUSE = 0xB3

    def __init__(self) -> None:
        if not sys.platform.startswith("win"):
            raise RuntimeError("MediaControl is supported only on Windows")

    @staticmethod
    def _tap_vk(vk: int) -> None:
        # Используем keybd_event: для медиаклавиш достаточно и очень стабильно.
        import ctypes

        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def play_pause(self) -> None:
        self._tap_vk(self.VK_MEDIA_PLAY_PAUSE)

    def next_track(self) -> None:
        self._tap_vk(self.VK_MEDIA_NEXT_TRACK)

    def prev_track(self) -> None:
        self._tap_vk(self.VK_MEDIA_PREV_TRACK)

    def stop(self) -> None:
        self._tap_vk(self.VK_MEDIA_STOP)

