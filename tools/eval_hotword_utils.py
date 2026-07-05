from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.hotword_utils import (
    has_hotword,
    is_ack_echo,
    is_only_hotword,
    should_ignore_during_ack_window,
    strip_hotword,
)


HOTWORDS = ("скайнет", "skynet")
ACK_TEXT = "Слушаю"

Case = Dict[str, Any]


HOTWORD_CASES: List[Case] = [
    {
        "text": "скайнет",
        "has_hotword": True,
        "only_hotword": True,
        "stripped": "",
    },
    {
        "text": "скайНет",
        "has_hotword": True,
        "only_hotword": True,
        "stripped": "",
    },
    {
        "text": "скайнет открой блокнот",
        "has_hotword": True,
        "only_hotword": False,
        "stripped": "открой блокнот",
    },
    {
        "text": "скайнет, открой блокнот",
        "has_hotword": True,
        "only_hotword": False,
        "stripped": "открой блокнот",
    },
    {
        "text": "skynet открой блокнот",
        "has_hotword": True,
        "only_hotword": False,
        "stripped": "открой блокнот",
    },
    {
        "text": "привет скайнет",
        "has_hotword": False,
        "only_hotword": False,
        "stripped": "",
    },
    {
        "text": "скайнетик открой блокнот",
        "has_hotword": False,
        "only_hotword": False,
        "stripped": "",
    },
]


ACK_CASES: List[Case] = [
    {
        "text": "слушаю",
        "is_ack": True,
        "ignore_during_ack": True,
    },
    {
        "text": "слушай",
        "is_ack": True,
        "ignore_during_ack": True,
    },
    {
        "text": "скайнет",
        "is_ack": False,
        "ignore_during_ack": True,
    },
    {
        "text": "скайнет открой блокнот",
        "is_ack": False,
        "ignore_during_ack": False,
    },
    {
        "text": "открой блокнот",
        "is_ack": False,
        "ignore_during_ack": False,
    },
]


def _check_equal(name: str, expected: Any, actual: Any) -> str | None:
    if expected != actual:
        return f"{name}: expected={expected!r}, actual={actual!r}"
    return None


def main() -> int:
    fail_count = 0

    print("=== HOTWORD UTILS EVAL REPORT ===")

    print()
    print("--- HOTWORD CASES ---")
    for case in HOTWORD_CASES:
        text = str(case["text"])

        actual_has = has_hotword(text, hotwords=HOTWORDS)
        actual_only = is_only_hotword(text, hotwords=HOTWORDS)
        actual_stripped = strip_hotword(text, hotwords=HOTWORDS)

        errors = [
            err
            for err in (
                _check_equal("has_hotword", case["has_hotword"], actual_has),
                _check_equal("only_hotword", case["only_hotword"], actual_only),
                _check_equal("stripped", case["stripped"], actual_stripped),
            )
            if err
        ]

        print(
            json.dumps(
                {
                    "text": text,
                    "has_hotword": actual_has,
                    "only_hotword": actual_only,
                    "stripped": actual_stripped,
                },
                ensure_ascii=False,
            )
        )

        if errors:
            fail_count += 1
            for error in errors:
                print(f"[FAIL] {error}")
        else:
            print("[OK] hotword case")

    print()
    print("--- ACK CASES ---")
    for case in ACK_CASES:
        text = str(case["text"])

        actual_ack = is_ack_echo(text, ack_text=ACK_TEXT)
        actual_ignore = should_ignore_during_ack_window(
            text,
            hotwords=HOTWORDS,
            ack_text=ACK_TEXT,
        )

        errors = [
            err
            for err in (
                _check_equal("is_ack", case["is_ack"], actual_ack),
                _check_equal("ignore_during_ack", case["ignore_during_ack"], actual_ignore),
            )
            if err
        ]

        print(
            json.dumps(
                {
                    "text": text,
                    "is_ack": actual_ack,
                    "ignore_during_ack": actual_ignore,
                },
                ensure_ascii=False,
            )
        )

        if errors:
            fail_count += 1
            for error in errors:
                print(f"[FAIL] {error}")
        else:
            print("[OK] ack case")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "hotword_cases": len(HOTWORD_CASES),
                "ack_cases": len(ACK_CASES),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())