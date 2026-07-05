from __future__ import annotations

from typing import Any, Mapping

from modules.command_decision import is_accepted


def filled_slot_count(meta: Mapping[str, Any]) -> int:
    slots = meta.get("slots") or {}
    count = 0

    for value in slots.values():
        if value is None:
            continue

        if isinstance(value, str) and not value.strip():
            continue

        if isinstance(value, (list, dict, tuple, set)) and not value:
            continue

        count += 1

    return count


def needs_normalization_retry(raw_text: str, meta: Mapping[str, Any]) -> bool:
    """
    Решает, стоит ли прогнать текст через TextNormalizer и повторить NLU.

    Это не общий fallback.
    Это осторожный retry для случаев:
      - intent не найден;
      - intent найден, но не хватает важной closed-set сущности.
    """
    _ = raw_text

    intent = str(meta.get("intent") or "").upper()
    slots = meta.get("slots") or {}

    if not intent:
        return True

    if intent in {"OPEN_APP", "CLOSE_APP"} and not slots.get("app"):
        return True

    if intent == "OPEN_URL" and not slots.get("url"):
        return True

    if intent == "OPEN_FOLDER" and not slots.get("folder"):
        return True

    return False


def should_use_retry_result(
    old_meta: Mapping[str, Any],
    new_meta: Mapping[str, Any],
    *,
    accept_conf: float,
) -> bool:
    """
    Решает, можно ли заменить старый NLU-result результатом после normalization retry.
    """
    old_intent = str(old_meta.get("intent") or "").upper()
    new_intent = str(new_meta.get("intent") or "").upper()

    if not new_intent:
        return False

    if not old_intent:
        return True

    if old_intent == new_intent:
        if filled_slot_count(new_meta) > filled_slot_count(old_meta):
            return True

        old_conf = float(old_meta.get("confidence") or 0.0)
        new_conf = float(new_meta.get("confidence") or 0.0)

        if new_conf > old_conf + 0.05:
            return True

        return False

    old_accepted = is_accepted(old_meta, accept_conf=accept_conf)
    new_accepted = is_accepted(new_meta, accept_conf=accept_conf)

    if not old_accepted and new_accepted:
        return True

    return False