from __future__ import annotations

import json

from pathlib import Path
from typing import Any

from modules.audio_control import (
    AudioControl,
    AudioControlOperationError,
    AudioControlUnavailableError,
    AudioControlVerificationError,
    AudioEndpointBinding,
)


class FakeDevice:
    pass


class FakeEndpoint:
    def __init__(
        self,
        *,
        volume: float = 0.5,
        muted: bool = False,
        read_error: Exception | None = None,
        set_volume_error: Exception | None = None,
        set_mute_error: Exception | None = None,
        set_volume_result: Any = None,
        set_mute_result: Any = None,
        ignore_volume_write: bool = False,
        ignore_mute_write: bool = False,
    ):
        self.volume = float(volume)
        self.muted = bool(muted)
        self.read_error = read_error
        self.set_volume_error = set_volume_error
        self.set_mute_error = set_mute_error
        self.set_volume_result = set_volume_result
        self.set_mute_result = set_mute_result
        self.ignore_volume_write = ignore_volume_write
        self.ignore_mute_write = ignore_mute_write
        self.volume_set_calls: list[float] = []
        self.mute_set_calls: list[int] = []

    def GetMasterVolumeLevelScalar(self) -> float:
        if self.read_error is not None:
            raise self.read_error

        return self.volume

    def GetMute(self) -> int:
        if self.read_error is not None:
            raise self.read_error

        return int(self.muted)

    def SetMasterVolumeLevelScalar(self, value: float, context: Any) -> Any:
        _ = context
        self.volume_set_calls.append(float(value))

        if self.set_volume_error is not None:
            raise self.set_volume_error

        if not self.ignore_volume_write:
            self.volume = float(value)

        return self.set_volume_result

    def SetMute(self, value: int, context: Any) -> Any:
        _ = context
        self.mute_set_calls.append(int(value))

        if self.set_mute_error is not None:
            raise self.set_mute_error

        if not self.ignore_mute_write:
            self.muted = bool(value)

        return self.set_mute_result


class SequenceProvider:
    def __init__(self, *values: Any):
        self.values = list(values)
        self.calls = 0

    def __call__(self) -> AudioEndpointBinding:
        self.calls += 1
        index = min(self.calls - 1, len(self.values) - 1)
        value = self.values[index]

        if isinstance(value, BaseException):
            raise value

        return value


def binding(
    endpoint: Any,
    device_id: str = "device-1",
    device_name: str = "Speakers",
) -> AudioEndpointBinding:
    return AudioEndpointBinding(
        device=FakeDevice(),
        endpoint=endpoint,
        device_id=device_id,
        device_name=device_name,
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

    provider = SequenceProvider(
        AudioControlUnavailableError("bind", "no endpoint"),
        AudioControlUnavailableError("bind", "no endpoint"),
    )
    error_info = {}

    try:
        AudioControl(endpoint_provider=provider, retry_delay_sec=0.0)
    except AudioControlUnavailableError as e:
        error_info = {
            "operation": e.operation,
            "detail": e.detail,
            "retry_attempted": e.retry_attempted,
            "provider_calls": provider.calls,
        }

    check(
        "INITIALIZATION FAILURE IS EXPLICIT",
        error_info,
        {
            "operation": "initialize",
            "detail": "no endpoint",
            "retry_attempted": True,
            "provider_calls": 2,
        },
    )

    endpoint = FakeEndpoint(volume=0.42, muted=True)
    audio = AudioControl(
        endpoint_provider=lambda: binding(endpoint, "device-a", "Headphones"),
        retry_delay_sec=0.0,
        validate_on_init=False,
    )
    probe = audio.probe()

    check(
        "READ ONLY PROBE",
        {
            "device_id": probe.device_id,
            "device_name": probe.device_name,
            "volume": probe.volume,
            "muted": probe.muted,
            "volume_writes": endpoint.volume_set_calls,
            "mute_writes": endpoint.mute_set_calls,
        },
        {
            "device_id": "device-a",
            "device_name": "Headphones",
            "volume": 42,
            "muted": True,
            "volume_writes": [],
            "mute_writes": [],
        },
    )

    speakers = FakeEndpoint(volume=0.30)
    headphones = FakeEndpoint(volume=0.80)
    provider = SequenceProvider(
        binding(speakers, "speakers", "Speakers"),
        binding(headphones, "headphones", "Headphones"),
    )
    audio = AudioControl(
        endpoint_provider=provider,
        retry_delay_sec=0.0,
        validate_on_init=False,
    )
    first = audio.probe()
    second = audio.probe()

    check(
        "DEFAULT ENDPOINT IS RESOLVED PER OPERATION",
        {
            "first": [first.device_id, first.volume],
            "second": [second.device_id, second.volume],
            "provider_calls": provider.calls,
        },
        {
            "first": ["speakers", 30],
            "second": ["headphones", 80],
            "provider_calls": 2,
        },
    )

    speakers = FakeEndpoint(volume=0.35)
    headphones = FakeEndpoint(volume=0.80)
    provider = SequenceProvider(
        binding(speakers, "speakers", "Speakers"),
        binding(headphones, "headphones", "Headphones"),
    )
    audio = AudioControl(
        endpoint_provider=provider,
        retry_delay_sec=0.0,
        validate_on_init=False,
    )
    before_switch = audio.probe()
    after_switch = audio.change_volume(-10)

    check(
        "VOLUME AFTER OUTPUT SWITCH USES ACTIVE ENDPOINT",
        {
            "before_device": before_switch.device_id,
            "after_volume": after_switch.volume,
            "speakers_volume": round(speakers.volume * 100),
            "headphones_volume": round(headphones.volume * 100),
            "speakers_writes": speakers.volume_set_calls,
            "headphones_writes": headphones.volume_set_calls,
        },
        {
            "before_device": "speakers",
            "after_volume": 70,
            "speakers_volume": 35,
            "headphones_volume": 70,
            "speakers_writes": [],
            "headphones_writes": [0.7],
        },
    )

    stale = FakeEndpoint(
        volume=0.30,
        read_error=RuntimeError("stale endpoint"),
    )
    fresh = FakeEndpoint(volume=0.70)
    provider = SequenceProvider(
        binding(stale),
        binding(fresh),
    )
    audio = AudioControl(
        endpoint_provider=provider,
        retry_delay_sec=0.0,
        validate_on_init=False,
    )
    state = audio.get_state()

    check(
        "READ RETRIES WITH FRESH ENDPOINT",
        {
            "volume": state.volume,
            "provider_calls": provider.calls,
        },
        {
            "volume": 70,
            "provider_calls": 2,
        },
    )

    stale = FakeEndpoint(
        volume=0.30,
        set_volume_error=RuntimeError("stale endpoint"),
    )
    fresh = FakeEndpoint(volume=0.30)
    provider = SequenceProvider(
        binding(stale),
        binding(fresh),
    )
    audio = AudioControl(
        endpoint_provider=provider,
        retry_delay_sec=0.0,
        validate_on_init=False,
    )
    state = audio.set_volume(65)

    check(
        "ABSOLUTE WRITE RETRIES SAFELY",
        {
            "volume": state.volume,
            "provider_calls": provider.calls,
            "stale_writes": stale.volume_set_calls,
            "fresh_writes": fresh.volume_set_calls,
        },
        {
            "volume": 65,
            "provider_calls": 2,
            "stale_writes": [0.65],
            "fresh_writes": [0.65],
        },
    )

    endpoint = FakeEndpoint(volume=0.50)
    audio = AudioControl(
        endpoint_provider=lambda: binding(endpoint),
        retry_delay_sec=0.0,
        validate_on_init=False,
    )
    low = audio.set_volume(-10)
    high = audio.set_volume(150)

    check(
        "VOLUME IS CLAMPED AND VERIFIED",
        {
            "low": low.volume,
            "high": high.volume,
            "writes": endpoint.volume_set_calls,
        },
        {
            "low": 0,
            "high": 100,
            "writes": [0.0, 1.0],
        },
    )

    endpoint = FakeEndpoint(
        volume=0.50,
        ignore_volume_write=True,
    )
    audio = AudioControl(
        endpoint_provider=lambda: binding(endpoint),
        retry_delay_sec=0.0,
        validate_on_init=False,
    )
    error_info = {}

    try:
        audio.set_volume(75)
    except AudioControlVerificationError as e:
        error_info = {
            "operation": e.operation,
            "retry_attempted": e.retry_attempted,
            "writes": endpoint.volume_set_calls,
        }

    check(
        "VOLUME VERIFICATION FAILURE IS EXPLICIT",
        error_info,
        {
            "operation": "set_volume",
            "retry_attempted": True,
            "writes": [0.75, 0.75],
        },
    )

    endpoint = FakeEndpoint(volume=0.40, muted=False)
    audio = AudioControl(
        endpoint_provider=lambda: binding(endpoint),
        retry_delay_sec=0.0,
        validate_on_init=False,
    )
    muted = audio.mute()
    unmuted = audio.unmute()

    check(
        "MUTE AND UNMUTE ARE VERIFIED",
        {
            "muted": muted.muted,
            "unmuted": unmuted.muted,
            "writes": endpoint.mute_set_calls,
        },
        {
            "muted": True,
            "unmuted": False,
            "writes": [1, 0],
        },
    )

    endpoint = FakeEndpoint(
        volume=0.50,
        set_volume_result=5,
    )
    audio = AudioControl(
        endpoint_provider=lambda: binding(endpoint),
        retry_delay_sec=0.0,
        validate_on_init=False,
    )
    error_info = {}

    try:
        audio.set_volume(60)
    except AudioControlOperationError as e:
        error_info = {
            "operation": e.operation,
            "detail": e.detail,
            "retry_attempted": e.retry_attempted,
        }

    check(
        "NONZERO COREAUDIO RESULT FAILS",
        error_info,
        {
            "operation": "set_volume",
            "detail": "CoreAudio returned 5",
            "retry_attempted": True,
        },
    )

    invalid_count = 0
    audio = AudioControl(
        endpoint_provider=lambda: binding(FakeEndpoint()),
        retry_delay_sec=0.0,
        validate_on_init=False,
    )

    for call in (
        lambda: audio.set_volume(True),
        lambda: audio.set_volume("bad"),
        lambda: audio.change_volume(False),
        lambda: audio.change_volume("bad"),
    ):
        try:
            call()
        except ValueError:
            invalid_count += 1

    check(
        "INVALID VOLUME INPUT IS REJECTED",
        invalid_count,
        4,
    )

    source = Path("modules/audio_control.py").read_text(encoding="utf-8")

    check(
        "PRODUCTION USES HIGH LEVEL PYCAW ENDPOINT",
        {
            "uses_endpoint_volume": "EndpointVolume" in source,
            "uses_get_speakers": "AudioUtilities.GetSpeakers()" in source,
            "uses_ctypes_cast": "from ctypes import" in source or "cast(" in source,
            "uses_manual_interface": "IAudioEndpointVolume" in source,
        },
        {
            "uses_endpoint_volume": True,
            "uses_get_speakers": True,
            "uses_ctypes_cast": False,
            "uses_manual_interface": False,
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