from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def norm(text: str) -> str:
    return " ".join((text or "").lower().split()).strip()


def looks_natural_command(text: str) -> bool:
    t = norm(text)
    if not t:
        return False

    natural_starters = (
        "открой ",
        "закрой ",
        "запусти ",
        "включи ",
        "выключи ",
        "останови ",
        "поставь ",
        "сделай ",
        "переключи ",
        "пауза",
        "стоп",
        "новая строка",
        "нажми ",
        "прочитай ",
        "скажи ",
        "покажи ",
        "какая ",
        "какое ",
        "что ",
        "режим ",
        "выйди ",
        "прекрати ",
    )

    return t.startswith(natural_starters) or len(t.split()) >= 2


def contains_noise_tokens(text: str) -> bool:
    t = norm(text)

    bad_substrings = {
        "де скоро",
        "дискомфорт",
        "гед хаб",
        "гид хаб",
        "гиды хаб",
        "чоджи пяти",
        "чат гбдд",
        "чат гпу",
        "мужик",
    }

    return any(x in t for x in bad_substrings)


def extract_entity_tail(text: str, intent: str) -> str:
    t = norm(text)

    if intent in {"OPEN_APP", "CLOSE_APP"}:
        patterns = [
            r"^(?:скайнет\s+)?(?:открой|закрой|запусти|выключи)\s+(?:приложение\s+|программу\s+)?(.+)$",
        ]
    elif intent == "OPEN_URL":
        patterns = [
            r"^(?:скайнет\s+)?(?:открой|зайди(?:\s+на)?|перейди(?:\s+на)?|запусти)\s+(?:сайт\s+|страницу\s+)?(.+)$",
        ]
    else:
        return ""

    for pattern in patterns:
        m = re.match(pattern, t)
        if m:
            return (m.group(1) or "").strip(" .,!?:;")
    return ""


def is_strong_intent_example_candidate(
    *,
    failed_text: str,
    corrected_text: str,
    corrected_confidence: float,
    seen_count: int,
) -> bool:
    return (
        seen_count >= 3
        and corrected_confidence >= 0.60
        and looks_natural_command(failed_text)
        and looks_natural_command(corrected_text)
        and not contains_noise_tokens(failed_text)
    )


def classify_row(row: Dict[str, Any]) -> Dict[str, Any]:
    failed_text = str(row.get("failed_text") or "").strip()
    corrected_text = str(row.get("corrected_text") or "").strip()
    intent = str(row.get("corrected_intent") or "").strip().upper()
    conf = float(row.get("corrected_confidence") or 0.0)
    slots = row.get("corrected_slots") or {}
    seen_count = int(row.get("seen_count") or 0)

    result: Dict[str, Any] = {
        "failed_text": failed_text,
        "corrected_text": corrected_text,
        "intent": intent,
        "seen_count": seen_count,
        "corrected_confidence": conf,
        "corrected_slots": slots,
        "promotion_type": "reject",
        "reason": "",
    }

    if not failed_text or not corrected_text or not intent:
        result["reason"] = "missing_core_fields"
        return result

    if seen_count < 1:
        result["reason"] = "not_enough_signal"
        return result

    # 1. Closed-set entity mismatch -> alias path
    if intent in {"OPEN_APP", "CLOSE_APP", "OPEN_URL"}:
        failed_entity = extract_entity_tail(failed_text, intent)
        corrected_entity = extract_entity_tail(corrected_text, intent)

        if failed_entity and corrected_entity and failed_entity != corrected_entity:
            if intent in {"OPEN_APP", "CLOSE_APP"} and slots.get("app") and seen_count >= 2:
                result["promotion_type"] = "entity_alias"
                result["reason"] = "closed_set_entity_mismatch"
                result["from"] = failed_entity
                result["to"] = corrected_entity
                return result

            if intent == "OPEN_URL" and slots.get("url") and seen_count >= 2:
                result["promotion_type"] = "entity_alias"
                result["reason"] = "closed_set_entity_mismatch"
                result["from"] = failed_entity
                result["to"] = corrected_entity
                return result

    # 2. Strong natural paraphrase -> intent example
    if is_strong_intent_example_candidate(
        failed_text=failed_text,
        corrected_text=corrected_text,
        corrected_confidence=conf,
        seen_count=seen_count,
    ):
        result["promotion_type"] = "intent_example"
        result["reason"] = "strong_natural_paraphrase"
        return result

    # 3. Otherwise, if corrected command is natural enough, treat as phrase correction
    if looks_natural_command(corrected_text) and conf >= 0.40:
        result["promotion_type"] = "phrase_correction"
        result["reason"] = "whole_phrase_distortion"
        return result

    result["reason"] = "low_quality_candidate"
    return result


def build_report(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    classified = [classify_row(row) for row in rows]

    intent_examples = [r for r in classified if r["promotion_type"] == "intent_example"]
    entity_aliases = [r for r in classified if r["promotion_type"] == "entity_alias"]
    phrase_corrections = [r for r in classified if r["promotion_type"] == "phrase_correction"]
    rejects = [r for r in classified if r["promotion_type"] == "reject"]

    return {
        "totals": {
            "source_rows": len(rows),
            "intent_examples": len(intent_examples),
            "entity_aliases": len(entity_aliases),
            "phrase_corrections": len(phrase_corrections),
            "rejects": len(rejects),
        },
        "intent_examples": intent_examples,
        "entity_aliases": entity_aliases,
        "phrase_corrections": phrase_corrections,
        "rejects": rejects,
    }