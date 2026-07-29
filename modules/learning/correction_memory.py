from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class CorrectionMemory:
    def __init__(self, path: str = "data/learning/correction_memory.jsonl") -> None:
        self._path = Path(path)

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _read_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []

        rows: List[Dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows

    def _write_all(self, rows: List[Dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _norm(self, text: str) -> str:
        return " ".join((text or "").lower().split()).strip()

    def _make_key(self, failed_text: str, corrected_text: str, corrected_intent: str) -> str:
        return " | ".join(
            [
                self._norm(failed_text),
                self._norm(corrected_text),
                str(corrected_intent or "").strip().upper(),
            ]
        )

    def upsert_candidate(
        self,
        *,
        failed_text: str,
        corrected_text: str,
        corrected_intent: str,
        corrected_confidence: float,
        corrected_slots: Dict[str, Any] | None = None,
        evidence_count: int = 1,
        source: str = "feedback_analyzer",
    ) -> Dict[str, Any]:
        rows = self._read_all()

        key = self._make_key(failed_text, corrected_text, corrected_intent)
        now = self._now()

        for row in rows:
            if str(row.get("key") or "") != key:
                continue

            row["seen_count"] = int(row.get("seen_count") or 0) + max(1, int(evidence_count or 1))
            row["last_seen_ts"] = now
            row["corrected_confidence"] = max(
                float(row.get("corrected_confidence") or 0.0),
                float(corrected_confidence or 0.0),
            )

            if corrected_slots:
                existing_slots = row.get("corrected_slots") or {}
                merged_slots = dict(existing_slots)
                merged_slots.update(corrected_slots)
                row["corrected_slots"] = merged_slots

            sources = list(row.get("sources") or [])
            if source not in sources:
                sources.append(source)
            row["sources"] = sources

            self._write_all(rows)
            return row

        new_row = {
            "key": key,
            "created_ts": now,
            "last_seen_ts": now,
            "seen_count": max(1, int(evidence_count or 1)),
            "failed_text": failed_text,
            "corrected_text": corrected_text,
            "corrected_intent": str(corrected_intent or "").strip().upper(),
            "corrected_confidence": float(corrected_confidence or 0.0),
            "corrected_slots": dict(corrected_slots or {}),
            "sources": [source],
            "status": "candidate",
        }

        rows.append(new_row)
        self._write_all(rows)
        return new_row