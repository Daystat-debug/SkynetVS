from __future__ import annotations

import re
from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any, Dict, Tuple


_APP_ALIASES: Dict[str, list[str]] = {
    "notepad": ["блокнот", "notepad", "нотпад"],
    "calc": ["калькулятор", "calculator", "calc", "кальк"],
    "chrome": [
        "хром",
        "chrome",
        "гугл хром",
        "google chrome",
        "браузер",
        "гугл браузер",
        "google браузер",
        "интернет браузер",
    ],
    "discord": ["дискорд", "discord", "дискомфорт", "де скоро", "диск орды", "дискорда"],
    "explorer": [
        "проводник",
        "проводник windows",
        "проводник виндовс",
        "explorer",
        "file explorer",
        "файловый менеджер",
    ],
}

_SITE_ALIASES: Dict[str, list[str]] = {
    "youtube": ["ютуб", "youtube", "you tube"],
    "google": ["гугл", "google"],
    "github": ["гитхаб", "github", "git hub", "гед хаб", "гид хаб", "гиды хаб"],
    "gmail": ["gmail", "джимейл", "почта gmail"],
    "chatgpt": ["chatgpt", "чат gpt", "чат жпт", "чат гпт", "чат гпу", "чат гбдд", "чоджи пяти"],
    "habr": ["хабр", "habr", "хабр ру"],
    "yandex": ["яндекс", "yandex", "яндекс ру"],
    "vk": ["вк", "vk", "вконтакте", "вк точка ком"],
    "openai": ["openai", "open ai", "опен аи"],
}

_SITE_TITLES: Dict[str, str] = {
    "youtube": "ютуб",
    "google": "гугл",
    "github": "гитхаб",
    "gmail": "gmail",
    "chatgpt": "chatgpt",
    "habr": "хабр",
    "yandex": "яндекс",
    "vk": "вк",
    "openai": "openai",
}

_SITE_URLS: Dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "chatgpt": "https://chatgpt.com",
    "habr": "https://habr.com",
    "yandex": "https://yandex.ru",
    "vk": "https://vk.com",
    "openai": "https://openai.com",
}


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _compact(text: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", _norm(text))


def _best_candidate_from_aliases(
    text: str,
    alias_map: Dict[str, list[str]],
    *,
    min_ratio: float = 0.84,
    min_margin: float = 0.08,
) -> Tuple[str, float]:
    t_norm = _norm(text)
    t_compact = _compact(text)

    # 1) exact-ish alias hit
    for code, aliases in alias_map.items():
        for alias in aliases:
            a_norm = _norm(alias)
            a_compact = _compact(alias)

            if a_norm and a_norm in t_norm:
                return code, 1.0
            if a_compact and a_compact in t_compact:
                return code, 0.99

    # 2) cautious fuzzy over aliases
    best_code = ""
    best_score = 0.0
    second_score = 0.0

    for code, aliases in alias_map.items():
        local_best = 0.0
        for alias in aliases:
            score = SequenceMatcher(None, t_compact, _compact(alias)).ratio()
            if score > local_best:
                local_best = score

        if local_best > best_score:
            second_score = best_score
            best_score = local_best
            best_code = code
        elif local_best > second_score:
            second_score = local_best

    if best_score >= min_ratio and (best_score - second_score) >= min_margin:
        return best_code, best_score

    return "", 0.0


def resolve_entities(text: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Консервативно дозаполняет сущности после NLU.
    Не меняет уже найденные slots, только добавляет недостающие.
    """
    result = deepcopy(meta)
    intent = str(result.get("intent") or "").upper()
    slots = result.get("slots") or {}
    text = _norm(text)

    if intent in {"OPEN_APP", "CLOSE_APP"} and not slots.get("app"):
        app_code, score = _best_candidate_from_aliases(text, _APP_ALIASES)
        if app_code:
            slots["app"] = app_code
            slots["_resolved_app_score"] = round(score, 3)

    if intent == "OPEN_URL" and not slots.get("url"):
        site_code, score = _best_candidate_from_aliases(text, _SITE_ALIASES)
        if site_code:
            slots["site"] = site_code
            slots["site_title"] = _SITE_TITLES.get(site_code, site_code)
            slots["url"] = _SITE_URLS.get(site_code, "")
            slots["_resolved_site_score"] = round(score, 3)

    result["slots"] = slots
    return result