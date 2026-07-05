from __future__ import annotations

import time
from typing import Any


def say(
    stt: Any,
    tts: Any,
    text: str,
    *,
    mute_stt: bool = True,
) -> float:
    """
    Синхронная речь ассистента.

    Если mute_stt=True:
      - ставим STT на паузу;
      - говорим;
      - всегда возвращаем STT обратно, даже если TTS упал.
    """
    if mute_stt:
        stt.pause()
        try:
            tts.speak_blocking(text)
        finally:
            stt.resume()
    else:
        tts.speak_blocking(text)

    return time.time()


def say_interruptible(tts: Any, text: str) -> float:
    """
    Прерываемая речь ассистента.

    Используется для длинных ответов, которые можно остановить командой STOP_TALKING.
    """
    tts.speak_interruptible(text)
    return time.time()