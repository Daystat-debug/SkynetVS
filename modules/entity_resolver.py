from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from modules.entity_registry import (
    get_site_title,
    get_site_url,
    match_app,
    match_site,
    normalize_entity_text,
)


def resolve_entities(text: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Консервативно дозаполняет сущности после NLU.
    Не меняет уже найденные slots, только добавляет недостающие.
    """
    result = deepcopy(meta)
    intent = str(result.get("intent") or "").upper()
    slots = result.get("slots") or {}

    text_norm = normalize_entity_text(text)

    if intent in {"OPEN_APP", "CLOSE_APP"} and not slots.get("app"):
        app_match = match_app(text_norm, fuzzy=True)

        if app_match:
            slots["app"] = app_match.code
            slots["_resolved_app_score"] = round(app_match.score, 3)

    if intent == "OPEN_URL" and not slots.get("url"):
        site_match = match_site(text_norm, fuzzy=True)

        if site_match:
            slots["site"] = site_match.code
            slots["site_title"] = get_site_title(site_match.code)
            slots["url"] = get_site_url(site_match.code)
            slots["_resolved_site_score"] = round(site_match.score, 3)

    result["slots"] = slots
    return result