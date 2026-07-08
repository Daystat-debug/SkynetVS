from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.nlu import predict_candidates


Case = Dict[str, Any]


def _env_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


ACCEPT_CONF = _env_float(
    "NLU_ACCEPT_CONF",
    os.getenv("NLU_MIN_CONF", "0.35"),
)


CASES: List[Case] = [
    {
        "text": "режим диктовки",
        "expected_model_top": "DICTATION_MODE_ON",
    },
    {
        "text": "режим ввода текста",
        "expected_model_top": "DICTATION_MODE_ON",
    },
    {
        "text": "включи диктовку",
        "expected_model_top": "DICTATION_MODE_ON",
    },
    {
        "text": "запусти режим диктовки",
        "expected_model_top": "DICTATION_MODE_ON",
    },
    {
        "text": "активируй режим диктовки",
        "expected_model_top": "DICTATION_MODE_ON",
    },
    {
        "text": "включи голосовой ввод",
        "expected_model_top": "DICTATION_MODE_ON",
    },
    {
        "text": "начни ввод текста голосом",
        "expected_model_top": "DICTATION_MODE_ON",
    },
    {
        "text": "выключи режим диктовки",
        "expected_model_top": "DICTATION_MODE_OFF",
    },
    {
        "text": "закрой режим диктовки",
        "expected_model_top": "DICTATION_MODE_OFF",
    },
    {
        "text": "закрой режим ввода текста",
        "expected_model_top": "DICTATION_MODE_OFF",
    },
    {
        "text": "отключи диктовку",
        "expected_model_top": "DICTATION_MODE_OFF",
    },
    {
        "text": "выключи голосовой ввод",
        "expected_model_top": "DICTATION_MODE_OFF",
    },
    {
        "text": "останови голосовой ввод",
        "expected_model_top": "DICTATION_MODE_OFF",
    },
    {
        "text": "заверши ввод текста голосом",
        "expected_model_top": "DICTATION_MODE_OFF",
    },
]


def _model_candidates(text: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for candidate in predict_candidates(text, limit=5, include_rules=True):
        if not isinstance(candidate, dict):
            continue

        if candidate.get("source") != "model":
            continue

        rows.append(dict(candidate))

    rows.sort(
        key=lambda item: float(item.get("confidence") or 0.0),
        reverse=True,
    )

    return rows


def check_case(case: Case) -> Dict[str, Any]:
    text = str(case["text"])
    expected = str(case["expected_model_top"]).upper()

    candidates = _model_candidates(text)
    top = candidates[0] if candidates else {}

    actual = str(top.get("intent") or "").upper() or None
    confidence = float(top.get("confidence") or 0.0)
    accepted = confidence >= ACCEPT_CONF

    errors: List[str] = []

    if actual != expected:
        errors.append(
            f"model top mismatch: expected={expected}, actual={actual}"
        )

    if not accepted:
        errors.append(
            f"model top confidence below threshold: got={confidence:.4f}, required>={ACCEPT_CONF:.4f}"
        )

    return {
        "text": text,
        "expected_model_top": expected,
        "actual_model_top": actual,
        "confidence": confidence,
        "accepted_by_threshold": accepted,
        "top_candidates": candidates,
        "errors": errors,
        "ok": not errors,
    }


def main() -> int:
    results = [check_case(case) for case in CASES]
    fail_count = sum(1 for result in results if not result["ok"])

    print("=== DICTATION INTENT SEPARATION REPORT ===")

    for idx, result in enumerate(results, start=1):
        print()
        print(f"{idx}. {result['text']}")
        print(
            json.dumps(
                {
                    "expected_model_top": result["expected_model_top"],
                    "actual_model_top": result["actual_model_top"],
                    "confidence": round(float(result["confidence"]), 4),
                    "accepted_by_threshold": result["accepted_by_threshold"],
                    "top_candidates": result["top_candidates"],
                    "errors": result["errors"],
                },
                ensure_ascii=False,
            )
        )

        if result["ok"]:
            print("[OK] dictation separation case")
        else:
            for error in result["errors"]:
                print(f"[FAIL] {error}")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "total_cases": len(results),
                "fail_count": fail_count,
                "accept_conf": ACCEPT_CONF,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())