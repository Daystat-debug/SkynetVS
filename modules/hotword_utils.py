from __future__ import annotations

from typing import Iterable


HOTWORD_STRIP_CHARS = " ,.!?:;—-"


def norm_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def _norm_hotwords(hotwords: Iterable[str]) -> list[str]:
    return [
        norm_text(hw)
        for hw in hotwords
        if norm_text(hw)
    ]


def split_hotword_prefix(
    text: str,
    *,
    hotwords: Iterable[str],
) -> tuple[bool, str]:
    """
    Проверяет, начинается ли фраза с hotword.

    Возвращает:
      (True, rest)  — hotword найден, rest = текст после hotword
      (False, "")   — hotword не найден

    Примеры:
      "скайнет открой блокнот"  -> (True, "открой блокнот")
      "скайнет, открой блокнот" -> (True, "открой блокнот")
      "скайнет"                 -> (True, "")
    """
    t = norm_text(text)

    if not t:
        return False, ""

    for hw in _norm_hotwords(hotwords):
        if t == hw:
            return True, ""

        if t.startswith(hw):
            tail = t[len(hw):]

            # Важно: не считать "скайнетик" hotword-ом.
            if not tail:
                return True, ""

            if tail[0] in HOTWORD_STRIP_CHARS:
                return True, tail.strip(HOTWORD_STRIP_CHARS)

    return False, ""


def has_hotword(
    text: str,
    *,
    hotwords: Iterable[str],
) -> bool:
    found, _ = split_hotword_prefix(text, hotwords=hotwords)
    return found


def strip_hotword(
    text: str,
    *,
    hotwords: Iterable[str],
) -> str:
    found, rest = split_hotword_prefix(text, hotwords=hotwords)
    if not found:
        return ""
    return rest


def is_only_hotword(
    text: str,
    *,
    hotwords: Iterable[str],
) -> bool:
    found, rest = split_hotword_prefix(text, hotwords=hotwords)
    return found and not rest


def is_ack_echo(
    text: str,
    *,
    ack_text: str,
) -> bool:
    """
    STT может распознать 'Слушаю' как 'слушай',
    поэтому проверяем несколько безопасных вариантов.
    """
    t = norm_text(text)
    ack = norm_text(ack_text)

    if not t:
        return False

    ack_variants = {
        ack,
        "слушаю",
        "слушай",
    }

    return t in ack_variants


def should_ignore_during_ack_window(
    text: str,
    *,
    hotwords: Iterable[str],
    ack_text: str,
) -> bool:
    """
    Во время короткого окна после ACK игнорируем:
      - эхо самой фразы ACK;
      - bare hotword.
    """
    return is_ack_echo(text, ack_text=ack_text) or is_only_hotword(
        text,
        hotwords=hotwords,
    )