# modules/stt_vosk.py
from __future__ import annotations

import json
import queue
import threading
import time

from dataclasses import dataclass
from typing import Callable, Iterator, Optional, Union

import sounddevice as sd
from vosk import Model, KaldiRecognizer


@dataclass(frozen=True)
class STTLifecycleSnapshot:
    stream_started: bool
    stream_active: bool
    stream_generation: int
    stream_phase: str
    paused: bool
    last_stream_started_at: float | None
    last_stream_stopped_at: float | None
    last_audio_block_at: float | None
    audio_block_count: int
    audio_bytes_total: int
    last_processed_audio_block_at: float | None
    processed_audio_block_count: int
    queue_size: int
    last_phrase_at: float | None
    phrase_count: int
    last_callback_status_at: float | None
    last_callback_status: str
    callback_status_count: int
    last_error_at: float | None
    last_error: str
    failure_count: int
    consecutive_failures: int


class VoskSTT:
    """
    Vosk STT (realtime) + сохранение аудио последней финальной фразы (PCM int16 mono).
    Это нужно для Whisper-refine fallback: если NLU не уверена, отправляем аудио в Whisper.
    """

    def _drain_queue(self, max_items: int = 50) -> None:
        """
        Сбрасываем хвост аудио из очереди (после свитча модели или других событий).
        Ограничиваем количество, чтобы не зависнуть, если очередь очень большая.
        """
        n = 0
        while n < max_items:
            try:
                self._q.get_nowait()
                n += 1
            except Exception:
                break

    def __init__(
            self,
            model_path: str,
            samplerate: int = 16000,
            blocksize: int = 1024,
            device: Optional[Union[int, str]] = None,
            time_func: Callable[[], float] = time.time,
    ):
        self.model = Model(model_path)
        self.active_model_path = str(model_path)
        self.samplerate = int(samplerate)
        self.blocksize = int(blocksize)
        self.device = self._resolve_input_device(device)
        self._q: queue.Queue[bytes] = queue.Queue()
        self._paused = threading.Event()
        self._reset_event = threading.Event()
        self._time_func = time_func

        self._lifecycle_lock = threading.RLock()
        self._stream_generation = 0
        self._stream_active = False
        self._stream_phase = "not_started"
        self._last_stream_started_at: float | None = None
        self._last_stream_stopped_at: float | None = None
        self._last_audio_block_at: float | None = None
        self._audio_block_count = 0
        self._audio_bytes_total = 0
        self._last_processed_audio_block_at: float | None = None
        self._processed_audio_block_count = 0
        self._last_phrase_at: float | None = None
        self._phrase_count = 0
        self._last_callback_status_at: float | None = None
        self._last_callback_status = ""
        self._callback_status_count = 0
        self._last_error_at: float | None = None
        self._last_error = ""
        self._failure_count = 0
        self._consecutive_failures = 0

        # last utterance audio (PCM int16 mono @ samplerate)
        self.last_utterance_audio: bytes = b""
        self.last_utterance_text: str = ""
        self.last_utterance_ts: float = 0.0

        # hot swap state
        self._lock = threading.RLock()
        self._pending_model: Optional[Model] = None
        self._swap_event = threading.Event()
        self._pending_model_path: str = ""

        dev_info = self.get_current_input_device_info()
        if dev_info:
            print(
                f"[STT] input device: index={dev_info.get('index')} "
                f"name={dev_info.get('name')} sr={dev_info.get('default_samplerate')}"
            )
        else:
            print("[STT] input device: system default")

    def _now(self) -> float:
        return float(self._time_func())

    def _error_text(self, error: BaseException | str) -> str:
        if isinstance(error, BaseException):
            text = str(error).strip()
            return text or type(error).__name__

        return str(error or "").strip() or "Unknown STT failure"

    def _begin_stream(self) -> int:
        now = self._now()

        with self._lifecycle_lock:
            if self._stream_active or self._stream_phase == "starting":
                raise RuntimeError("STT stream is already running")

            self._stream_generation += 1
            generation = self._stream_generation
            self._stream_active = False
            self._stream_phase = "starting"
            self._last_stream_started_at = now

        # Новый stream не должен обработать аудио, оставшееся от старого поколения.
        self._drain_queue(max_items=500)
        return generation

    def _mark_stream_active(self, generation: int) -> None:
        with self._lifecycle_lock:
            if generation != self._stream_generation:
                return

            self._stream_active = True
            self._stream_phase = "active"
            self._consecutive_failures = 0

    def _mark_stream_stopped(self, generation: int) -> None:
        now = self._now()

        with self._lifecycle_lock:
            if generation != self._stream_generation:
                return

            if self._stream_phase == "failed":
                return

            self._stream_active = False
            self._stream_phase = "stopped"
            self._last_stream_stopped_at = now

    def _mark_stream_failed(self, generation: int, error: BaseException | str) -> None:
        now = self._now()

        with self._lifecycle_lock:
            if generation != self._stream_generation:
                return

            self._stream_active = False
            self._stream_phase = "failed"
            self._last_stream_stopped_at = now
            self._last_error_at = now
            self._last_error = self._error_text(error)
            self._failure_count += 1
            self._consecutive_failures += 1

    def _record_audio_block(
        self,
        generation: int,
        data: bytes,
        status: object,
    ) -> bool:
        now = self._now()

        with self._lifecycle_lock:
            if generation != self._stream_generation:
                return False

            if self._stream_phase not in {"starting", "active"}:
                return False

            self._last_audio_block_at = now
            self._audio_block_count += 1
            self._audio_bytes_total += len(data)

            if status:
                try:
                    status_text = str(status).strip()
                except Exception:
                    status_text = type(status).__name__

                self._last_callback_status_at = now
                self._last_callback_status = status_text or type(status).__name__
                self._callback_status_count += 1

        return True

    def _record_processed_audio_block(self, generation: int) -> bool:
        now = self._now()

        with self._lifecycle_lock:
            if generation != self._stream_generation:
                return False

            if self._stream_phase != "active":
                return False

            self._last_processed_audio_block_at = now
            self._processed_audio_block_count += 1

        return True

    def _record_phrase(
        self,
        generation: int,
        text: str,
        audio: bytes,
    ) -> bool:
        now = self._now()

        with self._lifecycle_lock:
            if generation != self._stream_generation:
                return False

            if self._stream_phase != "active":
                return False

            self.last_utterance_audio = bytes(audio)
            self.last_utterance_text = str(text)
            self.last_utterance_ts = now
            self._last_phrase_at = now
            self._phrase_count += 1

        return True

    def _make_stream_callback(self, generation: int):
        def _stream_callback(indata, frames, time_info, status):
            self._callback(indata, frames, time_info, status, _generation=generation)

        return _stream_callback

    def get_lifecycle_telemetry(self) -> STTLifecycleSnapshot:
        with self._lifecycle_lock:
            return STTLifecycleSnapshot(
                stream_started=self._stream_generation > 0,
                stream_active=self._stream_active,
                stream_generation=self._stream_generation,
                stream_phase=self._stream_phase,
                paused=self._paused.is_set(),
                last_stream_started_at=self._last_stream_started_at,
                last_stream_stopped_at=self._last_stream_stopped_at,
                last_audio_block_at=self._last_audio_block_at,
                audio_block_count=self._audio_block_count,
                audio_bytes_total=self._audio_bytes_total,
                last_processed_audio_block_at=self._last_processed_audio_block_at,
                processed_audio_block_count=self._processed_audio_block_count,
                queue_size=self._q.qsize(),
                last_phrase_at=self._last_phrase_at,
                phrase_count=self._phrase_count,
                last_callback_status_at=self._last_callback_status_at,
                last_callback_status=self._last_callback_status,
                callback_status_count=self._callback_status_count,
                last_error_at=self._last_error_at,
                last_error=self._last_error,
                failure_count=self._failure_count,
                consecutive_failures=self._consecutive_failures,
            )

    @staticmethod
    def list_input_devices() -> list[dict]:
        """
        Возвращает список доступных устройств ввода.
        """
        out: list[dict] = []
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if int(dev.get("max_input_channels", 0)) > 0:
                    item = dict(dev)
                    item["index"] = idx
                    out.append(item)
        except Exception:
            return []
        return out

    @classmethod
    def print_input_devices(cls) -> None:
        """
        Печатает список доступных устройств ввода для отладки.
        """
        items = cls.list_input_devices()
        if not items:
            print("[STT] no input devices found")
            return
        print("[STT] available input devices:")
        for dev in items:
            print(
                f"  [{dev['index']}] {dev.get('name')} "
                f"(in={dev.get('max_input_channels')}, sr={dev.get('default_samplerate')})"
            )

    def _resolve_input_device(self, device: Optional[Union[int, str]]) -> Optional[int]:
        """
        Разрешает input device:
        - None / пусто -> системный default
        - int / строка-число -> индекс устройства
        - str -> поиск по части имени
        """
        if device is None:
            return None

        if isinstance(device, str):
            device = device.strip()
            if not device:
                return None
            if device.isdigit():
                return int(device)

            needle = device.lower()
            for dev in self.list_input_devices():
                name = str(dev.get("name") or "").lower()
                if needle in name:
                    return int(dev["index"])
            print(f"[STT] input device '{device}' not found, using system default")
            return None

        return int(device)

    def get_current_input_device_info(self) -> Optional[dict]:
        try:
            if self.device is None:
                default_input, _ = sd.default.device
                if default_input is None or default_input < 0:
                    return None
                dev = dict(sd.query_devices(default_input))
                dev["index"] = int(default_input)
                return  dev
            dev = dict(sd.query_devices(self.device))
            dev["index"] = int(self.device)
            return dev
        except Exception:
            return None

    def pause(self) -> None:
        self._paused.set()
        self._drain_queue(max_items=200)
        # при паузе сбрасываем “накапливаемую” речь в listen_phrases()

    def resume(self) -> None:
        self._drain_queue(max_items=50)
        # попросим цикл распознавания пересоздать recognizer (сброс хвостов)
        self._reset_event.set()
        self._paused.clear()

    def _callback(
            self,
            indata,
            frames,
            time_info,
            status,
            *,
            _generation: int | None = None,
    ) -> None:
        _ = frames
        _ = time_info
        data = bytes(indata)

        if _generation is None:
            with self._lifecycle_lock:
                generation = self._stream_generation
        else:
            generation = int(_generation)

        accepted = self._record_audio_block(generation, data, status)

        if accepted and not self._paused.is_set():
            self._q.put(data)

    def load_model_async(
        self,
        model_path: str,
        on_swapped: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Грузит новую (обычно большую) модель в фоне и помечает её для переключения.
        Переключение происходит внутри listen_phrases(), когда поток уже работает.
        """
        def _worker():
            try:
                m = Model(model_path)  # тяжёлая операция
                with self._lock:
                    self._pending_model = m
                    self._pending_model_path = str(model_path)
                    self._swap_event.set()
                if on_swapped:
                    on_swapped()
            except Exception as e:
                # не падаем, просто остаёмся на старой модели
                print(f"[STT] failed to load model '{model_path}': {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _age_seconds(self, timestamp: float | None, now: float) -> float | None:
        if timestamp is None:
            return None

        return round(max(0.0, now - timestamp), 3)

    def get_diagnostics(self) -> dict:
        """
        Возвращает безопасную диагностическую информацию по STT.
        Не включает сами audio bytes.
        """
        dev_info = self.get_current_input_device_info()

        if dev_info:
            input_device = {
                "index": dev_info.get("index"),
                "name": str(dev_info.get("name") or ""),
                "default_samplerate": dev_info.get("default_samplerate"),
            }
        else:
            input_device = None

        audio_bytes = len(self.last_utterance_audio or b"")

        if self.samplerate > 0:
            duration_sec = audio_bytes / (2 * self.samplerate)
        else:
            duration_sec = 0.0

        now = self._now()
        lifecycle = self.get_lifecycle_telemetry()

        with self._lock:
            active_model_path = self.active_model_path
            pending_model = self._pending_model is not None
            pending_model_path = self._pending_model_path

        return {
            "engine": "vosk",
            "active_model_path": active_model_path,
            "pending_model": pending_model,
            "pending_model_path": pending_model_path,
            "samplerate": self.samplerate,
            "blocksize": self.blocksize,
            "device": self.device,
            "input_device": input_device,
            "last_utterance_text": self.last_utterance_text,
            "last_utterance_audio_bytes": audio_bytes,
            "last_utterance_duration_sec": round(duration_sec, 3),
            "last_utterance_age_sec": self._age_seconds(
                self.last_utterance_ts or None,
                now,
            ),
            "lifecycle": {
                "stream_started": lifecycle.stream_started,
                "stream_active": lifecycle.stream_active,
                "stream_generation": lifecycle.stream_generation,
                "stream_phase": lifecycle.stream_phase,
                "paused": lifecycle.paused,
                "last_stream_started_age_sec": self._age_seconds(
                    lifecycle.last_stream_started_at,
                    now,
                ),
                "last_stream_stopped_age_sec": self._age_seconds(
                    lifecycle.last_stream_stopped_at,
                    now,
                ),
                "last_audio_block_age_sec": self._age_seconds(
                    lifecycle.last_audio_block_at,
                    now,
                ),
                "audio_block_count": lifecycle.audio_block_count,
                "audio_bytes_total": lifecycle.audio_bytes_total,
                "last_processed_audio_block_age_sec": self._age_seconds(
                    lifecycle.last_processed_audio_block_at,
                    now,
                ),
                "processed_audio_block_count": lifecycle.processed_audio_block_count,
                "queue_size": lifecycle.queue_size,
                "last_phrase_age_sec": self._age_seconds(
                    lifecycle.last_phrase_at,
                    now,
                ),
                "phrase_count": lifecycle.phrase_count,
                "last_callback_status_age_sec": self._age_seconds(
                    lifecycle.last_callback_status_at,
                    now,
                ),
                "last_callback_status": lifecycle.last_callback_status,
                "callback_status_count": lifecycle.callback_status_count,
                "last_error_age_sec": self._age_seconds(
                    lifecycle.last_error_at,
                    now,
                ),
                "last_error": lifecycle.last_error,
                "failure_count": lifecycle.failure_count,
                "consecutive_failures": lifecycle.consecutive_failures,
            },
        }

    def listen_phrases(self) -> Iterator[str]:
        """
        Генератор фраз. Возвращает финальные фразы Vosk.
        """
        generation = self._begin_stream()
        failed = False

        try:
            rec = KaldiRecognizer(self.model, self.samplerate)
            rec.SetWords(False)
            utt_pcm = bytearray()

            with sd.RawInputStream(
                    samplerate=self.samplerate,
                    blocksize=self.blocksize,
                    dtype="int16",
                    channels=1,
                    callback=self._make_stream_callback(generation),
                    device=self.device,
            ):
                self._mark_stream_active(generation)

                while True:
                    if self._paused.is_set():
                        utt_pcm.clear()
                        time.sleep(0.02)
                        continue

                    if self._reset_event.is_set():
                        rec = KaldiRecognizer(self.model, self.samplerate)
                        rec.SetWords(False)
                        self._drain_queue(max_items=200)
                        self._reset_event.clear()
                        utt_pcm.clear()

                    data = self._q.get()

                    if data:
                        utt_pcm.extend(data)

                    if self._swap_event.is_set():
                        with self._lock:
                            if self._pending_model is not None:
                                self.model = self._pending_model
                                self.active_model_path = self._pending_model_path or self.active_model_path
                                self._pending_model = None
                                self._pending_model_path = ""
                                self._drain_queue(max_items=50)
                                rec = KaldiRecognizer(self.model, self.samplerate)
                                rec.SetWords(False)
                                self._drain_queue(max_items=100)
                                utt_pcm.clear()

                        self._swap_event.clear()
                        print("[STT] switched to new model")

                    is_final = rec.AcceptWaveform(data)
                    self._record_processed_audio_block(generation)

                    if is_final:
                        try:
                            res = json.loads(rec.Result())
                        except Exception:
                            res = {}

                        text = (res.get("text") or "").strip()

                        if text:
                            audio = bytes(utt_pcm)
                            utt_pcm.clear()

                            if self._record_phrase(generation, text, audio):
                                yield text
                        else:
                            utt_pcm.clear()
        except Exception as e:
            failed = True
            self._mark_stream_failed(generation, e)
            raise
        finally:
            if not failed:
                self._mark_stream_stopped(generation)