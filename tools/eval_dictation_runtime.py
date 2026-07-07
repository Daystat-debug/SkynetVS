from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping

from dotenv import load_dotenv

load_dotenv()

from modules.dictation_runtime import handle_dictation_phrase


class FakeModeManager:
    def __init__(self, *, dictation_mode: bool = True) -> None:
        self.dictation_mode = dictation_mode
        self.events: List[str] = []
        self.separator_needed = False

    def is_dictation_mode(self) -> bool:
        return self.dictation_mode

    def exit_dictation_mode(self) -> None:
        self.events.append("mode.exit_dictation")
        self.dictation_mode = False

    def reset_dictation_separator(self) -> None:
        self.events.append("mode.reset_separator")
        self.separator_needed = False

    def dictation_prefix(self) -> str:
        return " " if self.separator_needed else ""

    def mark_dictation_text_typed(self) -> None:
        self.events.append("mode.mark_typed")
        self.separator_needed = True


class FakeTypingService:
    def __init__(self) -> None:
        self.events: List[str] = []

    def press_enter(self) -> None:
        self.events.append("typing.enter")

    def press_backspace(self) -> None:
        self.events.append("typing.backspace")

    def press_tab(self) -> None:
        self.events.append("typing.tab")

    def type_text(self, text: str) -> None:
        self.events.append(f"typing.text:{text}")


class FakeLogger:
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append({"kind": kind, "payload": payload})


def norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def has_hotword(text: str) -> bool:
    return norm(text).startswith("скайнет")


def strip_hotword(text: str) -> str:
    t = norm(text)

    if t == "скайнет":
        return ""

    if t.startswith("скайнет "):
        return t[len("скайнет"):].strip()

    return ""


def is_only_hotword(text: str) -> bool:
    return norm(text) == "скайнет"


def is_dictation_stop_phrase(text: str) -> bool:
    return norm(text) in {
        "выключи режим диктовки",
        "заверши диктовку",
    }


def predict_func(text: str) -> Mapping[str, Any]:
    t = norm(text)

    mapping = {
        "выключи режим диктовки": "DICTATION_MODE_OFF",
        "нажми enter": "PRESS_ENTER",
        "нажми бэкспейс": "PRESS_BACKSPACE",
        "нажми tab": "PRESS_TAB",
    }

    intent = mapping.get(t)

    if intent:
        return {
            "intent": intent,
            "confidence": 1.0,
            "slots": {},
        }

    return {
        "intent": None,
        "confidence": 0.0,
        "slots": {},
    }


def is_accepted(meta: Mapping[str, Any]) -> bool:
    return bool(meta.get("intent")) and float(meta.get("confidence") or 0.0) >= 0.35


def pick_named_response(name: str) -> str | None:
    if name == "DICTATION_MODE_OFF":
        return "Режим диктовки выключен."
    return None


def say_func(stt: Any, tts: Any, text: str) -> float:
    _ = stt
    _ = tts
    return 123.0 if text else 0.0


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "not dictation mode",
        "dictation_mode": False,
        "phrase": "любой текст",
        "expected": {
            "handled": False,
            "reason": "not_dictation_mode",
            "mode_events": [],
            "typing_events": [],
            "logger_events": [],
            "last_tts_end": None,
        },
    },
    {
        "name": "bare hotword ignored",
        "dictation_mode": True,
        "phrase": "скайнет",
        "expected": {
            "handled": True,
            "reason": "bare_hotword_ignored",
            "mode_events": [],
            "typing_events": [],
            "logger_events": ["dictation_ignore_bare_hotword"],
            "last_tts_end": None,
        },
    },
    {
        "name": "dictation stop phrase",
        "dictation_mode": True,
        "phrase": "заверши диктовку",
        "expected": {
            "handled": True,
            "reason": "dictation_stop_phrase",
            "mode_events": ["mode.exit_dictation"],
            "typing_events": [],
            "logger_events": ["dictation_mode_off"],
            "last_tts_end": 123.0,
        },
    },
    {
        "name": "press enter",
        "dictation_mode": True,
        "phrase": "нажми enter",
        "expected": {
            "handled": True,
            "reason": "press_enter",
            "mode_events": ["mode.reset_separator"],
            "typing_events": ["typing.enter"],
            "logger_events": ["dictation_editor_action"],
            "last_tts_end": None,
        },
    },
    {
        "name": "press backspace",
        "dictation_mode": True,
        "phrase": "нажми бэкспейс",
        "expected": {
            "handled": True,
            "reason": "press_backspace",
            "mode_events": [],
            "typing_events": ["typing.backspace"],
            "logger_events": ["dictation_editor_action"],
            "last_tts_end": None,
        },
    },
    {
        "name": "press tab",
        "dictation_mode": True,
        "phrase": "нажми tab",
        "expected": {
            "handled": True,
            "reason": "press_tab",
            "mode_events": ["mode.reset_separator"],
            "typing_events": ["typing.tab"],
            "logger_events": ["dictation_editor_action"],
            "last_tts_end": None,
        },
    },
    {
        "name": "type normal text",
        "dictation_mode": True,
        "phrase": "привет мир",
        "expected": {
            "handled": True,
            "reason": "typed_text",
            "mode_events": ["mode.mark_typed"],
            "typing_events": ["typing.text:привет мир"],
            "logger_events": ["dictation_typed"],
            "last_tts_end": None,
        },
    },
    {
        "name": "type normal text with hotword prefix",
        "dictation_mode": True,
        "phrase": "скайнет привет мир",
        "expected": {
            "handled": True,
            "reason": "typed_text",
            "mode_events": ["mode.mark_typed"],
            "typing_events": ["typing.text:привет мир"],
            "logger_events": ["dictation_typed"],
            "last_tts_end": None,
        },
    },
]


def main() -> int:
    fail_count = 0

    print("=== DICTATION RUNTIME EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        mode_manager = FakeModeManager(dictation_mode=bool(case["dictation_mode"]))
        typing_service = FakeTypingService()
        logger = FakeLogger()

        result = handle_dictation_phrase(
            str(case["phrase"]),
            mode_manager=mode_manager,
            typing_service=typing_service,
            logger=logger,
            stt=None,
            tts=None,
            say_func=say_func,
            has_hotword_func=has_hotword,
            strip_hotword_func=strip_hotword,
            is_only_hotword_func=is_only_hotword,
            norm_func=norm,
            is_dictation_stop_phrase_func=is_dictation_stop_phrase,
            predict_func=predict_func,
            is_accepted_func=is_accepted,
            pick_named_response_func=pick_named_response,
        )

        actual = {
            "handled": result.handled,
            "reason": result.reason,
            "mode_events": mode_manager.events,
            "typing_events": typing_service.events,
            "logger_events": [event["kind"] for event in logger.events],
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
            print("[OK] dictation runtime case")
        else:
            fail_count += 1
            print("[FAIL] dictation runtime mismatch")

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