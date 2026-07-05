from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class LearningMemory:
    def __init__(self, base_dir: str = "data/learning") -> None:
        self._base_dir = Path(base_dir)

        self._command_history_path = self._base_dir / "command_history.jsonl"
        self._nlu_hard_cases_path = self._base_dir / "nlu_hard_cases.jsonl"
        self._action_failures_path = self._base_dir / "action_failures.jsonl"
        self._resolver_candidates_path = self._base_dir / "resolver_candidates.jsonl"

    def _append_jsonl(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            **payload,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _meta_snapshot(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "intent": meta.get("intent"),
            "confidence": float(meta.get("confidence") or 0.0),
            "slots": dict(meta.get("slots") or {}),
            "say": meta.get("say") or "",
            "_text": meta.get("_text") or "",
        }

    def log_command(
        self,
        *,
        raw_text: str,
        final_text: str,
        meta: Dict[str, Any],
        mode: str,
        accepted: bool,
        immediate_label: str,
        missing_slots: List[str] | None = None,
    ) -> None:
        self._append_jsonl(
            self._command_history_path,
            {
                "raw_text": raw_text,
                "final_text": final_text,
                "mode": mode,
                "accepted": bool(accepted),
                "immediate_label": immediate_label,
                "missing_slots": list(missing_slots or []),
                "meta": self._meta_snapshot(meta),
            },
        )

    def log_nlu_hard_case(
        self,
        *,
        raw_text: str,
        final_text: str,
        meta: Dict[str, Any],
        mode: str,
        reason: str,
    ) -> None:
        self._append_jsonl(
            self._nlu_hard_cases_path,
            {
                "raw_text": raw_text,
                "final_text": final_text,
                "mode": mode,
                "reason": reason,
                "meta": self._meta_snapshot(meta),
            },
        )

    def log_action_failure(
        self,
        *,
        raw_text: str,
        final_text: str,
        meta: Dict[str, Any],
        mode: str,
        error: Exception,
    ) -> None:
        self._append_jsonl(
            self._action_failures_path,
            {
                "raw_text": raw_text,
                "final_text": final_text,
                "mode": mode,
                "error_type": type(error).__name__,
                "error": str(error),
                "meta": self._meta_snapshot(meta),
            },
        )

    def log_resolver_candidate(
        self,
        *,
        raw_text: str,
        final_text: str,
        meta: Dict[str, Any],
        mode: str,
        missing_slots: List[str],
        reason: str,
    ) -> None:
        self._append_jsonl(
            self._resolver_candidates_path,
            {
                "raw_text": raw_text,
                "final_text": final_text,
                "mode": mode,
                "reason": reason,
                "missing_slots": list(missing_slots),
                "meta": self._meta_snapshot(meta),
            },
        )