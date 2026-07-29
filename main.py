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
from modules.core.logger import JsonlLogger, LoggerConfig
from modules.core.config import Settings
from modules.weather_service import WeatherService
from modules.typing_service import TypingService
from modules.text_normalizer import normalize_command_text
from modules.runtime.mode_manager import ModeManager
from modules.window_context_service import WindowContextService
from modules.learning.learning_memory import LearningMemory
from modules.command_decision import build_command_decision
from modules.dictation_commands import is_dictation_stop_phrase
from modules.reply_builder import build_reply_text
from modules.phrase_event_processor import PhraseEventProcessor
from modules.command_processor import CommandProcessor
from modules.confirmation import (
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
from modules.timer_service import (
    TimerFiredEvent,
    TimerService,
)
from modules.reminder_repository import ReminderRepository
from modules.reminder_runtime import (
    build_reminder_fired_message,
    build_reminder_fired_queue_event,
)
from modules.reminder_service import (
    ReminderFiredEvent,
    ReminderService,
)
from modules.runtime_service_health_runtime import (
    collect_runtime_service_health,
    publish_runtime_service_health,
)
from modules.runtime_service_health_monitor import (
    RuntimeServiceHealthMonitor,
    publish_runtime_service_health_transition,
)
from modules.runtime.runtime_shutdown import shutdown_runtime_services

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
    tts = EdgeTTS(
        voice=SETTINGS.tts_voice,
        rate=SETTINGS.tts_rate,
        volume=SETTINGS.tts_volume,
        pitch=SETTINGS.tts_pitch,
    )
    logger = JsonlLogger(
        LoggerConfig(
            enabled = SETTINGS.log_enable,
            log_path = Path(SETTINGS.log_path),
            inbox_path = Path(SETTINGS.inbox_path),
        )
    )
    learning_memory = LearningMemory()

    event_q: queue.Queue[dict] = (
        queue.Queue()
    )

    def emit_event(evt: dict) -> None:
        event_q.put(evt)

    def on_timer_fired(
        event: TimerFiredEvent,
    ) -> None:
        emit_event(
            {
                "type": "timer_fired",
                "timer": {
                    "token": event.token,
                    "duration_seconds": (
                        event.duration_seconds
                    ),
                    "started_at": (
                        event.started_at
                    ),
                    "deadline": event.deadline,
                    "fired_at": event.fired_at,
                },
            }
        )

    timer_service = TimerService(
        on_fired=on_timer_fired,
    )

    def on_reminder_fired(event: ReminderFiredEvent) -> None:
        emit_event(build_reminder_fired_queue_event(event))

    reminder_service: ReminderService | None = None
    reminder_error = ""
    reminder_path = Path(__file__).resolve().parent / "data" / "reminders.json"

    try:
        reminder_path.parent.mkdir(parents=True, exist_ok=True)

        reminder_repository = ReminderRepository(reminder_path)
        reminder_service = ReminderService(
            repository=reminder_repository,
            on_fired=on_reminder_fired,
        )

        snapshot = reminder_service.status()

        print(f"[REMINDER] enabled: active={snapshot.count}")
        logger.event(
            "reminder_service_started",
            {
                "path": str(reminder_path),
                "active_count": snapshot.count,
                "scheduled_reminder_id": snapshot.scheduled_reminder_id,
            },
        )
    except Exception as e:
        reminder_error = str(e)
        print(f"[REMINDER] disabled: {e}")
        logger.event(
            "reminder_service_init_failed",
            {
                "path": str(reminder_path),
                "error": str(e),
            },
        )

    whisper = None
    if SETTINGS.whisper_enable:
        try:
            from modules.stt_whisper import WhisperRefiner
            whisper = WhisperRefiner(model_name=SETTINGS.whisper_model, language=SETTINGS.whisper_lang)
            print(f"[WHISPER] enabled: model={SETTINGS.whisper_model} lang={SETTINGS.whisper_lang}")
        except Exception as e:
            whisper = None
            print(f"[WHISPER] disabled: {e}")

    audio_error = ""

    try:
        audio = AudioControl(validate_on_init=False)
    except Exception as e:
        audio = None
        audio_error = str(e)
        print(f"[AUDIO] disabled: {e}")

    audio_output_error = ""

    try:
        audio_output = AudioOutputControl(
            headphones_name=SETTINGS.audio_output_headphones,
            speakers_name=SETTINGS.audio_output_speakers,
        )
        audio_output.debug_dump_devices()
    except Exception as e:
        audio_output = None
        audio_output_error = str(e)
        print(f"[AUDIO_OUTPUT] disabled: {e}")

    screenshot_service = ScreenshotService()
    weather_service = WeatherService()
    typing_service = TypingService()
    window_context_service = WindowContextService()

    def collect_runtime_health():
        return collect_runtime_service_health(
            stt=stt,
            stt_model_path=SETTINGS.stt_model_small,
            tts=tts,
            audio=audio,
            audio_output=audio_output,
            weather_service=weather_service,
            timer_service=timer_service,
            reminder_service=reminder_service,
            audio_error=audio_error,
            audio_output_error=audio_output_error,
            reminder_error=reminder_error,
            reminder_path=str(reminder_path),
        )

    def collect_and_publish_runtime_health(*, print_report: bool):
        report = collect_runtime_health()
        publish_runtime_service_health(
            report,
            event_func=logger.event,
            print_func=print if print_report else None,
        )
        return report

    actions = Actions(
        audio=audio,
        volume_step=SETTINGS.volume_step,
        audio_output=audio_output,
        screenshot_service=screenshot_service,
        weather_service=weather_service,
        typing_service=typing_service,
        window_context_service=window_context_service,
        timer_service=timer_service,
        reminder_service=reminder_service,
        event_func=logger.event,
        runtime_health_provider=lambda: collect_and_publish_runtime_health(print_report=False),
    )
    router = Router(actions, settings=SETTINGS)
    runtime_health_monitor = RuntimeServiceHealthMonitor(
        enabled=SETTINGS.runtime_health_monitor_enable,
        interval_sec=SETTINGS.runtime_health_monitor_interval_sec,
    )

    print("[BOOT] SkynetVS")
    print("[INFO] Скажи: 'Скайнет' / 'Skynet'")
    print(f"[STT] small model: {SETTINGS.stt_model_small}")

    runtime_health_report = collect_and_publish_runtime_health(print_report=True)
    runtime_health_monitor.set_baseline(runtime_health_report)

    if runtime_health_monitor.enabled:
        print(f"[HEALTH] monitor enabled: interval={runtime_health_monitor.interval_sec:.1f}s")
    else:
        print("[HEALTH] monitor disabled")

    if SETTINGS.stt_model_large:
        print(f"[STT] loading large model in background: {SETTINGS.stt_model_large}")
        stt.load_model_async(
            SETTINGS.stt_model_large,
            on_swapped=lambda: print("[STT] large model loaded (will switch automatically)"),
        )

    last_tts_end = 0.0
    ack_ignore_until = 0.0
    pending_command_wait_sec = 1.2
    cmd_timer: threading.Timer | None = None
    cmd_window_token = 0
    mode_manager = ModeManager()

    def current_mode_name() -> str:
        if mode_manager.is_dictation_mode():
            return "dictation"
        if mode_manager.is_command_window_open():
            return "command_window"
        return "direct"

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

    command_processor = CommandProcessor(
        router=router,
        logger=logger,
        whisper=whisper,
        stt=stt,
        tts=tts,
        settings=SETTINGS,
        learning_memory=learning_memory,
        mode_manager=mode_manager,
        say_func=say,
        say_interruptible_func=say_interruptible,
        reply_text_func=lambda m: _reply_text(router, dict(m)),
        current_mode_name_func=current_mode_name,
        cancel_cmd_timer_func=cancel_cmd_timer,
        print_func=print,
    )

    def handle_command_text(command_text: str, *, immediate_label: str) -> dict[str, Any]:
        nonlocal last_tts_end

        result = command_processor.process(
            command_text,
            immediate_label=immediate_label,
        )

        if result.last_tts_end is not None:
            last_tts_end = result.last_tts_end

        return result.meta

    phrase_event_processor = PhraseEventProcessor(
        tts=tts,
        stt=stt,
        logger=logger,
        settings=SETTINGS,
        mode_manager=mode_manager,
        learning_memory=learning_memory,
        typing_service=typing_service,
        say_func=say,
        has_hotword_func=has_hotword,
        strip_hotword_func=strip_hotword,
        is_only_hotword_func=is_only_hotword,
        norm_func=norm,
        is_dictation_stop_phrase_func=is_dictation_stop_phrase,
        predict_func=predict,
        is_accepted_func=_is_accepted,
        pick_named_response_func=pick_named_response,
        is_confirmation_yes_func=is_confirmation_yes,
        is_confirmation_no_func=is_confirmation_no,
        current_mode_name_func=current_mode_name,
        handle_command_text_func=handle_command_text,
        open_cmd_window_func=open_cmd_window,
        extend_cmd_window_func=extend_cmd_window,
        close_cmd_window_func=close_cmd_window,
        merge_phrases_func=_merge_phrases,
        looks_incomplete_command_func=_looks_incomplete_command,
        pending_command_wait_sec=pending_command_wait_sec,
        normalize_func=normalize_command_text,
        should_ignore_during_ack_window_func=should_ignore_during_ack_window,
        router=router,
        print_func=print,
        time_func=time.time,
    )

    def handle_cmd_timeout_event(evt: dict) -> None:
        if mode_manager.is_command_window_open() and int(evt.get("token") or -1) == cmd_window_token:
            close_cmd_window("cmd_window_close_timeout", speak_close=True)

    def handle_phrase_event(evt: dict) -> None:
        nonlocal last_tts_end, ack_ignore_until

        result = phrase_event_processor.process_phrase(
            evt.get("text") or "",
            last_tts_end=last_tts_end,
            ack_ignore_until=ack_ignore_until,
        )

        if result.last_tts_end is not None:
            last_tts_end = result.last_tts_end

        if result.ack_ignore_until is not None:
            ack_ignore_until = result.ack_ignore_until

    def handle_timer_fired_event(
        evt: dict,
    ) -> None:
        nonlocal last_tts_end

        payload = dict(
            evt.get("timer") or {}
        )

        event_token = int(
            payload.get("token") or -1
        )

        current_token = (
            timer_service.status().token
        )

        # Callback мог уже положить событие в queue,
        # после чего пользователь отменил или
        # заменил timer.
        if event_token != current_token:
            logger.event(
                "timer_fired_stale_ignored",
                {
                    **payload,
                    "current_token": (
                        current_token
                    ),
                },
            )
            return

        print("⏰ [TIMER] Таймер завершён")

        logger.event(
            "timer_fired",
            payload,
        )

        last_tts_end = say(
            stt,
            tts,
            "Таймер завершён",
        )

    def handle_reminder_fired_event(evt: dict) -> None:
        nonlocal last_tts_end

        payload = dict(evt.get("reminder") or {})
        message = build_reminder_fired_message(payload)

        print(f"⏰ [REMINDER] {message}")
        logger.event("reminder_fired", payload)

        last_tts_end = say(stt, tts, message)

    def log_runtime_health_monitor_event(
        kind: str,
        payload: dict[str, Any],
    ) -> None:
        try:
            logger.event(kind, payload)
        except Exception as e:
            print(f"[HEALTH] monitor log failed: {e}")

    def handle_runtime_health_monitor_poll() -> None:
        result = runtime_health_monitor.poll_if_due(
            collect_runtime_health
        )

        if not result.attempted:
            return

        if result.error:
            if result.error_changed:
                print(f"[HEALTH] monitor failed: {result.error}")
                log_runtime_health_monitor_event(
                    "runtime_service_health_monitor_failed",
                    {
                        "error": result.error,
                        "interval_sec": runtime_health_monitor.interval_sec,
                    },
                )
            return

        if result.recovered_from_error:
            print("[HEALTH] monitor recovered")
            log_runtime_health_monitor_event(
                "runtime_service_health_monitor_recovered",
                {
                    "previous_error": result.recovered_from_error,
                    "interval_sec": runtime_health_monitor.interval_sec,
                },
            )

        if result.transition is not None:
            publish_runtime_service_health_transition(
                result.transition,
                event_func=logger.event,
                print_func=print,
            )

    try:
        while True:
            handle_runtime_health_monitor_poll()

            try:
                evt = event_q.get(
                    timeout=runtime_health_monitor.seconds_until_poll()
                )
            except queue.Empty:
                continue

            event_type = evt.get("type")

            if event_type == "stt_error":
                print(f"[STT] producer error: {evt.get('error')}")
                logger.event("stt_error", {"error": evt.get("error")})
                continue

            if event_type == "cmd_timeout":
                handle_cmd_timeout_event(evt)
                continue

            if event_type == "timer_fired":
                handle_timer_fired_event(evt)
                continue

            if event_type == "reminder_fired":
                handle_reminder_fired_event(evt)
                continue

            if event_type == "phrase":
                handle_phrase_event(evt)
                continue
    except KeyboardInterrupt:
        print("\n[STOP] SkynetVS")
    finally:
        shutdown_runtime_services(
            cancel_command_timer_func=cancel_cmd_timer,
            tts=tts,
            timer_service=timer_service,
            reminder_service=reminder_service,
            event_func=logger.event,
            print_func=print,
        )

if __name__ == "__main__":
    main()