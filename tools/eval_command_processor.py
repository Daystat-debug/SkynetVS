from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping

from dotenv import load_dotenv

load_dotenv()

from modules.command_processor import CommandProcessor
from modules.config import Settings


class FakeLogger:
    def __init__(self) -> None:
        self.events: List[str] = []

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        _ = payload
        self.events.append(f"event:{kind}")

    def inbox(self, text: str, meta: Mapping[str, Any]) -> None:
        _ = text
        _ = meta
        self.events.append("inbox")


class FakeRouter:
    def __init__(self) -> None:
        self.events: List[str] = []

    def preprocess(self, meta: dict[str, Any]) -> dict[str, Any]:
        return meta

    def reply(self, meta: Mapping[str, Any]) -> str:
        intent = str(meta.get("intent") or "NONE")
        self.events.append(f"reply:{intent}")
        return f"ROUTER_REPLY:{intent}"

    def execute(self, meta: Mapping[str, Any]) -> None:
        intent = str(meta.get("intent") or "NONE")
        self.events.append(f"execute:{intent}")


class FakeModeManager:
    def __init__(self) -> None:
        self.events: List[str] = []
        self.pending_confirmation: dict[str, Any] | None = None

    def set_pending_confirmation(self, payload: dict[str, Any]) -> None:
        self.pending_confirmation = payload
        intent = str((payload.get("meta") or {}).get("intent") or "")
        self.events.append(f"set_pending_confirmation:{intent}")

    def enter_dictation_mode(self) -> None:
        self.events.append("enter_dictation_mode")

    def exit_dictation_mode(self) -> None:
        self.events.append("exit_dictation_mode")

    def close_command_window(self) -> None:
        self.events.append("close_command_window")


class FakeLearningMemory:
    def __init__(self) -> None:
        self.events: List[str] = []

    def log_command(self, **kwargs: Any) -> None:
        _ = kwargs
        self.events.append("log_command")

    def log_resolver_candidate(self, **kwargs: Any) -> None:
        _ = kwargs
        self.events.append("log_resolver_candidate")

    def log_nlu_hard_case(self, **kwargs: Any) -> None:
        _ = kwargs
        self.events.append("log_nlu_hard_case")

    def log_action_failure(self, **kwargs: Any) -> None:
        _ = kwargs
        self.events.append("log_action_failure")


class FakeSTT:
    last_utterance_audio = b""
    samplerate = 16000


class FakeTTS:
    pass


class CancelTimer:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


class SpeechRecorder:
    def __init__(self) -> None:
        self.events: List[str] = []

    def say(self, stt: Any, tts: Any, text: str, *, mute_stt: bool = True) -> float:
        _ = stt
        _ = tts
        _ = mute_stt
        self.events.append("say")
        return 100.0

    def say_interruptible(self, tts: Any, text: str) -> float:
        _ = tts
        self.events.append("say_interruptible")
        return 200.0


def reply_text(meta: Mapping[str, Any]) -> str:
    intent = str(meta.get("intent") or "NONE")
    return f"REPLY:{intent}"


def current_mode_name() -> str:
    return "direct"


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "open url command",
        "text": "открой ютуб",
        "expected": {
            "intent": "OPEN_URL",
            "reason": "executed",
            "router_events": ["execute:OPEN_URL"],
            "mode_events": [],
            "learning_events": ["log_command"],
            "speech_events": ["say"],
            "cancel_calls": 0,
            "last_tts_end": 100.0,
        },
    },
    {
        "name": "not accepted command",
        "text": "открой",
        "expected": {
            "intent": None,
            "reason": "not_accepted",
            "router_events": [],
            "mode_events": [],
            "learning_events": ["log_command", "log_nlu_hard_case"],
            "speech_events": ["say"],
            "cancel_calls": 0,
            "last_tts_end": 100.0,
        },
    },
    {
        "name": "confirmation command",
        "text": "очисти корзину",
        "expected": {
            "intent": "EMPTY_RECYCLE_BIN",
            "reason": "confirmation_required",
            "router_events": [],
            "mode_events": ["set_pending_confirmation:EMPTY_RECYCLE_BIN"],
            "learning_events": ["log_command"],
            "speech_events": ["say"],
            "cancel_calls": 0,
            "last_tts_end": 100.0,
        },
    },
    {
        "name": "dictation on command",
        "text": "режим диктовки",
        "expected": {
            "intent": "DICTATION_MODE_ON",
            "reason": "dictation_on",
            "router_events": [],
            "mode_events": ["enter_dictation_mode", "close_command_window"],
            "learning_events": ["log_command"],
            "speech_events": ["say"],
            "cancel_calls": 1,
            "last_tts_end": 100.0,
        },
    },
    {
        "name": "weather interruptible command",
        "text": "какая погода",
        "expected": {
            "intent": "WEATHER",
            "reason": "interruptible_reply",
            "router_events": [],
            "mode_events": [],
            "learning_events": ["log_command"],
            "speech_events": ["say_interruptible"],
            "cancel_calls": 0,
            "last_tts_end": 200.0,
        },
    },
]


def main() -> int:
    settings = Settings.from_env()
    fail_count = 0

    print("=== COMMAND PROCESSOR EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        logger = FakeLogger()
        router = FakeRouter()
        mode_manager = FakeModeManager()
        learning_memory = FakeLearningMemory()
        cancel_timer = CancelTimer()
        speech = SpeechRecorder()

        processor = CommandProcessor(
            router=router,
            logger=logger,
            whisper=None,
            stt=FakeSTT(),
            tts=FakeTTS(),
            settings=settings,
            learning_memory=learning_memory,
            mode_manager=mode_manager,
            say_func=speech.say,
            say_interruptible_func=speech.say_interruptible,
            reply_text_func=reply_text,
            current_mode_name_func=current_mode_name,
            cancel_cmd_timer_func=cancel_timer,
            print_func=None,
        )

        result = processor.process(
            str(case["text"]),
            immediate_label="immediate",
        )

        actual = {
            "intent": result.meta.get("intent"),
            "reason": result.reason,
            "router_events": router.events,
            "mode_events": mode_manager.events,
            "learning_events": learning_memory.events,
            "speech_events": speech.events,
            "cancel_calls": cancel_timer.calls,
            "last_tts_end": result.last_tts_end,
        }

        expected = dict(case["expected"])
        ok = actual == expected

        print()
        print(f"{idx}. {case['name']}")
        print(
            json.dumps(
                {
                    "text": case["text"],
                    "expected": expected,
                    "actual": actual,
                    "ok": ok,
                },
                ensure_ascii=False,
            )
        )

        if ok:
            print("[OK] command processor case")
        else:
            fail_count += 1
            print("[FAIL] command processor mismatch")

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