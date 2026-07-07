from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from modules.phrase_event_processor import PhraseEventProcessor


class FakeSettings:
    ignore_after_tts_sec = 0.8
    nlu_accept_conf = 0.35
    ack_text = "Слушаю"
    ack_ignore_sec = 0.5


class FakeLogger:
    def __init__(self) -> None:
        self.events: List[str] = []

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        _ = payload
        self.events.append(kind)


class FakeModeManager:
    def is_dictation_mode(self) -> bool:
        return False


class ScenarioHandlers:
    def __init__(self, stage: str, *, hotword_phrase: str | None = None) -> None:
        self.stage = stage
        self.hotword_phrase = hotword_phrase
        self.calls: List[str] = []

    def speech_interrupt(self, *args: Any, **kwargs: Any) -> Any:
        _ = args
        _ = kwargs
        self.calls.append("speech_interrupt")

        if self.stage == "speech_interrupt_stopped":
            return SimpleNamespace(handled=True, stopped=True)

        if self.stage == "speech_interrupt_handled":
            return SimpleNamespace(handled=True, stopped=False)

        return SimpleNamespace(handled=False, stopped=False)

    def phrase_guard(self, *args: Any, **kwargs: Any) -> Any:
        _ = args
        _ = kwargs
        self.calls.append("phrase_guard")

        if self.stage == "phrase_guard_ignored":
            return SimpleNamespace(ignored=True, reason="stt_ignored_ack_window")

        return SimpleNamespace(ignored=False, reason=None)

    def confirmation(self, *args: Any, **kwargs: Any) -> Any:
        _ = args
        _ = kwargs
        self.calls.append("confirmation")

        if self.stage == "confirmation_handled":
            return SimpleNamespace(handled=True, reason="confirmation_yes", last_tts_end=111.0)

        return SimpleNamespace(handled=False, reason=None, last_tts_end=None)

    def dictation(self, *args: Any, **kwargs: Any) -> Any:
        _ = args
        _ = kwargs
        self.calls.append("dictation")

        if self.stage == "dictation_handled":
            return SimpleNamespace(handled=True, reason="dictation_typed", last_tts_end=112.0)

        return SimpleNamespace(handled=False, reason=None, last_tts_end=None)

    def hotword_activation(self, phrase: str, *args: Any, **kwargs: Any) -> Any:
        _ = args
        _ = kwargs
        self.calls.append("hotword_activation")

        if self.stage == "hotword_activation_handled":
            return SimpleNamespace(
                handled=True,
                phrase=phrase,
                reason="command_window_opened",
                last_tts_end=113.0,
                ack_ignore_until=77.0,
            )

        return SimpleNamespace(
            handled=False,
            phrase=self.hotword_phrase if self.hotword_phrase is not None else phrase,
            reason="no_hotword_activation",
            last_tts_end=None,
            ack_ignore_until=None,
        )

    def command_window(self, *args: Any, **kwargs: Any) -> Any:
        _ = args
        _ = kwargs
        self.calls.append("command_window")

        if self.stage == "command_window_handled":
            return SimpleNamespace(
                handled=True,
                reason="command_executed_window_extended",
            )

        return SimpleNamespace(
            handled=False,
            reason="command_window_not_open",
        )


class FakeCallbacks:
    def __init__(self) -> None:
        self.open_calls = 0
        self.extend_calls = 0
        self.close_calls = 0
        self.command_calls: List[str] = []

    def open_cmd_window(self) -> None:
        self.open_calls += 1

    def extend_cmd_window(self) -> None:
        self.extend_calls += 1

    def close_cmd_window(self, reason: str, *, speak_close: bool) -> None:
        _ = reason
        _ = speak_close
        self.close_calls += 1

    def handle_command_text(self, command_text: str, *, immediate_label: str) -> dict[str, Any]:
        self.command_calls.append(f"{immediate_label}:{command_text}")
        return {"intent": "FAKE", "confidence": 1.0, "slots": {}}


def false_predicate(text: str) -> bool:
    _ = text
    return False


def identity(text: str) -> str:
    return text


def fake_predict(text: str) -> dict[str, Any]:
    _ = text
    return {"intent": None, "confidence": 0.0, "slots": {}}


def fake_say(*args: Any, **kwargs: Any) -> float:
    _ = args
    _ = kwargs
    return 100.0


CASES: List[Dict[str, Any]] = [
    {
        "name": "speech interrupt stopped",
        "stage": "speech_interrupt_stopped",
        "expected": {
            "handled": True,
            "reason": "speech_interrupt_stopped",
            "last_tts_end": 10.0,
            "ack_ignore_until": None,
            "logger_events": [],
            "calls": ["speech_interrupt"],
        },
    },
    {
        "name": "phrase guard ignored",
        "stage": "phrase_guard_ignored",
        "expected": {
            "handled": True,
            "reason": "stt_ignored_ack_window",
            "last_tts_end": None,
            "ack_ignore_until": None,
            "logger_events": ["stt_ignored_ack_window"],
            "calls": ["speech_interrupt", "phrase_guard"],
        },
    },
    {
        "name": "confirmation handled",
        "stage": "confirmation_handled",
        "expected": {
            "handled": True,
            "reason": "confirmation_yes",
            "last_tts_end": 111.0,
            "ack_ignore_until": None,
            "logger_events": ["stt_phrase"],
            "calls": ["speech_interrupt", "phrase_guard", "confirmation"],
        },
    },
    {
        "name": "dictation handled",
        "stage": "dictation_handled",
        "expected": {
            "handled": True,
            "reason": "dictation_typed",
            "last_tts_end": 112.0,
            "ack_ignore_until": None,
            "logger_events": ["stt_phrase"],
            "calls": ["speech_interrupt", "phrase_guard", "confirmation", "dictation"],
        },
    },
    {
        "name": "hotword activation handled",
        "stage": "hotword_activation_handled",
        "expected": {
            "handled": True,
            "reason": "command_window_opened",
            "last_tts_end": 113.0,
            "ack_ignore_until": 77.0,
            "logger_events": ["stt_phrase"],
            "calls": [
                "speech_interrupt",
                "phrase_guard",
                "confirmation",
                "dictation",
                "hotword_activation",
            ],
        },
    },
    {
        "name": "command window handled",
        "stage": "command_window_handled",
        "expected": {
            "handled": True,
            "reason": "command_executed_window_extended",
            "last_tts_end": None,
            "ack_ignore_until": None,
            "logger_events": ["stt_phrase"],
            "calls": [
                "speech_interrupt",
                "phrase_guard",
                "confirmation",
                "dictation",
                "hotword_activation",
                "command_window",
            ],
        },
    },
    {
        "name": "no handler matched",
        "stage": "none",
        "expected": {
            "handled": False,
            "reason": "no_phrase_handler_matched",
            "last_tts_end": None,
            "ack_ignore_until": None,
            "logger_events": ["stt_phrase"],
            "calls": [
                "speech_interrupt",
                "phrase_guard",
                "confirmation",
                "dictation",
                "hotword_activation",
                "command_window",
            ],
        },
    },
]


def main() -> int:
    fail_count = 0

    print("=== PHRASE EVENT PROCESSOR EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        handlers = ScenarioHandlers(str(case["stage"]))
        logger = FakeLogger()
        callbacks = FakeCallbacks()

        processor = PhraseEventProcessor(
            tts=None,
            stt=None,
            logger=logger,
            settings=FakeSettings(),
            mode_manager=FakeModeManager(),
            learning_memory=None,
            typing_service=None,
            say_func=fake_say,
            has_hotword_func=false_predicate,
            strip_hotword_func=identity,
            is_only_hotword_func=false_predicate,
            norm_func=identity,
            is_dictation_stop_phrase_func=false_predicate,
            predict_func=fake_predict,
            is_accepted_func=lambda meta: False,
            pick_named_response_func=lambda *args, **kwargs: None,
            is_confirmation_yes_func=false_predicate,
            is_confirmation_no_func=false_predicate,
            current_mode_name_func=lambda: "direct",
            handle_command_text_func=callbacks.handle_command_text,
            open_cmd_window_func=callbacks.open_cmd_window,
            extend_cmd_window_func=callbacks.extend_cmd_window,
            close_cmd_window_func=callbacks.close_cmd_window,
            merge_phrases_func=lambda left, right: f"{left} {right}".strip(),
            looks_incomplete_command_func=false_predicate,
            pending_command_wait_sec=1.2,
            normalize_func=lambda text: (text, {}),
            should_ignore_during_ack_window_func=false_predicate,
            router=None,
            print_func=None,
            time_func=lambda: 10.0,
            speech_interrupt_func=handlers.speech_interrupt,
            phrase_guard_func=handlers.phrase_guard,
            pending_confirmation_func=handlers.confirmation,
            dictation_phrase_func=handlers.dictation,
            hotword_activation_func=handlers.hotword_activation,
            command_window_func=handlers.command_window,
        )

        result = processor.process_phrase(
            "тестовая фраза",
            last_tts_end=0.0,
            ack_ignore_until=0.0,
        )

        actual = {
            "handled": result.handled,
            "reason": result.reason,
            "last_tts_end": result.last_tts_end,
            "ack_ignore_until": result.ack_ignore_until,
            "logger_events": logger.events,
            "calls": handlers.calls,
        }

        expected = dict(case["expected"])
        ok = actual == expected

        print()
        print(f"{idx}. {case['name']}")
        print(
            json.dumps(
                {
                    "expected": expected,
                    "actual": actual,
                    "ok": ok,
                },
                ensure_ascii=False,
            )
        )

        if ok:
            print("[OK] phrase event processor case")
        else:
            fail_count += 1
            print("[FAIL] phrase event processor mismatch")

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