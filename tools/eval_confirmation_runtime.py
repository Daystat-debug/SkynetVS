from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.confirmation_runtime import handle_pending_confirmation_phrase


class FakeModeManager:
    def __init__(self, *, pending: dict[str, Any] | None, command_window_open: bool) -> None:
        self.pending = pending
        self.command_window_open = command_window_open
        self.events: List[str] = []

    def has_pending_confirmation(self) -> bool:
        return self.pending is not None

    def get_pending_confirmation(self) -> dict[str, Any] | None:
        return self.pending

    def clear_pending_confirmation(self) -> None:
        self.events.append("mode.clear_pending_confirmation")
        self.pending = None

    def is_command_window_open(self) -> bool:
        return self.command_window_open


class FakeRouter:
    def __init__(self) -> None:
        self.events: List[str] = []

    def execute(self, meta: dict[str, Any]) -> None:
        intent = str(meta.get("intent") or "")
        self.events.append(f"router.execute:{intent}")


class FakeLearningMemory:
    def __init__(self) -> None:
        self.events: List[str] = []

    def log_action_failure(self, **kwargs: Any) -> None:
        _ = kwargs
        self.events.append("learning.log_action_failure")


class FakeExtender:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


def say_func(stt: Any, tts: Any, text: str) -> float:
    _ = stt
    _ = tts
    return 111.0 if text else 0.0


def pick_named_response(name: str) -> str | None:
    values = {
        "CONFIRM_OK": "Подтверждаю. Выполняю.",
        "CONFIRM_CANCEL": "Отменено.",
        "CONFIRM_REPEAT": "Скажи да или нет.",
    }
    return values.get(name)


def is_yes(text: str) -> bool:
    return text.strip().lower() in {"да", "ага"}


def is_no(text: str) -> bool:
    return text.strip().lower() in {"нет", "отмена"}


def current_mode_name() -> str:
    return "direct"


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "no pending confirmation",
        "phrase": "да",
        "pending": None,
        "command_window_open": False,
        "expected": {
            "handled": False,
            "reason": "no_pending_confirmation",
            "mode_events": [],
            "router_events": [],
            "learning_events": [],
            "extend_calls": 0,
            "last_tts_end": None,
        },
    },
    {
        "name": "yes executes pending command",
        "phrase": "да",
        "pending": {
            "meta": {
                "intent": "OPEN_URL",
                "confidence": 1.0,
                "slots": {"url": "https://www.youtube.com"},
                "_text": "открой ютуб",
            }
        },
        "command_window_open": True,
        "expected": {
            "handled": True,
            "reason": "confirmed_executed",
            "mode_events": ["mode.clear_pending_confirmation"],
            "router_events": ["router.execute:OPEN_URL"],
            "learning_events": [],
            "extend_calls": 1,
            "last_tts_end": 111.0,
        },
    },
    {
        "name": "yes does not execute if missing slots",
        "phrase": "да",
        "pending": {
            "meta": {
                "intent": "OPEN_URL",
                "confidence": 1.0,
                "slots": {},
                "_text": "открой",
            }
        },
        "command_window_open": False,
        "expected": {
            "handled": True,
            "reason": "confirmed_not_runnable",
            "mode_events": ["mode.clear_pending_confirmation"],
            "router_events": [],
            "learning_events": [],
            "extend_calls": 0,
            "last_tts_end": 111.0,
        },
    },
    {
        "name": "no cancels pending confirmation",
        "phrase": "нет",
        "pending": {
            "meta": {
                "intent": "EMPTY_RECYCLE_BIN",
                "confidence": 1.0,
                "slots": {},
                "_text": "очисти корзину",
            }
        },
        "command_window_open": True,
        "expected": {
            "handled": True,
            "reason": "confirmation_cancelled",
            "mode_events": ["mode.clear_pending_confirmation"],
            "router_events": [],
            "learning_events": [],
            "extend_calls": 1,
            "last_tts_end": 111.0,
        },
    },
    {
        "name": "unclear answer asks repeat",
        "phrase": "может быть",
        "pending": {
            "meta": {
                "intent": "EMPTY_RECYCLE_BIN",
                "confidence": 1.0,
                "slots": {},
                "_text": "очисти корзину",
            }
        },
        "command_window_open": True,
        "expected": {
            "handled": True,
            "reason": "confirmation_repeat",
            "mode_events": [],
            "router_events": [],
            "learning_events": [],
            "extend_calls": 1,
            "last_tts_end": 111.0,
        },
    },
]


def main() -> int:
    fail_count = 0

    print("=== CONFIRMATION RUNTIME EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        mode_manager = FakeModeManager(
            pending=case["pending"],
            command_window_open=bool(case["command_window_open"]),
        )
        router = FakeRouter()
        learning_memory = FakeLearningMemory()
        extender = FakeExtender()

        result = handle_pending_confirmation_phrase(
            str(case["phrase"]),
            mode_manager=mode_manager,
            router=router,
            learning_memory=learning_memory,
            stt=None,
            tts=None,
            say_func=say_func,
            pick_named_response_func=pick_named_response,
            is_confirmation_yes_func=is_yes,
            is_confirmation_no_func=is_no,
            accept_conf=0.35,
            current_mode_name_func=current_mode_name,
            extend_cmd_window_func=extender,
        )

        actual = {
            "handled": result.handled,
            "reason": result.reason,
            "mode_events": mode_manager.events,
            "router_events": router.events,
            "learning_events": learning_memory.events,
            "extend_calls": extender.calls,
            "last_tts_end": result.last_tts_end,
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
            print("[OK] confirmation runtime case")
        else:
            fail_count += 1
            print("[FAIL] confirmation runtime mismatch")

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