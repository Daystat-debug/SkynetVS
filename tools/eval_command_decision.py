from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.command_decision import build_command_decision
from modules.config import Settings
from modules.nlu import predict


Case = Dict[str, Any]


def expected_runnable() -> Dict[str, Any]:
    return {
        "accepted": True,
        "runnable": True,
        "requires_confirmation": False,
        "missing_slots": [],
        "reason": None,
    }


def expected_not_accepted() -> Dict[str, Any]:
    return {
        "accepted": False,
        "runnable": False,
        "requires_confirmation": False,
        "missing_slots": [],
        "reason": "not_accepted",
    }


def expected_requires_confirmation() -> Dict[str, Any]:
    return {
        "accepted": True,
        "runnable": False,
        "requires_confirmation": True,
        "missing_slots": [],
        "reason": "requires_confirmation",
    }


def expected_missing_slots(*slots: str) -> Dict[str, Any]:
    return {
        "accepted": True,
        "runnable": False,
        "requires_confirmation": False,
        "missing_slots": list(slots),
        "reason": "missing_required_slots",
    }


TEXT_CASE_GROUPS: List[tuple[str, List[Case]]] = [
    (
        "core_control_runnable",
        [
            {
                "name": "stop listen is runnable",
                "text": "стоп",
                "expected": expected_runnable(),
            },
            {
                "name": "dictation mode on is runnable",
                "text": "режим диктовки",
                "expected": expected_runnable(),
            },
            {
                "name": "dictation mode off is runnable",
                "text": "выключи режим диктовки",
                "expected": expected_runnable(),
            },
            {
                "name": "stop talking is runnable",
                "text": "замолчи",
                "expected": expected_runnable(),
            },
        ],
    ),
    (
        "normal_commands_runnable",
        [
            {
                "name": "open app is runnable",
                "text": "открой блокнот",
                "expected": expected_runnable(),
            },
            {
                "name": "open url is runnable",
                "text": "открой ютуб",
                "expected": expected_runnable(),
            },
            {
                "name": "search web is runnable",
                "text": "найди котиков",
                "expected": expected_runnable(),
            },
            {
                "name": "search youtube is runnable",
                "text": "найди на ютубе музыку",
                "expected": expected_runnable(),
            },
            {
                "name": "open folder is runnable",
                "text": "открой загрузки",
                "expected": expected_runnable(),
            },
            {
                "name": "open settings is runnable",
                "text": "открой настройки звука",
                "expected": expected_runnable(),
            },
            {
                "name": "set volume is runnable",
                "text": "громкость 50",
                "expected": expected_runnable(),
            },
            {
                "name": "lock screen is runnable",
                "text": "заблокируй компьютер",
                "expected": expected_runnable(),
            },
        ],
    ),
    (
        "confirmation_required",
        [
            {
                "name": "empty recycle bin requires confirmation",
                "text": "очисти корзину",
                "expected": expected_requires_confirmation(),
            },
        ],
    ),
    (
        "negative_text_commands",
        [
            {
                "name": "incomplete open is not accepted",
                "text": "открой",
                "expected": expected_not_accepted(),
            },
            {
                "name": "bare close is not accepted",
                "text": "закрой",
                "expected": expected_not_accepted(),
            },
            {
                "name": "bare search is not accepted",
                "text": "найди",
                "expected": expected_not_accepted(),
            },
            {
                "name": "bare switch is not accepted",
                "text": "переключи",
                "expected": expected_not_accepted(),
            },
            {
                "name": "bare volume is not accepted",
                "text": "громкость",
                "expected": expected_not_accepted(),
            },
            {
                "name": "bare sound is not accepted",
                "text": "звук",
                "expected": expected_not_accepted(),
            },
            {
                "name": "ambiguous close mode is not accepted",
                "text": "закрой режим",
                "expected": expected_not_accepted(),
            },
            {
                "name": "ambiguous back is not accepted",
                "text": "назад",
                "expected": expected_not_accepted(),
            },
        ],
    ),
]


META_CASE_GROUPS: List[tuple[str, List[Case]]] = [
    (
        "missing_required_slots",
        [
            {
                "name": "OPEN_URL without url is blocked",
                "meta": {
                    "intent": "OPEN_URL",
                    "confidence": 1.0,
                    "slots": {},
                },
                "expected": expected_missing_slots("url"),
            },
            {
                "name": "SET_VOLUME without volume is blocked",
                "meta": {
                    "intent": "SET_VOLUME",
                    "confidence": 1.0,
                    "slots": {},
                },
                "expected": expected_missing_slots("volume"),
            },
            {
                "name": "CLOSE_APP without app is blocked",
                "meta": {
                    "intent": "CLOSE_APP",
                    "confidence": 1.0,
                    "slots": {},
                },
                "expected": expected_missing_slots("app"),
            },
            {
                "name": "OPEN_APP without app is blocked",
                "meta": {
                    "intent": "OPEN_APP",
                    "confidence": 1.0,
                    "slots": {},
                },
                "expected": expected_missing_slots("app"),
            },
            {
                "name": "OPEN_FOLDER without folder is blocked",
                "meta": {
                    "intent": "OPEN_FOLDER",
                    "confidence": 1.0,
                    "slots": {},
                },
                "expected": expected_missing_slots("folder"),
            },
            {
                "name": "OPEN_SETTINGS without section is blocked",
                "meta": {
                    "intent": "OPEN_SETTINGS",
                    "confidence": 1.0,
                    "slots": {},
                },
                "expected": expected_missing_slots("section"),
            },
            {
                "name": "SEARCH_WEB without query is blocked",
                "meta": {
                    "intent": "SEARCH_WEB",
                    "confidence": 1.0,
                    "slots": {},
                },
                "expected": expected_missing_slots("query"),
            },
            {
                "name": "SEARCH_YOUTUBE without query is blocked",
                "meta": {
                    "intent": "SEARCH_YOUTUBE",
                    "confidence": 1.0,
                    "slots": {},
                },
                "expected": expected_missing_slots("query"),
            },
        ],
    ),
    (
        "confidence_guard",
        [
            {
                "name": "low confidence command is not accepted",
                "meta": {
                    "intent": "OPEN_APP",
                    "confidence": 0.01,
                    "slots": {"app": "notepad"},
                },
                "expected": expected_not_accepted(),
            },
        ],
    ),
]


def build_cases() -> List[Case]:
    rows: List[Case] = []

    for group_name, cases in TEXT_CASE_GROUPS:
        for case in cases:
            row = dict(case)
            row["group"] = group_name
            row["source"] = "text"
            rows.append(row)

    for group_name, cases in META_CASE_GROUPS:
        for case in cases:
            row = dict(case)
            row["group"] = group_name
            row["source"] = "meta"
            rows.append(row)

    return rows


def _compare_dict(expected: Dict[str, Any], actual: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    for key, expected_value in expected.items():
        actual_value = actual.get(key)

        if actual_value != expected_value:
            errors.append(
                f"{key}: expected={expected_value!r}, actual={actual_value!r}"
            )

    return errors


def _case_meta(case: Case) -> Dict[str, Any]:
    if "meta" in case:
        return dict(case["meta"])

    return predict(str(case["text"]))


def run_case(case: Case, *, accept_conf: float) -> Dict[str, Any]:
    meta = _case_meta(case)

    decision = build_command_decision(
        meta,
        accept_conf=accept_conf,
    ).to_dict()

    expected = dict(case["expected"])
    errors = _compare_dict(expected, decision)

    return {
        "group": case.get("group") or "unknown",
        "source": case.get("source") or "unknown",
        "name": case["name"],
        "text": case.get("text"),
        "meta": meta,
        "decision": decision,
        "expected": expected,
        "errors": errors,
        "ok": len(errors) == 0,
    }


def main() -> int:
    settings = Settings.from_env()
    cases = build_cases()

    results = [
        run_case(case, accept_conf=settings.nlu_accept_conf)
        for case in cases
    ]

    fail_count = 0
    group_stats: Dict[str, Dict[str, int]] = {}

    print("=== COMMAND DECISION EVAL REPORT ===")
    print(
        json.dumps(
            {
                "accept_conf": settings.nlu_accept_conf,
                "total_cases": len(results),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    current_group: str | None = None

    for idx, result in enumerate(results, start=1):
        group = str(result["group"])

        if group != current_group:
            current_group = group
            print()
            print(f"--- GROUP: {group} ---")

        stats = group_stats.setdefault(
            group,
            {
                "total": 0,
                "fail_count": 0,
            },
        )
        stats["total"] += 1

        print()
        print(f"{idx}. {result['name']}")

        print(
            json.dumps(
                {
                    "group": result["group"],
                    "source": result["source"],
                    "text": result["text"],
                    "meta": result["meta"],
                    "decision": result["decision"],
                    "expected": result["expected"],
                },
                ensure_ascii=False,
            )
        )

        if result["errors"]:
            fail_count += 1
            stats["fail_count"] += 1

            for error in result["errors"]:
                print(f"[FAIL] {error}")
        else:
            print("[OK] decision checks passed")

    print()
    print("=== GROUP SUMMARY ===")
    print(json.dumps(group_stats, ensure_ascii=False, indent=2))

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "total_cases": len(results),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())