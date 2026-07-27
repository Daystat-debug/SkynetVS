from __future__ import annotations

import json

from typing import Any
from unittest.mock import patch

from modules.stt_vosk import VoskSTT


class FakeClock:
    def __init__(self, value: float = 1000.0):
        self.value = float(value)

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += float(seconds)


class FakeRecognizer:
    def __init__(self, model: Any, samplerate: int):
        _ = model
        _ = samplerate

    def SetWords(self, enabled: bool) -> None:
        _ = enabled

    def AcceptWaveform(self, data: bytes) -> bool:
        return bool(data)

    def Result(self) -> str:
        return json.dumps({"text": "тестовая фраза"}, ensure_ascii=False)


class FakeRawInputStream:
    def __init__(self, *, callback, **kwargs: Any):
        _ = kwargs
        self.callback = callback

    def __enter__(self) -> "FakeRawInputStream":
        self.callback(b"\x01\x00\x02\x00", 2, None, "")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb


class FailingRawInputStream:
    def __init__(self, **kwargs: Any):
        _ = kwargs

    def __enter__(self) -> "FailingRawInputStream":
        raise RuntimeError("microphone open failed")

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb


class StatusObject:
    def __bool__(self) -> bool:
        return True

    def __str__(self) -> str:
        return "input overflow"


def _new_stt(clock: FakeClock | None = None) -> VoskSTT:
    clock = clock or FakeClock()

    with patch("modules.stt_vosk.Model", return_value=object()), patch.object(
        VoskSTT,
        "get_current_input_device_info",
        return_value=None,
    ):
        return VoskSTT(
            model_path="models/test",
            samplerate=16000,
            blocksize=1024,
            device=None,
            time_func=clock,
        )


def _contains_binary(value: Any) -> bool:
    if isinstance(value, (bytes, bytearray, memoryview)):
        return True

    if isinstance(value, dict):
        return any(_contains_binary(item) for item in value.values())

    if isinstance(value, (list, tuple, set)):
        return any(_contains_binary(item) for item in value)

    return False


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count

        case_count += 1
        ok = actual == expected

        print()
        print(f"=== {name} ===")
        print(json.dumps(
            {
                "actual": actual,
                "expected": expected,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ))

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    clock = FakeClock()
    stt = _new_stt(clock)
    snapshot = stt.get_lifecycle_telemetry()

    check(
        "INITIAL LIFECYCLE",
        {
            "started": snapshot.stream_started,
            "active": snapshot.stream_active,
            "generation": snapshot.stream_generation,
            "phase": snapshot.stream_phase,
            "audio_blocks": snapshot.audio_block_count,
            "phrases": snapshot.phrase_count,
            "failures": snapshot.failure_count,
        },
        {
            "started": False,
            "active": False,
            "generation": 0,
            "phase": "not_started",
            "audio_blocks": 0,
            "phrases": 0,
            "failures": 0,
        },
    )

    generation = stt._begin_stream()
    stt._mark_stream_active(generation)
    clock.advance(0.1)
    stt._callback(b"1234", 2, None, "", _generation=generation)
    snapshot = stt.get_lifecycle_telemetry()

    check(
        "ACTIVE STREAM RECORDS AUDIO HEARTBEAT",
        {
            "active": snapshot.stream_active,
            "phase": snapshot.stream_phase,
            "last_audio_at": snapshot.last_audio_block_at,
            "audio_blocks": snapshot.audio_block_count,
            "audio_bytes": snapshot.audio_bytes_total,
            "processed_blocks": snapshot.processed_audio_block_count,
            "queue_size": stt._q.qsize(),
        },
        {
            "active": True,
            "phase": "active",
            "last_audio_at": 1000.1,
            "audio_blocks": 1,
            "audio_bytes": 4,
            "processed_blocks": 0,
            "queue_size": 1,
        },
    )

    stt.pause()
    clock.advance(0.1)
    stt._callback(b"5678", 2, None, "", _generation=generation)
    snapshot = stt.get_lifecycle_telemetry()

    check(
        "PAUSED CALLBACK UPDATES HEARTBEAT WITHOUT QUEUEING",
        {
            "paused": snapshot.paused,
            "last_audio_at": snapshot.last_audio_block_at,
            "audio_blocks": snapshot.audio_block_count,
            "audio_bytes": snapshot.audio_bytes_total,
            "queue_size": stt._q.qsize(),
            "failures": snapshot.failure_count,
        },
        {
            "paused": True,
            "last_audio_at": 1000.2,
            "audio_blocks": 2,
            "audio_bytes": 8,
            "queue_size": 0,
            "failures": 0,
        },
    )

    stt.resume()
    resumed_snapshot = stt.get_lifecycle_telemetry()

    check(
        "RESUME STARTS PROCESSING GRACE",
        {
            "paused": resumed_snapshot.paused,
            "last_resumed_at": resumed_snapshot.last_resumed_at,
            "resume_pending": resumed_snapshot.resume_pending,
        },
        {
            "paused": False,
            "last_resumed_at": 1000.2,
            "resume_pending": True,
        },
    )

    clock.advance(0.1)
    stt._callback(b"90", 1, None, StatusObject(), _generation=generation)
    snapshot = stt.get_lifecycle_telemetry()

    check(
        "CALLBACK STATUS IS WARNING NOT FAILURE",
        {
            "paused": snapshot.paused,
            "status": snapshot.last_callback_status,
            "status_at": round(snapshot.last_callback_status_at or 0.0, 1),
            "status_count": snapshot.callback_status_count,
            "resume_pending": snapshot.resume_pending,
            "failures": snapshot.failure_count,
        },
        {
            "paused": False,
            "status": "input overflow",
            "status_at": 1000.3,
            "status_count": 1,
            "resume_pending": True,
            "failures": 0,
        },
    )

    stt._record_processed_audio_block(generation)
    processed_snapshot = stt.get_lifecycle_telemetry()

    check(
        "FIRST PROCESSED BLOCK COMPLETES RESUME",
        {
            "processed_at": round(
                processed_snapshot.last_processed_audio_block_at or 0.0,
                1,
            ),
            "processed_blocks": processed_snapshot.processed_audio_block_count,
            "resume_pending": processed_snapshot.resume_pending,
        },
        {
            "processed_at": 1000.3,
            "processed_blocks": 1,
            "resume_pending": False,
        },
    )

    clock.advance(0.1)
    stt.resume()
    redundant_snapshot = stt.get_lifecycle_telemetry()

    check(
        "REDUNDANT RESUME DOES NOT EXTEND GRACE",
        {
            "last_resumed_at": redundant_snapshot.last_resumed_at,
            "resume_pending": redundant_snapshot.resume_pending,
        },
        {
            "last_resumed_at": 1000.2,
            "resume_pending": False,
        },
    )

    stt._mark_stream_stopped(generation)
    generation_2 = stt._begin_stream()
    stt._mark_stream_active(generation_2)
    count_before = stt.get_lifecycle_telemetry().audio_block_count
    queue_before = stt._q.qsize()
    stt._callback(b"stale", 1, None, "", _generation=generation)
    duplicate_rejected = False

    try:
        stt._begin_stream()
    except RuntimeError:
        duplicate_rejected = True

    snapshot = stt.get_lifecycle_telemetry()

    check(
        "GENERATION GUARD AND DUPLICATE STREAM GUARD",
        {
            "generation": snapshot.stream_generation,
            "audio_blocks": snapshot.audio_block_count,
            "queue_size": stt._q.qsize(),
            "old_queue_drained": queue_before == 0,
            "duplicate_rejected": duplicate_rejected,
            "last_resumed_at": snapshot.last_resumed_at,
            "resume_pending": snapshot.resume_pending,
        },
        {
            "generation": 2,
            "audio_blocks": count_before,
            "queue_size": 0,
            "old_queue_drained": True,
            "duplicate_rejected": True,
            "last_resumed_at": None,
            "resume_pending": False,
        },
    )

    stt._mark_stream_stopped(generation_2)

    clock = FakeClock()
    stt = _new_stt(clock)

    with patch("modules.stt_vosk.KaldiRecognizer", FakeRecognizer), patch(
        "modules.stt_vosk.sd.RawInputStream",
        FakeRawInputStream,
    ):
        phrases = stt.listen_phrases()
        phrase = next(phrases)
        active_snapshot = stt.get_lifecycle_telemetry()
        clock.advance(0.2)
        phrases.close()

    stopped_snapshot = stt.get_lifecycle_telemetry()

    check(
        "LISTEN LOOP RECORDS PHRASE AND CLEAN STOP",
        {
            "phrase": phrase,
            "active_before_close": active_snapshot.stream_active,
            "phase_before_close": active_snapshot.stream_phase,
            "phrase_count": active_snapshot.phrase_count,
            "processed_blocks": active_snapshot.processed_audio_block_count,
            "last_text": stt.last_utterance_text,
            "audio_bytes": len(stt.last_utterance_audio),
            "active_after_close": stopped_snapshot.stream_active,
            "phase_after_close": stopped_snapshot.stream_phase,
            "failures": stopped_snapshot.failure_count,
        },
        {
            "phrase": "тестовая фраза",
            "active_before_close": True,
            "phase_before_close": "active",
            "phrase_count": 1,
            "processed_blocks": 1,
            "last_text": "тестовая фраза",
            "audio_bytes": 4,
            "active_after_close": False,
            "phase_after_close": "stopped",
            "failures": 0,
        },
    )

    clock = FakeClock()
    stt = _new_stt(clock)
    raised = False

    with patch("modules.stt_vosk.KaldiRecognizer", FakeRecognizer), patch(
        "modules.stt_vosk.sd.RawInputStream",
        FailingRawInputStream,
    ):
        try:
            next(stt.listen_phrases())
        except RuntimeError:
            raised = True

    snapshot = stt.get_lifecycle_telemetry()

    check(
        "STREAM OPEN FAILURE RECORDED",
        {
            "raised": raised,
            "active": snapshot.stream_active,
            "phase": snapshot.stream_phase,
            "last_error": snapshot.last_error,
            "failures": snapshot.failure_count,
            "consecutive_failures": snapshot.consecutive_failures,
        },
        {
            "raised": True,
            "active": False,
            "phase": "failed",
            "last_error": "microphone open failed",
            "failures": 1,
            "consecutive_failures": 1,
        },
    )

    with patch("modules.stt_vosk.KaldiRecognizer", FakeRecognizer), patch(
        "modules.stt_vosk.sd.RawInputStream",
        FakeRawInputStream,
    ):
        phrases = stt.listen_phrases()
        next(phrases)
        restarted_snapshot = stt.get_lifecycle_telemetry()
        phrases.close()

    check(
        "SUCCESSFUL RESTART RESETS CURRENT FAILURE",
        {
            "generation": restarted_snapshot.stream_generation,
            "active": restarted_snapshot.stream_active,
            "phase": restarted_snapshot.stream_phase,
            "failures": restarted_snapshot.failure_count,
            "consecutive_failures": restarted_snapshot.consecutive_failures,
            "last_error": restarted_snapshot.last_error,
        },
        {
            "generation": 2,
            "active": True,
            "phase": "active",
            "failures": 1,
            "consecutive_failures": 0,
            "last_error": "microphone open failed",
        },
    )

    diagnostics = stt.get_diagnostics()
    lifecycle = diagnostics.get("lifecycle") or {}

    check(
        "DIAGNOSTICS INCLUDE SAFE LIFECYCLE",
        {
            "has_lifecycle": isinstance(lifecycle, dict),
            "generation": lifecycle.get("stream_generation"),
            "phase": lifecycle.get("stream_phase"),
            "audio_blocks": lifecycle.get("audio_block_count"),
            "processed_blocks": lifecycle.get("processed_audio_block_count"),
            "queue_size": lifecycle.get("queue_size"),
            "phrases": lifecycle.get("phrase_count"),
            "failures": lifecycle.get("failure_count"),
            "contains_binary": _contains_binary(diagnostics),
            "last_resumed_age": lifecycle.get("last_resumed_age_sec"),
            "resume_pending": lifecycle.get("resume_pending"),
        },
        {
            "has_lifecycle": True,
            "generation": 2,
            "phase": "stopped",
            "audio_blocks": 1,
            "processed_blocks": 1,
            "queue_size": 0,
            "phrases": 1,
            "failures": 1,
            "contains_binary": False,
            "last_resumed_age": None,
            "resume_pending": False,
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps(
        {
            "case_count": case_count,
            "fail_count": fail_count,
        },
        ensure_ascii=False,
        indent=2,
    ))

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())