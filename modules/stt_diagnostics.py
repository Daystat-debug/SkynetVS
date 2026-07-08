from __future__ import annotations

from typing import Any, Dict


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_meta(meta: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(meta, dict):
        return {
            "intent": None,
            "confidence": 0.0,
            "slots": {},
            "rule": None,
        }

    slots = meta.get("slots") or {}
    if not isinstance(slots, dict):
        slots = {}

    return {
        "intent": meta.get("intent"),
        "confidence": round(_safe_float(meta.get("confidence")), 4),
        "slots": dict(slots),
        "rule": meta.get("_rule"),
    }


def _safe_stt_diagnostics(stt: Any) -> Dict[str, Any]:
    if stt is None:
        return {}

    if hasattr(stt, "get_diagnostics"):
        try:
            data = stt.get_diagnostics()
            if isinstance(data, dict):
                return dict(data)
        except Exception as e:
            return {
                "diagnostics_error": f"{type(e).__name__}: {e}",
            }

    audio = getattr(stt, "last_utterance_audio", b"") or b""
    samplerate = int(getattr(stt, "samplerate", 16000) or 16000)

    if samplerate > 0:
        duration_sec = len(audio) / (2 * samplerate)
    else:
        duration_sec = 0.0

    return {
        "engine": type(stt).__name__,
        "samplerate": samplerate,
        "last_utterance_text": getattr(stt, "last_utterance_text", ""),
        "last_utterance_audio_bytes": len(audio),
        "last_utterance_duration_sec": round(duration_sec, 3),
    }


def build_stt_diagnostic_payload(
    *,
    raw_text: str,
    text_before_refinement: str,
    final_text: str,
    meta_before_refinement: Dict[str, Any],
    meta_after_refinement: Dict[str, Any],
    refinement: Any,
    stt: Any,
) -> Dict[str, Any]:
    """
    Строит безопасный JSONL payload для анализа STT/NLU pipeline.

    Не пишет audio bytes, только размер/длительность.
    """
    reason = getattr(refinement, "reason", "")
    changed = bool(getattr(refinement, "changed", False))
    candidate_text = getattr(refinement, "candidate_text", None)
    candidate_meta = getattr(refinement, "candidate_meta", None)
    error = getattr(refinement, "error", None)

    return {
        "raw_text": raw_text,
        "text_before_refinement": text_before_refinement,
        "final_text": final_text,
        "changed_by_refinement": changed,
        "refinement_reason": reason,
        "refinement_candidate_text": candidate_text,
        "refinement_candidate_meta": _safe_meta(candidate_meta),
        "refinement_error": error,
        "original_meta": _safe_meta(meta_before_refinement),
        "final_meta": _safe_meta(meta_after_refinement),
        "stt": _safe_stt_diagnostics(stt),
    }