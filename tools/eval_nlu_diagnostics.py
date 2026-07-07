from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from tools.eval_nlu import TEST_CASES, check_case


def main() -> int:
    results = [check_case(case) for case in TEST_CASES]

    fail_count = 0
    warning_count = 0

    group_stats: Dict[str, Dict[str, int]] = {}

    print("=== NLU DIAGNOSTICS REPORT ===")

    current_group: str | None = None

    for idx, result in enumerate(results, start=1):
        group = str(result["group"])

        if group != current_group:
            current_group = group
            print()
            print(f"--- GROUP: {group} ---")

        stats = group_stats.setdefault(
            group,
            {
                "total": 0,
                "hard_fail_count": 0,
                "warning_count": 0,
            },
        )
        stats["total"] += 1

        if result["hard_fail_reasons"]:
            fail_count += 1
            stats["hard_fail_count"] += 1

        if result["warnings"]:
            warning_count += len(result["warnings"])
            stats["warning_count"] += len(result["warnings"])

        print()
        print(f"{idx}. {result['text']}")
        print(
            json.dumps(
                {
                    "group": result["group"],
                    "expected_intent": result["expected_intent"],
                    "forbidden_intents": result["forbidden_intents"],
                    "actual_intent": result["actual_intent"],
                    "confidence": round(float(result["confidence"]), 4),
                    "expected_slots": result["expected_slots"],
                    "actual_slots": result["actual_slots"],
                    "rule": result["rule"],
                    "top_candidates": result["top_candidates"],
                    "hard_fail_reasons": result["hard_fail_reasons"],
                    "warnings": result["warnings"],
                },
                ensure_ascii=False,
            )
        )

    print()
    print("=== GROUP SUMMARY ===")
    print(json.dumps(group_stats, ensure_ascii=False, indent=2))

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "total_cases": len(results),
                "hard_fail_count": fail_count,
                "warning_count": warning_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())