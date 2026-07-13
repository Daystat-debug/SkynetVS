from __future__ import annotations

import math
import threading
import time

from dataclasses import dataclass
from typing import Callable, Protocol


MIN_TIMER_DURATION_SEC = 1
MAX_TIMER_DURATION_SEC = 24 * 60 * 60


class TimerHandle(Protocol):
    daemon: bool

    def start(self) -> None:
        ...

    def cancel(self) -> None:
        ...


ClockFunc = Callable[[], float]
TimerFactory = Callable[
    [float, Callable[[], None]],
    TimerHandle,
]
TimerFiredCallback = Callable[
    ["TimerFiredEvent"],
    None,
]


@dataclass(frozen=True)
class TimerSnapshot:
    active: bool
    token: int
    duration_seconds: int
    remaining_seconds: int
    started_at: float | None
    deadline: float | None


@dataclass(frozen=True)
class TimerStartResult:
    replaced: bool
    snapshot: TimerSnapshot


@dataclass(frozen=True)
class TimerCancelResult:
    cancelled: bool
    previous_snapshot: TimerSnapshot


@dataclass(frozen=True)
class TimerFiredEvent:
    token: int
    duration_seconds: int
    started_at: float
    deadline: float
    fired_at: float


def _default_timer_factory(
    delay_seconds: float,
    callback: Callable[[], None],
) -> TimerHandle:
    return threading.Timer(
        delay_seconds,
        callback,
    )


class TimerService:
    """
    Потокобезопасный сервис одного активного таймера.

    Не зависит от:
      - main.py;
      - event queue;
      - TTS;
      - NLU;
      - Actions.

    При завершении вызывает переданный callback.
    """

    def __init__(
        self,
        *,
        on_fired: TimerFiredCallback,
        clock: ClockFunc = time.monotonic,
        timer_factory: TimerFactory = (
            _default_timer_factory
        ),
    ) -> None:
        self._on_fired = on_fired
        self._clock = clock
        self._timer_factory = timer_factory

        self._lock = threading.RLock()
        self._timer: TimerHandle | None = None

        self._token = 0
        self._active = False
        self._duration_seconds = 0
        self._started_at: float | None = None
        self._deadline: float | None = None

    def _snapshot_locked(
        self,
        *,
        now: float | None = None,
    ) -> TimerSnapshot:
        current_time = (
            self._clock()
            if now is None
            else float(now)
        )

        remaining_seconds = 0

        if (
            self._active
            and self._deadline is not None
        ):
            remaining_raw = max(
                0.0,
                self._deadline - current_time,
            )
            remaining_seconds = int(
                math.ceil(remaining_raw)
            )

        active = (
            self._active
            and remaining_seconds > 0
        )

        return TimerSnapshot(
            active=active,
            token=self._token,
            duration_seconds=(
                self._duration_seconds
                if self._active
                else 0
            ),
            remaining_seconds=remaining_seconds,
            started_at=(
                self._started_at
                if self._active
                else None
            ),
            deadline=(
                self._deadline
                if self._active
                else None
            ),
        )

    def status(self) -> TimerSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def start(
        self,
        duration_seconds: int,
    ) -> TimerStartResult:
        if isinstance(duration_seconds, bool):
            raise ValueError(
                "duration_seconds must be an integer"
            )

        try:
            duration = int(duration_seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "duration_seconds must be an integer"
            ) from exc

        if duration < MIN_TIMER_DURATION_SEC:
            raise ValueError(
                "timer duration is too short"
            )

        if duration > MAX_TIMER_DURATION_SEC:
            raise ValueError(
                "timer duration is too long"
            )

        with self._lock:
            previous_timer = self._timer
            replaced = self._active

            # Новый generation-token делает callback
            # предыдущего таймера неактуальным.
            self._token += 1
            token = self._token

            started_at = self._clock()
            deadline = started_at + duration

            timer = self._timer_factory(
                float(duration),
                lambda: self._fire(token),
            )

            try:
                timer.daemon = True
            except Exception:
                pass

            self._timer = timer
            self._active = True
            self._duration_seconds = duration
            self._started_at = started_at
            self._deadline = deadline

            snapshot = self._snapshot_locked(
                now=started_at
            )

            if previous_timer is not None:
                try:
                    previous_timer.cancel()
                except Exception:
                    pass

            try:
                timer.start()
            except Exception:
                # Не оставляем ложное активное состояние,
                # если системный timer не запустился.
                self._timer = None
                self._active = False
                self._duration_seconds = 0
                self._started_at = None
                self._deadline = None
                raise

            return TimerStartResult(
                replaced=replaced,
                snapshot=snapshot,
            )

    def cancel(self) -> TimerCancelResult:
        with self._lock:
            previous_snapshot = (
                self._snapshot_locked()
            )

            timer = self._timer
            cancelled = self._active

            # Инвалидируем callback текущего timer.
            self._token += 1

            self._timer = None
            self._active = False
            self._duration_seconds = 0
            self._started_at = None
            self._deadline = None

            if timer is not None:
                try:
                    timer.cancel()
                except Exception:
                    pass

            return TimerCancelResult(
                cancelled=cancelled,
                previous_snapshot=previous_snapshot,
            )

    def shutdown(self) -> None:
        self.cancel()

    def _fire(self, token: int) -> None:
        fired_event: TimerFiredEvent | None = None

        with self._lock:
            # Старый заменённый или отменённый timer
            # не должен породить событие.
            if (
                not self._active
                or token != self._token
                or self._started_at is None
                or self._deadline is None
            ):
                return

            fired_at = self._clock()

            fired_event = TimerFiredEvent(
                token=token,
                duration_seconds=(
                    self._duration_seconds
                ),
                started_at=self._started_at,
                deadline=self._deadline,
                fired_at=fired_at,
            )

            self._timer = None
            self._active = False
            self._duration_seconds = 0
            self._started_at = None
            self._deadline = None

        # Callback вызывается вне lock:
        # callback может отправить событие или обратиться
        # обратно к TimerService без deadlock.
        if fired_event is not None:
            self._on_fired(fired_event)