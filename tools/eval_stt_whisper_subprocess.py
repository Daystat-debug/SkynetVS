from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

from modules.stt_whisper import WhisperRefiner


def _write_fake_worker(tmp_dir: Path) -> Path:
    path = tmp_dir / "fake_whisper_worker.py"

    path.write_text(
        dedent(
            r'''
            from __future__ import annotations

            import base64
            import json
            import sys

            payload = json.loads(sys.stdin.read() or "{}")
            model_name = str(payload.get("model_name") or "")

            if model_name == "crash":
                sys.exit(7)

            if model_name == "error":
                print(json.dumps({"ok": False, "error": "fake worker error"}, ensure_ascii=False))
                sys.exit(1)

            pcm_b64 = str(payload.get("pcm_b64") or "")
            pcm = base64.b64decode(pcm_b64) if pcm_b64 else b""

            print(json.dumps({
                "ok": True,
                "text": "открой openai",
                "pcm_bytes": len(pcm),
                "samplerate": payload.get("samplerate"),
                "device": payload.get("device"),
                "compute_type": payload.get("compute_type"),
            }, ensure_ascii=False))
            '''
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    return path


def _run_case(name: str, actual: Dict[str, Any], expected: Dict[str, Any]) -> bool:
    errors: list[str] = []

    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            errors.append(
                f"{key}: expected={expected_value!r}, actual={actual.get(key)!r}"
            )

    print()
    print(f"--- {name} ---")
    print(
        json.dumps(
            {
                "expected": expected,
                "actual": actual,
                "errors": errors,
                "ok": not errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[OK] whisper subprocess case")

    return not errors


def main() -> int:
    fail_count = 0

    print("=== STT WHISPER SUBPROCESS EVAL REPORT ===")

    with tempfile.TemporaryDirectory() as tmp:
        worker = _write_fake_worker(Path(tmp))
        worker_cmd = [sys.executable, str(worker)]

        refiner = WhisperRefiner(
            model_name="ok",
            language="ru",
            backend="subprocess",
            device="cpu",
            compute_type="int8",
            timeout_sec=5,
            worker_cmd=worker_cmd,
        )

        try:
            text = refiner.refine_pcm(b"12345678", samplerate=16000)
            actual = {
                "text": text,
                "raised": False,
            }
        except Exception as e:
            actual = {
                "text": "",
                "raised": True,
                "error": f"{type(e).__name__}: {e}",
            }

        if not _run_case(
            "success worker",
            actual,
            {
                "text": "открой openai",
                "raised": False,
            },
        ):
            fail_count += 1

        refiner_error = WhisperRefiner(
            model_name="error",
            language="ru",
            backend="subprocess",
            device="cpu",
            compute_type="int8",
            timeout_sec=5,
            worker_cmd=worker_cmd,
        )

        try:
            _ = refiner_error.refine_pcm(b"12345678", samplerate=16000)
            actual = {
                "raised": False,
            }
        except RuntimeError as e:
            actual = {
                "raised": True,
                "contains_worker_failed": "whisper_worker_failed" in str(e),
            }

        if not _run_case(
            "worker error",
            actual,
            {
                "raised": True,
                "contains_worker_failed": True,
            },
        ):
            fail_count += 1

        refiner_crash = WhisperRefiner(
            model_name="crash",
            language="ru",
            backend="subprocess",
            device="cpu",
            compute_type="int8",
            timeout_sec=5,
            worker_cmd=worker_cmd,
        )

        try:
            _ = refiner_crash.refine_pcm(b"12345678", samplerate=16000)
            actual = {
                "raised": False,
            }
        except RuntimeError as e:
            actual = {
                "raised": True,
                "contains_worker_crashed": "whisper_worker_crashed" in str(e),
            }

        if not _run_case(
            "worker crash",
            actual,
            {
                "raised": True,
                "contains_worker_crashed": True,
            },
        ):
            fail_count += 1

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())