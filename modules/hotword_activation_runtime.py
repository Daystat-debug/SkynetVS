from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


SayFunc = Callable[[Any, Any, str], float]
TextPredicate = Callable[[str], bool]
TextTransform = Callable[[str], str]
OpenCommandWindowFunc = Callable[[], None]


@dataclass(frozen=True)
class HotwordActivationResult:
    handled: bool
    phrase: str
    reason: str
    last_tts_end: float | None = None
    ack_ignore_until: float | None = None
    meta: dict[str, Any] | None = None


def handle_hotword_activation_phrase(
    phrase: str,
    *,
    mode_manager: Any,
    stt: Any,
    tts: Any,
    now: float,
    ack_text: str,
    ack_ignore_sec: float,
    say_func: SayFunc,
    has_hotword_func: TextPredicate,
    strip_hotword_func: TextTransform,
    handle_command_text_func: Callable[..., dict[str, Any]],
    open_cmd_window_func: OpenCommandWindowFunc,
) -> HotwordActivationResult:
    """
    Обрабатывает hotword-активацию вне режима диктовки/confirmation.

    Сценарии:
      1. Окно команд уже открыто, пользователь сказал "скайнет <команда>"
         -> срезаем hotword и отдаём фразу дальше.

      2. Окно команд закрыто, пользователь сказал "скайнет <команда>"
         -> выполняем команду сразу.

      3. Окно команд закрыто, пользователь сказал только "скайнет"
         -> говорим ACK и открываем окно команд.
    """
    command_window_open = bool(mode_manager.is_command_window_open())

    if command_window_open and has_hotword_func(phrase):
        stripped = strip_hotword_func(phrase) or phrase

        return HotwordActivationResult(
            handled=False,
            phrase=stripped,
            reason="hotword_stripped_in_command_window",
        )

    if (not command_window_open) and has_hotword_func(phrase):
        rest = strip_hotword_func(phrase)

        if rest:
            meta = handle_command_text_func(
                rest,
                immediate_label="immediate",
            )

            return HotwordActivationResult(
                handled=True,
                phrase=phrase,
                reason="immediate_hotword_command",
                meta=meta,
            )

        last_tts_end = say_func(
            stt,
            tts,
            ack_text,
            mute_stt=False,
        )

        ack_ignore_until = now + max(0.2, ack_ignore_sec)

        open_cmd_window_func()

        return HotwordActivationResult(
            handled=True,
            phrase=phrase,
            reason="command_window_opened",
            last_tts_end=last_tts_end,
            ack_ignore_until=ack_ignore_until,
        )

    return HotwordActivationResult(
        handled=False,
        phrase=phrase,
        reason="no_hotword_activation",
    )