from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class PhraseGuardResult:
    ignored: bool
    reason: str | None


def check_phrase_preprocessing_guards(
    phrase: str,
    *,
    now: float,
    ack_ignore_until: float,
    last_tts_end: float,
    ignore_after_tts_sec: float,
    is_dictation_mode: bool,
    should_ignore_during_ack_window_func: Callable[[str], bool],
) -> PhraseGuardResult:
    """
    Проверяет ранние guard-условия перед основной обработкой STT-фразы.

    Guards:
      1. ACK-window: игнорируем эхо "слушаю" и bare hotword после ACK.
      2. ignore-after-TTS: игнорируем фразы сразу после TTS, кроме режима диктовки.
    """
    if now < ack_ignore_until and should_ignore_during_ack_window_func(phrase):
        return PhraseGuardResult(
            ignored=True,
            reason="stt_ignored_ack_window",
        )

    if not is_dictation_mode and (now - last_tts_end) < ignore_after_tts_sec:
        return PhraseGuardResult(
            ignored=True,
            reason="stt_ignored_after_tts",
        )

    return PhraseGuardResult(
        ignored=False,
        reason=None,
    )