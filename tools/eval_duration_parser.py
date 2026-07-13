from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from modules.duration_parser import (
    format_duration_ru,
    parse_duration,
)


PARSE_CASES: list[dict[str, Any]] = [
    {
        "text": "поставь таймер на 30 секунд",
        "seconds": 30,
        "error": None,
    },
    {
        "text": "таймер на 5 минут",
        "seconds": 300,
        "error": None,
    },
    {
        "text": "запусти таймер на 1 час 20 минут",
        "seconds": 4800,
        "error": None,
    },
    {
        "text": "таймер на одну минуту",
        "seconds": 60,
        "error": None,
    },
    {
        "text": "таймер на два часа",
        "seconds": 7200,
        "error": None,
    },
    {
        "text": "таймер на час",
        "seconds": 3600,
        "error": None,
    },
    {
        "text": "через минуту",
        "seconds": 60,
        "error": None,
    },
    {
        "text": "таймер на 1 минуту 30 секунд",
        "seconds": 90,
        "error": None,
    },
    {
        "text": "таймер на сто двадцать секунд",
        "seconds": 120,
        "error": None,
    },
    {
        "text": "таймер на 24 часа",
        "seconds": 86400,
        "error": None,
    },

    # Negative cases.
    {
        "text": "поставь таймер",
        "seconds": None,
        "error": "missing_duration",
    },
    {
        "text": "таймер на 10",
        "seconds": None,
        "error": "missing_duration",
    },
    {
        "text": "таймер на 0 секунд",
        "seconds": None,
        "error": "duration_too_short",
    },
    {
        "text": "таймер на 24 часа 1 секунду",
        "seconds": None,
        "error": "duration_too_long",
    },
    {
        "text": "таймер на часов",
        "seconds": None,
        "error": "invalid_duration",
    },
    {
        "text": "таймер на полторы минуты",
        "seconds": None,
        "error": "invalid_duration",
    },
]


FORMAT_CASES: list[dict[str, Any]] = [
    {
        "seconds": 1,
        "expected": "1 секунда",
    },
    {
        "seconds": 2,
        "expected": "2 секунды",
    },
    {
        "seconds": 5,
        "expected": "5 секунд",
    },
    {
        "seconds": 61,
        "expected": "1 минута 1 секунда",
    },
    {
        "seconds": 125,
        "expected": "2 минуты 5 секунд",
    },
    {
        "seconds": 3661,
        "expected": "1 час 1 минута 1 секунда",
    },
    {
        "seconds": 7200,
        "expected": "2 часа",
    },
    {
        "seconds": 18000,
        "expected": "5 часов",
    },
]


def main() -> int:
    fail_count = 0

    print("=== DURATION PARSER EVAL REPORT ===")
    print()
    print("--- parse cases ---")

    for index, case in enumerate(PARSE_CASES, start=1):
        result = parse_duration(str(case["text"]))

        actual = {
            "seconds": result.seconds,
            "error": result.error,
        }

        expected = {
            "seconds": case["seconds"],
            "error": case["error"],
        }

        ok = actual == expected

        print()
        print(f"{index}. {case['text']}")
        print(
            json.dumps(
                {
                    "actual": actual,
                    "expected": expected,
                    "result": asdict(result),
                    "ok": ok,
                },
                ensure_ascii=False,
            )
        )

        if ok:
            print("[OK] duration parse case")
        else:
            fail_count += 1
            print("[FAIL] duration parse mismatch")

    print()
    print("--- format cases ---")

    for index, case in enumerate(FORMAT_CASES, start=1):
        actual = format_duration_ru(
            int(case["seconds"])
        )
        expected = str(case["expected"])
        ok = actual == expected

        print()
        print(
            f"{index}. seconds={case['seconds']}"
        )
        print(
            json.dumps(
                {
                    "actual": actual,
                    "expected": expected,
                    "ok": ok,
                },
                ensure_ascii=False,
            )
        )

        if ok:
            print("[OK] duration format case")
        else:
            fail_count += 1
            print("[FAIL] duration format mismatch")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "parse_cases": len(PARSE_CASES),
                "format_cases": len(FORMAT_CASES),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())