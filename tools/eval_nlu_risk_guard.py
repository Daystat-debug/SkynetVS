from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tools.eval_nlu import TEST_CASES, check_case
from tools.eval_nlu_risk_report import analyze_result, dedupe_risks


Risk = Dict[str, Any]


ALLOWED_RECOMMENDATIONS = {
    "keep_rule",
}


def _count_by(items: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    result: Dict[str, int] = {}

    for item in items:
        value = str(item.get(key) or "unknown")
        result[value] = result.get(value, 0) + 1

    return dict(sorted(result.items(), key=lambda pair: pair[0]))


def _is_allowed_risk(risk: Risk) -> bool:
    recommendation = str(risk.get("recommendation") or "")
    covered_by_rule_any = bool(risk.get("covered_by_rule_any"))
    covered_by_rule = bool(risk.get("covered_by_rule"))

    if recommendation not in ALLOWED_RECOMMENDATIONS:
        return False

    # keep_rule должен быть именно про защищённые rule-сценарии,
    # а не про случайно замаскированную проблему.
    if not covered_by_rule_any and not covered_by_rule:
        return False

    return True


def main() -> int:
    results = [check_case(case) for case in TEST_CASES]

    raw_risks: List[Risk] = []

    for result in results:
        raw_risks.extend(analyze_result(result))

    risks = dedupe_risks(raw_risks)

    blocked_risks = [
        risk
        for risk in risks
        if not _is_allowed_risk(risk)
    ]

    print("=== NLU RISK GUARD REPORT ===")
    print()
    print(
        json.dumps(
            {
                "total_cases": len(results),
                "risk_count": len(risks),
                "raw_risk_count": len(raw_risks),
                "blocked_risk_count": len(blocked_risks),
                "by_recommendation": _count_by(risks, "recommendation"),
                "by_severity": _count_by(risks, "severity"),
                "allowed_recommendations": sorted(ALLOWED_RECOMMENDATIONS),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print("=== BLOCKED RISKS ===")

    if not blocked_risks:
        print("[OK] no blocked NLU risks")
    else:
        for idx, risk in enumerate(blocked_risks, start=1):
            print()
            print(
                f"{idx}. [{risk.get('severity')}] "
                f"{risk.get('kind')}: {risk.get('text')} "
                f"-> {risk.get('recommendation')}"
            )
            print(json.dumps(risk, ensure_ascii=False))

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "risk_count": len(risks),
                "blocked_risk_count": len(blocked_risks),
                "ok": len(blocked_risks) == 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if blocked_risks else 0


if __name__ == "__main__":
    raise SystemExit(main())