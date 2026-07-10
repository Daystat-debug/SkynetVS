from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


PredictFunc = Callable[[str], Dict[str, Any]]
NormFunc = Callable[[str], str]
PrepareTextFunc = Callable[[str], str]


@dataclass(frozen=True)
class SttRefinementResult:
    text: str
    meta: Dict[str, Any]
    changed: bool
    reason: str
    candidate_text: Optional[str] = None
    candidate_meta: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    trigger_reason: str = ""


def maybe_refine_with_whisper(
    *,
    original_text: str,
    meta: Dict[str, Any],
    whisper: Any,
    stt: Any,
    trigger_conf: float,
    predict_func: PredictFunc,
    norm_func: NormFunc,
    prepare_candidate_func: Optional[PrepareTextFunc] = None,
    preserve_intent: bool = False,
    skip_refine: bool = False,
    force_refine: bool = False,
    trigger_reason: str = "",
) -> SttRefinementResult:
    """
    Пробует уточнить STT-текст через Whisper, если NLU не уверена.

    Возвращает структуру с итоговым text/meta и диагностикой.
    """
    effective_trigger_reason = trigger_reason or "confidence"
    if skip_refine:
        return SttRefinementResult(
            text=original_text,
            meta=meta,
            changed=False,
            reason="accepted_complete",
            trigger_reason=effective_trigger_reason,
        )
    if whisper is None:
        return SttRefinementResult(
            text=original_text,
            meta=meta,
            changed=False,
            reason="whisper_disabled",
            trigger_reason=effective_trigger_reason,
        )

    conf = float(meta.get("confidence") or 0.0)
    intent = meta.get("intent")

    if not force_refine and intent and conf >= trigger_conf:
        return SttRefinementResult(
            text=original_text,
            meta=meta,
            changed=False,
            reason="confident_enough",
            trigger_reason=effective_trigger_reason,
        )

    pcm = getattr(stt, "last_utterance_audio", b"") or b""
    if not pcm:
        return SttRefinementResult(
            text=original_text,
            meta=meta,
            changed=False,
            reason="no_audio",
            trigger_reason=effective_trigger_reason,
        )

    try:
        refined = whisper.refine_pcm(
            pcm,
            samplerate=getattr(stt, "samplerate", 16000),
        )
        refined = norm_func(refined)

        if refined and prepare_candidate_func is not None:
            refined = norm_func(
                prepare_candidate_func(refined)
            )
    except Exception as e:
        return SttRefinementResult(
            text=original_text,
            meta=meta,
            changed=False,
            reason="refine_failed",
            error=f"{type(e).__name__}: {e}",
            trigger_reason=effective_trigger_reason,
        )

    if not refined or refined == norm_func(original_text):
        return SttRefinementResult(
            text=original_text,
            meta=meta,
            changed=False,
            reason="same_text",
            candidate_text=refined,
            trigger_reason=effective_trigger_reason,
        )

    refined_meta = predict_func(refined)
    conf2 = float(refined_meta.get("confidence") or 0.0)

    original_intent = str(
        meta.get("intent") or ""
    ).upper().strip()

    candidate_intent = str(
        refined_meta.get("intent") or ""
    ).upper().strip()

    if (
            preserve_intent
            and original_intent
            and candidate_intent
            and candidate_intent != original_intent
    ):
        return SttRefinementResult(
            text=original_text,
            meta=meta,
            changed=False,
            reason="intent_mismatch",
            candidate_text=refined,
            candidate_meta=refined_meta,
            trigger_reason=effective_trigger_reason,
        )

    if candidate_intent and conf2 >= conf:
        return SttRefinementResult(
            text=refined,
            meta=refined_meta,
            changed=True,
            reason="accepted_refinement",
            candidate_text=refined,
            candidate_meta=refined_meta,
            trigger_reason=effective_trigger_reason,
        )

    return SttRefinementResult(
        text=original_text,
        meta=meta,
        changed=False,
        reason="refinement_not_better",
        candidate_text=refined,
        candidate_meta=refined_meta,
        trigger_reason=effective_trigger_reason,
    )