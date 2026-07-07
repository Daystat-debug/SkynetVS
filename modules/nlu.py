# modules/nlu.py
from __future__ import annotations

import json
import os
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from modules.intent_rules import (
    build_incomplete_command_meta,
    build_set_volume_meta,
    get_exact_intent,
)

import joblib

from modules.entity_registry import (
    APP_ALIASES as _APP_SYNS,
    APP_TITLES as _APP_TITLES,
    SITE_ALIASES as _SITE_SYNS,
    SITE_TITLES as _SITE_TITLES,
    SITE_URLS as _SITE_URLS,
    FOLDER_ALIASES as _FOLDER_SYNS,
    FOLDER_TITLES as _FOLDER_TITLES,
    SETTINGS_SECTION_ALIASES as _SETTINGS_SECTION_SYNS,
    SETTINGS_SECTION_TITLES as _SETTINGS_SECTION_TITLES,
    match_app_code,
    match_folder_code,
    match_settings_section_code,
    match_site_code,
)

_MODEL = None
_MODEL_PATH = Path("models/nlu_intent.joblib")

_TEMPLATES = None
_TEMPLATES_PATH = Path("data/say_templates.json")


def _env_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


def _nlu_min_conf() -> float:
    return _env_float(
        "NLU_ACCEPT_CONF",
        os.getenv("NLU_MIN_CONF", "0.35"),
    )


def _load_model():
    global _MODEL
    if _MODEL is None:
        if not _MODEL_PATH.exists():
            return None
        _MODEL = joblib.load(_MODEL_PATH)
    return _MODEL


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _compact(text: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", _norm(text))


def _load_templates() -> Dict[str, Any]:
    global _TEMPLATES
    if _TEMPLATES is not None:
        return _TEMPLATES
    try:
        _TEMPLATES = json.loads(_TEMPLATES_PATH.read_text(encoding="utf-8"))
    except Exception:
        _TEMPLATES = {
            "FALLBACK": ["Команда не распознана. Повтори, пожалуйста."],
            "GREET": ["Привет. На связи."],
        }
    return _TEMPLATES


def _render_placeholders(s: str, slots: Dict[str, Any]) -> str:
    out = str(s)

    app_code = str(slots.get("app") or "")
    app_title = _APP_TITLES.get(app_code, app_code)
    city = str(slots.get("city") or "").strip()
    city_part = f" в {city}" if city else ""
    site_code = str(slots.get("site") or "")
    site_title = str(slots.get("site_title") or _SITE_TITLES.get(site_code, site_code))
    site_url = str(slots.get("url") or "")
    query = str(slots.get("query") or "").strip()
    folder_code = str(slots.get("folder") or "")
    folder_title = str(slots.get("folder_title") or _FOLDER_TITLES.get(folder_code, folder_code))
    section_code = str(slots.get("section") or "")
    section_title = str(slots.get("section_title") or _SETTINGS_SECTION_TITLES.get(section_code, section_code))

    out = out.replace("{app}", app_title)
    out = out.replace("{app_code}", app_code)
    out = out.replace("{volume}", str(slots.get("volume") or ""))
    out = out.replace("{city}", city_part)
    out = out.replace("{site}", site_title)
    out = out.replace("{url}", site_url)
    out = out.replace("{query}", query)
    out = out.replace("{folder}", folder_title)
    out = out.replace("{section}", section_title)

    if "{time}" in out:
        out = out.replace("{time}", datetime.now().strftime("%H:%M"))

    return out.strip()


def _pick_response(intent: str, slots: Dict[str, Any]) -> str:
    tpl = _load_templates()
    key = (intent or "FALLBACK").upper()
    arr = tpl.get(key) or tpl.get("FALLBACK") or ["..."]

    if isinstance(arr, str):
        s = arr
    else:
        s = random.choice(arr) if arr else "..."

    s = _render_placeholders(s, slots)
    return s.strip() or "..."


def pick_uncertain_response(intent: str, slots: Dict[str, Any]) -> str:
    """
    Возвращает отдельный шаблон ответа для low-confidence режима.
    Если отдельного uncertain-шаблона нет — возвращает пустую строку.
    """
    tpl = _load_templates()
    key = f"{(intent or '').upper()}_UNCERTAIN"
    arr = tpl.get(key)
    if not arr:
        return ""

    if isinstance(arr, str):
        s = arr
    else:
        s = random.choice(arr) if arr else ""

    s = _render_placeholders(s, slots)
    return s.strip()


def pick_generic_uncertain_response() -> str:
    """
    Возвращает общий ответ для low-confidence режима,
    если у конкретного интента нет собственного *_UNCERTAIN шаблона.
    """
    tpl = _load_templates()
    arr = tpl.get("UNCERTAIN_FALLBACK")
    if not arr:
        return ""

    if isinstance(arr, str):
        s = arr
    else:
        s = random.choice(arr) if arr else ""

    return str(s).strip()


def pick_named_response(key: str, slots: Optional[Dict[str, Any]] = None) -> str:
    """
    Возвращает шаблон по произвольному ключу из say_templates.json.
    Если ключа нет — возвращает пустую строку.
    """
    tpl = _load_templates()
    arr = tpl.get((key or "").upper())
    if not arr:
        return ""

    if isinstance(arr, str):
        s = arr
    else:
        s = random.choice(arr) if arr else ""

    return _render_placeholders(s, slots or {}).strip()


def _extract_city(text: str) -> Optional[str]:
    t = _norm(text)
    m = re.search(r"(?:скажи\s+|расскажи\s+)?(?:какая\s+)?(?:сейчас\s+)?погода\s+(?:в|во|на|по)\s+([a-zа-яё .\-]+)$", t)
    if not m:
        m = re.search(r"^(?:скажи\s+|расскажи\s+)?(?:какая\s+)?(?:сейчас\s+)?погода\s+([a-zа-яё .\-]+)$", t)
    if not m:
        return None
    city = m.group(1).strip(" .,!?:;")
    city = re.sub(r"\b(сейчас|сегодня|завтра)$", "", city).strip(" .,!?:;")
    try:
        return city.title()
    except Exception:
        return city


def _extract_open_folder_slots(text: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}
    folder = _fallback_match_folder(text)
    if folder:
        slots["folder"] = folder
        slots["folder_title"] = _FOLDER_TITLES.get(folder, folder)
    return slots


def _fallback_match_app(text: str) -> Optional[str]:
    return match_app_code(text)


def _fallback_match_site(text: str) -> Optional[str]:
    return match_site_code(text)


def _fallback_match_folder(text: str) -> Optional[str]:
    return match_folder_code(text)


def _fallback_match_settings_section(text: str) -> Optional[str]:
    return match_settings_section_code(text)


_TLD_SYNS: Dict[str, str] = {
    "ру": "ru",
    "ком": "com",
    "орг": "org",
    "нет": "net",
    "ио": "io",
    "ai": "ai",
}


def _strip_open_url_prefix(text: str) -> str:
    t = _norm(text)
    patterns = [
        r"^открой сайт\s+(.+)$",
        r"^открой страницу\s+(.+)$",
        r"^открой\s+(.+)$",
        r"^запусти сайт\s+(.+)$",
        r"^запусти\s+(.+)$",
        r"^перейди на\s+(.+)$",
        r"^зайди на\s+(.+)$",
        r"^зайди\s+(.+)$",
    ]

    for pattern in patterns:
        m = re.match(pattern, t)
        if m:
            return (m.group(1) or "").strip(" .,!?:;")

    return t


def _extract_direct_url(text: str) -> Optional[str]:
    candidate = _strip_open_url_prefix(text)
    if not candidate:
        return None

    # 1) если домен уже сказан/распознан как example.com
    m = re.search(r"\b([a-z0-9-]+\.[a-z]{2,10})\b", candidate)
    if m:
        host = m.group(1).lower()
        return f"https://{host}"

    # 2) вариант вида "openai точка com"
    c = _norm(candidate)
    c = re.sub(r"\bточка\b", ".", c)
    c = re.sub(r"\s*\.\s*", ".", c).strip()

    m = re.search(r"\b([a-z0-9-]+\.[a-zа-яё]{2,10})\b", c)
    if m:
        host = m.group(1).lower()
        parts = host.split(".")
        if len(parts) == 2:
            name, tld_raw = parts
            tld = _TLD_SYNS.get(tld_raw, tld_raw)
            if re.fullmatch(r"[a-z0-9-]+", name) and re.fullmatch(r"[a-z]{2,10}", tld):
                return f"https://{name}.{tld}"

    # 3) вариант вида "openai com"
    tokens = [tok for tok in re.split(r"[^a-zа-яё0-9]+", c) if tok]
    if len(tokens) >= 2:
        tld_raw = tokens[-1]
        tld = _TLD_SYNS.get(tld_raw, "")
        host = "".join(tokens[:-1]).lower()

        if tld and re.fullmatch(r"[a-z0-9-]+", host):
            return f"https://{host}.{tld}"

    return None


_NUM = {
    "ноль": 0,
    "один": 1, "раз": 1,
    "два": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,
    "сто": 100,
}


def _extract_volume(text: str) -> Optional[int]:
    t = _norm(text)
    # 1) цифры
    m = re.search(r"(\d{1,3})", t)
    if m:
        v = int(m.group(1))
        if v < 0:
            v = 0
        if v > 100:
            v = 100
        return v

    # 2) слова (очень простой парсер: "тридцать", "двадцать пять", "сто")
    words = [w for w in re.split(r"[^a-zа-яё]+", t) if w]
    total = 0
    used = False
    for w in words:
        if w in _NUM:
            val = _NUM[w]
            # если сказали "сто", считаем как 100 и останавливаемся
            if val == 100:
                total = 100
                used = True
                break
            total += val
            used = True
    if used:
        if total < 0:
            total = 0
        if total > 100:
            total = 100
        return int(total)
    return None


def _extract_search_query(text: str) -> Optional[str]:
    t = _norm(text)

    patterns = [
        r"^найди в интернете про\s+(.+)$",
        r"^поищи в интернете про\s+(.+)$",
        r"^найди в интернете\s+(.+)$",
        r"^поищи в интернете\s+(.+)$",
        r"^найди\s+(.+)$",
        r"^поищи\s+(.+)$",
        r"^поиск\s+(.+)$",
    ]

    for pattern in patterns:
        m = re.match(pattern, t)
        if m:
            q = (m.group(1) or "").strip(" .,!?:;")
            return q or None

    return None


def _extract_youtube_query(text: str) -> Optional[str]:
    t = _norm(text)

    patterns = [
        r"^найди на ютубе\s+(.+)$",
        r"^поищи на ютубе\s+(.+)$",
        r"^найди на youtube\s+(.+)$",
        r"^поищи на youtube\s+(.+)$",
        r"^найди видео про\s+(.+)\s+на ютубе$",
        r"^поищи ролик про\s+(.+)\s+на ютубе$",
        r"^ютуб поиск\s+(.+)$",
    ]

    for pattern in patterns:
        m = re.match(pattern, t)
        if m:
            q = (m.group(1) or "").strip(" .,!?:;")
            return q or None

    return None


def _extract_show_ip_slots(text: str) -> Dict[str, Any]:
    t = _norm(text)
    slots: Dict[str, Any] = {}

    if any(x in t for x in ("внешней", "внешний", "публичный", "наружный", "wan")):
        slots["ip_scope"] = "public"
    elif any(x in t for x in ("локальный", "внутренний", "lan")):
        slots["ip_scope"] = "local"
    else:
        slots["ip_scope"] = "local"

    return slots


def _extract_open_app_slots(text: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}
    app = _fallback_match_app(text)
    if app:
        slots["app"] = app
    return slots


def _extract_open_url_slots(text: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}

    site = _fallback_match_site(text)
    if site:
        slots["site"] = site
        slots["site_title"] = _SITE_TITLES.get(site, site)
        slots["url"] = _SITE_URLS.get(site, "")
        return slots

    direct_url = _extract_direct_url(text)
    if direct_url:
        title = re.sub(r"^https?://", "", direct_url).rstrip("/")
        slots["site"] = title
        slots["site_title"] = title
        slots["url"] = direct_url

    return slots


def _extract_search_web_slots(text: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}
    query = _extract_search_query(text)
    if query:
        slots["query"] = query
    return slots


def _extract_search_youtube_slots(text: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}
    query = _extract_youtube_query(text)
    if query:
        slots["query"] = query
    return slots


def _extract_weather_slots(text: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}
    city = _extract_city(text)
    if city:
        slots["city"] = city
    return slots


def _extract_set_volume_slots(text: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}
    v = _extract_volume(text)
    if v is not None:
        slots["volume"] = v
    return slots


def _extract_open_settings_slots(text: str) -> Dict[str, Any]:
    slots: Dict[str, Any] = {}
    section = _fallback_match_settings_section(text)
    if section:
        slots["section"] = section
        slots["section_title"] = _SETTINGS_SECTION_TITLES.get(section, section)
    return slots


_SLOT_EXTRACTORS: Dict[str, Callable[[str], Dict[str, Any]]] = {
    "OPEN_APP": _extract_open_app_slots,
    "OPEN_URL": _extract_open_url_slots,
    "SEARCH_WEB": _extract_search_web_slots,
    "SEARCH_YOUTUBE": _extract_search_youtube_slots,
    "WEATHER": _extract_weather_slots,
    "SET_VOLUME": _extract_set_volume_slots,
    "OPEN_FOLDER": _extract_open_folder_slots,
    "OPEN_SETTINGS": _extract_open_settings_slots,
    "SHOW_IP": _extract_show_ip_slots,
    "CLOSE_APP": _extract_open_app_slots,
}


def _model_classes(pipe: Any) -> list[Any]:
    classes = getattr(pipe, "classes_", None)
    if classes is not None:
        return list(classes)

    steps = getattr(pipe, "steps", None)
    if steps:
        try:
            last_step = steps[-1][1]
            classes = getattr(last_step, "classes_", None)
            if classes is not None:
                return list(classes)
        except Exception:
            return []

    return []


def _extract_slots_for_intent(intent: Optional[str], text: str) -> Dict[str, Any]:
    if not intent:
        return {}

    extractor = _SLOT_EXTRACTORS.get(str(intent).upper())
    if not extractor:
        return {}

    try:
        return dict(extractor(text) or {})
    except Exception:
        return {}


def predict_candidates(
    text: str,
    *,
    limit: int = 5,
    include_rules: bool = True,
) -> list[Dict[str, Any]]:
    """
    Возвращает diagnostic top-k кандидатов NLU.

    Важно:
      - не меняет поведение predict()
      - нужен для eval/debug
      - показывает rule-кандидаты и model-кандидаты
    """
    t = _norm(text)
    if not t:
        return []

    try:
        limit = max(1, int(limit))
    except Exception:
        limit = 5

    rows: list[Dict[str, Any]] = []

    if include_rules:
        incomplete_meta = build_incomplete_command_meta(t)
        if incomplete_meta:
            rows.append(
                {
                    "intent": None,
                    "confidence": 0.0,
                    "source": "rule",
                    "rule": "incomplete_command_rule",
                    "slots": {},
                    "accepted_by_threshold": False,
                }
            )

        rule_intent = get_exact_intent(t)
        if rule_intent:
            slots = _extract_slots_for_intent(rule_intent, t)
            rows.append(
                {
                    "intent": str(rule_intent).upper(),
                    "confidence": 1.0,
                    "source": "rule",
                    "rule": "exact_intent_rule",
                    "slots": slots,
                    "accepted_by_threshold": True,
                }
            )

        set_volume_meta = build_set_volume_meta(t, extract_volume=_extract_volume)
        if set_volume_meta:
            intent = str(set_volume_meta.get("intent") or "").upper()
            slots = dict(set_volume_meta.get("slots") or {})
            rows.append(
                {
                    "intent": intent or None,
                    "confidence": float(set_volume_meta.get("confidence") or 0.0),
                    "source": "rule",
                    "rule": "set_volume_rule",
                    "slots": slots,
                    "accepted_by_threshold": True,
                }
            )

    pipe = _load_model()
    if not pipe:
        return rows[:limit]

    try:
        if hasattr(pipe, "predict_proba"):
            proba = pipe.predict_proba([t])[0]
            classes = _model_classes(pipe)

            if classes and len(classes) == len(proba):
                pairs = sorted(
                    zip(classes, proba),
                    key=lambda pair: float(pair[1]),
                    reverse=True,
                )

                for rank, (intent_raw, conf_raw) in enumerate(pairs[:limit], start=1):
                    intent = str(intent_raw).upper()
                    conf = float(conf_raw)
                    slots = _extract_slots_for_intent(intent, t)

                    rows.append(
                        {
                            "rank": rank,
                            "intent": intent,
                            "confidence": round(conf, 4),
                            "source": "model",
                            "slots": slots,
                            "accepted_by_threshold": conf >= _nlu_min_conf(),
                        }
                    )

                return rows[: max(limit, len(rows))]

        intent = str(pipe.predict([t])[0]).upper()
        rows.append(
            {
                "rank": 1,
                "intent": intent,
                "confidence": 1.0,
                "source": "model",
                "slots": _extract_slots_for_intent(intent, t),
                "accepted_by_threshold": True,
            }
        )
    except Exception:
        return rows[:limit]

    return rows[:limit]


def predict(text: str) -> Dict[str, Any]:
    """
    -> {
        "intent": Optional[str],
        "confidence": float,
        "slots": dict,
        "say": str
    }
    """
    t = _norm(text)

    if not t:
        slots: Dict[str, Any] = {}
        return {
            "intent": None,
            "confidence": 0.0,
            "slots": slots,
            "say": _pick_response("FALLBACK", slots),
        }

    incomplete_meta = build_incomplete_command_meta(t)
    if incomplete_meta:
        return incomplete_meta

    rule_intent = get_exact_intent(t)
    if rule_intent:
        slots: Dict[str, Any] = {}

        extractor = _SLOT_EXTRACTORS.get(rule_intent)
        if extractor:
            slots.update(extractor(t))

        return {
            "intent": rule_intent,
            "confidence": 1.0,
            "slots": slots,
            "say": _pick_response(rule_intent, slots),
            "_rule": "exact_intent_rule",
        }

    set_volume_meta = build_set_volume_meta(t, extract_volume=_extract_volume)
    if set_volume_meta:
        slots = dict(set_volume_meta.get("slots") or {})
        set_volume_meta["say"] = _pick_response("SET_VOLUME", slots)
        return set_volume_meta

    pipe = _load_model()
    if not pipe:
        slots: Dict[str, Any] = {}
        return {
            "intent": None,
            "confidence": 0.0,
            "slots": slots,
            "say": _pick_response("FALLBACK", slots),
        }

    intent: Optional[str] = None
    conf: float = 0.0
    try:
        intent = str(pipe.predict([t])[0]).upper()
        if hasattr(pipe, "predict_proba"):
            proba = pipe.predict_proba([t])[0]
            conf = float(max(proba))
        else:
            conf = 1.0
    except Exception:
        intent = None
        conf = 0.0

    # ---- Порог уверенности ----
    if (intent is None) or (conf < _nlu_min_conf()):
        slots: Dict[str, Any] = {}
        return {"intent": None, "confidence": conf, "slots": slots, "say": _pick_response("FALLBACK", slots)}

    slots: Dict[str, Any] = {}

    extractor = _SLOT_EXTRACTORS.get(intent)
    if extractor:
        slots.update(extractor(t))

    say = _pick_response(intent, slots)

    return {"intent": intent, "confidence": conf, "slots": slots, "say": say}

