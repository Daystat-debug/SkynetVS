from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.speech_interrupt import handle_phrase_while_tts_speaking


class FakeTTS:
    def __init__(self, *, speaking: bool) -> None:
        self.speaking = speaking
        self.stop_called = False

    def is_speaking(self) -> bool:
        return self.speaking

    def stop(self) -> None:
        self.stop_called = True
        self.speaking = False


class FakeLogger:
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append({"kind": kind, "payload": payload})


def has_hotword(text: str) -> bool:
    return " ".join((text or "").lower().split()).startswith("скайнет")


def strip_hotword(text: str) -> str:
    t = " ".join((text or "").lower().split())
    if t == "скайнет":
        return ""
    if t.startswith("скайнет "):
        return t[len("скайнет"):].strip()
    return ""


def normalize_func(text: str) -> tuple[str, bool]:
    return " ".join((text or "").lower().split()), False


def predict_func(text: str) -> Dict[str, Any]:
    t = " ".join((text or "").lower().split())

    if t in {"замолчи", "прекрати говорить", "остановись говорить"}:
        return {
            "intent": "STOP_TALKING",
            "confidence": 1.0,
            "slots": {},
        }

    return {
        "intent": None,
        "confidence": 0.0,
        "slots": {},
    }


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "tts not speaking does nothing",
        "speaking": False,
        "phrase": "замолчи",
        "expected": {
            "handled": False,
            "stopped": False,
            "reason": "tts_not_speaking",
            "stop_called": False,
            "events": [],
        },
    },
    {
        "name": "stop talking without hotword",
        "speaking": True,
        "phrase": "замолчи",
        "expected": {
            "handled": True,
            "stopped": True,
            "reason": "stop_talking",
            "stop_called": True,
            "events": ["tts_stop_requested"],
        },
    },
    {
        "name": "stop talking with hotword",
        "speaking": True,
        "phrase": "скайнет замолчи",
        "expected": {
            "handled": True,
            "stopped": True,
            "reason": "stop_talking",
            "stop_called": True,
            "events": ["tts_stop_requested"],
        },
    },
    {
        "name": "ignore unrelated phrase while speaking",
        "speaking": True,
        "phrase": "открой блокнот",
        "expected": {
            "handled": True,
            "stopped": False,
            "reason": "ignored_while_tts_speaking",
            "stop_called": False,
            "events": ["stt_ignored_while_tts_speaking"],
        },
    },
]


def main() -> int:
    fail_count = 0

    print("=== SPEECH INTERRUPT EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        tts = FakeTTS(speaking=bool(case["speaking"]))
        logger = FakeLogger()

        result = handle_phrase_while_tts_speaking(
            str(case["phrase"]),
            tts=tts,
            logger=logger,
            has_hotword_func=has_hotword,
            strip_hotword_func=strip_hotword,
            normalize_func=normalize_func,
            predict_func=predict_func,
        )

        actual = {
            "handled": result.handled,
            "stopped": result.stopped,
            "reason": result.reason,
            "stop_called": tts.stop_called,
            "events": [event["kind"] for event in logger.events],
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
            print("[OK] speech interrupt case")
        else:
            fail_count += 1
            print("[FAIL] speech interrupt mismatch")

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