from __future__ import annotations

import threading
import time

from dataclasses import dataclass
from typing import Callable


OUTCOME_SUCCESS = "success"
OUTCOME_FAILURE = "failure"


@dataclass(frozen=True)
class OperationTelemetrySnapshot:
    last_outcome: str
    last_attempt_at: float | None
    last_success_at: float | None
    last_failure_at: float | None
    last_duration_ms: int | None
    last_error: str
    consecutive_failures: int

    @property
    def has_attempt(self) -> bool:
        return self.last_attempt_at is not None


class OperationTelemetry:
    def __init__(self, *, time_func: Callable[[], float] = time.time):
        self._time_func = time_func
        self._lock = threading.RLock()

        self._last_outcome = ""
        self._last_attempt_at: float | None = None
        self._last_success_at: float | None = None
        self._last_failure_at: float | None = None
        self._last_duration_ms: int | None = None
        self._last_error = ""
        self._consecutive_failures = 0

    def _normalize_duration_ms(self, value: int | float | None) -> int | None:
        if value is None:
            return None

        try:
            return max(0, int(round(float(value))))
        except (TypeError, ValueError):
            return None

    def _error_text(self, error: BaseException | str) -> str:
        if isinstance(error, BaseException):
            text = str(error).strip()
            return text or type(error).__name__

        return str(error or "").strip() or "Unknown operation failure"

    def record_success(self, *, duration_ms: int | float | None = None) -> None:
        now = float(self._time_func())

        with self._lock:
            self._last_outcome = OUTCOME_SUCCESS
            self._last_attempt_at = now
            self._last_success_at = now
            self._last_duration_ms = self._normalize_duration_ms(duration_ms)
            self._last_error = ""
            self._consecutive_failures = 0

    def record_failure(
        self,
        error: BaseException | str,
        *,
        duration_ms: int | float | None = None,
    ) -> None:
        now = float(self._time_func())

        with self._lock:
            self._last_outcome = OUTCOME_FAILURE
            self._last_attempt_at = now
            self._last_failure_at = now
            self._last_duration_ms = self._normalize_duration_ms(duration_ms)
            self._last_error = self._error_text(error)
            self._consecutive_failures += 1

    def snapshot(self) -> OperationTelemetrySnapshot:
        with self._lock:
            return OperationTelemetrySnapshot(
                last_outcome=self._last_outcome,
                last_attempt_at=self._last_attempt_at,
                last_success_at=self._last_success_at,
                last_failure_at=self._last_failure_at,
                last_duration_ms=self._last_duration_ms,
                last_error=self._last_error,
                consecutive_failures=self._consecutive_failures,
            )