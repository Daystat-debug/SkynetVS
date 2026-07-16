from __future__ import annotations

import json

from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.actions import Actions
from modules.nlu import predict, predict_candidates
from modules.reply_builder import DEFAULT_FORCE_BASE_REPLY_INTENTS
from modules.runtime_service_health import RuntimeServiceHealth
from modules.runtime_service_health_command import build_runtime_service_health_reply


class DummyService:
    pass


def _new_actions(provider) -> Actions:
    return Actions(
        audio=None,
        screenshot_service=DummyService(),
        weather_service=DummyService(),
        typing_service=DummyService(),
        window_context_service=DummyService(),
        runtime_health_provider=provider,
    )


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

    health = RuntimeServiceHealth()
    health.ready("stt")
    health.ready("tts")
    health.ready("audio_control")
    health.ready("audio_output")
    health.ready("weather")
    health.ready("timer")
    health.ready("reminders")
    ready_report = health.build()

    check(
        "ALL SERVICES READY REPLY",
        build_runtime_service_health_reply(ready_report),
        "Все проверенные сервисы работают нормально.",
    )

    health = RuntimeServiceHealth()
    health.ready("stt")
    health.degraded("audio_output", error="probe failed")
    degraded_report = health.build()

    check(
        "DEGRADED SERVICE REPLY",
        build_runtime_service_health_reply(degraded_report),
        "Обнаружены проблемы. Сервис «вывод звука» работает с ограничениями.",
    )

    health = RuntimeServiceHealth()
    health.ready("stt")
    health.disabled("reminders", error="repository failed")
    disabled_report = health.build()

    check(
        "DISABLED SERVICE REPLY",
        build_runtime_service_health_reply(disabled_report),
        "Обнаружены проблемы. Сервис «напоминания» недоступен.",
    )

    health = RuntimeServiceHealth()
    health.ready("stt")
    health.degraded("timer")
    health.disabled("weather")
    mixed_report = health.build()

    check(
        "ONLY PROBLEM SERVICES ARE SPOKEN",
        build_runtime_service_health_reply(mixed_report),
        "Обнаружены проблемы. Сервис «таймер» работает с ограничениями. Сервис «погода» недоступен.",
    )

    empty_report = RuntimeServiceHealth().build()

    check(
        "EMPTY REPORT REPLY",
        build_runtime_service_health_reply(empty_report),
        "Нет данных о состоянии системы.",
    )

    health = RuntimeServiceHealth()
    health.ready("stt")
    health.unknown("weather", details={"reason": "not_checked"})
    unknown_report = health.build()

    check(
        "UNKNOWN SERVICE REPLY",
        build_runtime_service_health_reply(unknown_report),
        "Проверенные сервисы работают нормально. Сервис «погода» ещё не проверялся.",
    )

    health = RuntimeServiceHealth()
    health.unknown("tts", details={"stale": True})
    stale_report = health.build()

    check(
        "STALE SERVICE REPLY",
        build_runtime_service_health_reply(stale_report),
        "Работоспособность сервисов пока не подтверждена. Данные о сервисе «синтез речи» устарели.",
    )

    model_phrases = (
        "состояние системы",
        "проверь сервисы",
        "покажи текущий статус системы",
        "есть ли сейчас проблемы с сервисами",
    )
    model_results = []

    for text in model_phrases:
        candidates = predict_candidates(text, limit=3, include_rules=False)
        top = candidates[0] if candidates else {}
        meta = predict(text)

        model_results.append(
            {
                "text": text,
                "final_intent": meta.get("intent"),
                "final_rule": meta.get("_rule"),
                "model_intent": top.get("intent"),
                "model_source": top.get("source"),
                "model_accepted": top.get("accepted_by_threshold"),
            }
        )

    check(
        "SYSTEM STATUS USES MODEL",
        model_results,
        [
            {
                "text": text,
                "final_intent": "SYSTEM_STATUS",
                "final_rule": None,
                "model_intent": "SYSTEM_STATUS",
                "model_source": "model",
                "model_accepted": True,
            }
            for text in model_phrases
        ],
    )

    provider_calls = 0

    def provider():
        nonlocal provider_calls
        provider_calls += 1
        return ready_report

    actions = _new_actions(provider)
    first_reply = actions.handle({"intent": "SYSTEM_STATUS", "confidence": 1.0, "slots": {}})
    second_reply = actions.handle({"intent": "SYSTEM_STATUS", "confidence": 1.0, "slots": {}})

    check(
        "ACTIONS REFRESHES REPORT",
        {
            "calls": provider_calls,
            "first_reply": first_reply,
            "second_reply": second_reply,
        },
        {
            "calls": 2,
            "first_reply": "Все проверенные сервисы работают нормально.",
            "second_reply": "Все проверенные сервисы работают нормально.",
        },
    )

    def broken_provider():
        raise RuntimeError("fake health failure")

    actions = _new_actions(broken_provider)

    with patch("modules.actions.log_exception"):
        failure_reply = actions.handle({"intent": "SYSTEM_STATUS", "confidence": 1.0, "slots": {}})

    check(
        "PROVIDER FAILURE REPLY",
        failure_reply,
        "Не получилось проверить состояние системы.",
    )

    main_source = Path("main.py").read_text(encoding="utf-8")
    actions_source = Path("modules/actions.py").read_text(encoding="utf-8")

    check(
        "MAIN AND ACTIONS WIRING",
        {
            "main_provider": "def collect_and_publish_runtime_health" in main_source,
            "main_boot_call": "collect_and_publish_runtime_health(print_report=True)" in main_source,
            "main_actions_provider": "runtime_health_provider=lambda: collect_and_publish_runtime_health(print_report=False)" in main_source,
            "actions_handler": '"SYSTEM_STATUS": self._reply_system_status' in actions_source,
            "forced_reply": "SYSTEM_STATUS" in DEFAULT_FORCE_BASE_REPLY_INTENTS,
        },
        {
            "main_provider": True,
            "main_boot_call": True,
            "main_actions_provider": True,
            "actions_handler": True,
            "forced_reply": True,
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