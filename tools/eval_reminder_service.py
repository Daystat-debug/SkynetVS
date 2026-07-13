from __future__ import annotations

import json
import tempfile

from pathlib import Path
from typing import Any, Callable

from modules.reminder_repository import (
    ReminderRepository,
)
from modules.reminder_service import (
    ReminderFiredEvent,
    ReminderService,
)


class FakeClock:
    def __init__(self, value: float) -> None:
        self.value = float(value)

    def __call__(self) -> float:
        return self.value

    def set(self, value: float) -> None:
        self.value = float(value)


class FakeTimer:
    def __init__(
        self,
        delay_seconds: float,
        callback: Callable[[], None],
    ) -> None:
        self.delay_seconds = float(delay_seconds)
        self.callback = callback
        self.daemon = False
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        self.callback()


class FakeTimerFactory:
    def __init__(self) -> None:
        self.timers: list[FakeTimer] = []

    def __call__(
        self,
        delay_seconds: float,
        callback: Callable[[], None],
    ) -> FakeTimer:
        timer = FakeTimer(
            delay_seconds,
            callback,
        )
        self.timers.append(timer)
        return timer

    @property
    def latest(self) -> FakeTimer | None:
        return (
            self.timers[-1]
            if self.timers
            else None
        )


class IdFactory:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"r{self.value}"


def main() -> int:
    fail_count = 0
    case_count = 0

    def check(
        name: str,
        actual: Any,
        expected: Any,
    ) -> None:
        nonlocal fail_count, case_count

        case_count += 1
        ok = actual == expected

        print()
        print(f"=== {name} ===")
        print(
            json.dumps(
                {
                    "actual": actual,
                    "expected": expected,
                    "ok": ok,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        clock = FakeClock(1000.0)
        factory = FakeTimerFactory()
        fired: list[ReminderFiredEvent] = []

        repository = ReminderRepository(
            root / "reminders.json",
            clock=clock,
            id_factory=IdFactory(),
        )

        service = ReminderService(
            repository=repository,
            on_fired=fired.append,
            clock=clock,
            timer_factory=factory,
        )

        check(
            "EMPTY SERVICE",
            {
                "count": service.status().count,
                "scheduled": (
                    service.status()
                    .scheduled_reminder_id
                ),
                "timer_count": len(factory.timers),
            },
            {
                "count": 0,
                "scheduled": None,
                "timer_count": 0,
            },
        )

        first = service.add(
            text="Купить хлеб",
            due_at_epoch=1100.0,
        )
        first_timer = factory.latest

        check(
            "ADD FIRST REMINDER",
            {
                "id": first.record.reminder_id,
                "scheduled": (
                    first.snapshot
                    .scheduled_reminder_id
                ),
                "remaining": (
                    first.snapshot.remaining_seconds
                ),
                "delay": (
                    first_timer.delay_seconds
                    if first_timer
                    else None
                ),
                "started": (
                    first_timer.started
                    if first_timer
                    else None
                ),
                "daemon": (
                    first_timer.daemon
                    if first_timer
                    else None
                ),
            },
            {
                "id": "r1",
                "scheduled": "r1",
                "remaining": 100,
                "delay": 100.0,
                "started": True,
                "daemon": True,
            },
        )

        second = service.add(
            text="Проверить духовку",
            due_at_epoch=1050.0,
        )
        second_timer = factory.latest

        check(
            "EARLIER REMINDER REPLANS",
            {
                "id": second.record.reminder_id,
                "old_cancelled": (
                    first_timer.cancelled
                    if first_timer
                    else None
                ),
                "scheduled": (
                    second.snapshot
                    .scheduled_reminder_id
                ),
                "delay": (
                    second_timer.delay_seconds
                    if second_timer
                    else None
                ),
            },
            {
                "id": "r2",
                "old_cancelled": True,
                "scheduled": "r2",
                "delay": 50.0,
            },
        )

        if first_timer is not None:
            first_timer.fire()

        check(
            "STALE CALLBACK IGNORED",
            {
                "fired_count": len(fired),
                "count": repository.count(),
                "scheduled": (
                    service.status()
                    .scheduled_reminder_id
                ),
            },
            {
                "fired_count": 0,
                "count": 2,
                "scheduled": "r2",
            },
        )

        clock.set(1050.0)

        if second_timer is not None:
            second_timer.fire()

        next_timer = factory.latest

        check(
            "CURRENT REMINDER FIRES",
            {
                "events": [
                    {
                        "id": row.reminder_id,
                        "text": row.text,
                        "late": row.late_by_seconds,
                    }
                    for row in fired
                ],
                "remaining_ids": [
                    row.reminder_id
                    for row in repository.list_all()
                ],
                "scheduled": (
                    service.status()
                    .scheduled_reminder_id
                ),
                "next_delay": (
                    next_timer.delay_seconds
                    if next_timer
                    else None
                ),
            },
            {
                "events": [
                    {
                        "id": "r2",
                        "text": "Проверить духовку",
                        "late": 0.0,
                    }
                ],
                "remaining_ids": ["r1"],
                "scheduled": "r1",
                "next_delay": 50.0,
            },
        )

        third = service.add(
            text="Позвонить Сергею",
            due_at_epoch=1075.0,
        )
        third_timer = factory.latest

        cancelled = service.cancel(
            third.record.reminder_id
        )
        after_cancel_timer = factory.latest

        check(
            "CANCEL SCHEDULED REMINDER",
            {
                "cancelled": cancelled.cancelled,
                "record": (
                    cancelled.record.reminder_id
                    if cancelled.record
                    else None
                ),
                "old_cancelled": (
                    third_timer.cancelled
                    if third_timer
                    else None
                ),
                "scheduled": (
                    cancelled.snapshot
                    .scheduled_reminder_id
                ),
                "delay": (
                    after_cancel_timer.delay_seconds
                    if after_cancel_timer
                    else None
                ),
            },
            {
                "cancelled": True,
                "record": "r3",
                "old_cancelled": True,
                "scheduled": "r1",
                "delay": 50.0,
            },
        )

        fourth = service.add(
            text="Отправить отчёт",
            due_at_epoch=1200.0,
        )
        latest_cancel = service.cancel_latest()

        check(
            "CANCEL LATEST CREATED",
            {
                "created": fourth.record.reminder_id,
                "cancelled": latest_cancel.cancelled,
                "removed": (
                    latest_cancel.record.reminder_id
                    if latest_cancel.record
                    else None
                ),
                "remaining": [
                    row.reminder_id
                    for row in service.list_all()
                ],
            },
            {
                "created": "r4",
                "cancelled": True,
                "removed": "r4",
                "remaining": ["r1"],
            },
        )

        invalid_count = 0

        for due_at in (
            1050.0,
            1050.0 + 31 * 24 * 60 * 60,
            float("inf"),
        ):
            try:
                service.add(
                    text="Некорректное",
                    due_at_epoch=due_at,
                )
            except ValueError:
                invalid_count += 1

        check(
            "INVALID NEW TIMES REJECTED",
            invalid_count,
            3,
        )

        restore_path = root / "restore.json"
        restore_repository = ReminderRepository(
            restore_path,
        )
        restore_repository.add(
            reminder_id="future",
            text="Будущее",
            due_at_epoch=1300.0,
            created_at_epoch=900.0,
        )
        restore_repository.add(
            reminder_id="overdue",
            text="Просроченное",
            due_at_epoch=1040.0,
            created_at_epoch=800.0,
        )

        restore_factory = FakeTimerFactory()
        restore_fired: list[
            ReminderFiredEvent
        ] = []

        restored_service = ReminderService(
            repository=restore_repository,
            on_fired=restore_fired.append,
            clock=clock,
            timer_factory=restore_factory,
        )
        overdue_timer = restore_factory.latest

        check(
            "RESTORE OVERDUE REMINDER",
            {
                "scheduled": (
                    restored_service.status()
                    .scheduled_reminder_id
                ),
                "delay": (
                    overdue_timer.delay_seconds
                    if overdue_timer
                    else None
                ),
            },
            {
                "scheduled": "overdue",
                "delay": 0.0,
            },
        )

        if overdue_timer is not None:
            overdue_timer.fire()

        restored_next_timer = (
            restore_factory.latest
        )

        check(
            "OVERDUE FIRES AND NEXT IS SCHEDULED",
            {
                "events": [
                    {
                        "id": row.reminder_id,
                        "late": row.late_by_seconds,
                    }
                    for row in restore_fired
                ],
                "scheduled": (
                    restored_service.status()
                    .scheduled_reminder_id
                ),
                "next_delay": (
                    restored_next_timer.delay_seconds
                    if restored_next_timer
                    else None
                ),
            },
            {
                "events": [
                    {
                        "id": "overdue",
                        "late": 10.0,
                    }
                ],
                "scheduled": "future",
                "next_delay": 250.0,
            },
        )

        active_timer = restore_factory.latest
        restored_service.shutdown()

        check(
            "SHUTDOWN PRESERVES RECORDS",
            {
                "shutdown": (
                    restored_service.status().shutdown
                ),
                "scheduled": (
                    restored_service.status()
                    .scheduled_reminder_id
                ),
                "timer_cancelled": (
                    active_timer.cancelled
                    if active_timer
                    else None
                ),
                "repository_count": (
                    restore_repository.count()
                ),
            },
            {
                "shutdown": True,
                "scheduled": None,
                "timer_cancelled": True,
                "repository_count": 1,
            },
        )

        if active_timer is not None:
            active_timer.fire()

        check(
            "CALLBACK AFTER SHUTDOWN IGNORED",
            {
                "fired_count": len(restore_fired),
                "repository_count": (
                    restore_repository.count()
                ),
            },
            {
                "fired_count": 1,
                "repository_count": 1,
            },
        )

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "case_count": case_count,
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
