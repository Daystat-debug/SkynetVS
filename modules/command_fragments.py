from __future__ import annotations

from typing import Iterable

from modules.hotword_utils import is_only_hotword, norm_text


INCOMPLETE_COMMAND_STARTERS = {
    "открой",
    "запусти",
    "включи",
    "выключи",
    "переключи",
    "сделай",
    "поставь",
    "установи",
    "добавь",
    "убавь",
    "уменьши",
    "увеличь",
}


def merge_phrases(left: str, right: str) -> str:
    """
    Склеивает две STT-фразы в одну команду.

    Пример:
      "открой" + "блокнот" -> "открой блокнот"
    """
    left_n = norm_text(left)
    right_n = norm_text(right)

    if not left_n:
        return right_n

    if not right_n:
        return left_n

    return f"{left_n} {right_n}".strip()


def looks_incomplete_command(
    text: str,
    *,
    hotwords: Iterable[str] = (),
) -> bool:
    """
    Определяет, похожа ли фраза на обрезанное начало команды.

    Примеры:
      "открой"      -> True
      "запусти"     -> True
      "открой хром" -> False
      "скайнет"     -> False
    """
    t = norm_text(text)

    if not t:
        return False

    if is_only_hotword(t, hotwords=hotwords):
        return False

    words = t.split()

    return len(words) == 1 and t in INCOMPLETE_COMMAND_STARTERS