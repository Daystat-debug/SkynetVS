"""M082 nonactive bridge between M081 learning and an existing voice-confirmation port.

No STT, TTS, NLU, persistence, model activation, or command execution is owned
by this adapter. Only an operator-driven caller may call ``begin``.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable
import copy


@dataclass(frozen=True)
class BridgeReceipt:
    code: str
    message: str
    candidate_only: bool


class VoiceLearningConfirmationBridge:
    def __init__(
        self,
        *,
        dialogue: Any,
        ordinary_confirmation: Callable[..., Any],
        mode_manager: Any,
        result_type: type,
        has_hotword: Callable[[str], bool],
        strip_hotword: Callable[[str], str],
        report_event: Callable[[Any], None] | None = None,
        persist_confirmed: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        self._dialogue = dialogue
        self._ordinary_confirmation = ordinary_confirmation
        self._mode_manager = mode_manager
        self._result_type = result_type
        self._has_hotword = has_hotword
        self._strip_hotword = strip_hotword
        self._report_event = report_event
        self._persist_confirmed = persist_confirmed
        self._confirmed_candidate_rows: list[dict[str, Any]] = []
        self._events: list[BridgeReceipt] = []

    @property
    def state(self) -> str:
        return self._dialogue.state

    @property
    def confirmed_candidate_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(copy.deepcopy(self._confirmed_candidate_rows))

    @property
    def events(self) -> tuple[BridgeReceipt, ...]:
        return tuple(self._events)

    def begin(self, approved_intent: str) -> BridgeReceipt:
        # Do not steal an already-active confirmation or dictate into a text field.
        if (
            self._mode_manager.is_dictation_mode()
            or self._mode_manager.has_pending_confirmation()
            or self._mode_manager.has_pending_command()
        ):
            return BridgeReceipt("MODE_BUSY", "Сначала заверши текущую команду.", False)
        e = self._dialogue.arm(approved_intent)
        return BridgeReceipt(e.code, e.message, False)

    def __call__(self, phrase: str, **ordinary_kwargs: Any) -> Any:
        # Preserve original behavior and exact kwargs when learning is inactive.
        if self._dialogue.state == "IDLE":
            return self._ordinary_confirmation(phrase, **ordinary_kwargs)

        # An already-active learning session owns the transcript, not the router.
        # The hook is invoked after phrase guards, before ordinary confirmations.
        prepared = self._strip_hotword(phrase) if self._has_hotword(phrase) else phrase
        event = self._dialogue.on_transcript(prepared)
        if not event.consumed:
            return self._result_type(handled=True, reason="voice_learning_unexpected_idle")

        if event.row is not None:
            # Nothing reaches an ordinary action even if persistence fails.
            # The callback is invoked only AFTER an explicit confirmation.
            if self._persist_confirmed is not None:
                try:
                    result = self._persist_confirmed(copy.deepcopy(event.row))
                    if result == "SAVED":
                        event = replace(event, code="EXAMPLE_SAVED_FOR_TRAINING", message=(
                            "Фраза сохранена в очереди обучения. Модель ещё не переобучена."
                        ))
                    elif result in ("ALREADY_RECORDED", "ALREADY_IN_TRAINING"):
                        event = replace(event, code="EXAMPLE_ALREADY_RECORDED", message=(
                            "Эта фраза уже есть в очереди или обучающих примерах. Модель не изменена."
                        ))
                    else:
                        raise RuntimeError("PERSISTENCE_UNEXPECTED_STATUS")
                except Exception as exc:
                    event = replace(event, code="EXAMPLE_PERSIST_FAILED", message=(
                        "Не удалось подтвердить сохранение. Пример не активирован; проверь журнал."
                    ), row=None)
            if event.row is not None:
                self._confirmed_candidate_rows.append(copy.deepcopy(event.row))
        self._events.append(BridgeReceipt(event.code, event.message, event.row is not None))
        if self._report_event is not None:
            try:
                self._report_event(event)
            except Exception:
                # Do not fall through to ordinary confirmation / command execution.
                return self._result_type(handled=True, reason="voice_learning_report_failed")
        return self._result_type(handled=True, reason="voice_learning_" + event.code.lower())
