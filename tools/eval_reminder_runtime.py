from __future__ import annotations

import ast
import json

from pathlib import Path
from typing import Any

from modules.reminder_runtime import (
    build_reminder_fired_message,
    build_reminder_fired_queue_event,
)
from modules.reminder_service import ReminderFiredEvent


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"


def _imported_names(tree: ast.AST) -> set[str]:
    result: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue

        for alias in node.names:
            result.add(alias.asname or alias.name)

    return result


def _call_names(tree: ast.AST) -> list[str]:
    result: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        if isinstance(func, ast.Name):
            result.append(func.id)
        elif isinstance(func, ast.Attribute):
            result.append(func.attr)

    return result


def _call_has_keyword(tree: ast.AST, call_name: str, keyword_name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        name = ""

        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr

        if name != call_name:
            continue

        if any(keyword.arg == keyword_name for keyword in node.keywords):
            return True

    return False


def _string_constant_count(tree: ast.AST, value: str) -> int:
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value == value
    )


def main() -> int:
    fail_count = 0
    case_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal fail_count, case_count

        case_count += 1
        ok = actual == expected

        print()
        print(f"=== {name} ===")
        print(
            json.dumps(
                {
                    "actual": actual,
                    "expected": expected,
                    "ok": ok,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    event = ReminderFiredEvent(
        reminder_id="r1",
        text="проверить духовку",
        due_at_epoch=100.0,
        created_at_epoch=10.0,
        fired_at_epoch=101.5,
        late_by_seconds=1.5,
    )

    check(
        "QUEUE EVENT PAYLOAD",
        build_reminder_fired_queue_event(event),
        {
            "type": "reminder_fired",
            "reminder": {
                "reminder_id": "r1",
                "text": "проверить духовку",
                "due_at_epoch": 100.0,
                "created_at_epoch": 10.0,
                "fired_at_epoch": 101.5,
                "late_by_seconds": 1.5,
            },
        },
    )

    check(
        "FIRED MESSAGE",
        build_reminder_fired_message({"text": "проверить духовку"}),
        "Напоминаю: проверить духовку",
    )

    check(
        "FIRED MESSAGE FALLBACK",
        build_reminder_fired_message({}),
        "Сработало напоминание.",
    )

    source = MAIN_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MAIN_PATH))
    imported = _imported_names(tree)
    call_names = _call_names(tree)

    check(
        "MAIN IMPORTS REMINDER TYPES",
        {
            "ReminderRepository",
            "ReminderService",
            "ReminderFiredEvent",
            "build_reminder_fired_queue_event",
            "build_reminder_fired_message",
        }.issubset(imported),
        True,
    )

    check(
        "MAIN CREATES REMINDER REPOSITORY",
        "ReminderRepository" in call_names,
        True,
    )

    check(
        "MAIN CREATES REMINDER SERVICE",
        (
            "ReminderService" in call_names
            and _call_has_keyword(tree, "ReminderService", "repository")
            and _call_has_keyword(tree, "ReminderService", "on_fired")
        ),
        True,
    )

    check(
        "ACTIONS RECEIVES REMINDER SERVICE",
        _call_has_keyword(tree, "Actions", "reminder_service"),
        True,
    )

    check(
        "MAIN PRODUCES AND CONSUMES REMINDER EVENT",
        _string_constant_count(tree, "reminder_fired") >= 2,
        True,
    )

    check(
        "MAIN DELEGATES REMINDER SERVICE SHUTDOWN",
        (
            "shutdown_runtime_services" in imported
            and "shutdown_runtime_services" in call_names
            and _call_has_keyword(tree, "shutdown_runtime_services", "reminder_service")
        ),
        True,
    )

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "case_count": case_count,
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
