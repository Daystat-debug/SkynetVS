from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from modules.promotion_engine import build_report, read_jsonl, norm


CORRECTION_MEMORY_PATH = Path("data/learning/correction_memory.jsonl")
INTENTS_PATH = Path("data/intents.json")
INBOX_PATH = Path("data/inbox_unlabeled.jsonl")
ALIAS_SUGGESTIONS_PATH = Path("data/learning/alias_suggestions.jsonl")
PHRASE_CORR_SUGGESTIONS_PATH = Path("data/learning/phrase_correction_suggestions.jsonl")


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_intents() -> Dict[str, Any]:
    if not INTENTS_PATH.exists():
        return {"intents": []}
    return json.loads(INTENTS_PATH.read_text(encoding="utf-8"))


def existing_intent_examples() -> Set[Tuple[str, str]]:
    data = load_intents()
    result: Set[Tuple[str, str]] = set()

    for item in data.get("intents") or []:
        intent = str(item.get("intent") or "").strip().upper()
        for ex in item.get("examples") or []:
            text = norm(str(ex or ""))
            if text and intent:
                result.add((text, intent))

    return result


def existing_inbox_keys(rows: List[Dict[str, Any]]) -> Set[Tuple[str, str]]:
    result: Set[Tuple[str, str]] = set()
    for row in rows:
        text = norm(str(row.get("text") or ""))
        intent = str((row.get("meta") or {}).get("intent") or "").strip().upper()
        if text:
            result.add((text, intent))
    return result


def main() -> None:
    source_rows = read_jsonl(CORRECTION_MEMORY_PATH)
    report = build_report(source_rows)

    inbox = read_jsonl(INBOX_PATH)
    inbox_keys = existing_inbox_keys(inbox)
    intent_keys = existing_intent_examples()

    added_inbox = 0
    added_alias = 0
    added_phrase = 0

    # 1. intent_examples -> inbox
    for row in report["intent_examples"]:
        text = norm(str(row.get("corrected_text") or ""))
        intent = str(row.get("intent") or "").strip().upper()
        if not text or not intent:
            continue

        key = (text, intent)
        if key in inbox_keys or key in intent_keys:
            continue

        inbox.append(
            {
                "text": text,
                "meta": {
                    "intent": intent,
                    "confidence": row.get("corrected_confidence"),
                    "slots": row.get("corrected_slots") or {},
                    "say": "",
                },
            }
        )
        inbox_keys.add(key)
        added_inbox += 1

    # 2. entity_aliases -> alias suggestions
    alias_rows_existing = read_jsonl(ALIAS_SUGGESTIONS_PATH)
    alias_keys = {
        (
            str(r.get("intent") or "").strip().upper(),
            norm(str(r.get("from") or "")),
            norm(str(r.get("to") or "")),
        )
        for r in alias_rows_existing
    }

    for row in report["entity_aliases"]:
        key = (
            str(row.get("intent") or "").strip().upper(),
            norm(str(row.get("from") or "")),
            norm(str(row.get("to") or "")),
        )
        if not key[0] or not key[1] or not key[2]:
            continue
        if key in alias_keys:
            continue

        alias_rows_existing.append(
            {
                "intent": key[0],
                "from": key[1],
                "to": key[2],
                "seen_count": int(row.get("seen_count") or 0),
                "corrected_confidence": float(row.get("corrected_confidence") or 0.0),
                "reason": row.get("reason") or "",
            }
        )
        alias_keys.add(key)
        added_alias += 1

    # 3. phrase_corrections -> phrase correction suggestions
    phrase_rows_existing = read_jsonl(PHRASE_CORR_SUGGESTIONS_PATH)
    phrase_keys = {
        (
            norm(str(r.get("failed_text") or "")),
            norm(str(r.get("corrected_text") or "")),
            str(r.get("intent") or "").strip().upper(),
        )
        for r in phrase_rows_existing
    }

    for row in report["phrase_corrections"]:
        key = (
            norm(str(row.get("failed_text") or "")),
            norm(str(row.get("corrected_text") or "")),
            str(row.get("intent") or "").strip().upper(),
        )
        if not key[0] or not key[1] or not key[2]:
            continue
        if key in phrase_keys:
            continue

        phrase_rows_existing.append(
            {
                "failed_text": key[0],
                "corrected_text": key[1],
                "intent": key[2],
                "seen_count": int(row.get("seen_count") or 0),
                "corrected_confidence": float(row.get("corrected_confidence") or 0.0),
                "reason": row.get("reason") or "",
            }
        )
        phrase_keys.add(key)
        added_phrase += 1

    write_jsonl(INBOX_PATH, inbox)
    write_jsonl(ALIAS_SUGGESTIONS_PATH, alias_rows_existing)
    write_jsonl(PHRASE_CORR_SUGGESTIONS_PATH, phrase_rows_existing)

    print(f"[OK] inbox additions: {added_inbox}")
    print(f"[OK] alias suggestions additions: {added_alias}")
    print(f"[OK] phrase correction suggestions additions: {added_phrase}")
    print("[OK] written:")
    print(f"  - {INBOX_PATH}")
    print(f"  - {ALIAS_SUGGESTIONS_PATH}")
    print(f"  - {PHRASE_CORR_SUGGESTIONS_PATH}")


if __name__ == "__main__":
    main()