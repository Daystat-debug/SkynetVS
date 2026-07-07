from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping

from dotenv import load_dotenv

load_dotenv()

from modules.command_decision import build_command_decision
from modules.command_outcome import classify_command_outcome
from modules.command_runtime import handle_command_runtime


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
    def __init__(self, *, fail_execute: bool = False) -> None:
        self.events: List[str] = []
        self.fail_execute = fail_execute

    def reply(self, meta: Mapping[str, Any]) -> str:
        intent = str(meta.get("intent") or "")
        self.events.append(f"reply:{intent}")
        return f"ROUTER_REPLY:{intent}"

    def execute(self, meta: Mapping[str, Any]) -> None:
        intent = str(meta.get("intent") or "")
        self.events.append(f"execute:{intent}")

        if self.fail_execute:
            raise RuntimeError("fake execute failure")


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

    def log_nlu_hard_case(self, **kwargs: Any) -> None:
        _ = kwargs
        self.events.append("log_nlu_hard_case")

    def log_action_failure(self, **kwargs: Any) -> None:
        _ = kwargs
        self.events.append("log_action_failure")


class FakeCancelTimer:
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
        self.events.append(f"say:{text}")
        return 100.0

    def say_interruptible(self, tts: Any, text: str) -> float:
        _ = tts
        self.events.append(f"say_interruptible:{text}")
        return 200.0


def reply_text(meta: Mapping[str, Any]) -> str:
    intent = str(meta.get("intent") or "")
    return f"REPLY:{intent or 'NONE'}"


def current_mode_name() -> str:
    return "direct"


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "not accepted runtime",
        "meta": {
            "intent": None,
            "confidence": 0.0,
            "slots": {},
            "say": "Не понял.",
        },
        "expected": {
            "reason": "not_accepted",
            "logger_events": ["inbox"],
            "router_events": [],
            "mode_events": [],
            "learning_events": ["log_nlu_hard_case"],
            "speech_events": ["say:REPLY:NONE"],
            "cancel_calls": 0,
            "last_tts_end": 100.0,
            "raised": False,
        },
    },
    {
        "name": "missing slots runtime",
        "meta": {
            "intent": "OPEN_URL",
            "confidence": 1.0,
            "slots": {},
        },
        "expected": {
            "reason": "missing_required_slots",
            "logger_events": ["event:missing_required_slots_blocked"],
            "router_events": ["reply:OPEN_URL"],
            "mode_events": [],
            "learning_events": [],
            "speech_events": ["say:ROUTER_REPLY:OPEN_URL"],
            "cancel_calls": 0,
            "last_tts_end": 100.0,
            "raised": False,
        },
    },
    {
        "name": "confirmation runtime",
        "meta": {
            "intent": "EMPTY_RECYCLE_BIN",
            "confidence": 1.0,
            "slots": {},
        },
        "expected": {
            "reason": "confirmation_required",
            "logger_events": [],
            "router_events": [],
            "mode_events": ["set_pending_confirmation:EMPTY_RECYCLE_BIN"],
            "learning_events": [],
            "speech_events": ["say:Ты уверен, что хочешь очистить корзину?"],
            "cancel_calls": 0,
            "last_tts_end": 100.0,
            "raised": False,
        },
    },
    {
        "name": "dictation on runtime",
        "meta": {
            "intent": "DICTATION_MODE_ON",
            "confidence": 1.0,
            "slots": {},
        },
        "expected": {
            "reason": "dictation_on",
            "logger_events": [],
            "router_events": [],
            "mode_events": ["enter_dictation_mode", "close_command_window"],
            "learning_events": [],
            "speech_events": ["say:REPLY:DICTATION_MODE_ON"],
            "cancel_calls": 1,
            "last_tts_end": 100.0,
            "raised": False,
        },
    },
    {
        "name": "dictation off runtime",
        "meta": {
            "intent": "DICTATION_MODE_OFF",
            "confidence": 1.0,
            "slots": {},
        },
        "expected": {
            "reason": "dictation_off",
            "logger_events": [],
            "router_events": [],
            "mode_events": ["exit_dictation_mode"],
            "learning_events": [],
            "speech_events": ["say:REPLY:DICTATION_MODE_OFF"],
            "cancel_calls": 0,
            "last_tts_end": 100.0,
            "raised": False,
        },
    },
    {
        "name": "interruptible reply runtime",
        "meta": {
            "intent": "WEATHER",
            "confidence": 1.0,
            "slots": {},
        },
        "expected": {
            "reason": "interruptible_reply",
            "logger_events": [],
            "router_events": [],
            "mode_events": [],
            "learning_events": [],
            "speech_events": ["say_interruptible:REPLY:WEATHER"],
            "cancel_calls": 0,
            "last_tts_end": 200.0,
            "raised": False,
        },
    },
    {
        "name": "execute runtime",
        "meta": {
            "intent": "OPEN_URL",
            "confidence": 1.0,
            "slots": {"url": "https://www.youtube.com"},
        },
        "expected": {
            "reason": "executed",
            "logger_events": [],
            "router_events": ["execute:OPEN_URL"],
            "mode_events": [],
            "learning_events": [],
            "speech_events": ["say:REPLY:OPEN_URL"],
            "cancel_calls": 0,
            "last_tts_end": 100.0,
            "raised": False,
        },
    },
    {
        "name": "execute failure runtime",
        "meta": {
            "intent": "OPEN_URL",
            "confidence": 1.0,
            "slots": {"url": "https://www.youtube.com"},
        },
        "fail_execute": True,
        "expected": {
            "reason": None,
            "logger_events": [],
            "router_events": ["execute:OPEN_URL"],
            "mode_events": [],
            "learning_events": ["log_action_failure"],
            "speech_events": ["say:REPLY:OPEN_URL"],
            "cancel_calls": 0,
            "last_tts_end": None,
            "raised": True,
        },
    },
]


def main() -> int:
    fail_count = 0

    print("=== COMMAND RUNTIME EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        logger = FakeLogger()
        router = FakeRouter(fail_execute=bool(case.get("fail_execute") or False))
        mode_manager = FakeModeManager()
        learning_memory = FakeLearningMemory()
        cancel_timer = FakeCancelTimer()
        speech = SpeechRecorder()

        meta = dict(case["meta"])
        decision = build_command_decision(meta, accept_conf=0.35)
        outcome = classify_command_outcome(meta, decision)

        result_reason = None
        result_last_tts_end = None
        raised = False

        try:
            result = handle_command_runtime(
                raw_text=str(meta.get("_text") or ""),
                final_text=str(meta.get("_text") or ""),
                meta=meta,
                decision=decision,
                outcome=outcome,
                learning_memory=learning_memory,
                logger=logger,
                router=router,
                mode_manager=mode_manager,
                stt=None,
                tts=None,
                say_func=speech.say,
                say_interruptible_func=speech.say_interruptible,
                reply_text_func=reply_text,
                current_mode_name_func=current_mode_name,
                cancel_cmd_timer_func=cancel_timer,
            )
            result_reason = result.reason
            result_last_tts_end = result.last_tts_end
        except RuntimeError:
            raised = True

        actual = {
            "reason": result_reason,
            "logger_events": logger.events,
            "router_events": router.events,
            "mode_events": mode_manager.events,
            "learning_events": learning_memory.events,
            "speech_events": speech.events,
            "cancel_calls": cancel_timer.calls,
            "last_tts_end": result_last_tts_end,
            "raised": raised,
        }

        expected = dict(case["expected"])
        ok = actual == expected

        print()
        print(f"{idx}. {case['name']}")
        print(
            json.dumps(
                {
                    "meta": meta,
                    "decision": decision.to_dict(),
                    "outcome": outcome.__dict__,
                    "expected": expected,
                    "actual": actual,
                    "ok": ok,
                },
                ensure_ascii=False,
            )
        )

        if ok:
            print("[OK] command runtime case")
        else:
            fail_count += 1
            print("[FAIL] command runtime mismatch")

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