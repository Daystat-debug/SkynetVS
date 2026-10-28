"""Best-effort, text-free attribution of one ordinary main-process route.

The existing private runtime logger is the only sink. An append-returned event
is a call-boundary observation, not fsync durability, read-back or action proof.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
from typing import Any
from uuid import uuid4


EVENT_KIND = "runtime_observation_trace"
MAX_PHRASE_SEQUENCE = 2**31 - 1
EVENTS = frozenset({
    "SESSION_STARTED", "LOOP_READY", "LOOP_EXITED",
    "PHRASE_ENTERED", "PHRASE_RETURNED", "PHRASE_RAISED",
    "COMMAND_ENTERED", "COMMAND_RETURNED", "COMMAND_RAISED",
    "OBSERVATION_ATTEMPTED", "OBSERVATION_APPEND_RETURNED",
    "OBSERVATION_REFUSED", "OBSERVATION_RAISED",
})
REFUSAL_REASONS = frozenset({
    "BUSY", "INVALID_PATH", "UNSAFE_PATH", "DIRECTORY_MISSING",
    "LOCK_INVALID", "LOCK_CHANGED", "STORAGE_ERROR", "CONTROL_INVALID",
    "CONTROL_CHANGED", "ORPHAN_LEDGER", "RUNTIME_REFUSED",
})
PHRASE_REASONS = frozenset({
    "speech_interrupt_stopped", "speech_interrupt_handled",
    "stt_ignored_ack_window", "stt_ignored_after_tts", "stt_ignored",
    "confirmed_executed", "confirmed_not_runnable", "confirmation_cancelled",
    "confirmation_repeat", "confirmation_handled", "dictation_handled",
    "bare_hotword_ignored", "empty_dictation_text", "dictation_stop_phrase",
    "dictation_off_intent", "press_enter", "press_backspace", "press_tab", "typed_text",
    "immediate_hotword_command", "command_window_opened", "hotword_activation_handled",
    "pending_bare_hotword_ignored", "pending_fragment_set", "stop_listen_closed_window",
    "command_executed_window_extended", "command_window_handled", "no_phrase_handler_matched",
    "voice_learning_nlu_error", "voice_learning_start_report_failed",
    "voice_learning_unexpected_idle", "voice_learning_report_failed",
    "voice_learning_start_dialogue_already_active", "voice_learning_start_intent_not_permitted",
    "voice_learning_start_await_phrase", "voice_learning_not_in_learning_mode",
    "voice_learning_invalid_transcript", "voice_learning_learning_timeout",
    "voice_learning_cancelled", "voice_learning_phrase_length", "voice_learning_phrase_words",
    "voice_learning_phrase_control_character", "voice_learning_phrase_reserved",
    "voice_learning_phrase_no_words", "voice_learning_example_already_exists",
    "voice_learning_confirm_required", "voice_learning_confirm_explicit_yes_required",
    "voice_learning_add_example_rejected", "voice_learning_example_confirmed_candidate_only",
    "voice_learning_example_saved_for_training", "voice_learning_example_already_recorded",
    "voice_learning_example_persist_failed",
})


class RuntimeObservationTrace:
    def __init__(self, logger: Any, *, project_root: Path, history_base: str) -> None:
        self._logger = logger
        self._phrase = ContextVar("runtime_observation_phrase", default=None)
        self._next_phrase = 0
        try:
            self._session = uuid4().hex
        except Exception:
            self._session = None
        try:
            actual = os.path.normcase(os.path.abspath(history_base))
            expected = os.path.normcase(os.path.abspath(project_root / "data" / "learning"))
            self._history_scope = "PROJECT" if actual == expected else "OTHER"
        except Exception:
            self._history_scope = "UNKNOWN"

    def _emit(self, event: str, *, reason: str = "NONE", control_state: str = "UNKNOWN") -> None:
        try:
            if self._session is None or event not in EVENTS:
                return
            self._logger.event(EVENT_KIND, {
                "schema": 1,
                "session_id": self._session,
                "phrase_sequence": self._phrase.get(),
                "event": event,
                "reason": reason,
                "control_state": control_state,
                "history_scope": self._history_scope,
            })
        except Exception:
            # Diagnostics must not replace a primary return or exception.
            pass

    def session_started(self) -> None:
        self._emit("SESSION_STARTED")

    def loop_ready(self) -> None:
        self._emit("LOOP_READY")

    def loop_exited(self) -> None:
        self._emit("LOOP_EXITED")

    @contextmanager
    def phrase(self):
        if self._next_phrase >= MAX_PHRASE_SEQUENCE:
            # Disable this trace rather than reuse an ordinal and misattribute.
            self._session = None
            ordinal = None
        else:
            self._next_phrase += 1
            ordinal = self._next_phrase
        token = self._phrase.set(ordinal)
        self._emit("PHRASE_ENTERED")
        try:
            yield
        except Exception:
            self._emit("PHRASE_RAISED")
            raise
        finally:
            self._phrase.reset(token)

    def phrase_returned(self, reason: Any) -> None:
        closed = reason if type(reason) is str and reason in PHRASE_REASONS else "OTHER"
        self._emit("PHRASE_RETURNED", reason=closed)

    @contextmanager
    def command(self):
        self._emit("COMMAND_ENTERED")
        try:
            yield
        except Exception:
            self._emit("COMMAND_RAISED")
            raise
        else:
            self._emit("COMMAND_RETURNED")

    def observation(self, *, status: str, control_state: str, reason: str) -> None:
        if type(status) is not str or status not in {"ATTEMPTED", "APPEND_RETURNED", "REFUSED", "RAISED"}:
            return
        state = control_state if type(control_state) is str and control_state in {
            "ACTIVE", "PREPARING", "LEGACY",
        } else "UNKNOWN"
        closed = "NONE"
        if status == "REFUSED":
            closed = reason if type(reason) is str and reason in REFUSAL_REASONS else "RUNTIME_REFUSED"
        self._emit("OBSERVATION_" + status, reason=closed, control_state=state)
