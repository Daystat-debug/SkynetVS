from __future__ import annotations

from typing import Any, Mapping

from modules.reminder_service import ReminderFiredEvent


def build_reminder_fired_queue_event(event: ReminderFiredEvent) -> dict[str, Any]:
    return {
        "type": "reminder_fired",
        "reminder": {
            "reminder_id": event.reminder_id,
            "text": event.text,
            "due_at_epoch": event.due_at_epoch,
            "created_at_epoch": event.created_at_epoch,
            "fired_at_epoch": event.fired_at_epoch,
            "late_by_seconds": event.late_by_seconds,
        },
    }


def build_reminder_fired_message(payload: Mapping[str, Any]) -> str:
    text = str(payload.get("text") or "").strip()

    if not text:
        return "Сработало напоминание."

    return f"Напоминаю: {text}"
