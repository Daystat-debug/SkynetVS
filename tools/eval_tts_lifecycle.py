from __future__ import annotations

import json
import threading

from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.core.operation_telemetry import OUTCOME_FAILURE, OUTCOME_SUCCESS
from modules.tts_edge import EdgeTTS, TTSPlaybackError


class FakeClock:
    def __init__(self, epoch: float = 1000.0, monotonic: float = 50.0):
        self.epoch = float(epoch)
        self.monotonic = float(monotonic)

    def time(self) -> float:
        return self.epoch

    def monotonic_time(self) -> float:
        return self.monotonic

    def advance(self, seconds: float) -> None:
        self.epoch += float(seconds)
        self.monotonic += float(seconds)


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
        wait_error: Exception | None = None,
        terminate_error: Exception | None = None,
        kill_error: Exception | None = None,
    ):
        self.poll_result = poll_result
        self.wait_error = wait_error
        self.terminate_error = terminate_error
        self.kill_error = kill_error
        self.terminated = False
        self.killed = False
        self.wait_calls: list[float | None] = []

    def poll(self) -> int | None:
        return self.poll_result

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)

        if timeout is None and self.wait_error is not None:
            raise self.wait_error

        return int(self.poll_result or 0)

    def terminate(self) -> None:
        self.terminated = True

        if self.terminate_error is not None:
            raise self.terminate_error

        self.poll_result = 0

    def kill(self) -> None:
        self.killed = True

        if self.kill_error is not None:
            raise self.kill_error

        self.poll_result = -9


class FakeThread:
    instances: list["FakeThread"] = []

    def __init__(
        self,
        *,
        target,
        args=(),
        name: str | None = None,
        daemon: bool | None = None,
    ):
        self.target = target
        self.args = args
        self.name = name
        self.daemon = daemon
        self.started = False
        self.__class__.instances.append(self)

    def start(self) -> None:
        self.started = True

    def run(self) -> None:
        self.target(*self.args)


class ProcessFactory:
    def __init__(self, *processes: FakeProcess):
        self._processes = list(processes)
        self.calls: list[str] = []

    def __call__(self, path: str) -> FakeProcess:
        self.calls.append(path)

        if not self._processes:
            raise RuntimeError("No fake process configured")

        return self._processes.pop(0)


def _new_tts(clock: FakeClock) -> EdgeTTS:
    tts = EdgeTTS(
        ducking_enable=False,
        time_func=clock.time,
        monotonic_func=clock.monotonic_time,
    )
    tts._ducker = FakeDucker()
    return tts


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

    clock = FakeClock()
    tts = _new_tts(clock)
    lifecycle = tts.get_lifecycle_telemetry()

    check(
        "INITIAL LIFECYCLE",
        {
            "has_attempt": lifecycle.operation.has_attempt,
            "active": lifecycle.active,
            "active_operation_id": lifecycle.active_operation_id,
            "active_mode": lifecycle.active_mode,
            "active_phase": lifecycle.active_phase,
            "cancellation_count": lifecycle.cancellation_count,
            "last_cancel_reason": lifecycle.last_cancel_reason,
        },
        {
            "has_attempt": False,
            "active": False,
            "active_operation_id": None,
            "active_mode": "",
            "active_phase": "",
            "cancellation_count": 0,
            "last_cancel_reason": "",
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)

    def blocking_synth(text: str, out_path: str) -> None:
        _ = text
        Path(out_path).write_bytes(b"audio")
        clock.advance(0.1)

    def blocking_play(out_path: str) -> None:
        _ = out_path
        clock.advance(0.2)

    tts._run_synthesis = blocking_synth
    tts._play_mp3_blocking_windows = blocking_play

    with patch("modules.tts_edge.platform.system", return_value="Windows"):
        tts.speak_blocking("Проверка")

    snapshot = tts.get_operation_telemetry()

    check(
        "BLOCKING SUCCESS RECORDED",
        {
            "outcome": snapshot.last_outcome,
            "duration_ms": snapshot.last_duration_ms,
            "last_error": snapshot.last_error,
            "failures": snapshot.consecutive_failures,
        },
        {
            "outcome": OUTCOME_SUCCESS,
            "duration_ms": 300,
            "last_error": "",
            "failures": 0,
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)
    play_started = threading.Event()
    allow_finish = threading.Event()
    worker_errors: list[str] = []

    def blocking_wait_play(out_path: str) -> None:
        _ = out_path
        play_started.set()

        if not allow_finish.wait(timeout=2.0):
            raise RuntimeError("blocking test timeout")

        clock.advance(0.2)

    def run_blocking_speech() -> None:
        try:
            with patch("modules.tts_edge.platform.system", return_value="Windows"):
                tts.speak_blocking("Длинный блокирующий ответ")
        except Exception as e:
            worker_errors.append(str(e))

    tts._run_synthesis = blocking_synth
    tts._play_mp3_blocking_windows = blocking_wait_play
    worker = threading.Thread(target=run_blocking_speech, name="tts-blocking-eval")
    worker.start()
    started = play_started.wait(timeout=2.0)
    active_lifecycle = tts.get_lifecycle_telemetry()
    allow_finish.set()
    worker.join(timeout=2.0)
    final_lifecycle = tts.get_lifecycle_telemetry()

    check(
        "BLOCKING OPERATION EXPOSES ACTIVE LIFECYCLE",
        {
            "started": started,
            "active": active_lifecycle.active,
            "mode": active_lifecycle.active_mode,
            "phase": active_lifecycle.active_phase,
            "worker_alive": worker.is_alive(),
            "worker_errors": worker_errors,
            "final_active": final_lifecycle.active,
            "final_outcome": final_lifecycle.operation.last_outcome,
        },
        {
            "started": True,
            "active": True,
            "mode": "blocking",
            "phase": "playing",
            "worker_alive": False,
            "worker_errors": [],
            "final_active": False,
            "final_outcome": OUTCOME_SUCCESS,
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)
    tts._run_synthesis = blocking_synth

    def blocking_fail(out_path: str) -> None:
        _ = out_path
        clock.advance(0.2)
        raise TTSPlaybackError("fake blocking playback failure")

    tts._play_mp3_blocking_windows = blocking_fail
    raised = False

    try:
        with patch("modules.tts_edge.platform.system", return_value="Windows"):
            tts.speak_blocking("Ошибка")
    except TTSPlaybackError:
        raised = True

    snapshot = tts.get_operation_telemetry()

    check(
        "BLOCKING FAILURE RECORDED",
        {
            "raised": raised,
            "outcome": snapshot.last_outcome,
            "duration_ms": snapshot.last_duration_ms,
            "last_error": snapshot.last_error,
            "failures": snapshot.consecutive_failures,
        },
        {
            "raised": True,
            "outcome": OUTCOME_FAILURE,
            "duration_ms": 300,
            "last_error": "fake blocking playback failure",
            "failures": 1,
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)
    process = FakeProcess()
    paths: list[str] = []

    def interruptible_synth(text: str, out_path: str) -> None:
        _ = text
        paths.append(out_path)
        Path(out_path).write_bytes(b"audio")
        clock.advance(0.1)

    tts._run_synthesis = interruptible_synth
    tts._spawn_mp3_player_windows = ProcessFactory(process)
    FakeThread.instances.clear()

    with patch("modules.tts_edge.platform.system", return_value="Windows"), patch(
        "modules.tts_edge.threading.Thread",
        FakeThread,
    ):
        tts.speak_interruptible("Длинный ответ")

    before_watcher = tts.get_lifecycle_telemetry()
    thread = FakeThread.instances[-1]
    clock.advance(0.4)
    process.poll_result = 0
    thread.run()
    after_watcher = tts.get_lifecycle_telemetry()

    check(
        "INTERRUPTIBLE SUCCESS WAITS FOR WATCHER",
        {
            "before_has_attempt": before_watcher.operation.has_attempt,
            "before_active": before_watcher.active,
            "before_mode": before_watcher.active_mode,
            "before_phase": before_watcher.active_phase,
            "thread_started": thread.started,
            "after_outcome": after_watcher.operation.last_outcome,
            "after_duration_ms": after_watcher.operation.last_duration_ms,
            "after_active": after_watcher.active,
            "file_exists": Path(paths[0]).exists(),
        },
        {
            "before_has_attempt": False,
            "before_active": True,
            "before_mode": "interruptible",
            "before_phase": "playing",
            "thread_started": True,
            "after_outcome": OUTCOME_SUCCESS,
            "after_duration_ms": 500,
            "after_active": False,
            "file_exists": False,
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)
    process = FakeProcess()
    tts._run_synthesis = interruptible_synth
    tts._spawn_mp3_player_windows = ProcessFactory(process)
    FakeThread.instances.clear()

    with patch("modules.tts_edge.platform.system", return_value="Windows"), patch(
        "modules.tts_edge.threading.Thread",
        FakeThread,
    ):
        tts.speak_interruptible("Ошибка")

    thread = FakeThread.instances[-1]
    clock.advance(0.2)
    process.poll_result = 7
    thread.run()
    snapshot = tts.get_operation_telemetry()

    check(
        "INTERRUPTIBLE NONZERO EXIT RECORDED",
        {
            "outcome": snapshot.last_outcome,
            "duration_ms": snapshot.last_duration_ms,
            "last_error": snapshot.last_error,
            "failures": snapshot.consecutive_failures,
        },
        {
            "outcome": OUTCOME_FAILURE,
            "duration_ms": 300,
            "last_error": "TTS-плеер завершился с кодом 7.",
            "failures": 1,
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)
    process = FakeProcess(wait_error=RuntimeError("fake wait failure"))
    tts._run_synthesis = interruptible_synth
    tts._spawn_mp3_player_windows = ProcessFactory(process)
    FakeThread.instances.clear()

    with patch("modules.tts_edge.platform.system", return_value="Windows"), patch(
        "modules.tts_edge.threading.Thread",
        FakeThread,
    ):
        tts.speak_interruptible("Ошибка")

    thread = FakeThread.instances[-1]
    wait_failure_path = tts._player_temp_path
    clock.advance(0.2)
    thread.run()
    lifecycle = tts.get_lifecycle_telemetry()

    check(
        "INTERRUPTIBLE WAIT FAILURE RECORDED",
        {
            "outcome": lifecycle.operation.last_outcome,
            "last_error": lifecycle.operation.last_error,
            "failures": lifecycle.operation.consecutive_failures,
            "terminated": process.terminated,
            "active": lifecycle.active,
            "file_exists": Path(wait_failure_path).exists(),
        },
        {
            "outcome": OUTCOME_FAILURE,
            "last_error": "Ошибка ожидания TTS-плеера: fake wait failure",
            "failures": 1,
            "terminated": True,
            "active": False,
            "file_exists": False,
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)
    tts._run_synthesis = blocking_synth
    tts._play_mp3_blocking_windows = blocking_play

    with patch("modules.tts_edge.platform.system", return_value="Windows"):
        tts.speak_blocking("Успех")

    success_snapshot = tts.get_operation_telemetry()
    process = FakeProcess()
    tts._run_synthesis = interruptible_synth
    tts._spawn_mp3_player_windows = ProcessFactory(process)
    FakeThread.instances.clear()

    with patch("modules.tts_edge.platform.system", return_value="Windows"), patch(
        "modules.tts_edge.threading.Thread",
        FakeThread,
    ):
        tts.speak_interruptible("Останови меня")

    thread = FakeThread.instances[-1]
    clock.advance(0.4)
    stopped = tts.stop()
    after_stop = tts.get_lifecycle_telemetry()
    thread.run()
    after_stale_watcher = tts.get_lifecycle_telemetry()

    check(
        "REQUESTED STOP IS NEUTRAL",
        {
            "stopped": stopped,
            "terminated": process.terminated,
            "operation_outcome": after_stop.operation.last_outcome,
            "operation_attempt_at_unchanged": (
                after_stop.operation.last_attempt_at
                == success_snapshot.last_attempt_at
            ),
            "cancellation_count": after_stop.cancellation_count,
            "cancel_reason": after_stop.last_cancel_reason,
            "cancel_duration_ms": after_stop.last_cancelled_duration_ms,
            "after_watcher_outcome": after_stale_watcher.operation.last_outcome,
        },
        {
            "stopped": True,
            "terminated": True,
            "operation_outcome": OUTCOME_SUCCESS,
            "operation_attempt_at_unchanged": True,
            "cancellation_count": 1,
            "cancel_reason": "requested",
            "cancel_duration_ms": 500,
            "after_watcher_outcome": OUTCOME_SUCCESS,
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)
    first_process = FakeProcess()
    second_process = FakeProcess()
    tts._run_synthesis = interruptible_synth
    tts._spawn_mp3_player_windows = ProcessFactory(first_process, second_process)
    FakeThread.instances.clear()

    with patch("modules.tts_edge.platform.system", return_value="Windows"), patch(
        "modules.tts_edge.threading.Thread",
        FakeThread,
    ):
        tts.speak_interruptible("Первый ответ")
        first_thread = FakeThread.instances[-1]
        tts.speak_interruptible("Второй ответ")
        second_thread = FakeThread.instances[-1]

    after_replacement = tts.get_lifecycle_telemetry()
    first_thread.run()
    after_old_watcher = tts.get_lifecycle_telemetry()
    clock.advance(0.2)
    second_process.poll_result = 0
    second_thread.run()
    final_lifecycle = tts.get_lifecycle_telemetry()

    check(
        "REPLACEMENT AND STALE WATCHER ARE SAFE",
        {
            "first_terminated": first_process.terminated,
            "after_replace_active": after_replacement.active,
            "after_replace_cancel_reason": after_replacement.last_cancel_reason,
            "after_replace_cancellations": after_replacement.cancellation_count,
            "old_watcher_kept_new_active": after_old_watcher.active,
            "old_watcher_has_attempt": after_old_watcher.operation.has_attempt,
            "final_outcome": final_lifecycle.operation.last_outcome,
            "final_active": final_lifecycle.active,
            "final_cancellations": final_lifecycle.cancellation_count,
        },
        {
            "first_terminated": True,
            "after_replace_active": True,
            "after_replace_cancel_reason": "replaced",
            "after_replace_cancellations": 1,
            "old_watcher_kept_new_active": True,
            "old_watcher_has_attempt": False,
            "final_outcome": OUTCOME_SUCCESS,
            "final_active": False,
            "final_cancellations": 1,
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)
    process = FakeProcess(terminate_error=RuntimeError("terminate failed"))
    tts._run_synthesis = interruptible_synth
    tts._spawn_mp3_player_windows = ProcessFactory(process)
    FakeThread.instances.clear()

    with patch("modules.tts_edge.platform.system", return_value="Windows"), patch(
        "modules.tts_edge.threading.Thread",
        FakeThread,
    ):
        tts.speak_interruptible("Останови меня")

    stopped = tts.stop()
    lifecycle = tts.get_lifecycle_telemetry()

    check(
        "STOP FALLS BACK TO KILL",
        {
            "stopped": stopped,
            "terminated": process.terminated,
            "killed": process.killed,
            "outcome_has_attempt": lifecycle.operation.has_attempt,
            "cancellations": lifecycle.cancellation_count,
            "reason": lifecycle.last_cancel_reason,
        },
        {
            "stopped": True,
            "terminated": True,
            "killed": True,
            "outcome_has_attempt": False,
            "cancellations": 1,
            "reason": "requested",
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)
    process = FakeProcess(
        terminate_error=RuntimeError("terminate failed"),
        kill_error=RuntimeError("kill failed"),
    )
    synth_calls = 0

    def count_synth(text: str, out_path: str) -> None:
        nonlocal synth_calls
        synth_calls += 1
        interruptible_synth(text, out_path)

    tts._run_synthesis = count_synth
    tts._spawn_mp3_player_windows = ProcessFactory(process)
    FakeThread.instances.clear()

    with patch("modules.tts_edge.platform.system", return_value="Windows"), patch(
        "modules.tts_edge.threading.Thread",
        FakeThread,
    ):
        tts.speak_interruptible("Старый ответ")

        raised = False

        try:
            tts.speak_blocking("Новый ответ")
        except TTSPlaybackError:
            raised = True

    lifecycle = tts.get_lifecycle_telemetry()
    failed_path = tts._player_temp_path

    check(
        "FAILED STOP BLOCKS REPLACEMENT",
        {
            "raised": raised,
            "synth_calls": synth_calls,
            "terminated": process.terminated,
            "killed": process.killed,
            "outcome": lifecycle.operation.last_outcome,
            "last_error": lifecycle.operation.last_error,
            "failures": lifecycle.operation.consecutive_failures,
            "cancellations": lifecycle.cancellation_count,
            "active": lifecycle.active,
            "active_phase": lifecycle.active_phase,
            "process_preserved": tts._player_proc is process,
            "file_exists": Path(failed_path).exists(),
        },
        {
            "raised": True,
            "synth_calls": 1,
            "terminated": True,
            "killed": True,
            "outcome": OUTCOME_FAILURE,
            "last_error": "Не удалось остановить TTS-плеер.",
            "failures": 1,
            "cancellations": 0,
            "active": True,
            "active_phase": "stop_failed",
            "process_preserved": True,
            "file_exists": True,
        },
    )

    process.kill_error = None
    retry_stopped = tts.stop()
    retry_lifecycle = tts.get_lifecycle_telemetry()

    check(
        "FAILED STOP CAN BE RETRIED",
        {
            "stopped": retry_stopped,
            "active": retry_lifecycle.active,
            "outcome": retry_lifecycle.operation.last_outcome,
            "last_error": retry_lifecycle.operation.last_error,
            "cancellations": retry_lifecycle.cancellation_count,
            "file_exists": Path(failed_path).exists(),
        },
        {
            "stopped": True,
            "active": False,
            "outcome": OUTCOME_FAILURE,
            "last_error": "Не удалось остановить TTS-плеер.",
            "cancellations": 1,
            "file_exists": False,
        },
    )

    clock = FakeClock()
    tts = _new_tts(clock)
    tts.speak_blocking("   ")
    tts.speak_interruptible("")
    lifecycle = tts.get_lifecycle_telemetry()

    check(
        "EMPTY TEXT DOES NOT CREATE OPERATION",
        {
            "has_attempt": lifecycle.operation.has_attempt,
            "active": lifecycle.active,
            "cancellations": lifecycle.cancellation_count,
        },
        {
            "has_attempt": False,
            "active": False,
            "cancellations": 0,
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
