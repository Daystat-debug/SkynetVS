from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from modules.promotion_engine import build_report, read_jsonl


CORRECTION_MEMORY_PATH = Path("data/learning/correction_memory.jsonl")


def print_block(title: str, rows: List[Dict[str, Any]]) -> None:
    print(f"\n=== {title} ===")
    if not rows:
        print("нет данных")
        return

    for i, row in enumerate(rows, start=1):
        print(f"{i}. {json.dumps(row, ensure_ascii=False)}")


def main() -> None:
    rows = read_jsonl(CORRECTION_MEMORY_PATH)
    report = build_report(rows)

    print("=== TOTALS ===")
    print(json.dumps(report["totals"], ensure_ascii=False, indent=2))

    print_block("INTENT EXAMPLES", report["intent_examples"])
    print_block("ENTITY ALIASES", report["entity_aliases"])
    print_block("PHRASE CORRECTIONS", report["phrase_corrections"])
    print_block("REJECTS", report["rejects"])


if __name__ == "__main__":
    main()