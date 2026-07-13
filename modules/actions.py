# modules/actions.py

from __future__ import annotations

import os
import subprocess
import webbrowser
import time
import ctypes
import socket
import urllib.request

from typing import Optional, Dict, Any, Callable
from modules.audio_control import AudioControl
from modules.audio_output import AudioOutputControl
from modules.media_control import MediaControl
from modules.screenshot import ScreenshotService
from modules.error_log import log_exception
from urllib.parse import quote_plus
from pathlib import Path
from modules.weather_service import WeatherService
from modules.typing_service import TypingService
from modules.window_context_service import WindowContextService
from modules.entity_registry import (
    get_app_close_strategy,
    get_app_image_names,
    get_app_open_command,
    get_app_title_patterns,
    get_folder_path_kind,
    get_settings_section_uri,
)
from modules.duration_parser import (
    format_duration_ru,
)
from modules.timer_service import TimerService


class Actions:
    """
    Единая точка выполнения действий по интентам.
    main.py отвечает только за:
      - STT (распознавание)
      - wake-word + окно команд
      - вызов NLU
      - TTS ответа
    А здесь: запуск приложений, звук и т.п.
    """

    def __init__(
        self,
        *,
        audio: Optional[AudioControl],
        volume_step: int = 10,
        audio_output: Optional[AudioOutputControl] = None,
        screenshot_service: Optional[ScreenshotService] = None,
        weather_service: Optional[WeatherService] = None,
        typing_service: Optional[TypingService] = None,
        window_context_service: Optional[WindowContextService] = None,
        timer_service: Optional[TimerService] = None,
    ):
        self._audio = audio
        self._audio_output = audio_output
        self._screenshot_service = screenshot_service or ScreenshotService()
        self._weather_service = weather_service or WeatherService()
        self._volume_step = int(volume_step)
        self._timer_service = timer_service
        self._music_prev_double = os.getenv("MUSIC_PREV_DOUBLE", "1").strip() == "1"
        self._music_prev_double_delay = float(os.getenv("MUSIC_PREV_DOUBLE_DELAY", "0.15"))
        self._typing_service = typing_service or TypingService()
        self._window_context_service = window_context_service or WindowContextService()
        self._execute_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {
            "VOLUME_UP": self._exec_volume_up,
            "VOLUME_DOWN": self._exec_volume_down,
            "MUTE": self._exec_mute,
            "UNMUTE": self._exec_unmute,
            "SET_VOLUME": self._exec_set_volume,

            "OPEN_APP": self._exec_open_app,
            "OPEN_URL": self._exec_open_url,
            "SEARCH_WEB": self._exec_search_web,
            "SEARCH_YOUTUBE": self._exec_search_youtube,
            "SCREENSHOT": self._exec_screenshot,
            "AUDIO_OUTPUT_TOGGLE": self._exec_audio_output_toggle,
            "AUDIO_OUTPUT_HEADPHONES": self._exec_audio_output_headphones,
            "AUDIO_OUTPUT_SPEAKERS": self._exec_audio_output_speakers,
            "MUSIC_PLAY": self._exec_music_play,
            "MUSIC_PAUSE": self._exec_music_pause,
            "MUSIC_NEXT": self._exec_music_next,
            "MUSIC_PREV": self._exec_music_prev,
            "MUSIC_RESTART": self._exec_music_restart,
            "LOCK_SCREEN": self._exec_lock_screen,
            "OPEN_FOLDER": self._exec_open_folder,
            "OPEN_SETTINGS": self._exec_open_settings,
            "OPEN_TASK_MANAGER": self._exec_open_task_manager,
            "EMPTY_RECYCLE_BIN": self._exec_empty_recycle_bin,
            "CLOSE_ACTIVE_WINDOW": self._exec_close_active_window,
            "CLOSE_APP": self._exec_close_app,
            "PRESS_ENTER": self._exec_press_enter,
            "PRESS_BACKSPACE": self._exec_press_backspace,
            "PRESS_TAB": self._exec_press_tab,
            "SET_TIMER": self._exec_set_timer,
            "CANCEL_TIMER": self._exec_cancel_timer,

        }
        self._reply_handlers: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], str]] = {
            "VOLUME_UP": self._reply_volume_up,
            "VOLUME_DOWN": self._reply_volume_down,
            "MUTE": self._reply_mute,
            "UNMUTE": self._reply_unmute,
            "SET_VOLUME": self._reply_set_volume,
            "AUDIO_OUTPUT_TOGGLE": self._reply_audio_output_toggle,
            "AUDIO_OUTPUT_HEADPHONES": self._reply_audio_output_headphones,
            "AUDIO_OUTPUT_SPEAKERS": self._reply_audio_output_speakers,
            "SCREENSHOT": self._reply_screenshot,
            "OPEN_APP": self._reply_open_app,
            "OPEN_URL": self._reply_open_url,
            "SEARCH_WEB": self._reply_search_web,
            "SEARCH_YOUTUBE": self._reply_search_youtube,
            "MUSIC_PLAY": self._reply_music_play,
            "MUSIC_PAUSE": self._reply_music_pause,
            "MUSIC_NEXT": self._reply_music_next,
            "MUSIC_PREV": self._reply_music_prev,
            "MUSIC_RESTART": self._reply_music_restart,
            "LOCK_SCREEN": self._reply_lock_screen,
            "OPEN_FOLDER": self._reply_open_folder,
            "OPEN_SETTINGS": self._reply_open_settings,
            "OPEN_TASK_MANAGER": self._reply_open_task_manager,
            "SHOW_IP": self._reply_show_ip,
            "EMPTY_RECYCLE_BIN": self._reply_empty_recycle_bin,
            "WEATHER": self._reply_weather,
            "CLOSE_ACTIVE_WINDOW": self._reply_close_active_window,
            "CLOSE_APP": self._reply_close_app,
            "PRESS_ENTER": self._reply_press_enter,
            "PRESS_BACKSPACE": self._reply_press_backspace,
            "PRESS_TAB": self._reply_press_tab,
            "ACTIVE_WINDOW_INFO": self._reply_active_window_info,
            "SET_TIMER": self._reply_set_timer,
            "TIMER_STATUS": self._reply_timer_status,
            "CANCEL_TIMER": self._reply_cancel_timer,
        }

    def _reply_volume_up(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if self._audio is None:
            return "Управление звуком недоступно на этом компьютере."
        return meta.get("say") or "Делаю громче."

    def _reply_volume_down(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if self._audio is None:
            return "Управление звуком недоступно на этом компьютере."
        return meta.get("say") or "Делаю тише."

    def _reply_mute(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if self._audio is None:
            return "Управление звуком недоступно на этом компьютере."
        return meta.get("say") or "Выключаю звук."

    def _reply_unmute(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if self._audio is None:
            return "Управление звуком недоступно на этом компьютере."
        return meta.get("say") or "Включаю звук."

    def _reply_set_volume(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if self._audio is None:
            return "Управление звуком недоступно на этом компьютере."

        v = slots.get("volume")
        if v is None:
            return "Скажи число от 0 до 100."

        return meta.get("say") or f"Ставлю громкость на {v} процентов."

    def _reply_audio_output_toggle(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if self._audio_output is None:
            return "Переключение устройства звука недоступно на этом компьютере."
        return "Переключаю устройство вывода звука"

    def _reply_audio_output_headphones(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if self._audio_output is None:
            return "Переключение устройства звука недоступно на этом компьютере."
        return "Переключаю звук на наушники"

    def _reply_audio_output_speakers(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if self._audio_output is None:
            return "Переключение устройства звука недоступно на этом компьютере."
        return "Переключаю звук на колонки"

    def _reply_screenshot(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "Делаю скриншот."

    def _reply_open_app(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "..."

    def _reply_open_url(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if not slots.get("url"):
            return "Скажи, какой сайт открыть."
        return meta.get("say") or "Открываю сайт."

    def _reply_search_web(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if not slots.get("query"):
            return "Скажи, что именно найти."
        return meta.get("say") or "Ищу в интернете."

    def _reply_search_youtube(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if not slots.get("query"):
            return "Скажи, что именно найти на ютубе."
        return meta.get("say") or "Ищу на ютубе."

    def _reply_music_play(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "..."

    def _reply_music_pause(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "..."

    def _reply_music_next(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "..."

    def _reply_music_prev(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "..."

    def _reply_music_restart(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "..."

    def _reply_music_stop(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "..."

    def _reply_lock_screen(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "Блокирую экран."

    def _reply_open_folder(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if not slots.get("folder"):
            return "Скажи, какую папку открыть."
        return meta.get("say") or "Открываю папку."

    def _reply_open_settings(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "Открываю настройки."

    def _reply_open_task_manager(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "Открываю диспетчер задач."

    def _reply_show_ip(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        scope = str(slots.get("ip_scope") or "local").strip().lower()

        try:
            local_ip = self._get_local_ip()
        except Exception:
            local_ip = ""

        if scope == "public":
            try:
                public_ip = self._get_public_ip()
                if public_ip:
                    return f"Внешний IP: {public_ip}"
            except Exception:
                pass
            return "Не получилось определить внешний IP."

        if local_ip:
            return f"Локальный IP: {local_ip}"

        return "Не получилось определить локальный IP."

    def _reply_empty_recycle_bin(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "Очищаю корзину."

    def _reply_weather(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        city = str(slots.get("city") or "").strip()
        if not city:
            return "Скажи, в каком городе посмотреть погоду."

        try:
            weather = self._weather_service.get_current_weather(city)
        except Exception:
            return f"Не получилось узнать погоду для города {city}."

        temp = round(weather.temperature_c)
        feels = round(weather.apparent_temperature_c)
        wind = round(weather.wind_speed_ms)

        return (
            f"Сейчас в {weather.place} {weather.description}. "
            f"Температура {temp} градусов, ощущается как {feels}. "
            f"Ветер {wind} метров в секунду."
        )

    def _reply_close_active_window(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "Закрываю активное окно."

    def _reply_close_app(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        if not slots.get("app"):
            return "Скажи, какую программу закрыть."
        return meta.get("say") or "Закрываю программу."

    def _reply_press_enter(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "Нажимаю enter."

    def _reply_press_backspace(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "Удаляю символ."

    def _reply_press_tab(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        return meta.get("say") or "Нажимаю tab."

    def _reply_active_window_info(self, meta: Dict[str, Any], slots: Dict[str, Any]) -> str:
        try:
            info = self._window_context_service.get_active_window_info()
        except Exception:
            info = None

        if not info:
            return "Не получилось определить активное окно."

        title = (info.title or "").strip()
        class_name = (info.class_name or "").strip()
        process_name = (info.process_name or "").strip()

        parts = []

        if title:
            parts.append(f'активно окно "{title}"')
        else:
            parts.append("активно окно без заголовка")

        if process_name:
            parts.append(f"процесс {process_name}")

        if class_name:
            parts.append(f"класс окна {class_name}")

        return "Сейчас " + ". ".join(parts) + "."

    def _reply_set_timer(
        self,
        meta: Dict[str, Any],
        slots: Dict[str, Any],
    ) -> str:
        if self._timer_service is None:
            return "Таймер недоступен."

        duration_value = slots.get(
            "duration_seconds"
        )

        if duration_value is None:
            return (
                "Скажи, на какое время "
                "поставить таймер."
            )

        try:
            duration_seconds = int(
                duration_value
            )
        except (TypeError, ValueError):
            return (
                "Скажи, на какое время "
                "поставить таймер."
            )

        duration_text = format_duration_ru(
            duration_seconds,
            grammatical_case="accusative",
        )

        try:
            replacing = (
                self._timer_service
                .status()
                .active
            )
        except Exception:
            replacing = False

        if replacing:
            return (
                "Заменяю активный таймер. "
                f"Новый таймер на "
                f"{duration_text}."
            )

        return (
            f"Ставлю таймер на "
            f"{duration_text}."
        )

    def _reply_timer_status(
        self,
        meta: Dict[str, Any],
        slots: Dict[str, Any],
    ) -> str:
        _ = meta
        _ = slots

        if self._timer_service is None:
            return "Таймер недоступен."

        snapshot = self._timer_service.status()

        if not snapshot.active:
            return "Активного таймера нет."

        remaining_text = format_duration_ru(
            snapshot.remaining_seconds
        )

        return (
            "До окончания таймера осталось "
            f"{remaining_text}."
        )

    def _reply_cancel_timer(
        self,
        meta: Dict[str, Any],
        slots: Dict[str, Any],
    ) -> str:
        _ = meta
        _ = slots

        if self._timer_service is None:
            return "Таймер недоступен."

        if not self._timer_service.status().active:
            return "Активного таймера нет."

        return "Отменяю таймер."

    def handle(self, meta: Dict[str, Any]) -> str:
        """
        Возвращает текст, который ассистент должен сказать.
        """
        intent = (meta.get("intent") or "").upper()
        slots = meta.get("slots") or {}

        handler: Optional[Callable[[Dict[str, Any], Dict[str, Any]], str]] = self._reply_handlers.get(intent)
        if handler:
            return handler(meta, slots)

        return meta.get("say") or "..."

    def _open_app(self, app: str) -> None:
        app_code = str(app or "").lower().strip()
        if not app_code:
            return

        command = get_app_open_command(app_code)
        if not command:
            return

        try:
            subprocess.Popen(list(command))
        except Exception:
            return

    def _resolve_folder_path(self, folder_code: str) -> Optional[str]:
        home = Path.home()
        path_kind = get_folder_path_kind(str(folder_code or "").strip())

        mapping = {
            "downloads": home / "Downloads",
            "desktop": home / "Desktop",
            "documents": home / "Documents",
            "pictures": home / "Pictures",
        }

        path = mapping.get(path_kind)
        if path is None:
            return None

        return str(path)

    def _resolve_settings_uri(self, section_code: str) -> str:
        section = str(section_code or "system").strip()
        return get_settings_section_uri(section)

    def _get_local_ip(self) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
        finally:
            s.close()

    def _get_public_ip(self) -> str:
        with urllib.request.urlopen("https://api.ipify.org", timeout=4) as resp:
            return resp.read().decode("utf-8", errors="replace").strip()

    def _get_foreground_window(self) -> int:
        try:
            return int(ctypes.windll.user32.GetForegroundWindow())
        except Exception:
            return 0

    def _get_window_class_name(self, hwnd: int) -> str:
        if not hwnd:
            return ""

        buf = ctypes.create_unicode_buffer(256)
        try:
            ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
            return buf.value or ""
        except Exception:
            return ""

    def _get_window_text(self, hwnd: int) -> str:
        if not hwnd:
            return ""

        buf = ctypes.create_unicode_buffer(512)
        try:
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
            return buf.value or ""
        except Exception:
            return ""

    def _is_protected_shell_window(self, hwnd: int) -> bool:
        class_name = self._get_window_class_name(hwnd)

        # Не трогаем рабочий стол и панель задач.
        protected_classes = {
            "Progman",
            "WorkerW",
            "Shell_TrayWnd",
        }
        return class_name in protected_classes

    def _app_image_names(self, app_code: str) -> list[str]:
        return list(get_app_image_names(str(app_code or "").strip().lower()))

    def _app_window_title_patterns(self, app_code: str) -> list[str]:
        return list(get_app_title_patterns(str(app_code or "").strip().lower()))

    def _get_window_process_image(self, hwnd: int) -> str:
        if not hwnd:
            return ""

        pid = ctypes.c_ulong(0)
        try:
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return ""

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            hproc = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not hproc:
                return ""

            try:
                buf_len = ctypes.c_ulong(1024)
                buf = ctypes.create_unicode_buffer(1024)
                ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
                    hproc, 0, buf, ctypes.byref(buf_len)
                )
                if not ok:
                    return ""
                return os.path.basename(buf.value).lower()
            finally:
                ctypes.windll.kernel32.CloseHandle(hproc)
        except Exception:
            return ""

    def _close_windows_by_image_names(self, image_names: list[str]) -> bool:
        if not image_names:
            return False

        image_names_lc = {x.lower() for x in image_names if x}
        closed_any = False
        hwnds: list[int] = []

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_proc(hwnd, lparam):
            try:
                if not ctypes.windll.user32.IsWindowVisible(hwnd):
                    return True
                if self._is_protected_shell_window(hwnd):
                    return True

                img = self._get_window_process_image(int(hwnd))
                if img and img in image_names_lc:
                    hwnds.append(int(hwnd))
            except Exception:
                pass
            return True

        try:
            ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_proc), 0)
        except Exception:
            return False

        WM_CLOSE = 0x0010
        for hwnd in hwnds:
            try:
                ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                closed_any = True
            except Exception:
                pass

        return closed_any

    def _close_windows_by_title_patterns(self, patterns: list[str]) -> bool:
        if not patterns:
            return False

        pats = [p.lower() for p in patterns if p]
        closed_any = False
        hwnds: list[int] = []

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_proc(hwnd, lparam):
            try:
                if not ctypes.windll.user32.IsWindowVisible(hwnd):
                    return True
                if self._is_protected_shell_window(hwnd):
                    return True

                title = self._get_window_text(int(hwnd)).lower()
                if not title:
                    return True

                for pat in pats:
                    if pat in title:
                        hwnds.append(int(hwnd))
                        break
            except Exception:
                pass
            return True

        try:
            ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_proc), 0)
        except Exception:
            return False

        WM_CLOSE = 0x0010
        for hwnd in hwnds:
            try:
                ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                closed_any = True
            except Exception:
                pass

        return closed_any

    def _close_explorer_windows(self) -> bool:
        closed_any = False
        hwnds: list[int] = []

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def enum_proc(hwnd, lparam):
            try:
                if not ctypes.windll.user32.IsWindowVisible(hwnd):
                    return True

                class_name = self._get_window_class_name(int(hwnd))
                if class_name in {"CabinetWClass", "ExploreWClass"}:
                    hwnds.append(int(hwnd))
            except Exception:
                pass
            return True

        try:
            ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_proc), 0)
        except Exception:
            return False

        WM_CLOSE = 0x0010
        for hwnd in hwnds:
            try:
                ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                closed_any = True
            except Exception:
                pass

        return closed_any

    def _terminate_by_image_names(self, image_names: list[str]) -> bool:
        ok_any = False

        for image in image_names:
            if not image:
                continue

            try:
                rc = subprocess.run(
                    ["taskkill", "/IM", image, "/T"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                ).returncode

                if rc != 0:
                    rc = subprocess.run(
                        ["taskkill", "/F", "/IM", image, "/T"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    ).returncode

                if rc == 0:
                    ok_any = True
            except Exception:
                pass

        return ok_any

    def _exec_volume_up(self, slots: Dict[str, Any]) -> None:
        if self._audio is None:
            return

        try:
            self._audio.change_volume(+self._volume_step)
        except Exception as e:
            log_exception("actions.volume_up", e, intent="VOLUME_UP", slots=slots)

    def _exec_volume_down(self, slots: Dict[str, Any]) -> None:
        if self._audio is None:
            return

        try:
            self._audio.change_volume(-self._volume_step)
        except Exception as e:
            log_exception("actions.volume_down", e, intent="VOLUME_DOWN", slots=slots)

    def _exec_mute(self, slots: Dict[str, Any]) -> None:
        if self._audio is None:
            return

        try:
            self._audio.mute()
        except Exception as e:
            log_exception("actions.mute", e, intent="MUTE", slots=slots)

    def _exec_unmute(self, slots: Dict[str, Any]) -> None:
        if self._audio is None:
            return

        try:
            self._audio.unmute()
        except Exception as e:
            log_exception("actions.unmute", e, intent="UNMUTE", slots=slots)

    def _exec_set_volume(self, slots: Dict[str, Any]) -> None:
        if self._audio is None:
            return

        v = slots.get("volume")
        if v is None:
            return

        try:
            self._audio.set_volume(int(v))
        except Exception as e:
            log_exception("actions.set_volume", e, intent="SET_VOLUME", slots=slots)

    def _exec_open_app(self, slots: Dict[str, Any]) -> None:
        app = (slots.get("app") or "").lower().strip()
        if app:
            self._open_app(app)

    def _exec_open_url(self, slots: Dict[str, Any]) -> None:
        url = str(slots.get("url") or "").strip()
        if url:
            try:
                webbrowser.open(url, new=2)
            except Exception:
                pass

    def _exec_search_web(self, slots: Dict[str, Any]) -> None:
        query = str(slots.get("query") or "").strip()
        if query:
            try:
                url = f"https://www.google.com/search?q={quote_plus(query)}"
                webbrowser.open(url, new=2)
            except Exception:
                pass

    def _exec_search_youtube(self, slots: Dict[str, Any]) -> None:
        query = str(slots.get("query") or "").strip()
        if query:
            try:
                url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
                webbrowser.open(url, new=2)
            except Exception:
                pass

    def _exec_screenshot(self, slots: Dict[str, Any]) -> None:
        try:
            self._screenshot_service.make_screenshot()
        except Exception as e:
            log_exception("actions.screenshot", e, intent="SCREENSHOT")

    def _exec_audio_output_toggle(self, slots: Dict[str, Any]) -> None:
        try:
            if self._audio_output is not None:
                self._audio_output.toggle()
        except Exception as e:
            print(f"[AUDIO_OUTPUT] execute failed: {e}")
            log_exception("actions.audio_output_execute", e, intent="AUDIO_OUTPUT_TOGGLE", slots=slots)

    def _exec_audio_output_headphones(self, slots: Dict[str, Any]) -> None:
        try:
            if self._audio_output is not None:
                self._audio_output.set_headphones()
        except Exception as e:
            print(f"[AUDIO_OUTPUT] execute failed: {e}")
            log_exception("actions.audio_output_execute", e, intent="AUDIO_OUTPUT_HEADPHONES", slots=slots)

    def _exec_audio_output_speakers(self, slots: Dict[str, Any]) -> None:
        try:
            if self._audio_output is not None:
                self._audio_output.set_speakers()
        except Exception as e:
            print(f"[AUDIO_OUTPUT] execute failed: {e}")
            log_exception("actions.audio_output_execute", e, intent="AUDIO_OUTPUT_SPEAKERS", slots=slots)

    def _exec_music_play(self, slots: Dict[str, Any]) -> None:
        try:
            mc = MediaControl()
            mc.play_pause()
        except Exception:
            pass

    def _exec_music_pause(self, slots: Dict[str, Any]) -> None:
        try:
            mc = MediaControl()
            mc.play_pause()
        except Exception:
            pass

    def _exec_music_next(self, slots: Dict[str, Any]) -> None:
        try:
            mc = MediaControl()
            mc.next_track()
        except Exception:
            pass

    def _exec_music_prev(self, slots: Dict[str, Any]) -> None:
        try:
            mc = MediaControl()
            mc.prev_track()
            if self._music_prev_double:
                time.sleep(max(0.05, self._music_prev_double_delay))
                mc.prev_track()
        except Exception:
            pass

    def _exec_music_restart(self, slots: Dict[str, Any]) -> None:
        try:
            mc = MediaControl()
            mc.prev_track()
        except Exception:
            pass

    def _exec_lock_screen(self, slots: Dict[str, Any]) -> None:
        try:
            ctypes.windll.user32.LockWorkStation()
        except Exception:
            pass

    def _exec_open_folder(self, slots: Dict[str, Any]) -> None:
        folder_code = str(slots.get("folder") or "").strip()
        if not folder_code:
            return

        path = self._resolve_folder_path(folder_code)
        if not path:
            return

        try:
            os.startfile(path)
        except Exception:
            pass

    def _exec_open_settings(self, slots: Dict[str, Any]) -> None:
        section_code = str(slots.get("section") or "system").strip()
        uri = self._resolve_settings_uri(section_code)

        try:
            os.startfile(uri)
        except Exception:
            pass

    def _exec_open_task_manager(self, slots: Dict[str, Any]) -> None:
        try:
            subprocess.Popen(["taskmgr.exe"])
        except Exception:
            pass

    def _exec_empty_recycle_bin(self, slots: Dict[str, Any]) -> None:
        try:
            # без подтверждения, без прогресс-бара, без звука
            flags = 0x00000001 | 0x00000002 | 0x00000004
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
        except Exception:
            pass

    def _exec_close_active_window(self, slots: Dict[str, Any]) -> None:
        hwnd = self._get_foreground_window()
        if not hwnd:
            return

        if self._is_protected_shell_window(hwnd):
            return

        try:
            WM_CLOSE = 0x0010
            ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        except Exception:
            pass

    def _exec_close_app(self, slots: Dict[str, Any]) -> None:
        app_code = str(slots.get("app") or "").strip().lower()
        if not app_code:
            return

        # Важный special-case: не убиваем explorer.exe как shell,
        # закрываем только конкретные окна Проводника.
        if get_app_close_strategy(app_code) == "explorer_windows_only":
            self._close_explorer_windows()
            return

        image_names = self._app_image_names(app_code)
        title_patterns = self._app_window_title_patterns(app_code)

        # Сначала пытаемся закрыть окна штатно по image name.
        closed_any = self._close_windows_by_image_names(image_names)
        if closed_any:
            return

        # Потом fallback по заголовку окна (важно для Calculator/UWP и похожих случаев).
        closed_any = self._close_windows_by_title_patterns(title_patterns)
        if closed_any:
            return

        # Если окон не нашли, fallback на завершение процесса.
        self._terminate_by_image_names(image_names)

    def _exec_press_enter(self, slots: Dict[str, Any]) -> None:
        try:
            self._typing_service.press_enter()
        except Exception:
            pass

    def _exec_press_backspace(self, slots: Dict[str, Any]) -> None:
        try:
            self._typing_service.press_backspace()
        except Exception:
            pass

    def _exec_press_tab(self, slots: Dict[str, Any]) -> None:
        try:
            self._typing_service.press_tab()
        except Exception:
            pass

    def _exec_set_timer(
        self,
        slots: Dict[str, Any],
    ) -> None:
        if self._timer_service is None:
            return

        duration_value = slots.get(
            "duration_seconds"
        )

        if duration_value is None:
            return

        duration_seconds = int(
            duration_value
        )

        # Ошибку намеренно не подавляем:
        # command_runtime должен записать
        # action failure и не произнести ложный успех.
        self._timer_service.start(
            duration_seconds
        )

    def _exec_cancel_timer(
        self,
        slots: Dict[str, Any],
    ) -> None:
        _ = slots

        if self._timer_service is None:
            return

        self._timer_service.cancel()

    def execute(self, meta: Dict[str, Any]) -> None:
        """
        Фактическое выполнение действия ПОСЛЕ TTS.
        """
        intent = (meta.get("intent") or "").upper()
        slots = meta.get("slots") or {}

        handler: Optional[Callable[[Dict[str, Any]], None]] = self._execute_handlers.get(intent)
        if handler:
            handler(slots)