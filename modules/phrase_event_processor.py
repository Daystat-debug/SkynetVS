from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from modules.command_window_runtime import handle_command_window_phrase
from modules.confirmation_runtime import handle_pending_confirmation_phrase
from modules.dictation_runtime import handle_dictation_phrase
from modules.hotword_activation_runtime import handle_hotword_activation_phrase
from modules.phrase_guards import check_phrase_preprocessing_guards
from modules.speech_interrupt import handle_phrase_while_tts_speaking


TextPredicate = Callable[[str], bool]
TextTransform = Callable[[str], str]
SayFunc = Callable[..., float]
HandleCommandTextFunc = Callable[..., dict[str, Any]]
VoidFunc = Callable[[], None]
CloseCommandWindowFunc = Callable[..., None]


@dataclass(frozen=True)
class PhraseEventProcessorResult:
    handled: bool
    reason: str
    last_tts_end: float | None = None
    ack_ignore_until: float | None = None


class PhraseEventProcessor:
    """
    Обрабатывает одну STT-фразу.

    Делает:
      - interruption while TTS is speaking;
      - phrase preprocessing guards;
      - pending confirmation;
      - dictation mode phrase handling;
      - hotword activation;
      - command window phrase handling.

    Не делает:
      - event loop;
      - cmd timeout;
      - STT producer;
      - создание зависимостей.
    """

    def __init__(
        self,
        *,
        tts: Any,
        stt: Any,
        logger: Any,
        settings: Any,
        mode_manager: Any,
        learning_memory: Any,
        typing_service: Any,
        say_func: SayFunc,
        has_hotword_func: TextPredicate,
        strip_hotword_func: TextTransform,
        is_only_hotword_func: TextPredicate,
        norm_func: TextTransform,
        is_dictation_stop_phrase_func: TextPredicate,
        predict_func: Callable[[str], dict[str, Any]],
        is_accepted_func: Callable[[dict[str, Any]], bool],
        pick_named_response_func: Callable[..., str | None],
        is_confirmation_yes_func: TextPredicate,
        is_confirmation_no_func: TextPredicate,
        current_mode_name_func: Callable[[], str],
        handle_command_text_func: HandleCommandTextFunc,
        open_cmd_window_func: VoidFunc,
        extend_cmd_window_func: VoidFunc,
        close_cmd_window_func: CloseCommandWindowFunc,
        merge_phrases_func: Callable[[str, str], str],
        looks_incomplete_command_func: TextPredicate,
        pending_command_wait_sec: float,
        normalize_func: Callable[..., Any],
        should_ignore_during_ack_window_func: TextPredicate,
        router: Any,
        print_func: Callable[[str], None] | None = print,
        time_func: Callable[[], float] = time.time,
        speech_interrupt_func: Callable[..., Any] = handle_phrase_while_tts_speaking,
        phrase_guard_func: Callable[..., Any] = check_phrase_preprocessing_guards,
        pending_confirmation_func: Callable[..., Any] = handle_pending_confirmation_phrase,
        dictation_phrase_func: Callable[..., Any] = handle_dictation_phrase,
        hotword_activation_func: Callable[..., Any] = handle_hotword_activation_phrase,
        command_window_func: Callable[..., Any] = handle_command_window_phrase,
    ) -> None:
        self._tts = tts
        self._stt = stt
        self._logger = logger
        self._settings = settings
        self._mode_manager = mode_manager
        self._learning_memory = learning_memory
        self._typing_service = typing_service
        self._say_func = say_func
        self._has_hotword_func = has_hotword_func
        self._strip_hotword_func = strip_hotword_func
        self._is_only_hotword_func = is_only_hotword_func
        self._norm_func = norm_func
        self._is_dictation_stop_phrase_func = is_dictation_stop_phrase_func
        self._predict_func = predict_func
        self._is_accepted_func = is_accepted_func
        self._pick_named_response_func = pick_named_response_func
        self._is_confirmation_yes_func = is_confirmation_yes_func
        self._is_confirmation_no_func = is_confirmation_no_func
        self._current_mode_name_func = current_mode_name_func
        self._handle_command_text_func = handle_command_text_func
        self._open_cmd_window_func = open_cmd_window_func
        self._extend_cmd_window_func = extend_cmd_window_func
        self._close_cmd_window_func = close_cmd_window_func
        self._merge_phrases_func = merge_phrases_func
        self._looks_incomplete_command_func = looks_incomplete_command_func
        self._pending_command_wait_sec = pending_command_wait_sec
        self._normalize_func = normalize_func
        self._should_ignore_during_ack_window_func = should_ignore_during_ack_window_func
        self._router = router
        self._print_func = print_func
        self._time_func = time_func

        self._speech_interrupt_func = speech_interrupt_func
        self._phrase_guard_func = phrase_guard_func
        self._pending_confirmation_func = pending_confirmation_func
        self._dictation_phrase_func = dictation_phrase_func
        self._hotword_activation_func = hotword_activation_func
        self._command_window_func = command_window_func

    def _print(self, text: str) -> None:
        if self._print_func is not None:
            self._print_func(text)

    def process_phrase(
        self,
        phrase: str,
        *,
        last_tts_end: float,
        ack_ignore_until: float,
    ) -> PhraseEventProcessorResult:
        speech_interrupt = self._speech_interrupt_func(
            phrase,
            tts=self._tts,
            logger=self._logger,
            has_hotword_func=self._has_hotword_func,
            strip_hotword_func=self._strip_hotword_func,
            normalize_func=self._normalize_func,
            predict_func=self._predict_func,
        )

        if speech_interrupt.handled:
            if getattr(speech_interrupt, "stopped", False):
                return PhraseEventProcessorResult(
                    handled=True,
                    reason="speech_interrupt_stopped",
                    last_tts_end=self._time_func(),
                )

            return PhraseEventProcessorResult(
                handled=True,
                reason="speech_interrupt_handled",
            )

        phrase_guard = self._phrase_guard_func(
            phrase,
            now=self._time_func(),
            ack_ignore_until=ack_ignore_until,
            last_tts_end=last_tts_end,
            ignore_after_tts_sec=self._settings.ignore_after_tts_sec,
            is_dictation_mode=self._mode_manager.is_dictation_mode(),
            should_ignore_during_ack_window_func=self._should_ignore_during_ack_window_func,
        )

        if phrase_guard.ignored:
            reason = phrase_guard.reason or "stt_ignored"
            self._logger.event(reason, {"text": phrase})

            return PhraseEventProcessorResult(
                handled=True,
                reason=reason,
            )

        self._print(f"🎧 распознано: {phrase}")
        self._logger.event("stt_phrase", {"text": phrase})

        confirmation_result = self._pending_confirmation_func(
            phrase,
            mode_manager=self._mode_manager,
            router=self._router,
            learning_memory=self._learning_memory,
            stt=self._stt,
            tts=self._tts,
            say_func=self._say_func,
            pick_named_response_func=self._pick_named_response_func,
            is_confirmation_yes_func=self._is_confirmation_yes_func,
            is_confirmation_no_func=self._is_confirmation_no_func,
            accept_conf=self._settings.nlu_accept_conf,
            current_mode_name_func=self._current_mode_name_func,
            extend_cmd_window_func=self._extend_cmd_window_func,
        )

        if confirmation_result.handled:
            return PhraseEventProcessorResult(
                handled=True,
                reason=getattr(confirmation_result, "reason", "confirmation_handled"),
                last_tts_end=confirmation_result.last_tts_end,
            )

        dictation_result = self._dictation_phrase_func(
            phrase,
            mode_manager=self._mode_manager,
            typing_service=self._typing_service,
            logger=self._logger,
            stt=self._stt,
            tts=self._tts,
            say_func=self._say_func,
            has_hotword_func=self._has_hotword_func,
            strip_hotword_func=self._strip_hotword_func,
            is_only_hotword_func=self._is_only_hotword_func,
            norm_func=self._norm_func,
            is_dictation_stop_phrase_func=self._is_dictation_stop_phrase_func,
            predict_func=self._predict_func,
            is_accepted_func=self._is_accepted_func,
            pick_named_response_func=self._pick_named_response_func,
        )

        if dictation_result.handled:
            return PhraseEventProcessorResult(
                handled=True,
                reason=getattr(dictation_result, "reason", "dictation_handled"),
                last_tts_end=dictation_result.last_tts_end,
            )

        hotword_activation = self._hotword_activation_func(
            phrase,
            mode_manager=self._mode_manager,
            stt=self._stt,
            tts=self._tts,
            now=self._time_func(),
            ack_text=self._settings.ack_text,
            ack_ignore_sec=self._settings.ack_ignore_sec,
            say_func=self._say_func,
            has_hotword_func=self._has_hotword_func,
            strip_hotword_func=self._strip_hotword_func,
            handle_command_text_func=self._handle_command_text_func,
            open_cmd_window_func=self._open_cmd_window_func,
        )

        phrase = hotword_activation.phrase

        if hotword_activation.handled:
            return PhraseEventProcessorResult(
                handled=True,
                reason=getattr(hotword_activation, "reason", "hotword_activation_handled"),
                last_tts_end=hotword_activation.last_tts_end,
                ack_ignore_until=hotword_activation.ack_ignore_until,
            )

        command_window_result = self._command_window_func(
            phrase,
            mode_manager=self._mode_manager,
            logger=self._logger,
            now=self._time_func(),
            pending_command_wait_sec=self._pending_command_wait_sec,
            is_only_hotword_func=self._is_only_hotword_func,
            norm_func=self._norm_func,
            merge_phrases_func=self._merge_phrases_func,
            looks_incomplete_command_func=self._looks_incomplete_command_func,
            handle_command_text_func=self._handle_command_text_func,
            extend_cmd_window_func=self._extend_cmd_window_func,
            close_cmd_window_func=self._close_cmd_window_func,
        )

        if command_window_result.handled:
            return PhraseEventProcessorResult(
                handled=True,
                reason=getattr(command_window_result, "reason", "command_window_handled"),
            )

        return PhraseEventProcessorResult(
            handled=False,
            reason="no_phrase_handler_matched",
        )