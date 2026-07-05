from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


LEARNING_HARD_CASES = Path("data/learning/nlu_hard_cases.jsonl")
LEARNING_RESOLVER_CANDIDATES = Path("data/learning/resolver_candidates.jsonl")
INBOX_PATH = Path("data/inbox_unlabeled.jsonl")


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


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split()).strip()


def extract_inbox_entry(row: Dict[str, Any]) -> Dict[str, Any] | None:
    text = str(row.get("raw_text") or row.get("final_text") or "").strip()
    if not text:
        return None

    meta = row.get("meta") or {}
    return {
        "text": text,
        "meta": {
            "intent": meta.get("intent"),
            "confidence": meta.get("confidence"),
            "slots": meta.get("slots") or {},
            "say": meta.get("say") or "",
        },
    }


def main() -> None:
    hard_cases = read_jsonl(LEARNING_HARD_CASES)
    resolver_candidates = read_jsonl(LEARNING_RESOLVER_CANDIDATES)
    inbox = read_jsonl(INBOX_PATH)

    existing_keys = set()
    for row in inbox:
        text = normalize_text(str(row.get("text") or ""))
        intent = str((row.get("meta") or {}).get("intent") or "")
        if text:
            existing_keys.add((text, intent))

    added = 0

    for source_rows in (hard_cases, resolver_candidates):
        for row in source_rows:
            entry = extract_inbox_entry(row)
            if not entry:
                continue

            text = normalize_text(entry["text"])
            intent = str((entry.get("meta") or {}).get("intent") or "")
            key = (text, intent)

            if key in existing_keys:
                continue

            inbox.append(entry)
            existing_keys.add(key)
            added += 1

    write_jsonl(INBOX_PATH, inbox)

    print(f"[OK] inbox updated: {INBOX_PATH}")
    print(f"[OK] added rows: {added}")
    print("Дальше можно запускать: python tools/label_inbox.py")


if __name__ == "__main__":
    main()