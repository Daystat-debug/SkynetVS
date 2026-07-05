from __future__ import annotations

import json
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

from modules.stt_refinement import maybe_refine_with_whisper


class FakeSTT:
    def __init__(self, *, audio: bytes = b"audio", samplerate: int = 16000) -> None:
        self.last_utterance_audio = audio
        self.samplerate = samplerate


class FakeWhisper:
    def __init__(self, *, text: str = "", fail: bool = False) -> None:
        self.text = text
        self.fail = fail

    def refine_pcm(self, pcm: bytes, *, samplerate: int) -> str:
        _ = pcm
        _ = samplerate

        if self.fail:
            raise RuntimeError("fake whisper failure")

        return self.text


def norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def predict_good(text: str) -> Dict[str, Any]:
    if text == "открой блокнот":
        return {
            "intent": "OPEN_APP",
            "confidence": 0.8,
            "slots": {"app": "notepad"},
        }

    return {
        "intent": None,
        "confidence": 0.0,
        "slots": {},
    }


def predict_bad(text: str) -> Dict[str, Any]:
    _ = text
    return {
        "intent": None,
        "confidence": 0.1,
        "slots": {},
    }


def _print_result(name: str, result: Any, expected: Dict[str, Any]) -> bool:
    actual = {
        "text": result.text,
        "changed": result.changed,
        "reason": result.reason,
        "intent": result.meta.get("intent"),
    }

    ok = all(actual.get(key) == value for key, value in expected.items())

    print()
    print(f"--- {name} ---")
    print(
        json.dumps(
            {
                "expected": expected,
                "actual": actual,
                "error": result.error,
                "candidate_text": result.candidate_text,
                "candidate_meta": result.candidate_meta,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if ok:
        print("[OK] stt refinement case")
    else:
        print("[FAIL] stt refinement case")

    return ok


def main() -> int:
    fail_count = 0

    print("=== STT REFINEMENT EVAL REPORT ===")

    base_meta = {
        "intent": None,
        "confidence": 0.2,
        "slots": {},
    }

    # 1. Whisper disabled
    result = maybe_refine_with_whisper(
        original_text="открой блокнат",
        meta=base_meta,
        whisper=None,
        stt=FakeSTT(),
        trigger_conf=0.5,
        predict_func=predict_good,
        norm_func=norm,
    )
    if not _print_result(
        "whisper disabled",
        result,
        {
            "text": "открой блокнат",
            "changed": False,
            "reason": "whisper_disabled",
            "intent": None,
        },
    ):
        fail_count += 1

    # 2. Confident enough, no refinement needed
    result = maybe_refine_with_whisper(
        original_text="открой блокнот",
        meta={
            "intent": "OPEN_APP",
            "confidence": 0.9,
            "slots": {"app": "notepad"},
        },
        whisper=FakeWhisper(text="что-то другое"),
        stt=FakeSTT(),
        trigger_conf=0.5,
        predict_func=predict_good,
        norm_func=norm,
    )
    if not _print_result(
        "confident enough",
        result,
        {
            "text": "открой блокнот",
            "changed": False,
            "reason": "confident_enough",
            "intent": "OPEN_APP",
        },
    ):
        fail_count += 1

    # 3. No audio
    result = maybe_refine_with_whisper(
        original_text="открой блокнат",
        meta=base_meta,
        whisper=FakeWhisper(text="открой блокнот"),
        stt=FakeSTT(audio=b""),
        trigger_conf=0.5,
        predict_func=predict_good,
        norm_func=norm,
    )
    if not _print_result(
        "no audio",
        result,
        {
            "text": "открой блокнат",
            "changed": False,
            "reason": "no_audio",
            "intent": None,
        },
    ):
        fail_count += 1

    # 4. Accepted refinement
    result = maybe_refine_with_whisper(
        original_text="открой блокнат",
        meta=base_meta,
        whisper=FakeWhisper(text="открой блокнот"),
        stt=FakeSTT(),
        trigger_conf=0.5,
        predict_func=predict_good,
        norm_func=norm,
    )
    if not _print_result(
        "accepted refinement",
        result,
        {
            "text": "открой блокнот",
            "changed": True,
            "reason": "accepted_refinement",
            "intent": "OPEN_APP",
        },
    ):
        fail_count += 1

    # 5. Refinement not better
    result = maybe_refine_with_whisper(
        original_text="открой блокнат",
        meta=base_meta,
        whisper=FakeWhisper(text="какая-то ошибка"),
        stt=FakeSTT(),
        trigger_conf=0.5,
        predict_func=predict_bad,
        norm_func=norm,
    )
    if not _print_result(
        "refinement not better",
        result,
        {
            "text": "открой блокнат",
            "changed": False,
            "reason": "refinement_not_better",
            "intent": None,
        },
    ):
        fail_count += 1

    # 6. Whisper failure
    result = maybe_refine_with_whisper(
        original_text="открой блокнат",
        meta=base_meta,
        whisper=FakeWhisper(fail=True),
        stt=FakeSTT(),
        trigger_conf=0.5,
        predict_func=predict_good,
        norm_func=norm,
    )
    if not _print_result(
        "whisper failure",
        result,
        {
            "text": "открой блокнат",
            "changed": False,
            "reason": "refine_failed",
            "intent": None,
        },
    ):
        fail_count += 1

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())