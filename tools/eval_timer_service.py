from __future__ import annotations

import json

from typing import Callable

from dotenv import load_dotenv

load_dotenv()

from modules.timer_service import (
    TimerFiredEvent,
    TimerService,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += float(seconds)


class FakeTimer:
    def __init__(
        self,
        delay: float,
        callback: Callable[[], None],
    ) -> None:
        self.delay = delay
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
        delay: float,
        callback: Callable[[], None],
    ) -> FakeTimer:
        timer = FakeTimer(
            delay,
            callback,
        )
        self.timers.append(timer)
        return timer


def main() -> int:
    fail_count = 0

    def check(
        name: str,
        actual: object,
        expected: object,
    ) -> None:
        nonlocal fail_count

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

    clock = FakeClock()
    factory = FakeTimerFactory()
    fired_events: list[TimerFiredEvent] = []

    service = TimerService(
        on_fired=fired_events.append,
        clock=clock,
        timer_factory=factory,
    )

    # 1. Начальное состояние.
    initial = service.status()

    check(
        "INITIAL TIMER INACTIVE",
        {
            "active": initial.active,
            "remaining": (
                initial.remaining_seconds
            ),
        },
        {
            "active": False,
            "remaining": 0,
        },
    )

    # 2. Запуск.
    first_start = service.start(60)
    first_timer = factory.timers[-1]

    check(
        "START TIMER",
        {
            "replaced": first_start.replaced,
            "active": (
                first_start.snapshot.active
            ),
            "duration": (
                first_start.snapshot
                .duration_seconds
            ),
            "remaining": (
                first_start.snapshot
                .remaining_seconds
            ),
            "timer_started": (
                first_timer.started
            ),
            "timer_daemon": (
                first_timer.daemon
            ),
        },
        {
            "replaced": False,
            "active": True,
            "duration": 60,
            "remaining": 60,
            "timer_started": True,
            "timer_daemon": True,
        },
    )

    # 3. Остаток времени уменьшается.
    clock.advance(12.2)
    status_after_time = service.status()

    check(
        "REMAINING TIME",
        status_after_time.remaining_seconds,
        48,
    )

    # 4. Новый timer заменяет старый.
    second_start = service.start(30)
    second_timer = factory.timers[-1]

    check(
        "REPLACE TIMER",
        {
            "replaced": second_start.replaced,
            "old_cancelled": (
                first_timer.cancelled
            ),
            "new_started": (
                second_timer.started
            ),
            "remaining": (
                second_start.snapshot
                .remaining_seconds
            ),
        },
        {
            "replaced": True,
            "old_cancelled": True,
            "new_started": True,
            "remaining": 30,
        },
    )

    # 5. Запоздалый callback старого timer
    # ничего не делает.
    first_timer.fire()

    check(
        "STALE TIMER CALLBACK IGNORED",
        {
            "fired_count": len(fired_events),
            "active": service.status().active,
            "remaining": (
                service.status()
                .remaining_seconds
            ),
        },
        {
            "fired_count": 0,
            "active": True,
            "remaining": 30,
        },
    )

    # 6. Актуальный timer завершается.
    clock.advance(30)
    second_timer.fire()

    check(
        "CURRENT TIMER FIRES",
        {
            "fired_count": len(fired_events),
            "duration": (
                fired_events[0]
                .duration_seconds
                if fired_events
                else None
            ),
            "active": service.status().active,
        },
        {
            "fired_count": 1,
            "duration": 30,
            "active": False,
        },
    )

    # 7. Отмена активного timer.
    service.start(20)
    third_timer = factory.timers[-1]

    cancel_result = service.cancel()

    check(
        "CANCEL TIMER",
        {
            "cancelled": (
                cancel_result.cancelled
            ),
            "previous_remaining": (
                cancel_result
                .previous_snapshot
                .remaining_seconds
            ),
            "timer_cancelled": (
                third_timer.cancelled
            ),
            "active": service.status().active,
        },
        {
            "cancelled": True,
            "previous_remaining": 20,
            "timer_cancelled": True,
            "active": False,
        },
    )

    # 8. Callback отменённого timer игнорируется.
    third_timer.fire()

    check(
        "CANCELLED TIMER CALLBACK IGNORED",
        len(fired_events),
        1,
    )

    # 9. Повторная отмена.
    second_cancel = service.cancel()

    check(
        "CANCEL WITHOUT ACTIVE TIMER",
        second_cancel.cancelled,
        False,
    )

    # 10. Ограничения длительности.
    invalid_cases = [
        0,
        -1,
        86401,
        True,
    ]

    invalid_errors = 0

    for value in invalid_cases:
        try:
            service.start(value)
        except ValueError:
            invalid_errors += 1

    check(
        "INVALID DURATIONS REJECTED",
        invalid_errors,
        len(invalid_cases),
    )

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "case_count": 10,
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())