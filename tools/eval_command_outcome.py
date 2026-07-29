from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.command_decision import build_command_decision
from modules.command_outcome import classify_command_outcome
from modules.core.config import Settings


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "not accepted",
        "meta": {
            "intent": None,
            "confidence": 0.0,
            "slots": {},
        },
        "expected_kind": "not_accepted",
    },
    {
        "name": "missing slots",
        "meta": {
            "intent": "OPEN_URL",
            "confidence": 1.0,
            "slots": {},
        },
        "expected_kind": "missing_required_slots",
    },
    {
        "name": "confirmation required",
        "meta": {
            "intent": "EMPTY_RECYCLE_BIN",
            "confidence": 1.0,
            "slots": {},
        },
        "expected_kind": "confirmation_required",
    },
    {
        "name": "dictation on",
        "meta": {
            "intent": "DICTATION_MODE_ON",
            "confidence": 1.0,
            "slots": {},
        },
        "expected_kind": "dictation_on",
    },
    {
        "name": "dictation off",
        "meta": {
            "intent": "DICTATION_MODE_OFF",
            "confidence": 1.0,
            "slots": {},
        },
        "expected_kind": "dictation_off",
    },
    {
        "name": "weather interruptible reply",
        "meta": {
            "intent": "WEATHER",
            "confidence": 1.0,
            "slots": {},
        },
        "expected_kind": "interruptible_reply",
    },
    {
        "name": "normal execute",
        "meta": {
            "intent": "OPEN_URL",
            "confidence": 1.0,
            "slots": {
                "url": "https://www.youtube.com",
            },
        },
        "expected_kind": "execute",
    },
    {
        "name": "set volume execute",
        "meta": {
            "intent": "SET_VOLUME",
            "confidence": 1.0,
            "slots": {
                "volume": 50,
            },
        },
        "expected_kind": "execute",
    },
]


def main() -> int:
    settings = Settings.from_env()
    fail_count = 0

    print("=== COMMAND OUTCOME EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        meta = dict(case["meta"])

        decision = build_command_decision(
            meta,
            accept_conf=settings.nlu_accept_conf,
        )

        outcome = classify_command_outcome(
            meta,
            decision,
        )

        expected_kind = str(case["expected_kind"])
        ok = outcome.kind == expected_kind

        print()
        print(f"{idx}. {case['name']}")
        print(
            json.dumps(
                {
                    "meta": meta,
                    "decision": decision.to_dict(),
                    "expected_kind": expected_kind,
                    "actual_kind": outcome.kind,
                    "intent": outcome.intent,
                    "ok": ok,
                },
                ensure_ascii=False,
            )
        )

        if ok:
            print("[OK] outcome case")
        else:
            fail_count += 1
            print("[FAIL] outcome mismatch")

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