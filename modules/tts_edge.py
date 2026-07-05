from __future__ import annotations

import asyncio
import os
import tempfile
import subprocess
import platform
import threading
from dataclasses import dataclass

import edge_tts


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
            for s in AudioUtilities.GetAllSessions():
                if s is None:
                    continue

                # нам интересны только "живые" сессии с управляемой громкостью
                ctl = getattr(s, "SimpleAudioVolume", None)
                if ctl is None:
                    continue

                # если сессия уже mute, не трогаем
                try:
                    if bool(ctl.GetMute()):
                        continue
                except Exception:
                    pass

                try:
                    current = float(ctl.GetMasterVolume())
                except Exception:
                    continue

                # нет смысла трогать почти нулевую громкость
                if current <= 0.01:
                    continue

                try:
                    ctl.SetMasterVolume(self._level, None)
                    self._sessions.append(_DuckedSession(session=s, original_volume=current))
                except Exception:
                    continue
        except Exception:
            # ducking — best effort, не валим TTS
            self._sessions.clear()

    def restore(self) -> None:
        if not self._sessions:
            return

        for item in self._sessions:
            try:
                ctl = getattr(item.session, "SimpleAudioVolume", None)
                if ctl is None:
                    continue
                ctl.SetMasterVolume(float(item.original_volume), None)
            except Exception:
                continue

        self._sessions.clear()


class EdgeTTS:
    """
    Надёжный Edge TTS для Windows:
    - генерация MP3 через edge-tts
    - воспроизведение через PowerShell MediaPlayer
    - блокирующее воспроизведение
    - опциональное усиление голоса
    - опциональный ducking фоновой музыки/других приложений
    """

    def __init__(
        self,
        voice: str = "ru-RU-SvetlanaNeural",
        rate: str = "+0%",
        volume: str | None = None,
        ducking_enable: bool | None = None,
        ducking_level: float | None = None,
    ):
        self.voice = voice
        self.rate = rate
        self.volume = (volume or os.getenv("TTS_VOLUME", "+20%")).strip()

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
        )
        await communicate.save(out_path)

    def _build_player_script(self, path: str) -> str:
        p = path.replace("'", "''")
        return rf"""
            Add-Type -AssemblyName presentationCore | Out-Null
            $player = New-Object System.Windows.Media.MediaPlayer
            $player.Open([Uri]'{p}')
            $player.Volume = 1.0
            $player.Play()

            Start-Sleep -Milliseconds 200

            while (-not $player.NaturalDuration.HasTimeSpan) {{
                Start-Sleep -Milliseconds 100
            }}

            $ms = [int]$player.NaturalDuration.TimeSpan.TotalMilliseconds
            if ($ms -lt 200) {{ $ms = 200 }}

            Start-Sleep -Milliseconds $ms
            $player.Stop()
        """

    def _spawn_mp3_player_windows(self, path: str) -> subprocess.Popen:
        ps_script = self._build_player_script(path)
        return subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _play_mp3_blocking_windows(self, path: str) -> None:
        ps_script = self._build_player_script(path)
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def _cleanup_temp_file(self, path: str | None) -> None:
        if not path:
            return
        try:
            os.remove(path)
        except Exception:
            pass

    def _watch_interruptible_playback(self, proc: subprocess.Popen, path: str) -> None:
        try:
            proc.wait()
        finally:
            with self._play_lock:
                if self._player_proc is proc:
                    self._player_proc = None
                    self._player_temp_path = None
            self._ducker.restore()
            self._cleanup_temp_file(path)

    def is_speaking(self) -> bool:
        with self._play_lock:
            proc = self._player_proc
            if proc is None:
                return False
            if proc.poll() is None:
                return True

            path = self._player_temp_path
            self._player_proc = None
            self._player_temp_path = None

        self._cleanup_temp_file(path)
        return False

    def stop(self) -> None:
        with self._play_lock:
            proc = self._player_proc
            path = self._player_temp_path
            self._player_proc = None
            self._player_temp_path = None

        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=0.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        self._ducker.restore()
        self._cleanup_temp_file(path)

    def speak_interruptible(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return

        self.stop()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            out_path = f.name

        try:
            try:
                asyncio.run(self._synth_mp3(text, out_path))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._synth_mp3(text, out_path))
                loop.close()

            self._ducker.duck()

            if platform.system().lower().startswith("win"):
                proc = self._spawn_mp3_player_windows(out_path)
            else:
                self._cleanup_temp_file(out_path)
                return

            with self._play_lock:
                self._player_proc = proc
                self._player_temp_path = out_path

            threading.Thread(
                target=self._watch_interruptible_playback,
                args=(proc, out_path),
                daemon=True,
            ).start()

        except Exception:
            self._ducker.restore()
            self._cleanup_temp_file(out_path)
            raise

    def speak_blocking(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            out_path = f.name

        try:
            try:
                asyncio.run(self._synth_mp3(text, out_path))
            except RuntimeError:
                # если event loop уже существует
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._synth_mp3(text, out_path))
                loop.close()

            self._ducker.duck()
            try:
                if platform.system().lower().startswith("win"):
                    self._play_mp3_blocking_windows(out_path)
                else:
                    print(f"[TTS] audio saved: {out_path}")
            finally:
                self._ducker.restore()

        finally:
            try:
                os.remove(out_path)
            except Exception:
                pass
