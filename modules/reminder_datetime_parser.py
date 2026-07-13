from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from typing import Any


MIN_REMINDER_LEAD_SEC = 1
MAX_REMINDER_HORIZON_SEC = 30 * 24 * 60 * 60


@dataclass(frozen=True)
class ReminderDateTimeParseResult:
    due_at: datetime | None
    due_at_epoch: float | None
    reminder_text: str
    time_kind: str | None
    matched_time_text: str
    error: str | None
    normalized_text: str

    @property
    def ok(self) -> bool:
        return self.due_at is not None and self.due_at_epoch is not None and self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "due_at": self.due_at.isoformat() if self.due_at is not None else None,
            "due_at_epoch": self.due_at_epoch,
            "reminder_text": self.reminder_text,
            "time_kind": self.time_kind,
            "matched_time_text": self.matched_time_text,
            "error": self.error,
            "normalized_text": self.normalized_text,
        }


@dataclass(frozen=True)
class _Token:
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class _TimeCandidate:
    start: int
    end: int
    due_at: datetime
    time_kind: str
    matched_text: str


_NUMBER_WORDS = {
    "ноль": 0,
    "один": 1, "одна": 1, "одно": 1, "одну": 1,
    "два": 2, "две": 2,
    "три": 3, "четыре": 4, "пять": 5, "шесть": 6,
    "семь": 7, "восемь": 8, "девять": 9,
    "десять": 10, "одиннадцать": 11, "двенадцать": 12,
    "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15,
    "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18,
    "девятнадцать": 19,
    "двадцать": 20, "тридцать": 30, "сорок": 40,
    "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
    "восемьдесят": 80, "девяносто": 90,
    "сто": 100, "двести": 200, "триста": 300, "четыреста": 400,
    "пятьсот": 500, "шестьсот": 600, "семьсот": 700,
    "восемьсот": 800, "девятьсот": 900,
}

_RELATIVE_UNITS = {
    "секунда": ("seconds", 1), "секунду": ("seconds", 1),
    "секунды": ("seconds", 1), "секунд": ("seconds", 1),
    "сек": ("seconds", 1),
    "минута": ("minutes", 60), "минуту": ("minutes", 60),
    "минуты": ("minutes", 60), "минут": ("minutes", 60),
    "мин": ("minutes", 60),
    "час": ("hours", 3600), "часа": ("hours", 3600),
    "часов": ("hours", 3600),
    "день": ("days", 86400), "дня": ("days", 86400),
    "дней": ("days", 86400), "сутки": ("days", 86400),
    "суток": ("days", 86400),
}

_BARE_UNITS = {"секунда", "секунду", "минута", "минуту", "час", "день", "сутки"}
_DAY_MARKERS = {"сегодня": (0, "today"), "завтра": (1, "tomorrow")}
_DAY_PARTS = {"утра", "дня", "вечера", "ночи"}


def normalize_reminder_text(text: str) -> str:
    value = str(text or "").lower()
    value = re.sub(r"[\t\r\n,]+", " ", value)
    return " ".join(value.split())


def _strip_reminder_prefix(text: str) -> str:
    pattern = (
        r"^(?:пожалуйста\s+)?напомни(?:\s+мне)?"
        r"(?:\s+пожалуйста)?(?:\s+что)?\s*"
    )
    return re.sub(pattern, "", text, count=1).strip()


def _tokenize(text: str) -> list[_Token]:
    return [
        _Token(match.group(0), match.start(), match.end())
        for match in re.finditer(r"\d+|[a-zа-яё]+", text, flags=re.IGNORECASE)
    ]


def _is_number(token: str) -> bool:
    return token.isdigit() or token in _NUMBER_WORDS


def _parse_number(tokens: list[str]) -> int | None:
    if not tokens:
        return None
    if len(tokens) == 1 and tokens[0].isdigit():
        return int(tokens[0])
    if any(token.isdigit() for token in tokens):
        return None

    total = 0
    seen_hundreds = seen_tens = seen_small = False

    for token in tokens:
        value = _NUMBER_WORDS.get(token)
        if value is None:
            return None
        if value >= 100:
            if seen_hundreds or seen_tens or seen_small:
                return None
            seen_hundreds = True
        elif value >= 20:
            if seen_tens or seen_small:
                return None
            seen_tens = True
        else:
            if seen_small:
                return None
            seen_small = True
        total += value

    return total


def _consume_clock_number(
    tokens: list[_Token],
    cursor: int,
    *,
    max_value: int,
) -> tuple[int, int] | None:
    if cursor >= len(tokens):
        return None

    raw = tokens[cursor].value
    if raw.isdigit():
        value = int(raw)
        return (value, cursor + 1) if value <= max_value else None

    first = _NUMBER_WORDS.get(raw)
    if first is None:
        return None

    value = first
    end_cursor = cursor + 1

    if cursor + 1 < len(tokens):
        second = _NUMBER_WORDS.get(tokens[cursor + 1].value)
        if first in {20, 30, 40, 50} and second is not None and 1 <= second <= 9:
            value = first + second
            end_cursor = cursor + 2
        elif first == 0 and second is not None and 1 <= second <= 9:
            value = second
            end_cursor = cursor + 2

    return (value, end_cursor) if value <= max_value else None


def _convert_hour(hour: int, day_part: str | None) -> int | None:
    if day_part is None:
        return hour if 0 <= hour <= 23 else None
    if not 1 <= hour <= 12:
        return None
    if day_part in {"утра", "ночи"}:
        return 0 if hour == 12 else hour
    return 12 if hour == 12 else hour + 12


def _parse_clock(tokens: list[_Token], cursor: int) -> tuple[int, int, int] | None:
    hour_result = _consume_clock_number(tokens, cursor, max_value=59)
    if hour_result is None:
        return None

    hour, cursor = hour_result
    minute = 0

    if cursor < len(tokens) and _is_number(tokens[cursor].value):
        minute_result = _consume_clock_number(tokens, cursor, max_value=59)
        if minute_result is None:
            return None
        minute, cursor = minute_result

    day_part: str | None = None
    if cursor < len(tokens) and tokens[cursor].value in _DAY_PARTS:
        day_part = tokens[cursor].value
        cursor += 1

    converted_hour = _convert_hour(hour, day_part)
    if converted_hour is None:
        return None

    return converted_hour, minute, cursor


def _looks_like_relative_start(tokens: list[_Token], index: int) -> bool:
    if index + 1 >= len(tokens):
        return False

    next_value = tokens[index + 1].value
    if _is_number(next_value) or next_value in _RELATIVE_UNITS:
        return True

    # "через полторы минуты" должно дать invalid_reminder_time.
    return any(
        token.value in _RELATIVE_UNITS
        for token in tokens[index + 2:min(len(tokens), index + 5)]
    )


def _parse_relative(
    body: str,
    tokens: list[_Token],
    index: int,
    now: datetime,
) -> tuple[_TimeCandidate | None, str | None]:
    cursor = index + 1
    total_seconds = 0
    parsed_parts = 0
    seen_units: set[str] = set()

    while cursor < len(tokens):
        if tokens[cursor].value == "и":
            cursor += 1
            if cursor >= len(tokens):
                break

        number_start = cursor
        number_tokens: list[str] = []

        while cursor < len(tokens) and _is_number(tokens[cursor].value):
            number_tokens.append(tokens[cursor].value)
            cursor += 1

        if cursor >= len(tokens):
            break

        unit_info = _RELATIVE_UNITS.get(tokens[cursor].value)
        if unit_info is None:
            cursor = number_start
            break

        unit_name, multiplier = unit_info
        value = _parse_number(number_tokens)

        if value is None and tokens[cursor].value in _BARE_UNITS:
            value = 1
        if value is None or unit_name in seen_units:
            return None, "invalid_reminder_time"

        seen_units.add(unit_name)
        total_seconds += value * multiplier
        parsed_parts += 1
        cursor += 1

        if cursor >= len(tokens):
            break

        next_value = tokens[cursor].value
        if (
            next_value != "и"
            and not _is_number(next_value)
            and next_value not in _BARE_UNITS
        ):
            break

    if parsed_parts == 0:
        return None, "invalid_reminder_time"
    if total_seconds < MIN_REMINDER_LEAD_SEC:
        return None, "reminder_in_past"

    start = tokens[index].start
    end = tokens[cursor - 1].end
    return (
        _TimeCandidate(
            start=start,
            end=end,
            due_at=now + timedelta(seconds=total_seconds),
            time_kind="relative",
            matched_text=body[start:end],
        ),
        None,
    )


def _parse_day_time(
    body: str,
    tokens: list[_Token],
    index: int,
    now: datetime,
) -> tuple[_TimeCandidate | None, str | None]:
    cursor = index + 1
    if cursor < len(tokens) and tokens[cursor].value == "в":
        cursor += 1

    clock = _parse_clock(tokens, cursor)
    if clock is None:
        return None, "invalid_reminder_time"

    hour, minute, end_cursor = clock
    day_offset, time_kind = _DAY_MARKERS[tokens[index].value]
    target_date = (now + timedelta(days=day_offset)).date()
    due_at = datetime.combine(
        target_date,
        dt_time(hour=hour, minute=minute),
        tzinfo=now.tzinfo,
    )

    start = tokens[index].start
    end = tokens[end_cursor - 1].end
    return (
        _TimeCandidate(
            start=start,
            end=end,
            due_at=due_at,
            time_kind=time_kind,
            matched_text=body[start:end],
        ),
        None,
    )


def _parse_next_clock(
    body: str,
    tokens: list[_Token],
    index: int,
    now: datetime,
) -> _TimeCandidate | None:
    clock = _parse_clock(tokens, index + 1)
    if clock is None:
        return None

    hour, minute, end_cursor = clock
    due_at = datetime.combine(
        now.date(),
        dt_time(hour=hour, minute=minute),
        tzinfo=now.tzinfo,
    )
    if due_at <= now:
        due_at += timedelta(days=1)

    start = tokens[index].start
    end = tokens[end_cursor - 1].end
    return _TimeCandidate(
        start=start,
        end=end,
        due_at=due_at,
        time_kind="next_clock",
        matched_text=body[start:end],
    )


def _overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return not (left[1] <= right[0] or left[0] >= right[1])


def _error(normalized_text: str, error: str) -> ReminderDateTimeParseResult:
    return ReminderDateTimeParseResult(
        due_at=None,
        due_at_epoch=None,
        reminder_text="",
        time_kind=None,
        matched_time_text="",
        error=error,
        normalized_text=normalized_text,
    )


def parse_reminder_datetime(
    text: str,
    *,
    now: datetime | None = None,
    min_lead_seconds: int = MIN_REMINDER_LEAD_SEC,
    max_horizon_seconds: int = MAX_REMINDER_HORIZON_SEC,
) -> ReminderDateTimeParseResult:
    """
    Поддерживает:
      - через 20 минут;
      - через 1 день 2 часа;
      - сегодня в 18:30;
      - завтра в девять утра;
      - в 18:30 — ближайшее такое время.
    """
    normalized = normalize_reminder_text(text)
    body = _strip_reminder_prefix(normalized)
    if not body:
        return _error(normalized, "missing_reminder_time")

    now_value = now if now is not None else datetime.now()
    tokens = _tokenize(body)

    candidates: list[_TimeCandidate] = []
    invalid_errors: list[str] = []
    occupied: list[tuple[int, int]] = []

    for index, token in enumerate(tokens):
        if token.value == "через" and _looks_like_relative_start(tokens, index):
            candidate, error = _parse_relative(body, tokens, index, now_value)
            if candidate is not None:
                candidates.append(candidate)
                occupied.append((candidate.start, candidate.end))
            elif error:
                invalid_errors.append(error)

    for index, token in enumerate(tokens):
        if token.value not in _DAY_MARKERS:
            continue
        candidate, error = _parse_day_time(body, tokens, index, now_value)
        if candidate is not None:
            candidates.append(candidate)
            occupied.append((candidate.start, candidate.end))
        elif error:
            invalid_errors.append(error)

    for index, token in enumerate(tokens):
        if token.value != "в":
            continue
        if index > 0 and tokens[index - 1].value in _DAY_MARKERS:
            continue

        candidate = _parse_next_clock(body, tokens, index, now_value)
        if candidate is None:
            continue

        candidate_range = (candidate.start, candidate.end)
        if any(_overlap(candidate_range, item) for item in occupied):
            continue

        candidates.append(candidate)
        occupied.append(candidate_range)

    candidates = list({
        (candidate.start, candidate.end, candidate.time_kind): candidate
        for candidate in candidates
    }.values())

    if len(candidates) > 1:
        return _error(normalized, "ambiguous_reminder_time")
    if not candidates:
        return _error(
            normalized,
            invalid_errors[0] if invalid_errors else "missing_reminder_time",
        )

    candidate = candidates[0]
    reminder_text = body[:candidate.start] + " " + body[candidate.end:]
    reminder_text = re.sub(r"^[\s:;,.!?-]+|[\s:;,.!?-]+$", "", reminder_text)
    reminder_text = " ".join(reminder_text.split())

    if not reminder_text:
        return ReminderDateTimeParseResult(
            None, None, "", candidate.time_kind, candidate.matched_text,
            "missing_reminder_text", normalized,
        )

    delta_seconds = (candidate.due_at - now_value).total_seconds()
    if delta_seconds < int(min_lead_seconds):
        error = "reminder_in_past"
    elif delta_seconds > int(max_horizon_seconds):
        error = "reminder_too_far"
    else:
        error = None

    if error:
        return ReminderDateTimeParseResult(
            None, None, reminder_text, candidate.time_kind,
            candidate.matched_text, error, normalized,
        )

    return ReminderDateTimeParseResult(
        due_at=candidate.due_at,
        due_at_epoch=candidate.due_at.timestamp(),
        reminder_text=reminder_text,
        time_kind=candidate.time_kind,
        matched_time_text=candidate.matched_text,
        error=None,
        normalized_text=normalized,
    )
