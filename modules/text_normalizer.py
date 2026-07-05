from __future__ import annotations

import re
from typing import Dict, Tuple


# Очень консервативные ручные alias-замены.
# Ключ = как STT часто коверкает, значение = как хотим нормализовать.
_SAFE_ALIASES: Dict[str, str] = {
    "дискомфорт": "дискорд",
    "де скоро": "дискорд",
    "диск орды": "дискорд",
    "гед хаб": "гитхаб",
    "гид хаб": "гитхаб",
    "гиды хаб": "гитхаб",
    "чат гпу": "chatgpt",
    "чат гбдд": "chatgpt",
    "чоджи пяти": "chatgpt",
    "чат же пяти": "chatgpt",
    "чат джип идти": "chatgpt",
}

# Применяем нормализацию только если фраза выглядит как команда,
# а не как свободная диктовка.
_COMMAND_PREFIXES = (
    "открой ",
    "закрой ",
    "запусти ",
    "включи ",
    "выключи ",
    "найди ",
    "поищи ",
    "переключи ",
    "скажи ",
    "покажи ",
    "режим ",
    "включи режим ",
    "выключи режим ",
    "выйди из ",
    "начни ",
    "прекрати ",
    "останови ",
    "напечатай ",
    "введи ",
    "напиши ",
)


def _norm_spaces(text: str) -> str:
    return " ".join((text or "").lower().split())


def _replace_whole_phrase(text: str, src: str, dst: str) -> str:
    pattern = r"(?<!\w)" + re.escape(src) + r"(?!\w)"
    return re.sub(pattern, dst, text)


def looks_like_command(text: str) -> bool:
    t = _norm_spaces(text)
    return any(t.startswith(prefix) for prefix in _COMMAND_PREFIXES)


def normalize_command_text(text: str) -> Tuple[str, bool]:
    """
    Возвращает (normalized_text, changed).
    Меняет только очень безопасные alias'ы и только в командных фразах.
    """
    t = _norm_spaces(text)
    if not t:
        return t, False

    if not looks_like_command(t):
        return t, False

    original = t
    for wrong, correct in _SAFE_ALIASES.items():
        t = _replace_whole_phrase(t, wrong, correct)

    return t, (t != original)