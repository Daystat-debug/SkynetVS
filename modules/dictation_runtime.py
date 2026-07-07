from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


SayFunc = Callable[[Any, Any, str], float]
TextPredicate = Callable[[str], bool]
TextTransform = Callable[[str], str]
PredictFunc = Callable[[str], Mapping[str, Any]]
PickNamedResponseFunc = Callable[[str], str | None]
IsAcceptedFunc = Callable[[Mapping[str, Any]], bool]


@dataclass(frozen=True)
class DictationPhraseResult:
    handled: bool
    reason: str
    last_tts_end: float | None = None


def handle_dictation_phrase(
    phrase: str,
    *,
    mode_manager: Any,
    typing_service: Any,
    logger: Any,
    stt: Any,
    tts: Any,
    say_func: SayFunc,
    has_hotword_func: TextPredicate,
    strip_hotword_func: TextTransform,
    is_only_hotword_func: TextPredicate,
    norm_func: TextTransform,
    is_dictation_stop_phrase_func: TextPredicate,
    predict_func: PredictFunc,
    is_accepted_func: IsAcceptedFunc,
    pick_named_response_func: PickNamedResponseFunc,
) -> DictationPhraseResult:
    """
    Обрабатывает фразу, когда ассистент находится в режиме диктовки.

    Не занимается:
      - hotword activation;
      - command window;
      - confirmation;
      - обычными командами вне диктовки.
    """
    if not mode_manager.is_dictation_mode():
        return DictationPhraseResult(
            handled=False,
            reason="not_dictation_mode",
        )

    if is_only_hotword_func(phrase):
        logger.event("dictation_ignore_bare_hotword", {"text": phrase})
        return DictationPhraseResult(
            handled=True,
            reason="bare_hotword_ignored",
        )

    dictation_text = phrase

    if has_hotword_func(dictation_text):
        dictation_text = strip_hotword_func(dictation_text) or ""

    dictation_text = norm_func(dictation_text)

    if not dictation_text:
        return DictationPhraseResult(
            handled=True,
            reason="empty_dictation_text",
        )

    if is_dictation_stop_phrase_func(dictation_text):
        mode_manager.exit_dictation_mode()

        text_out = (
            pick_named_response_func("DICTATION_MODE_OFF")
            or "Режим диктовки выключен."
        )

        last_tts_end = say_func(stt, tts, text_out)

        logger.event("dictation_mode_off", {"text": phrase})

        return DictationPhraseResult(
            handled=True,
            reason="dictation_stop_phrase",
            last_tts_end=last_tts_end,
        )

    stop_meta = dict(predict_func(dictation_text))
    stop_intent = str(stop_meta.get("intent") or "").upper()

    if stop_intent == "DICTATION_MODE_OFF" and is_accepted_func(stop_meta):
        mode_manager.exit_dictation_mode()

        text_out = (
            pick_named_response_func("DICTATION_MODE_OFF")
            or "Режим диктовки выключен."
        )

        last_tts_end = say_func(stt, tts, text_out)

        logger.event("dictation_mode_off", {"text": phrase})

        return DictationPhraseResult(
            handled=True,
            reason="dictation_off_intent",
            last_tts_end=last_tts_end,
        )

    if stop_intent == "PRESS_ENTER" and is_accepted_func(stop_meta):
        typing_service.press_enter()
        mode_manager.reset_dictation_separator()
        logger.event("dictation_editor_action", {"action": "enter", "text": phrase})

        return DictationPhraseResult(
            handled=True,
            reason="press_enter",
        )

    if stop_intent == "PRESS_BACKSPACE" and is_accepted_func(stop_meta):
        typing_service.press_backspace()
        logger.event("dictation_editor_action", {"action": "backspace", "text": phrase})

        return DictationPhraseResult(
            handled=True,
            reason="press_backspace",
        )

    if stop_intent == "PRESS_TAB" and is_accepted_func(stop_meta):
        typing_service.press_tab()
        mode_manager.reset_dictation_separator()
        logger.event("dictation_editor_action", {"action": "tab", "text": phrase})

        return DictationPhraseResult(
            handled=True,
            reason="press_tab",
        )

    text_to_type = mode_manager.dictation_prefix() + dictation_text

    typing_service.type_text(text_to_type)
    mode_manager.mark_dictation_text_typed()

    logger.event("dictation_typed", {"text": text_to_type})

    return DictationPhraseResult(
        handled=True,
        reason="typed_text",
    )