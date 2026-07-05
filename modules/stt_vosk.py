# modules/stt_vosk.py
from __future__ import annotations

import json
import os
import queue
import threading
import time
from typing import Iterator, Optional, Union

import sounddevice as sd
from vosk import Model, KaldiRecognizer


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
    ):
        self.model = Model(model_path)
        self.samplerate = int(samplerate)
        self.blocksize = int(blocksize)
        self.device = self._resolve_input_device(device)
        self._q: queue.Queue[bytes] = queue.Queue()
        self._paused = threading.Event()
        self._reset_event = threading.Event()

        # last utterance audio (PCM int16 mono @ samplerate)
        self.last_utterance_audio: bytes = b""
        self.last_utterance_text: str = ""
        self.last_utterance_ts: float = 0.0

        # hot swap state
        self._lock = threading.RLock()
        self._pending_model: Optional[Model] = None
        self._swap_event = threading.Event()

        dev_info = self.get_current_input_device_info()
        if dev_info:
            print(
                f"[STT] input device: index={dev_info.get('index')} "
                f"name={dev_info.get('name')} sr={dev_info.get('default_samplerate')}"
            )
        else:
            print("[STT] input device: system default")

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
                default_input, _ =sd.default.device
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

    def _callback(self, indata, frames, time, status):
        if status:
            # можно логировать статус, но пока молчим
            pass
        if not self._paused.is_set():
            self._q.put(bytes(indata))

    def load_model_async(self, model_path: str, on_swapped: Optional[callable] = None) -> None:
        """
        Грузит новую (обычно большую) модель в фоне и помечает её для переключения.
        Переключение происходит внутри listen_phrases(), когда поток уже работает.
        """
        def _worker():
            try:
                m = Model(model_path)  # тяжёлая операция
                with self._lock:
                    self._pending_model = m
                    self._swap_event.set()
                if on_swapped:
                    on_swapped()
            except Exception as e:
                # не падаем, просто остаёмся на старой модели
                print(f"[STT] failed to load model '{model_path}': {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def listen_phrases(self) -> Iterator[str]:
        """
        Генератор фраз. Возвращает финальные фразы Vosk.
        """
        rec = KaldiRecognizer(self.model, self.samplerate)
        rec.SetWords(False)

        # накапливаем PCM текущей фразы, чтобы потом (на финале) отдать в Whisper
        utt_pcm = bytearray()

        with sd.RawInputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=1,
            callback=self._callback,
            device=self.device,
        ):
            while True:
                if self._paused.is_set():
                    # сбрасываем накопленное, чтобы TTS/пауза не “примешивались”
                    utt_pcm.clear()
                    time.sleep(0.02)
                    continue

                # жёсткий reset распознавателя после TTS
                if self._reset_event.is_set():
                    rec = KaldiRecognizer(self.model, self.samplerate)
                    rec.SetWords(False)
                    self._drain_queue(max_items=200)
                    self._reset_event.clear()
                    utt_pcm.clear()

                data = self._q.get()
                # накапливаем аудио (PCM int16 mono)
                if data:
                     utt_pcm.extend(data)

                # Если в фоне загрузилась новая модель — переключаемся
                if self._swap_event.is_set():
                    with self._lock:
                        if self._pending_model is not None:
                            self.model = self._pending_model
                            self._pending_model = None
                            self._drain_queue(max_items=50)
                            # новый распознаватель на новой модели
                            rec = KaldiRecognizer(self.model, self.samplerate)
                            rec.SetWords(False)
                            self._drain_queue(max_items=100)
                            utt_pcm.clear()
                            # сброс очереди шумов/хвостов не обязателен, но иногда полезно:
                            # while not self._q.empty(): self._q.get_nowait()
                    self._swap_event.clear()
                    print("[STT] switched to new model")

                if rec.AcceptWaveform(data):
                    try:
                        res = json.loads(rec.Result())
                    except Exception:
                        res = {}
                    text = (res.get("text") or "").strip()
                    if text:
                        # сохраняем аудио последней фразы (для Whisper-refine)
                        self.last_utterance_audio = bytes(utt_pcm)
                        self.last_utterance_text = text
                        self.last_utterance_ts = time.time()
                        utt_pcm.clear()
                        yield text
                    else:
                        # даже если пусто — сбрасываем накопление, чтобы не копить бесконечно
                        utt_pcm.clear()