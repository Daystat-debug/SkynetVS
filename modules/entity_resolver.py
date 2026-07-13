from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Dict, Sequence

from modules.entity_registry import (
    RescueMatch,
    get_site_title,
    get_site_url,
    match_app,
    match_app_rescue,
    match_site,
    match_site_rescue,
    normalize_entity_text,
)


@dataclass(frozen=True)
class EntityRescueResult:
    meta: Dict[str, Any]
    changed: bool
    kind: str = ""
    code: str = ""
    score: float = 0.0
    margin: float = 0.0
    source_text: str = ""
    candidate_text: str = ""
    alias: str = ""


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


def _changed_rescue_result(
    *,
    meta: Dict[str, Any],
    kind: str,
    match: RescueMatch,
) -> EntityRescueResult:
    return EntityRescueResult(
        meta=meta,
        changed=True,
        kind=kind,
        code=match.code,
        score=round(match.score, 4),
        margin=round(match.margin, 4),
        source_text=match.source_text,
        candidate_text=match.candidate_text,
        alias=match.alias,
    )


def rescue_missing_entities(
    texts: Sequence[str],
    meta: Dict[str, Any],
) -> EntityRescueResult:
    """
    Восстанавливает только отсутствующую registry-сущность.

    Не меняет intent и не принимает произвольные приложения/домены.
    """
    result = deepcopy(meta)

    intent = str(
        result.get("intent") or ""
    ).upper().strip()

    slots_raw = result.get("slots") or {}
    slots = (
        dict(slots_raw)
        if isinstance(slots_raw, dict)
        else {}
    )

    source_texts = [
        str(text or "").strip()
        for text in texts
        if str(text or "").strip()
    ]

    if not source_texts:
        result["slots"] = slots
        return EntityRescueResult(
            meta=result,
            changed=False,
        )

    if (
        intent in {"OPEN_APP", "CLOSE_APP"}
        and not slots.get("app")
    ):
        app_match = match_app_rescue(source_texts)

        if app_match:
            slots["app"] = app_match.code
            result["slots"] = slots

            return _changed_rescue_result(
                meta=result,
                kind="app",
                match=app_match,
            )

    if (
        intent == "OPEN_URL"
        and not slots.get("url")
    ):
        site_match = match_site_rescue(source_texts)

        if site_match:
            slots["site"] = site_match.code
            slots["site_title"] = get_site_title(
                site_match.code
            )
            slots["url"] = get_site_url(
                site_match.code
            )
            result["slots"] = slots

            return _changed_rescue_result(
                meta=result,
                kind="site",
                match=site_match,
            )

    result["slots"] = slots

    return EntityRescueResult(
        meta=result,
        changed=False,
    )