"""M081: pure, non-executing confirmation dialogue for existing SkynetVS intents.

No persistence, no model loading, no action routing. The caller must explicitly
arm a known action, then route subsequent recognized speech here first.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import math
import re
import time
from typing import Any, Callable, Mapping

from tools.label_inbox import add_example


_ALLOWED_CONFIRM = frozenset(("да", "подтверждаю"))
_ALLOWED_CANCEL = frozenset(("нет", "отмена", "отменить"))
_RESERVED_PHRASES = _ALLOWED_CONFIRM | _ALLOWED_CANCEL | frozenset(("стоп", "хватит"))
_MAX_PHRASE_LENGTH = 160


def normalize_phrase(s: str) -> str:
    if not isinstance(s, str):
        raise ValueError("PHRASE_NOT_TEXT")
    return " ".join(s.casefold().split())


def validate_intents(data: Mapping[str, Any]) -> tuple[set[str], dict[str, str]]:
    """Validate the existing {intents:[{intent,examples}]} training format."""
    if not isinstance(data, dict) or "intents" not in data:
        raise ValueError("INTENTS_SCHEMA")
    rows = data["intents"]
    if not isinstance(rows, list) or not (1 <= len(rows) <= 128):
        raise ValueError("INTENTS_COUNT")
    names: set[str] = set()
    examples: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or "intent" not in row or "examples" not in row:
            raise ValueError("INTENT_ROW_SCHEMA")
        name = row["intent"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", name):
            raise ValueError("INTENT_NAME")
        if name in names:
            raise ValueError("INTENT_DUPLICATE")
        names.add(name)
        vals = row["examples"]
        if not isinstance(vals, list) or len(vals) > 5000:
            raise ValueError("EXAMPLES_SCHEMA")
        for val in vals:
            if not isinstance(val, str) or not (1 <= len(val) <= 200):
                raise ValueError("EXAMPLE_INVALID")
            key = normalize_phrase(val)
            if not key or key in examples:
                raise ValueError("EXAMPLE_COLLISION")
            examples[key] = name
    return names, examples


def _phrase_quality(text: str) -> str:
    if not (5 <= len(text) <= _MAX_PHRASE_LENGTH):
        return "PHRASE_LENGTH"
    if len(text.split()) < 2 or len(text.split()) > 24:
        return "PHRASE_WORDS"
    if any((ord(c) < 32 or ord(c) == 127) for c in text):
        return "PHRASE_CONTROL_CHARACTER"
    if text in _RESERVED_PHRASES:
        return "PHRASE_RESERVED"
    if not re.search(r"[а-яёa-z]", text):
        return "PHRASE_NO_WORDS"
    return ""


@dataclass(frozen=True)
class DialogueEvent:
    state: str
    code: str
    message: str
    consumed: bool
    row: dict[str, Any] | None = None
    preview_data: dict[str, Any] | None = None


class ConfirmedVoiceLearning:
    """A caller-driven, bounded two-step input -> confirm state machine.

    This is NOT a voice parser/registrar. The caller's management UI explicitly
    supplies a vetted intent ID and must keep this session above normal NLU
    while pending. Nothing is stored until caller separately persists output.
    """
    def __init__(
        self,
        *,
        data: dict[str, Any],
        operator_allowed_intents: frozenset[str],
        ttl_seconds: float = 45,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._base = copy.deepcopy(data)
        self._names, self._examples = validate_intents(self._base)
        if not isinstance(operator_allowed_intents, frozenset) or not operator_allowed_intents.issubset(self._names):
            raise ValueError("UNREGISTERED_CAPABILITY_ID")
        if not (1 <= ttl_seconds <= 120) or not math.isfinite(ttl_seconds):
            raise ValueError("TTL_INVALID")
        self._allowed = operator_allowed_intents
        self._ttl = ttl_seconds
        self._clock = clock
        self._phase = "IDLE"
        self._intent = ""
        self._phrase = ""
        self._expires = 0.0

    @property
    def state(self) -> str:
        return self._phase

    def _reset(self) -> None:
        self._phase = "IDLE"
        self._intent = ""
        self._phrase = ""
        self._expires = 0.0

    def arm(self, intent: str) -> DialogueEvent:
        if self._phase != "IDLE":
            return DialogueEvent(self._phase, "DIALOGUE_ALREADY_ACTIVE", "Сначала заверши текущую попытку обучения.", True)
        if not isinstance(intent, str) or intent not in self._allowed:
            return DialogueEvent("IDLE", "INTENT_NOT_PERMITTED", "Это действие пока нельзя обучать.", True)
        self._phase = "AWAIT_PHRASE"
        self._intent = intent
        self._expires = self._clock() + self._ttl
        return DialogueEvent(self._phase, "AWAIT_PHRASE", "Назови новую фразу для выбранного действия.", True)

    def on_transcript(self, recognized_text: str) -> DialogueEvent:
        if self._phase == "IDLE":
            return DialogueEvent("IDLE", "NOT_IN_LEARNING_MODE", "", False)
        if not isinstance(recognized_text, str):
            self._reset()
            return DialogueEvent("IDLE", "INVALID_TRANSCRIPT", "Обучение отменено.", True)
        if self._clock() > self._expires:
            self._reset()
            return DialogueEvent("IDLE", "LEARNING_TIMEOUT", "Время подтверждения истекло.", True)
        text = normalize_phrase(recognized_text)
        if text in _ALLOWED_CANCEL:
            self._reset()
            return DialogueEvent("IDLE", "CANCELLED", "Обучение отменено.", True)
        if self._phase == "AWAIT_PHRASE":
            issue = _phrase_quality(text)
            if issue:
                return DialogueEvent(self._phase, issue, "Назови более конкретную фразу.", True)
            if text in self._examples:
                return DialogueEvent(self._phase, "EXAMPLE_ALREADY_EXISTS", "Такая фраза уже есть в обучении.", True)
            self._phrase = text
            self._phase = "AWAIT_CONFIRMATION"
            self._expires = self._clock() + self._ttl
            return DialogueEvent(self._phase, "CONFIRM_REQUIRED", f"Запомнить фразу «{text}» для {self._intent}? Скажи «да» или «нет».", True)
        if text not in _ALLOWED_CONFIRM:
            return DialogueEvent(self._phase, "CONFIRM_EXPLICIT_YES_REQUIRED", "Подтверди только словом «да» или отмени словом «нет».", True)
        # No side effects; the unchanged existing label_inbox.add_example is used on COPY.
        output = copy.deepcopy(self._base)
        if not add_example(output, self._intent, self._phrase):
            self._reset()
            return DialogueEvent("IDLE", "ADD_EXAMPLE_REJECTED", "Пример не сохранён.", True)
        row = {
            "text": self._phrase,
            "meta": {"intent": None, "confidence": None, "slots": {}, "say": ""},
            "label": self._intent,
            "added": True,
            "approved": True,
            "source": "VOICE_LEARNING_USER_CONFIRMATION_CANDIDATE",
        }
        self._reset()
        return DialogueEvent(
            "IDLE", "EXAMPLE_CONFIRMED_CANDIDATE_ONLY",
            "Фраза подтверждена для очереди обучения. Модель ещё не переобучена и команда не активирована.",
            True, row=row, preview_data=output,
        )
