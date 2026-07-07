from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


NormalizeFunc = Callable[[str], tuple[str, bool]]
PredictFunc = Callable[[str], Mapping[str, Any]]
TextPredicate = Callable[[str], bool]
TextTransform = Callable[[str], str]


@dataclass(frozen=True)
class SpeechInterruptResult:
    handled: bool
    stopped: bool
    reason: str
    stop_text: str = ""
    intent: str = ""


def handle_phrase_while_tts_speaking(
    phrase: str,
    *,
    tts: Any,
    logger: Any,
    has_hotword_func: TextPredicate,
    strip_hotword_func: TextTransform,
    normalize_func: NormalizeFunc,
    predict_func: PredictFunc,
) -> SpeechInterruptResult:
    """
    Обрабатывает STT-фразу, пока ассистент говорит.

    Поведение:
      - если TTS не говорит -> handled=False;
      - если пользователь сказал STOP_TALKING -> остановить TTS;
      - иначе проигнорировать фразу, чтобы ассистент не реагировал на шум/эхо.
    """
    if not tts.is_speaking():
        return SpeechInterruptResult(
            handled=False,
            stopped=False,
            reason="tts_not_speaking",
        )

    stop_text = phrase

    if has_hotword_func(stop_text):
        stop_text = strip_hotword_func(stop_text) or stop_text

    stop_text, _ = normalize_func(stop_text)

    meta = predict_func(stop_text)
    intent = str(meta.get("intent") or "").upper()

    if intent == "STOP_TALKING":
        logger.event("tts_stop_requested", {"text": phrase})
        tts.stop()

        return SpeechInterruptResult(
            handled=True,
            stopped=True,
            reason="stop_talking",
            stop_text=stop_text,
            intent=intent,
        )

    logger.event("stt_ignored_while_tts_speaking", {"text": phrase})

    return SpeechInterruptResult(
        handled=True,
        stopped=False,
        reason="ignored_while_tts_speaking",
        stop_text=stop_text,
        intent=intent,
    )