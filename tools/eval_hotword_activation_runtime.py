from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.hotword_activation_runtime import handle_hotword_activation_phrase


class FakeModeManager:
    def __init__(self, *, command_window_open: bool) -> None:
        self.command_window_open = command_window_open

    def is_command_window_open(self) -> bool:
        return self.command_window_open


class FakeOpenCommandWindow:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


class FakeImmediateCommandHandler:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, command_text: str, *, immediate_label: str) -> dict[str, Any]:
        self.calls.append(
            {
                "command_text": command_text,
                "immediate_label": immediate_label,
            }
        )

        return {
            "intent": "FAKE_INTENT",
            "confidence": 1.0,
            "slots": {},
            "_text": command_text,
        }


def norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def has_hotword(text: str) -> bool:
    t = norm(text)
    return t == "скайнет" or t.startswith("скайнет ") or t.startswith("скайнет,")


def strip_hotword(text: str) -> str:
    t = norm(text)

    if t == "скайнет":
        return ""

    if t.startswith("скайнет "):
        return t[len("скайнет"):].strip(" ,.!?:;—-")

    if t.startswith("скайнет,"):
        return t[len("скайнет"):].strip(" ,.!?:;—-")

    return ""


def say_func(stt: Any, tts: Any, text: str, *, mute_stt: bool = True) -> float:
    _ = stt
    _ = tts
    _ = mute_stt

    return 222.0 if text else 0.0


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "no hotword does nothing",
        "phrase": "открой блокнот",
        "command_window_open": False,
        "expected": {
            "handled": False,
            "phrase": "открой блокнот",
            "reason": "no_hotword_activation",
            "last_tts_end": None,
            "ack_ignore_until": None,
            "open_calls": 0,
            "immediate_calls": [],
        },
    },
    {
        "name": "hotword with command outside window runs immediately",
        "phrase": "скайнет открой блокнот",
        "command_window_open": False,
        "expected": {
            "handled": True,
            "phrase": "скайнет открой блокнот",
            "reason": "immediate_hotword_command",
            "last_tts_end": None,
            "ack_ignore_until": None,
            "open_calls": 0,
            "immediate_calls": [
                {
                    "command_text": "открой блокнот",
                    "immediate_label": "immediate",
                }
            ],
        },
    },
    {
        "name": "bare hotword outside window opens command window",
        "phrase": "скайнет",
        "command_window_open": False,
        "expected": {
            "handled": True,
            "phrase": "скайнет",
            "reason": "command_window_opened",
            "last_tts_end": 222.0,
            "ack_ignore_until": 10.5,
            "open_calls": 1,
            "immediate_calls": [],
        },
    },
    {
        "name": "hotword with command inside window strips hotword and continues",
        "phrase": "скайнет открой блокнот",
        "command_window_open": True,
        "expected": {
            "handled": False,
            "phrase": "открой блокнот",
            "reason": "hotword_stripped_in_command_window",
            "last_tts_end": None,
            "ack_ignore_until": None,
            "open_calls": 0,
            "immediate_calls": [],
        },
    },
    {
        "name": "bare hotword inside window stays phrase for command-window block",
        "phrase": "скайнет",
        "command_window_open": True,
        "expected": {
            "handled": False,
            "phrase": "скайнет",
            "reason": "hotword_stripped_in_command_window",
            "last_tts_end": None,
            "ack_ignore_until": None,
            "open_calls": 0,
            "immediate_calls": [],
        },
    },
]


def main() -> int:
    fail_count = 0

    print("=== HOTWORD ACTIVATION RUNTIME EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        mode_manager = FakeModeManager(
            command_window_open=bool(case["command_window_open"]),
        )
        opener = FakeOpenCommandWindow()
        immediate_handler = FakeImmediateCommandHandler()

        result = handle_hotword_activation_phrase(
            str(case["phrase"]),
            mode_manager=mode_manager,
            stt=None,
            tts=None,
            now=10.0,
            ack_text="Слушаю",
            ack_ignore_sec=0.5,
            say_func=say_func,
            has_hotword_func=has_hotword,
            strip_hotword_func=strip_hotword,
            handle_command_text_func=immediate_handler,
            open_cmd_window_func=opener,
        )

        actual = {
            "handled": result.handled,
            "phrase": result.phrase,
            "reason": result.reason,
            "last_tts_end": result.last_tts_end,
            "ack_ignore_until": result.ack_ignore_until,
            "open_calls": opener.calls,
            "immediate_calls": immediate_handler.calls,
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
            print("[OK] hotword activation case")
        else:
            fail_count += 1
            print("[FAIL] hotword activation mismatch")

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