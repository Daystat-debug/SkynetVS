# modules/logger.py
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def _now_iso() -> str:
    # локальное время, читаемо в логах
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class LoggerConfig:
    enabled: bool = True
    log_path: Path = Path("data/logs/runtime.jsonl")
    inbox_path: Path = Path("data/inbox_unlabeled.jsonl")


class JsonlLogger:
    """
    Простой JSONL логгер (append-only).
    - runtime.jsonl: всё подряд (STT/NLU/решения)
    - inbox_unlabeled.jsonl: фразы, которые NLU не поняла/не уверена
    """

    def __init__(self, cfg: LoggerConfig):
        self.cfg = cfg
        self._lock = threading.Lock()

    def _append(self, path: Path, obj: Dict[str, Any]) -> None:
        if not self.cfg.enabled:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(obj, ensure_ascii=False)
        with self._lock:
            path.open("a", encoding="utf-8").write(line + "\n")

    def event(self, kind: str, payload: Dict[str, Any]) -> None:
        self._append(
            self.cfg.log_path,
            {"ts": _now_iso(), "kind": kind, **payload},
        )

    def inbox(self, text: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._append(
            self.cfg.inbox_path,
            {
                "ts": _now_iso(),
                "text": text,
                "meta": meta or {},
            },
        )