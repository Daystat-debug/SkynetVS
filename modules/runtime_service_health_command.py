from __future__ import annotations

from modules.runtime_service_health import (
    RuntimeServiceHealthReport,
    STATUS_DEGRADED,
    STATUS_DISABLED,
    STATUS_UNKNOWN,
)


SERVICE_TITLES = {
    "stt": "распознавание речи",
    "tts": "синтез речи",
    "audio_control": "управление громкостью",
    "audio_output": "вывод звука",
    "weather": "погода",
    "timer": "таймер",
    "reminders": "напоминания",
}


def _service_title(name: str) -> str:
    normalized = str(name or "").strip().lower()
    return SERVICE_TITLES.get(normalized, normalized.replace("_", " ") or "неизвестный сервис")


def build_runtime_service_health_reply(report: RuntimeServiceHealthReport) -> str:
    if report.total_count <= 0:
        return "Нет данных о состоянии системы."

    problems = [
        item
        for item in report.services
        if item.status in {STATUS_DEGRADED, STATUS_DISABLED}
    ]
    unknown_services = [
        item
        for item in report.services
        if item.status == STATUS_UNKNOWN
    ]

    if not problems and not unknown_services:
        return "Все проверенные сервисы работают нормально."

    parts: list[str] = []

    if problems:
        parts.append("Обнаружены проблемы.")
    elif report.ready_count:
        parts.append("Проверенные сервисы работают нормально.")
    else:
        parts.append("Работоспособность сервисов пока не подтверждена.")

    for item in problems:
        title = _service_title(item.name)

        if item.status == STATUS_DISABLED:
            parts.append(f"Сервис «{title}» недоступен.")
        elif item.status == STATUS_DEGRADED:
            parts.append(f"Сервис «{title}» работает с ограничениями.")

    for item in unknown_services:
        title = _service_title(item.name)

        if bool(item.details.get("stale")):
            parts.append(f"Данные о сервисе «{title}» устарели.")
        else:
            parts.append(f"Сервис «{title}» ещё не проверялся.")

    return " ".join(parts)