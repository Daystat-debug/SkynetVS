# main.py
from __future__ import annotations

import time
import queue
import threading
import warnings
from pathlib import Path
from typing import Any, Dict

from colorama import init as colorama_init
from dotenv import load_dotenv
from modules.stt_vosk import VoskSTT
from modules.tts_edge import EdgeTTS
from modules.nlu import predict, pick_named_response
from modules.audio_control import AudioControl
from modules.audio_output import AudioOutputControl
from modules.screenshot import ScreenshotService
from modules.actions import Actions
from modules.router import Router
from modules.logger import JsonlLogger, LoggerConfig
from modules.config import Settings
from modules.weather_service import WeatherService
from modules.typing_service import TypingService
from modules.text_normalizer import normalize_command_text
from modules.mode_manager import ModeManager
from modules.window_context_service import WindowContextService
from modules.learning_memory import LearningMemory
from modules.command_decision import build_command_decision
from modules.dictation_commands import is_dictation_stop_phrase
from modules.reply_builder import build_reply_text
from modules.command_understanding import understand_command_text
from modules.confirmation import (
    build_confirmation_prompt,
    is_confirmation_no,
    is_confirmation_yes,
)
from modules.hotword_utils import (
    has_hotword as hotword_has_hotword,
    is_ack_echo as hotword_is_ack_echo,
    is_only_hotword as hotword_is_only_hotword,
    norm_text,
    should_ignore_during_ack_window as hotword_should_ignore_during_ack_window,
    strip_hotword as hotword_strip_hotword,
)
from modules.command_fragments import (
    looks_incomplete_command,
    merge_phrases,
)
from modules.speech_io import (
    say as speech_say,
    say_interruptible as speech_say_interruptible,
)
from modules.command_outcome import (
    OUTCOME_CONFIRMATION_REQUIRED,
    OUTCOME_DICTATION_OFF,
    OUTCOME_DICTATION_ON,
    OUTCOME_INTERRUPTIBLE_REPLY,
    OUTCOME_MISSING_SLOTS,
    OUTCOME_NOT_ACCEPTED,
    classify_command_outcome,
)
from modules.command_learning import (
    log_command_action_failure,
    log_command_observation,
    log_not_accepted_command,
)

colorama_init()
load_dotenv()

# подавляем шумные warnings от pycaw (не влияют на работу)
warnings.filterwarnings(
    "ignore",
    message=r"COMError attempting to get property .* from device .*",
    category=UserWarning,
    module=r"pycaw\.utils",
)

SETTINGS = Settings.from_env()

def norm(text: str) -> str:
    return norm_text(text)


def has_hotword(text: str) -> bool:
    return hotword_has_hotword(text, hotwords=SETTINGS.hotwords)


def strip_hotword(text: str) -> str:
    return hotword_strip_hotword(text, hotwords=SETTINGS.hotwords)


def is_only_hotword(text: str) -> bool:
    return hotword_is_only_hotword(text, hotwords=SETTINGS.hotwords)


def is_ack_echo(text: str) -> bool:
    return hotword_is_ack_echo(text, ack_text=SETTINGS.ack_text)


def should_ignore_during_ack_window(text: str) -> bool:
    return hotword_should_ignore_during_ack_window(
        text,
        hotwords=SETTINGS.hotwords,
        ack_text=SETTINGS.ack_text,
    )


def say(stt: VoskSTT, tts: EdgeTTS, text: str, *, mute_stt: bool = True) -> float:
    return speech_say(stt, tts, text, mute_stt=mute_stt)


def say_interruptible(tts: EdgeTTS, text: str) -> float:
    return speech_say_interruptible(tts, text)


def _merge_phrases(left: str, right: str) -> str:
    return merge_phrases(left, right)


def _looks_incomplete_command(text: str) -> bool:
    return looks_incomplete_command(
        text,
        hotwords=SETTINGS.hotwords,
    )

def _is_accepted(meta: Dict[str, Any]) -> bool:
    """
    Совместимый helper для старых мест main.py.

    Важно:
    источник истины по accepted теперь modules.command_decision,
    а не ручная проверка intent/confidence в main.py.
    """
    decision = build_command_decision(
        meta,
        accept_conf=SETTINGS.nlu_accept_conf,
    )
    return decision.accepted


def _reply_text(router: Router, meta: Dict[str, Any]) -> str:
    return build_reply_text(
        router=router,
        meta=meta,
        accept_conf=SETTINGS.nlu_accept_conf,
        say_conf=SETTINGS.nlu_say_conf,
    )


def main():
    stt = VoskSTT(
        model_path = SETTINGS.stt_model_small,
        samplerate = 16000,
        blocksize = 1024,
        device = SETTINGS.stt_input_device,
    )
    tts = EdgeTTS()
    logger = JsonlLogger(
        LoggerConfig(
            enabled = SETTINGS.log_enable,
            log_path = Path(SETTINGS.log_path),
            inbox_path = Path(SETTINGS.inbox_path),
        )
    )
    learning_memory = LearningMemory()

    whisper = None
    if SETTINGS.whisper_enable:
        try:
            from modules.stt_whisper import WhisperRefiner
            whisper = WhisperRefiner(model_name=SETTINGS.whisper_model, language=SETTINGS.whisper_lang)
            print(f"[WHISPER] enabled: model={SETTINGS.whisper_model} lang={SETTINGS.whisper_lang}")
        except Exception as e:
            whisper = None
            print(f"[WHISPER] disabled: {e}")

    try:
        audio = AudioControl()
    except Exception as e:
        audio = None
        print(f"[AUDIO] disabled: {e}")

    try:
        audio_output = AudioOutputControl(
            headphones_name=SETTINGS.audio_output_headphones,
            speakers_name=SETTINGS.audio_output_speakers,
        )
        audio_output.debug_dump_devices()
    except Exception as e:
        audio_output = None
        print(f"[AUDIO_OUTPUT] disabled: {e}")

    screenshot_service = ScreenshotService()
    weather_service = WeatherService()
    typing_service = TypingService()
    window_context_service = WindowContextService()

    actions = Actions(
        audio=audio,
        volume_step=SETTINGS.volume_step,
        audio_output=audio_output,
        screenshot_service=screenshot_service,
        weather_service=weather_service,
        typing_service=typing_service,
        window_context_service=window_context_service,
    )
    router = Router(actions, settings=SETTINGS)

    print("[BOOT] SkynetVS")
    print("[INFO] Скажи: 'Скайнет' / 'Skynet'")
    print(f"[STT] small model: {SETTINGS.stt_model_small}")

    if SETTINGS.stt_model_large:
        print(f"[STT] loading large model in background: {SETTINGS.stt_model_large}")
        stt.load_model_async(
            SETTINGS.stt_model_large,
            on_swapped=lambda: print("[STT] large model loaded (will switch automatically)"),
        )

    last_tts_end = 0.0
    ack_ignore_until = 0.0
    pending_command_wait_sec = 1.2
    event_q: queue.Queue[dict] = queue.Queue()
    cmd_timer: threading.Timer | None = None
    cmd_window_token = 0
    mode_manager = ModeManager()

    def current_mode_name() -> str:
        if mode_manager.is_dictation_mode():
            return "dictation"
        if mode_manager.is_command_window_open():
            return "command_window"
        return "direct"

    def emit_event(evt: dict) -> None:
        event_q.put(evt)

    def cancel_cmd_timer() -> None:
        nonlocal cmd_timer
        if cmd_timer is not None:
            try:
                cmd_timer.cancel()
            except Exception:
                pass
            cmd_timer = None

    def schedule_cmd_timeout() -> None:
        nonlocal cmd_timer, cmd_window_token
        cancel_cmd_timer()
        cmd_window_token += 1
        token = cmd_window_token

        def _fire() -> None:
            emit_event({"type": "cmd_timeout", "token": token})

        cmd_timer = threading.Timer(SETTINGS.command_window_sec, _fire)
        cmd_timer.daemon = True
        cmd_timer.start()

    def open_cmd_window() -> None:
        mode_manager.open_command_window()
        logger.event("cmd_window_open", {"deadline_sec": SETTINGS.command_window_sec, "ack": SETTINGS.ack_text})
        schedule_cmd_timeout()

    def extend_cmd_window() -> None:
        if mode_manager.is_command_window_open():
            schedule_cmd_timeout()
            logger.event("cmd_window_extend", {"deadline_sec": SETTINGS.command_window_sec})

    def close_cmd_window(reason: str, *, speak_close: bool) -> None:
        nonlocal last_tts_end
        if not mode_manager.is_command_window_open():
            return
        mode_manager.close_command_window()
        cancel_cmd_timer()
        print("⬛ [SKYNET] окно команды закрыто")
        logger.event(reason, {})
        if speak_close:
            last_tts_end = say(stt, tts, "Окно команды закрыто")

    def stt_producer() -> None:
        try:
            for phrase in stt.listen_phrases():
                emit_event({"type": "phrase", "text": phrase})
        except Exception as e:
            emit_event({"type": "stt_error", "error": str(e)})

    threading.Thread(target=stt_producer, daemon=True).start()

    def handle_command_text(command_text: str, *, immediate_label: str) -> dict[str, Any]:
        """
        Единая обработка текстовой команды:
        NLU -> Whisper fallback -> Router preprocess -> reply -> execute.
        immediate_label нужен только для красивого лога:
          - "команда сразу"
          - "команда"
        """
        nonlocal last_tts_end

        raw_text_in = norm(command_text)
        if not raw_text_in:
            return {"intent": None, "confidence": 0.0, "slots": {}, "say": ""}

        if immediate_label == "immediate":
            print(f"✅ команда сразу: {raw_text_in}")
        else:
            print(f"✅ команда: {raw_text_in}")

        understanding = understand_command_text(
            raw_text_in,
            router=router,
            logger=logger,
            whisper=whisper,
            stt=stt,
            accept_conf=SETTINGS.nlu_accept_conf,
            whisper_trigger_conf=SETTINGS.whisper_trigger_conf,
            print_func=print,
        )

        raw_text_in = understanding.raw_text
        text_in = understanding.final_text
        meta = understanding.meta
        decision = understanding.decision
        outcome = classify_command_outcome(meta, decision)

        accepted = decision.accepted
        missing_slots = decision.missing_slots

        log_command_observation(
            learning_memory=learning_memory,
            raw_text=raw_text_in,
            final_text=text_in,
            meta=meta,
            mode=current_mode_name(),
            accepted=accepted,
            immediate_label=immediate_label,
            missing_slots=missing_slots,
        )

        if outcome.kind == OUTCOME_NOT_ACCEPTED:
            log_not_accepted_command(
                learning_memory=learning_memory,
                raw_text=raw_text_in,
                final_text=text_in,
                meta=meta,
                mode=current_mode_name(),
                reason=decision.reason or "not_accepted",
            )
            text_out = _reply_text(router, meta)
            logger.inbox(text_in, meta)
            last_tts_end = say(stt, tts, text_out)
            return meta

        if outcome.kind == OUTCOME_MISSING_SLOTS:
            logger.event(
                "missing_required_slots_blocked",
                {
                    "text": text_in,
                    "intent": meta.get("intent"),
                    "missing_slots": decision.missing_slots,
                    "slots": meta.get("slots") or {},
                },
            )

            text_out = router.reply(meta) or "Не хватает данных для выполнения команды."
            last_tts_end = say(stt, tts, text_out)
            return meta

        if outcome.kind == OUTCOME_CONFIRMATION_REQUIRED:
            mode_manager.set_pending_confirmation(
                {
                    "meta": meta,
                }
            )
            prompt = build_confirmation_prompt(meta)
            last_tts_end = say(stt, tts, prompt)
            return meta

        intent_name = (meta.get("intent") or "").upper()

        if outcome.kind == OUTCOME_DICTATION_ON:
            mode_manager.enter_dictation_mode()
            mode_manager.close_command_window()
            cancel_cmd_timer()

            text_out = _reply_text(router, meta)
            last_tts_end = say(stt, tts, text_out)
            return meta

        if outcome.kind == OUTCOME_DICTATION_OFF:
            mode_manager.exit_dictation_mode()
            text_out = _reply_text(router, meta)
            last_tts_end = say(stt, tts, text_out)
            return meta

        text_out = _reply_text(router, meta)

        if outcome.kind == OUTCOME_INTERRUPTIBLE_REPLY:
            last_tts_end = say_interruptible(tts, text_out)
            return meta

        last_tts_end = say(stt, tts, text_out)
        try:
            router.execute(meta)
        except Exception as e:
            log_command_action_failure(
                learning_memory=learning_memory,
                raw_text=raw_text_in,
                final_text=text_in,
                meta=meta,
                mode=current_mode_name(),
                error=e,
            )
            raise
        return meta

    def handle_cmd_timeout_event(evt: dict) -> None:
        if mode_manager.is_command_window_open() and int(evt.get("token") or -1) == cmd_window_token:
            close_cmd_window("cmd_window_close_timeout", speak_close=True)

    def handle_phrase_event(evt: dict) -> None:
        nonlocal last_tts_end, ack_ignore_until

        phrase = evt.get("text") or ""

        # Пока ассистент говорит interruptible-речь, сначала даём шанс команде STOP_TALKING.
        # Во время активной речи разрешаем stop и с hotword, и без hotword.
        if tts.is_speaking():
            stop_text = phrase
            if has_hotword(stop_text):
                stop_text = strip_hotword(stop_text) or stop_text

            stop_text, _ = normalize_command_text(stop_text)

            stop_meta = predict(stop_text)
            if (stop_meta.get("intent") or "").upper() == "STOP_TALKING":
                logger.event("tts_stop_requested", {"text": phrase})
                tts.stop()
                last_tts_end = time.time()
                return

            logger.event("stt_ignored_while_tts_speaking", {"text": phrase})
            return

        # Сначала фильтруем эхо ACK/горячее слово после ACK,
        # и только потом печатаем/логируем как обычную фразу.
        if time.time() < ack_ignore_until and should_ignore_during_ack_window(phrase):
            logger.event("stt_ignored_ack_window", {"text": phrase})
            return

        if not mode_manager.is_dictation_mode() and (time.time() - last_tts_end) < SETTINGS.ignore_after_tts_sec:
            logger.event("stt_ignored_after_tts", {"text": phrase})
            return

        print(f"🎧 распознано: {phrase}")
        logger.event("stt_phrase", {"text": phrase})

        if mode_manager.has_pending_confirmation():
            pending_confirmation = mode_manager.get_pending_confirmation() or {}
            if is_confirmation_yes(phrase):
                meta = pending_confirmation.get("meta") or {}
                clear_pending_confirmation()

                confirm_ok = pick_named_response("CONFIRM_OK")
                last_tts_end = say(
                    stt,
                    tts,
                    confirm_ok or "Подтверждаю. Выполняю."
                )

                confirm_decision = build_command_decision(
                    meta,
                    accept_conf=SETTINGS.nlu_accept_conf,
                )

                if confirm_decision.accepted and not confirm_decision.missing_slots:
                    try:
                        router.execute(meta)
                    except Exception as e:
                        log_command_action_failure(
                            learning_memory=learning_memory,
                            raw_text=meta.get("_text") or "",
                            final_text=meta.get("_text") or "",
                            meta=meta,
                            mode=current_mode_name(),
                            error=e,
                        )
                        raise

                if mode_manager.is_command_window_open():
                    extend_cmd_window()
                return

            if is_confirmation_no(phrase):
                clear_pending_confirmation()

                confirm_cancel = pick_named_response("CONFIRM_CANCEL")
                last_tts_end = say(
                    stt,
                    tts,
                    confirm_cancel or "Отменено."
                )

                if mode_manager.is_command_window_open():
                    extend_cmd_window()
                return

            confirm_repeat = pick_named_response("CONFIRM_REPEAT")
            last_tts_end = say(
                stt,
                tts,
                confirm_repeat or "Скажи да или нет."
            )

            if mode_manager.is_command_window_open():
                extend_cmd_window()
            return

        if mode_manager.is_dictation_mode():
            if is_only_hotword(phrase):
                logger.event("dictation_ignore_bare_hotword", {"text": phrase})
                return

            dictation_text = phrase
            if has_hotword(dictation_text):
                dictation_text = strip_hotword(dictation_text) or ""

            dictation_text = norm(dictation_text)
            if not dictation_text:
                return

            if is_dictation_stop_phrase(dictation_text):
                mode_manager.exit_dictation_mode()
                text_out = pick_named_response("DICTATION_MODE_OFF") or "Режим диктовки выключен."
                last_tts_end = say(stt, tts, text_out)
                logger.event("dictation_mode_off", {"text": phrase})
                return

            stop_meta = predict(dictation_text)
            if (stop_meta.get("intent") or "").upper() == "DICTATION_MODE_OFF" and _is_accepted(stop_meta):
                mode_manager.exit_dictation_mode()
                text_out = pick_named_response("DICTATION_MODE_OFF") or "Режим диктовки выключен."
                last_tts_end = say(stt, tts, text_out)
                logger.event("dictation_mode_off", {"text": phrase})
                return

            dictation_intent = (stop_meta.get("intent") or "").upper()
            if dictation_intent == "PRESS_ENTER" and _is_accepted(stop_meta):
                typing_service.press_enter()
                mode_manager.reset_dictation_separator()
                logger.event("dictation_editor_action", {"action": "enter", "text": phrase})
                return

            if dictation_intent == "PRESS_BACKSPACE" and _is_accepted(stop_meta):
                typing_service.press_backspace()
                logger.event("dictation_editor_action", {"action": "backspace", "text": phrase})
                return

            if dictation_intent == "PRESS_TAB" and _is_accepted(stop_meta):
                typing_service.press_tab()
                mode_manager.reset_dictation_separator()
                logger.event("dictation_editor_action", {"action": "tab", "text": phrase})
                return

            text_to_type = mode_manager.dictation_prefix() + dictation_text
            typing_service.type_text(text_to_type)
            mode_manager.mark_dictation_text_typed()
            logger.event("dictation_typed", {"text": text_to_type})
            return

        # если уже ждём команду, и пользователь сказал "скайнет <...>", считаем это командой
        if mode_manager.is_command_window_open() and has_hotword(phrase):
            phrase = strip_hotword(phrase) or phrase

        if not mode_manager.is_command_window_open() and has_hotword(phrase):
            rest = strip_hotword(phrase)
            if rest:
                handle_command_text(rest, immediate_label="immediate")
                return

            # Говорим ACK и открываем независимое окно команд
            # mute_stt=False чтобы не терять начало команды после "Слушаю"
            last_tts_end = say(stt, tts, SETTINGS.ack_text, mute_stt=False)
            ack_ignore_until = time.time() + max(0.2, SETTINGS.ack_ignore_sec)
            open_cmd_window()
            return

        if mode_manager.is_command_window_open():
            now = time.time()

            # если в уже открытом окне снова прилетел только hotword,
            # просто игнорируем его и держим окно открытым
            if is_only_hotword(phrase):
                logger.event("cmd_ignore_bare_hotword", {"text": phrase})
                extend_cmd_window()
                return

            cmd_candidate = norm(phrase)

            # если уже ждём хвост короткой команды и пришла новая фраза —
            # ВСЕГДА сначала пробуем склеить, даже если wait_sec уже почти истёк
            if mode_manager.has_pending_command() and cmd_candidate:
                cmd_candidate = _merge_phrases(mode_manager.get_pending_command_text(), cmd_candidate)
                mode_manager.clear_pending_command()
            elif mode_manager.has_pending_command() and (
                    now - mode_manager.get_pending_command_ts()) > pending_command_wait_sec:
                if is_only_hotword(mode_manager.get_pending_command_text()):
                    mode_manager.clear_pending_command()
                    extend_cmd_window()
                    return
                cmd_candidate = mode_manager.get_pending_command_text()
                mode_manager.clear_pending_command()

            # если команда выглядит обрезанной/незавершённой —
            # подождём хвост, а окно продлим
            if _looks_incomplete_command(cmd_candidate):
                mode_manager.set_pending_command(cmd_candidate, now)
                extend_cmd_window()
                logger.event("cmd_pending_fragment", {"text": cmd_candidate})
                return

            phrase = cmd_candidate

            cmd = norm(phrase)
            meta = handle_command_text(cmd, immediate_label="window")

            # Если сказали "стоп/всё/закрой режим" — закрываем окно команд явно
            if (meta.get("intent") or "").upper() == "STOP_LISTEN":
                close_cmd_window("cmd_window_close_stop_intent", speak_close=False)
                return

            # Окно команд НЕ закрываем после одной команды.
            extend_cmd_window()
            return


    def clear_pending_confirmation() -> None:
        mode_manager.clear_pending_confirmation()

    while True:
        evt = event_q.get()

        if evt.get("type") == "stt_error":
            print(f"[STT] producer error: {evt.get('error')}")
            logger.event("stt_error", {"error": evt.get("error")})
            continue

        if evt.get("type") == "cmd_timeout":
            handle_cmd_timeout_event(evt)
            continue

        if evt.get("type") == "phrase":
            handle_phrase_event(evt)
            continue


if __name__ == "__main__":
    main()