from __future__ import annotations

import math
import threading
import time

from dataclasses import dataclass
from typing import Callable, Protocol

from modules.reminder_repository import (
    ReminderRecord,
    ReminderRepository,
)


MAX_REMINDER_HORIZON_SEC = 30 * 24 * 60 * 60


class ReminderTimerHandle(Protocol):
    daemon: bool

    def start(self) -> None:
        ...

    def cancel(self) -> None:
        ...


ClockFunc = Callable[[], float]
ReminderTimerFactory = Callable[
    [float, Callable[[], None]],
    ReminderTimerHandle,
]
ReminderFiredCallback = Callable[
    ["ReminderFiredEvent"],
    None,
]


@dataclass(frozen=True)
class ReminderServiceSnapshot:
    count: int
    token: int
    scheduled_reminder_id: str | None
    scheduled_due_at_epoch: float | None
    remaining_seconds: int
    shutdown: bool


@dataclass(frozen=True)
class ReminderAddResult:
    record: ReminderRecord
    snapshot: ReminderServiceSnapshot


@dataclass(frozen=True)
class ReminderCancelResult:
    cancelled: bool
    record: ReminderRecord | None
    snapshot: ReminderServiceSnapshot


@dataclass(frozen=True)
class ReminderFiredEvent:
    reminder_id: str
    text: str
    due_at_epoch: float
    created_at_epoch: float
    fired_at_epoch: float
    late_by_seconds: float


def _default_timer_factory(
    delay_seconds: float,
    callback: Callable[[], None],
) -> ReminderTimerHandle:
    return threading.Timer(
        delay_seconds,
        callback,
    )


class ReminderService:
    """
    Планировщик одноразовых напоминаний.

    Использует один системный timer, который всегда
    указывает на ближайшую запись в repository.

    Не зависит от:
      - main.py;
      - event queue;
      - TTS;
      - NLU;
      - Actions.
    """

    def __init__(
        self,
        *,
        repository: ReminderRepository,
        on_fired: ReminderFiredCallback,
        clock: ClockFunc = time.time,
        timer_factory: ReminderTimerFactory = (
            _default_timer_factory
        ),
        max_horizon_seconds: float = (
            MAX_REMINDER_HORIZON_SEC
        ),
    ) -> None:
        self._repository = repository
        self._on_fired = on_fired
        self._clock = clock
        self._timer_factory = timer_factory
        self._max_horizon_seconds = float(
            max_horizon_seconds
        )

        if (
            not math.isfinite(
                self._max_horizon_seconds
            )
            or self._max_horizon_seconds <= 0
        ):
            raise ValueError(
                "max_horizon_seconds must be positive"
            )

        self._lock = threading.RLock()
        self._timer: ReminderTimerHandle | None = None
        self._token = 0
        self._scheduled_reminder_id: str | None = None
        self._scheduled_due_at_epoch: float | None = None
        self._shutdown = False

        with self._lock:
            self._reschedule_locked()

    @property
    def repository(self) -> ReminderRepository:
        return self._repository

    def _snapshot_locked(
        self,
        *,
        now: float | None = None,
    ) -> ReminderServiceSnapshot:
        current_time = (
            self._clock()
            if now is None
            else float(now)
        )

        remaining_seconds = 0

        if self._scheduled_due_at_epoch is not None:
            remaining_seconds = int(
                math.ceil(
                    max(
                        0.0,
                        self._scheduled_due_at_epoch
                        - current_time,
                    )
                )
            )

        return ReminderServiceSnapshot(
            count=self._repository.count(),
            token=self._token,
            scheduled_reminder_id=(
                self._scheduled_reminder_id
            ),
            scheduled_due_at_epoch=(
                self._scheduled_due_at_epoch
            ),
            remaining_seconds=remaining_seconds,
            shutdown=self._shutdown,
        )

    def status(self) -> ReminderServiceSnapshot:
        with self._lock:
            return self._snapshot_locked()

    def list_all(self) -> list[ReminderRecord]:
        return self._repository.list_all()

    def get(
        self,
        reminder_id: str,
    ) -> ReminderRecord | None:
        return self._repository.get(reminder_id)

    def search_text(
        self,
        query: str,
    ) -> list[ReminderRecord]:
        return self._repository.search_text(query)

    def latest_created(
        self,
    ) -> ReminderRecord | None:
        return self._repository.latest_created()

    def add(
        self,
        *,
        text: str,
        due_at_epoch: float,
        created_at_epoch: float | None = None,
        reminder_id: str | None = None,
    ) -> ReminderAddResult:
        due_at = self._validate_new_due_at(
            due_at_epoch
        )

        with self._lock:
            if self._shutdown:
                raise RuntimeError(
                    "reminder service is shut down"
                )

            record = self._repository.add(
                text=text,
                due_at_epoch=due_at,
                created_at_epoch=created_at_epoch,
                reminder_id=reminder_id,
            )

            try:
                self._reschedule_locked()
            except Exception:
                # Не оставляем записанное, но фактически
                # не запланированное напоминание.
                self._repository.remove(
                    record.reminder_id
                )
                self._reschedule_locked()
                raise

            return ReminderAddResult(
                record=record,
                snapshot=self._snapshot_locked(),
            )

    def cancel(
        self,
        reminder_id: str,
    ) -> ReminderCancelResult:
        with self._lock:
            if self._shutdown:
                return ReminderCancelResult(
                    cancelled=False,
                    record=None,
                    snapshot=self._snapshot_locked(),
                )

            record = self._repository.remove(
                reminder_id
            )

            if record is not None:
                self._reschedule_locked()

            return ReminderCancelResult(
                cancelled=record is not None,
                record=record,
                snapshot=self._snapshot_locked(),
            )

    def cancel_latest(self) -> ReminderCancelResult:
        with self._lock:
            latest = self._repository.latest_created()

            if latest is None:
                return ReminderCancelResult(
                    cancelled=False,
                    record=None,
                    snapshot=self._snapshot_locked(),
                )

            return self.cancel(
                latest.reminder_id
            )

    def restore(self) -> ReminderServiceSnapshot:
        with self._lock:
            if self._shutdown:
                raise RuntimeError(
                    "reminder service is shut down"
                )

            self._reschedule_locked()
            return self._snapshot_locked()

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown = True
            self._invalidate_timer_locked()

    def _validate_new_due_at(
        self,
        due_at_epoch: float,
    ) -> float:
        if isinstance(due_at_epoch, bool):
            raise ValueError(
                "due_at_epoch must be numeric"
            )

        try:
            due_at = float(due_at_epoch)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "due_at_epoch must be numeric"
            ) from exc

        if not math.isfinite(due_at):
            raise ValueError(
                "due_at_epoch must be finite"
            )

        now = self._clock()

        if due_at <= now:
            raise ValueError(
                "reminder time must be in the future"
            )

        if (
            due_at - now
            > self._max_horizon_seconds
        ):
            raise ValueError(
                "reminder time is too far"
            )

        return due_at

    def _invalidate_timer_locked(self) -> None:
        timer = self._timer

        self._token += 1
        self._timer = None
        self._scheduled_reminder_id = None
        self._scheduled_due_at_epoch = None

        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass

    def _reschedule_locked(self) -> None:
        self._invalidate_timer_locked()

        if self._shutdown:
            return

        rows = self._repository.list_all()

        if not rows:
            return

        record = rows[0]
        now = self._clock()
        delay_seconds = max(
            0.0,
            record.due_at_epoch - now,
        )

        token = self._token
        reminder_id = record.reminder_id

        timer = self._timer_factory(
            delay_seconds,
            lambda: self._fire(
                token,
                reminder_id,
            ),
        )

        try:
            timer.daemon = True
        except Exception:
            pass

        self._timer = timer
        self._scheduled_reminder_id = reminder_id
        self._scheduled_due_at_epoch = (
            record.due_at_epoch
        )

        try:
            timer.start()
        except Exception:
            self._timer = None
            self._scheduled_reminder_id = None
            self._scheduled_due_at_epoch = None
            self._token += 1
            raise

    def _fire(
        self,
        token: int,
        reminder_id: str,
    ) -> None:
        fired_event: ReminderFiredEvent | None = None

        with self._lock:
            if (
                self._shutdown
                or token != self._token
                or reminder_id
                != self._scheduled_reminder_id
            ):
                return

            record = self._repository.get(
                reminder_id
            )

            if record is None:
                self._reschedule_locked()
                return

            fired_at = self._clock()

            # threading.Timer может проснуться немного
            # раньше из-за изменения системного времени.
            if fired_at < record.due_at_epoch:
                self._reschedule_locked()
                return

            removed = self._repository.remove(
                reminder_id
            )

            if removed is None:
                self._reschedule_locked()
                return

            fired_event = ReminderFiredEvent(
                reminder_id=removed.reminder_id,
                text=removed.text,
                due_at_epoch=removed.due_at_epoch,
                created_at_epoch=(
                    removed.created_at_epoch
                ),
                fired_at_epoch=fired_at,
                late_by_seconds=max(
                    0.0,
                    fired_at - removed.due_at_epoch,
                ),
            )

            self._reschedule_locked()

        # Callback вызывается вне lock, чтобы event_q
        # или внешний код не могли создать deadlock.
        if fired_event is not None:
            self._on_fired(fired_event)
