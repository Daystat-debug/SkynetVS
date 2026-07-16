from __future__ import annotations

from modules.runtime_service_health import (
    RuntimeServiceHealthReport,
    STATUS_DEGRADED,
    STATUS_DISABLED,
    STATUS_READY,
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

    problems = [item for item in report.services if item.status != STATUS_READY]

    if not problems:
        return "Все основные сервисы работают нормально."

    parts = ["Обнаружены проблемы."]

    for item in problems:
        title = _service_title(item.name)

        if item.status == STATUS_DISABLED:
            parts.append(f"Сервис «{title}» недоступен.")
        elif item.status == STATUS_DEGRADED:
            parts.append(f"Сервис «{title}» работает с ограничениями.")
        else:
            parts.append(f"Сервис «{title}» находится в неизвестном состоянии.")

    return " ".join(parts)