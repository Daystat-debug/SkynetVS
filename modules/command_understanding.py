from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, Mapping, Protocol, Sequence

from modules.command_decision import (
    CommandDecision,
    build_command_decision,
)
from modules.entity_resolver import (
    EntityRescueResult,
    resolve_entities,
    rescue_missing_entities,
)
from modules.hotword_utils import (
    norm_text,
    split_hotword_prefix,
)
from modules.nlu import predict
from modules.stt_refinement import maybe_refine_with_whisper
from modules.text_normalizer import normalize_command_text
from modules.stt_diagnostics import build_stt_diagnostic_payload

from modules.understanding_helpers import (
    needs_normalization_retry,
    should_use_retry_result,
)


PrintFunc = Callable[[str], None]
DEFAULT_WHISPER_HOTWORDS = (
    "скайнет",
    "skynet",
)

WHISPER_EDGE_STRIP_CHARS = " ,.!?:;—-"


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


def _prepare_whisper_candidate_text(
    text: str,
    *,
    hotwords: Sequence[str],
) -> str:
    """
    Удаляет ведущий hotword, который Whisper часто возвращает
    вместе с самой командой.

    Пример:
      "скайнет, запусти музыку."
        -> "запусти музыку"
    """
    normalized = norm_text(text)

    found, rest = split_hotword_prefix(
        normalized,
        hotwords=hotwords,
    )

    prepared = rest if found else normalized

    return prepared.strip(
        WHISPER_EDGE_STRIP_CHARS
    )


def _norm_url(value: Any) -> str:
    return str(value or "").strip().lower().rstrip("/")


def _registry_site_urls() -> dict[str, str]:
    try:
        from modules.entity_registry import SITE_URLS
    except Exception:
        return {}

    if not isinstance(SITE_URLS, dict):
        return {}

    return {
        str(code or "").strip().lower(): str(url or "").strip()
        for code, url in SITE_URLS.items()
        if str(code or "").strip() and str(url or "").strip()
    }


def _is_known_registry_site_candidate(meta: Mapping[str, Any]) -> bool:
    slots = dict(meta.get("slots") or {})
    site = str(slots.get("site") or "").strip().lower()
    url = _norm_url(slots.get("url"))

    registry_urls = _registry_site_urls()

    if site and site in registry_urls:
        return True

    known_urls = {
        _norm_url(value)
        for value in registry_urls.values()
        if str(value or "").strip()
    }

    return bool(url and url in known_urls)


def _is_safe_missing_slots_refinement_candidate(meta: Mapping[str, Any]) -> bool:
    intent = str(meta.get("intent") or "").upper().strip()

    # Для сайтов не принимаем произвольные домены типа www.opanae.com.
    # Принимаем только известные сайты из entity_registry.
    if intent == "OPEN_URL":
        return _is_known_registry_site_candidate(meta)

    return True


def _has_slot_value(
    slots: Mapping[str, Any],
    slot_name: str,
) -> bool:
    value = slots.get(slot_name)

    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _maybe_accept_refinement_that_fills_missing_slots(
    refinement: Any,
    *,
    original_text: str,
    original_meta: Mapping[str, Any],
    missing_slots_before_refinement: Sequence[str],
    force_refine_missing_slots: bool,
    accept_conf: float,
) -> Any:
    """
    Проверяет Whisper-кандидат для команды с отсутствующими обязательными slots.

    Кандидат принимается только если он:
      - сохраняет исходный intent;
      - заполняет именно исходно отсутствовавшие обязательные slots;
      - становится runnable;
      - проходит дополнительные safety-проверки.

    Если базовая refinement-логика уже приняла небезопасный кандидат,
    исходные text/meta восстанавливаются.
    """
    if not force_refine_missing_slots:
        return refinement

    refinement_reason = str(getattr(refinement, "reason", "") or "")

    if refinement_reason not in {
        "accepted_refinement",
        "refinement_not_better",
    }:
        return refinement

    candidate_text = getattr(refinement, "candidate_text", None)
    candidate_meta_raw = getattr(refinement, "candidate_meta", None)

    if not candidate_text or not isinstance(candidate_meta_raw, dict):
        return refinement

    original_meta_copy = dict(original_meta)
    original_slots = original_meta_copy.get("slots") or {}
    original_meta_copy["slots"] = (
        dict(original_slots)
        if isinstance(original_slots, Mapping)
        else {}
    )

    original_intent = str(
        original_meta_copy.get("intent") or ""
    ).upper().strip()

    candidate_meta = dict(candidate_meta_raw)
    candidate_slots_raw = candidate_meta.get("slots") or {}
    candidate_meta["slots"] = (
        dict(candidate_slots_raw)
        if isinstance(candidate_slots_raw, Mapping)
        else {}
    )
    candidate_meta["_text"] = candidate_text

    candidate_meta = resolve_entities(candidate_text, candidate_meta)

    candidate_intent = str(
        candidate_meta.get("intent") or ""
    ).upper().strip()

    def reject_candidate() -> Any:
        return replace(
            refinement,
            text=original_text,
            meta=original_meta_copy,
            changed=False,
            reason="refinement_not_better",
        )

    # Missing-slots refinement не должен менять тип команды.
    # OPEN_URL -> GREET / OPEN_APP относится уже к intent correction.
    if not original_intent or candidate_intent != original_intent:
        return reject_candidate()

    candidate_slots = dict(candidate_meta.get("slots") or {})

    unfilled_slots = [
        slot_name
        for slot_name in missing_slots_before_refinement
        if not _has_slot_value(candidate_slots, slot_name)
    ]

    if unfilled_slots:
        return reject_candidate()

    candidate_decision = build_command_decision(
        candidate_meta,
        accept_conf=accept_conf,
    )

    if not candidate_decision.runnable:
        return reject_candidate()

    # Для OPEN_URL принимаем только известные сайты из entity_registry.
    # Произвольный домен, ошибочно придуманный Whisper, отклоняется.
    if not _is_safe_missing_slots_refinement_candidate(candidate_meta):
        return reject_candidate()

    return replace(
        refinement,
        text=candidate_text,
        meta=candidate_meta,
        changed=True,
        reason="accepted_refinement",
    )


def _maybe_accept_registry_entity_rescue(
    refinement: Any,
    *,
    original_text: str,
    original_meta: Mapping[str, Any],
    missing_slots_before_refinement: Sequence[str],
    force_refine_missing_slots: bool,
    accept_conf: float,
) -> tuple[Any, EntityRescueResult | None]:
    """
    Последний безопасный rescue-pass после обычного Whisper refinement.

    Анализирует:
      - Whisper candidate;
      - исходный Vosk text.

    Принимает только известную registry-сущность и не меняет intent.
    """
    if not force_refine_missing_slots:
        return refinement, None

    current_decision = build_command_decision(
        refinement.meta,
        accept_conf=accept_conf,
    )

    if current_decision.runnable:
        return refinement, None

    candidate_text = str(
        getattr(
            refinement,
            "candidate_text",
            "",
        )
        or ""
    ).strip()

    rescue_texts = []

    if candidate_text:
        rescue_texts.append(candidate_text)

    rescue_texts.append(original_text)

    rescue = rescue_missing_entities(
        rescue_texts,
        dict(original_meta),
    )

    if not rescue.changed:
        return refinement, None

    original_intent = str(
        original_meta.get("intent") or ""
    ).upper().strip()

    rescued_intent = str(
        rescue.meta.get("intent") or ""
    ).upper().strip()

    if (
        not original_intent
        or rescued_intent != original_intent
    ):
        return refinement, None

    rescued_slots = dict(
        rescue.meta.get("slots") or {}
    )

    still_missing = [
        slot_name
        for slot_name in missing_slots_before_refinement
        if not _has_slot_value(
            rescued_slots,
            slot_name,
        )
    ]

    if still_missing:
        return refinement, None

    rescued_decision = build_command_decision(
        rescue.meta,
        accept_conf=accept_conf,
    )

    if not rescued_decision.runnable:
        return refinement, None

    rescued_refinement = replace(
        refinement,
        text=original_text,
        meta=rescue.meta,
        changed=True,
        reason="accepted_registry_rescue",
        candidate_text=(
            rescue.source_text
            or candidate_text
            or original_text
        ),
        candidate_meta=rescue.meta,
    )

    return rescued_refinement, rescue


def understand_command_text(
    command_text: str,
    *,
    router: PreprocessRouter,
    logger: EventLogger | None,
    whisper: Any,
    stt: Any,
    accept_conf: float,
    whisper_trigger_conf: float,
    hotwords: Sequence[str] = DEFAULT_WHISPER_HOTWORDS,
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

    pre_refinement_decision = build_command_decision(
        meta,
        accept_conf=accept_conf,
    )

    original_is_accepted = pre_refinement_decision.accepted
    missing_slots_before_refinement = list(
        pre_refinement_decision.missing_slots
    )

    force_refine_missing_slots = (
            original_is_accepted
            and bool(missing_slots_before_refinement)
    )

    skip_refine_complete_command = (
            original_is_accepted
            and not missing_slots_before_refinement
    )

    if force_refine_missing_slots:
        whisper_trigger_reason = "missing_required_slots"
    elif skip_refine_complete_command:
        whisper_trigger_reason = "accepted_complete"
    else:
        whisper_trigger_reason = "confidence"

    refinement = maybe_refine_with_whisper(
        original_text=text_in,
        meta=meta,
        whisper=whisper,
        stt=stt,
        trigger_conf=whisper_trigger_conf,
        predict_func=predict,
        norm_func=norm_text,
        prepare_candidate_func=lambda candidate: (
            _prepare_whisper_candidate_text(
                candidate,
                hotwords=hotwords,
            )
        ),
        preserve_intent=original_is_accepted,
        skip_refine=skip_refine_complete_command,
        force_refine=force_refine_missing_slots,
        trigger_reason=whisper_trigger_reason,
    )

    refinement = _maybe_accept_refinement_that_fills_missing_slots(
        refinement,
        original_text=text_before_refinement,
        original_meta=meta_before_refinement,
        missing_slots_before_refinement=missing_slots_before_refinement,
        force_refine_missing_slots=force_refine_missing_slots,
        accept_conf=accept_conf,
    )

    refinement, registry_rescue = (
        _maybe_accept_registry_entity_rescue(
            refinement,
            original_text=text_before_refinement,
            original_meta=meta_before_refinement,
            missing_slots_before_refinement=(
                missing_slots_before_refinement
            ),
            force_refine_missing_slots=(
                force_refine_missing_slots
            ),
            accept_conf=accept_conf,
        )
    )

    if refinement.error:
        _print(print_func, f"[WHISPER] refine failed: {refinement.error}")

    if refinement.candidate_text and refinement.candidate_meta is not None:
        candidate_source = (
            "REGISTRY RESCUE"
            if refinement.reason
            == "accepted_registry_rescue"
            else "WHISPER"
        )

        _print(
            print_func,
            f"[{candidate_source}] '{text_in}' -> "
            f"'{refinement.candidate_text}'",
        )

        candidate_status = (
            "accepted"
            if refinement.changed
            else "rejected candidate"
        )

        _print(
            print_func,
            f"[NLU] {candidate_status} "
            f"intent={refinement.candidate_meta.get('intent')} "
            f"conf={refinement.candidate_meta.get('confidence', 0.0):.2f} "
            f"slots={refinement.candidate_meta.get('slots')}",
        )

    if registry_rescue is not None:
        _log_event(
            logger,
            "entity_registry_rescue",
            {
                "text": text_before_refinement,
                "intent": refinement.meta.get("intent"),
                "kind": registry_rescue.kind,
                "code": registry_rescue.code,
                "score": registry_rescue.score,
                "margin": registry_rescue.margin,
                "source_text": registry_rescue.source_text,
                "candidate_text": (
                    registry_rescue.candidate_text
                ),
                "matched_alias": registry_rescue.alias,
                "slots": (
                    refinement.meta.get("slots")
                    or {}
                ),
            },
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