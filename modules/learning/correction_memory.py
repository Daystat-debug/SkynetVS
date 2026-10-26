from __future__ import annotations

import json
import math
import os
import stat
import tempfile
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

    @staticmethod
    def _strict_object(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate field in correction memory")
            result[key] = value
        return result

    @staticmethod
    def _invalid_constant(value: str) -> None:
        raise ValueError("Non-finite JSON value in correction memory: " + value)

    def _read_snapshot_rows(self) -> List[Dict[str, Any]]:
        """Refuse malformed state instead of silently dropping it on rewrite."""
        if not self._path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        keys: set[str] = set()
        with self._path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line, object_pairs_hook=self._strict_object,
                                     parse_constant=self._invalid_constant)
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Invalid correction memory at line {line_number}") from exc
                if not isinstance(row, dict) or not isinstance(row.get("key"), str) or not row["key"]:
                    raise ValueError(f"Invalid correction memory row at line {line_number}")
                if row["key"] in keys:
                    raise ValueError("Duplicate correction memory key")
                keys.add(row["key"])
                count = row.get("seen_count", 0)
                if type(count) is not int or count < 0:
                    raise ValueError("Invalid correction memory seen_count")
                confidence = row.get("corrected_confidence", 0.0)
                if type(confidence) not in (int, float) or not math.isfinite(confidence):
                    raise ValueError("Invalid correction memory confidence")
                if row.get("corrected_slots") is not None and not isinstance(row["corrected_slots"], dict):
                    raise ValueError("Invalid correction memory slots")
                if row.get("sources") is not None and (
                        not isinstance(row["sources"], list) or
                        any(not isinstance(source, str) for source in row["sources"])):
                    raise ValueError("Invalid correction memory sources")
                states = row.get("cumulative_evidence", {})
                if not isinstance(states, dict):
                    raise ValueError("Invalid cumulative evidence state")
                for source, state in states.items():
                    if (not isinstance(source, str) or not source.strip() or not isinstance(state, dict)
                            or type(state.get("version")) is not int or state["version"] != 1
                            or type(state.get("observed_count")) is not int or state["observed_count"] < 0
                            or type(state.get("legacy_baseline")) is not bool):
                        raise ValueError("Invalid cumulative evidence checkpoint")
                rows.append(row)
        return rows

    def _write_snapshot(self, rows: List[Dict[str, Any]]) -> None:
        """Serialize before touching disk, then replace one complete JSONL file."""
        encoded = "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
                          for row in rows).encode("utf-8")
        # Resolve a configured file symlink so replacement keeps its target semantics.
        target = self._path.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        old_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else None
        descriptor, temporary_name = tempfile.mkstemp(prefix="." + target.name + ".", suffix=".tmp",
                                                      dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            if old_mode is not None:
                os.chmod(temporary, old_mode)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()

    def sync_cumulative_candidates(
        self,
        candidates: List[Dict[str, Any]],
        *,
        source: str = "feedback_analyzer_v2",
    ) -> Dict[str, Any]:
        """Merge a complete cumulative snapshot without replaying old evidence.

        Counts are high-water marks per source and normalized candidate, not event
        IDs. A smaller/replaced history cannot establish new independent evidence;
        its total never lowers a checkpoint. Legacy counts may already be inflated:
        first adoption records a baseline without guessing a corrected seen_count.
        Only positive growth changes candidate metadata or observation time. This
        method does not serialize concurrent writers; callers must run it serially.
        """
        if not isinstance(source, str) or not source.strip():
            raise ValueError("A cumulative evidence source is required")
        grouped: Dict[str, Dict[str, Any]] = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("Correction candidates must be objects")
            failed = str(candidate.get("failed_text") or "").strip()
            corrected = str(candidate.get("corrected_text") or "").strip()
            intent = str(candidate.get("corrected_intent") or "").strip().upper()
            if not failed or not corrected or not intent:
                continue
            count = candidate.get("count", 1)
            confidence = candidate.get("corrected_confidence", 0.0)
            slots = candidate.get("corrected_slots")
            if slots is None:
                slots = {}
            if type(count) is not int or count < 1:
                raise ValueError("Cumulative evidence counts must be positive integers")
            if type(confidence) not in (int, float) or not math.isfinite(confidence):
                raise ValueError("Correction confidence must be finite")
            if not isinstance(slots, dict):
                raise ValueError("Correction slots must be an object")
            key = self._make_key(failed, corrected, intent)
            if key not in grouped:
                grouped[key] = {
                    "key": key, "failed_text": failed, "corrected_text": corrected,
                    "corrected_intent": intent, "corrected_confidence": float(confidence),
                    "corrected_slots": dict(slots), "count": count,
                }
            else:
                group = grouped[key]
                group["count"] += count
                group["corrected_confidence"] = max(group["corrected_confidence"], float(confidence))
                group["corrected_slots"].update(slots)

        rows = self._read_snapshot_rows()
        existing = {row["key"]: row for row in rows}
        stats: Dict[str, Any] = {
            "processed": len(grouped), "created": 0, "baselined": 0, "increased": 0,
            "unchanged": 0, "lower_totals": 0, "new_evidence": 0, "written": False,
        }
        for key, candidate in grouped.items():
            count = candidate["count"]
            if key not in existing:
                now = self._now()
                row = {
                    "key": key, "created_ts": now, "last_seen_ts": now, "seen_count": count,
                    **{name: candidate[name] for name in (
                        "failed_text", "corrected_text", "corrected_intent",
                        "corrected_confidence", "corrected_slots")},
                    "sources": [source], "status": "candidate",
                    "cumulative_evidence": {
                        source: {"version": 1, "observed_count": count, "legacy_baseline": False}},
                }
                rows.append(row)
                existing[key] = row
                stats["created"] += 1
                stats["new_evidence"] += count
                continue

            row = existing[key]
            states = row.get("cumulative_evidence", {})
            if source not in states:
                # Existing counts have unknown provenance. Adopt the current total,
                # preserving all old business fields, timestamps and decisions.
                states = dict(states)
                states[source] = {"version": 1, "observed_count": count, "legacy_baseline": True}
                row["cumulative_evidence"] = states
                stats["baselined"] += 1
                continue
            previous = states[source]["observed_count"]
            if count <= previous:
                stats["unchanged"] += 1
                stats["lower_totals"] += int(count < previous)
                continue

            delta = count - previous
            row["seen_count"] = row.get("seen_count", 0) + delta
            row["last_seen_ts"] = self._now()
            row["corrected_confidence"] = max(row.get("corrected_confidence", 0.0),
                                              candidate["corrected_confidence"])
            slots = dict(row.get("corrected_slots") or {})
            slots.update(candidate["corrected_slots"])
            row["corrected_slots"] = slots
            sources = list(row.get("sources") or [])
            if source not in sources:
                sources.append(source)
            row["sources"] = sources
            states[source]["observed_count"] = count
            stats["increased"] += 1
            stats["new_evidence"] += delta

        if stats["created"] or stats["baselined"] or stats["increased"]:
            self._write_snapshot(rows)
            stats["written"] = True
        return stats

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
