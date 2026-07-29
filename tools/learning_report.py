from __future__ import annotations

import json

from modules.learning.feedback_analyzer import FeedbackAnalyzer


def _print_block(title: str, rows: list[dict]) -> None:
    print(f"\n=== {title} ===")
    if not rows:
        print("нет данных")
        return

    for i, row in enumerate(rows, start=1):
        print(f"{i}. {json.dumps(row, ensure_ascii=False)}")


def main() -> None:
    analyzer = FeedbackAnalyzer()
    report = analyzer.analyze()

    print("=== TOTALS ===")
    print(json.dumps(report.get("totals") or {}, ensure_ascii=False, indent=2))

    _print_block("TOP HARD CASES", report.get("top_hard_cases") or [])
    _print_block("REPEAT-LIKE HARD CASES", report.get("repeat_like_hard_cases") or [])
    _print_block("SIMILAR HARD CASE GROUPS", report.get("similar_hard_case_groups") or [])
    _print_block("TOP MISSING SLOTS", report.get("top_missing_slots") or [])
    _print_block("TOP ACTION FAILURES", report.get("top_action_failures") or [])
    _print_block("TOP RESOLVER CANDIDATES", report.get("top_resolver_candidates") or [])
    _print_block("CORRECTION PAIRS", report.get("correction_pairs") or [])
    _print_block("ALIAS CANDIDATES", report.get("alias_candidates") or [])

    print("\n=== SUGGESTIONS ===")
    suggestions = report.get("suggestions") or []
    if not suggestions:
        print("нет предложений")
    else:
        for i, s in enumerate(suggestions, start=1):
            print(f"{i}. {s}")


if __name__ == "__main__":
    main()