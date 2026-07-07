from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from modules.command_decision import build_command_decision
from modules.command_learning import log_command_action_failure


SayFunc = Callable[[Any, Any, str], float]
PickNamedResponseFunc = Callable[..., str | None]
TextPredicate = Callable[[str], bool]
ModeNameFunc = Callable[[], str]
ExtendCommandWindowFunc = Callable[[], None]


@dataclass(frozen=True)
class ConfirmationRuntimeResult:
    handled: bool
    reason: str
    last_tts_end: float | None = None


def _meta_text(meta: dict[str, Any]) -> str:
    return str(meta.get("_text") or "")


def handle_pending_confirmation_phrase(
    phrase: str,
    *,
    mode_manager: Any,
    router: Any,
    learning_memory: Any,
    stt: Any,
    tts: Any,
    say_func: SayFunc,
    pick_named_response_func: PickNamedResponseFunc,
    is_confirmation_yes_func: TextPredicate,
    is_confirmation_no_func: TextPredicate,
    accept_conf: float,
    current_mode_name_func: ModeNameFunc,
    extend_cmd_window_func: ExtendCommandWindowFunc,
) -> ConfirmationRuntimeResult:
    """
    Обрабатывает фразу, если ассистент ждёт подтверждение опасного действия.

    Сценарии:
      - да  -> подтверждаем и выполняем pending meta;
      - нет -> отменяем;
      - другое -> просим сказать да или нет.
    """
    if not mode_manager.has_pending_confirmation():
        return ConfirmationRuntimeResult(
            handled=False,
            reason="no_pending_confirmation",
        )

    pending_confirmation = mode_manager.get_pending_confirmation() or {}

    if is_confirmation_yes_func(phrase):
        meta = dict(pending_confirmation.get("meta") or {})
        mode_manager.clear_pending_confirmation()

        confirm_ok = pick_named_response_func("CONFIRM_OK")
        last_tts_end = say_func(
            stt,
            tts,
            confirm_ok or "Подтверждаю. Выполняю.",
        )

        confirm_decision = build_command_decision(
            meta,
            accept_conf=accept_conf,
        )

        if confirm_decision.accepted and not confirm_decision.missing_slots:
            try:
                router.execute(meta)
            except Exception as e:
                log_command_action_failure(
                    learning_memory=learning_memory,
                    raw_text=_meta_text(meta),
                    final_text=_meta_text(meta),
                    meta=meta,
                    mode=current_mode_name_func(),
                    error=e,
                )
                raise

            reason = "confirmed_executed"
        else:
            reason = "confirmed_not_runnable"

        if mode_manager.is_command_window_open():
            extend_cmd_window_func()

        return ConfirmationRuntimeResult(
            handled=True,
            reason=reason,
            last_tts_end=last_tts_end,
        )

    if is_confirmation_no_func(phrase):
        mode_manager.clear_pending_confirmation()

        confirm_cancel = pick_named_response_func("CONFIRM_CANCEL")
        last_tts_end = say_func(
            stt,
            tts,
            confirm_cancel or "Отменено.",
        )

        if mode_manager.is_command_window_open():
            extend_cmd_window_func()

        return ConfirmationRuntimeResult(
            handled=True,
            reason="confirmation_cancelled",
            last_tts_end=last_tts_end,
        )

    confirm_repeat = pick_named_response_func("CONFIRM_REPEAT")
    last_tts_end = say_func(
        stt,
        tts,
        confirm_repeat or "Скажи да или нет.",
    )

    if mode_manager.is_command_window_open():
        extend_cmd_window_func()

    return ConfirmationRuntimeResult(
        handled=True,
        reason="confirmation_repeat",
        last_tts_end=last_tts_end,
    )