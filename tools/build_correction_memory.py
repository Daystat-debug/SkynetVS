from __future__ import annotations

from modules.correction_memory import CorrectionMemory
from modules.feedback_analyzer import FeedbackAnalyzer


def main() -> None:
    analyzer = FeedbackAnalyzer()
    report = analyzer.analyze()

    correction_pairs = report.get("correction_pairs") or []
    memory = CorrectionMemory()

    added = 0

    for row in correction_pairs:
        failed_text = str(row.get("failed_text") or "").strip()
        corrected_text = str(row.get("corrected_text") or "").strip()
        corrected_intent = str(row.get("corrected_intent") or "").strip().upper()

        if not failed_text or not corrected_text or not corrected_intent:
            continue

        memory.upsert_candidate(
            failed_text=failed_text,
            corrected_text=corrected_text,
            corrected_intent=corrected_intent,
            corrected_confidence=float(row.get("corrected_confidence") or 0.0),
            corrected_slots=row.get("corrected_slots") or {},
            evidence_count=int(row.get("count") or 1),
            source="feedback_analyzer_v2",
        )
        added += 1

    print("[OK] correction memory updated: data/learning/correction_memory.jsonl")
    print(f"[OK] processed correction pairs: {added}")


if __name__ == "__main__":
    main()