from __future__ import annotations

from typing import Any, Dict, Optional


class ModeManager:
    """
    v2:
    - режим диктовки
    - состояние окна команд
    - pending-фрагмент команды
    - pending confirmation

    Таймеры и token'ы окна команд остаются в main.py.
    """

    def __init__(self) -> None:
        self._dictation_mode = False
        self._dictation_need_separator = False

        self._command_window_open = False
        self._pending_command_text = ""
        self._pending_command_ts = 0.0

        self._pending_confirmation: Optional[Dict[str, Any]] = None

    # -------------------------
    # Dictation mode
    # -------------------------
    def is_dictation_mode(self) -> bool:
        return self._dictation_mode

    def enter_dictation_mode(self) -> None:
        self._dictation_mode = True
        self._dictation_need_separator = False

    def exit_dictation_mode(self) -> None:
        self._dictation_mode = False
        self._dictation_need_separator = False

    def dictation_prefix(self) -> str:
        return " " if self._dictation_need_separator else ""

    def mark_dictation_text_typed(self) -> None:
        self._dictation_need_separator = True

    def reset_dictation_separator(self) -> None:
        self._dictation_need_separator = False

    # -------------------------
    # Command window
    # -------------------------
    def is_command_window_open(self) -> bool:
        return self._command_window_open

    def open_command_window(self) -> None:
        self._command_window_open = True
        self.clear_pending_command()

    def close_command_window(self) -> None:
        self._command_window_open = False
        self.clear_pending_command()
        self.clear_pending_confirmation()

    # -------------------------
    # Pending command fragment
    # -------------------------
    def has_pending_command(self) -> bool:
        return bool(self._pending_command_text)

    def get_pending_command_text(self) -> str:
        return self._pending_command_text

    def get_pending_command_ts(self) -> float:
        return self._pending_command_ts

    def set_pending_command(self, text: str, ts: float) -> None:
        self._pending_command_text = str(text or "")
        self._pending_command_ts = float(ts or 0.0)

    def clear_pending_command(self) -> None:
        self._pending_command_text = ""
        self._pending_command_ts = 0.0

    # -------------------------
    # Pending confirmation
    # -------------------------
    def has_pending_confirmation(self) -> bool:
        return self._pending_confirmation is not None

    def get_pending_confirmation(self) -> Optional[Dict[str, Any]]:
        return self._pending_confirmation

    def set_pending_confirmation(self, payload: Dict[str, Any]) -> None:
        self._pending_confirmation = payload

    def clear_pending_confirmation(self) -> None:
        self._pending_confirmation = None