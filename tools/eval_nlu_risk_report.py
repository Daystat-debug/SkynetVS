from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from tools.eval_nlu import TEST_CASES, check_case


Risk = Dict[str, Any]


REQUIRED_SLOTS_BY_INTENT: Dict[str, List[str]] = {
    "OPEN_APP": ["app"],
    "CLOSE_APP": ["app"],
    "OPEN_URL": ["url"],
    "SEARCH_WEB": ["query"],
    "SEARCH_YOUTUBE": ["query"],
    "SET_VOLUME": ["volume"],
    "OPEN_FOLDER": ["folder"],
    "OPEN_SETTINGS": ["section"],
}


SEVERITY_ORDER = {
    "high": 0,
    "medium": 1,
    "low": 2,
}


KIND_ORDER = {
    "negative_case_model_would_execute": 0,
    "actual_none_but_model_would_execute": 1,
    "actual_intent_missing_required_slots": 2,
    "model_top_differs_from_actual": 3,
    "model_top_missing_required_slots": 4,
    "model_confidence_near_threshold": 5,
}


def _env_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


ACCEPT_CONF = _env_float(
    "NLU_ACCEPT_CONF",
    os.getenv("NLU_MIN_CONF", "0.35"),
)

NEAR_THRESHOLD_MARGIN = _env_float("NLU_RISK_NEAR_THRESHOLD_MARGIN", "0.03")


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _model_candidates(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []

    for candidate in result.get("top_candidates") or []:
        if not isinstance(candidate, dict):
            continue

        if candidate.get("source") != "model":
            continue

        intent = str(candidate.get("intent") or "").upper().strip()
        if not intent:
            continue

        row = dict(candidate)
        row["intent"] = intent
        rows.append(row)

    rows.sort(
        key=lambda item: _as_float(item.get("confidence")),
        reverse=True,
    )
    return rows


def _top_model_candidate(result: Dict[str, Any]) -> Dict[str, Any] | None:
    candidates = _model_candidates(result)
    if not candidates:
        return None
    return candidates[0]


def _is_model_candidate_accepted(candidate: Dict[str, Any] | None) -> bool:
    if not candidate:
        return False

    accepted = candidate.get("accepted_by_threshold")
    if accepted is not None:
        return bool(accepted)

    return _as_float(candidate.get("confidence")) >= ACCEPT_CONF


def _missing_required_slots_for_candidate(candidate: Dict[str, Any]) -> List[str]:
    intent = str(candidate.get("intent") or "").upper()
    required = REQUIRED_SLOTS_BY_INTENT.get(intent) or []
    slots = candidate.get("slots") or {}

    if not isinstance(slots, dict):
        slots = {}

    missing: List[str] = []

    for key in required:
        value = slots.get(key)
        if value is None or value == "":
            missing.append(key)

    return missing


def _missing_required_slots_for_actual(result: Dict[str, Any]) -> List[str]:
    intent = str(result.get("actual_intent") or "").upper()
    required = REQUIRED_SLOTS_BY_INTENT.get(intent) or []
    slots = result.get("actual_slots") or {}

    if not isinstance(slots, dict):
        slots = {}

    missing: List[str] = []

    for key in required:
        value = slots.get(key)
        if value is None or value == "":
            missing.append(key)

    return missing


def _is_covered_by_rule(result: Dict[str, Any]) -> bool:
    """
    True означает: модель хотела бы что-то выполнить,
    но финальный слой правил/защит оставил actual_intent пустым.
    """
    rule = str(result.get("rule") or "").strip()
    actual_intent = str(result.get("actual_intent") or "").upper().strip()

    return bool(rule and not actual_intent)


def _recommendation_for_risk(risk: Risk) -> str:
    kind = str(risk.get("kind") or "")
    rule = str(risk.get("rule") or "")
    covered_by_rule = bool(risk.get("covered_by_rule"))

    if covered_by_rule and rule == "incomplete_command_rule":
        return "keep_rule"

    if kind in {
        "negative_case_model_would_execute",
        "actual_none_but_model_would_execute",
    }:
        if covered_by_rule:
            return "keep_rule"
        return "add_negative_training_examples"

    if kind == "model_top_missing_required_slots":
        if covered_by_rule:
            return "keep_rule"
        return "improve_slot_extractor"

    if kind == "actual_intent_missing_required_slots":
        return "improve_slot_extractor"

    if kind == "model_top_differs_from_actual":
        return "candidate_for_nlu_reasoning"

    if kind == "model_confidence_near_threshold":
        return "add_training_examples"

    return "review"


def _risk_sort_key(risk: Risk) -> tuple[int, int, str, str]:
    return (
        SEVERITY_ORDER.get(str(risk.get("severity")), 99),
        KIND_ORDER.get(str(risk.get("kind")), 99),
        str(risk.get("group") or ""),
        str(risk.get("text") or ""),
    )


def _add_risk(
    risks: List[Risk],
    *,
    severity: str,
    kind: str,
    result: Dict[str, Any],
    intent: str | None = None,
    details: Dict[str, Any] | None = None,
) -> None:
    risk: Risk = {
        "severity": severity,
        "kind": kind,
        "group": result.get("group"),
        "text": result.get("text"),
        "expected_intent": result.get("expected_intent"),
        "actual_intent": result.get("actual_intent"),
        "confidence": round(_as_float(result.get("confidence")), 4),
        "rule": result.get("rule"),
        "intent": intent,
        "covered_by_rule": _is_covered_by_rule(result),
        "details": details or {},
    }

    risk["recommendation"] = _recommendation_for_risk(risk)
    risks.append(risk)


def analyze_result(result: Dict[str, Any]) -> List[Risk]:
    risks: List[Risk] = []

    actual_intent = str(result.get("actual_intent") or "").upper().strip()
    expected_intent = result.get("expected_intent")
    rule = str(result.get("rule") or "").strip()

    model_top = _top_model_candidate(result)
    model_top_intent = str(model_top.get("intent") or "").upper() if model_top else ""
    model_top_conf = _as_float(model_top.get("confidence")) if model_top else 0.0
    model_top_accepted = _is_model_candidate_accepted(model_top)

    if expected_intent is None and model_top and model_top_accepted:
        _add_risk(
            risks,
            severity="high",
            kind="negative_case_model_would_execute",
            result=result,
            intent=model_top_intent,
            details={
                "model_top": model_top,
                "reason": "eval expects no accepted intent, but model top candidate passes threshold",
            },
        )

    if not actual_intent and model_top and model_top_accepted:
        _add_risk(
            risks,
            severity="high" if rule == "incomplete_command_rule" else "medium",
            kind="actual_none_but_model_would_execute",
            result=result,
            intent=model_top_intent,
            details={
                "model_top": model_top,
                "reason": "final decision is None, but model top candidate passes threshold",
            },
        )

    if actual_intent and model_top and model_top_accepted and model_top_intent != actual_intent:
        _add_risk(
            risks,
            severity="medium",
            kind="model_top_differs_from_actual",
            result=result,
            intent=model_top_intent,
            details={
                "model_top": model_top,
                "reason": "model top candidate differs from final actual intent",
            },
        )

    if model_top:
        delta = abs(model_top_conf - ACCEPT_CONF)
        if delta <= NEAR_THRESHOLD_MARGIN:
            _add_risk(
                risks,
                severity="low",
                kind="model_confidence_near_threshold",
                result=result,
                intent=model_top_intent,
                details={
                    "model_top": model_top,
                    "accept_conf": ACCEPT_CONF,
                    "margin": NEAR_THRESHOLD_MARGIN,
                    "delta": round(delta, 4),
                },
            )

    if model_top and model_top_accepted:
        missing_model_slots = _missing_required_slots_for_candidate(model_top)
        if missing_model_slots:
            _add_risk(
                risks,
                severity="medium",
                kind="model_top_missing_required_slots",
                result=result,
                intent=model_top_intent,
                details={
                    "model_top": model_top,
                    "missing_slots": missing_model_slots,
                },
            )

    missing_actual_slots = _missing_required_slots_for_actual(result)
    if actual_intent and missing_actual_slots:
        _add_risk(
            risks,
            severity="high",
            kind="actual_intent_missing_required_slots",
            result=result,
            intent=actual_intent,
            details={
                "missing_slots": missing_actual_slots,
                "actual_slots": result.get("actual_slots") or {},
            },
        )

    return risks


def dedupe_risks(raw_risks: List[Risk]) -> List[Risk]:
    """
    Схлопывает несколько рисков по одной фразе в один primary-risk.

    Пример:
      "открой" может одновременно попасть в:
        - negative_case_model_would_execute
        - actual_none_but_model_would_execute
        - model_top_missing_required_slots

    В отчёте оставляем главный риск, а остальные складываем в related_*.
    """
    grouped: Dict[str, List[Risk]] = {}

    for risk in raw_risks:
        text = str(risk.get("text") or "")
        grouped.setdefault(text, []).append(risk)

    result: List[Risk] = []

    for text, group in grouped.items():
        ordered = sorted(group, key=_risk_sort_key)
        primary = dict(ordered[0])

        primary["related_raw_risk_count"] = len(group)
        primary["related_risk_kinds"] = sorted({
            str(item.get("kind") or "")
            for item in group
            if item.get("kind")
        })
        primary["related_recommendations"] = sorted({
            str(item.get("recommendation") or "")
            for item in group
            if item.get("recommendation")
        })
        primary["covered_by_rule_any"] = any(bool(item.get("covered_by_rule")) for item in group)

        result.append(primary)

    result.sort(key=_risk_sort_key)
    return result


def _count_by(items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    result: Dict[str, int] = {}

    for item in items:
        value = str(item.get(key) or "unknown")
        result[value] = result.get(value, 0) + 1

    return dict(sorted(result.items(), key=lambda pair: pair[0]))


def main() -> int:
    results = [check_case(case) for case in TEST_CASES]

    raw_risks: List[Risk] = []

    for result in results:
        raw_risks.extend(analyze_result(result))

    risks = dedupe_risks(raw_risks)

    print("=== NLU RISK REPORT ===")
    print()
    print(
        json.dumps(
            {
                "total_cases": len(results),
                "risk_count": len(risks),
                "raw_risk_count": len(raw_risks),
                "by_severity": _count_by(risks, "severity"),
                "by_kind": _count_by(risks, "kind"),
                "by_recommendation": _count_by(risks, "recommendation"),
                "raw_by_kind": _count_by(raw_risks, "kind"),
                "accept_conf": ACCEPT_CONF,
                "near_threshold_margin": NEAR_THRESHOLD_MARGIN,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print("=== RISKS ===")

    if not risks:
        print("[OK] no NLU risks found")
    else:
        for idx, risk in enumerate(risks, start=1):
            print()
            print(
                f"{idx}. [{risk['severity']}] "
                f"{risk['kind']}: {risk['text']} "
                f"-> {risk['recommendation']}"
            )
            print(json.dumps(risk, ensure_ascii=False))

    print()
    print("=== RECOMMENDATIONS ===")
    recommendation_counts = _count_by(risks, "recommendation")

    if not recommendation_counts:
        print("[OK] no recommendations")
    else:
        print(json.dumps(recommendation_counts, ensure_ascii=False, indent=2))

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "total_cases": len(results),
                "risk_count": len(risks),
                "raw_risk_count": len(raw_risks),
                "high": _count_by(risks, "severity").get("high", 0),
                "medium": _count_by(risks, "severity").get("medium", 0),
                "low": _count_by(risks, "severity").get("low", 0),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    # Это аналитический отчёт. Он НЕ должен ломать pipeline.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())