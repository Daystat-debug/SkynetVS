# modules/config.py

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple


DEFAULT_NLU_ACCEPT_CONF = 0.35


@dataclass(frozen=True)
class Settings:
    # STT
    stt_model_small: str
    stt_model_large: str
    stt_input_device: str

    # Wake word / flow
    hotwords: Tuple[str, ...]
    command_window_sec: float
    ignore_after_tts_sec: float
    ack_text: str
    ack_ignore_sec: float

    # NLU thresholds
    nlu_accept_conf: float
    nlu_say_conf: float

    # TTS
    tts_voice: str
    tts_rate: str
    tts_volume: str
    tts_pitch: str

    # Audio
    volume_step: int
    audio_output_headphones: str
    audio_output_speakers: str

    # Whisper refine
    whisper_enable: bool
    whisper_model: str
    whisper_lang: str
    whisper_trigger_conf: float

    # Logging
    log_enable: bool
    log_path: str
    inbox_path: str

    # Router / execution
    exec_mode: str
    repeat_context_sec: float

    @staticmethod
    def _hotwords_from_env() -> Tuple[str, ...]:
        raw = os.getenv("HOTWORDS", "скайнет,skynet")
        arr = [w.strip().lower() for w in raw.split(",") if w.strip()]
        return tuple(arr)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            stt_model_small=os.getenv("STT_MODEL_SMALL", "models/model_small").strip(),
            stt_model_large=os.getenv("STT_MODEL_LARGE", "models/model_large").strip(),
            stt_input_device=os.getenv("STT_DEVICE", "").strip(),

            hotwords=cls._hotwords_from_env(),
            command_window_sec=float(os.getenv("COMMAND_WINDOW_SEC", "7.0")),
            ignore_after_tts_sec=float(os.getenv("IGNORE_AFTER_TTS_SEC", "1.0")),
            ack_text=os.getenv("ACK_TEXT", "Слушаю").strip(),
            ack_ignore_sec=float(os.getenv("ACK_IGNORE_SEC", "1.2")),

            nlu_accept_conf=float(os.getenv("NLU_ACCEPT_CONF", str(DEFAULT_NLU_ACCEPT_CONF))),
            nlu_say_conf=float(os.getenv("NLU_SAY_CONF", "0.55")),

            tts_voice=os.getenv("TTS_VOICE", "ru-RU-SvetlanaNeural").strip() or "ru-RU-SvetlanaNeural",
            tts_rate=os.getenv("TTS_RATE", "+0%").strip() or "+0%",
            tts_volume=os.getenv("TTS_VOLUME", "+20%").strip() or "+20%",
            tts_pitch=os.getenv("TTS_PITCH", "+0Hz").strip() or "+0Hz",

            volume_step=int(os.getenv("VOLUME_STEP", "10")),
            audio_output_headphones=os.getenv("AUDIO_OUTPUT_HEADPHONES", "Динамики (6- USB Audio Device)").strip(),
            audio_output_speakers=os.getenv("AUDIO_OUTPUT_SPEAKERS",
                                            "Динамики (Realtek High Definition Audio)").strip(),

            whisper_enable=os.getenv("WHISPER_ENABLE", "0").strip() == "1",
            whisper_model=os.getenv("WHISPER_MODEL", "small").strip(),
            whisper_lang=os.getenv("WHISPER_LANG", "ru").strip(),
            whisper_trigger_conf=float(os.getenv("WHISPER_TRIGGER_CONF", "0.45")),

            log_enable=os.getenv("LOG_ENABLE", "1").strip() == "1",
            log_path=os.getenv("LOG_PATH", "data/logs/runtime.jsonl").strip(),
            inbox_path=os.getenv("INBOX_PATH", "data/inbox_unlabeled.jsonl").strip(),

            exec_mode=os.getenv("EXEC_MODE", "direct").strip().lower(),
            repeat_context_sec=float(os.getenv("REPEAT_CONTEXT_SEC", "15")),
        )
