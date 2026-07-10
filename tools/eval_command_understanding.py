from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.command_understanding import understand_command_text
from modules.config import Settings


class FakeLogger:
    def __init__(self) -> None:
        self.events: List[dict[str, Any]] = []

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append(
            {
                "kind": kind,
                "payload": payload,
            }
        )


class FakeRouter:
    def __init__(self, *, repeat_mode: bool = False) -> None:
        self.repeat_mode = repeat_mode

    def preprocess(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        text = str(meta.get("_text") or "").lower().strip()

        if self.repeat_mode and text in {"ещё", "еще", "повтори"}:
            return {
                "intent": "VOLUME_UP",
                "confidence": 1.0,
                "slots": {},
                "_text": text,
                "_from_history": True,
            }

        return meta


class FakeSTT:
    last_utterance_audio = b""
    samplerate = 16000


class FakeSTTWithAudio:
    last_utterance_audio = b"audio"
    samplerate = 16000


class FakeWhisper:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def refine_pcm(
        self,
        pcm: bytes,
        *,
        samplerate: int,
    ) -> str:
        _ = pcm
        _ = samplerate

        self.calls += 1
        return self.text


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "open url understanding",
        "text": "открой ютуб",
        "router": FakeRouter(),
        "expected": {
            "intent": "OPEN_URL",
            "accepted": True,
            "runnable": True,
            "missing_slots": [],
            "requires_confirmation": False,
        },
    },
    {
        "name": "open github dot com understanding",
        "text": "открой github точка com",
        "router": FakeRouter(),
        "expected": {
            "intent": "OPEN_URL",
            "accepted": True,
            "runnable": True,
            "missing_slots": [],
            "requires_confirmation": False,
        },
    },
    {
        "name": "open network settings understanding",
        "text": "открой настройки интернета",
        "router": FakeRouter(),
        "expected": {
            "intent": "OPEN_SETTINGS",
            "accepted": True,
            "runnable": True,
            "missing_slots": [],
            "requires_confirmation": False,
        },
    },
    {
        "name": "open downloads folder accusative understanding",
        "text": "открой папку загрузок",
        "router": FakeRouter(),
        "expected": {
            "intent": "OPEN_FOLDER",
            "accepted": True,
            "runnable": True,
            "missing_slots": [],
            "requires_confirmation": False,
        },
    },
    {
        "name": "open chrome app understanding",
        "text": "открой хром",
        "router": FakeRouter(),
        "expected": {
            "intent": "OPEN_APP",
            "accepted": True,
            "runnable": True,
            "missing_slots": [],
            "requires_confirmation": False,
        },
    },
    {
        "name": "open browser app understanding",
        "text": "открой браузер",
        "router": FakeRouter(),
        "expected": {
            "intent": "OPEN_APP",
            "accepted": True,
            "runnable": True,
            "missing_slots": [],
            "requires_confirmation": False,
        },
    },
    {
        "name": "open explorer app understanding",
        "text": "открой проводник",
        "router": FakeRouter(),
        "expected": {
            "intent": "OPEN_APP",
            "accepted": True,
            "runnable": True,
            "missing_slots": [],
            "requires_confirmation": False,
        },
    },
    {
        "name": "set volume understanding",
        "text": "громкость 50",
        "router": FakeRouter(),
        "expected": {
            "intent": "SET_VOLUME",
            "accepted": True,
            "runnable": True,
            "missing_slots": [],
            "requires_confirmation": False,
        },
    },
    {
        "name": "incomplete command understanding",
        "text": "открой",
        "router": FakeRouter(),
        "expected": {
            "intent": None,
            "accepted": False,
            "runnable": False,
            "missing_slots": [],
            "requires_confirmation": False,
        },
    },
    {
        "name": "confirmation command understanding",
        "text": "очисти корзину",
        "router": FakeRouter(),
        "expected": {
            "intent": "EMPTY_RECYCLE_BIN",
            "accepted": True,
            "runnable": False,
            "missing_slots": [],
            "requires_confirmation": True,
        },
    },
    {
        "name": "router repeat preprocess understanding",
        "text": "ещё",
        "router": FakeRouter(repeat_mode=True),
        "expected": {
            "intent": "VOLUME_UP",
            "accepted": True,
            "runnable": True,
            "missing_slots": [],
            "requires_confirmation": False,
        },
    },
]


def _compare(expected: Dict[str, Any], actual: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    for key, expected_value in expected.items():
        actual_value = actual.get(key)

        if actual_value != expected_value:
            errors.append(
                f"{key}: expected={expected_value!r}, actual={actual_value!r}"
            )

    return errors


def main() -> int:
    settings = Settings.from_env()
    fail_count = 0

    print("=== COMMAND UNDERSTANDING EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        logger = FakeLogger()

        result = understand_command_text(
            str(case["text"]),
            router=case["router"],
            logger=logger,
            whisper=None,
            stt=FakeSTT(),
            accept_conf=settings.nlu_accept_conf,
            whisper_trigger_conf=settings.whisper_trigger_conf,
            print_func=None,
        )

        actual = {
            "intent": result.meta.get("intent"),
            "accepted": result.decision.accepted,
            "runnable": result.decision.runnable,
            "missing_slots": result.decision.missing_slots,
            "requires_confirmation": result.decision.requires_confirmation,
        }

        expected = dict(case["expected"])
        errors = _compare(expected, actual)

        print()
        print(f"{idx}. {case['name']}")
        print(
            json.dumps(
                {
                    "text": case["text"],
                    "raw_text": result.raw_text,
                    "final_text": result.final_text,
                    "meta": result.meta,
                    "decision": result.decision.to_dict(),
                    "events_count": len(logger.events),
                    "actual": actual,
                    "expected": expected,
                },
                ensure_ascii=False,
            )
        )

        if errors:
            fail_count += 1
            for error in errors:
                print(f"[FAIL] {error}")
        else:
            print("[OK] command understanding case")

    logger = FakeLogger()
    whisper = FakeWhisper(
        "скайнет запусти музыку."
    )

    result = understand_command_text(
        "запусти музыку",
        router=FakeRouter(),
        logger=logger,
        whisper=whisper,
        stt=FakeSTTWithAudio(),
        accept_conf=settings.nlu_accept_conf,
        whisper_trigger_conf=0.99,
        hotwords=settings.hotwords,
        print_func=None,
    )

    diagnostic_events = [
        event
        for event in logger.events
        if event.get("kind") == "stt_diagnostic"
    ]

    diagnostic_payload = (
        diagnostic_events[-1]["payload"]
        if diagnostic_events
        else {}
    )

    actual = {
        "intent": result.meta.get("intent"),
        "final_text": result.final_text,
        "accepted": result.decision.accepted,
        "whisper_calls": whisper.calls,
        "refinement_reason": diagnostic_payload.get(
            "refinement_reason"
        ),
        "changed_by_refinement": diagnostic_payload.get(
            "changed_by_refinement"
        ),
    }

    expected = {
        "intent": "MUSIC_PLAY",
        "final_text": "запусти музыку",
        "accepted": True,
        "whisper_calls": 1,
        "refinement_reason": "same_text",
        "changed_by_refinement": False,
    }

    errors = _compare(expected, actual)

    print()
    print(f"{len(CASES) + 1}. whisper hotword intent stability")
    print(
        json.dumps(
            {
                "actual": actual,
                "expected": expected,
                "diagnostic_payload": diagnostic_payload,
            },
            ensure_ascii=False,
        )
    )

    if errors:
        fail_count += 1

        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[OK] whisper hotword intent stability")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "total_cases": len(CASES) + 1,
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())