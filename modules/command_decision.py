from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence


DEFAULT_REQUIRED_SLOTS: Dict[str, Sequence[str]] = {
    "OPEN_APP": ("app",),
    "CLOSE_APP": ("app",),
    "OPEN_URL": ("url",),
    "OPEN_FOLDER": ("folder",),
    "OPEN_SETTINGS": ("section",),
    "SEARCH_WEB": ("query",),
    "SEARCH_YOUTUBE": ("query",),
    "SET_VOLUME": ("volume",),
    "SET_TIMER": ("duration_seconds",),
    "CREATE_REMINDER": (
        "due_at_epoch",
        "reminder_text",
    ),
    "CANCEL_REMINDER": ("cancel_mode",),
}


DEFAULT_CONFIRM_REQUIRED_INTENTS = {
    "EMPTY_RECYCLE_BIN",
}


@dataclass(frozen=True)
class CommandDecision:
    accepted: bool
    runnable: bool
    requires_confirmation: bool
    missing_slots: List[str]
    reason: str | None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _intent(meta: Mapping[str, Any]) -> str:
    return str(meta.get("intent") or "").upper().strip()


def _confidence(meta: Mapping[str, Any]) -> float:
    try:
        return float(meta.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def is_accepted(meta: Mapping[str, Any], *, accept_conf: float) -> bool:
    intent = _intent(meta)
    confidence = _confidence(meta)

    return bool(intent) and confidence >= accept_conf


def missing_required_slots(
    meta: Mapping[str, Any],
    *,
    required_slots: Mapping[str, Sequence[str]] | None = None,
) -> List[str]:
    intent = _intent(meta)
    slots = dict(meta.get("slots") or {})
    required = required_slots or DEFAULT_REQUIRED_SLOTS

    missing: List[str] = []

    for slot_name in required.get(intent, ()):
        value = slots.get(slot_name)

        if value is None:
            missing.append(slot_name)
            continue

        if isinstance(value, str) and not value.strip():
            missing.append(slot_name)
            continue

    return missing


def requires_confirmation(
    meta: Mapping[str, Any],
    *,
    confirm_required_intents: Iterable[str] | None = None,
) -> bool:
    intent = _intent(meta)

    confirm_required = {
        str(x).upper().strip()
        for x in (confirm_required_intents or DEFAULT_CONFIRM_REQUIRED_INTENTS)
        if str(x).strip()
    }

    return intent in confirm_required


def build_command_decision(
    meta: Mapping[str, Any],
    *,
    accept_conf: float,
    required_slots: Mapping[str, Sequence[str]] | None = None,
    confirm_required_intents: Iterable[str] | None = None,
) -> CommandDecision:
    accepted = is_accepted(meta, accept_conf=accept_conf)

    if not accepted:
        return CommandDecision(
            accepted=False,
            runnable=False,
            requires_confirmation=False,
            missing_slots=[],
            reason="not_accepted",
        )

    missing_slots = missing_required_slots(meta, required_slots=required_slots)

    if missing_slots:
        return CommandDecision(
            accepted=True,
            runnable=False,
            requires_confirmation=False,
            missing_slots=missing_slots,
            reason="missing_required_slots",
        )

    confirmation_required = requires_confirmation(
        meta,
        confirm_required_intents=confirm_required_intents,
    )

    if confirmation_required:
        return CommandDecision(
            accepted=True,
            runnable=False,
            requires_confirmation=True,
            missing_slots=[],
            reason="requires_confirmation",
        )

    return CommandDecision(
        accepted=True,
        runnable=True,
        requires_confirmation=False,
        missing_slots=[],
        reason=None,
    )