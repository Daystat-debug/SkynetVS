"""M084: narrow speech-entry control for the already-tested confirmation bridge.

Only an approved, high-confidence START_LEARNING NLU intent (with hotword)
starts a session; this adapter cannot persist/activate a model or execute actions.
"""
from __future__ import annotations

from typing import Any, Callable


class VoiceLearningEntryPort:
    def __init__(
        self,
        *,
        bridge: Any,
        has_hotword: Callable[[str], bool],
        strip_hotword: Callable[[str], str],
        operator_start_intent: str,
        predict_nlu_intent: Callable[[str], dict[str, Any]],
        result_type: type,
        report_start: Callable[[Any], None],
    ) -> None:
        self._bridge = bridge
        self._has_hotword = has_hotword
        self._strip_hotword = strip_hotword
        self._start_intent = operator_start_intent
        self._predict = predict_nlu_intent
        self._result_type = result_type
        self._report_start = report_start

    @property
    def state(self) -> str:
        return self._bridge.state

    def __call__(self, phrase: str, **ordinary_kwargs: Any) -> Any:
        # Active learning always owns the phrase, including "да" and "нет".
        if self._bridge.state != "IDLE":
            return self._bridge(phrase, **ordinary_kwargs)

        # Do not steal ordinary commands, or teach from an unaddressed phrase.
        if not isinstance(phrase, str) or not self._has_hotword(phrase):
            return self._bridge(phrase, **ordinary_kwargs)
        command = self._strip_hotword(phrase).strip().lstrip(" ,.!?:;").strip().casefold()
        command = " ".join(command.split())
        # START_LEARNING is a *trained intent* in the existing intents.json / NLU.
        # No individual phrase is embedded in this adapter. An untrusted or
        # ambiguous NLU result never starts a session.
        try:
            prediction = self._predict(command)
            intent = prediction.get("intent")
            confidence = float(prediction.get("confidence", 0.0))
        except Exception:
            return self._result_type(handled=True, reason="voice_learning_nlu_error")
        if intent != "START_LEARNING" or not (0.65 <= confidence <= 1.0):
            return self._bridge(phrase, **ordinary_kwargs)

        # Never accept the spoken intent, a file path, or arbitrary parameters.
        receipt = self._bridge.begin(self._start_intent)
        try:
            self._report_start(receipt)
        except Exception:
            # Failure cannot fall through to ordinary confirmation/execution.
            return self._result_type(handled=True, reason="voice_learning_start_report_failed")
        return self._result_type(handled=True, reason="voice_learning_start_" + receipt.code.lower())
