from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


TextPredicate = Callable[[str], bool]
TextTransform = Callable[[str], str]
MergePhrasesFunc = Callable[[str, str], str]
LooksIncompleteFunc = Callable[[str], bool]
HandleCommandTextFunc = Callable[..., dict[str, Any]]
ExtendCommandWindowFunc = Callable[[], None]
CloseCommandWindowFunc = Callable[..., None]


@dataclass(frozen=True)
class CommandWindowRuntimeResult:
    handled: bool
    reason: str
    meta: dict[str, Any] | None = None


def handle_command_window_phrase(
    phrase: str,
    *,
    mode_manager: Any,
    logger: Any,
    now: float,
    pending_command_wait_sec: float,
    is_only_hotword_func: TextPredicate,
    norm_func: TextTransform,
    merge_phrases_func: MergePhrasesFunc,
    looks_incomplete_command_func: LooksIncompleteFunc,
    handle_command_text_func: HandleCommandTextFunc,
    extend_cmd_window_func: ExtendCommandWindowFunc,
    close_cmd_window_func: CloseCommandWindowFunc,
) -> CommandWindowRuntimeResult:
    """
    Обрабатывает фразу внутри открытого command-window.

    Сценарии:
      - bare hotword -> игнорируем, окно продлеваем;
      - pending fragment + новая фраза -> склеиваем;
      - incomplete command -> сохраняем pending fragment;
      - обычная команда -> handle_command_text(...);
      - STOP_LISTEN -> закрываем command window.
    """
    if not mode_manager.is_command_window_open():
        return CommandWindowRuntimeResult(
            handled=False,
            reason="command_window_not_open",
        )

    if is_only_hotword_func(phrase):
        logger.event("cmd_ignore_bare_hotword", {"text": phrase})
        extend_cmd_window_func()

        return CommandWindowRuntimeResult(
            handled=True,
            reason="bare_hotword_ignored",
        )

    cmd_candidate = norm_func(phrase)

    # Если уже ждём хвост короткой команды и пришла новая фраза —
    # ВСЕГДА сначала пробуем склеить, даже если wait_sec уже почти истёк.
    if mode_manager.has_pending_command() and cmd_candidate:
        cmd_candidate = merge_phrases_func(
            mode_manager.get_pending_command_text(),
            cmd_candidate,
        )
        mode_manager.clear_pending_command()

    elif mode_manager.has_pending_command() and (
        now - mode_manager.get_pending_command_ts()
    ) > pending_command_wait_sec:
        pending_text = mode_manager.get_pending_command_text()

        if is_only_hotword_func(pending_text):
            mode_manager.clear_pending_command()
            extend_cmd_window_func()

            return CommandWindowRuntimeResult(
                handled=True,
                reason="pending_bare_hotword_ignored",
            )

        cmd_candidate = pending_text
        mode_manager.clear_pending_command()

    if looks_incomplete_command_func(cmd_candidate):
        mode_manager.set_pending_command(cmd_candidate, now)
        extend_cmd_window_func()
        logger.event("cmd_pending_fragment", {"text": cmd_candidate})

        return CommandWindowRuntimeResult(
            handled=True,
            reason="pending_fragment_set",
        )

    cmd = norm_func(cmd_candidate)

    meta = handle_command_text_func(
        cmd,
        immediate_label="window",
    )

    if (meta.get("intent") or "").upper() == "STOP_LISTEN":
        close_cmd_window_func(
            "cmd_window_close_stop_intent",
            speak_close=False,
        )

        return CommandWindowRuntimeResult(
            handled=True,
            reason="stop_listen_closed_window",
            meta=meta,
        )

    extend_cmd_window_func()

    return CommandWindowRuntimeResult(
        handled=True,
        reason="command_executed_window_extended",
        meta=meta,
    )