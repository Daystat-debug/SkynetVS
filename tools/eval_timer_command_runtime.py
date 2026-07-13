from __future__ import annotations

import json
from typing import Any, Mapping

from dotenv import load_dotenv

load_dotenv()

from modules.command_decision import (
    build_command_decision,
)
from modules.command_outcome import (
    classify_command_outcome,
)
from modules.command_runtime import (
    handle_command_runtime,
)


class FakeLogger:
    def event(
        self,
        kind: str,
        payload: dict[str, Any],
    ) -> None:
        _ = kind
        _ = payload

    def inbox(
        self,
        text: str,
        meta: Mapping[str, Any],
    ) -> None:
        _ = text
        _ = meta


class FakeRouter:
    def __init__(
        self,
        events: list[str],
    ) -> None:
        self.events = events

    def execute(
        self,
        meta: Mapping[str, Any],
    ) -> None:
        intent = str(
            meta.get("intent") or ""
        )
        self.events.append(
            f"execute:{intent}"
        )

    def reply(
        self,
        meta: Mapping[str, Any],
    ) -> str:
        intent = str(
            meta.get("intent") or ""
        )
        return f"REPLY:{intent}"


class Dummy:
    pass


class FakeLearningMemory:
    def log_action_failure(
        self,
        **kwargs: Any,
    ) -> None:
        _ = kwargs


def run_case(
    *,
    intent: str,
    slots: dict[str, Any],
) -> dict[str, Any]:
    events: list[str] = []

    meta = {
        "intent": intent,
        "confidence": 1.0,
        "slots": slots,
    }

    decision = build_command_decision(
        meta,
        accept_conf=0.35,
    )

    outcome = classify_command_outcome(
        meta,
        decision,
    )

    def reply_text(
        value: Mapping[str, Any],
    ) -> str:
        current_intent = str(
            value.get("intent") or ""
        )
        events.append(
            f"reply:{current_intent}"
        )
        return f"REPLY:{current_intent}"

    def say(
        stt: Any,
        tts: Any,
        text: str,
        *,
        mute_stt: bool = True,
    ) -> float:
        _ = stt
        _ = tts
        _ = mute_stt
        events.append(f"say:{text}")
        return 100.0

    result = handle_command_runtime(
        raw_text="test",
        final_text="test",
        meta=meta,
        decision=decision,
        outcome=outcome,
        learning_memory=FakeLearningMemory(),
        logger=FakeLogger(),
        router=FakeRouter(events),
        mode_manager=Dummy(),
        stt=Dummy(),
        tts=Dummy(),
        say_func=say,
        say_interruptible_func=(
            lambda tts, text: 200.0
        ),
        reply_text_func=reply_text,
        current_mode_name_func=lambda: "direct",
        cancel_cmd_timer_func=lambda: None,
    )

    return {
        "events": events,
        "reason": result.reason,
    }


def main() -> int:
    fail_count = 0

    cases = [
        {
            "name": "SET_TIMER EXECUTES BEFORE SAY",
            "intent": "SET_TIMER",
            "slots": {
                "duration_seconds": 30,
            },
            "expected": {
                "events": [
                    "reply:SET_TIMER",
                    "execute:SET_TIMER",
                    "say:REPLY:SET_TIMER",
                ],
                "reason": "executed",
            },
        },
        {
            "name": "CANCEL_TIMER EXECUTES BEFORE SAY",
            "intent": "CANCEL_TIMER",
            "slots": {},
            "expected": {
                "events": [
                    "reply:CANCEL_TIMER",
                    "execute:CANCEL_TIMER",
                    "say:REPLY:CANCEL_TIMER",
                ],
                "reason": "executed",
            },
        },
        {
            "name": "NORMAL ACTION STILL SAYS FIRST",
            "intent": "OPEN_URL",
            "slots": {
                "url": "https://example.com",
            },
            "expected": {
                "events": [
                    "reply:OPEN_URL",
                    "say:REPLY:OPEN_URL",
                    "execute:OPEN_URL",
                ],
                "reason": "executed",
            },
        },
    ]

    for case in cases:
        actual = run_case(
            intent=str(case["intent"]),
            slots=dict(case["slots"]),
        )
        expected = dict(case["expected"])
        ok = actual == expected

        print()
        print(f"=== {case['name']} ===")
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
            print(f"[OK] {case['name']}")
        else:
            fail_count += 1
            print(f"[FAIL] {case['name']}")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "case_count": len(cases),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())