from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


STATUS_READY = "ready"
STATUS_DEGRADED = "degraded"
STATUS_DISABLED = "disabled"
STATUS_UNKNOWN = "unknown"

_ALLOWED_STATUSES = {
    STATUS_READY,
    STATUS_DEGRADED,
    STATUS_DISABLED,
    STATUS_UNKNOWN,
}


@dataclass(frozen=True)
class ServiceHealth:
    name: str
    status: str
    details: dict[str, Any]
    error: str = ""


@dataclass(frozen=True)
class RuntimeServiceHealthReport:
    services: tuple[ServiceHealth, ...]
    ready_count: int
    degraded_count: int
    disabled_count: int
    unknown_count: int = 0

    @property
    def total_count(self) -> int:
        return len(self.services)

    @property
    def status(self) -> str:
        if self.degraded_count or self.disabled_count:
            return STATUS_DEGRADED

        if self.unknown_count or self.total_count == 0:
            return STATUS_UNKNOWN

        return STATUS_READY


class RuntimeServiceHealth:
    def __init__(self) -> None:
        self._services: list[ServiceHealth] = []

    def add(
        self,
        name: str,
        status: str,
        *,
        details: Mapping[str, Any] | None = None,
        error: str = "",
    ) -> ServiceHealth:
        normalized_name = str(name or "").strip().lower()
        normalized_status = str(status or "").strip().lower()
        normalized_error = str(error or "").strip()

        if not normalized_name:
            raise ValueError("Service health name is empty")

        if normalized_status not in _ALLOWED_STATUSES:
            raise ValueError(f"Unknown service health status: {status}")

        if any(item.name == normalized_name for item in self._services):
            raise ValueError(f"Service health already registered: {normalized_name}")

        item = ServiceHealth(
            name=normalized_name,
            status=normalized_status,
            details=dict(details or {}),
            error=normalized_error,
        )
        self._services.append(item)
        return item

    def ready(self, name: str, *, details: Mapping[str, Any] | None = None) -> ServiceHealth:
        return self.add(name, STATUS_READY, details=details)

    def degraded(
        self,
        name: str,
        *,
        details: Mapping[str, Any] | None = None,
        error: str = "",
    ) -> ServiceHealth:
        return self.add(name, STATUS_DEGRADED, details=details, error=error)

    def disabled(
        self,
        name: str,
        *,
        details: Mapping[str, Any] | None = None,
        error: str = "",
    ) -> ServiceHealth:
        return self.add(name, STATUS_DISABLED, details=details, error=error)

    def unknown(
        self,
        name: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> ServiceHealth:
        return self.add(name, STATUS_UNKNOWN, details=details)

    def build(self) -> RuntimeServiceHealthReport:
        services = tuple(self._services)

        return RuntimeServiceHealthReport(
            services=services,
            ready_count=sum(item.status == STATUS_READY for item in services),
            degraded_count=sum(item.status == STATUS_DEGRADED for item in services),
            disabled_count=sum(item.status == STATUS_DISABLED for item in services),
            unknown_count=sum(item.status == STATUS_UNKNOWN for item in services),
        )


def runtime_service_health_payload(report: RuntimeServiceHealthReport) -> dict[str, Any]:
    return {
        "status": report.status,
        "services": [
            {
                "name": item.name,
                "status": item.status,
                "details": dict(item.details),
                "error": item.error,
            }
            for item in report.services
        ],
        "summary": {
            "total_count": report.total_count,
            "ready_count": report.ready_count,
            "degraded_count": report.degraded_count,
            "disabled_count": report.disabled_count,
            "unknown_count": report.unknown_count,
        },
    }


def format_runtime_service_health_lines(report: RuntimeServiceHealthReport) -> list[str]:
    lines = ["[HEALTH] Runtime services"]

    for item in report.services:
        parts = []

        if item.details:
            details_text = ", ".join(f"{key}={value}" for key, value in item.details.items())
            parts.append(details_text)

        if item.error:
            parts.append(f"error={item.error}")

        suffix = f": {'; '.join(parts)}" if parts else ""
        lines.append(f"[HEALTH] {item.status.upper()} {item.name}{suffix}")

    lines.append(
        "[HEALTH] summary: "
        f"status={report.status} "
        f"ready={report.ready_count} "
        f"degraded={report.degraded_count} "
        f"disabled={report.disabled_count} "
        f"unknown={report.unknown_count} "
        f"total={report.total_count}"
    )

    return lines