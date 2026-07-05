# /modules/router.py

from __future__ import annotations

import re
from typing import Dict, Any, Optional

from modules.actions import Actions
from modules.dialog_state import DialogState
from modules.config import Settings


class Router:
    """
    Router = слой оркестрации.

    Решает:
      - какой текст говорить через Actions.handle(...)
      - что выполнять через Actions.execute(...)

    Также держит минимальную историю действий для команд:
      - "ещё"
      - "ещё раз"
      - "снова"
      - "повтори"

    Важно:
      "повтори" здесь пока означает повторить последнее repeatable-действие,
      а не повторить последнюю фразу ассистента.
    """

    def __init__(self, actions: Actions, *, settings: Optional[Settings] = None):
        self._actions = actions
        self._settings = settings or Settings.from_env()
        self._mode = self._settings.exec_mode
        self._state = DialogState()
        self._repeat_context_sec = self._settings.repeat_context_sec

        # Интенты, которые безопасно/осмысленно повторять по "ещё/повтори".
        # OPEN_APP намеренно исключён, чтобы "ещё" не открывало повторно приложения.
        self._repeatable_intents = {
            "VOLUME_UP",
            "VOLUME_DOWN",
            "MUTE",
            "UNMUTE",
            "SET_VOLUME",
            "MUSIC_PLAY",
            "MUSIC_PAUSE",
            "MUSIC_NEXT",
            "MUSIC_PREV",
            "MUSIC_RESTART",
        }

    @property
    def mode(self) -> str:
        return self._mode

    def _norm(self, s: str) -> str:
        return " ".join((s or "").lower().split())

    def _is_repeat_cmd(self, text: str) -> bool:
        """
        Детектор простых repeat-команд.
        Работает поверх NLU, чтобы "ещё/повтори" не нужно было тащить в intents.json.
        """
        t = self._norm(text)
        return bool(re.fullmatch(r"(еще|ещё|ещё раз|еще раз|повтори|повтор|снова)", t))

    def _repeat_variant_intent(self, text: str) -> str | None:
        """
        Быстрые уточнённые repeat-команды:
          - "ещё громче" -> VOLUME_UP
          - "ещё тише"   -> VOLUME_DOWN
        """
        t = self._norm(text)

        if t in ("еще громче", "ещё громче"):
            return "VOLUME_UP"

        if t in ("еще тише", "ещё тише"):
            return "VOLUME_DOWN"

        return None

    def _already_resolved(self, meta: Dict[str, Any]) -> bool:
        """
        Защита от повторного преобразования одного и того же meta.

        main.py может вызвать:
          router.preprocess(meta)
          router.reply(meta)
          router.execute(meta)

        Поэтому Router не должен второй раз преобразовывать уже обработанную meta.
        """
        return bool(
            meta.get("_from_history")
            or meta.get("_from_repeat_variant")
        )

    def _history_meta(self, last: Dict[str, Any], *, current_text: str) -> Dict[str, Any]:
        """
        Создаёт meta из истории, но не тащит старый _text.

        Старый intent/slots нужны для выполнения,
        а текущий текст нужен для логов и отладки.
        """
        m = dict(last)

        old_confidence = m.get("confidence")

        m["_text"] = current_text
        m["_from_history"] = True
        m["_history_intent"] = (last.get("intent") or "").upper()
        m["_original_confidence"] = old_confidence

        # Repeat из истории — это уже не NLU-уверенность.
        # Мы доверяем ему, потому что повторяем только allowlist-интенты.
        m["confidence"] = 1.0

        m.setdefault("slots", {})
        return m

    def _variant_meta(self, meta: Dict[str, Any], *, intent: str) -> Dict[str, Any]:
        """
        Создаёт meta для быстрых команд вроде "ещё громче".
        """
        m = dict(meta)
        m["intent"] = intent
        m["confidence"] = 1.0
        m.setdefault("slots", {})
        m["_from_repeat_variant"] = True
        return m

    def _clean_meta_for_history(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        В историю нельзя складывать служебные transient-флаги.
        """
        m = dict(meta)

        for key in (
            "_from_history",
            "_from_repeat_variant",
            "_history_intent",
            "_original_confidence",
        ):
            m.pop(key, None)

        return m

    def _resolve_meta(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Преобразует meta для repeat-команд.

        Примеры:
          - "ещё громче" -> VOLUME_UP
          - "ещё тише"   -> VOLUME_DOWN
          - "ещё"         -> последнее repeatable-действие
          - "повтори"     -> последнее repeatable-действие
        """
        if self._already_resolved(meta):
            return meta

        text = meta.get("_text") or ""
        if not text:
            return meta

        # 1. Уточнённые варианты repeat-команд.
        variant_intent = self._repeat_variant_intent(text)
        if variant_intent:
            return self._variant_meta(meta, intent=variant_intent)

        # 2. Простое "ещё/повтори/снова".
        if self._is_repeat_cmd(text):
            last = self._state.get_last(within_sec=self._repeat_context_sec)

            if last:
                last_intent = (last.get("intent") or "").upper()

                if last_intent in self._repeatable_intents:
                    return self._history_meta(last, current_text=text)

            m = dict(meta)
            m["_repeat_failed"] = True
            m["_repeat_reason"] = "no_recent_repeatable_action"
            return m

        return meta

    def preprocess(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Публичный вход для main.py.

        Позволяет Router'у преобразовать meta до того, как main.py примет решение:
          - accepted / not accepted
          - reply
          - execute
        """
        return self._resolve_meta(meta)

    def reply(self, meta: Dict[str, Any]) -> str:
        meta2 = self._resolve_meta(meta)
        return self._actions.handle(meta2)

    def execute(self, meta: Dict[str, Any]) -> None:
        meta2 = self._resolve_meta(meta)
        intent = (meta2.get("intent") or "").upper()

        if self._mode == "userlike":
            # Задел на будущее:
            # позже сюда можно подключить UI-автоматику через мышь/клавиатуру.
            # Сейчас direct fallback оставлен намеренно.
            pass

        self._actions.execute(meta2)

        # В историю кладём только то, что реально можно безопасно повторять.
        if intent in self._repeatable_intents:
            self._state.remember(self._clean_meta_for_history(meta2))