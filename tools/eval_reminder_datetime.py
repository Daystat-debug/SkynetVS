from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from modules.reminder_datetime_parser import parse_reminder_datetime


NOW = datetime(
    2026,
    7,
    13,
    15,
    0,
    0,
    tzinfo=timezone(timedelta(hours=3)),
)


CASES: list[dict[str, Any]] = [
    {
        "name": "relative time before text",
        "text": "напомни через 20 минут проверить духовку",
        "expected": {
            "due_at": "2026-07-13T15:20:00+03:00",
            "reminder_text": "проверить духовку",
            "time_kind": "relative",
            "matched_time_text": "через 20 минут",
            "error": None,
        },
    },
    {
        "name": "relative time after text",
        "text": "напомни проверить духовку через 20 минут",
        "expected": {
            "due_at": "2026-07-13T15:20:00+03:00",
            "reminder_text": "проверить духовку",
            "time_kind": "relative",
            "matched_time_text": "через 20 минут",
            "error": None,
        },
    },
    {
        "name": "compound relative time",
        "text": "напомни через 1 день 2 часа позвонить Сергею",
        "expected": {
            "due_at": "2026-07-14T17:00:00+03:00",
            "reminder_text": "позвонить сергею",
            "time_kind": "relative",
            "matched_time_text": "через 1 день 2 часа",
            "error": None,
        },
    },
    {
        "name": "today numeric clock",
        "text": "напомни сегодня в 18:30 купить хлеб",
        "expected": {
            "due_at": "2026-07-13T18:30:00+03:00",
            "reminder_text": "купить хлеб",
            "time_kind": "today",
            "matched_time_text": "сегодня в 18:30",
            "error": None,
        },
    },
    {
        "name": "tomorrow clock after text",
        "text": "напомни купить хлеб завтра в 9 утра",
        "expected": {
            "due_at": "2026-07-14T09:00:00+03:00",
            "reminder_text": "купить хлеб",
            "time_kind": "tomorrow",
            "matched_time_text": "завтра в 9 утра",
            "error": None,
        },
    },
    {
        "name": "tomorrow word clock",
        "text": "напомни завтра в девять утра отправить отчёт",
        "expected": {
            "due_at": "2026-07-14T09:00:00+03:00",
            "reminder_text": "отправить отчёт",
            "time_kind": "tomorrow",
            "matched_time_text": "завтра в девять утра",
            "error": None,
        },
    },
    {
        "name": "word hour and minute",
        "text": "напомни сегодня в восемнадцать тридцать купить хлеб",
        "expected": {
            "due_at": "2026-07-13T18:30:00+03:00",
            "reminder_text": "купить хлеб",
            "time_kind": "today",
            "matched_time_text": "сегодня в восемнадцать тридцать",
            "error": None,
        },
    },
    {
        "name": "next clock today",
        "text": "напомни в 16:00 проверить духовку",
        "expected": {
            "due_at": "2026-07-13T16:00:00+03:00",
            "reminder_text": "проверить духовку",
            "time_kind": "next_clock",
            "matched_time_text": "в 16:00",
            "error": None,
        },
    },
    {
        "name": "next clock tomorrow",
        "text": "напомни в 14:00 позвонить",
        "expected": {
            "due_at": "2026-07-14T14:00:00+03:00",
            "reminder_text": "позвонить",
            "time_kind": "next_clock",
            "matched_time_text": "в 14:00",
            "error": None,
        },
    },
    {
        "name": "missing time",
        "text": "напомни купить хлеб",
        "expected": {
            "due_at": None,
            "reminder_text": "",
            "time_kind": None,
            "matched_time_text": "",
            "error": "missing_reminder_time",
        },
    },
    {
        "name": "missing reminder text",
        "text": "напомни завтра в 9",
        "expected": {
            "due_at": None,
            "reminder_text": "",
            "time_kind": "tomorrow",
            "matched_time_text": "завтра в 9",
            "error": "missing_reminder_text",
        },
    },
    {
        "name": "explicit time in past",
        "text": "напомни сегодня в 14:00 купить хлеб",
        "expected": {
            "due_at": None,
            "reminder_text": "купить хлеб",
            "time_kind": "today",
            "matched_time_text": "сегодня в 14:00",
            "error": "reminder_in_past",
        },
    },
    {
        "name": "relative time too far",
        "text": "напомни через 31 день проверить подписку",
        "expected": {
            "due_at": None,
            "reminder_text": "проверить подписку",
            "time_kind": "relative",
            "matched_time_text": "через 31 день",
            "error": "reminder_too_far",
        },
    },
    {
        "name": "ambiguous two times",
        "text": "напомни через час завтра в 9 проверить духовку",
        "expected": {
            "due_at": None,
            "reminder_text": "",
            "time_kind": None,
            "matched_time_text": "",
            "error": "ambiguous_reminder_time",
        },
    },
    {
        "name": "invalid clock",
        "text": "напомни завтра в 25:00 проверить духовку",
        "expected": {
            "due_at": None,
            "reminder_text": "",
            "time_kind": None,
            "matched_time_text": "",
            "error": "invalid_reminder_time",
        },
    },
    {
        "name": "invalid minutes",
        "text": "напомни завтра в 12:75 проверить духовку",
        "expected": {
            "due_at": None,
            "reminder_text": "",
            "time_kind": None,
            "matched_time_text": "",
            "error": "invalid_reminder_time",
        },
    },
    {
        "name": "zero relative duration",
        "text": "напомни через 0 минут проверить духовку",
        "expected": {
            "due_at": None,
            "reminder_text": "",
            "time_kind": None,
            "matched_time_text": "",
            "error": "reminder_in_past",
        },
    },
    {
        "name": "unsupported fractional duration",
        "text": "напомни через полторы минуты проверить духовку",
        "expected": {
            "due_at": None,
            "reminder_text": "",
            "time_kind": None,
            "matched_time_text": "",
            "error": "invalid_reminder_time",
        },
    },
]


def _selected_payload(result: Any) -> dict[str, Any]:
    return {
        "due_at": result.due_at.isoformat() if result.due_at is not None else None,
        "reminder_text": result.reminder_text,
        "time_kind": result.time_kind,
        "matched_time_text": result.matched_time_text,
        "error": result.error,
    }


def main() -> int:
    fail_count = 0

    print("=== REMINDER DATETIME PARSER EVAL REPORT ===")

    for index, case in enumerate(CASES, start=1):
        result = parse_reminder_datetime(case["text"], now=NOW)
        actual = _selected_payload(result)
        expected = dict(case["expected"])
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
            print("[OK] reminder datetime case")
        else:
            fail_count += 1
            print("[FAIL] reminder datetime case")

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
