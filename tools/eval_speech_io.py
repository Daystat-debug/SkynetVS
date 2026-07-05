from __future__ import annotations

import json
from typing import List

from dotenv import load_dotenv

load_dotenv()

from modules.speech_io import say, say_interruptible


class FakeSTT:
    def __init__(self) -> None:
        self.events: List[str] = []

    def pause(self) -> None:
        self.events.append("stt.pause")

    def resume(self) -> None:
        self.events.append("stt.resume")


class FakeTTS:
    def __init__(self, *, fail_blocking: bool = False) -> None:
        self.events: List[str] = []
        self.fail_blocking = fail_blocking

    def speak_blocking(self, text: str) -> None:
        self.events.append(f"tts.speak_blocking:{text}")

        if self.fail_blocking:
            raise RuntimeError("fake tts failure")

    def speak_interruptible(self, text: str) -> None:
        self.events.append(f"tts.speak_interruptible:{text}")


def _print_case(name: str, expected: List[str], actual: List[str]) -> bool:
    ok = actual == expected

    print()
    print(f"--- {name} ---")
    print(
        json.dumps(
            {
                "expected": expected,
                "actual": actual,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if ok:
        print("[OK] speech io case")
    else:
        print("[FAIL] speech io case")

    return ok


def main() -> int:
    fail_count = 0

    print("=== SPEECH IO EVAL REPORT ===")

    # 1. mute_stt=True должен pause -> speak -> resume
    stt = FakeSTT()
    tts = FakeTTS()

    say(stt, tts, "Привет", mute_stt=True)

    actual = [*stt.events[:1], *tts.events, *stt.events[1:]]
    expected = [
        "stt.pause",
        "tts.speak_blocking:Привет",
        "stt.resume",
    ]

    if not _print_case("blocking speech with muted STT", expected, actual):
        fail_count += 1

    # 2. mute_stt=False не должен трогать STT
    stt = FakeSTT()
    tts = FakeTTS()

    say(stt, tts, "Слушаю", mute_stt=False)

    actual = [*stt.events, *tts.events]
    expected = [
        "tts.speak_blocking:Слушаю",
    ]

    if not _print_case("blocking speech without muted STT", expected, actual):
        fail_count += 1

    # 3. При ошибке TTS всё равно должен быть resume
    stt = FakeSTT()
    tts = FakeTTS(fail_blocking=True)

    raised = False
    try:
        say(stt, tts, "Ошибка", mute_stt=True)
    except RuntimeError:
        raised = True

    actual = [*stt.events[:1], *tts.events, *stt.events[1:]]
    expected = [
        "stt.pause",
        "tts.speak_blocking:Ошибка",
        "stt.resume",
    ]

    ok = raised and actual == expected

    print()
    print("--- blocking speech resumes STT after failure ---")
    print(
        json.dumps(
            {
                "raised": raised,
                "expected": expected,
                "actual": actual,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if ok:
        print("[OK] speech io failure case")
    else:
        fail_count += 1
        print("[FAIL] speech io failure case")

    # 4. interruptible speech вызывает speak_interruptible
    tts = FakeTTS()

    say_interruptible(tts, "Длинный ответ")

    actual = tts.events
    expected = [
        "tts.speak_interruptible:Длинный ответ",
    ]

    if not _print_case("interruptible speech", expected, actual):
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

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())