from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.command_window_runtime import handle_command_window_phrase


class FakeModeManager:
    def __init__(
        self,
        *,
        command_window_open: bool,
        pending_text: str | None = None,
        pending_ts: float = 0.0,
    ) -> None:
        self.command_window_open = command_window_open
        self.pending_text = pending_text
        self.pending_ts = pending_ts
        self.events: List[str] = []

    def is_command_window_open(self) -> bool:
        return self.command_window_open

    def has_pending_command(self) -> bool:
        return self.pending_text is not None

    def get_pending_command_text(self) -> str:
        return self.pending_text or ""

    def get_pending_command_ts(self) -> float:
        return self.pending_ts

    def set_pending_command(self, text: str, ts: float) -> None:
        self.pending_text = text
        self.pending_ts = ts
        self.events.append(f"mode.set_pending:{text}")

    def clear_pending_command(self) -> None:
        self.events.append("mode.clear_pending")
        self.pending_text = None


class FakeLogger:
    def __init__(self) -> None:
        self.events: List[str] = []

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        _ = payload
        self.events.append(kind)


class FakeExtender:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


class FakeCloser:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, reason: str, *, speak_close: bool) -> None:
        self.calls.append(
            {
                "reason": reason,
                "speak_close": speak_close,
            }
        )


class FakeCommandHandler:
    def __init__(self, *, stop_on: str | None = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.stop_on = stop_on

    def __call__(self, command_text: str, *, immediate_label: str) -> dict[str, Any]:
        self.calls.append(
            {
                "command_text": command_text,
                "immediate_label": immediate_label,
            }
        )

        if self.stop_on and command_text == self.stop_on:
            return {
                "intent": "STOP_LISTEN",
                "confidence": 1.0,
                "slots": {},
                "_text": command_text,
            }

        return {
            "intent": "FAKE_INTENT",
            "confidence": 1.0,
            "slots": {},
            "_text": command_text,
        }


def norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def is_only_hotword(text: str) -> bool:
    return norm(text) in {"скайнет", "skynet"}


def merge_phrases(left: str, right: str) -> str:
    left_n = norm(left)
    right_n = norm(right)

    if not left_n:
        return right_n

    if not right_n:
        return left_n

    return f"{left_n} {right_n}"


def looks_incomplete(text: str) -> bool:
    return norm(text) in {"открой", "запусти", "переключи"}


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "window not open",
        "phrase": "открой блокнот",
        "window_open": False,
        "pending_text": None,
        "pending_ts": 0.0,
        "stop_on": None,
        "expected": {
            "handled": False,
            "reason": "command_window_not_open",
            "mode_events": [],
            "logger_events": [],
            "extend_calls": 0,
            "close_calls": [],
            "handler_calls": [],
        },
    },
    {
        "name": "bare hotword inside window is ignored",
        "phrase": "скайнет",
        "window_open": True,
        "pending_text": None,
        "pending_ts": 0.0,
        "stop_on": None,
        "expected": {
            "handled": True,
            "reason": "bare_hotword_ignored",
            "mode_events": [],
            "logger_events": ["cmd_ignore_bare_hotword"],
            "extend_calls": 1,
            "close_calls": [],
            "handler_calls": [],
        },
    },
    {
        "name": "incomplete command becomes pending",
        "phrase": "открой",
        "window_open": True,
        "pending_text": None,
        "pending_ts": 0.0,
        "stop_on": None,
        "expected": {
            "handled": True,
            "reason": "pending_fragment_set",
            "mode_events": ["mode.set_pending:открой"],
            "logger_events": ["cmd_pending_fragment"],
            "extend_calls": 1,
            "close_calls": [],
            "handler_calls": [],
        },
    },
    {
        "name": "pending fragment merges with next phrase",
        "phrase": "блокнот",
        "window_open": True,
        "pending_text": "открой",
        "pending_ts": 10.0,
        "stop_on": None,
        "expected": {
            "handled": True,
            "reason": "command_executed_window_extended",
            "mode_events": ["mode.clear_pending"],
            "logger_events": [],
            "extend_calls": 1,
            "close_calls": [],
            "handler_calls": [
                {
                    "command_text": "открой блокнот",
                    "immediate_label": "window",
                }
            ],
        },
    },
    {
        "name": "normal command executes and extends window",
        "phrase": "открой блокнот",
        "window_open": True,
        "pending_text": None,
        "pending_ts": 0.0,
        "stop_on": None,
        "expected": {
            "handled": True,
            "reason": "command_executed_window_extended",
            "mode_events": [],
            "logger_events": [],
            "extend_calls": 1,
            "close_calls": [],
            "handler_calls": [
                {
                    "command_text": "открой блокнот",
                    "immediate_label": "window",
                }
            ],
        },
    },
    {
        "name": "stop listen closes command window",
        "phrase": "стоп",
        "window_open": True,
        "pending_text": None,
        "pending_ts": 0.0,
        "stop_on": "стоп",
        "expected": {
            "handled": True,
            "reason": "stop_listen_closed_window",
            "mode_events": [],
            "logger_events": [],
            "extend_calls": 0,
            "close_calls": [
                {
                    "reason": "cmd_window_close_stop_intent",
                    "speak_close": False,
                }
            ],
            "handler_calls": [
                {
                    "command_text": "стоп",
                    "immediate_label": "window",
                }
            ],
        },
    },
]


def main() -> int:
    fail_count = 0

    print("=== COMMAND WINDOW RUNTIME EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        mode_manager = FakeModeManager(
            command_window_open=bool(case["window_open"]),
            pending_text=case["pending_text"],
            pending_ts=float(case["pending_ts"]),
        )
        logger = FakeLogger()
        extender = FakeExtender()
        closer = FakeCloser()
        handler = FakeCommandHandler(stop_on=case["stop_on"])

        result = handle_command_window_phrase(
            str(case["phrase"]),
            mode_manager=mode_manager,
            logger=logger,
            now=11.0,
            pending_command_wait_sec=1.2,
            is_only_hotword_func=is_only_hotword,
            norm_func=norm,
            merge_phrases_func=merge_phrases,
            looks_incomplete_command_func=looks_incomplete,
            handle_command_text_func=handler,
            extend_cmd_window_func=extender,
            close_cmd_window_func=closer,
        )

        actual = {
            "handled": result.handled,
            "reason": result.reason,
            "mode_events": mode_manager.events,
            "logger_events": logger.events,
            "extend_calls": extender.calls,
            "close_calls": closer.calls,
            "handler_calls": handler.calls,
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
            print("[OK] command window case")
        else:
            fail_count += 1
            print("[FAIL] command window mismatch")

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