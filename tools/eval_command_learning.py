from __future__ import annotations

import json
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.command_learning import (
    log_command_action_failure,
    log_command_observation,
    log_not_accepted_command,
)


class FakeLearningMemory:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def log_command(self, **kwargs: Any) -> None:
        self.calls.append({"method": "log_command", "kwargs": kwargs})

    def log_resolver_candidate(self, **kwargs: Any) -> None:
        self.calls.append({"method": "log_resolver_candidate", "kwargs": kwargs})

    def log_nlu_hard_case(self, **kwargs: Any) -> None:
        self.calls.append({"method": "log_nlu_hard_case", "kwargs": kwargs})

    def log_action_failure(self, **kwargs: Any) -> None:
        self.calls.append({"method": "log_action_failure", "kwargs": kwargs})


def _methods(memory: FakeLearningMemory) -> List[str]:
    return [call["method"] for call in memory.calls]


def _print_case(name: str, expected: List[str], actual: List[str]) -> bool:
    ok = actual == expected

    print()
    print(f"--- {name} ---")
    print(
        json.dumps(
            {
                "expected": expected,
                "actual": actual,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if ok:
        print("[OK] command learning case")
    else:
        print("[FAIL] command learning case")

    return ok


def main() -> int:
    fail_count = 0

    print("=== COMMAND LEARNING EVAL REPORT ===")

    memory = FakeLearningMemory()

    log_command_observation(
        learning_memory=memory,
        raw_text="открой ютуб",
        final_text="открой ютуб",
        meta={
            "intent": "OPEN_URL",
            "confidence": 0.9,
            "slots": {"url": "https://www.youtube.com"},
        },
        mode="direct",
        accepted=True,
        immediate_label="immediate",
        missing_slots=[],
    )

    if not _print_case(
        "accepted command without missing slots",
        ["log_command"],
        _methods(memory),
    ):
        fail_count += 1

    memory = FakeLearningMemory()

    log_command_observation(
        learning_memory=memory,
        raw_text="открой де скоро",
        final_text="открой де скоро",
        meta={
            "intent": "OPEN_URL",
            "confidence": 0.8,
            "slots": {},
        },
        mode="direct",
        accepted=True,
        immediate_label="immediate",
        missing_slots=["url"],
    )

    if not _print_case(
        "accepted command with missing slots",
        ["log_command", "log_resolver_candidate"],
        _methods(memory),
    ):
        fail_count += 1

    memory = FakeLearningMemory()

    log_not_accepted_command(
        learning_memory=memory,
        raw_text="непонятная команда",
        final_text="непонятная команда",
        meta={
            "intent": None,
            "confidence": 0.0,
            "slots": {},
        },
        mode="direct",
        reason="not_accepted",
    )

    if not _print_case(
        "not accepted command",
        ["log_nlu_hard_case"],
        _methods(memory),
    ):
        fail_count += 1

    memory = FakeLearningMemory()

    log_command_action_failure(
        learning_memory=memory,
        raw_text="открой блокнот",
        final_text="открой блокнот",
        meta={
            "intent": "OPEN_APP",
            "confidence": 0.9,
            "slots": {"app": "notepad"},
        },
        mode="direct",
        error=RuntimeError("fake failure"),
    )

    if not _print_case(
        "action failure",
        ["log_action_failure"],
        _methods(memory),
    ):
        fail_count += 1

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "total_cases": 4,
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())