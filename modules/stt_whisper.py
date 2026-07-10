from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKER_PATH = PROJECT_ROOT / "tools" / "whisper_refine_worker.py"


def _env_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


def _shorten(text: str, *, limit: int = 1200) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


class WhisperRefiner:
    """
    Offline Whisper refine fallback.

    По умолчанию работает через subprocess, чтобы native crash в
    faster-whisper / ctranslate2 не убивал основной процесс SkynetVS.

    Env:
      WHISPER_BACKEND=subprocess | inprocess
      WHISPER_DEVICE=cpu | cuda
      WHISPER_COMPUTE_TYPE=int8 | float16 | float32
      WHISPER_TIMEOUT_SEC=90
      WHISPER_BEAM=3
    """

    def __init__(
        self,
        model_name: str = "small",
        language: str = "ru",
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        backend: Optional[str] = None,
        timeout_sec: Optional[float] = None,
        worker_cmd: Optional[list[str]] = None,
    ):
        self.model_name = model_name
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.backend = (backend or os.getenv("WHISPER_BACKEND", "subprocess")).strip().lower()
        self.timeout_sec = (
            float(timeout_sec)
            if timeout_sec is not None
            else _env_float("WHISPER_TIMEOUT_SEC", "90")
        )
        self.worker_cmd = list(worker_cmd) if worker_cmd else None
        self._model = None

    def _effective_device(self) -> str:
        return (self.device or os.getenv("WHISPER_DEVICE") or "cpu").strip() or "cpu"

    def _effective_compute_type(self, device: str) -> str:
        configured = self.compute_type or os.getenv("WHISPER_COMPUTE_TYPE")
        if configured:
            return configured.strip()

        if device.lower() == "cpu":
            return "int8"

        return "float16"

    def _effective_worker_cmd(self) -> list[str]:
        if self.worker_cmd:
            return list(self.worker_cmd)

        return [
            sys.executable,
            str(DEFAULT_WORKER_PATH),
        ]

    def _load_inprocess(self):
        if self._model is not None:
            return self._model

        from faster_whisper import WhisperModel  # lazy import

        device = self._effective_device()
        compute_type = self._effective_compute_type(device)

        self._model = WhisperModel(
            self.model_name,
            device=device,
            compute_type=compute_type,
        )

        return self._model

    def _refine_pcm_inprocess(self, pcm_i16_mono: bytes, *, samplerate: int) -> str:
        import numpy as np

        if not pcm_i16_mono:
            return ""

        audio = np.frombuffer(pcm_i16_mono, dtype=np.int16).astype(np.float32) / 32768.0
        if audio.size == 0:
            return ""

        model = self._load_inprocess()

        segments, _info = model.transcribe(
            audio,
            language=self.language,
            vad_filter=True,
            beam_size=int(os.getenv("WHISPER_BEAM", "3")),
        )

        parts = []
        for seg in segments:
            text = (seg.text or "").strip()
            if text:
                parts.append(text)

        return " ".join(parts).strip()

    def _parse_worker_stdout(self, stdout: str) -> dict:
        lines = [
            line.strip()
            for line in str(stdout or "").splitlines()
            if line.strip()
        ]

        json_lines = [
            line
            for line in lines
            if line.startswith("{") and line.endswith("}")
        ]

        if not json_lines:
            raise RuntimeError(
                "whisper_worker_no_json_output: "
                f"stdout={_shorten(stdout)!r}"
            )

        try:
            data = json.loads(json_lines[-1])
        except Exception as e:
            raise RuntimeError(
                "whisper_worker_bad_json: "
                f"{type(e).__name__}: {e}; stdout={_shorten(stdout)!r}"
            ) from e

        if not isinstance(data, dict):
            raise RuntimeError(f"whisper_worker_bad_payload: {data!r}")

        return data

    def _refine_pcm_subprocess(self, pcm_i16_mono: bytes, *, samplerate: int) -> str:
        if not pcm_i16_mono:
            return ""

        device = self._effective_device()
        compute_type = self._effective_compute_type(device)

        payload = {
            "pcm_b64": base64.b64encode(pcm_i16_mono).decode("ascii"),
            "samplerate": int(samplerate),
            "model_name": self.model_name,
            "language": self.language,
            "device": device,
            "compute_type": compute_type,
            "beam_size": int(os.getenv("WHISPER_BEAM", "3")),
        }

        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        cmd = self._effective_worker_cmd()

        try:
            completed = subprocess.run(
                cmd,
                input=json.dumps(payload, ensure_ascii=False),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(1.0, float(self.timeout_sec)),
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                "whisper_worker_timeout: "
                f"timeout_sec={self.timeout_sec}, cmd={cmd!r}"
            ) from e

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""

        data = {}
        try:
            data = self._parse_worker_stdout(stdout)
        except Exception:
            if completed.returncode != 0:
                raise RuntimeError(
                    "whisper_worker_crashed: "
                    f"returncode={completed.returncode}, "
                    f"stderr={_shorten(stderr)!r}, "
                    f"stdout={_shorten(stdout)!r}"
                )
            raise

        if completed.returncode != 0:
            raise RuntimeError(
                "whisper_worker_failed: "
                f"returncode={completed.returncode}, "
                f"payload={data!r}, "
                f"stderr={_shorten(stderr)!r}"
            )

        if not data.get("ok"):
            raise RuntimeError(
                "whisper_worker_error: "
                f"payload={data!r}, stderr={_shorten(stderr)!r}"
            )

        return str(data.get("text") or "").strip()

    def refine_pcm(self, pcm_i16_mono: bytes, samplerate: int) -> str:
        if self.backend == "inprocess":
            return self._refine_pcm_inprocess(pcm_i16_mono, samplerate=samplerate)

        return self._refine_pcm_subprocess(pcm_i16_mono, samplerate=samplerate)