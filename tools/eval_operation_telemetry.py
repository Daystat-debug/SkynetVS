from __future__ import annotations

import json

from typing import Any

from modules.core.operation_telemetry import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    OperationTelemetry,
)


class FakeClock:
    def __init__(self, value: float = 1000.0):
        self.value = float(value)

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += float(seconds)


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count

        case_count += 1
        ok = actual == expected

        print()
        print(f"=== {name} ===")
        print(json.dumps(
            {
                "actual": actual,
                "expected": expected,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ))

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    clock = FakeClock()
    telemetry = OperationTelemetry(time_func=clock)
    snapshot = telemetry.snapshot()

    check(
        "INITIAL SNAPSHOT",
        {
            "has_attempt": snapshot.has_attempt,
            "last_outcome": snapshot.last_outcome,
            "last_attempt_at": snapshot.last_attempt_at,
            "last_error": snapshot.last_error,
            "consecutive_failures": snapshot.consecutive_failures,
        },
        {
            "has_attempt": False,
            "last_outcome": "",
            "last_attempt_at": None,
            "last_error": "",
            "consecutive_failures": 0,
        },
    )

    telemetry.record_success(duration_ms=12.6)
    snapshot = telemetry.snapshot()

    check(
        "SUCCESS SNAPSHOT",
        {
            "last_outcome": snapshot.last_outcome,
            "last_attempt_at": snapshot.last_attempt_at,
            "last_success_at": snapshot.last_success_at,
            "last_duration_ms": snapshot.last_duration_ms,
            "last_error": snapshot.last_error,
            "consecutive_failures": snapshot.consecutive_failures,
        },
        {
            "last_outcome": OUTCOME_SUCCESS,
            "last_attempt_at": 1000.0,
            "last_success_at": 1000.0,
            "last_duration_ms": 13,
            "last_error": "",
            "consecutive_failures": 0,
        },
    )

    clock.advance(5.0)
    telemetry.record_failure(RuntimeError("network failed"), duration_ms=-5)
    snapshot = telemetry.snapshot()

    check(
        "FAILURE PRESERVES LAST SUCCESS",
        {
            "last_outcome": snapshot.last_outcome,
            "last_attempt_at": snapshot.last_attempt_at,
            "last_success_at": snapshot.last_success_at,
            "last_failure_at": snapshot.last_failure_at,
            "last_duration_ms": snapshot.last_duration_ms,
            "last_error": snapshot.last_error,
            "consecutive_failures": snapshot.consecutive_failures,
        },
        {
            "last_outcome": OUTCOME_FAILURE,
            "last_attempt_at": 1005.0,
            "last_success_at": 1000.0,
            "last_failure_at": 1005.0,
            "last_duration_ms": 0,
            "last_error": "network failed",
            "consecutive_failures": 1,
        },
    )

    clock.advance(5.0)
    telemetry.record_failure("", duration_ms=None)
    snapshot = telemetry.snapshot()

    check(
        "CONSECUTIVE FAILURES INCREMENT",
        {
            "last_outcome": snapshot.last_outcome,
            "last_attempt_at": snapshot.last_attempt_at,
            "last_error": snapshot.last_error,
            "consecutive_failures": snapshot.consecutive_failures,
        },
        {
            "last_outcome": OUTCOME_FAILURE,
            "last_attempt_at": 1010.0,
            "last_error": "Unknown operation failure",
            "consecutive_failures": 2,
        },
    )

    clock.advance(5.0)
    telemetry.record_success(duration_ms="invalid")
    snapshot = telemetry.snapshot()

    check(
        "SUCCESS RESETS CURRENT FAILURE",
        {
            "last_outcome": snapshot.last_outcome,
            "last_attempt_at": snapshot.last_attempt_at,
            "last_success_at": snapshot.last_success_at,
            "last_failure_at": snapshot.last_failure_at,
            "last_duration_ms": snapshot.last_duration_ms,
            "last_error": snapshot.last_error,
            "consecutive_failures": snapshot.consecutive_failures,
        },
        {
            "last_outcome": OUTCOME_SUCCESS,
            "last_attempt_at": 1015.0,
            "last_success_at": 1015.0,
            "last_failure_at": 1010.0,
            "last_duration_ms": None,
            "last_error": "",
            "consecutive_failures": 0,
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps(
        {
            "case_count": case_count,
            "fail_count": fail_count,
        },
        ensure_ascii=False,
        indent=2,
    ))

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())