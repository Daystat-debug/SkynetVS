from __future__ import annotations

import json

from datetime import datetime, timezone, timedelta
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from modules.reminder_command_parser import (
    parse_reminder_command,
)


TZ = timezone(timedelta(hours=3))
NOW = datetime(2026, 7, 13, 15, 0, tzinfo=TZ)


CASES: list[dict[str, Any]] = [
    {
        "name": "create relative reminder",
        "text": "напомни через 20 минут проверить духовку",
        "expected": {
            "intent": "CREATE_REMINDER",
            "error": None,
            "slots": {
                "due_at_epoch": datetime(2026, 7, 13, 15, 20, tzinfo=TZ).timestamp(),
                "reminder_text": "проверить духовку",
                "reminder_time_kind": "relative",
                "matched_time_text": "через 20 минут",
            },
        },
    },
    {
        "name": "create reminder alias",
        "text": "создай напоминание завтра в 9 купить хлеб",
        "expected": {
            "intent": "CREATE_REMINDER",
            "error": None,
            "slots": {
                "due_at_epoch": datetime(2026, 7, 14, 9, 0, tzinfo=TZ).timestamp(),
                "reminder_text": "купить хлеб",
                "reminder_time_kind": "tomorrow",
                "matched_time_text": "завтра в 9",
            },
        },
    },
    {
        "name": "create reminder missing time",
        "text": "напомни купить хлеб",
        "expected": {
            "intent": "CREATE_REMINDER",
            "error": "missing_reminder_time",
            "slots": {
                "reminder_error": "missing_reminder_time",
            },
        },
    },
    {
        "name": "create reminder missing text",
        "text": "напомни завтра в 9",
        "expected": {
            "intent": "CREATE_REMINDER",
            "error": "missing_reminder_text",
            "slots": {
                "reminder_time_kind": "tomorrow",
                "matched_time_text": "завтра в 9",
                "reminder_error": "missing_reminder_text",
            },
        },
    },
    {
        "name": "create reminder invalid time",
        "text": "напомни завтра в 25:00 проверить духовку",
        "expected": {
            "intent": "CREATE_REMINDER",
            "error": "invalid_reminder_time",
            "slots": {
                "reminder_error": "invalid_reminder_time",
            },
        },
    },
    {
        "name": "list reminders",
        "text": "какие у меня напоминания",
        "expected": {
            "intent": "LIST_REMINDERS",
            "error": None,
            "slots": {},
        },
    },
    {
        "name": "list reminders alias",
        "text": "покажи мои напоминания",
        "expected": {
            "intent": "LIST_REMINDERS",
            "error": None,
            "slots": {},
        },
    },
    {
        "name": "cancel latest reminder",
        "text": "отмени последнее напоминание",
        "expected": {
            "intent": "CANCEL_REMINDER",
            "error": None,
            "slots": {
                "cancel_mode": "latest",
            },
        },
    },
    {
        "name": "cancel reminder by query",
        "text": "отмени напоминание про хлеб",
        "expected": {
            "intent": "CANCEL_REMINDER",
            "error": None,
            "slots": {
                "cancel_mode": "query",
                "reminder_query": "хлеб",
            },
        },
    },
    {
        "name": "cancel reminder by query without preposition",
        "text": "удали напоминание позвонить Сергею",
        "expected": {
            "intent": "CANCEL_REMINDER",
            "error": None,
            "slots": {
                "cancel_mode": "query",
                "reminder_query": "позвонить сергею",
            },
        },
    },
    {
        "name": "cancel reminder missing target",
        "text": "отмени напоминание",
        "expected": {
            "intent": "CANCEL_REMINDER",
            "error": "missing_reminder_target",
            "slots": {
                "reminder_error": "missing_reminder_target",
            },
        },
    },
    {
        "name": "bulk cancel unsupported",
        "text": "отмени все напоминания",
        "expected": {
            "intent": "CANCEL_REMINDER",
            "error": "bulk_cancel_not_supported",
            "slots": {
                "reminder_error": "bulk_cancel_not_supported",
            },
        },
    },
    {
        "name": "bare reminder is not a command",
        "text": "напоминание",
        "expected": {
            "intent": None,
            "error": None,
            "slots": {},
        },
    },
    {
        "name": "unrelated text is not a reminder command",
        "text": "открой блокнот",
        "expected": {
            "intent": None,
            "error": None,
            "slots": {},
        },
    },
]


def main() -> int:
    fail_count = 0

    print("=== REMINDER COMMAND PARSER EVAL REPORT ===")

    for index, case in enumerate(CASES, start=1):
        result = parse_reminder_command(
            case["text"],
            now=NOW,
        )

        actual = {
            "intent": result.intent,
            "error": result.error,
            "slots": result.slots,
        }
        expected = case["expected"]
        ok = actual == expected

        print()
        print(f"{index}. {case['name']}")
        print(
            json.dumps(
                {
                    "text": case["text"],
                    "actual": actual,
                    "expected": expected,
                    "ok": ok,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        if ok:
            print("[OK] reminder command parser case")
        else:
            fail_count += 1
            print("[FAIL] reminder command parser case")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "case_count": len(CASES),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
