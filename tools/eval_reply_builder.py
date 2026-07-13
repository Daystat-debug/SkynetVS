from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.reply_builder import build_reply_text


class FakeRouter:
    def __init__(self, reply_text: str = "BASE_REPLY") -> None:
        self.reply_text = reply_text
        self.calls = 0

    def reply(self, meta: dict[str, Any]) -> str:
        _ = meta
        self.calls += 1
        return self.reply_text


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "accepted high confidence uses base reply",
        "meta": {
            "intent": "OPEN_APP",
            "confidence": 0.90,
            "slots": {"app": "notepad"},
            "say": "META_SAY",
        },
        "accept_conf": 0.35,
        "say_conf": 0.55,
        "router_reply": "BASE_REPLY",
        "expected_text": "BASE_REPLY",
        "expected_router_calls": 1,
    },
    {
        "name": "forced base intent uses base reply even with lower confidence",
        "meta": {
            "intent": "WEATHER",
            "confidence": 0.40,
            "slots": {},
            "say": "META_SAY",
        },
        "accept_conf": 0.35,
        "say_conf": 0.55,
        "router_reply": "WEATHER_REPLY",
        "expected_text": "WEATHER_REPLY",
        "expected_router_calls": 1,
    },
    {
        "name": "not accepted uses meta fallback",
        "meta": {
            "intent": None,
            "confidence": 0.0,
            "slots": {},
            "say": "Не понял команду.",
        },
        "accept_conf": 0.35,
        "say_conf": 0.55,
        "router_reply": "SHOULD_NOT_BE_USED",
        "expected_text": "Не понял команду.",
        "expected_router_calls": 0,
    },
    {
        "name": "not accepted without say uses default fallback",
        "meta": {
            "intent": None,
            "confidence": 0.0,
            "slots": {},
        },
        "accept_conf": 0.35,
        "say_conf": 0.55,
        "router_reply": "SHOULD_NOT_BE_USED",
        "expected_text": "Не понял команду. Повтори, пожалуйста.",
        "expected_router_calls": 0,
    },
    {
        "name": (
            "timer status forces "
            "dynamic base reply"
        ),
        "meta": {
            "intent": "TIMER_STATUS",
            "confidence": 0.40,
            "slots": {},
            "say": "META_SAY",
        },
        "accept_conf": 0.35,
        "say_conf": 0.55,
        "router_reply": "TIMER_STATUS_REPLY",
        "expected_text": "TIMER_STATUS_REPLY",
        "expected_router_calls": 1,
    },
]


def main() -> int:
    fail_count = 0

    print("=== REPLY BUILDER EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        router = FakeRouter(str(case["router_reply"]))

        actual_text = build_reply_text(
            router=router,
            meta=case["meta"],
            accept_conf=float(case["accept_conf"]),
            say_conf=float(case["say_conf"]),
        )

        expected_text = str(case["expected_text"])
        expected_router_calls = int(case["expected_router_calls"])

        errors: List[str] = []

        if actual_text != expected_text:
            errors.append(
                f"text: expected={expected_text!r}, actual={actual_text!r}"
            )

        if router.calls != expected_router_calls:
            errors.append(
                f"router_calls: expected={expected_router_calls}, actual={router.calls}"
            )

        print()
        print(f"{idx}. {case['name']}")
        print(
            json.dumps(
                {
                    "actual_text": actual_text,
                    "expected_text": expected_text,
                    "router_calls": router.calls,
                    "expected_router_calls": expected_router_calls,
                },
                ensure_ascii=False,
            )
        )

        if errors:
            fail_count += 1
            for error in errors:
                print(f"[FAIL] {error}")
        else:
            print("[OK] reply builder case")

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