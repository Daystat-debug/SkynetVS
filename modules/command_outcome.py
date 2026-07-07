from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from modules.command_decision import CommandDecision


OUTCOME_NOT_ACCEPTED = "not_accepted"
OUTCOME_MISSING_SLOTS = "missing_required_slots"
OUTCOME_CONFIRMATION_REQUIRED = "confirmation_required"
OUTCOME_DICTATION_ON = "dictation_on"
OUTCOME_DICTATION_OFF = "dictation_off"
OUTCOME_INTERRUPTIBLE_REPLY = "interruptible_reply"
OUTCOME_EXECUTE = "execute"


@dataclass(frozen=True)
class CommandOutcome:
    kind: str
    intent: str


def _intent(meta: Mapping[str, Any]) -> str:
    return str(meta.get("intent") or "").upper().strip()


def classify_command_outcome(
    meta: Mapping[str, Any],
    decision: CommandDecision,
) -> CommandOutcome:
    """
    Классифицирует, что main.py должен делать с понятой командой.

    Здесь нет TTS, execute, logging или state mutations.
    Только выбор ветки исполнения.
    """
    intent = _intent(meta)

    if not decision.accepted:
        return CommandOutcome(
            kind=OUTCOME_NOT_ACCEPTED,
            intent=intent,
        )

    if decision.reason == "missing_required_slots":
        return CommandOutcome(
            kind=OUTCOME_MISSING_SLOTS,
            intent=intent,
        )

    if decision.requires_confirmation:
        return CommandOutcome(
            kind=OUTCOME_CONFIRMATION_REQUIRED,
            intent=intent,
        )

    if intent == "DICTATION_MODE_ON":
        return CommandOutcome(
            kind=OUTCOME_DICTATION_ON,
            intent=intent,
        )

    if intent == "DICTATION_MODE_OFF":
        return CommandOutcome(
            kind=OUTCOME_DICTATION_OFF,
            intent=intent,
        )

    if intent == "WEATHER":
        return CommandOutcome(
            kind=OUTCOME_INTERRUPTIBLE_REPLY,
            intent=intent,
        )

    return CommandOutcome(
        kind=OUTCOME_EXECUTE,
        intent=intent,
    )