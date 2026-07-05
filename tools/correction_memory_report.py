from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


CORRECTION_MEMORY_PATH = Path("data/learning/correction_memory.jsonl")


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


def promotion_candidates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    for row in rows:
        intent = str(row.get("corrected_intent") or "").upper()
        seen_count = int(row.get("seen_count") or 0)
        conf = float(row.get("corrected_confidence") or 0.0)
        slots = row.get("corrected_slots") or {}

        if not intent:
            continue
        if seen_count < 2:
            continue
        if conf < 0.45:
            continue

        if intent in {"OPEN_APP", "CLOSE_APP"} and not slots.get("app"):
            continue
        if intent == "OPEN_URL" and not slots.get("url"):
            continue

        candidates.append(
            {
                "intent": intent,
                "failed_text": row.get("failed_text") or "",
                "corrected_text": row.get("corrected_text") or "",
                "seen_count": seen_count,
                "corrected_confidence": conf,
                "corrected_slots": slots,
                "status": row.get("status") or "candidate",
            }
        )

    candidates.sort(
        key=lambda x: (
            -int(x.get("seen_count") or 0),
            -float(x.get("corrected_confidence") or 0.0),
            str(x.get("intent") or ""),
        )
    )
    return candidates


def print_block(title: str, rows: List[Dict[str, Any]]) -> None:
    print(f"\n=== {title} ===")
    if not rows:
        print("нет данных")
        return

    for i, row in enumerate(rows, start=1):
        print(f"{i}. {json.dumps(row, ensure_ascii=False)}")


def main() -> None:
    rows = read_jsonl(CORRECTION_MEMORY_PATH)
    rows.sort(
        key=lambda x: (
            -int(x.get("seen_count") or 0),
            -float(x.get("corrected_confidence") or 0.0),
            str(x.get("corrected_intent") or ""),
        )
    )

    print("=== TOTALS ===")
    print(
        json.dumps(
            {
                "correction_memory_rows": len(rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    print_block("ALL CORRECTION MEMORY", rows[:20])
    print_block("PROMOTION CANDIDATES", promotion_candidates(rows))


if __name__ == "__main__":
    main()