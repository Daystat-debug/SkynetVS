from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.phrase_guards import check_phrase_preprocessing_guards


Case = Dict[str, Any]


def ignore_ack_only(text: str) -> bool:
    return text in {"слушаю", "слушай", "скайнет"}


def ignore_nothing(text: str) -> bool:
    _ = text
    return False


CASES: List[Case] = [
    {
        "name": "ack echo inside ack window is ignored",
        "phrase": "слушаю",
        "now": 10.0,
        "ack_ignore_until": 11.0,
        "last_tts_end": 0.0,
        "ignore_after_tts_sec": 1.0,
        "is_dictation_mode": False,
        "ack_func": ignore_ack_only,
        "expected": {
            "ignored": True,
            "reason": "stt_ignored_ack_window",
        },
    },
    {
        "name": "bare hotword inside ack window is ignored",
        "phrase": "скайнет",
        "now": 10.0,
        "ack_ignore_until": 11.0,
        "last_tts_end": 0.0,
        "ignore_after_tts_sec": 1.0,
        "is_dictation_mode": False,
        "ack_func": ignore_ack_only,
        "expected": {
            "ignored": True,
            "reason": "stt_ignored_ack_window",
        },
    },
    {
        "name": "normal phrase inside ack window is not ignored by ack guard",
        "phrase": "открой блокнот",
        "now": 10.0,
        "ack_ignore_until": 11.0,
        "last_tts_end": 0.0,
        "ignore_after_tts_sec": 1.0,
        "is_dictation_mode": False,
        "ack_func": ignore_ack_only,
        "expected": {
            "ignored": False,
            "reason": None,
        },
    },
    {
        "name": "phrase right after tts is ignored outside dictation",
        "phrase": "открой блокнот",
        "now": 10.5,
        "ack_ignore_until": 0.0,
        "last_tts_end": 10.0,
        "ignore_after_tts_sec": 1.0,
        "is_dictation_mode": False,
        "ack_func": ignore_nothing,
        "expected": {
            "ignored": True,
            "reason": "stt_ignored_after_tts",
        },
    },
    {
        "name": "phrase right after tts is not ignored in dictation",
        "phrase": "печатаю текст",
        "now": 10.5,
        "ack_ignore_until": 0.0,
        "last_tts_end": 10.0,
        "ignore_after_tts_sec": 1.0,
        "is_dictation_mode": True,
        "ack_func": ignore_nothing,
        "expected": {
            "ignored": False,
            "reason": None,
        },
    },
    {
        "name": "old phrase after tts window is not ignored",
        "phrase": "открой блокнот",
        "now": 12.0,
        "ack_ignore_until": 0.0,
        "last_tts_end": 10.0,
        "ignore_after_tts_sec": 1.0,
        "is_dictation_mode": False,
        "ack_func": ignore_nothing,
        "expected": {
            "ignored": False,
            "reason": None,
        },
    },
]


def main() -> int:
    fail_count = 0

    print("=== PHRASE GUARDS EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        result = check_phrase_preprocessing_guards(
            str(case["phrase"]),
            now=float(case["now"]),
            ack_ignore_until=float(case["ack_ignore_until"]),
            last_tts_end=float(case["last_tts_end"]),
            ignore_after_tts_sec=float(case["ignore_after_tts_sec"]),
            is_dictation_mode=bool(case["is_dictation_mode"]),
            should_ignore_during_ack_window_func=case["ack_func"],
        )

        actual = {
            "ignored": result.ignored,
            "reason": result.reason,
        }

        expected = dict(case["expected"])
        ok = actual == expected

        print()
        print(f"{idx}. {case['name']}")
        print(
            json.dumps(
                {
                    "phrase": case["phrase"],
                    "expected": expected,
                    "actual": actual,
                    "ok": ok,
                },
                ensure_ascii=False,
            )
        )

        if ok:
            print("[OK] phrase guard case")
        else:
            fail_count += 1
            print("[FAIL] phrase guard mismatch")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "total_cases": len(CASES),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())