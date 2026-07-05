from __future__ import annotations

from ctypes import HRESULT, POINTER
from ctypes.wintypes import LPCWSTR
from dataclasses import dataclass
from typing import Optional

import comtypes
from comtypes import COMMETHOD, GUID
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities
import os

from modules.error_log import log_exception


# Windows audio roles
ERole_eConsole = 0
ERole_eMultimedia = 1
ERole_eCommunications = 2
_EROLE_ALL = (ERole_eConsole, ERole_eMultimedia, ERole_eCommunications)


@dataclass(frozen=True)
class OutputDevice:
    id: str
    name: str


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

    _POLICY_CONFIG_VISTA_CLSID = GUID("{294935CE-F637-4E7C-A41B-AB255460B862}")

    def __init__(self, *, headphones_name: str, speakers_name: str):
        comtypes.CoInitialize()
        self._debug = os.getenv("AUDIO_OUTPUT_DEBUG", "0").strip() == "1"

        self._headphones_name = str(headphones_name).strip()
        self._speakers_name = str(speakers_name).strip()

        if not self._headphones_name:
            raise RuntimeError("Headphones device name is empty")
        if not self._speakers_name:
            raise RuntimeError("Speakers device name is empty")

    def _norm(self, s: str) -> str:
        return " ".join((s or "").lower().split())

    def _dbg(self, msg: str) -> None:
        if self._debug:
            print(msg)

    def _iter_all_devices(self) -> list[OutputDevice]:
        result: list[OutputDevice] = []
        for dev in AudioUtilities.GetAllDevices():
            name = getattr(dev, "FriendlyName", "") or ""
            dev_id = getattr(dev, "id", "") or getattr(dev, "Id", "") or ""
            if not name or not dev_id:
                continue

            # только playback/render устройства
            if not str(dev_id).startswith("{0.0.0."):
                continue

            result.append(OutputDevice(id=dev_id, name=name))
        return result

    def debug_dump_devices(self) -> None:
        self._dbg("[AUDIO_OUTPUT] available playback devices:")
        for dev in self._iter_all_devices():
            self._dbg(f"  - name='{dev.name}' id='{dev.id}'")

    def _find_device_by_exact_name(self, target_name: str) -> Optional[OutputDevice]:
        target = self._norm(target_name)
        for dev in self._iter_all_devices():
            if self._norm(dev.name) == target:
                self._dbg(f"[AUDIO_OUTPUT] matched device: '{dev.name}' -> {dev.id}")
                return dev
        self._dbg(f"[AUDIO_OUTPUT] device not found by exact name: '{target_name}'")
        return None

    def current(self) -> Optional[OutputDevice]:
        dev = AudioUtilities.GetSpeakers()
        if dev is None:
            self._dbg("[AUDIO_OUTPUT] current device: None")
            return None

        name = getattr(dev, "FriendlyName", "") or ""
        dev_id = getattr(dev, "id", "") or getattr(dev, "Id", "") or ""

        self._dbg(f"[AUDIO_OUTPUT] current device: name='{name}' id='{dev_id}'")
        return OutputDevice(id=dev_id, name=name) if name else None

    def _policy_config(self) -> IPolicyConfigVista:
        return comtypes.CoCreateInstance(
            self._POLICY_CONFIG_VISTA_CLSID,
            interface=IPolicyConfigVista,
            clsctx=CLSCTX_ALL,
        )

    def _set_default_by_id(self, device_id: str) -> None:
        if not device_id:
            raise RuntimeError("Audio output device id is empty")

        self._dbg(f"[AUDIO_OUTPUT] setting default device id='{device_id}'")
        pc = self._policy_config()

        for role in _EROLE_ALL:
            hr = pc.SetDefaultEndpoint(device_id, role)
            if hr != 0:
                raise RuntimeError(f"SetDefaultEndpoint failed for role={role}, hr={hr}")

    def _set_default_by_name(self, device_name: str) -> None:
        dev = self._find_device_by_exact_name(device_name)
        if dev is None:
            raise RuntimeError(f"Audio output device not found: {device_name}")

        before = self.current()
        self._dbg(f"[AUDIO_OUTPUT] target device: name='{dev.name}' id='{dev.id}'")
        self._set_default_by_id(dev.id)

        after = self.current()
        if after is None:
            raise RuntimeError("Audio output switched, but current device is unavailable")

        if self._norm(after.id) != self._norm(dev.id) and self._norm(after.name) != self._norm(dev.name):
            raise RuntimeError(
                f"Audio output did not switch. Current='{after.name}' target='{dev.name}'"
            )

    def set_headphones(self) -> None:
        try:
            self._set_default_by_name(self._headphones_name)
        except Exception as e:
            log_exception("audio_output.set_headphones", e, target=self._headphones_name)
            raise

    def set_speakers(self) -> None:
        try:
            self._set_default_by_name(self._speakers_name)
        except Exception as e:
            log_exception("audio_output.set_speakers", e, target=self._speakers_name)
            raise

    def toggle(self) -> None:
        try:
            cur = self.current()
            cur_name = self._norm(cur.name) if cur else ""
            hp = self._norm(self._headphones_name)
            sp = self._norm(self._speakers_name)

            if cur_name == hp:
                self.set_speakers()
                return
            if cur_name == sp:
                self.set_headphones()
                return

            self.set_headphones()
        except Exception as e:
            log_exception("audio_output.toggle", e)
            raise
