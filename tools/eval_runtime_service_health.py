from __future__ import annotations

import json

from typing import Any

from modules.runtime_service_health import (
    RuntimeServiceHealth,
    STATUS_DEGRADED,
    STATUS_DISABLED,
    STATUS_READY,
    format_runtime_service_health_lines,
    runtime_service_health_payload,
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
    report = health.build()

    check(
        "EMPTY REPORT",
        {
            "status": report.status,
            "total": report.total_count,
            "ready": report.ready_count,
            "degraded": report.degraded_count,
            "disabled": report.disabled_count,
        },
        {
            "status": STATUS_READY,
            "total": 0,
            "ready": 0,
            "degraded": 0,
            "disabled": 0,
        },
    )

    health = RuntimeServiceHealth()
    health.ready("stt", details={"engine": "VoskSTT", "samplerate": 16000})
    health.ready("tts", details={"engine": "EdgeTTS", "voice": "ru-RU-SvetlanaNeural"})
    health.degraded("audio_output", details={"current": ""}, error="Current device unavailable")
    health.disabled("reminders", error="Broken repository")
    report = health.build()

    check(
        "STATUS COUNTS",
        {
            "status": report.status,
            "names": [item.name for item in report.services],
            "ready": report.ready_count,
            "degraded": report.degraded_count,
            "disabled": report.disabled_count,
            "total": report.total_count,
        },
        {
            "status": STATUS_DEGRADED,
            "names": ["stt", "tts", "audio_output", "reminders"],
            "ready": 2,
            "degraded": 1,
            "disabled": 1,
            "total": 4,
        },
    )

    payload = runtime_service_health_payload(report)

    check(
        "JSON PAYLOAD",
        payload,
        {
            "status": STATUS_DEGRADED,
            "services": [
                {
                    "name": "stt",
                    "status": STATUS_READY,
                    "details": {
                        "engine": "VoskSTT",
                        "samplerate": 16000,
                    },
                    "error": "",
                },
                {
                    "name": "tts",
                    "status": STATUS_READY,
                    "details": {
                        "engine": "EdgeTTS",
                        "voice": "ru-RU-SvetlanaNeural",
                    },
                    "error": "",
                },
                {
                    "name": "audio_output",
                    "status": STATUS_DEGRADED,
                    "details": {
                        "current": "",
                    },
                    "error": "Current device unavailable",
                },
                {
                    "name": "reminders",
                    "status": STATUS_DISABLED,
                    "details": {},
                    "error": "Broken repository",
                },
            ],
            "summary": {
                "total_count": 4,
                "ready_count": 2,
                "degraded_count": 1,
                "disabled_count": 1,
            },
        },
    )

    lines = format_runtime_service_health_lines(report)

    check(
        "CONSOLE LINES",
        lines,
        [
            "[HEALTH] Runtime services",
            "[HEALTH] READY stt: engine=VoskSTT, samplerate=16000",
            "[HEALTH] READY tts: engine=EdgeTTS, voice=ru-RU-SvetlanaNeural",
            "[HEALTH] DEGRADED audio_output: current=; error=Current device unavailable",
            "[HEALTH] DISABLED reminders: error=Broken repository",
            "[HEALTH] summary: status=degraded ready=2 degraded=1 disabled=1 total=4",
        ],
    )

    health = RuntimeServiceHealth()
    health.ready("stt")
    duplicate_rejected = False

    try:
        health.disabled("STT", error="duplicate")
    except ValueError:
        duplicate_rejected = True

    check(
        "DUPLICATE SERVICE REJECTED",
        duplicate_rejected,
        True,
    )

    invalid_count = 0

    for name, status in (
        ("", STATUS_READY),
        ("stt", ""),
        ("stt", "unknown"),
    ):
        try:
            RuntimeServiceHealth().add(name, status)
        except ValueError:
            invalid_count += 1

    check(
        "INVALID VALUES REJECTED",
        invalid_count,
        3,
    )

    source_details = {
        "voice": "ru-RU-SvetlanaNeural",
    }

    health = RuntimeServiceHealth()
    health.ready("tts", details=source_details)
    report_before_change = health.build()

    source_details["voice"] = "changed"

    check(
        "DETAILS ARE COPIED",
        report_before_change.services[0].details,
        {
            "voice": "ru-RU-SvetlanaNeural",
        },
    )

    health = RuntimeServiceHealth()
    health.ready("stt")
    first_report = health.build()
    health.ready("tts")
    second_report = health.build()

    check(
        "REPORT IS SNAPSHOT",
        {
            "first": [item.name for item in first_report.services],
            "second": [item.name for item in second_report.services],
        },
        {
            "first": ["stt"],
            "second": ["stt", "tts"],
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