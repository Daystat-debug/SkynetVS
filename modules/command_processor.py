from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from modules.command_learning import log_command_observation
from modules.command_outcome import classify_command_outcome
from modules.command_runtime import handle_command_runtime
from modules.command_understanding import understand_command_text
from modules.hotword_utils import norm_text


SayFunc = Callable[..., float]
SayInterruptibleFunc = Callable[..., float]
ReplyTextFunc = Callable[[Mapping[str, Any]], str]
ModeNameFunc = Callable[[], str]
CancelTimerFunc = Callable[[], None]
PrintFunc = Callable[[str], None]


@dataclass(frozen=True)
class CommandProcessorResult:
    meta: dict[str, Any]
    raw_text: str
    final_text: str
    last_tts_end: float | None
    reason: str


class CommandProcessor:
    """
    Обрабатывает одну текстовую команду.

    Делает:
      - raw text normalization;
      - command understanding;
      - outcome classification;
      - command observation logging;
      - command runtime execution.

    Не делает:
      - STT event loop;
      - hotword handling;
      - command window state machine;
      - dictation phrase handling.
    """

    def __init__(
        self,
        *,
        router: Any,
        logger: Any,
        whisper: Any,
        stt: Any,
        tts: Any,
        settings: Any,
        learning_memory: Any,
        mode_manager: Any,
        say_func: SayFunc,
        say_interruptible_func: SayInterruptibleFunc,
        reply_text_func: ReplyTextFunc,
        current_mode_name_func: ModeNameFunc,
        cancel_cmd_timer_func: CancelTimerFunc,
        timer_actions: Any | None = None,
        volume_actions: Any | None = None,
        print_func: PrintFunc | None = print,
    ) -> None:
        self._router = router
        self._logger = logger
        self._whisper = whisper
        self._stt = stt
        self._tts = tts
        self._settings = settings
        self._learning_memory = learning_memory
        self._mode_manager = mode_manager
        self._say_func = say_func
        self._say_interruptible_func = say_interruptible_func
        self._reply_text_func = reply_text_func
        self._current_mode_name_func = current_mode_name_func
        self._cancel_cmd_timer_func = cancel_cmd_timer_func
        self._timer_actions = timer_actions
        self._volume_actions = volume_actions
        self._print_func = print_func

    def _print(self, text: str) -> None:
        if self._print_func is not None:
            self._print_func(text)

    def process(
        self,
        command_text: str,
        *,
        immediate_label: str,
    ) -> CommandProcessorResult:
        raw_text_in = norm_text(command_text)

        if not raw_text_in:
            meta = {
                "intent": None,
                "confidence": 0.0,
                "slots": {},
                "say": "",
            }

            return CommandProcessorResult(
                meta=meta,
                raw_text="",
                final_text="",
                last_tts_end=None,
                reason="empty_command",
            )

        if immediate_label == "immediate":
            self._print(f"✅ команда сразу: {raw_text_in}")
        else:
            self._print(f"✅ команда: {raw_text_in}")

        understanding = understand_command_text(
            raw_text_in,
            router=self._router,
            logger=self._logger,
            whisper=self._whisper,
            stt=self._stt,
            accept_conf=self._settings.nlu_accept_conf,
            whisper_trigger_conf=self._settings.whisper_trigger_conf,
            hotwords=self._settings.hotwords,
            print_func=self._print_func,
        )

        raw_text_in = understanding.raw_text
        text_in = understanding.final_text
        meta = understanding.meta
        decision = understanding.decision
        outcome = classify_command_outcome(meta, decision)

        log_command_observation(
            learning_memory=self._learning_memory,
            raw_text=raw_text_in,
            final_text=text_in,
            meta=meta,
            mode=self._current_mode_name_func(),
            accepted=decision.accepted,
            immediate_label=immediate_label,
            missing_slots=decision.missing_slots,
        )

        runtime_result = handle_command_runtime(
            raw_text=raw_text_in,
            final_text=text_in,
            meta=meta,
            decision=decision,
            outcome=outcome,
            learning_memory=self._learning_memory,
            logger=self._logger,
            router=self._router,
            mode_manager=self._mode_manager,
            stt=self._stt,
            tts=self._tts,
            say_func=self._say_func,
            say_interruptible_func=self._say_interruptible_func,
            reply_text_func=self._reply_text_func,
            current_mode_name_func=self._current_mode_name_func,
            cancel_cmd_timer_func=self._cancel_cmd_timer_func,
            timer_actions=self._timer_actions,
            volume_actions=self._volume_actions,
        )

        return CommandProcessorResult(
            meta=runtime_result.meta,
            raw_text=raw_text_in,
            final_text=text_in,
            last_tts_end=runtime_result.last_tts_end,
            reason=runtime_result.reason,
        )