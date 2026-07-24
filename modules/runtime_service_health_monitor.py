from __future__ import annotations

import math
import time

from dataclasses import dataclass
from typing import Any, Callable

from modules.runtime_service_health import (
    RuntimeServiceHealthReport,
    runtime_service_health_payload,
)


ReportFunc = Callable[[], RuntimeServiceHealthReport]
EventFunc = Callable[[str, dict[str, Any]], None]
PrintFunc = Callable[[str], None]


@dataclass(frozen=True)
class ServiceHealthChange:
    name: str
    previous_status: str
    current_status: str
    previous_error: str
    current_error: str


@dataclass(frozen=True)
class RuntimeServiceHealthTransition:
    previous_status: str
    current_status: str
    changed_services: tuple[ServiceHealthChange, ...]
    report: RuntimeServiceHealthReport


@dataclass(frozen=True)
class RuntimeServiceHealthMonitorPoll:
    attempted: bool
    transition: RuntimeServiceHealthTransition | None = None
    error: str = ""
    error_changed: bool = False
    recovered_from_error: str = ""


@dataclass(frozen=True)
class _ServiceState:
    status: str
    error: str


class RuntimeServiceHealthMonitor:
    def __init__(
        self,
        *,
        enabled: bool = True,
        interval_sec: float = 5.0,
        monotonic_func: Callable[[], float] = time.monotonic,
    ):
        try:
            interval_value = float(interval_sec)
        except (TypeError, ValueError) as e:
            raise ValueError(
                "Runtime health monitor interval must be at least 1 second"
            ) from e

        if not math.isfinite(interval_value) or interval_value < 1.0:
            raise ValueError(
                "Runtime health monitor interval must be at least 1 second"
            )

        self._enabled = bool(enabled)
        self._interval_sec = interval_value
        self._monotonic_func = monotonic_func
        self._next_poll_at: float | None = None
        self._last_report_status = ""
        self._service_states: dict[str, _ServiceState] | None = None
        self._last_poll_error = ""

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def interval_sec(self) -> float:
        return self._interval_sec

    def _now(self) -> float:
        value = float(self._monotonic_func())

        if not math.isfinite(value):
            raise RuntimeError("Runtime health monitor clock is invalid")

        return value

    def _snapshot_services(
        self,
        report: RuntimeServiceHealthReport,
    ) -> dict[str, _ServiceState]:
        result: dict[str, _ServiceState] = {}

        for item in report.services:
            name = str(item.name or "").strip().lower()

            if not name:
                raise RuntimeError("Runtime health report contains an unnamed service")

            if name in result:
                raise RuntimeError(
                    f"Runtime health report contains duplicate service: {name}"
                )

            result[name] = _ServiceState(
                status=str(item.status or "").strip().lower(),
                error=str(item.error or "").strip(),
            )

        return result

    def _schedule_next_poll(self) -> None:
        self._next_poll_at = (
            self._now() + self._interval_sec
            if self._enabled
            else None
        )

    def set_baseline(self, report: RuntimeServiceHealthReport) -> None:
        self._last_report_status = str(report.status or "").strip().lower()
        self._service_states = self._snapshot_services(report)
        self._last_poll_error = ""
        self._schedule_next_poll()

    def seconds_until_poll(self) -> float | None:
        if not self._enabled:
            return None

        if self._next_poll_at is None:
            return 0.0

        return max(0.0, self._next_poll_at - self._now())

    def _observe(
        self,
        report: RuntimeServiceHealthReport,
    ) -> RuntimeServiceHealthTransition | None:
        current_status = str(report.status or "").strip().lower()
        current_states = self._snapshot_services(report)

        if self._service_states is None:
            self._last_report_status = current_status
            self._service_states = current_states
            return None

        previous_status = self._last_report_status
        previous_states = self._service_states
        changed_services: list[ServiceHealthChange] = []
        ordered_names = [
            str(item.name or "").strip().lower()
            for item in report.services
        ]
        ordered_names.extend(
            sorted(set(previous_states) - set(current_states))
        )

        for name in ordered_names:
            before = previous_states.get(name)
            after = current_states.get(name)
            previous_service_status = (
                before.status
                if before is not None
                else "missing"
            )
            current_service_status = (
                after.status
                if after is not None
                else "missing"
            )
            previous_error = (
                before.error
                if before is not None
                else ""
            )
            current_error = (
                after.error
                if after is not None
                else ""
            )

            if (
                previous_service_status == current_service_status
                and previous_error == current_error
            ):
                continue

            changed_services.append(
                ServiceHealthChange(
                    name=name,
                    previous_status=previous_service_status,
                    current_status=current_service_status,
                    previous_error=previous_error,
                    current_error=current_error,
                )
            )

        self._last_report_status = current_status
        self._service_states = current_states

        if not changed_services:
            return None

        return RuntimeServiceHealthTransition(
            previous_status=previous_status,
            current_status=current_status,
            changed_services=tuple(changed_services),
            report=report,
        )

    def poll_if_due(
        self,
        report_func: ReportFunc,
    ) -> RuntimeServiceHealthMonitorPoll:
        if not self._enabled:
            return RuntimeServiceHealthMonitorPoll(
                attempted=False,
            )

        now = self._now()

        if (
            self._next_poll_at is not None
            and now < self._next_poll_at
        ):
            return RuntimeServiceHealthMonitorPoll(
                attempted=False,
            )

        try:
            report = report_func()
            transition = self._observe(report)
        except Exception as e:
            error = str(e).strip() or type(e).__name__
            error_changed = error != self._last_poll_error
            self._last_poll_error = error
            self._schedule_next_poll()

            return RuntimeServiceHealthMonitorPoll(
                attempted=True,
                error=error,
                error_changed=error_changed,
            )

        recovered_from_error = self._last_poll_error
        self._last_poll_error = ""
        self._schedule_next_poll()

        return RuntimeServiceHealthMonitorPoll(
            attempted=True,
            transition=transition,
            recovered_from_error=recovered_from_error,
        )


def runtime_service_health_transition_payload(
    transition: RuntimeServiceHealthTransition,
) -> dict[str, Any]:
    return {
        "previous_status": transition.previous_status,
        "current_status": transition.current_status,
        "changed_services": [
            {
                "name": item.name,
                "previous_status": item.previous_status,
                "current_status": item.current_status,
                "previous_error": item.previous_error,
                "current_error": item.current_error,
            }
            for item in transition.changed_services
        ],
        "report": runtime_service_health_payload(
            transition.report
        ),
    }


def format_runtime_service_health_transition_lines(
    transition: RuntimeServiceHealthTransition,
) -> list[str]:
    if transition.previous_status == transition.current_status:
        lines = [
            f"[HEALTH] services changed: status={transition.current_status}"
        ]
    else:
        lines = [
            "[HEALTH] transition: "
            f"{transition.previous_status} -> {transition.current_status}"
        ]

    for item in transition.changed_services:
        suffix = (
            f"; error={item.current_error}"
            if item.current_error
            else ""
        )
        lines.append(
            "[HEALTH] "
            f"{item.name}: "
            f"{item.previous_status} -> {item.current_status}"
            f"{suffix}"
        )

    return lines


def publish_runtime_service_health_transition(
    transition: RuntimeServiceHealthTransition,
    *,
    event_func: EventFunc | None = None,
    print_func: PrintFunc | None = print,
) -> dict[str, Any]:
    payload = runtime_service_health_transition_payload(
        transition
    )

    if print_func is not None:
        for line in format_runtime_service_health_transition_lines(
            transition
        ):
            print_func(line)

    if event_func is not None:
        try:
            event_func(
                "runtime_service_health_changed",
                payload,
            )
        except Exception as e:
            if print_func is not None:
                print_func(
                    f"[HEALTH] transition log failed: {e}"
                )

    return payload