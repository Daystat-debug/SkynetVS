# modules/error_log.py
from __future__ import annotations

import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any


_ERROR_LOG_PATH = os.getenv("ERROR_LOG_PATH", "data/logs/errors.jsonl").strip()


def log_error(source: str, message: str, **extra: Any) -> None:
    try:
        path = Path(_ERROR_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)

        row = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "message": message,
            **extra,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def log_exception(source: str, exc: Exception, **extra: Any) -> None:
    log_error(
        source=source,
        message=str(exc),
        error_type=type(exc).__name__,
        traceback=traceback.format_exc(),
        **extra,
    )
