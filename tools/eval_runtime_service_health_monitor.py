from __future__ import annotations

import ast
import json
import os

from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.config import Settings
from modules.runtime_service_health import (
    RuntimeServiceHealth,
    STATUS_DEGRADED,
    STATUS_READY,
    STATUS_UNKNOWN,
)
from modules.runtime_service_health_monitor import (
    RuntimeServiceHealthMonitor,
    format_runtime_service_health_transition_lines,
    publish_runtime_service_health_transition,
    runtime_service_health_transition_payload,
)


class FakeClock:
    def __init__(self, value: float = 1000.0):
        self.value = float(value)

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += float(seconds)


def _report(
    *items: tuple[str, str, str, dict[str, Any]],
):
    health = RuntimeServiceHealth()

    for name, status, error, details in items:
        if status == STATUS_READY:
            health.ready(
                name,
                details=details,
            )
        elif status == STATUS_DEGRADED:
            health.degraded(
                name,
                details=details,
                error=error,
            )
        elif status == STATUS_UNKNOWN:
            health.unknown(
                name,
                details=details,
            )
        else:
            health.disabled(
                name,
                details=details,
                error=error,
            )

    return health.build()


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(
        name: str,
        actual: Any,
        expected: Any,
    ) -> None:
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

    invalid_count = 0

    for interval in (
        0.0,
        float("nan"),
        float("inf"),
        "broken",
    ):
        try:
            RuntimeServiceHealthMonitor(
                interval_sec=interval,
            )
        except ValueError:
            invalid_count += 1

    check(
        "INVALID INTERVAL REJECTED",
        invalid_count,
        4,
    )

    clock = FakeClock()
    initial_report = _report(
        (
            "stt",
            STATUS_UNKNOWN,
            "",
            {"reason": "not_started"},
        )
    )
    provider_calls = 0

    def disabled_provider():
        nonlocal provider_calls
        provider_calls += 1
        return initial_report

    disabled_monitor = RuntimeServiceHealthMonitor(
        enabled=False,
        interval_sec=5.0,
        monotonic_func=clock,
    )
    disabled_monitor.set_baseline(
        initial_report
    )
    disabled_poll = disabled_monitor.poll_if_due(
        disabled_provider
    )

    check(
        "DISABLED MONITOR DOES NOT POLL",
        {
            "enabled": disabled_monitor.enabled,
            "timeout": disabled_monitor.seconds_until_poll(),
            "attempted": disabled_poll.attempted,
            "provider_calls": provider_calls,
        },
        {
            "enabled": False,
            "timeout": None,
            "attempted": False,
            "provider_calls": 0,
        },
    )

    clock = FakeClock()
    monitor = RuntimeServiceHealthMonitor(
        interval_sec=5.0,
        monotonic_func=clock,
    )
    monitor.set_baseline(
        initial_report
    )
    early_poll = monitor.poll_if_due(
        lambda: initial_report
    )

    check(
        "BASELINE SCHEDULES FIRST POLL",
        {
            "interval": monitor.interval_sec,
            "timeout": monitor.seconds_until_poll(),
            "attempted": early_poll.attempted,
        },
        {
            "interval": 5.0,
            "timeout": 5.0,
            "attempted": False,
        },
    )

    clock.advance(5.0)

    def slow_provider():
        clock.advance(3.0)
        return initial_report

    slow_poll = monitor.poll_if_due(
        slow_provider
    )

    check(
        "NEXT POLL IS SCHEDULED FROM COMPLETION",
        {
            "attempted": slow_poll.attempted,
            "timeout": monitor.seconds_until_poll(),
        },
        {
            "attempted": True,
            "timeout": 5.0,
        },
    )

    clock.advance(5.0)
    ready_report = _report(
        (
            "stt",
            STATUS_READY,
            "",
            {"audio_block_count": 100},
        )
    )
    ready_poll = monitor.poll_if_due(
        lambda: ready_report
    )
    ready_transition = ready_poll.transition

    check(
        "UNKNOWN TO READY EMITS TRANSITION",
        {
            "attempted": ready_poll.attempted,
            "previous_status": (
                ready_transition.previous_status
                if ready_transition
                else None
            ),
            "current_status": (
                ready_transition.current_status
                if ready_transition
                else None
            ),
            "changes": [
                {
                    "name": item.name,
                    "before": item.previous_status,
                    "after": item.current_status,
                }
                for item in (
                    ready_transition.changed_services
                    if ready_transition
                    else ()
                )
            ],
        },
        {
            "attempted": True,
            "previous_status": STATUS_UNKNOWN,
            "current_status": STATUS_READY,
            "changes": [
                {
                    "name": "stt",
                    "before": STATUS_UNKNOWN,
                    "after": STATUS_READY,
                }
            ],
        },
    )

    clock.advance(5.0)
    volatile_report = _report(
        (
            "stt",
            STATUS_READY,
            "",
            {"audio_block_count": 9999},
        )
    )
    volatile_poll = monitor.poll_if_due(
        lambda: volatile_report
    )

    check(
        "VOLATILE DETAILS DO NOT EMIT",
        {
            "attempted": volatile_poll.attempted,
            "transition": volatile_poll.transition,
        },
        {
            "attempted": True,
            "transition": None,
        },
    )

    clock = FakeClock()
    degraded_report = _report(
        (
            "stt",
            STATUS_DEGRADED,
            "audio stalled",
            {"age": 5.0},
        )
    )
    monitor = RuntimeServiceHealthMonitor(
        interval_sec=5.0,
        monotonic_func=clock,
    )
    monitor.set_baseline(
        degraded_report
    )
    clock.advance(5.0)
    same_error_poll = monitor.poll_if_due(
        lambda: _report(
            (
                "stt",
                STATUS_DEGRADED,
                "audio stalled",
                {"age": 10.0},
            )
        )
    )

    check(
        "SAME DEGRADED ERROR IS DEDUPED",
        same_error_poll.transition,
        None,
    )

    clock.advance(5.0)
    changed_error_poll = monitor.poll_if_due(
        lambda: _report(
            (
                "stt",
                STATUS_DEGRADED,
                "recognizer stalled",
                {"age": 15.0},
            )
        )
    )
    changed_error = (
        changed_error_poll.transition.changed_services[0]
        if changed_error_poll.transition
        else None
    )

    check(
        "CHANGED DEGRADED ERROR EMITS",
        {
            "before_status": (
                changed_error.previous_status
                if changed_error
                else None
            ),
            "after_status": (
                changed_error.current_status
                if changed_error
                else None
            ),
            "before_error": (
                changed_error.previous_error
                if changed_error
                else None
            ),
            "after_error": (
                changed_error.current_error
                if changed_error
                else None
            ),
        },
        {
            "before_status": STATUS_DEGRADED,
            "after_status": STATUS_DEGRADED,
            "before_error": "audio stalled",
            "after_error": "recognizer stalled",
        },
    )

    clock = FakeClock()
    monitor = RuntimeServiceHealthMonitor(
        interval_sec=5.0,
        monotonic_func=clock,
    )
    monitor.set_baseline(
        _report(
            (
                "stt",
                STATUS_UNKNOWN,
                "",
                {},
            ),
            (
                "tts",
                STATUS_UNKNOWN,
                "",
                {},
            ),
        )
    )
    clock.advance(5.0)
    mixed_report = _report(
        (
            "stt",
            STATUS_READY,
            "",
            {},
        ),
        (
            "tts",
            STATUS_DEGRADED,
            "player failed",
            {},
        ),
    )
    mixed_poll = monitor.poll_if_due(
        lambda: mixed_report
    )
    mixed_transition = mixed_poll.transition
    mixed_payload = (
        runtime_service_health_transition_payload(
            mixed_transition
        )
        if mixed_transition
        else {}
    )

    check(
        "MULTIPLE SERVICE CHANGES INCLUDE FULL REPORT",
        {
            "previous_status": mixed_payload.get(
                "previous_status"
            ),
            "current_status": mixed_payload.get(
                "current_status"
            ),
            "changed_services": mixed_payload.get(
                "changed_services"
            ),
            "report_status": (
                mixed_payload.get("report") or {}
            ).get("status"),
        },
        {
            "previous_status": STATUS_UNKNOWN,
            "current_status": STATUS_DEGRADED,
            "changed_services": [
                {
                    "name": "stt",
                    "previous_status": STATUS_UNKNOWN,
                    "current_status": STATUS_READY,
                    "previous_error": "",
                    "current_error": "",
                },
                {
                    "name": "tts",
                    "previous_status": STATUS_UNKNOWN,
                    "current_status": STATUS_DEGRADED,
                    "previous_error": "",
                    "current_error": "player failed",
                },
            ],
            "report_status": STATUS_DEGRADED,
        },
    )

    clock = FakeClock()
    monitor = RuntimeServiceHealthMonitor(
        interval_sec=5.0,
        monotonic_func=clock,
    )
    monitor.set_baseline(
        _report(
            (
                "stt",
                STATUS_READY,
                "",
                {},
            ),
            (
                "weather",
                STATUS_READY,
                "",
                {},
            ),
        )
    )
    clock.advance(5.0)
    service_set_poll = monitor.poll_if_due(
        lambda: _report(
            (
                "stt",
                STATUS_READY,
                "",
                {},
            ),
            (
                "timer",
                STATUS_READY,
                "",
                {},
            ),
        )
    )

    check(
        "ADDED AND REMOVED SERVICES ARE REPORTED",
        [
            {
                "name": item.name,
                "before": item.previous_status,
                "after": item.current_status,
            }
            for item in (
                service_set_poll.transition.changed_services
                if service_set_poll.transition
                else ()
            )
        ],
        [
            {
                "name": "timer",
                "before": "missing",
                "after": STATUS_READY,
            },
            {
                "name": "weather",
                "before": STATUS_READY,
                "after": "missing",
            },
        ],
    )

    clock = FakeClock()
    monitor = RuntimeServiceHealthMonitor(
        interval_sec=5.0,
        monotonic_func=clock,
    )
    monitor.set_baseline(
        initial_report
    )

    def failed_provider():
        raise RuntimeError(
            "collector failed"
        )

    clock.advance(5.0)
    first_failure = monitor.poll_if_due(
        failed_provider
    )
    clock.advance(5.0)
    repeated_failure = monitor.poll_if_due(
        failed_provider
    )
    clock.advance(5.0)
    recovered_poll = monitor.poll_if_due(
        lambda: initial_report
    )

    check(
        "POLL FAILURE IS DEDUPED AND RECOVERY REPORTED",
        {
            "first_error": first_failure.error,
            "first_changed": first_failure.error_changed,
            "repeated_changed": repeated_failure.error_changed,
            "recovered_from": recovered_poll.recovered_from_error,
            "transition": recovered_poll.transition,
        },
        {
            "first_error": "collector failed",
            "first_changed": True,
            "repeated_changed": False,
            "recovered_from": "collector failed",
            "transition": None,
        },
    )

    lines: list[str] = []
    events: list[dict[str, Any]] = []
    payload = publish_runtime_service_health_transition(
        mixed_transition,
        event_func=lambda name, body: events.append(
            {
                "name": name,
                "payload": body,
            }
        ),
        print_func=lines.append,
    )

    check(
        "TRANSITION IS PRINTED AND LOGGED",
        {
            "lines": lines,
            "event_name": events[0]["name"],
            "event_status": events[0]["payload"]["current_status"],
            "payload_status": payload["current_status"],
        },
        {
            "lines": format_runtime_service_health_transition_lines(
                mixed_transition
            ),
            "event_name": "runtime_service_health_changed",
            "event_status": STATUS_DEGRADED,
            "payload_status": STATUS_DEGRADED,
        },
    )

    failure_lines: list[str] = []

    def broken_logger(
        name: str,
        payload: dict[str, Any],
    ) -> None:
        _ = name
        _ = payload
        raise RuntimeError(
            "fake logger failure"
        )

    raised = False

    try:
        publish_runtime_service_health_transition(
            mixed_transition,
            event_func=broken_logger,
            print_func=failure_lines.append,
        )
    except Exception:
        raised = True

    check(
        "LOGGER FAILURE DOES NOT BREAK MONITOR",
        {
            "raised": raised,
            "last_line": failure_lines[-1],
        },
        {
            "raised": False,
            "last_line": (
                "[HEALTH] transition log failed: "
                "fake logger failure"
            ),
        },
    )

    with patch.dict(
        os.environ,
        {},
        clear=True,
    ):
        default_settings = Settings.from_env()

    with patch.dict(
        os.environ,
        {
            "RUNTIME_HEALTH_MONITOR_ENABLE": "0",
            "RUNTIME_HEALTH_MONITOR_INTERVAL_SEC": "12.5",
        },
        clear=True,
    ):
        custom_settings = Settings.from_env()

    env_source = Path(
        ".env.example"
    ).read_text(
        encoding="utf-8"
    )

    check(
        "MONITOR SETTINGS AND ENV EXAMPLE",
        {
            "default_enable": (
                default_settings.runtime_health_monitor_enable
            ),
            "default_interval": (
                default_settings.runtime_health_monitor_interval_sec
            ),
            "custom_enable": (
                custom_settings.runtime_health_monitor_enable
            ),
            "custom_interval": (
                custom_settings.runtime_health_monitor_interval_sec
            ),
            "env_enable": (
                "RUNTIME_HEALTH_MONITOR_ENABLE="
                in env_source
            ),
            "env_interval": (
                "RUNTIME_HEALTH_MONITOR_INTERVAL_SEC="
                in env_source
            ),
        },
        {
            "default_enable": True,
            "default_interval": 5.0,
            "custom_enable": False,
            "custom_interval": 12.5,
            "env_enable": True,
            "env_interval": True,
        },
    )

    main_source = Path(
        "main.py"
    ).read_text(
        encoding="utf-8"
    )
    main_tree = ast.parse(
        main_source
    )
    monitor_source = Path(
        "modules/runtime_service_health_monitor.py"
    ).read_text(
        encoding="utf-8"
    )
    imported_names: set[str] = set()
    monitor_method_calls: set[str] = set()
    queue_get_has_timeout = False
    catches_queue_empty = False

    for node in ast.walk(main_tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            == "modules.runtime_service_health_monitor"
        ):
            imported_names.update(
                alias.name
                for alias in node.names
            )

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        ):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id
                == "runtime_health_monitor"
            ):
                monitor_method_calls.add(
                    node.func.attr
                )

            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "event_q"
                and node.func.attr == "get"
            ):
                queue_get_has_timeout = any(
                    keyword.arg == "timeout"
                    for keyword in node.keywords
                )

        if (
            isinstance(node, ast.ExceptHandler)
            and isinstance(node.type, ast.Attribute)
        ):
            if (
                isinstance(node.type.value, ast.Name)
                and node.type.value.id == "queue"
                and node.type.attr == "Empty"
            ):
                catches_queue_empty = True

    check(
        "MAIN LOOP MONITOR WIRING",
        {
            "monitor_import": (
                "RuntimeServiceHealthMonitor"
                in imported_names
            ),
            "publish_import": (
                "publish_runtime_service_health_transition"
                in imported_names
            ),
            "baseline_call": (
                "set_baseline"
                in monitor_method_calls
            ),
            "poll_call": (
                "poll_if_due"
                in monitor_method_calls
            ),
            "timeout_call": (
                "seconds_until_poll"
                in monitor_method_calls
            ),
            "queue_timeout": queue_get_has_timeout,
            "queue_empty": catches_queue_empty,
            "monitor_has_threading": (
                "threading"
                in monitor_source
            ),
        },
        {
            "monitor_import": True,
            "publish_import": True,
            "baseline_call": True,
            "poll_call": True,
            "timeout_call": True,
            "queue_timeout": True,
            "queue_empty": True,
            "monitor_has_threading": False,
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