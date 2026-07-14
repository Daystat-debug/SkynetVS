from __future__ import annotations

import json

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from modules.reminder_actions import ReminderActions


@dataclass(frozen=True)
class FakeRecord:
    reminder_id: str
    text: str
    due_at_epoch: float
    created_at_epoch: float


class FakeService:
    def __init__(self) -> None:
        self.records: list[FakeRecord] = []
        self.add_calls: list[dict[str, Any]] = []
        self.cancel_calls: list[str] = []

    def add(self, **kwargs: Any) -> None:
        self.add_calls.append(dict(kwargs))

    def list_all(self) -> list[FakeRecord]:
        return list(self.records)

    def latest_created(self) -> FakeRecord | None:
        if not self.records:
            return None
        return max(
            self.records,
            key=lambda row: (
                row.created_at_epoch,
                row.reminder_id,
            ),
        )

    def search_text(self, query: str) -> list[FakeRecord]:
        q = str(query or "").casefold()
        return [
            row
            for row in self.records
            if q in row.text.casefold()
        ]

    def cancel(self, reminder_id: str) -> None:
        self.cancel_calls.append(reminder_id)
        self.records = [
            row
            for row in self.records
            if row.reminder_id != reminder_id
        ]


def main() -> int:
    fixed_now = datetime(
        2026,
        7,
        14,
        12,
        0,
        tzinfo=timezone.utc,
    ).timestamp()

    service = FakeService()
    actions = ReminderActions(
        service,  # type: ignore[arg-type]
        clock=lambda: fixed_now,
        timezone=timezone.utc,
        list_limit=2,
    )

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

    create_slots = {
        "due_at_epoch": fixed_now + 20 * 60,
        "reminder_text": "проверить духовку",
        "matched_time_text": "через 20 минут",
    }

    check(
        "CREATE REPLY",
        actions.reply_create(create_slots),
        (
            "Создаю напоминание через 20 минут: "
            "проверить духовку."
        ),
    )

    actions.execute_create(create_slots)

    check(
        "CREATE EXECUTE",
        service.add_calls,
        [
            {
                "text": "проверить духовку",
                "due_at_epoch": fixed_now + 20 * 60,
            }
        ],
    )

    check(
        "CREATE ERROR REPLY",
        actions.reply_create(
            {
                "reminder_error": (
                    "missing_reminder_time"
                )
            }
        ),
        "Скажи, когда нужно напомнить.",
    )

    check(
        "EMPTY LIST",
        actions.reply_list({}),
        "Активных напоминаний нет.",
    )

    service.records = [
        FakeRecord(
            "r1",
            "купить хлеб",
            fixed_now + 3600,
            fixed_now - 100,
        ),
        FakeRecord(
            "r2",
            "позвонить Сергею",
            fixed_now + 24 * 3600,
            fixed_now - 50,
        ),
        FakeRecord(
            "r3",
            "проверить подписку",
            fixed_now + 2 * 24 * 3600,
            fixed_now - 10,
        ),
    ]

    check(
        "LIST WITH LIMIT",
        actions.reply_list({}),
        (
            "У тебя 3 напоминания. "
            "1. сегодня в 13:00 — купить хлеб. "
            "2. завтра в 12:00 — позвонить Сергею. "
            "И ещё 1 напоминание."
        ),
    )

    latest_slots = {"cancel_mode": "latest"}
    latest_reply = actions.reply_cancel(latest_slots)
    actions.execute_cancel(latest_slots)

    check(
        "CANCEL LATEST",
        {
            "reply": latest_reply,
            "resolved": latest_slots.get(
                "_resolved_reminder_id"
            ),
            "cancel_calls": service.cancel_calls,
        },
        {
            "reply": (
                "Отменяю напоминание: "
                "проверить подписку."
            ),
            "resolved": "r3",
            "cancel_calls": ["r3"],
        },
    )

    query_slots = {
        "cancel_mode": "query",
        "reminder_query": "хлеб",
    }
    query_reply = actions.reply_cancel(query_slots)
    actions.execute_cancel(query_slots)

    check(
        "CANCEL QUERY",
        {
            "reply": query_reply,
            "resolved": query_slots.get(
                "_resolved_reminder_id"
            ),
            "cancel_calls": service.cancel_calls,
        },
        {
            "reply": (
                "Отменяю напоминание: "
                "купить хлеб."
            ),
            "resolved": "r1",
            "cancel_calls": ["r3", "r1"],
        },
    )

    service.records = [
        FakeRecord(
            "m1",
            "купить хлеб",
            fixed_now + 100,
            fixed_now - 20,
        ),
        FakeRecord(
            "m2",
            "купить хлеб и молоко",
            fixed_now + 200,
            fixed_now - 10,
        ),
    ]

    ambiguous_slots = {
        "cancel_mode": "query",
        "reminder_query": "хлеб",
    }
    ambiguous_reply = actions.reply_cancel(
        ambiguous_slots
    )
    actions.execute_cancel(ambiguous_slots)

    check(
        "AMBIGUOUS CANCEL DOES NOT EXECUTE",
        {
            "reply": ambiguous_reply,
            "resolved": ambiguous_slots.get(
                "_resolved_reminder_id"
            ),
            "cancel_calls": service.cancel_calls,
        },
        {
            "reply": (
                "Нашёл несколько напоминаний по запросу "
                "«хлеб». Уточни текст."
            ),
            "resolved": None,
            "cancel_calls": ["r3", "r1"],
        },
    )

    check(
        "BULK CANCEL ERROR",
        actions.reply_cancel(
            {
                "reminder_error": (
                    "bulk_cancel_not_supported"
                )
            }
        ),
        (
            "Массовая отмена напоминаний "
            "пока не поддерживается."
        ),
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
