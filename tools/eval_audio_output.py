from __future__ import annotations

import json

from dataclasses import asdict
from typing import Any
from unittest.mock import patch

from modules.audio_output import (
    AudioOutputControl,
    AudioOutputError,
    OutputDevice,
    STATUS_ALREADY_ACTIVE,
    STATUS_AMBIGUOUS_DEVICE,
    STATUS_CURRENT_UNKNOWN,
    STATUS_DEVICE_NOT_FOUND,
    STATUS_SWITCHED,
    STATUS_SWITCH_FAILED,
    STATUS_VERIFICATION_FAILED,
)


HEADPHONES_NAME = (
    "Динамики (6- USB Audio Device)"
)
SPEAKERS_NAME = (
    "Динамики "
    "(Realtek High Definition Audio)"
)

HEADPHONES = OutputDevice(
    id="{0.0.0.00000000}.headphones",
    name=HEADPHONES_NAME,
)
SPEAKERS = OutputDevice(
    id="{0.0.0.00000000}.speakers",
    name=SPEAKERS_NAME,
)
OTHER = OutputDevice(
    id="{0.0.0.00000000}.other",
    name="Монитор",
)


class FakeEndpoint:
    def __init__(
        self,
        device: OutputDevice,
    ):
        self.id = device.id
        self.FriendlyName = device.name


class FakePolicyConfig:
    def __init__(
        self,
        *,
        fail_role: int | None = None,
        fail_hr: int = 5,
    ):
        self.fail_role = fail_role
        self.fail_hr = fail_hr
        self.calls: list[
            tuple[str, int]
        ] = []

    def SetDefaultEndpoint(
        self,
        device_id: str,
        role: int,
    ) -> int:
        self.calls.append(
            (
                device_id,
                role,
            )
        )

        if role == self.fail_role:
            return self.fail_hr

        return 0


def _new_control(
    *,
    attempts: int = 3,
) -> AudioOutputControl:
    with patch(
        "modules.audio_output."
        "comtypes.CoInitialize"
    ):
        return AudioOutputControl(
            headphones_name=HEADPHONES_NAME,
            speakers_name=SPEAKERS_NAME,
            verification_attempts=attempts,
            verification_delay_sec=0.0,
        )


def _error_status(
    call: Any,
) -> str | None:
    try:
        call()
    except AudioOutputError as e:
        return e.status

    return None


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(
        name: str,
        actual: Any,
        expected: Any,
    ) -> None:
        nonlocal case_count
        nonlocal fail_count

        case_count += 1
        ok = actual == expected

        print()
        print(f"=== {name} ===")
        print(
            json.dumps(
                {
                    "actual": actual,
                    "expected": expected,
                    "ok": ok,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    constructor_errors = 0

    with patch(
        "modules.audio_output."
        "comtypes.CoInitialize"
    ):
        for headphones_name, speakers_name in (
            (
                "",
                SPEAKERS_NAME,
            ),
            (
                HEADPHONES_NAME,
                "",
            ),
            (
                HEADPHONES_NAME,
                f"  {HEADPHONES_NAME.lower()}  ",
            ),
        ):
            try:
                AudioOutputControl(
                    headphones_name=(
                        headphones_name
                    ),
                    speakers_name=(
                        speakers_name
                    ),
                )
            except RuntimeError:
                constructor_errors += 1

    check(
        "INVALID CONFIGURATION REJECTED",
        constructor_errors,
        3,
    )

    control = _new_control()

    devices = [
        FakeEndpoint(
            HEADPHONES
        ),
        FakeEndpoint(
            SPEAKERS
        ),
        FakeEndpoint(
            OutputDevice(
                id="capture-device",
                name="Микрофон",
            )
        ),
    ]

    with patch(
        "modules.audio_output."
        "AudioUtilities.GetAllDevices",
        return_value=devices,
    ):
        actual_devices = [
            asdict(device)
            for device
            in control._iter_all_devices()
        ]

    check(
        "ONLY PLAYBACK DEVICES RETURNED",
        actual_devices,
        [
            asdict(HEADPHONES),
            asdict(SPEAKERS),
        ],
    )

    control = _new_control()
    control._iter_all_devices = (
        lambda: [
            HEADPHONES,
            SPEAKERS,
        ]
    )

    check(
        "EXACT NAME NORMALIZATION",
        asdict(
            control._resolve_exact_device(
                f"  {HEADPHONES_NAME.upper()}  "
            )
        ),
        asdict(HEADPHONES),
    )

    control = _new_control()
    control._iter_all_devices = (
        lambda: [
            SPEAKERS,
        ]
    )

    with patch(
        "modules.audio_output."
        "log_exception"
    ):
        not_found_status = (
            _error_status(
                control.set_headphones
            )
        )

    check(
        "DEVICE NOT FOUND STATUS",
        not_found_status,
        STATUS_DEVICE_NOT_FOUND,
    )

    control = _new_control()

    duplicate_headphones = (
        OutputDevice(
            id=(
                "{0.0.0.00000000}."
                "headphones-2"
            ),
            name=HEADPHONES_NAME,
        )
    )

    control._iter_all_devices = (
        lambda: [
            HEADPHONES,
            duplicate_headphones,
        ]
    )

    with patch(
        "modules.audio_output."
        "log_exception"
    ):
        ambiguous_status = (
            _error_status(
                control.set_headphones
            )
        )

    check(
        "AMBIGUOUS DEVICE STATUS",
        ambiguous_status,
        STATUS_AMBIGUOUS_DEVICE,
    )

    control = _new_control()
    control._iter_all_devices = (
        lambda: [
            HEADPHONES,
            SPEAKERS,
        ]
    )
    control.current = (
        lambda: HEADPHONES
    )

    set_calls: list[str] = []

    control._set_default_by_id = (
        lambda device_id:
        set_calls.append(
            device_id
        )
    )

    result = (
        control.set_headphones()
    )

    check(
        "ALREADY ACTIVE SKIPS SWITCH",
        {
            "status": result.status,
            "changed": result.changed,
            "set_calls": set_calls,
            "after": (
                asdict(result.after)
                if result.after
                else None
            ),
        },
        {
            "status": (
                STATUS_ALREADY_ACTIVE
            ),
            "changed": False,
            "set_calls": [],
            "after": asdict(
                HEADPHONES
            ),
        },
    )

    control = _new_control()
    policy = FakePolicyConfig()

    current_values = iter(
        [
            HEADPHONES,
            SPEAKERS,
        ]
    )

    control.current = (
        lambda:
        next(current_values)
    )
    control._iter_all_devices = (
        lambda: [
            HEADPHONES,
            SPEAKERS,
        ]
    )
    control._policy_config = (
        lambda: policy
    )

    result = (
        control.set_speakers()
    )

    check(
        "SUCCESSFUL SWITCH SETS ALL ROLES",
        {
            "status": result.status,
            "changed": result.changed,
            "calls": policy.calls,
            "before": (
                asdict(result.before)
                if result.before
                else None
            ),
            "after": (
                asdict(result.after)
                if result.after
                else None
            ),
        },
        {
            "status": STATUS_SWITCHED,
            "changed": True,
            "calls": [
                (
                    SPEAKERS.id,
                    0,
                ),
                (
                    SPEAKERS.id,
                    1,
                ),
                (
                    SPEAKERS.id,
                    2,
                ),
            ],
            "before": asdict(
                HEADPHONES
            ),
            "after": asdict(
                SPEAKERS
            ),
        },
    )

    control = _new_control()

    policy = FakePolicyConfig(
        fail_role=1
    )

    control.current = (
        lambda: HEADPHONES
    )
    control._iter_all_devices = (
        lambda: [
            HEADPHONES,
            SPEAKERS,
        ]
    )
    control._policy_config = (
        lambda: policy
    )

    with patch(
        "modules.audio_output."
        "log_exception"
    ):
        switch_failed_status = (
            _error_status(
                control.set_speakers
            )
        )

    check(
        "POLICY FAILURE STATUS",
        {
            "status": (
                switch_failed_status
            ),
            "calls": policy.calls,
        },
        {
            "status": (
                STATUS_SWITCH_FAILED
            ),
            "calls": [
                (
                    SPEAKERS.id,
                    0,
                ),
                (
                    SPEAKERS.id,
                    1,
                ),
            ],
        },
    )

    control = _new_control(
        attempts=3
    )

    current_values = iter(
        [
            HEADPHONES,
            HEADPHONES,
            SPEAKERS,
        ]
    )

    control.current = (
        lambda:
        next(current_values)
    )
    control._iter_all_devices = (
        lambda: [
            HEADPHONES,
            SPEAKERS,
        ]
    )
    control._set_default_by_id = (
        lambda device_id: None
    )

    result = (
        control.set_speakers()
    )

    check(
        "VERIFICATION RETRIES UNTIL TARGET",
        {
            "status": result.status,
            "after": (
                asdict(result.after)
                if result.after
                else None
            ),
        },
        {
            "status": STATUS_SWITCHED,
            "after": asdict(
                SPEAKERS
            ),
        },
    )

    control = _new_control(
        attempts=2
    )

    current_values = iter(
        [
            HEADPHONES,
            HEADPHONES,
            HEADPHONES,
        ]
    )

    control.current = (
        lambda:
        next(current_values)
    )
    control._iter_all_devices = (
        lambda: [
            HEADPHONES,
            SPEAKERS,
        ]
    )
    control._set_default_by_id = (
        lambda device_id: None
    )

    with patch(
        "modules.audio_output."
        "log_exception"
    ):
        verification_status = (
            _error_status(
                control.set_speakers
            )
        )

    check(
        "VERIFICATION FAILURE STATUS",
        verification_status,
        STATUS_VERIFICATION_FAILED,
    )

    control = _new_control()
    control.current = (
        lambda: HEADPHONES
    )
    control._iter_all_devices = (
        lambda: [
            HEADPHONES,
            SPEAKERS,
        ]
    )

    def fake_set_target(
        **kwargs: Any,
    ) -> Any:
        return control._result(
            status=STATUS_SWITCHED,
            changed=True,
            requested_name=(
                kwargs["requested_name"]
            ),
            target=kwargs["target"],
            before=kwargs["before"],
            after=kwargs["target"],
        )

    control._set_target = (
        fake_set_target
    )

    result = control.toggle()

    check(
        "TOGGLE HEADPHONES TO SPEAKERS",
        {
            "requested_name": (
                result.requested_name
            ),
            "target": (
                asdict(result.target)
                if result.target
                else None
            ),
            "before": (
                asdict(result.before)
                if result.before
                else None
            ),
        },
        {
            "requested_name": (
                SPEAKERS_NAME
            ),
            "target": asdict(
                SPEAKERS
            ),
            "before": asdict(
                HEADPHONES
            ),
        },
    )

    control = _new_control()
    control.current = (
        lambda: SPEAKERS
    )
    control._iter_all_devices = (
        lambda: [
            HEADPHONES,
            SPEAKERS,
        ]
    )
    control._set_target = (
        fake_set_target
    )

    result = control.toggle()

    check(
        "TOGGLE SPEAKERS TO HEADPHONES",
        {
            "requested_name": (
                result.requested_name
            ),
            "target": (
                asdict(result.target)
                if result.target
                else None
            ),
            "before": (
                asdict(result.before)
                if result.before
                else None
            ),
        },
        {
            "requested_name": (
                HEADPHONES_NAME
            ),
            "target": asdict(
                HEADPHONES
            ),
            "before": asdict(
                SPEAKERS
            ),
        },
    )

    control = _new_control()
    control.current = (
        lambda: OTHER
    )
    control._iter_all_devices = (
        lambda: [
            HEADPHONES,
            SPEAKERS,
            OTHER,
        ]
    )

    with patch(
        "modules.audio_output."
        "log_exception"
    ):
        current_unknown_status = (
            _error_status(
                control.toggle
            )
        )

    check(
        "UNKNOWN CURRENT DEVICE IS NOT SWITCHED",
        current_unknown_status,
        STATUS_CURRENT_UNKNOWN,
    )

    control = _new_control()
    control.current = (
        lambda: None
    )

    with patch(
        "modules.audio_output."
        "log_exception"
    ):
        unavailable_status = (
            _error_status(
                control.toggle
            )
        )

    check(
        "UNAVAILABLE CURRENT DEVICE IS NOT SWITCHED",
        unavailable_status,
        STATUS_CURRENT_UNKNOWN,
    )

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "case_count": case_count,
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())