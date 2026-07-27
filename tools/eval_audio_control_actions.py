from __future__ import annotations

import json

from typing import Any, Callable, Dict
from unittest.mock import patch

from modules.action_error import ActionExecutionError
from modules.actions import Actions
from modules.audio_control import (
    AudioControlOperationError,
    AudioState,
)


class DummyService:
    pass


class FakeAudioControl:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        invalid_result: bool = False,
    ):
        self.error = error
        self.invalid_result = invalid_result
        self.calls: list[tuple[str, Any]] = []

    def _execute(
        self,
        operation: str,
        value: Any,
        state: AudioState,
    ) -> AudioState:
        self.calls.append((operation, value))

        if self.error is not None:
            raise self.error

        if self.invalid_result:
            return object()  # type: ignore[return-value]

        return state

    def change_volume(self, delta: int) -> AudioState:
        volume = 60 if delta > 0 else 40

        return self._execute(
            "change_volume",
            delta,
            AudioState(volume=volume, muted=False),
        )

    def set_volume(self, value: Any) -> AudioState:
        if value is None:
            raise ValueError(
                "Volume must be an integer from 0 to 100"
            )

        volume = int(value)

        return self._execute(
            "set_volume",
            value,
            AudioState(volume=volume, muted=False),
        )

    def mute(self) -> AudioState:
        return self._execute(
            "mute",
            None,
            AudioState(volume=50, muted=True),
        )

    def unmute(self) -> AudioState:
        return self._execute(
            "unmute",
            None,
            AudioState(volume=50, muted=False),
        )


def _new_actions(
    audio: Any,
    events: list[Dict[str, Any]],
    *,
    event_func: Callable[[str, Dict[str, Any]], None] | None = None,
) -> Actions:
    if event_func is None:
        def event_func(name: str, payload: Dict[str, Any]) -> None:
            events.append(
                {
                    "name": name,
                    "payload": payload,
                }
            )

    return Actions(
        audio=audio,
        volume_step=10,
        screenshot_service=DummyService(),
        weather_service=DummyService(),
        typing_service=DummyService(),
        window_context_service=DummyService(),
        event_func=event_func,
    )


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(
        name: str,
        actual: Any,
        expected: Any,
    ) -> None:
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

    events: list[Dict[str, Any]] = []
    audio = FakeAudioControl()
    actions = _new_actions(audio, events)

    actions.execute({
        "intent": "VOLUME_UP",
        "slots": {},
    })
    actions.execute({
        "intent": "VOLUME_DOWN",
        "slots": {},
    })
    actions.execute({
        "intent": "MUTE",
        "slots": {},
    })
    actions.execute({
        "intent": "UNMUTE",
        "slots": {},
    })
    actions.execute({
        "intent": "SET_VOLUME",
        "slots": {"volume": 35},
    })

    check(
        "ALL AUDIO CONTROL ACTIONS SUCCEED",
        {
            "calls": audio.calls,
            "events": [
                {
                    "name": item["name"],
                    "intent": item["payload"]["intent"],
                    "operation": item["payload"]["operation"],
                    "request": item["payload"]["request"],
                    "volume": item["payload"]["volume"],
                    "muted": item["payload"]["muted"],
                }
                for item in events
            ],
        },
        {
            "calls": [
                ("change_volume", 10),
                ("change_volume", -10),
                ("mute", None),
                ("unmute", None),
                ("set_volume", 35),
            ],
            "events": [
                {
                    "name": "audio_control_applied",
                    "intent": "VOLUME_UP",
                    "operation": "change_volume",
                    "request": {"delta": 10},
                    "volume": 60,
                    "muted": False,
                },
                {
                    "name": "audio_control_applied",
                    "intent": "VOLUME_DOWN",
                    "operation": "change_volume",
                    "request": {"delta": -10},
                    "volume": 40,
                    "muted": False,
                },
                {
                    "name": "audio_control_applied",
                    "intent": "MUTE",
                    "operation": "mute",
                    "request": {},
                    "volume": 50,
                    "muted": True,
                },
                {
                    "name": "audio_control_applied",
                    "intent": "UNMUTE",
                    "operation": "unmute",
                    "request": {},
                    "volume": 50,
                    "muted": False,
                },
                {
                    "name": "audio_control_applied",
                    "intent": "SET_VOLUME",
                    "operation": "set_volume",
                    "request": {"volume": 35},
                    "volume": 35,
                    "muted": False,
                },
            ],
        },
    )

    events = []
    actions = _new_actions(None, events)
    error_info: dict[str, Any] = {}

    try:
        actions.execute({
            "intent": "VOLUME_UP",
            "slots": {},
        })
    except ActionExecutionError as e:
        error_info = {
            "intent": e.intent,
            "operation": e.operation,
            "error_code": e.error_code,
            "user_message": e.user_message,
            "event_name": events[0]["name"],
            "event_error_code": events[0]["payload"]["error_code"],
        }

    check(
        "UNAVAILABLE AUDIO SERVICE IS ACTION FAILURE",
        error_info,
        {
            "intent": "VOLUME_UP",
            "operation": "audio_control.change_volume",
            "error_code": "audio_control_unavailable",
            "user_message": "Управление звуком сейчас недоступно.",
            "event_name": "audio_control_failed",
            "event_error_code": "audio_control_unavailable",
        },
    )

    events = []
    audio = FakeAudioControl(
        error=AudioControlOperationError(
            "change_volume",
            "fake CoreAudio failure",
            retry_attempted=True,
        )
    )
    actions = _new_actions(audio, events)
    error_info = {}

    try:
        actions.execute({
            "intent": "VOLUME_DOWN",
            "slots": {},
        })
    except ActionExecutionError as e:
        error_info = {
            "intent": e.intent,
            "operation": e.operation,
            "error_code": e.error_code,
            "detail": e.detail,
            "retry_attempted": e.context.get("retry_attempted"),
            "audio_error_type": e.context.get("error_type"),
            "event_name": events[0]["name"],
        }

    check(
        "STRUCTURED AUDIO ERROR IS CONVERTED",
        error_info,
        {
            "intent": "VOLUME_DOWN",
            "operation": "audio_control.change_volume",
            "error_code": "audio_control_failed",
            "detail": "fake CoreAudio failure",
            "retry_attempted": True,
            "audio_error_type": "AudioControlOperationError",
            "event_name": "audio_control_failed",
        },
    )

    events = []
    actions = _new_actions(FakeAudioControl(), events)
    error_info = {}

    try:
        actions.execute({
            "intent": "SET_VOLUME",
            "slots": {},
        })
    except ActionExecutionError as e:
        error_info = {
            "error_code": e.error_code,
            "user_message": e.user_message,
            "request": e.context.get("request"),
            "event_name": events[0]["name"],
        }

    check(
        "INVALID SET VOLUME REQUEST IS STRUCTURED",
        error_info,
        {
            "error_code": "audio_control_invalid_request",
            "user_message": "Не понял, какую громкость установить.",
            "request": {"volume": None},
            "event_name": "audio_control_failed",
        },
    )

    events = []
    audio = FakeAudioControl(
        error=RuntimeError("fake unexpected failure")
    )
    actions = _new_actions(audio, events)
    error_info = {}

    try:
        actions.execute({
            "intent": "MUTE",
            "slots": {},
        })
    except ActionExecutionError as e:
        error_info = {
            "error_code": e.error_code,
            "detail": e.detail,
            "event_error_type": events[0]["payload"]["error_type"],
        }

    check(
        "UNEXPECTED AUDIO ERROR IS CONVERTED",
        error_info,
        {
            "error_code": "audio_control_unexpected_error",
            "detail": "fake unexpected failure",
            "event_error_type": "RuntimeError",
        },
    )

    events = []
    actions = _new_actions(
        FakeAudioControl(invalid_result=True),
        events,
    )
    error_info = {}

    try:
        actions.execute({
            "intent": "UNMUTE",
            "slots": {},
        })
    except ActionExecutionError as e:
        error_info = {
            "error_code": e.error_code,
            "detail": e.detail,
            "event_name": events[0]["name"],
        }

    check(
        "INVALID AUDIO STATE IS REJECTED",
        error_info,
        {
            "error_code": "audio_control_unexpected_error",
            "detail": "AudioControl returned an invalid state",
            "event_name": "audio_control_failed",
        },
    )

    audio = FakeAudioControl()

    def broken_event_func(
        name: str,
        payload: Dict[str, Any],
    ) -> None:
        _ = name
        _ = payload
        raise RuntimeError("fake event logger failure")

    actions = _new_actions(
        audio,
        [],
        event_func=broken_event_func,
    )
    raised = False

    try:
        actions.execute({
            "intent": "VOLUME_UP",
            "slots": {},
        })
    except Exception:
        raised = True

    check(
        "EVENT LOGGER FAILURE DOES NOT BREAK SUCCESS",
        {
            "raised": raised,
            "calls": audio.calls,
        },
        {
            "raised": False,
            "calls": [("change_volume", 10)],
        },
    )

    events = []
    audio = FakeAudioControl(
        error=AudioControlOperationError(
            "mute",
            "fake mute failure",
        )
    )
    actions = _new_actions(audio, events)
    error_type = ""

    with patch(
        "modules.actions.log_exception",
        side_effect=RuntimeError("fake error logger failure"),
    ):
        try:
            actions.execute({
                "intent": "MUTE",
                "slots": {},
            })
        except Exception as e:
            error_type = type(e).__name__

    check(
        "ERROR LOGGER FAILURE DOES NOT MASK ACTION ERROR",
        {
            "error_type": error_type,
            "event_name": events[0]["name"],
            "event_error": events[0]["payload"]["error"],
        },
        {
            "error_type": "ActionExecutionError",
            "event_name": "audio_control_failed",
            "event_error": "fake mute failure",
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