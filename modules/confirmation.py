from __future__ import annotations

from typing import Any, Mapping

from modules.nlu import pick_named_response


CONFIRM_YES_PHRASES = {
    "да",
    "ага",
    "угу",
    "подтверждаю",
    "подтвердить",
    "ок",
    "okay",
    "ok",
    "выполняй",
}


CONFIRM_NO_PHRASES = {
    "нет",
    "не",
    "отмена",
    "отменить",
    "не надо",
    "не нужно",
    "стоп",
}


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def is_confirmation_yes(text: str) -> bool:
    return _norm(text) in CONFIRM_YES_PHRASES


def is_confirmation_no(text: str) -> bool:
    return _norm(text) in CONFIRM_NO_PHRASES


def build_confirmation_prompt(meta: Mapping[str, Any]) -> str:
    """
    Формирует текст запроса подтверждения для опасных действий.

    Пример:
      EMPTY_RECYCLE_BIN -> EMPTY_RECYCLE_BIN_CONFIRM

    Если специального шаблона нет, используется CONFIRM_FALLBACK.
    """
    intent = str(meta.get("intent") or "").upper()
    slots = dict(meta.get("slots") or {})

    if intent:
        prompt = pick_named_response(f"{intent}_CONFIRM", slots)
        if prompt:
            return prompt

    prompt = pick_named_response("CONFIRM_FALLBACK", slots)
    if prompt:
        return prompt

    return "Подтвердить выполнение команды?"