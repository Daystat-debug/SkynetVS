from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INTENTS_PATH = PROJECT_ROOT / "data" / "intents.json"
TEMPLATES_PATH = PROJECT_ROOT / "data" / "say_templates.json"
ACTIONS_PATH = PROJECT_ROOT / "modules" / "actions.py"


SUSPICIOUS_TOKENS = {
    "мужик",
    "дискомфорт",
    "де скоро",
    "гед хаб",
    "гид хаб",
    "диск орды",
}


CORE_HANDLED_INTENTS = {
    "DICTATION_MODE_ON",
    "DICTATION_MODE_OFF",
    "GREET",
    "STOP_LISTEN",
    "STOP_TALKING",
}


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _clean_examples(examples: Any) -> List[str]:
    clean_examples: List[str] = []

    if not isinstance(examples, list):
        return clean_examples

    for ex in examples:
        if isinstance(ex, str) and ex.strip():
            clean_examples.append(ex.strip())

    return clean_examples


def _collect_intents_from_rows(rows: Any) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}

    if not isinstance(rows, list):
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue

        intent = str(row.get("intent") or "").upper().strip()
        examples = _clean_examples(row.get("examples") or [])

        if not intent:
            continue

        result[intent] = examples

    return result


def _collect_intents(data: Any) -> Dict[str, List[str]]:
    """
    Поддерживаем несколько возможных форматов data/intents.json.

    Формат 1:
      [
        {"intent": "GREET", "examples": [...]}
      ]

    Формат 2:
      {
        "intents": [
          {"intent": "GREET", "examples": [...]}
        ]
      }

    Формат 3:
      {
        "GREET": ["привет", "здравствуй"],
        "OPEN_APP": [...]
      }

    Формат 4:
      {
        "GREET": {"examples": ["привет"]},
        "OPEN_APP": {"examples": [...]}
      }
    """
    # Формат 1: верхний уровень — список.
    if isinstance(data, list):
        result = _collect_intents_from_rows(data)
        if result:
            return result

    # Форматы с верхним уровнем object.
    if isinstance(data, dict):
        # Формат 2: {"intents": [...]}
        for key in ("intents", "data", "items"):
            if isinstance(data.get(key), list):
                result = _collect_intents_from_rows(data.get(key))
                if result:
                    return result

        # Формат 3/4: {"GREET": [...]} или {"GREET": {"examples": [...]}}
        result: Dict[str, List[str]] = {}

        for key, value in data.items():
            intent = str(key or "").upper().strip()
            if not intent:
                continue

            if isinstance(value, list):
                result[intent] = _clean_examples(value)
                continue

            if isinstance(value, dict):
                result[intent] = _clean_examples(value.get("examples") or [])
                continue

        if result:
            return result

    raise ValueError(
        "Не удалось распознать формат data/intents.json. "
        "Ожидается список интентов, объект с ключом 'intents', "
        "или объект вида {'INTENT': [...]}."
    )


def _collect_templates(data: Any) -> Set[str]:
    """
    Ожидаемый формат say_templates.json:
      {
        "INTENT": [...],
        "INTENT_UNCERTAIN": [...]
      }
    """
    if not isinstance(data, dict):
        raise ValueError("data/say_templates.json должен быть объектом")

    return {str(k).upper().strip() for k in data.keys() if str(k).strip()}


def _extract_handler_keys(source: str, attr_name: str) -> Set[str]:
    """
    Статически вытаскивает ключи из self._reply_handlers / self._execute_handlers.

    Не идеальный parser Python, но для текущей структуры Actions достаточно.
    """
    pattern = re.compile(
        rf"self\.{re.escape(attr_name)}\s*:[^=]+=\s*\{{(?P<body>.*?)\n\s*\}}",
        re.DOTALL,
    )

    match = pattern.search(source)
    if not match:
        return set()

    body = match.group("body")
    return {
        m.group(1).upper()
        for m in re.finditer(r'"([A-Z0-9_]+)"\s*:', body)
    }


def _find_duplicate_examples(intents: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    by_example: Dict[str, List[str]] = defaultdict(list)

    for intent, examples in intents.items():
        for ex in examples:
            by_example[_norm(ex)].append(intent)

    duplicates: List[Dict[str, Any]] = []

    for example, owners in by_example.items():
        unique_owners = sorted(set(owners))
        if len(unique_owners) > 1:
            duplicates.append(
                {
                    "example": example,
                    "intents": unique_owners,
                }
            )

    return sorted(duplicates, key=lambda x: x["example"])


def _find_suspicious_examples(intents: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for intent, examples in intents.items():
        for ex in examples:
            n = _norm(ex)
            hits = sorted(token for token in SUSPICIOUS_TOKENS if token in n)
            if hits:
                rows.append(
                    {
                        "intent": intent,
                        "example": ex,
                        "tokens": hits,
                    }
                )

    return rows


def _print_section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def _print_rows(rows: Iterable[Any]) -> None:
    printed = False
    for idx, row in enumerate(rows, start=1):
        printed = True
        print(f"{idx}. {json.dumps(row, ensure_ascii=False)}")

    if not printed:
        print("нет данных")


def main() -> int:
    intents_data = _load_json(INTENTS_PATH)
    templates_data = _load_json(TEMPLATES_PATH)
    actions_source = _read_text(ACTIONS_PATH)

    intents = _collect_intents(intents_data)
    template_keys = _collect_templates(templates_data)

    reply_handlers = _extract_handler_keys(actions_source, "_reply_handlers")
    execute_handlers = _extract_handler_keys(actions_source, "_execute_handlers")
    action_handlers = reply_handlers | execute_handlers

    intent_keys = set(intents.keys())

    duplicate_examples = _find_duplicate_examples(intents)
    suspicious_examples = _find_suspicious_examples(intents)

    missing_any_handler = sorted(intent_keys - action_handlers - CORE_HANDLED_INTENTS)
    handler_without_intent = sorted(action_handlers - intent_keys)
    core_handled_present = sorted(intent_keys & CORE_HANDLED_INTENTS)

    missing_base_template = sorted(
        intent
        for intent in intent_keys
        if intent not in template_keys
    )

    missing_uncertain_template = sorted(
        intent
        for intent in intent_keys
        if f"{intent}_UNCERTAIN" not in template_keys
    )

    empty_examples = sorted(
        intent
        for intent, examples in intents.items()
        if not examples
    )

    _print_section("COMMAND AUDIT TOTALS")
    print(
        json.dumps(
            {
                "intents": len(intent_keys),
                "reply_handlers": len(reply_handlers),
                "execute_handlers": len(execute_handlers),
                "templates": len(template_keys),
                "core_handled_present": len(core_handled_present),
                "duplicate_examples": len(duplicate_examples),
                "suspicious_examples": len(suspicious_examples),
                "empty_examples": len(empty_examples),
                "missing_any_handler": len(missing_any_handler),
                "handler_without_intent": len(handler_without_intent),
                "missing_base_template": len(missing_base_template),
                "missing_uncertain_template": len(missing_uncertain_template),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    _print_section("DUPLICATE EXAMPLES ACROSS INTENTS")
    _print_rows(duplicate_examples)

    _print_section("SUSPICIOUS EXAMPLES IN intents.json")
    _print_rows(suspicious_examples)

    _print_section("INTENTS WITHOUT ANY ACTION HANDLER")
    _print_rows(missing_any_handler)

    _print_section("CORE-HANDLED INTENTS")
    _print_rows(core_handled_present)

    _print_section("ACTION HANDLERS WITHOUT INTENT EXAMPLES")
    _print_rows(handler_without_intent)

    _print_section("INTENTS WITHOUT BASE TEMPLATE")
    _print_rows(missing_base_template)

    _print_section("INTENTS WITHOUT UNCERTAIN TEMPLATE")
    _print_rows(missing_uncertain_template)

    _print_section("INTENTS WITH EMPTY EXAMPLES")
    _print_rows(empty_examples)

    hard_fail = bool(duplicate_examples or suspicious_examples or empty_examples)

    print()
    if hard_fail:
        print("[FAIL] Command audit found critical problems.")
        return 1

    print("[OK] Command audit passed critical checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())