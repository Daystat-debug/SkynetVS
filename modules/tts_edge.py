from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import tempfile
import threading

from dataclasses import dataclass

import edge_tts


class TTSSynthesisError(RuntimeError):
    pass


class TTSPlaybackError(RuntimeError):
    pass


@dataclass
class _DuckedSession:
    session: object
    original_volume: float


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
    - восстановление ducking и очистка временных файлов при ошибках.
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
    ):
        self.voice = (voice or "ru-RU-SvetlanaNeural").strip()
        self.rate = (rate or "+0%").strip()
        self.volume = (volume or "+20%").strip()
        self.pitch = (pitch or "+0Hz").strip()
        self._player_timeout_sec = max(1.0, float(player_timeout_sec))

        if ducking_enable is None:
            ducking_enable = os.getenv("AUDIO_DUCKING_ENABLE", "1").strip() == "1"

        if ducking_level is None:
            ducking_level = float(os.getenv("AUDIO_DUCKING_LEVEL", "0.25"))

        self._ducker = _AudioDucker(
            enabled=ducking_enable,
            level=ducking_level,
        )

        self._play_lock = threading.RLock()
        self._player_proc: subprocess.Popen | None = None
        self._player_temp_path: str | None = None

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

    def _run_synthesis_without_running_loop(
        self,
        text: str,
        out_path: str,
    ) -> None:
        try:
            asyncio.run(self._synth_mp3(text, out_path))
        except Exception as e:
            raise TTSSynthesisError(f"Ошибка синтеза речи: {e}") from e

    def _run_synthesis_in_worker_thread(
        self,
        text: str,
        out_path: str,
    ) -> None:
        errors: list[Exception] = []

        def _worker() -> None:
            try:
                asyncio.run(self._synth_mp3(text, out_path))
            except Exception as e:
                errors.append(e)

        thread = threading.Thread(
            target=_worker,
            name="edge-tts-synthesis",
        )
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
            raise TTSPlaybackError(
                f"Не удалось запустить TTS-плеер: {e}"
            ) from e

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
            raise TTSPlaybackError(
                "Превышено время ожидания TTS-плеера."
            ) from e
        except OSError as e:
            raise TTSPlaybackError(
                f"Не удалось запустить TTS-плеер: {e}"
            ) from e

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

    def _process_is_running(self, proc: subprocess.Popen) -> bool:
        try:
            return proc.poll() is None
        except Exception:
            return True

    def _terminate_process(self, proc: subprocess.Popen | None) -> None:
        if proc is None:
            return
        if not self._process_is_running(proc):
            return

        try:
            proc.terminate()
            proc.wait(timeout=0.5)
            return
        except Exception:
            pass

        try:
            proc.kill()
            proc.wait(timeout=0.5)
        except Exception:
            pass

    def _watch_interruptible_playback(
        self,
        proc: subprocess.Popen,
        path: str,
    ) -> None:
        try:
            proc.wait()
        except Exception:
            pass
        finally:
            restore_ducking = False

            with self._play_lock:
                if self._player_proc is proc:
                    self._player_proc = None
                    self._player_temp_path = None
                    restore_ducking = True

            if restore_ducking:
                self._ducker.restore()

            self._cleanup_temp_file(path)

    def is_speaking(self) -> bool:
        restore_ducking = False

        with self._play_lock:
            proc = self._player_proc

            if proc is None:
                return False

            if self._process_is_running(proc):
                return True

            path = self._player_temp_path
            self._player_proc = None
            self._player_temp_path = None
            restore_ducking = True

        if restore_ducking:
            self._ducker.restore()

        self._cleanup_temp_file(path)
        return False

    def stop(self) -> None:
        with self._play_lock:
            proc = self._player_proc
            path = self._player_temp_path
            self._player_proc = None
            self._player_temp_path = None

        self._terminate_process(proc)
        self._ducker.restore()
        self._cleanup_temp_file(path)

    def speak_interruptible(self, text: str) -> None:
        text = (text or "").strip()

        if not text:
            return

        self.stop()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp3",
        ) as temp_file:
            out_path = temp_file.name

        proc: subprocess.Popen | None = None

        try:
            self._run_synthesis(text, out_path)

            if not platform.system().lower().startswith("win"):
                return

            self._ducker.duck()
            proc = self._spawn_mp3_player_windows(out_path)

            with self._play_lock:
                self._player_proc = proc
                self._player_temp_path = out_path

            watcher = threading.Thread(
                target=self._watch_interruptible_playback,
                args=(proc, out_path),
                name="edge-tts-playback-watch",
                daemon=True,
            )
            watcher.start()
        except Exception:
            with self._play_lock:
                if proc is not None and self._player_proc is proc:
                    self._player_proc = None
                    self._player_temp_path = None

            self._terminate_process(proc)
            self._ducker.restore()
            self._cleanup_temp_file(out_path)
            raise
        finally:
            if not platform.system().lower().startswith("win"):
                self._cleanup_temp_file(out_path)

    def speak_blocking(self, text: str) -> None:
        text = (text or "").strip()

        if not text:
            return

        self.stop()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp3",
        ) as temp_file:
            out_path = temp_file.name

        try:
            self._run_synthesis(text, out_path)

            if not platform.system().lower().startswith("win"):
                print(f"[TTS] audio saved: {out_path}")
                return

            self._ducker.duck()

            try:
                self._play_mp3_blocking_windows(out_path)
            finally:
                self._ducker.restore()
        finally:
            self._cleanup_temp_file(out_path)
