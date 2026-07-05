# modules/dialog_state.py

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, Optional


@dataclass
class DialogState:
    """
    Минимальный контекст диалога:
    - последнее "полезное" действие (meta с intent)
    """
    last_meta: Optional[Dict[str, Any]] = None
    last_intent: Optional[str] = None
    last_ts: float = field(default_factory=time.time)

    def remember(self, meta: Dict[str, Any]) -> None:
        intent = (meta.get("intent") or "").upper()
        if not intent:
            return
        # сохраняем только то, что реально можно повторять
        self.last_meta = dict(meta)
        self.last_intent = intent
        self.last_ts = time.time()

    def get_last(self, within_sec: float) -> Optional[Dict[str, Any]]:
        """
        Возвращает последнее сохранённое meta, если оно свежее within_sec.
        within_sec <= 0 -> всегда возвращаем, если есть.
        """
        if not self.last_meta:
            return None
        if within_sec <= 0:
            return self.last_meta
        if (time.time() - float(self.last_ts or 0.0)) <= within_sec:
            return self.last_meta
        return None