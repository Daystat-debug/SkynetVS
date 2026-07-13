from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from modules.actions import Actions


@dataclass(frozen=True)
class FakeSnapshot:
    active: bool
    remaining_seconds: int
    token: int = 1


class FakeTimerService:
    def __init__(
        self,
        *,
        active: bool = False,
        remaining_seconds: int = 0,
    ) -> None:
        self.active = active
        self.remaining_seconds = (
            remaining_seconds
        )
        self.start_calls: list[int] = []
        self.cancel_calls = 0

    def status(self) -> FakeSnapshot:
        return FakeSnapshot(
            active=self.active,
            remaining_seconds=(
                self.remaining_seconds
            ),
        )

    def start(self, seconds: int) -> None:
        self.start_calls.append(int(seconds))
        self.active = True
        self.remaining_seconds = int(seconds)

    def cancel(self) -> None:
        self.cancel_calls += 1
        self.active = False
        self.remaining_seconds = 0


class DummyService:
    pass


def make_actions(
    timer: FakeTimerService,
) -> Actions:
    return Actions(
        audio=None,
        screenshot_service=DummyService(),
        weather_service=DummyService(),
        typing_service=DummyService(),
        window_context_service=DummyService(),
        timer_service=timer,  # type: ignore[arg-type]
    )


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
            )
        )

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    timer = FakeTimerService()
    actions = make_actions(timer)

    set_meta = {
        "intent": "SET_TIMER",
        "confidence": 1.0,
        "slots": {
            "duration_seconds": 30,
        },
    }

    check(
        "SET TIMER REPLY",
        actions.handle(set_meta),
        "Ставлю таймер на 30 секунд.",
    )

    actions.execute(set_meta)

    check(
        "SET TIMER EXECUTE",
        timer.start_calls,
        [30],
    )

    check(
        "TIMER STATUS ACTIVE",
        actions.handle(
            {
                "intent": "TIMER_STATUS",
                "confidence": 1.0,
                "slots": {},
            }
        ),
        (
            "До окончания таймера "
            "осталось 30 секунд."
        ),
    )

    replacement_reply = actions.handle(
        {
            "intent": "SET_TIMER",
            "confidence": 1.0,
            "slots": {
                "duration_seconds": 60,
            },
        }
    )

    check(
        "REPLACE TIMER REPLY",
        replacement_reply,
        (
            "Заменяю активный таймер. "
            "Новый таймер на 1 минуту."
        ),
    )

    check(
        "CANCEL TIMER REPLY",
        actions.handle(
            {
                "intent": "CANCEL_TIMER",
                "confidence": 1.0,
                "slots": {},
            }
        ),
        "Отменяю таймер.",
    )

    actions.execute(
        {
            "intent": "CANCEL_TIMER",
            "confidence": 1.0,
            "slots": {},
        }
    )

    check(
        "CANCEL TIMER EXECUTE",
        timer.cancel_calls,
        1,
    )

    check(
        "TIMER STATUS INACTIVE",
        actions.handle(
            {
                "intent": "TIMER_STATUS",
                "confidence": 1.0,
                "slots": {},
            }
        ),
        "Активного таймера нет.",
    )

    check(
        "CANCEL INACTIVE TIMER REPLY",
        actions.handle(
            {
                "intent": "CANCEL_TIMER",
                "confidence": 1.0,
                "slots": {},
            }
        ),
        "Активного таймера нет.",
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