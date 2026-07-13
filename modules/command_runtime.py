from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from modules.command_decision import CommandDecision
from modules.command_learning import (
    log_command_action_failure,
    log_not_accepted_command,
)
from modules.command_outcome import (
    CommandOutcome,
    OUTCOME_CONFIRMATION_REQUIRED,
    OUTCOME_DICTATION_OFF,
    OUTCOME_DICTATION_ON,
    OUTCOME_INTERRUPTIBLE_REPLY,
    OUTCOME_MISSING_SLOTS,
    OUTCOME_NOT_ACCEPTED,
)
from modules.confirmation import build_confirmation_prompt


SayFunc = Callable[[Any, Any, str], float]
SayInterruptibleFunc = Callable[[Any, str], float]
ReplyTextFunc = Callable[[Mapping[str, Any]], str]
ModeNameFunc = Callable[[], str]
CancelTimerFunc = Callable[[], None]


PRE_SPEECH_EXECUTE_INTENTS = {
    "SET_TIMER",
    "CANCEL_TIMER",
}


class LoggerLike(Protocol):
    def event(self, kind: str, payload: dict[str, Any]) -> None:
        ...

    def inbox(self, text: str, meta: Mapping[str, Any]) -> None:
        ...


@dataclass(frozen=True)
class CommandRuntimeResult:
    meta: dict[str, Any]
    reason: str
    last_tts_end: float | None = None


def handle_command_runtime(
    *,
    raw_text: str,
    final_text: str,
    meta: Mapping[str, Any],
    decision: CommandDecision,
    outcome: CommandOutcome,
    learning_memory: Any,
    logger: LoggerLike,
    router: Any,
    mode_manager: Any,
    stt: Any,
    tts: Any,
    say_func: SayFunc,
    say_interruptible_func: SayInterruptibleFunc,
    reply_text_func: ReplyTextFunc,
    current_mode_name_func: ModeNameFunc,
    cancel_cmd_timer_func: CancelTimerFunc,
) -> CommandRuntimeResult:
    """
    Выполняет runtime-ветку после understanding + decision + outcome.

    Не занимается:
      - NLU;
      - entity resolving;
      - router preprocess;
      - universal command observation logging.
    """
    meta_dict = dict(meta)

    intent = str(
        meta_dict.get("intent") or ""
    ).upper().strip()

    if outcome.kind == OUTCOME_NOT_ACCEPTED:
        log_not_accepted_command(
            learning_memory=learning_memory,
            raw_text=raw_text,
            final_text=final_text,
            meta=meta_dict,
            mode=current_mode_name_func(),
            reason=decision.reason or "not_accepted",
        )

        text_out = reply_text_func(meta_dict)
        logger.inbox(final_text, meta_dict)
        last_tts_end = say_func(stt, tts, text_out)

        return CommandRuntimeResult(
            meta=meta_dict,
            reason="not_accepted",
            last_tts_end=last_tts_end,
        )

    if outcome.kind == OUTCOME_MISSING_SLOTS:
        logger.event(
            "missing_required_slots_blocked",
            {
                "text": final_text,
                "intent": meta_dict.get("intent"),
                "missing_slots": decision.missing_slots,
                "slots": meta_dict.get("slots") or {},
            },
        )

        text_out = router.reply(meta_dict) or "Не хватает данных для выполнения команды."
        last_tts_end = say_func(stt, tts, text_out)

        return CommandRuntimeResult(
            meta=meta_dict,
            reason="missing_required_slots",
            last_tts_end=last_tts_end,
        )

    if outcome.kind == OUTCOME_CONFIRMATION_REQUIRED:
        mode_manager.set_pending_confirmation(
            {
                "meta": meta_dict,
            }
        )

        prompt = build_confirmation_prompt(meta_dict)
        last_tts_end = say_func(stt, tts, prompt)

        return CommandRuntimeResult(
            meta=meta_dict,
            reason="confirmation_required",
            last_tts_end=last_tts_end,
        )

    if outcome.kind == OUTCOME_DICTATION_ON:
        mode_manager.enter_dictation_mode()
        mode_manager.close_command_window()
        cancel_cmd_timer_func()

        text_out = reply_text_func(meta_dict)
        last_tts_end = say_func(stt, tts, text_out)

        return CommandRuntimeResult(
            meta=meta_dict,
            reason="dictation_on",
            last_tts_end=last_tts_end,
        )

    if outcome.kind == OUTCOME_DICTATION_OFF:
        mode_manager.exit_dictation_mode()

        text_out = reply_text_func(meta_dict)
        last_tts_end = say_func(stt, tts, text_out)

        return CommandRuntimeResult(
            meta=meta_dict,
            reason="dictation_off",
            last_tts_end=last_tts_end,
        )

    text_out = reply_text_func(meta_dict)

    if outcome.kind == OUTCOME_INTERRUPTIBLE_REPLY:
        last_tts_end = say_interruptible_func(tts, text_out)

        return CommandRuntimeResult(
            meta=meta_dict,
            reason="interruptible_reply",
            last_tts_end=last_tts_end,
        )

    if intent in PRE_SPEECH_EXECUTE_INTENTS:
        try:
            router.execute(meta_dict)
        except Exception as e:
            log_command_action_failure(
                learning_memory=learning_memory,
                raw_text=raw_text,
                final_text=final_text,
                meta=meta_dict,
                mode=current_mode_name_func(),
                error=e,
            )
            raise

        last_tts_end = say_func(
            stt,
            tts,
            text_out,
        )

        return CommandRuntimeResult(
            meta=meta_dict,
            reason="executed",
            last_tts_end=last_tts_end,
        )

    last_tts_end = say_func(
        stt,
        tts,
        text_out,
    )

    try:
        router.execute(meta_dict)
    except Exception as e:
        log_command_action_failure(
            learning_memory=learning_memory,
            raw_text=raw_text,
            final_text=final_text,
            meta=meta_dict,
            mode=current_mode_name_func(),
            error=e,
        )
        raise

    return CommandRuntimeResult(
        meta=meta_dict,
        reason="executed",
        last_tts_end=last_tts_end,
    )