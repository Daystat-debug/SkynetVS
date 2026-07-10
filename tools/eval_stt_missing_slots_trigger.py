from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.command_understanding import understand_command_text


class FakeLogger:
    def __init__(self) -> None:
        self.events: List[dict[str, Any]] = []

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append({"kind": kind, "payload": payload})


class FakeRouter:
    def preprocess(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        return meta


class FakeSTT:
    last_utterance_audio = b"audio"
    last_utterance_text = "скайнет открой окна и"
    samplerate = 16000

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "engine": "fake",
            "active_model_path": "models/test",
            "last_utterance_text": self.last_utterance_text,
            "last_utterance_audio_bytes": len(self.last_utterance_audio),
            "last_utterance_duration_sec": 1.0,
        }


class FakeWhisper:
    def __init__(self) -> None:
        self.calls = 0

    def refine_pcm(self, pcm: bytes, *, samplerate: int) -> str:
        _ = pcm
        _ = samplerate
        self.calls += 1
        return "открой openai"


def main() -> int:
    logger = FakeLogger()
    whisper = FakeWhisper()

    result = understand_command_text(
        "открой окна и",
        router=FakeRouter(),
        logger=logger,
        whisper=whisper,
        stt=FakeSTT(),
        accept_conf=0.35,
        whisper_trigger_conf=0.99,
        print_func=None,
    )

    diagnostic_events = [
        event
        for event in logger.events
        if event.get("kind") == "stt_diagnostic"
    ]

    payload = diagnostic_events[-1]["payload"] if diagnostic_events else {}

    actual = {
        "final_text": result.final_text,
        "intent": result.meta.get("intent"),
        "slots": result.meta.get("slots") or {},
        "whisper_calls": whisper.calls,
        "diagnostic_trigger_reason": payload.get("refinement_trigger_reason"),
        "diagnostic_refinement_reason": payload.get("refinement_reason"),
        "diagnostic_changed": payload.get("changed_by_refinement"),
    }

    expected = {
        "final_text": "открой openai",
        "intent": "OPEN_URL",
        "site": "openai",
        "whisper_calls": 1,
        "diagnostic_trigger_reason": "missing_required_slots",
        "diagnostic_refinement_reason": "accepted_refinement",
        "diagnostic_changed": True,
    }

    errors: List[str] = []

    if actual["final_text"] != expected["final_text"]:
        errors.append(f"final_text: expected={expected['final_text']!r}, actual={actual['final_text']!r}")

    if actual["intent"] != expected["intent"]:
        errors.append(f"intent: expected={expected['intent']!r}, actual={actual['intent']!r}")

    if actual["slots"].get("site") != expected["site"]:
        errors.append(f"site: expected={expected['site']!r}, actual={actual['slots'].get('site')!r}")

    for key in (
        "whisper_calls",
        "diagnostic_trigger_reason",
        "diagnostic_refinement_reason",
        "diagnostic_changed",
    ):
        if actual.get(key) != expected.get(key):
            errors.append(f"{key}: expected={expected.get(key)!r}, actual={actual.get(key)!r}")

    print("=== STT MISSING SLOTS TRIGGER EVAL REPORT ===")
    print(
        json.dumps(
            {
                "actual": actual,
                "expected": expected,
                "diagnostic_payload": payload,
                "errors": errors,
                "ok": not errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[OK] STT missing slots trigger case")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())