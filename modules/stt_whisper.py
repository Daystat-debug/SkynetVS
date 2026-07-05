# modules/stt_whisper.py
from __future__ import annotations

import os
from typing import Optional

import numpy as np


class WhisperRefiner:
    """
    Offline Whisper refine (fallback).
    Lazy-loads model. Works on raw PCM int16 mono bytes.
    Requires: faster-whisper
    """

    def __init__(
        self,
        model_name: str = "small",
        language: str = "ru",
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ):
        self.model_name = model_name
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model

        from faster_whisper import WhisperModel  # lazy import

        device = self.device or os.getenv("WHISPER_DEVICE") or "cuda"
        compute_type = self.compute_type or os.getenv("WHISPER_COMPUTE_TYPE") or "float16"

        # если cuda недоступна — faster-whisper сам упадет; тогда лучше cpu
        try:
            self._model = WhisperModel(self.model_name, device=device, compute_type=compute_type)
        except Exception:
            self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")

        return self._model

    def refine_pcm(self, pcm_i16_mono: bytes, samplerate: int) -> str:
        if not pcm_i16_mono:
            return ""

        # PCM int16 -> float32 [-1..1]
        audio = np.frombuffer(pcm_i16_mono, dtype=np.int16).astype(np.float32) / 32768.0
        if audio.size == 0:
            return ""

        model = self._load()

        # beam_size маленький — быстрее; можно поднять позже
        segments, info = model.transcribe(
            audio,
            language=self.language,
            vad_filter=True,
            beam_size=int(os.getenv("WHISPER_BEAM", "3")),
        )

        parts = []
        for seg in segments:
            t = (seg.text or "").strip()
            if t:
                parts.append(t)

        return " ".join(parts).strip()
