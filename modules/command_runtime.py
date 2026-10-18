from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from modules.action_error import ActionExecutionError, DEFAULT_ACTION_FAILURE_MESSAGE
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
    "OPEN_DEVELOPER_TASK",
    "SET_TIMER",
    "CANCEL_TIMER",
    "CREATE_REMINDER",
    "CANCEL_REMINDER",
}


HWA02B1_TIMER_INTENTS = frozenset({
    "SET_TIMER",
    "CANCEL_TIMER",
})

HWA02B2_VOLUME_INTENTS = frozenset({
    "VOLUME_UP",
    "VOLUME_DOWN",
})


class LoggerLike(Protocol):
    def event(self, kind: str, payload: dict[str, Any]) -> None:
        ...

    def inbox(self, text: str, meta: Mapping[str, Any]) -> None:
        ...


class TimerActionPortLike(Protocol):
    def prepare(self, *, intent: str, slots: dict[str, Any]) -> Any:
        ...

    def execute(self, request: Any) -> None:
        ...


class VolumeActionPortLike(Protocol):
    def prepare(self, *, intent: str, slots: dict[str, Any]) -> Any:
        ...

    def execute(self, plan: Any) -> None:
        ...


@dataclass(frozen=True)
class CommandRuntimeResult:
    meta: dict[str, Any]
    reason: str
    last_tts_end: float | None = None


def _error_text(error: BaseException) -> str:
    return str(error).strip() or type(error).__name__


def _safe_logger_event(logger: LoggerLike, kind: str, payload: dict[str, Any]) -> None:
    try:
        logger.event(kind, payload)
    except Exception:
        pass


def _action_failure_payload(
    *,
    intent: str,
    raw_text: str,
    final_text: str,
    error: BaseException,
    success_reply_spoken: bool,
) -> dict[str, Any]:
    if isinstance(error, ActionExecutionError):
        payload = error.to_payload()
    else:
        payload = {
            "intent": intent,
            "operation": "execute",
            "error_code": "unexpected_action_error",
            "error_type": type(error).__name__,
            "error": _error_text(error),
            "user_message": DEFAULT_ACTION_FAILURE_MESSAGE,
            "context": {},
        }

    payload["intent"] = str(payload.get("intent") or intent).upper().strip()
    payload["raw_text"] = raw_text
    payload["final_text"] = final_text
    payload["success_reply_spoken"] = bool(success_reply_spoken)

    return payload


def _handle_action_failure(
    *,
    raw_text: str,
    final_text: str,
    meta: dict[str, Any],
    intent: str,
    error: BaseException,
    learning_memory: Any,
    logger: LoggerLike,
    stt: Any,
    tts: Any,
    say_func: SayFunc,
    current_mode_name_func: ModeNameFunc,
    previous_last_tts_end: float | None,
    success_reply_spoken: bool,
) -> CommandRuntimeResult:
    try:
        mode = current_mode_name_func()
    except Exception:
        mode = "unknown"

    try:
        log_command_action_failure(
            learning_memory=learning_memory,
            raw_text=raw_text,
            final_text=final_text,
            meta=meta,
            mode=mode,
            error=error,
        )
    except Exception as logging_error:
        _safe_logger_event(
            logger,
            "command_action_failure_logging_failed",
            {
                "intent": intent,
                "error_type": type(logging_error).__name__,
                "error": _error_text(logging_error),
            },
        )

    payload = _action_failure_payload(
        intent=intent,
        raw_text=raw_text,
        final_text=final_text,
        error=error,
        success_reply_spoken=success_reply_spoken,
    )
    _safe_logger_event(logger, "command_action_failed", payload)

    last_tts_end = previous_last_tts_end
    failure_text = str(payload.get("user_message") or DEFAULT_ACTION_FAILURE_MESSAGE).strip()

    try:
        last_tts_end = say_func(stt, tts, failure_text)
    except Exception as speech_error:
        _safe_logger_event(
            logger,
            "command_action_failure_reply_failed",
            {
                "intent": intent,
                "action_error_code": payload.get("error_code"),
                "error_type": type(speech_error).__name__,
                "error": _error_text(speech_error),
            },
        )

    return CommandRuntimeResult(
        meta=meta,
        reason="action_failed",
        last_tts_end=last_tts_end,
    )


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
    timer_actions: TimerActionPortLike | None = None,
    volume_actions: VolumeActionPortLike | None = None,
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

    timer_request: Any | None = None
    timer_migrated = timer_actions is not None and intent in HWA02B1_TIMER_INTENTS
    volume_plan: Any | None = None
    volume_migrated = volume_actions is not None and intent in HWA02B2_VOLUME_INTENTS

    if timer_migrated:
        try:
            slots = meta_dict.get("slots")
            timer_request = timer_actions.prepare(
                intent=intent,
                slots=slots,
            )
        except Exception as e:
            return _handle_action_failure(
                raw_text=raw_text,
                final_text=final_text,
                meta=meta_dict,
                intent=intent,
                error=e,
                learning_memory=learning_memory,
                logger=logger,
                stt=stt,
                tts=tts,
                say_func=say_func,
                current_mode_name_func=current_mode_name_func,
                previous_last_tts_end=None,
                success_reply_spoken=False,
            )

    if volume_migrated:
        try:
            slots = meta_dict.get("slots")
            volume_plan = volume_actions.prepare(
                intent=intent,
                slots=slots,
            )
        except Exception as e:
            return _handle_action_failure(
                raw_text=raw_text,
                final_text=final_text,
                meta=meta_dict,
                intent=intent,
                error=e,
                learning_memory=learning_memory,
                logger=logger,
                stt=stt,
                tts=tts,
                say_func=say_func,
                current_mode_name_func=current_mode_name_func,
                previous_last_tts_end=None,
                success_reply_spoken=False,
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
            if timer_migrated:
                timer_actions.execute(timer_request)
            else:
                router.execute(meta_dict)
        except Exception as e:
            return _handle_action_failure(
                raw_text=raw_text,
                final_text=final_text,
                meta=meta_dict,
                intent=intent,
                error=e,
                learning_memory=learning_memory,
                logger=logger,
                stt=stt,
                tts=tts,
                say_func=say_func,
                current_mode_name_func=current_mode_name_func,
                previous_last_tts_end=None,
                success_reply_spoken=False,
            )

        last_tts_end = say_func(stt, tts, text_out)

        return CommandRuntimeResult(
            meta=meta_dict,
            reason="executed",
            last_tts_end=last_tts_end,
        )

    last_tts_end = say_func(stt, tts, text_out)

    try:
        if volume_migrated:
            volume_actions.execute(volume_plan)
        else:
            router.execute(meta_dict)
    except Exception as e:
        return _handle_action_failure(
            raw_text=raw_text,
            final_text=final_text,
            meta=meta_dict,
            intent=intent,
            error=e,
            learning_memory=learning_memory,
            logger=logger,
            stt=stt,
            tts=tts,
            say_func=say_func,
            current_mode_name_func=current_mode_name_func,
            previous_last_tts_end=last_tts_end,
            success_reply_spoken=True,
        )

    return CommandRuntimeResult(
        meta=meta_dict,
        reason="executed",
        last_tts_end=last_tts_end,
    )