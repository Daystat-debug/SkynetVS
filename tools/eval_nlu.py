from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set

from dotenv import load_dotenv

load_dotenv()

from modules.nlu import predict, predict_candidates


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INTENTS_PATH = PROJECT_ROOT / "data" / "intents.json"


Case = Dict[str, Any]


BASE_CASES: List[Case] = [
    {
        "text": "привет",
        "intent": "GREET",
        "recommended_conf": 0.35,
    },
    {
        "text": "какая погода",
        "intent": "WEATHER",
        "recommended_conf": 0.40,
    },
    {
        "text": "какая погода в минске",
        "intent": "WEATHER",
        "required_slots": {"city": ["Минск", "Минске"]},
        "recommended_conf": 0.40,
    },
    {
        "text": "сделай скриншот",
        "intent": "SCREENSHOT",
        "recommended_conf": 0.35,
    },
    {
        "text": "стоп",
        "intent": "STOP_LISTEN",
        "recommended_conf": 0.90,
    },
]


APP_CASES: List[Case] = [
    {
        "text": "открой блокнот",
        "intent": "OPEN_APP",
        "required_slots": {"app": "notepad"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой хром",
        "intent": "OPEN_APP",
        "required_slots": {"app": "chrome"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой браузер",
        "intent": "OPEN_APP",
        "required_slots": {"app": "chrome"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой проводник",
        "intent": "OPEN_APP",
        "required_slots": {"app": "explorer"},
        "recommended_conf": 0.35,
    },
    {
        "text": "закрой блокнот",
        "intent": "CLOSE_APP",
        "required_slots": {"app": "notepad"},
        "recommended_conf": 0.35,
    },
    {
        "text": "закрой проводник",
        "intent": "CLOSE_APP",
        "required_slots": {"app": "explorer"},
        "recommended_conf": 0.35,
    },
]


MUSIC_CASES: List[Case] = [
    {
        "text": "останови музыку",
        "intent": "MUSIC_PAUSE",
        "recommended_conf": 0.35,
    },
    {
        "text": "включи музыку",
        "intent": "MUSIC_PLAY",
        "recommended_conf": 0.35,
    },
    {
        "text": "поставь музыку на паузу",
        "intent": "MUSIC_PAUSE",
        "recommended_conf": 0.35,
    },
    {
        "text": "следующий трек",
        "intent": "MUSIC_NEXT",
        "recommended_conf": 0.90,
    },
    {
        "text": "предыдущий трек",
        "intent": "MUSIC_PREV",
        "recommended_conf": 0.35,
    },
    {
        "text": "перезапусти музыку",
        "intent": "MUSIC_RESTART",
        "recommended_conf": 0.90,
    },
]


EDITOR_DICTATION_CASES: List[Case] = [
    {
        "text": "нажми бэк спайс",
        "intent": "PRESS_BACKSPACE",
        "recommended_conf": 0.35,
    },
    {
        "text": "нажми бэк спейс",
        "intent": "PRESS_BACKSPACE",
        "recommended_conf": 0.35,
    },
    {
        "text": "нажми бэкспейс",
        "intent": "PRESS_BACKSPACE",
        "recommended_conf": 0.35,
    },
    {
        "text": "удали символ",
        "intent": "PRESS_BACKSPACE",
        "recommended_conf": 0.35,
    },
    {
        "text": "режим диктовки",
        "intent": "DICTATION_MODE_ON",
        "recommended_conf": 0.35,
    },
    {
        "text": "режим ввода текста",
        "intent": "DICTATION_MODE_ON",
        "recommended_conf": 0.35,
    },
    {
        "text": "выключи режим диктовки",
        "intent": "DICTATION_MODE_OFF",
        "recommended_conf": 0.90,
    },
    {
        "text": "закрой режим диктовки",
        "intent": "DICTATION_MODE_OFF",
        "recommended_conf": 0.90,
    },
    {
        "text": "нажми enter",
        "intent": "PRESS_ENTER",
        "recommended_conf": 0.35,
    },
    {
        "text": "новая строка",
        "intent": "PRESS_ENTER",
        "recommended_conf": 0.35,
    },
    {
        "text": "нажми tab",
        "intent": "PRESS_TAB",
        "recommended_conf": 0.35,
    },
    {
        "text": "отступ",
        "intent": "PRESS_TAB",
        "recommended_conf": 0.35,
    },
]


AUDIO_VOLUME_CASES: List[Case] = [
    {
        "text": "включи звук",
        "intent": "UNMUTE",
        "recommended_conf": 0.90,
    },
    {
        "text": "выключи звук",
        "intent": "MUTE",
        "recommended_conf": 0.90,
    },
    {
        "text": "переключи звук на наушники",
        "intent": "AUDIO_OUTPUT_HEADPHONES",
        "recommended_conf": 0.35,
    },
    {
        "text": "переключи звук на колонки",
        "intent": "AUDIO_OUTPUT_SPEAKERS",
        "recommended_conf": 0.35,
    },
    {
        "text": "переключи устройство вывода звука",
        "intent": "AUDIO_OUTPUT_TOGGLE",
        "recommended_conf": 0.35,
    },
    {
        "text": "сделай громче",
        "intent": "VOLUME_UP",
        "recommended_conf": 0.35,
    },
    {
        "text": "сделай тише",
        "intent": "VOLUME_DOWN",
        "recommended_conf": 0.35,
    },
    {
        "text": "прибавь звук",
        "intent": "VOLUME_UP",
        "recommended_conf": 0.35,
    },
    {
        "text": "убавь звук",
        "intent": "VOLUME_DOWN",
        "recommended_conf": 0.35,
    },
    {
        "text": "громкость 50",
        "intent": "SET_VOLUME",
        "required_slots": {"volume": 50},
        "recommended_conf": 0.90,
    },
    {
        "text": "поставь звук на 30",
        "intent": "SET_VOLUME",
        "required_slots": {"volume": 30},
        "recommended_conf": 0.90,
    },
]


OPEN_SEARCH_CASES: List[Case] = [
    {
        "text": "открой ютуб",
        "intent": "OPEN_URL",
        "required_slots": {"site": "youtube"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой гугл",
        "intent": "OPEN_URL",
        "required_slots": {"site": "google"},
        "recommended_conf": 0.35,
    },
    {
        "text": "найди котиков",
        "intent": "SEARCH_WEB",
        "required_slots": {"query": "котиков"},
        "recommended_conf": 0.35,
    },
    {
        "text": "найди на ютубе музыку",
        "intent": "SEARCH_YOUTUBE",
        "required_slots": {"query": "музыку"},
        "recommended_conf": 0.35,
    },
    {
        "text": "найди в интернете про python",
        "intent": "SEARCH_WEB",
        "required_slots": {"query": "python"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой github точка com",
        "intent": "OPEN_URL",
        "required_slots": {"site": "github"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой openai точка com",
        "intent": "OPEN_URL",
        "required_slots": {"site": "openai"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой почту джимейл",
        "intent": "OPEN_URL",
        "required_slots": {"site": "gmail"},
        "recommended_conf": 0.35,
    },
]


FOLDER_SETTINGS_CASES: List[Case] = [
    {
        "text": "открой загрузки",
        "intent": "OPEN_FOLDER",
        "required_slots": {"folder": "downloads"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой рабочий стол",
        "intent": "OPEN_FOLDER",
        "required_slots": {"folder": "desktop"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой настройки звука",
        "intent": "OPEN_SETTINGS",
        "required_slots": {"section": "sound"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой настройки bluetooth",
        "intent": "OPEN_SETTINGS",
        "required_slots": {"section": "bluetooth"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой папку загрузок",
        "intent": "OPEN_FOLDER",
        "required_slots": {"folder": "downloads"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой папку документы",
        "intent": "OPEN_FOLDER",
        "required_slots": {"folder": "documents"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой настройки интернета",
        "intent": "OPEN_SETTINGS",
        "required_slots": {"section": "network"},
        "recommended_conf": 0.35,
    },
    {
        "text": "открой параметры интернета",
        "intent": "OPEN_SETTINGS",
        "required_slots": {"section": "network"},
        "recommended_conf": 0.35,
    },
]


WINDOW_SYSTEM_CASES: List[Case] = [
    {
        "text": "открой диспетчер задач",
        "intent": "OPEN_TASK_MANAGER",
        "recommended_conf": 0.35,
    },
    {
        "text": "закрой активное окно",
        "intent": "CLOSE_ACTIVE_WINDOW",
        "recommended_conf": 0.35,
    },
    {
        "text": "что за окно открыто",
        "intent": "ACTIVE_WINDOW_INFO",
        "recommended_conf": 0.35,
    },
    {
        "text": "покажи мой ip",
        "intent": "SHOW_IP",
        "recommended_conf": 0.35,
    },
    {
        "text": "очисти корзину",
        "intent": "EMPTY_RECYCLE_BIN",
        "recommended_conf": 0.35,
    },
    {
        "text": "заблокируй компьютер",
        "intent": "LOCK_SCREEN",
        "recommended_conf": 0.35,
    },
]


TTS_CASES: List[Case] = [
    {
        "text": "замолчи",
        "intent": "STOP_TALKING",
        "recommended_conf": 0.35,
    },
    {
        "text": "прекрати говорить",
        "intent": "STOP_TALKING",
        "recommended_conf": 0.35,
    },
    {
        "text": "остановись говорить",
        "intent": "STOP_TALKING",
        "recommended_conf": 0.35,
    },
]


NEGATIVE_CASES: List[Case] = [
    {
        "text": "назад",
        "intent": None,
        "forbidden_intents": ["MUSIC_PREV", "PRESS_BACKSPACE"],
    },
    {
        "text": "закрой режим",
        "intent": None,
        "forbidden_intents": ["CLOSE_APP", "DICTATION_MODE_OFF"],
    },
    {
        "text": "открой",
        "intent": None,
        "forbidden_intents": ["OPEN_APP", "OPEN_URL", "OPEN_FOLDER", "OPEN_SETTINGS"],
    },
    {
        "text": "громкость",
        "intent": None,
        "forbidden_intents": ["SET_VOLUME", "VOLUME_UP", "VOLUME_DOWN"],
    },
    {
        "text": "звук",
        "intent": None,
        "forbidden_intents": ["SET_VOLUME", "MUTE", "UNMUTE", "VOLUME_UP", "VOLUME_DOWN"],
    },
    {
        "text": "закрой",
        "intent": None,
        "forbidden_intents": ["CLOSE_APP", "CLOSE_ACTIVE_WINDOW"],
    },
    {
        "text": "найди",
        "intent": None,
        "forbidden_intents": ["SEARCH_WEB", "SEARCH_YOUTUBE"],
    },
    {
        "text": "переключи",
        "intent": None,
        "forbidden_intents": [
            "AUDIO_OUTPUT_TOGGLE",
            "AUDIO_OUTPUT_HEADPHONES",
            "AUDIO_OUTPUT_SPEAKERS",
        ],
    },
]


CASE_GROUPS: List[tuple[str, List[Case]]] = [
    ("base", BASE_CASES),
    ("app", APP_CASES),
    ("music", MUSIC_CASES),
    ("editor_dictation", EDITOR_DICTATION_CASES),
    ("audio_volume", AUDIO_VOLUME_CASES),
    ("open_search", OPEN_SEARCH_CASES),
    ("folder_settings", FOLDER_SETTINGS_CASES),
    ("window_system", WINDOW_SYSTEM_CASES),
    ("tts", TTS_CASES),
    ("negative", NEGATIVE_CASES),
]


def build_test_cases() -> List[Case]:
    rows: List[Case] = []

    for group_name, cases in CASE_GROUPS:
        for case in cases:
            row = dict(case)
            row["group"] = group_name
            rows.append(row)

    return rows


TEST_CASES = build_test_cases()


def _clean_examples(examples: Any) -> List[str]:
    if not isinstance(examples, list):
        return []

    return [
        ex.strip()
        for ex in examples
        if isinstance(ex, str) and ex.strip()
    ]


def _collect_intents_from_rows(rows: Any) -> Set[str]:
    result: Set[str] = set()

    if not isinstance(rows, list):
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue

        intent = str(row.get("intent") or "").upper().strip()
        examples = _clean_examples(row.get("examples") or [])

        if intent and examples:
            result.add(intent)

    return result


def load_project_intents() -> Set[str]:
    with INTENTS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return _collect_intents_from_rows(data)

    if isinstance(data, dict):
        for key in ("intents", "data", "items"):
            if isinstance(data.get(key), list):
                result = _collect_intents_from_rows(data.get(key))
                if result:
                    return result

        result: Set[str] = set()

        for key, value in data.items():
            intent = str(key or "").upper().strip()
            if not intent:
                continue

            if isinstance(value, list) and _clean_examples(value):
                result.add(intent)
                continue

            if isinstance(value, dict) and _clean_examples(value.get("examples") or []):
                result.add(intent)
                continue

        return result

    return set()


def build_intent_coverage() -> Dict[str, Any]:
    project_intents = load_project_intents()

    covered_intents = {
        str(case.get("intent") or "").upper()
        for case in TEST_CASES
        if case.get("intent") is not None
    }
    covered_intents = {intent for intent in covered_intents if intent}

    missing_eval_intents = sorted(project_intents - covered_intents)
    extra_eval_intents = sorted(covered_intents - project_intents)

    return {
        "project_intents": len(project_intents),
        "covered_intents": len(covered_intents),
        "missing_eval_intents": missing_eval_intents,
        "extra_eval_intents": extra_eval_intents,
    }


def check_case(case: Dict[str, Any]) -> Dict[str, Any]:
    text = str(case["text"])
    group = str(case.get("group") or "unknown")

    has_expected_intent = "intent" in case
    expected_intent_value = case.get("intent")

    if expected_intent_value is None:
        expected_intent = None
    else:
        expected_intent = str(expected_intent_value).upper()

    forbidden_intents = {
        str(intent).upper()
        for intent in (case.get("forbidden_intents") or [])
        if str(intent).strip()
    }

    required_slots = dict(case.get("required_slots") or {})
    recommended_conf = float(case.get("recommended_conf") or 0.0)

    meta = predict(text)
    actual_intent = str(meta.get("intent") or "").upper()
    actual_conf = float(meta.get("confidence") or 0.0)
    actual_slots = dict(meta.get("slots") or {})
    top_candidates = predict_candidates(text, limit=5)

    hard_fail_reasons: List[str] = []
    warnings: List[str] = []

    if has_expected_intent:
        if expected_intent is None:
            if actual_intent:
                hard_fail_reasons.append(
                    f"expected no accepted intent, actual={actual_intent}"
                )
        elif actual_intent != expected_intent:
            hard_fail_reasons.append(
                f"intent mismatch: expected={expected_intent}, actual={actual_intent or 'None'}"
            )

    if actual_intent and actual_intent in forbidden_intents:
        hard_fail_reasons.append(
            f"forbidden intent matched: actual={actual_intent}, forbidden={sorted(forbidden_intents)}"
        )

    for key, expected_value in required_slots.items():
        actual_value = actual_slots.get(key)

        if isinstance(expected_value, list):
            ok = actual_value in expected_value
        else:
            ok = actual_value == expected_value

        if not ok:
            hard_fail_reasons.append(
                f"slot mismatch for '{key}': expected={expected_value}, actual={actual_value}"
            )

    if expected_intent is not None and recommended_conf > 0 and actual_conf < recommended_conf:
        warnings.append(
            f"low confidence: got={actual_conf:.2f}, recommended>={recommended_conf:.2f}"
        )

    return {
        "group": group,
        "text": text,
        "expected_intent": expected_intent,
        "forbidden_intents": sorted(forbidden_intents),
        "actual_intent": actual_intent or None,
        "confidence": actual_conf,
        "expected_slots": required_slots,
        "actual_slots": actual_slots,
        "rule": meta.get("_rule"),
        "hard_fail_reasons": hard_fail_reasons,
        "warnings": warnings,
        "top_candidates": top_candidates,
        "ok": len(hard_fail_reasons) == 0,
    }


def main() -> int:
    results = [check_case(case) for case in TEST_CASES]

    hard_fail_count = 0
    warning_count = 0

    group_stats: Dict[str, Dict[str, int]] = {}

    print("=== NLU EVAL REPORT ===")

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
                "hard_fail_count": 0,
                "warning_count": 0,
            },
        )
        stats["total"] += 1

        print()
        print(f"{idx}. {result['text']}")
        payload = {
            "group": result["group"],
            "expected_intent": result["expected_intent"],
            "forbidden_intents": result["forbidden_intents"],
            "actual_intent": result["actual_intent"],
            "confidence": round(float(result["confidence"]), 4),
            "expected_slots": result["expected_slots"],
            "actual_slots": result["actual_slots"],
            "rule": result["rule"],
        }

        if result["hard_fail_reasons"] or result["warnings"]:
            payload["top_candidates"] = result["top_candidates"]

        print(json.dumps(payload, ensure_ascii=False))

        if result["hard_fail_reasons"]:
            hard_fail_count += 1
            stats["hard_fail_count"] += 1

            for reason in result["hard_fail_reasons"]:
                print(f"[FAIL] {reason}")
        else:
            print("[OK] hard checks passed")

        if result["warnings"]:
            warning_count += len(result["warnings"])
            stats["warning_count"] += len(result["warnings"])

            for warning in result["warnings"]:
                print(f"[WARN] {warning}")

    print()
    print("=== GROUP SUMMARY ===")
    print(json.dumps(group_stats, ensure_ascii=False, indent=2))

    coverage = build_intent_coverage()
    coverage_fail_count = 0

    if coverage["missing_eval_intents"] or coverage["extra_eval_intents"]:
        coverage_fail_count = 1

    print()
    print("=== INTENT COVERAGE ===")
    print(json.dumps(coverage, ensure_ascii=False, indent=2))

    if coverage_fail_count:
        print("[FAIL] Intent coverage check failed.")
    else:
        print("[OK] Intent coverage check passed.")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "total_cases": len(results),
                "hard_fail_count": hard_fail_count,
                "warning_count": warning_count,
                "coverage_fail_count": coverage_fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if hard_fail_count > 0 or coverage_fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())