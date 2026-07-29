from __future__ import annotations

import ctypes
import time
from ctypes import wintypes


WM_CHAR = 0x0102
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D


class TypingService:
    """
    Посимвольная печать в активный сфокусированный контрол через WM_CHAR.
    Это не буфер обмена и не paste.
    """

    def __init__(self, char_delay_sec: float = 0.02, start_delay_sec: float = 0.12):
        self._char_delay_sec = max(0.0, float(char_delay_sec))
        self._start_delay_sec = max(0.0, float(start_delay_sec))

        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        self._kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        self._user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        self._user32.AttachThreadInput.restype = wintypes.BOOL

        self._user32.GetFocus.restype = wintypes.HWND

        self._user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self._user32.SendMessageW.restype = ctypes.c_ssize_t

    def _get_target_hwnd(self) -> int:
        fg = self._user32.GetForegroundWindow()
        if not fg:
            return 0

        pid = wintypes.DWORD(0)
        target_thread_id = self._user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
        current_thread_id = self._kernel32.GetCurrentThreadId()

        attached = False
        try:
            if target_thread_id and target_thread_id != current_thread_id:
                attached = bool(self._user32.AttachThreadInput(current_thread_id, target_thread_id, True))

            focus = self._user32.GetFocus()
            if focus:
                return int(focus)

            return int(fg)
        finally:
            if attached:
                self._user32.AttachThreadInput(current_thread_id, target_thread_id, False)

    def _send_char_code(self, code: int) -> None:
        hwnd = self._get_target_hwnd()
        if not hwnd:
            return
        self._user32.SendMessageW(hwnd, WM_CHAR, code, 0)

    def _send_virtual_key(self, vk_code: int) -> None:
        hwnd = self._get_target_hwnd()
        if not hwnd:
            return

        self._user32.SendMessageW(hwnd, WM_KEYDOWN, vk_code, 0)
        self._user32.SendMessageW(hwnd, WM_KEYUP, vk_code, 0)

    def press_enter(self) -> None:
        if self._start_delay_sec > 0:
            time.sleep(self._start_delay_sec)
        self._send_virtual_key(VK_RETURN)

    def press_backspace(self) -> None:
        if self._start_delay_sec > 0:
            time.sleep(self._start_delay_sec)
        self._send_virtual_key(VK_BACK)

    def press_tab(self) -> None:
        if self._start_delay_sec > 0:
            time.sleep(self._start_delay_sec)
        self._send_virtual_key(VK_TAB)

    def type_text(self, text: str) -> None:
        text = str(text or "")
        if not text:
            return

        if self._start_delay_sec > 0:
            time.sleep(self._start_delay_sec)

        hwnd = self._get_target_hwnd()
        if not hwnd:
            return

        for ch in text:
            self._user32.SendMessageW(hwnd, WM_CHAR, ord(ch), 0)
            if self._char_delay_sec > 0:
                time.sleep(self._char_delay_sec)
