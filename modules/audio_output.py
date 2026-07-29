from __future__ import annotations

import os
import time

from ctypes import HRESULT
from ctypes.wintypes import LPCWSTR
from dataclasses import dataclass
from typing import Optional

import comtypes
from comtypes import CLSCTX_ALL, COMMETHOD, GUID
from pycaw.pycaw import AudioUtilities

from modules.core.error_log import log_exception


# Windows audio roles
ERole_eConsole = 0
ERole_eMultimedia = 1
ERole_eCommunications = 2
_EROLE_ALL = (ERole_eConsole, ERole_eMultimedia, ERole_eCommunications)
STATUS_SWITCHED = "switched"
STATUS_ALREADY_ACTIVE = "already_active"
STATUS_DEVICE_NOT_FOUND = "device_not_found"
STATUS_AMBIGUOUS_DEVICE = "ambiguous_device"
STATUS_SWITCH_FAILED = "switch_failed"
STATUS_VERIFICATION_FAILED = "verification_failed"
STATUS_CURRENT_UNKNOWN = "current_unknown"


@dataclass(frozen=True)
class OutputDevice:
    id: str
    name: str


@dataclass(frozen=True)
class AudioOutputResult:
    status: str
    changed: bool
    requested_name: str
    target: Optional[OutputDevice]
    before: Optional[OutputDevice]
    after: Optional[OutputDevice]


class AudioOutputError(RuntimeError):
    def __init__(self, message: str, result: AudioOutputResult):
        super().__init__(message)
        self.result = result
        self.status = result.status


class IPolicyConfigVista(comtypes.IUnknown):
    """
    Более совместимый вариант интерфейса для переключения default audio endpoint.
    """
    _iid_ = GUID("{568B9108-44BF-40B4-9006-86AFE5B5A620}")
    _methods_ = [
        COMMETHOD([], HRESULT, "GetMixFormat"),
        COMMETHOD([], HRESULT, "GetDeviceFormat"),
        COMMETHOD([], HRESULT, "SetDeviceFormat"),
        COMMETHOD([], HRESULT, "GetProcessingPeriod"),
        COMMETHOD([], HRESULT, "SetProcessingPeriod"),
        COMMETHOD([], HRESULT, "GetShareMode"),
        COMMETHOD([], HRESULT, "SetShareMode"),
        COMMETHOD([], HRESULT, "GetPropertyValue"),
        COMMETHOD([], HRESULT, "SetPropertyValue"),
        COMMETHOD(
            [],
            HRESULT,
            "SetDefaultEndpoint",
            (["in"], LPCWSTR, "wszDeviceId"),
            (["in"], comtypes.c_int, "eRole"),
        ),
        COMMETHOD([], HRESULT, "SetEndpointVisibility"),
    ]


class AudioOutputControl:
    """
    Переключение default playback device без внешних утилит.
    """

    _POLICY_CONFIG_VISTA_CLSID = GUID(
        "{294935CE-F637-4E7C-A41B-AB255460B862}"
    )

    def __init__(
        self,
        *,
        headphones_name: str,
        speakers_name: str,
        verification_attempts: int = 5,
        verification_delay_sec: float = 0.15,
    ):
        comtypes.CoInitialize()
        self._debug = os.getenv(
            "AUDIO_OUTPUT_DEBUG",
            "0",
        ).strip() == "1"

        self._headphones_name = str(
            headphones_name
        ).strip()
        self._speakers_name = str(
            speakers_name
        ).strip()

        self._verification_attempts = max(
            1,
            int(verification_attempts),
        )
        self._verification_delay_sec = max(
            0.0,
            float(verification_delay_sec),
        )

        if not self._headphones_name:
            raise RuntimeError(
                "Headphones device name is empty"
            )

        if not self._speakers_name:
            raise RuntimeError(
                "Speakers device name is empty"
            )

        if self._norm(
            self._headphones_name
        ) == self._norm(
            self._speakers_name
        ):
            raise RuntimeError(
                "Headphones and speakers device names must be different"
            )

    def _norm(self, value: str) -> str:
        return " ".join(
            (value or "").lower().split()
        )

    def _dbg(self, message: str) -> None:
        if self._debug:
            print(message)

    def _iter_all_devices(
        self,
    ) -> list[OutputDevice]:
        result: list[OutputDevice] = []

        for dev in AudioUtilities.GetAllDevices():
            name = (
                getattr(
                    dev,
                    "FriendlyName",
                    "",
                )
                or ""
            )
            dev_id = (
                getattr(
                    dev,
                    "id",
                    "",
                )
                or getattr(
                    dev,
                    "Id",
                    "",
                )
                or ""
            )

            if not name or not dev_id:
                continue

            if not str(dev_id).startswith(
                "{0.0.0."
            ):
                continue

            result.append(
                OutputDevice(
                    id=str(dev_id),
                    name=str(name),
                )
            )

        return result

    def debug_dump_devices(self) -> None:
        self._dbg(
            "[AUDIO_OUTPUT] available playback devices:"
        )

        for dev in self._iter_all_devices():
            self._dbg(
                f"  - name='{dev.name}' id='{dev.id}'"
            )

    def _find_devices_by_exact_name(
        self,
        target_name: str,
    ) -> list[OutputDevice]:
        target = self._norm(target_name)
        unique: dict[str, OutputDevice] = {}

        for dev in self._iter_all_devices():
            if self._norm(dev.name) != target:
                continue

            unique[
                self._norm(dev.id)
            ] = dev

        matches = list(
            unique.values()
        )

        if matches:
            for dev in matches:
                self._dbg(
                    "[AUDIO_OUTPUT] "
                    f"matched device: "
                    f"'{dev.name}' -> {dev.id}"
                )
        else:
            self._dbg(
                "[AUDIO_OUTPUT] "
                "device not found by exact name: "
                f"'{target_name}'"
            )

        return matches

    def _result(
        self,
        *,
        status: str,
        changed: bool,
        requested_name: str,
        target: Optional[OutputDevice] = None,
        before: Optional[OutputDevice] = None,
        after: Optional[OutputDevice] = None,
    ) -> AudioOutputResult:
        return AudioOutputResult(
            status=status,
            changed=changed,
            requested_name=requested_name,
            target=target,
            before=before,
            after=after,
        )

    def _error(
        self,
        message: str,
        *,
        status: str,
        requested_name: str,
        target: Optional[OutputDevice] = None,
        before: Optional[OutputDevice] = None,
        after: Optional[OutputDevice] = None,
    ) -> AudioOutputError:
        return AudioOutputError(
            message,
            self._result(
                status=status,
                changed=False,
                requested_name=requested_name,
                target=target,
                before=before,
                after=after,
            ),
        )

    def _resolve_exact_device(
        self,
        device_name: str,
    ) -> OutputDevice:
        matches = (
            self._find_devices_by_exact_name(
                device_name
            )
        )

        if not matches:
            raise self._error(
                "Audio output device "
                f"not found: {device_name}",
                status=STATUS_DEVICE_NOT_FOUND,
                requested_name=device_name,
            )

        if len(matches) > 1:
            ids = ", ".join(
                dev.id
                for dev in matches
            )

            raise self._error(
                "Multiple audio output devices "
                f"matched '{device_name}': {ids}",
                status=STATUS_AMBIGUOUS_DEVICE,
                requested_name=device_name,
            )

        return matches[0]

    def current(
        self,
    ) -> Optional[OutputDevice]:
        dev = AudioUtilities.GetSpeakers()

        if dev is None:
            self._dbg(
                "[AUDIO_OUTPUT] current device: None"
            )
            return None

        name = (
            getattr(
                dev,
                "FriendlyName",
                "",
            )
            or ""
        )
        dev_id = (
            getattr(
                dev,
                "id",
                "",
            )
            or getattr(
                dev,
                "Id",
                "",
            )
            or ""
        )

        self._dbg(
            "[AUDIO_OUTPUT] current device: "
            f"name='{name}' id='{dev_id}'"
        )

        if not name and not dev_id:
            return None

        return OutputDevice(
            id=str(dev_id),
            name=str(name),
        )

    def _same_device(
        self,
        left: Optional[OutputDevice],
        right: Optional[OutputDevice],
    ) -> bool:
        if left is None or right is None:
            return False

        if left.id and right.id:
            return (
                self._norm(left.id)
                == self._norm(right.id)
            )

        return bool(
            left.name
            and right.name
            and self._norm(left.name)
            == self._norm(right.name)
        )

    def _policy_config(
        self,
    ) -> IPolicyConfigVista:
        return comtypes.CoCreateInstance(
            self._POLICY_CONFIG_VISTA_CLSID,
            interface=IPolicyConfigVista,
            clsctx=CLSCTX_ALL,
        )

    def _set_default_by_id(
        self,
        device_id: str,
    ) -> None:
        if not device_id:
            raise RuntimeError(
                "Audio output device id is empty"
            )

        self._dbg(
            "[AUDIO_OUTPUT] "
            f"setting default device id='{device_id}'"
        )

        policy_config = (
            self._policy_config()
        )

        for role in _EROLE_ALL:
            hr = (
                policy_config
                .SetDefaultEndpoint(
                    device_id,
                    role,
                )
            )

            if hr not in (None, 0):
                raise RuntimeError(
                    "SetDefaultEndpoint failed "
                    f"for role={role}, hr={hr}"
                )

    def _wait_until_current(
        self,
        target: OutputDevice,
    ) -> Optional[OutputDevice]:
        after: Optional[
            OutputDevice
        ] = None

        for attempt in range(
            self._verification_attempts
        ):
            after = self.current()

            if self._same_device(
                after,
                target,
            ):
                return after

            if (
                attempt + 1
                < self._verification_attempts
            ):
                time.sleep(
                    self._verification_delay_sec
                )

        return after

    def _set_target(
        self,
        *,
        requested_name: str,
        target: Optional[
            OutputDevice
        ] = None,
        before: Optional[
            OutputDevice
        ] = None,
    ) -> AudioOutputResult:
        target = (
            target
            or self._resolve_exact_device(
                requested_name
            )
        )

        before = (
            before
            if before is not None
            else self.current()
        )

        self._dbg(
            "[AUDIO_OUTPUT] target device: "
            f"name='{target.name}' "
            f"id='{target.id}'"
        )

        if self._same_device(
            before,
            target,
        ):
            return self._result(
                status=STATUS_ALREADY_ACTIVE,
                changed=False,
                requested_name=requested_name,
                target=target,
                before=before,
                after=before,
            )

        try:
            self._set_default_by_id(
                target.id
            )
        except Exception as e:
            raise self._error(
                "Audio output switch failed: "
                f"{e}",
                status=STATUS_SWITCH_FAILED,
                requested_name=requested_name,
                target=target,
                before=before,
            ) from e

        after = self._wait_until_current(
            target
        )

        if not self._same_device(
            after,
            target,
        ):
            current_name = (
                after.name
                if after
                else "unavailable"
            )

            raise self._error(
                "Audio output did not switch. "
                f"Current='{current_name}' "
                f"target='{target.name}'",
                status=STATUS_VERIFICATION_FAILED,
                requested_name=requested_name,
                target=target,
                before=before,
                after=after,
            )

        return self._result(
            status=STATUS_SWITCHED,
            changed=True,
            requested_name=requested_name,
            target=target,
            before=before,
            after=after,
        )

    def set_headphones(
        self,
    ) -> AudioOutputResult:
        try:
            return self._set_target(
                requested_name=(
                    self._headphones_name
                )
            )
        except Exception as e:
            log_exception(
                "audio_output.set_headphones",
                e,
                target=self._headphones_name,
            )
            raise

    def set_speakers(
        self,
    ) -> AudioOutputResult:
        try:
            return self._set_target(
                requested_name=(
                    self._speakers_name
                )
            )
        except Exception as e:
            log_exception(
                "audio_output.set_speakers",
                e,
                target=self._speakers_name,
            )
            raise

    def toggle(
        self,
    ) -> AudioOutputResult:
        try:
            current = self.current()

            if current is None:
                raise self._error(
                    "Current audio output "
                    "device is unavailable",
                    status=STATUS_CURRENT_UNKNOWN,
                    requested_name="toggle",
                )

            headphones = (
                self._resolve_exact_device(
                    self._headphones_name
                )
            )
            speakers = (
                self._resolve_exact_device(
                    self._speakers_name
                )
            )

            if self._same_device(
                current,
                headphones,
            ):
                return self._set_target(
                    requested_name=(
                        self._speakers_name
                    ),
                    target=speakers,
                    before=current,
                )

            if self._same_device(
                current,
                speakers,
            ):
                return self._set_target(
                    requested_name=(
                        self._headphones_name
                    ),
                    target=headphones,
                    before=current,
                )

            raise self._error(
                "Current audio output "
                f"is not managed: '{current.name}'",
                status=STATUS_CURRENT_UNKNOWN,
                requested_name="toggle",
                before=current,
                after=current,
            )
        except Exception as e:
            log_exception(
                "audio_output.toggle",
                e,
            )
            raise