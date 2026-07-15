from __future__ import annotations

import json

from typing import Any, Callable, Dict, Optional

from modules.actions import Actions
from modules.audio_output import (
    AudioOutputError,
    AudioOutputResult,
    OutputDevice,
    STATUS_ALREADY_ACTIVE,
    STATUS_DEVICE_NOT_FOUND,
    STATUS_SWITCHED,
)


HEADPHONES = OutputDevice(
    id="{0.0.0.00000000}.headphones",
    name="Динамики (6- USB Audio Device)",
)

SPEAKERS = OutputDevice(
    id="{0.0.0.00000000}.speakers",
    name="Динамики (Realtek High Definition Audio)",
)


class DummyService:
    pass


class FakeAudioOutput:
    def __init__(
        self,
        *,
        headphones_result: Optional[AudioOutputResult] = None,
        speakers_result: Optional[AudioOutputResult] = None,
        toggle_result: Optional[AudioOutputResult] = None,
        error: Optional[Exception] = None,
    ):
        self.headphones_result = headphones_result
        self.speakers_result = speakers_result
        self.toggle_result = toggle_result
        self.error = error
        self.calls: list[str] = []

    def _execute(self, name: str, result: Optional[AudioOutputResult]) -> AudioOutputResult:
        self.calls.append(name)

        if self.error is not None:
            raise self.error

        if result is None:
            raise RuntimeError(f"Missing fake result: {name}")

        return result

    def set_headphones(self) -> AudioOutputResult:
        return self._execute("headphones", self.headphones_result)

    def set_speakers(self) -> AudioOutputResult:
        return self._execute("speakers", self.speakers_result)

    def toggle(self) -> AudioOutputResult:
        return self._execute("toggle", self.toggle_result)


def _new_actions(
    audio_output: Optional[FakeAudioOutput],
    events: list[Dict[str, Any]],
    event_func: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Actions:
    if event_func is None:
        def event_func(name: str, payload: Dict[str, Any]) -> None:
            events.append({"name": name, "payload": payload})

    return Actions(
        audio=None,
        audio_output=audio_output,
        screenshot_service=DummyService(),
        weather_service=DummyService(),
        typing_service=DummyService(),
        window_context_service=DummyService(),
        event_func=event_func,
    )


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

    switched_result = AudioOutputResult(
        status=STATUS_SWITCHED,
        changed=True,
        requested_name=HEADPHONES.name,
        target=HEADPHONES,
        before=SPEAKERS,
        after=HEADPHONES,
    )

    events: list[Dict[str, Any]] = []
    audio_output = FakeAudioOutput(headphones_result=switched_result)
    actions = _new_actions(audio_output, events)
    actions._exec_audio_output_headphones({})

    check(
        "SWITCHED RESULT EVENT",
        {
            "calls": audio_output.calls,
            "events": events,
        },
        {
            "calls": ["headphones"],
            "events": [
                {
                    "name": "audio_output_switched",
                    "payload": {
                        "intent": "AUDIO_OUTPUT_HEADPHONES",
                        "status": "switched",
                        "changed": True,
                        "requested_name": HEADPHONES.name,
                        "target_name": HEADPHONES.name,
                        "before_name": SPEAKERS.name,
                        "after_name": HEADPHONES.name,
                        "error": "",
                    },
                }
            ],
        },
    )

    already_active_result = AudioOutputResult(
        status=STATUS_ALREADY_ACTIVE,
        changed=False,
        requested_name=HEADPHONES.name,
        target=HEADPHONES,
        before=HEADPHONES,
        after=HEADPHONES,
    )

    events = []
    audio_output = FakeAudioOutput(headphones_result=already_active_result)
    actions = _new_actions(audio_output, events)
    actions._exec_audio_output_headphones({})

    check(
        "ALREADY ACTIVE RESULT EVENT",
        {
            "calls": audio_output.calls,
            "event_name": events[0]["name"],
            "status": events[0]["payload"]["status"],
            "changed": events[0]["payload"]["changed"],
        },
        {
            "calls": ["headphones"],
            "event_name": "audio_output_already_active",
            "status": "already_active",
            "changed": False,
        },
    )

    toggle_result = AudioOutputResult(
        status=STATUS_SWITCHED,
        changed=True,
        requested_name=SPEAKERS.name,
        target=SPEAKERS,
        before=HEADPHONES,
        after=SPEAKERS,
    )

    events = []
    audio_output = FakeAudioOutput(toggle_result=toggle_result)
    actions = _new_actions(audio_output, events)
    actions._exec_audio_output_toggle({})

    check(
        "TOGGLE RESULT EVENT",
        {
            "calls": audio_output.calls,
            "event_name": events[0]["name"],
            "intent": events[0]["payload"]["intent"],
            "after_name": events[0]["payload"]["after_name"],
        },
        {
            "calls": ["toggle"],
            "event_name": "audio_output_switched",
            "intent": "AUDIO_OUTPUT_TOGGLE",
            "after_name": SPEAKERS.name,
        },
    )

    failed_result = AudioOutputResult(
        status=STATUS_DEVICE_NOT_FOUND,
        changed=False,
        requested_name=HEADPHONES.name,
        target=None,
        before=SPEAKERS,
        after=SPEAKERS,
    )

    events = []
    error = AudioOutputError("Audio output device not found", failed_result)
    audio_output = FakeAudioOutput(error=error)
    actions = _new_actions(audio_output, events)
    raised = False

    try:
        actions._exec_audio_output_headphones({})
    except AudioOutputError:
        raised = True

    check(
        "STRUCTURED FAILURE EVENT",
        {
            "raised": raised,
            "event_name": events[0]["name"],
            "status": events[0]["payload"]["status"],
            "error": events[0]["payload"]["error"],
        },
        {
            "raised": True,
            "event_name": "audio_output_failed",
            "status": "device_not_found",
            "error": "Audio output device not found",
        },
    )

    events = []
    audio_output = FakeAudioOutput(error=RuntimeError("fake unexpected failure"))
    actions = _new_actions(audio_output, events)
    raised = False

    try:
        actions._exec_audio_output_speakers({})
    except RuntimeError:
        raised = True

    check(
        "UNEXPECTED FAILURE EVENT",
        {
            "raised": raised,
            "event_name": events[0]["name"],
            "status": events[0]["payload"]["status"],
            "error": events[0]["payload"]["error"],
        },
        {
            "raised": True,
            "event_name": "audio_output_failed",
            "status": "unexpected_error",
            "error": "fake unexpected failure",
        },
    )

    events = []
    actions = _new_actions(None, events)
    actions._exec_audio_output_toggle({})

    check(
        "UNAVAILABLE SERVICE IS IGNORED",
        events,
        [],
    )

    events = []
    audio_output = FakeAudioOutput(headphones_result=switched_result)

    def broken_event_func(name: str, payload: Dict[str, Any]) -> None:
        _ = name
        _ = payload
        raise RuntimeError("fake logger failure")

    actions = _new_actions(audio_output, events, event_func=broken_event_func)
    raised = False

    try:
        actions._exec_audio_output_headphones({})
    except Exception:
        raised = True

    check(
        "LOGGER FAILURE DOES NOT BREAK ACTION",
        {
            "raised": raised,
            "calls": audio_output.calls,
        },
        {
            "raised": False,
            "calls": ["headphones"],
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