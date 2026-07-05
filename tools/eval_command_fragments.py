from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.command_fragments import (
    looks_incomplete_command,
    merge_phrases,
)


HOTWORDS = ("скайнет", "skynet")

Case = Dict[str, Any]


MERGE_CASES: List[Case] = [
    {
        "left": "открой",
        "right": "блокнот",
        "expected": "открой блокнот",
    },
    {
        "left": "  открой  ",
        "right": "   блокнот  ",
        "expected": "открой блокнот",
    },
    {
        "left": "",
        "right": "блокнот",
        "expected": "блокнот",
    },
    {
        "left": "открой",
        "right": "",
        "expected": "открой",
    },
    {
        "left": "",
        "right": "",
        "expected": "",
    },
]


INCOMPLETE_CASES: List[Case] = [
    {
        "text": "открой",
        "expected": True,
    },
    {
        "text": "запусти",
        "expected": True,
    },
    {
        "text": "переключи",
        "expected": True,
    },
    {
        "text": "поставь",
        "expected": True,
    },
    {
        "text": "открой блокнот",
        "expected": False,
    },
    {
        "text": "запусти калькулятор",
        "expected": False,
    },
    {
        "text": "скайнет",
        "expected": False,
    },
    {
        "text": "skynet",
        "expected": False,
    },
    {
        "text": "",
        "expected": False,
    },
]


def main() -> int:
    fail_count = 0

    print("=== COMMAND FRAGMENTS EVAL REPORT ===")

    print()
    print("--- MERGE CASES ---")
    for case in MERGE_CASES:
        actual = merge_phrases(
            str(case["left"]),
            str(case["right"]),
        )

        expected = str(case["expected"])
        ok = actual == expected

        print(
            json.dumps(
                {
                    "left": case["left"],
                    "right": case["right"],
                    "expected": expected,
                    "actual": actual,
                },
                ensure_ascii=False,
            )
        )

        if not ok:
            fail_count += 1
            print("[FAIL] merge mismatch")
        else:
            print("[OK] merge case")

    print()
    print("--- INCOMPLETE CASES ---")
    for case in INCOMPLETE_CASES:
        text = str(case["text"])
        actual = looks_incomplete_command(
            text,
            hotwords=HOTWORDS,
        )

        expected = bool(case["expected"])
        ok = actual == expected

        print(
            json.dumps(
                {
                    "text": text,
                    "expected": expected,
                    "actual": actual,
                },
                ensure_ascii=False,
            )
        )

        if not ok:
            fail_count += 1
            print("[FAIL] incomplete mismatch")
        else:
            print("[OK] incomplete case")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "merge_cases": len(MERGE_CASES),
                "incomplete_cases": len(INCOMPLETE_CASES),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())