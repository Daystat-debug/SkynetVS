from __future__ import annotations

import re

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from modules.reminder_datetime_parser import (
    ReminderDateTimeParseResult,
    normalize_reminder_text,
    parse_reminder_datetime,
)


CREATE_REMINDER = "CREATE_REMINDER"
LIST_REMINDERS = "LIST_REMINDERS"
CANCEL_REMINDER = "CANCEL_REMINDER"


@dataclass(frozen=True)
class ReminderCommandParseResult:
    intent: str | None
    slots: dict[str, Any]
    error: str | None
    normalized_text: str
    rule: str | None

    @property
    def recognized(self) -> bool:
        return self.intent is not None

    @property
    def ok(self) -> bool:
        return self.recognized and self.error is None

    def to_meta(self) -> dict[str, Any] | None:
        if not self.recognized:
            return None

        return {
            "intent": self.intent,
            "confidence": 1.0,
            "slots": dict(self.slots),
            "_rule": self.rule or "reminder_command_rule",
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "slots": dict(self.slots),
            "error": self.error,
            "normalized_text": self.normalized_text,
            "rule": self.rule,
        }


_LIST_PHRASES = {
    "какие у меня напоминания",
    "покажи напоминания",
    "покажи мои напоминания",
    "список напоминаний",
    "что у меня по напоминаниям",
    "есть ли у меня напоминания",
}

_LATEST_CANCEL_PHRASES = {
    "отмени последнее напоминание",
    "удали последнее напоминание",
    "сними последнее напоминание",
}

_CREATE_PREFIXES = (
    "напомни",
    "напомню",
    "напомнить",
    "создай напоминание",
    "поставь напоминание",
)

_CANCEL_VERBS = (
    "отмени",
    "удали",
    "сними",
)


def _empty_result(normalized_text: str) -> ReminderCommandParseResult:
    return ReminderCommandParseResult(
        intent=None,
        slots={},
        error=None,
        normalized_text=normalized_text,
        rule=None,
    )


def _normalize_create_phrase(text: str) -> str | None:
    if text == "напомни" or text.startswith("напомни "):
        return text

    for prefix in _CREATE_PREFIXES[1:]:
        if text == prefix:
            return "напомни"
        if text.startswith(prefix + " "):
            tail = text[len(prefix):].strip()
            return f"напомни {tail}".strip()

    return None


def _create_slots(
    parsed: ReminderDateTimeParseResult,
) -> dict[str, Any]:
    slots: dict[str, Any] = {}

    if parsed.due_at_epoch is not None:
        slots["due_at_epoch"] = float(parsed.due_at_epoch)

    if parsed.reminder_text:
        slots["reminder_text"] = parsed.reminder_text

    if parsed.time_kind:
        slots["reminder_time_kind"] = parsed.time_kind

    if parsed.matched_time_text:
        slots["matched_time_text"] = parsed.matched_time_text

    if parsed.error:
        slots["reminder_error"] = parsed.error

    return slots


def _parse_create(
    normalized_text: str,
    *,
    now: datetime | None,
) -> ReminderCommandParseResult | None:
    parser_text = _normalize_create_phrase(
        normalized_text
    )

    if parser_text is None:
        return None

    parsed = parse_reminder_datetime(
        parser_text,
        now=now,
    )

    return ReminderCommandParseResult(
        intent=CREATE_REMINDER,
        slots=_create_slots(parsed),
        error=parsed.error,
        normalized_text=normalized_text,
        rule="reminder_create_rule",
    )


def _parse_list(
    normalized_text: str,
) -> ReminderCommandParseResult | None:
    if normalized_text not in _LIST_PHRASES:
        return None

    return ReminderCommandParseResult(
        intent=LIST_REMINDERS,
        slots={},
        error=None,
        normalized_text=normalized_text,
        rule="reminder_list_rule",
    )


def _parse_cancel(
    normalized_text: str,
) -> ReminderCommandParseResult | None:
    if normalized_text in _LATEST_CANCEL_PHRASES:
        return ReminderCommandParseResult(
            intent=CANCEL_REMINDER,
            slots={"cancel_mode": "latest"},
            error=None,
            normalized_text=normalized_text,
            rule="reminder_cancel_rule",
        )

    if not normalized_text.startswith(
        tuple(f"{verb} " for verb in _CANCEL_VERBS)
    ):
        return None

    if "напомин" not in normalized_text:
        return None

    if re.search(
        r"\b(?:все|всё)\s+напоминания\b",
        normalized_text,
    ):
        error = "bulk_cancel_not_supported"
        return ReminderCommandParseResult(
            intent=CANCEL_REMINDER,
            slots={"reminder_error": error},
            error=error,
            normalized_text=normalized_text,
            rule="reminder_cancel_rule",
        )

    patterns = (
        r"^(?:отмени|удали|сними)\s+напоминание\s+про\s+(.+)$",
        r"^(?:отмени|удали|сними)\s+напоминание\s+(.+)$",
    )

    for pattern in patterns:
        match = re.match(pattern, normalized_text)
        if not match:
            continue

        query = (match.group(1) or "").strip(" .,!?:;")

        if query:
            return ReminderCommandParseResult(
                intent=CANCEL_REMINDER,
                slots={
                    "cancel_mode": "query",
                    "reminder_query": query,
                },
                error=None,
                normalized_text=normalized_text,
                rule="reminder_cancel_rule",
            )

    if normalized_text in {
        "отмени напоминание",
        "удали напоминание",
        "сними напоминание",
    }:
        error = "missing_reminder_target"
        return ReminderCommandParseResult(
            intent=CANCEL_REMINDER,
            slots={"reminder_error": error},
            error=error,
            normalized_text=normalized_text,
            rule="reminder_cancel_rule",
        )

    return None


def parse_reminder_command(
    text: str,
    *,
    now: datetime | None = None,
) -> ReminderCommandParseResult:
    """
    Детерминированно распознаёт команды напоминаний.

    Не выполняет команды и не обращается к repository/service.
    """
    normalized = normalize_reminder_text(text)

    if not normalized:
        return _empty_result(normalized)

    for parser in (
        lambda value: _parse_create(value, now=now),
        _parse_list,
        _parse_cancel,
    ):
        result = parser(normalized)
        if result is not None:
            return result

    return _empty_result(normalized)
