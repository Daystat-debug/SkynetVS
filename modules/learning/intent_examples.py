"""Shared, in-memory editing of NLU training examples."""
from __future__ import annotations

from typing import Dict, Any


def add_example(data: Dict[str, Any], intent: str, text: str) -> bool:
    """
    Добавляет text в examples выбранного intent.
    Возвращает True если добавили, False если уже был.
    """
    intent = intent.strip().upper()
    text = " ".join(text.lower().split()).strip()
    if not intent or not text:
        return False

    intents = data.get("intents") or []
    # найти intent
    target = None
    for it in intents:
        if str(it.get("intent") or "").strip().upper() == intent:
            target = it
            break
    if target is None:
        # если вдруг нет такого intent — создадим
        target = {"intent": intent, "examples": []}
        intents.append(target)
        data["intents"] = intents

    examples = target.get("examples")
    if not isinstance(examples, list):
        examples = []
        target["examples"] = examples

    if any((" ".join(str(x).lower().split()) == text) for x in examples):
        return False

    examples.append(text)
    return True
