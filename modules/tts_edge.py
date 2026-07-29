from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import tempfile
import threading
import time

from dataclasses import dataclass
from typing import Callable

import edge_tts

from modules.core.operation_telemetry import OperationTelemetry, OperationTelemetrySnapshot


class TTSSynthesisError(RuntimeError):
    pass


class TTSPlaybackError(RuntimeError):
    pass


@dataclass
class _DuckedSession:
    session: object
    original_volume: float


@dataclass
class _TTSOperation:
    operation_id: int
    mode: str
    started_at_monotonic: float
    phase: str = "synthesizing"
    terminal_claimed: bool = False


@dataclass(frozen=True)
class TTSLifecycleSnapshot:
    operation: OperationTelemetrySnapshot
    active_operation_id: int | None
    active: bool
    active_mode: str
    active_phase: str
    last_cancelled_at: float | None
    last_cancelled_duration_ms: int | None
    last_cancel_reason: str
    cancellation_count: int


class _AudioDucker:
    """
    Временное приглушение чужих audio sessions на время речи ассистента.
    Работает только на Windows, использует pycaw.
    """

    def __init__(self, enabled: bool = True, level: float = 0.25):
        self._enabled = bool(enabled)
        self._level = max(0.0, min(1.0, float(level)))
        self._sessions: list[_DuckedSession] = []

    def duck(self) -> None:
        if not self._enabled:
            return
        if not platform.system().lower().startswith("win"):
            return

        try:
            from pycaw.pycaw import AudioUtilities
        except Exception:
            return

        self._sessions.clear()

        try:
            for session in AudioUtilities.GetAllSessions():
                if session is None:
                    continue

                control = getattr(session, "SimpleAudioVolume", None)
                if control is None:
                    continue

                try:
                    if bool(control.GetMute()):
                        continue
                except Exception:
                    pass

                try:
                    current = float(control.GetMasterVolume())
                except Exception:
                    continue

                if current <= 0.01:
                    continue

                try:
                    control.SetMasterVolume(self._level, None)
                    self._sessions.append(
                        _DuckedSession(
                            session=session,
                            original_volume=current,
                        )
                    )
                except Exception:
                    continue
        except Exception:
            self._sessions.clear()

    def restore(self) -> None:
        if not self._sessions:
            return

        for item in self._sessions:
            try:
                control = getattr(item.session, "SimpleAudioVolume", None)
                if control is None:
                    continue

                control.SetMasterVolume(float(item.original_volume), None)
            except Exception:
                continue

        self._sessions.clear()


class EdgeTTS:
    """
    Edge TTS для Windows:
    - генерация MP3 через edge-tts;
    - воспроизведение через PowerShell MediaPlayer;
    - блокирующее и прерываемое воспроизведение;
    - восстановление ducking и очистка временных файлов при ошибках;
    - lifecycle telemetry без ложного failure при штатной остановке.
    """

    def __init__(
        self,
        voice: str = "ru-RU-SvetlanaNeural",
        rate: str = "+0%",
        volume: str = "+20%",
        pitch: str = "+0Hz",
        ducking_enable: bool | None = None,
        ducking_level: float | None = None,
        player_timeout_sec: float = 120.0,
        health_ttl_sec: float = 1800.0,
        time_func: Callable[[], float] = time.time,
        monotonic_func: Callable[[], float] = time.monotonic,
    ):
        self.voice = (voice or "ru-RU-SvetlanaNeural").strip()
        self.rate = (rate or "+0%").strip()
        self.volume = (volume or "+20%").strip()
        self.pitch = (pitch or "+0Hz").strip()
        self._player_timeout_sec = max(1.0, float(player_timeout_sec))
        self._health_ttl_sec = max(1.0, float(health_ttl_sec))
        self._time_func = time_func
        self._monotonic_func = monotonic_func
        self._telemetry = OperationTelemetry(time_func=time_func)

        if ducking_enable is None:
            ducking_enable = os.getenv("AUDIO_DUCKING_ENABLE", "1").strip() == "1"

        if ducking_level is None:
            ducking_level = float(os.getenv("AUDIO_DUCKING_LEVEL", "0.25"))

        self._ducker = _AudioDucker(
            enabled=ducking_enable,
            level=ducking_level,
        )

        self._speak_lock = threading.RLock()
        self._play_lock = threading.RLock()
        self._player_proc: subprocess.Popen | None = None
        self._player_temp_path: str | None = None
        self._active_operation: _TTSOperation | None = None
        self._operation_seq = 0
        self._last_cancelled_at: float | None = None
        self._last_cancelled_duration_ms: int | None = None
        self._last_cancel_reason = ""
        self._cancellation_count = 0

    @property
    def health_ttl_sec(self) -> float:
        return self._health_ttl_sec

    def get_operation_telemetry(self) -> OperationTelemetrySnapshot:
        return self._telemetry.snapshot()

    def get_lifecycle_telemetry(self) -> TTSLifecycleSnapshot:
        with self._play_lock:
            operation = self._active_operation

            return TTSLifecycleSnapshot(
                operation=self._telemetry.snapshot(),
                active_operation_id=(
                    operation.operation_id
                    if operation is not None
                    else None
                ),
                active=operation is not None,
                active_mode=operation.mode if operation is not None else "",
                active_phase=operation.phase if operation is not None else "",
                last_cancelled_at=self._last_cancelled_at,
                last_cancelled_duration_ms=self._last_cancelled_duration_ms,
                last_cancel_reason=self._last_cancel_reason,
                cancellation_count=self._cancellation_count,
            )

    async def _synth_mp3(self, text: str, out_path: str) -> None:
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
            pitch=self.pitch,
        )
        await communicate.save(out_path)

    def _run_synthesis(self, text: str, out_path: str) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            self._run_synthesis_without_running_loop(text, out_path)
        else:
            self._run_synthesis_in_worker_thread(text, out_path)

        try:
            audio_size = os.path.getsize(out_path)
        except OSError as e:
            raise TTSSynthesisError("TTS не создал аудиофайл.") from e

        if audio_size <= 0:
            raise TTSSynthesisError("TTS создал пустой аудиофайл.")

    def _run_synthesis_without_running_loop(self, text: str, out_path: str) -> None:
        try:
            asyncio.run(self._synth_mp3(text, out_path))
        except Exception as e:
            raise TTSSynthesisError(f"Ошибка синтеза речи: {e}") from e

    def _run_synthesis_in_worker_thread(self, text: str, out_path: str) -> None:
        errors: list[Exception] = []

        def _worker() -> None:
            try:
                asyncio.run(self._synth_mp3(text, out_path))
            except Exception as e:
                errors.append(e)

        thread = threading.Thread(target=_worker, name="edge-tts-synthesis")
        thread.start()
        thread.join()

        if errors:
            error = errors[0]
            raise TTSSynthesisError(f"Ошибка синтеза речи: {error}") from error

    def _build_player_script(self, path: str) -> str:
        escaped_path = path.replace("'", "''")

        return rf"""
            Add-Type -AssemblyName presentationCore | Out-Null
            $player = New-Object System.Windows.Media.MediaPlayer

            try {{
                $player.Open([Uri]'{escaped_path}')
                $player.Volume = 1.0
                $player.Play()

                Start-Sleep -Milliseconds 200
                $durationDeadline = (Get-Date).AddSeconds(10)

                while (-not $player.NaturalDuration.HasTimeSpan) {{
                    if ((Get-Date) -ge $durationDeadline) {{
                        throw "Media duration timeout"
                    }}

                    Start-Sleep -Milliseconds 100
                }}

                $ms = [int]$player.NaturalDuration.TimeSpan.TotalMilliseconds
                if ($ms -lt 200) {{ $ms = 200 }}

                Start-Sleep -Milliseconds $ms
            }}
            finally {{
                $player.Stop()
                $player.Close()
            }}
        """

    def _spawn_mp3_player_windows(self, path: str) -> subprocess.Popen:
        ps_script = self._build_player_script(path)

        try:
            return subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    ps_script,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            raise TTSPlaybackError(f"Не удалось запустить TTS-плеер: {e}") from e

    def _play_mp3_blocking_windows(self, path: str) -> None:
        ps_script = self._build_player_script(path)

        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    ps_script,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=self._player_timeout_sec,
            )
        except subprocess.TimeoutExpired as e:
            raise TTSPlaybackError("Превышено время ожидания TTS-плеера.") from e
        except OSError as e:
            raise TTSPlaybackError(f"Не удалось запустить TTS-плеер: {e}") from e

        if result.returncode != 0:
            raise TTSPlaybackError(
                f"TTS-плеер завершился с кодом {result.returncode}."
            )

    def _cleanup_temp_file(self, path: str | None) -> None:
        if not path:
            return

        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError:
            pass

    def _duration_ms(self, started_at_monotonic: float) -> int:
        elapsed = max(
            0.0,
            float(self._monotonic_func()) - float(started_at_monotonic),
        )
        return int(round(elapsed * 1000.0))

    def _begin_operation_locked(self, mode: str) -> _TTSOperation:
        if self._active_operation is not None:
            raise RuntimeError("TTS operation is already active")

        self._operation_seq += 1
        operation = _TTSOperation(
            operation_id=self._operation_seq,
            mode=str(mode or "unknown").strip() or "unknown",
            started_at_monotonic=float(self._monotonic_func()),
        )
        self._active_operation = operation
        return operation

    def _begin_operation(self, mode: str) -> _TTSOperation:
        with self._play_lock:
            return self._begin_operation_locked(mode)

    def _ensure_active_operation_locked(self) -> _TTSOperation:
        operation = self._active_operation

        if operation is None:
            operation = self._begin_operation_locked("interruptible")
            operation.phase = "playing"

        return operation

    def _clear_active_operation_locked(self, operation: _TTSOperation) -> None:
        if self._active_operation is operation:
            self._active_operation = None

    def _finalize_operation_locked(
        self,
        operation: _TTSOperation,
        *,
        return_code: int | None = None,
        error: BaseException | str | None = None,
        clear_active: bool = True,
    ) -> bool:
        recorded = False

        if not operation.terminal_claimed:
            operation.terminal_claimed = True
            duration_ms = self._duration_ms(operation.started_at_monotonic)

            if error is not None:
                self._telemetry.record_failure(error, duration_ms=duration_ms)
            elif return_code == 0:
                self._telemetry.record_success(duration_ms=duration_ms)
            elif return_code is None:
                self._telemetry.record_failure(
                    TTSPlaybackError("TTS-плеер завершился без кода возврата."),
                    duration_ms=duration_ms,
                )
            else:
                self._telemetry.record_failure(
                    TTSPlaybackError(
                        f"TTS-плеер завершился с кодом {return_code}."
                    ),
                    duration_ms=duration_ms,
                )

            recorded = True

        if clear_active:
            self._clear_active_operation_locked(operation)

        return recorded

    def _record_cancelled_locked(
        self,
        operation: _TTSOperation,
        *,
        reason: str,
    ) -> None:
        operation.terminal_claimed = True
        self._last_cancelled_at = float(self._time_func())
        self._last_cancelled_duration_ms = self._duration_ms(
            operation.started_at_monotonic
        )
        self._last_cancel_reason = str(reason or "requested").strip() or "requested"
        self._cancellation_count += 1
        self._clear_active_operation_locked(operation)

    def _process_is_running(self, proc: subprocess.Popen) -> bool:
        try:
            return proc.poll() is None
        except Exception:
            return True

    def _terminate_process(self, proc: subprocess.Popen | None) -> bool:
        if proc is None:
            return True

        try:
            if proc.poll() is not None:
                return True
        except Exception:
            pass

        try:
            proc.terminate()
            proc.wait(timeout=0.5)
            return True
        except Exception:
            pass

        try:
            proc.kill()
            proc.wait(timeout=0.5)
            return True
        except Exception:
            return False

    def _watch_interruptible_playback(
        self,
        proc: subprocess.Popen,
        path: str,
        operation: _TTSOperation | None = None,
    ) -> None:
        return_code: int | None = None
        wait_error: Exception | None = None

        try:
            return_code = proc.wait()
        except Exception as e:
            wait_error = e

        with self._speak_lock:
            restore_ducking = False
            cleanup_file = True

            with self._play_lock:
                is_current = self._player_proc is proc

                if operation is None and is_current:
                    operation = self._ensure_active_operation_locked()

                if wait_error is not None and operation is not None:
                    self._finalize_operation_locked(
                        operation,
                        error=TTSPlaybackError(
                            f"Ошибка ожидания TTS-плеера: {wait_error}"
                        ),
                        clear_active=False,
                    )

                if wait_error is None and operation is not None:
                    self._finalize_operation_locked(
                        operation,
                        return_code=return_code,
                        clear_active=is_current,
                    )

                if wait_error is None and is_current:
                    self._player_proc = None
                    self._player_temp_path = None
                    restore_ducking = True

            if wait_error is not None and is_current:
                terminated = self._terminate_process(proc)

                with self._play_lock:
                    if terminated and self._player_proc is proc:
                        self._player_proc = None
                        self._player_temp_path = None
                        if operation is not None:
                            self._clear_active_operation_locked(operation)
                        restore_ducking = True
                    elif not terminated:
                        cleanup_file = False
                        if operation is not None:
                            operation.phase = "watch_failed"

            if restore_ducking:
                self._ducker.restore()

            if cleanup_file:
                self._cleanup_temp_file(path)

    def is_speaking(self) -> bool:
        with self._speak_lock:
            restore_ducking = False
            path: str | None = None

            with self._play_lock:
                proc = self._player_proc

                if proc is None:
                    return False

                operation = self._ensure_active_operation_locked()

                try:
                    return_code = proc.poll()
                except Exception as e:
                    operation.phase = "poll_failed"
                    self._finalize_operation_locked(
                        operation,
                        error=TTSPlaybackError(
                            f"Не удалось проверить TTS-плеер: {e}"
                        ),
                        clear_active=False,
                    )
                    return True

                if return_code is None:
                    return True

                path = self._player_temp_path
                self._finalize_operation_locked(
                    operation,
                    return_code=return_code,
                )
                self._player_proc = None
                self._player_temp_path = None
                restore_ducking = True

            if restore_ducking:
                self._ducker.restore()

            self._cleanup_temp_file(path)
            return False

    def _stop_active(self, *, reason: str) -> bool:
        path: str | None = None

        with self._play_lock:
            proc = self._player_proc
            path = self._player_temp_path

            if proc is None:
                self._ducker.restore()
                return True

            operation = self._ensure_active_operation_locked()

            try:
                return_code = proc.poll()
            except Exception:
                return_code = None

            if return_code is not None:
                self._finalize_operation_locked(
                    operation,
                    return_code=return_code,
                )
                self._player_proc = None
                self._player_temp_path = None
                process_already_finished = True
            else:
                operation.phase = "stopping"
                process_already_finished = False

        if process_already_finished:
            self._ducker.restore()
            self._cleanup_temp_file(path)
            return True

        terminated = self._terminate_process(proc)

        with self._play_lock:
            if terminated:
                self._record_cancelled_locked(operation, reason=reason)
                if self._player_proc is proc:
                    self._player_proc = None
                    self._player_temp_path = None
            else:
                operation.phase = "stop_failed"
                self._finalize_operation_locked(
                    operation,
                    error=TTSPlaybackError("Не удалось остановить TTS-плеер."),
                    clear_active=False,
                )

        if not terminated:
            return False

        self._ducker.restore()
        self._cleanup_temp_file(path)
        return True

    def stop(self) -> bool:
        with self._speak_lock:
            return self._stop_active(reason="requested")

    def speak_interruptible(self, text: str) -> None:
        text = (text or "").strip()

        if not text:
            return

        is_windows = platform.system().lower().startswith("win")

        with self._speak_lock:
            if not self._stop_active(reason="replaced"):
                raise TTSPlaybackError(
                    "Не удалось остановить предыдущее воспроизведение TTS."
                )

            operation = self._begin_operation("interruptible")
            out_path: str | None = None
            proc: subprocess.Popen | None = None

            try:
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".mp3",
                ) as temp_file:
                    out_path = temp_file.name

                self._run_synthesis(text, out_path)

                if not is_windows:
                    with self._play_lock:
                        self._finalize_operation_locked(operation, return_code=0)
                    return

                self._ducker.duck()
                proc = self._spawn_mp3_player_windows(out_path)

                with self._play_lock:
                    operation.phase = "playing"
                    self._player_proc = proc
                    self._player_temp_path = out_path

                watcher = threading.Thread(
                    target=self._watch_interruptible_playback,
                    args=(proc, out_path, operation),
                    name="edge-tts-playback-watch",
                    daemon=True,
                )
                watcher.start()
            except Exception as e:
                terminated = self._terminate_process(proc)

                with self._play_lock:
                    self._finalize_operation_locked(
                        operation,
                        error=e,
                        clear_active=proc is None or terminated,
                    )

                    if proc is not None and terminated and self._player_proc is proc:
                        self._player_proc = None
                        self._player_temp_path = None

                    if proc is not None and not terminated:
                        operation.phase = "unmonitored"

                if proc is None or terminated:
                    self._ducker.restore()
                    self._cleanup_temp_file(out_path)

                raise
            finally:
                if not is_windows:
                    self._cleanup_temp_file(out_path)

    def speak_blocking(self, text: str) -> None:
        text = (text or "").strip()

        if not text:
            return

        is_windows = platform.system().lower().startswith("win")

        with self._speak_lock:
            if not self._stop_active(reason="replaced"):
                raise TTSPlaybackError(
                    "Не удалось остановить предыдущее воспроизведение TTS."
                )

            operation = self._begin_operation("blocking")
            out_path: str | None = None

            try:
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=".mp3",
                ) as temp_file:
                    out_path = temp_file.name

                self._run_synthesis(text, out_path)

                if not is_windows:
                    print(f"[TTS] audio saved: {out_path}")
                    with self._play_lock:
                        self._finalize_operation_locked(operation, return_code=0)
                    return

                with self._play_lock:
                    operation.phase = "playing"

                self._ducker.duck()

                try:
                    self._play_mp3_blocking_windows(out_path)
                finally:
                    self._ducker.restore()

                with self._play_lock:
                    self._finalize_operation_locked(operation, return_code=0)
            except Exception as e:
                with self._play_lock:
                    self._finalize_operation_locked(operation, error=e)
                raise
            finally:
                self._cleanup_temp_file(out_path)
