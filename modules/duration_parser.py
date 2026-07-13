from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


DEFAULT_MIN_DURATION_SEC = 1
DEFAULT_MAX_DURATION_SEC = 24 * 60 * 60


@dataclass(frozen=True)
class DurationPart:
    unit: str
    value: int
    seconds: int


@dataclass(frozen=True)
class DurationParseResult:
    seconds: int | None
    parts: tuple[DurationPart, ...]
    error: str | None
    normalized_text: str

    @property
    def ok(self) -> bool:
        return self.seconds is not None and self.error is None


_NUMBER_WORDS = {
    "ноль": 0,

    "один": 1,
    "одна": 1,
    "одно": 1,
    "одну": 1,

    "два": 2,
    "две": 2,

    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,

    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,

    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,

    "сто": 100,
    "двести": 200,
    "триста": 300,
    "четыреста": 400,
    "пятьсот": 500,
    "шестьсот": 600,
    "семьсот": 700,
    "восемьсот": 800,
    "девятьсот": 900,
}


_UNIT_INFO = {
    # seconds
    "секунда": ("seconds", 1),
    "секунду": ("seconds", 1),
    "секунды": ("seconds", 1),
    "секунд": ("seconds", 1),
    "сек": ("seconds", 1),

    # minutes
    "минута": ("minutes", 60),
    "минуту": ("minutes", 60),
    "минуты": ("minutes", 60),
    "минут": ("minutes", 60),
    "мин": ("minutes", 60),

    # hours
    "час": ("hours", 3600),
    "часа": ("hours", 3600),
    "часов": ("hours", 3600),
}


_BARE_SINGULAR_UNITS = {
    "секунда",
    "секунду",
    "минута",
    "минуту",
    "час",
}


def normalize_duration_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def _tokenize(text: str) -> list[str]:
    return re.findall(
        r"\d+|[a-zа-яё]+",
        normalize_duration_text(text),
        flags=re.IGNORECASE,
    )


def _is_number_token(token: str) -> bool:
    return token.isdigit() or token in _NUMBER_WORDS


def _parse_number_tokens(tokens: Iterable[str]) -> int | None:
    values = list(tokens)

    if not values:
        return None

    if len(values) == 1 and values[0].isdigit():
        return int(values[0])

    # Не смешиваем цифры и словесные числа в одном значении.
    if any(token.isdigit() for token in values):
        return None

    total = 0
    seen_hundreds = False
    seen_tens = False
    seen_small = False

    for token in values:
        value = _NUMBER_WORDS.get(token)

        if value is None:
            return None

        if value >= 100:
            if seen_hundreds or seen_tens or seen_small:
                return None

            seen_hundreds = True
            total += value
            continue

        if value >= 20:
            if seen_tens or seen_small:
                return None

            seen_tens = True
            total += value
            continue

        # 0..19 — последняя часть числа.
        if seen_small:
            return None

        seen_small = True
        total += value

    return total


def parse_duration(
    text: str,
    *,
    min_seconds: int = DEFAULT_MIN_DURATION_SEC,
    max_seconds: int = DEFAULT_MAX_DURATION_SEC,
) -> DurationParseResult:
    normalized = normalize_duration_text(text)
    tokens = _tokenize(normalized)

    parts: list[DurationPart] = []
    saw_unit = False

    for index, token in enumerate(tokens):
        unit_info = _UNIT_INFO.get(token)

        if unit_info is None:
            continue

        saw_unit = True
        unit, multiplier = unit_info

        number_tokens: list[str] = []
        cursor = index - 1

        while cursor >= 0 and _is_number_token(tokens[cursor]):
            number_tokens.insert(0, tokens[cursor])
            cursor -= 1

        value = _parse_number_tokens(number_tokens)

        # "на минуту", "через секунду", "таймер на час".
        if value is None and token in _BARE_SINGULAR_UNITS:
            value = 1

        if value is None:
            continue

        parts.append(
            DurationPart(
                unit=unit,
                value=value,
                seconds=value * multiplier,
            )
        )

    if not parts:
        return DurationParseResult(
            seconds=None,
            parts=(),
            error=(
                "invalid_duration"
                if saw_unit
                else "missing_duration"
            ),
            normalized_text=normalized,
        )

    total_seconds = sum(part.seconds for part in parts)

    if total_seconds < int(min_seconds):
        return DurationParseResult(
            seconds=None,
            parts=tuple(parts),
            error="duration_too_short",
            normalized_text=normalized,
        )

    if total_seconds > int(max_seconds):
        return DurationParseResult(
            seconds=None,
            parts=tuple(parts),
            error="duration_too_long",
            normalized_text=normalized,
        )

    return DurationParseResult(
        seconds=total_seconds,
        parts=tuple(parts),
        error=None,
        normalized_text=normalized,
    )


def parse_duration_seconds(
    text: str,
    *,
    min_seconds: int = DEFAULT_MIN_DURATION_SEC,
    max_seconds: int = DEFAULT_MAX_DURATION_SEC,
) -> int | None:
    return parse_duration(
        text,
        min_seconds=min_seconds,
        max_seconds=max_seconds,
    ).seconds


def _plural_ru(
    value: int,
    forms: tuple[str, str, str],
) -> str:
    value_abs = abs(int(value))
    last_two = value_abs % 100
    last = value_abs % 10

    if 11 <= last_two <= 14:
        return forms[2]

    if last == 1:
        return forms[0]

    if 2 <= last <= 4:
        return forms[1]

    return forms[2]


def format_duration_ru(
    total_seconds: int,
    *,
    max_parts: int = 3,
) -> str:
    seconds = max(0, int(total_seconds))

    hours, remainder = divmod(seconds, 3600)
    minutes, seconds_left = divmod(remainder, 60)

    rows: list[tuple[int, tuple[str, str, str]]] = [
        (hours, ("час", "часа", "часов")),
        (minutes, ("минута", "минуты", "минут")),
        (
            seconds_left,
            ("секунда", "секунды", "секунд"),
        ),
    ]

    rendered = [
        f"{value} {_plural_ru(value, forms)}"
        for value, forms in rows
        if value > 0
    ]

    if not rendered:
        return "0 секунд"

    limit = max(1, int(max_parts))
    return " ".join(rendered[:limit])