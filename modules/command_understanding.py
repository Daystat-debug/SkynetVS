from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Protocol

from modules.command_decision import CommandDecision, build_command_decision
from modules.entity_resolver import resolve_entities
from modules.hotword_utils import norm_text
from modules.nlu import predict
from modules.stt_refinement import maybe_refine_with_whisper
from modules.text_normalizer import normalize_command_text
from modules.stt_diagnostics import build_stt_diagnostic_payload
from modules.understanding_helpers import (
    needs_normalization_retry,
    should_use_retry_result,
)


PrintFunc = Callable[[str], None]


class EventLogger(Protocol):
    def event(self, kind: str, payload: dict[str, Any]) -> None:
        ...


class PreprocessRouter(Protocol):
    def preprocess(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        ...


@dataclass(frozen=True)
class CommandUnderstandingResult:
    raw_text: str
    final_text: str
    meta: Dict[str, Any]
    decision: CommandDecision


def _log_event(
    logger: EventLogger | None,
    kind: str,
    payload: dict[str, Any],
) -> None:
    if logger is not None:
        logger.event(kind, payload)


def _print(
    print_func: PrintFunc | None,
    text: str,
) -> None:
    if print_func is not None:
        print_func(text)


def understand_command_text(
    command_text: str,
    *,
    router: PreprocessRouter,
    logger: EventLogger | None,
    whisper: Any,
    stt: Any,
    accept_conf: float,
    whisper_trigger_conf: float,
    print_func: PrintFunc | None = print,
) -> CommandUnderstandingResult:
    """
    Понимание текстовой команды.

    Делает:
      - normalize raw command text;
      - NLU predict;
      - normalization retry;
      - optional Whisper refinement;
      - entity resolver;
      - router preprocess;
      - command decision.

    Не делает:
      - learning log;
      - TTS;
      - confirmation;
      - action execution.
    """
    raw_text_in = norm_text(command_text)

    if not raw_text_in:
        meta: Dict[str, Any] = {
            "intent": None,
            "confidence": 0.0,
            "slots": {},
            "say": "",
            "_text": "",
        }
        decision = build_command_decision(
            meta,
            accept_conf=accept_conf,
        )

        return CommandUnderstandingResult(
            raw_text=raw_text_in,
            final_text=raw_text_in,
            meta=meta,
            decision=decision,
        )

    text_in = raw_text_in

    meta = predict(text_in)
    meta["_text"] = text_in

    if needs_normalization_retry(raw_text_in, meta):
        normalized_text, was_normalized = normalize_command_text(raw_text_in)

        if was_normalized and normalized_text != raw_text_in:
            meta_retry = predict(normalized_text)
            meta_retry["_text"] = normalized_text

            _log_event(
                logger,
                "nlu_retry",
                {
                    "from": raw_text_in,
                    "to": normalized_text,
                    "meta_before": meta,
                    "meta_after": meta_retry,
                },
            )

            if should_use_retry_result(
                meta,
                meta_retry,
                accept_conf=accept_conf,
            ):
                text_in = normalized_text
                meta = meta_retry

                _log_event(
                    logger,
                    "text_normalized",
                    {
                        "from": raw_text_in,
                        "to": normalized_text,
                    },
                )

    _print(
        print_func,
        f"[NLU] intent={meta.get('intent')} "
        f"conf={meta.get('confidence', 0.0):.2f} "
        f"slots={meta.get('slots')}",
    )

    _log_event(
        logger,
        "nlu",
        {
            "text": text_in,
            "meta": meta,
        },
    )

    text_before_refinement = text_in
    meta_before_refinement = dict(meta)

    refinement = maybe_refine_with_whisper(
        original_text=text_in,
        meta=meta,
        whisper=whisper,
        stt=stt,
        trigger_conf=whisper_trigger_conf,
        predict_func=predict,
        norm_func=norm_text,
    )

    if refinement.error:
        _print(print_func, f"[WHISPER] refine failed: {refinement.error}")

    if refinement.candidate_text and refinement.candidate_meta is not None:
        _print(print_func, f"[WHISPER] '{text_in}' -> '{refinement.candidate_text}'")
        _print(
            print_func,
            "[NLU] refined "
            f"intent={refinement.candidate_meta.get('intent')} "
            f"conf={refinement.candidate_meta.get('confidence', 0.0):.2f} "
            f"slots={refinement.candidate_meta.get('slots')}",
        )

    _log_event(
        logger,
        "stt_diagnostic",
        build_stt_diagnostic_payload(
            raw_text=raw_text_in,
            text_before_refinement=text_before_refinement,
            final_text=refinement.text,
            meta_before_refinement=meta_before_refinement,
            meta_after_refinement=refinement.meta,
            refinement=refinement,
            stt=stt,
        ),
    )

    text2 = refinement.text
    meta = refinement.meta

    if text2 != text_in:
        _log_event(
            logger,
            "whisper_refine",
            {
                "from": text_in,
                "to": text2,
                "meta": meta,
            },
        )

        text_in = text2
        meta["_text"] = text_in

    meta_before_resolve = {
        "intent": meta.get("intent"),
        "slots": dict(meta.get("slots") or {}),
    }

    meta = resolve_entities(text_in, meta)

    if (meta.get("slots") or {}) != meta_before_resolve.get("slots", {}):
        _log_event(
            logger,
            "entity_resolved",
            {
                "text": text_in,
                "intent": meta.get("intent"),
                "slots_before": meta_before_resolve.get("slots", {}),
                "slots_after": meta.get("slots") or {},
            },
        )

    meta_before = dict(meta)
    meta = router.preprocess(meta)

    if meta is not meta_before and meta.get("_from_history"):
        _log_event(
            logger,
            "router_preprocess",
            {
                "from": meta_before.get("_text"),
                "to_intent": meta.get("intent"),
                "from_history": True,
            },
        )

    decision = build_command_decision(
        meta,
        accept_conf=accept_conf,
    )

    return CommandUnderstandingResult(
        raw_text=raw_text_in,
        final_text=text_in,
        meta=meta,
        decision=decision,
    )