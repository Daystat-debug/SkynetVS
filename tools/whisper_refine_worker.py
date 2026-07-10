from __future__ import annotations

import base64
import json
import sys
import warnings
from typing import Any, Dict


def _emit(payload: Dict[str, Any], *, exit_code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    return exit_code


def _read_payload() -> Dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}

    data = json.loads(raw)
    if not isinstance(data, dict):
        return {}

    return data


def _main() -> int:
    warnings.filterwarnings(
        "ignore",
        message=r"pkg_resources is deprecated.*",
        category=UserWarning,
    )

    try:
        import numpy as np
        from faster_whisper import WhisperModel
    except Exception as e:
        return _emit(
            {
                "ok": False,
                "error": f"import_failed: {type(e).__name__}: {e}",
            },
            exit_code=1,
        )

    try:
        payload = _read_payload()

        pcm_b64 = str(payload.get("pcm_b64") or "")
        if not pcm_b64:
            return _emit(
                {
                    "ok": True,
                    "text": "",
                    "reason": "empty_audio",
                },
                exit_code=0,
            )

        pcm = base64.b64decode(pcm_b64)
        samplerate = int(payload.get("samplerate") or 16000)
        model_name = str(payload.get("model_name") or "small")
        language = str(payload.get("language") or "ru")
        device = str(payload.get("device") or "cpu")
        compute_type = str(payload.get("compute_type") or ("int8" if device == "cpu" else "float16"))
        beam_size = int(payload.get("beam_size") or 3)

        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if audio.size == 0:
            return _emit(
                {
                    "ok": True,
                    "text": "",
                    "reason": "empty_audio_array",
                },
                exit_code=0,
            )

        model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )

        segments, info = model.transcribe(
            audio,
            language=language,
            vad_filter=True,
            beam_size=beam_size,
        )

        parts: list[str] = []
        segment_count = 0

        for seg in segments:
            segment_count += 1
            text = (seg.text or "").strip()
            if text:
                parts.append(text)

        return _emit(
            {
                "ok": True,
                "text": " ".join(parts).strip(),
                "model_name": model_name,
                "language": language,
                "device": device,
                "compute_type": compute_type,
                "beam_size": beam_size,
                "segment_count": segment_count,
                "duration": getattr(info, "duration", None),
            },
            exit_code=0,
        )

    except Exception as e:
        return _emit(
            {
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
            },
            exit_code=1,
        )


if __name__ == "__main__":
    raise SystemExit(_main())