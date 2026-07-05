from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass


@dataclass
class ActiveWindowInfo:
    hwnd: int
    title: str
    class_name: str
    process_name: str


class WindowContextService:
    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self._user32.GetWindowTextLengthW.restype = ctypes.c_int

        self._user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self._user32.GetWindowTextW.restype = ctypes.c_int

        self._user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self._user32.GetClassNameW.restype = ctypes.c_int

        self._user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel32.OpenProcess.restype = wintypes.HANDLE

        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL

        self._kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

    def _get_foreground_window(self) -> int:
        try:
            hwnd = self._user32.GetForegroundWindow()
            return int(hwnd) if hwnd else 0
        except Exception:
            return 0

    def _get_window_title(self, hwnd: int) -> str:
        if not hwnd:
            return ""

        try:
            length = self._user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(max(256, length + 1))
            self._user32.GetWindowTextW(hwnd, buf, len(buf))
            return (buf.value or "").strip()
        except Exception:
            return ""

    def _get_class_name(self, hwnd: int) -> str:
        if not hwnd:
            return ""

        try:
            buf = ctypes.create_unicode_buffer(256)
            self._user32.GetClassNameW(hwnd, buf, len(buf))
            return (buf.value or "").strip()
        except Exception:
            return ""

    def _get_process_name(self, hwnd: int) -> str:
        if not hwnd:
            return ""

        pid = wintypes.DWORD(0)
        try:
            self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return ""

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = self._kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not handle:
                return ""

            try:
                size = wintypes.DWORD(1024)
                buf = ctypes.create_unicode_buffer(size.value)
                ok = self._kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
                if not ok:
                    return ""
                return os.path.basename(buf.value).strip()
            finally:
                self._kernel32.CloseHandle(handle)
        except Exception:
            return ""

    def get_active_window_info(self) -> ActiveWindowInfo | None:
        hwnd = self._get_foreground_window()
        if not hwnd:
            return None

        return ActiveWindowInfo(
            hwnd=hwnd,
            title=self._get_window_title(hwnd),
            class_name=self._get_class_name(hwnd),
            process_name=self._get_process_name(hwnd),
        )