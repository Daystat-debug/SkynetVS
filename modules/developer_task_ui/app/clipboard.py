"""Explicit Windows-friendly Tk clipboard bindings for DTR UI widgets only.

No clipboard reads except a user paste action, no automatic uploads, and the
source/request/patch displays remain immutable. Tk's virtual events alone can
be inconsistent with a non-Latin Windows keyboard layout.
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
from typing import Callable


class ClipboardBindings:
    _WIN_KEYCODES = {65: "select", 67: "copy", 86: "paste", 88: "cut"}
    _KEYSYMS = {"a": "select", "c": "copy", "v": "paste", "x": "cut"}

    def __init__(self, root: tk.Misc, *, notify: Callable[[str], None] | None = None,
                 windows_physical_fallback: bool | None = None):
        self.root = root
        self.notify = notify or (lambda message: None)
        self._windows = sys.platform == "win32" if windows_physical_fallback is None else windows_physical_fallback
        self._menus: list[tk.Menu] = []

    @staticmethod
    def _text(widget: tk.Misc) -> bool:
        return isinstance(widget, tk.Text)

    @staticmethod
    def _selected(widget: tk.Misc) -> str | None:
        try:
            if isinstance(widget, tk.Text):
                if not widget.tag_ranges("sel"):
                    return None
                return widget.get("sel.first", "sel.last")
            if isinstance(widget, (tk.Entry, ttk.Entry)) and widget.selection_present():
                return widget.selection_get()
        except tk.TclError:
            return None
        return None

    @staticmethod
    def _delete_selection(widget: tk.Misc) -> None:
        if isinstance(widget, tk.Text):
            if widget.tag_ranges("sel"):
                widget.delete("sel.first", "sel.last")
        elif isinstance(widget, (tk.Entry, ttk.Entry)) and widget.selection_present():
            widget.delete("sel.first", "sel.last")

    def select_all(self, widget: tk.Misc) -> str:
        if self._text(widget):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
        else:
            widget.selection_range(0, "end")
            widget.icursor("end")
        return "break"

    def copy(self, widget: tk.Misc) -> str:
        selected = self._selected(widget)
        if selected is not None:
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        return "break"

    def cut(self, widget: tk.Misc, *, editable: bool) -> str:
        if editable and str(widget.cget("state")) == "normal":
            selected = self._selected(widget)
            if selected is not None:
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self._delete_selection(widget)
        return "break"

    def paste(self, widget: tk.Misc, *, editable: bool) -> str:
        if not editable or str(widget.cget("state")) != "normal":
            return "break"
        try:
            value = self.root.clipboard_get()
        except tk.TclError:
            self.notify("Буфер обмена не содержит доступного текста.")
            return "break"
        if len(value.encode("utf-8")) > 262144:
            self.notify("Текст в буфере слишком большой (более 256 КиБ).")
            return "break"
        self._delete_selection(widget)
        if isinstance(widget, tk.Text):
            widget.insert("insert", value)
        else:
            widget.insert("insert", value)
        return "break"

    def _on_control(self, event: tk.Event, widget: tk.Misc, editable: bool):
        # AltGr is Ctrl+Alt on Windows; don't convert it into clipboard commands.
        if int(getattr(event, "state", 0)) & 0x0008:
            return None
        key = str(getattr(event, "keysym", "")).lower()
        action = self._KEYSYMS.get(key)
        if action is None and self._windows:
            action = self._WIN_KEYCODES.get(int(getattr(event, "keycode", -1)))
        if action == "select":
            return self.select_all(widget)
        if action == "copy":
            return self.copy(widget)
        if action == "cut":
            return self.cut(widget, editable=editable)
        if action == "paste":
            return self.paste(widget, editable=editable)
        return None

    def attach(self, widget: tk.Misc, *, editable: bool) -> None:
        # Explicit Ctrl binding is important for Windows Cyrillic keyboard layout.
        widget.bind("<Control-KeyPress>", lambda event: self._on_control(event, widget, editable), add="+")
        widget.bind("<Control-Insert>", lambda event: self.copy(widget), add="+")
        widget.bind("<Shift-Insert>", lambda event: self.paste(widget, editable=editable), add="+")
        widget.bind("<Shift-Delete>", lambda event: self.cut(widget, editable=editable), add="+")
        menu = tk.Menu(widget, tearoff=False)
        menu.add_command(label="Копировать", command=lambda: self.copy(widget))
        menu.add_command(label="Выделить всё", command=lambda: self.select_all(widget))
        if editable:
            menu.add_separator()
            menu.add_command(label="Вырезать", command=lambda: self.cut(widget, editable=True))
            menu.add_command(label="Вставить", command=lambda: self.paste(widget, editable=True))
        self._menus.append(menu)

        def show_menu(event):
            widget.focus_set()
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        widget.bind("<Button-3>", show_menu, add="+")
