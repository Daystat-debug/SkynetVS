from __future__ import annotations

from modules.learning.correction_memory import CorrectionMemory
from modules.learning.feedback_analyzer import FeedbackAnalyzer


def main() -> None:
    analyzer = FeedbackAnalyzer()
    # A reporting top-ten limit is not a complete cumulative evidence snapshot.
    report = analyzer.analyze(correction_limit=None)

    correction_pairs = report.get("correction_pairs") or []
    memory = CorrectionMemory()

    stats = memory.sync_cumulative_candidates(correction_pairs, source="feedback_analyzer_v2")

    print("[OK] correction memory checked: data/learning/correction_memory.jsonl")
    print(f"[OK] normalized correction pairs: {stats['processed']}")
    print(f"[OK] created={stats['created']}; increased={stats['increased']}; "
          f"baselined={stats['baselined']}; unchanged={stats['unchanged']}; "
          f"new_evidence={stats['new_evidence']}; written={stats['written']}")
    if stats["baselined"]:
        print("[INFO] Legacy counts preserved; current totals recorded as a baseline.")
    if stats["lower_totals"]:
        print(f"[INFO] Lower cumulative totals retained: {stats['lower_totals']}; "
              "history truncation or replacement requires a separate review.")


if __name__ == "__main__":
    main()
