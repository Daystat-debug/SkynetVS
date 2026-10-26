from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List


class FeedbackAnalyzer:
    def __init__(self, base_dir: str = "data/learning") -> None:
        self._base_dir = Path(base_dir)

        self._command_history_path = self._base_dir / "command_history.jsonl"
        self._nlu_hard_cases_path = self._base_dir / "nlu_hard_cases.jsonl"
        self._action_failures_path = self._base_dir / "action_failures.jsonl"
        self._resolver_candidates_path = self._base_dir / "resolver_candidates.jsonl"

        self._repeat_like_phrases = {
            "повтори",
            "еще",
            "ещё",
            "повтори",
        }

    def _read_jsonl(self, path: Path) -> List[Dict[str, Any]]:
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

    def _compact(self, text: str) -> str:
        return re.sub(r"[^a-zа-яё0-9]+", "", (text or "").lower())

    def _parse_ts(self, value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(str(value or "").strip())
        except Exception:
            return None

    def _is_repeat_like_text(self, text: str) -> bool:
        t = " ".join((text or "").lower().split()).strip()
        return t in self._repeat_like_phrases

    def _is_valid_corrected_row(self, row: Dict[str, Any]) -> bool:
        meta = row.get("meta") or {}
        intent = str(meta.get("intent") or "").upper()
        conf = float(meta.get("confidence") or 0.0)
        accepted = bool(row.get("accepted"))
        missing_slots = row.get("missing_slots") or []

        if not accepted:
            return False
        if not intent:
            return False
        if missing_slots:
            return False
        if conf < 0.40:
            return False

        return True

    def analyze(self, *, correction_limit: int | None = 10) -> Dict[str, Any]:
        command_history = self._read_jsonl(self._command_history_path)
        hard_cases = self._read_jsonl(self._nlu_hard_cases_path)
        action_failures = self._read_jsonl(self._action_failures_path)
        resolver_candidates = self._read_jsonl(self._resolver_candidates_path)

        correction_pairs = self._find_correction_pairs(command_history, limit=correction_limit)
        alias_candidates = self._build_alias_candidates(correction_pairs)

        summary: Dict[str, Any] = {
            "totals": {
                "command_history": len(command_history),
                "hard_cases": len(hard_cases),
                "action_failures": len(action_failures),
                "resolver_candidates": len(resolver_candidates),
            },
            "top_hard_cases": self._top_hard_cases(hard_cases),
            "repeat_like_hard_cases": self._top_repeat_like_hard_cases(hard_cases),
            "similar_hard_case_groups": self._group_similar_hard_cases(hard_cases),
            "top_missing_slots": self._top_missing_slots(command_history),
            "top_action_failures": self._top_action_failures(action_failures),
            "top_resolver_candidates": self._top_resolver_candidates(resolver_candidates),
            "correction_pairs": correction_pairs,
            "alias_candidates": alias_candidates,
            "suggestions": self._build_suggestions(
                command_history=command_history,
                hard_cases=hard_cases,
                action_failures=action_failures,
                resolver_candidates=resolver_candidates,
                correction_pairs=correction_pairs,
                alias_candidates=alias_candidates,
            ),
        }

        return summary

    def _top_hard_cases(self, hard_cases: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        counter = Counter()
        examples: Dict[str, Dict[str, Any]] = {}

        for row in hard_cases:
            text = str(row.get("raw_text") or row.get("final_text") or "").strip()
            if not text:
                continue

            counter[text] += 1
            if text not in examples:
                examples[text] = {
                    "text": text,
                    "reason": row.get("reason") or "",
                    "meta": row.get("meta") or {},
                }

        result: List[Dict[str, Any]] = []
        for text, count in counter.most_common(limit):
            item = dict(examples[text])
            item["count"] = count
            result.append(item)
        return result

    def _top_repeat_like_hard_cases(self, hard_cases: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        counter = Counter()

        for row in hard_cases:
            text = str(row.get("raw_text") or row.get("final_text") or "").strip()
            if not text:
                continue
            if self._is_repeat_like_text(text):
                counter[text] += 1

        return [{"text": text, "count": count} for text, count in counter.most_common(limit)]

    def _group_similar_hard_cases(self, hard_cases: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
        text_counter = Counter(
            str(row.get("raw_text") or row.get("final_text") or "").strip()
            for row in hard_cases
            if str(row.get("raw_text") or row.get("final_text") or "").strip()
            and not self._is_repeat_like_text(str(row.get("raw_text") or row.get("final_text") or "").strip())
        )

        items = [{"text": text, "count": count, "compact": self._compact(text)} for text, count in text_counter.items()]
        items.sort(key=lambda x: (-x["count"], x["text"]))

        used: set[int] = set()
        groups: List[Dict[str, Any]] = []

        for i, base in enumerate(items):
            if i in used:
                continue

            cluster = [base]
            used.add(i)

            for j in range(i + 1, len(items)):
                if j in used:
                    continue

                other = items[j]
                ratio = SequenceMatcher(None, base["compact"], other["compact"]).ratio()
                contains = (
                    base["compact"]
                    and other["compact"]
                    and (base["compact"] in other["compact"] or other["compact"] in base["compact"])
                )

                if ratio >= 0.82 or contains:
                    cluster.append(other)
                    used.add(j)

            if len(cluster) < 2:
                continue

            groups.append(
                {
                    "count": sum(x["count"] for x in cluster),
                    "samples": [x["text"] for x in cluster[:5]],
                }
            )

        groups.sort(key=lambda x: x["count"], reverse=True)
        return groups[:limit]

    def _top_missing_slots(self, command_history: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        counter = Counter()
        examples: Dict[str, Dict[str, Any]] = {}

        for row in command_history:
            meta = row.get("meta") or {}
            intent = str(meta.get("intent") or "").upper()
            missing_slots = row.get("missing_slots") or []

            if not intent or not missing_slots:
                continue

            for slot_name in missing_slots:
                key = f"{intent}:{slot_name}"
                counter[key] += 1
                if key not in examples:
                    examples[key] = {
                        "intent": intent,
                        "slot": slot_name,
                        "example_text": row.get("raw_text") or row.get("final_text") or "",
                    }

        result: List[Dict[str, Any]] = []
        for key, count in counter.most_common(limit):
            item = dict(examples[key])
            item["count"] = count
            result.append(item)
        return result

    def _top_action_failures(self, action_failures: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        counter = Counter()
        examples: Dict[str, Dict[str, Any]] = {}

        for row in action_failures:
            meta = row.get("meta") or {}
            intent = str(meta.get("intent") or "").upper()
            error_type = str(row.get("error_type") or "").strip()
            key = f"{intent}:{error_type}"

            counter[key] += 1
            if key not in examples:
                examples[key] = {
                    "intent": intent,
                    "error_type": error_type,
                    "error": row.get("error") or "",
                    "example_text": row.get("raw_text") or row.get("final_text") or "",
                }

        result: List[Dict[str, Any]] = []
        for key, count in counter.most_common(limit):
            item = dict(examples[key])
            item["count"] = count
            result.append(item)
        return result

    def _top_resolver_candidates(self, resolver_candidates: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        counter = Counter()
        examples: Dict[str, Dict[str, Any]] = {}

        for row in resolver_candidates:
            meta = row.get("meta") or {}
            intent = str(meta.get("intent") or "").upper()
            missing_slots = tuple(row.get("missing_slots") or [])
            text = str(row.get("raw_text") or row.get("final_text") or "").strip()

            if not text:
                continue

            key = f"{intent}|{','.join(missing_slots)}|{text}"
            counter[key] += 1

            if key not in examples:
                examples[key] = {
                    "intent": intent,
                    "missing_slots": list(missing_slots),
                    "text": text,
                    "reason": row.get("reason") or "",
                }

        result: List[Dict[str, Any]] = []
        for key, count in counter.most_common(limit):
            item = dict(examples[key])
            item["count"] = count
            result.append(item)
        return result

    def _find_correction_pairs(self, command_history: List[Dict[str, Any]], limit: int | None = 10) -> List[Dict[str, Any]]:
        rows = sorted(
            command_history,
            key=lambda row: (self._parse_ts(row.get("ts")) or datetime.min),
        )

        counter = Counter()
        examples: Dict[str, Dict[str, Any]] = {}

        for i in range(len(rows) - 1):
            prev_row = rows[i]
            next_row = rows[i + 1]

            prev_ts = self._parse_ts(prev_row.get("ts"))
            next_ts = self._parse_ts(next_row.get("ts"))
            if prev_ts is None or next_ts is None:
                continue

            delta_sec = (next_ts - prev_ts).total_seconds()
            if delta_sec < 0 or delta_sec > 60:
                continue

            prev_accepted = bool(prev_row.get("accepted"))
            if prev_accepted:
                continue

            if not self._is_valid_corrected_row(next_row):
                continue

            prev_text = str(prev_row.get("raw_text") or prev_row.get("final_text") or "").strip()
            next_text = str(next_row.get("raw_text") or next_row.get("final_text") or "").strip()
            if not prev_text or not next_text or prev_text == next_text:
                continue

            if self._is_repeat_like_text(prev_text) or self._is_repeat_like_text(next_text):
                continue

            next_meta = next_row.get("meta") or {}
            next_intent = str(next_meta.get("intent") or "").upper()

            key = f"{prev_text}|{next_text}|{next_intent}"
            counter[key] += 1

            if key not in examples:
                examples[key] = {
                    "failed_text": prev_text,
                    "corrected_text": next_text,
                    "corrected_intent": next_intent,
                    "corrected_confidence": float(next_meta.get("confidence") or 0.0),
                    "corrected_slots": dict(next_meta.get("slots") or {}),
                    "delta_sec": round(delta_sec, 2),
                }

        result: List[Dict[str, Any]] = []
        for key, count in counter.most_common(limit):
            item = dict(examples[key])
            item["count"] = count
            result.append(item)
        return result

    def _extract_entity_tail(self, text: str, intent: str) -> str:
        t = " ".join((text or "").lower().split())

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

    def _build_alias_candidates(self, correction_pairs: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        allowed_intents = {"OPEN_APP", "CLOSE_APP", "OPEN_URL"}

        counter = Counter()
        examples: Dict[str, Dict[str, Any]] = {}

        for row in correction_pairs:
            intent = str(row.get("corrected_intent") or "").upper()
            if intent not in allowed_intents:
                continue

            failed_text = str(row.get("failed_text") or "").strip()
            corrected_text = str(row.get("corrected_text") or "").strip()
            corrected_slots = row.get("corrected_slots") or {}
            pair_count = int(row.get("count") or 1)

            wrong_entity = self._extract_entity_tail(failed_text, intent)
            correct_entity = self._extract_entity_tail(corrected_text, intent)

            if not wrong_entity or not correct_entity:
                continue
            if wrong_entity == correct_entity:
                continue

            if intent in {"OPEN_APP", "CLOSE_APP"} and not corrected_slots.get("app"):
                continue
            if intent == "OPEN_URL" and not corrected_slots.get("url"):
                continue

            key = f"{intent}|{wrong_entity}|{correct_entity}"
            counter[key] += pair_count

            if key not in examples:
                examples[key] = {
                    "intent": intent,
                    "from": wrong_entity,
                    "to": correct_entity,
                }

        result: List[Dict[str, Any]] = []
        for key, count in counter.most_common(limit):
            if count < 2:
                continue
            item = dict(examples[key])
            item["count"] = count
            result.append(item)
        return result

    def _build_suggestions(
        self,
        *,
        command_history: List[Dict[str, Any]],
        hard_cases: List[Dict[str, Any]],
        action_failures: List[Dict[str, Any]],
        resolver_candidates: List[Dict[str, Any]],
        correction_pairs: List[Dict[str, Any]],
        alias_candidates: List[Dict[str, Any]],
    ) -> List[str]:
        suggestions: List[str] = []

        repeat_counter = Counter(
            str(row.get("raw_text") or row.get("final_text") or "").strip()
            for row in hard_cases
            if self._is_repeat_like_text(str(row.get("raw_text") or row.get("final_text") or "").strip())
        )

        for text, count in repeat_counter.most_common(3):
            if count >= 2:
                suggestions.append(
                    f'Проверить repeat/history logic: фраза "{text}" {count} раз(а) попала в hard case.'
                )

        hard_case_counts = Counter(
            str(row.get("raw_text") or row.get("final_text") or "").strip()
            for row in hard_cases
            if str(row.get("raw_text") or row.get("final_text") or "").strip()
            and not self._is_repeat_like_text(str(row.get("raw_text") or row.get("final_text") or "").strip())
        )

        for text, count in hard_case_counts.most_common(5):
            if count >= 2:
                suggestions.append(
                    f'Добавить примеры или alias для фразы "{text}" — встретилась {count} раз(а) как hard case.'
                )

        missing_slot_counter = Counter()
        for row in command_history:
            meta = row.get("meta") or {}
            intent = str(meta.get("intent") or "").upper()
            for slot_name in row.get("missing_slots") or []:
                missing_slot_counter[(intent, slot_name)] += 1

        for (intent, slot_name), count in missing_slot_counter.most_common(5):
            if count >= 2:
                suggestions.append(
                    f'Усилить extractor/resolver для интента {intent}: часто отсутствует slot "{slot_name}" ({count} раз(а)).'
                )

        failure_counter = Counter()
        for row in action_failures:
            meta = row.get("meta") or {}
            intent = str(meta.get("intent") or "").upper()
            failure_counter[intent] += 1

        for intent, count in failure_counter.most_common(5):
            if intent and count >= 2:
                suggestions.append(
                    f'Проверить action-реализацию для {intent}: зафиксировано {count} ошибок выполнения.'
                )

        resolver_counter = Counter()
        for row in resolver_candidates:
            meta = row.get("meta") or {}
            intent = str(meta.get("intent") or "").upper()
            resolver_counter[intent] += 1

        for intent, count in resolver_counter.most_common(5):
            if intent and count >= 2:
                suggestions.append(
                    f'Добавить правила в EntityResolver для {intent}: накоплено {count} resolver candidate(s).'
                )

        for row in alias_candidates[:5]:
            suggestions.append(
                f'Кандидат на alias для {row.get("intent")}: "{row.get("from")}" → "{row.get("to")}" ({row.get("count")} раз(а)).'
            )

        for row in correction_pairs[:5]:
            suggestions.append(
                f'Похоже на correction pair: "{row.get("failed_text")}" → "{row.get("corrected_text")}" ({row.get("corrected_intent")}).'
            )

        return suggestions[:15]
