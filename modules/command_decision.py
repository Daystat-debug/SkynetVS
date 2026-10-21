from __future__ import annotations

import re
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
    "EXIT_SKYNETVS",
    "RESTART_SKYNETVS",
}

# These rules do not map utterances to intents. They prevent an NLU guess from
# turning a request about music, another application or the PC into the
# assistant's own lifecycle action.
_LIFECYCLE_INTENTS = frozenset({"EXIT_SKYNETVS", "RESTART_SKYNETVS"})
_LIFECYCLE_TARGET = re.compile(
    r"\b(?:скайнет\w*|skynet|ассистент\w*|помощник\w*|себя|"
    r"сво[юейй]\s+(?:работу|программу|процесс)|"
    r"самого\s+себя|выключись|отключись|перезапустись|"
    r"перезагрузись|закройся|запустись)\b", re.IGNORECASE)
_LIFECYCLE_NOT_SELF = re.compile(
    r"\b(?:компьютер\w*|windows|виндовс|систему|пк|"
    r"музык\w*|трек\w*|песн\w*|плеер\w*|"
    r"браузер\w*|блокнот\w*|дискорд\w*|калькулятор\w*)\b", re.IGNORECASE)


def _lifecycle_scope_allowed(meta: Mapping[str, Any]) -> bool:
    text = str(meta.get("_text") or "").lower().strip()
    return bool(_LIFECYCLE_TARGET.search(text) and not _LIFECYCLE_NOT_SELF.search(text))



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

    # Two protected actions must be both confidently classified and explicitly
    # about SkynetVS itself. Deny OS/media/other-app requests regardless of NLU.
    if accepted and _intent(meta) in _LIFECYCLE_INTENTS:
        if _confidence(meta) < max(float(accept_conf), 0.48) or not _lifecycle_scope_allowed(meta):
            accepted = False

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