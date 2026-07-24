from __future__ import annotations

import json
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

from modules.stt_diagnostics import build_stt_diagnostic_payload
from modules.stt_refinement import SttRefinementResult


class FakeSTT:
    def __init__(self) -> None:
        self.last_utterance_audio = b"12345678"
        self.last_utterance_text = "открой гитхаб"
        self.samplerate = 16000

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "engine": "fake",
            "active_model_path": "models/test",
            "samplerate": self.samplerate,
            "last_utterance_text": self.last_utterance_text,
            "last_utterance_audio_bytes": len(self.last_utterance_audio),
            "last_utterance_duration_sec": 0.001,
            "lifecycle": {
                "stream_started": True,
                "stream_active": True,
                "stream_generation": 1,
                "stream_phase": "active",
                "paused": False,
                "last_audio_block_age_sec": 0.01,
                "audio_block_count": 10,
                "audio_bytes_total": 20480,
                "last_processed_audio_block_age_sec": 0.02,
                "processed_audio_block_count": 10,
                "queue_size": 0,
                "phrase_count": 1,
                "last_callback_status": "",
                "callback_status_count": 0,
                "last_error": "",
                "failure_count": 0,
                "consecutive_failures": 0,
            },
        }


def _contains_binary(value: Any) -> bool:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return True

    if isinstance(value, dict):
        return any(_contains_binary(item) for item in value.values())

    if isinstance(value, (list, tuple, set)):
        return any(_contains_binary(item) for item in value)

    return False


def _check_payload(name: str, payload: Dict[str, Any], expected: Dict[str, Any]) -> bool:
    errors: list[str] = []

    for key, expected_value in expected.items():
        actual_value = payload.get(key)

        if actual_value != expected_value:
            errors.append(
                f"{key}: expected={expected_value!r}, actual={actual_value!r}"
            )

    if "stt" not in payload or not isinstance(payload["stt"], dict):
        errors.append("missing stt diagnostics")

    if "original_meta" not in payload or not isinstance(payload["original_meta"], dict):
        errors.append("missing original_meta")

    if "final_meta" not in payload or not isinstance(payload["final_meta"], dict):
        errors.append("missing final_meta")

    stt_payload = payload.get("stt")

    if isinstance(stt_payload, dict):
        lifecycle = stt_payload.get("lifecycle")

        if not isinstance(lifecycle, dict):
            errors.append("missing stt lifecycle diagnostics")

    if _contains_binary(payload):
        errors.append("payload contains raw binary audio data")

    print()
    print(f"--- {name} ---")
    print(
        json.dumps(
            {
                "expected": expected,
                "payload": payload,
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
        print("[OK] stt diagnostics case")

    return not errors


def main() -> int:
    fail_count = 0

    print("=== STT DIAGNOSTICS EVAL REPORT ===")

    refinement = SttRefinementResult(
        text="открой github",
        meta={
            "intent": "OPEN_URL",
            "confidence": 0.72,
            "slots": {"site": "github"},
        },
        changed=True,
        reason="accepted_refinement",
        candidate_text="открой github",
        candidate_meta={
            "intent": "OPEN_URL",
            "confidence": 0.72,
            "slots": {"site": "github"},
        },
    )

    payload = build_stt_diagnostic_payload(
        raw_text="открой гид хаб",
        text_before_refinement="открой гид хаб",
        final_text="открой github",
        meta_before_refinement={
            "intent": "OPEN_URL",
            "confidence": 0.31,
            "slots": {},
        },
        meta_after_refinement=refinement.meta,
        refinement=refinement,
        stt=FakeSTT(),
    )

    if not _check_payload(
        "accepted refinement payload",
        payload,
        {
            "raw_text": "открой гид хаб",
            "text_before_refinement": "открой гид хаб",
            "final_text": "открой github",
            "changed_by_refinement": True,
            "refinement_reason": "accepted_refinement",
            "refinement_candidate_text": "открой github",
            "refinement_error": None,
        },
    ):
        fail_count += 1

    refinement_disabled = SttRefinementResult(
        text="открой ютуб",
        meta={
            "intent": "OPEN_URL",
            "confidence": 0.8,
            "slots": {"site": "youtube"},
        },
        changed=False,
        reason="whisper_disabled",
    )

    payload_disabled = build_stt_diagnostic_payload(
        raw_text="открой ютуб",
        text_before_refinement="открой ютуб",
        final_text="открой ютуб",
        meta_before_refinement=refinement_disabled.meta,
        meta_after_refinement=refinement_disabled.meta,
        refinement=refinement_disabled,
        stt=FakeSTT(),
    )

    if not _check_payload(
        "whisper disabled payload",
        payload_disabled,
        {
            "raw_text": "открой ютуб",
            "text_before_refinement": "открой ютуб",
            "final_text": "открой ютуб",
            "changed_by_refinement": False,
            "refinement_reason": "whisper_disabled",
            "refinement_candidate_text": None,
            "refinement_error": None,
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