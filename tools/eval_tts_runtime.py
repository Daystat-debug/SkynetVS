from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile

from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.tts_edge import EdgeTTS, TTSPlaybackError, TTSSynthesisError


class FakeDucker:
    def __init__(self) -> None:
        self.events: list[str] = []

    def duck(self) -> None:
        self.events.append("duck")

    def restore(self) -> None:
        self.events.append("restore")


class FakeProcess:
    def __init__(
        self,
        *,
        poll_result: int | None = None,
        terminate_error: Exception | None = None,
    ):
        self.poll_result = poll_result
        self.terminate_error = terminate_error
        self.terminated = False
        self.killed = False
        self.wait_calls: list[float | None] = []

    def poll(self) -> int | None:
        return self.poll_result

    def terminate(self) -> None:
        self.terminated = True

        if self.terminate_error is not None:
            raise self.terminate_error

        self.poll_result = 0

    def kill(self) -> None:
        self.killed = True
        self.poll_result = -9

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        return int(self.poll_result or 0)


def _temp_audio() -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as file:
        file.write(b"audio")
        return file.name


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count

        case_count += 1
        ok = actual == expected

        print()
        print(f"=== {name} ===")
        print(json.dumps(
            {
                "actual": actual,
                "expected": expected,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ))

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    tts = EdgeTTS(ducking_enable=False)
    tts._ducker = FakeDucker()

    path_holder: list[str] = []
    events: list[str] = []

    def synth_ok(text: str, out_path: str) -> None:
        events.append(f"synth:{text}")
        path_holder.append(out_path)
        Path(out_path).write_bytes(b"audio")

    def play_ok(out_path: str) -> None:
        events.append(f"play_exists:{Path(out_path).exists()}")

    tts._run_synthesis = synth_ok
    tts._play_mp3_blocking_windows = play_ok

    with patch(
        "modules.tts_edge.platform.system",
        return_value="Windows",
    ):
        tts.speak_blocking("Проверка")

    check(
        "BLOCKING SUCCESS CLEANS AND RESTORES",
        {
            "events": events,
            "ducker": tts._ducker.events,
            "file_exists": Path(path_holder[0]).exists(),
        },
        {
            "events": [
                "synth:Проверка",
                "play_exists:True",
            ],
            "ducker": [
                "restore",
                "duck",
                "restore",
            ],
            "file_exists": False,
        },
    )

    tts = EdgeTTS(ducking_enable=False)
    tts._ducker = FakeDucker()

    synth_error_path: list[str] = []

    def synth_fail(text: str, out_path: str) -> None:
        _ = text
        synth_error_path.append(out_path)
        raise TTSSynthesisError("fake synth error")

    tts._run_synthesis = synth_fail
    raised = False

    try:
        with patch(
            "modules.tts_edge.platform.system",
            return_value="Windows",
        ):
            tts.speak_blocking("Ошибка")
    except TTSSynthesisError:
        raised = True

    check(
        "SYNTHESIS FAILURE CLEANS TEMP FILE",
        {
            "raised": raised,
            "file_exists": Path(synth_error_path[0]).exists(),
            "ducker": tts._ducker.events,
        },
        {
            "raised": True,
            "file_exists": False,
            "ducker": [
                "restore",
            ],
        },
    )

    tts = EdgeTTS(ducking_enable=False)
    tts._ducker = FakeDucker()

    playback_path: list[str] = []

    def synth_for_play(text: str, out_path: str) -> None:
        _ = text
        playback_path.append(out_path)
        Path(out_path).write_bytes(b"audio")

    def play_fail(out_path: str) -> None:
        _ = out_path
        raise TTSPlaybackError("fake play error")

    tts._run_synthesis = synth_for_play
    tts._play_mp3_blocking_windows = play_fail
    raised = False

    try:
        with patch(
            "modules.tts_edge.platform.system",
            return_value="Windows",
        ):
            tts.speak_blocking("Ошибка")
    except TTSPlaybackError:
        raised = True

    check(
        "PLAYBACK FAILURE RESTORES AND CLEANS",
        {
            "raised": raised,
            "file_exists": Path(playback_path[0]).exists(),
            "ducker": tts._ducker.events,
        },
        {
            "raised": True,
            "file_exists": False,
            "ducker": [
                "restore",
                "duck",
                "restore",
            ],
        },
    )

    tts = EdgeTTS(ducking_enable=False)
    tts._ducker = FakeDucker()

    spawn_path: list[str] = []

    def synth_for_spawn(text: str, out_path: str) -> None:
        _ = text
        spawn_path.append(out_path)
        Path(out_path).write_bytes(b"audio")

    def spawn_fail(out_path: str) -> Any:
        _ = out_path
        raise TTSPlaybackError("fake spawn error")

    tts._run_synthesis = synth_for_spawn
    tts._spawn_mp3_player_windows = spawn_fail
    raised = False

    try:
        with patch(
            "modules.tts_edge.platform.system",
            return_value="Windows",
        ):
            tts.speak_interruptible("Ошибка")
    except TTSPlaybackError:
        raised = True

    check(
        "INTERRUPTIBLE SPAWN FAILURE RESTORES AND CLEANS",
        {
            "raised": raised,
            "file_exists": Path(spawn_path[0]).exists(),
            "ducker": tts._ducker.events,
        },
        {
            "raised": True,
            "file_exists": False,
            "ducker": [
                "restore",
                "duck",
                "restore",
            ],
        },
    )

    tts = EdgeTTS(ducking_enable=False)
    tts._ducker = FakeDucker()

    stop_path = _temp_audio()
    stop_proc = FakeProcess()

    tts._player_proc = stop_proc
    tts._player_temp_path = stop_path

    tts.stop()

    check(
        "STOP TERMINATES AND CLEANS",
        {
            "terminated": stop_proc.terminated,
            "killed": stop_proc.killed,
            "wait_calls": stop_proc.wait_calls,
            "file_exists": Path(stop_path).exists(),
            "proc": tts._player_proc,
            "path": tts._player_temp_path,
            "ducker": tts._ducker.events,
        },
        {
            "terminated": True,
            "killed": False,
            "wait_calls": [
                0.5,
            ],
            "file_exists": False,
            "proc": None,
            "path": None,
            "ducker": [
                "restore",
            ],
        },
    )

    tts = EdgeTTS(ducking_enable=False)
    tts._ducker = FakeDucker()

    stale_path = _temp_audio()
    current_path = _temp_audio()

    stale_proc = FakeProcess(poll_result=0)
    current_proc = FakeProcess()

    tts._player_proc = current_proc
    tts._player_temp_path = current_path

    tts._watch_interruptible_playback(
        stale_proc,
        stale_path,
    )

    check(
        "STALE WATCHER DOES NOT RESTORE NEW PLAYBACK",
        {
            "current_proc": tts._player_proc is current_proc,
            "current_path": tts._player_temp_path == current_path,
            "stale_exists": Path(stale_path).exists(),
            "current_exists": Path(current_path).exists(),
            "ducker": tts._ducker.events,
        },
        {
            "current_proc": True,
            "current_path": True,
            "stale_exists": False,
            "current_exists": True,
            "ducker": [],
        },
    )

    os.remove(current_path)

    tts = EdgeTTS(ducking_enable=False)
    tts._ducker = FakeDucker()

    complete_path = _temp_audio()
    complete_proc = FakeProcess(poll_result=0)

    tts._player_proc = complete_proc
    tts._player_temp_path = complete_path

    speaking = tts.is_speaking()

    check(
        "IS SPEAKING FINALIZES COMPLETED PROCESS",
        {
            "speaking": speaking,
            "file_exists": Path(complete_path).exists(),
            "proc": tts._player_proc,
            "path": tts._player_temp_path,
            "ducker": tts._ducker.events,
        },
        {
            "speaking": False,
            "file_exists": False,
            "proc": None,
            "path": None,
            "ducker": [
                "restore",
            ],
        },
    )

    tts = EdgeTTS(ducking_enable=False)

    nonzero_raised = False
    timeout_raised = False

    with patch(
        "modules.tts_edge.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=7,
        ),
    ):
        try:
            tts._play_mp3_blocking_windows("fake.mp3")
        except TTSPlaybackError:
            nonzero_raised = True

    with patch(
        "modules.tts_edge.subprocess.run",
        side_effect=subprocess.TimeoutExpired(
            cmd=["powershell"],
            timeout=120,
        ),
    ):
        try:
            tts._play_mp3_blocking_windows("fake.mp3")
        except TTSPlaybackError:
            timeout_raised = True

    check(
        "PLAYER FAILURES RAISE",
        {
            "nonzero": nonzero_raised,
            "timeout": timeout_raised,
        },
        {
            "nonzero": True,
            "timeout": True,
        },
    )

    tts = EdgeTTS(ducking_enable=False)

    runtime_error_calls = 0

    async def synth_runtime_error(
        text: str,
        out_path: str,
    ) -> None:
        nonlocal runtime_error_calls

        _ = text
        _ = out_path

        runtime_error_calls += 1

        raise RuntimeError("fake network error")

    tts._synth_mp3 = synth_runtime_error

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp3",
    ) as file:
        runtime_error_path = file.name

    raised = False

    try:
        try:
            tts._run_synthesis(
                "Ошибка",
                runtime_error_path,
            )
        except TTSSynthesisError:
            raised = True
    finally:
        if Path(runtime_error_path).exists():
            os.remove(runtime_error_path)

    check(
        "SYNTHESIS RUNTIME ERROR IS NOT RETRIED",
        {
            "raised": raised,
            "calls": runtime_error_calls,
        },
        {
            "raised": True,
            "calls": 1,
        },
    )

    tts = EdgeTTS(ducking_enable=False)

    loop_calls = 0

    async def synth_in_loop(
        text: str,
        out_path: str,
    ) -> None:
        nonlocal loop_calls

        _ = text
        loop_calls += 1

        Path(out_path).write_bytes(b"audio")

    tts._synth_mp3 = synth_in_loop

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".mp3",
    ) as file:
        loop_path = file.name

    async def run_inside_loop() -> None:
        tts._run_synthesis(
            "Проверка",
            loop_path,
        )

    try:
        asyncio.run(
            run_inside_loop()
        )
        loop_size = Path(loop_path).stat().st_size
    finally:
        if Path(loop_path).exists():
            os.remove(loop_path)

    check(
        "SYNTHESIS WORKS WITH RUNNING EVENT LOOP",
        {
            "calls": loop_calls,
            "size": loop_size,
        },
        {
            "calls": 1,
            "size": 5,
        },
    )

    script = EdgeTTS(
        ducking_enable=False,
    )._build_player_script(
        "fake.mp3"
    )

    check(
        "PLAYER SCRIPT HAS GUARDS",
        {
            "deadline": "AddSeconds(10)" in script,
            "timeout_error": "Media duration timeout" in script,
            "close": "$player.Close()" in script,
        },
        {
            "deadline": True,
            "timeout_error": True,
            "close": True,
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps(
        {
            "case_count": case_count,
            "fail_count": fail_count,
        },
        ensure_ascii=False,
        indent=2,
    ))

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())