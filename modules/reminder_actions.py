from __future__ import annotations

import time

from datetime import datetime, timedelta, tzinfo
from typing import Any, Callable, Protocol


ClockFunc = Callable[[], float]


class ReminderServiceLike(Protocol):
    def add(self, **kwargs: Any) -> Any:
        ...

    def list_all(self) -> list[Any]:
        ...

    def latest_created(self) -> Any | None:
        ...

    def search_text(self, query: str) -> list[Any]:
        ...

    def cancel(self, reminder_id: str) -> Any:
        ...


_REMINDER_ERROR_MESSAGES = {
    "missing_reminder_time": "Скажи, когда нужно напомнить.",
    "invalid_reminder_time": "Не получилось распознать время напоминания.",
    "ambiguous_reminder_time": (
        "Я услышал несколько вариантов времени. "
        "Назови одно время напоминания."
    ),
    "missing_reminder_text": "Скажи, о чём нужно напомнить.",
    "reminder_in_past": "Это время уже прошло.",
    "reminder_too_far": (
        "Напоминание можно создать не более чем "
        "на 30 дней вперёд."
    ),
    "missing_reminder_target": (
        "Скажи, какое напоминание отменить: "
        "последнее или напоминание с конкретным текстом."
    ),
    "bulk_cancel_not_supported": (
        "Массовая отмена напоминаний пока не поддерживается."
    ),
}


def _plural_ru(
    value: int,
    one: str,
    few: str,
    many: str,
) -> str:
    n = abs(int(value))
    n100 = n % 100
    n10 = n % 10

    if 11 <= n100 <= 14:
        return many
    if n10 == 1:
        return one
    if 2 <= n10 <= 4:
        return few
    return many


class ReminderActions:
    """
    Командный адаптер над ReminderService.

    Отвечает только за:
      - пользовательские ответы;
      - выбор записи для отмены;
      - вызовы add/cancel;
      - компактное форматирование списка.

    Не знает о TTS, event_q, main.py и NLU.
    """

    def __init__(
        self,
        service: ReminderServiceLike,
        *,
        clock: ClockFunc = time.time,
        timezone: tzinfo | None = None,
        list_limit: int = 5,
    ) -> None:
        self._service = service
        self._clock = clock
        self._timezone = timezone
        self._list_limit = max(1, int(list_limit))

    def _to_datetime(self, epoch: float) -> datetime:
        if self._timezone is not None:
            return datetime.fromtimestamp(
                float(epoch),
                tz=self._timezone,
            )

        return datetime.fromtimestamp(
            float(epoch)
        ).astimezone()

    def _now(self) -> datetime:
        return self._to_datetime(self._clock())

    def _format_when(self, epoch: float) -> str:
        due = self._to_datetime(epoch)
        now = self._now()

        if due.date() == now.date():
            return f"сегодня в {due:%H:%M}"

        if due.date() == now.date() + timedelta(days=1):
            return f"завтра в {due:%H:%M}"

        return due.strftime("%d.%m в %H:%M")

    @staticmethod
    def _error_reply(slots: dict[str, Any]) -> str:
        error = str(
            slots.get("reminder_error") or ""
        ).strip()

        if not error:
            return ""

        return _REMINDER_ERROR_MESSAGES.get(
            error,
            "Не получилось обработать напоминание.",
        )

    def reply_create(
        self,
        slots: dict[str, Any],
    ) -> str:
        error_reply = self._error_reply(slots)
        if error_reply:
            return error_reply

        text = str(
            slots.get("reminder_text") or ""
        ).strip()
        due_value = slots.get("due_at_epoch")

        if due_value is None:
            return _REMINDER_ERROR_MESSAGES[
                "missing_reminder_time"
            ]

        if not text:
            return _REMINDER_ERROR_MESSAGES[
                "missing_reminder_text"
            ]

        matched_time = str(
            slots.get("matched_time_text") or ""
        ).strip()

        when = (
            matched_time
            or self._format_when(float(due_value))
        )

        return (
            f"Создаю напоминание {when}: "
            f"{text}."
        )

    def execute_create(
        self,
        slots: dict[str, Any],
    ) -> None:
        if self._error_reply(slots):
            return

        text = str(
            slots.get("reminder_text") or ""
        ).strip()
        due_value = slots.get("due_at_epoch")

        if due_value is None or not text:
            return

        self._service.add(
            text=text,
            due_at_epoch=float(due_value),
        )

    def reply_list(
        self,
        slots: dict[str, Any],
    ) -> str:
        _ = slots
        records = self._service.list_all()

        if not records:
            return "Активных напоминаний нет."

        count = len(records)
        noun = _plural_ru(
            count,
            "напоминание",
            "напоминания",
            "напоминаний",
        )

        visible = records[: self._list_limit]
        parts = [
            (
                f"{index}. "
                f"{self._format_when(record.due_at_epoch)} — "
                f"{record.text}"
            )
            for index, record in enumerate(
                visible,
                start=1,
            )
        ]

        result = (
            f"У тебя {count} {noun}. "
            + ". ".join(parts)
            + "."
        )

        hidden_count = count - len(visible)
        if hidden_count > 0:
            hidden_noun = _plural_ru(
                hidden_count,
                "напоминание",
                "напоминания",
                "напоминаний",
            )
            result += (
                f" И ещё {hidden_count} "
                f"{hidden_noun}."
            )

        return result

    def reply_cancel(
        self,
        slots: dict[str, Any],
    ) -> str:
        slots.pop(
            "_resolved_reminder_id",
            None,
        )

        error_reply = self._error_reply(slots)
        if error_reply:
            return error_reply

        mode = str(
            slots.get("cancel_mode") or ""
        ).strip().lower()

        record = None

        if mode == "latest":
            record = self._service.latest_created()

            if record is None:
                return "Активных напоминаний нет."

        elif mode == "query":
            query = str(
                slots.get("reminder_query") or ""
            ).strip()

            if not query:
                return _REMINDER_ERROR_MESSAGES[
                    "missing_reminder_target"
                ]

            matches = self._service.search_text(query)

            if not matches:
                return (
                    "Напоминание по запросу "
                    f"«{query}» не найдено."
                )

            if len(matches) > 1:
                return (
                    "Нашёл несколько напоминаний по запросу "
                    f"«{query}». Уточни текст."
                )

            record = matches[0]

        else:
            return _REMINDER_ERROR_MESSAGES[
                "missing_reminder_target"
            ]

        slots["_resolved_reminder_id"] = (
            record.reminder_id
        )

        return (
            "Отменяю напоминание: "
            f"{record.text}."
        )

    def execute_cancel(
        self,
        slots: dict[str, Any],
    ) -> None:
        reminder_id = str(
            slots.get("_resolved_reminder_id")
            or ""
        ).strip()

        if not reminder_id:
            return

        self._service.cancel(reminder_id)
