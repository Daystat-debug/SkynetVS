from __future__ import annotations

import ast
import asyncio
import json
import os
import tempfile

from pathlib import Path
from typing import Any
from unittest.mock import patch

import modules.tts_edge as tts_edge_module

from modules.core.config import Settings
from modules.tts_edge import EdgeTTS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

TTS_ENV_KEYS = (
    "TTS_VOICE",
    "TTS_RATE",
    "TTS_VOLUME",
    "TTS_PITCH",
)


class FakeCommunicate:
    last_kwargs: dict[str, Any] | None = None

    def __init__(self, **kwargs: Any):
        type(self).last_kwargs = dict(kwargs)

    async def save(self, out_path: str) -> None:
        Path(out_path).write_bytes(b"fake-mp3")


def _tts_settings(settings: Settings) -> dict[str, str]:
    return {
        "voice": settings.tts_voice,
        "rate": settings.tts_rate,
        "volume": settings.tts_volume,
        "pitch": settings.tts_pitch,
    }


def _edge_tts_keywords(tree: ast.AST) -> set[str]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "EdgeTTS":
            continue

        return {
            keyword.arg
            for keyword in node.keywords
            if keyword.arg is not None
        }

    return set()


def main() -> int:
    fail_count = 0
    case_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal fail_count, case_count

        case_count += 1
        ok = actual == expected

        print()
        print(f"=== {name} ===")
        print(json.dumps(
            {"actual": actual, "expected": expected, "ok": ok},
            ensure_ascii=False,
            indent=2,
            default=str,
        ))

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    with patch.dict(os.environ, {}, clear=True):
        settings = Settings.from_env()

    check(
        "DEFAULT TTS SETTINGS",
        _tts_settings(settings),
        {
            "voice": "ru-RU-SvetlanaNeural",
            "rate": "+0%",
            "volume": "+20%",
            "pitch": "+0Hz",
        },
    )

    with patch.dict(
        os.environ,
        {
            "TTS_VOICE": "ru-RU-DmitryNeural",
            "TTS_RATE": "+12%",
            "TTS_VOLUME": "+5%",
            "TTS_PITCH": "-2Hz",
        },
        clear=True,
    ):
        settings = Settings.from_env()

    check(
        "CUSTOM TTS SETTINGS",
        _tts_settings(settings),
        {
            "voice": "ru-RU-DmitryNeural",
            "rate": "+12%",
            "volume": "+5%",
            "pitch": "-2Hz",
        },
    )

    tts = EdgeTTS(
        voice=settings.tts_voice,
        rate=settings.tts_rate,
        volume=settings.tts_volume,
        pitch=settings.tts_pitch,
        ducking_enable=False,
    )

    check(
        "EDGE TTS RECEIVES SETTINGS",
        {
            "voice": tts.voice,
            "rate": tts.rate,
            "volume": tts.volume,
            "pitch": tts.pitch,
        },
        _tts_settings(settings),
    )

    FakeCommunicate.last_kwargs = None

    with patch.object(tts_edge_module.edge_tts, "Communicate", FakeCommunicate):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_path = str(Path(temp_dir) / "speech.mp3")
            asyncio.run(tts._synth_mp3("Проверка", out_path))

    check(
        "SYNTHESIS USES ALL TTS PARAMETERS",
        FakeCommunicate.last_kwargs,
        {
            "text": "Проверка",
            "voice": "ru-RU-DmitryNeural",
            "rate": "+12%",
            "volume": "+5%",
            "pitch": "-2Hz",
        },
    )

    main_source = MAIN_PATH.read_text(encoding="utf-8")
    main_tree = ast.parse(main_source, filename=str(MAIN_PATH))

    check(
        "MAIN PASSES TTS SETTINGS",
        _edge_tts_keywords(main_tree),
        {"voice", "rate", "volume", "pitch"},
    )

    env_example = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")

    check(
        "ENV EXAMPLE CONTAINS TTS SETTINGS",
        {key: f"{key}=" in env_example for key in TTS_ENV_KEYS},
        {key: True for key in TTS_ENV_KEYS},
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps(
        {"case_count": case_count, "fail_count": fail_count},
        ensure_ascii=False,
        indent=2,
    ))

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
