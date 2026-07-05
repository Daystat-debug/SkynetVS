from __future__ import annotations

from typing import Iterable


DICTATION_STOP_PHRASES = {
    "прекрати печать",
    "останови печать",
    "выйди из режима диктовки",
    "выключи режим диктовки",
    "выйди из режима ввода текста",
    "выключи режим ввода текста",
    "заверши диктовку",
}


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def strip_hotword_prefix(text: str, *, hotwords: Iterable[str] | None = None) -> str:
    """
    Убирает hotword в начале фразы, если он есть.

    Пример:
      "скайнет выключи режим диктовки" -> "выключи режим диктовки"
    """
    t = _norm(text)

    if not t or not hotwords:
        return t

    for hotword in hotwords:
        hw = _norm(hotword)
        if not hw:
            continue

        if t == hw:
            return ""

        if t.startswith(hw + " "):
            return t[len(hw):].strip(" ,.!?:;—-")

    return t


def is_dictation_stop_phrase(
    text: str,
    *,
    hotwords: Iterable[str] | None = None,
) -> bool:
    """
    Проверяет, является ли фраза командой выхода из режима диктовки.
    """
    t = strip_hotword_prefix(text, hotwords=hotwords)
    return t in DICTATION_STOP_PHRASES