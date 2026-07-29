from __future__ import annotations

import json

from typing import Any
from unittest.mock import patch

from modules.core.operation_telemetry import OUTCOME_FAILURE, OUTCOME_SUCCESS
from modules.weather_service import (
    WeatherLocationNotFoundError,
    WeatherResponseError,
    WeatherService,
)


VALID_PLACE = {
    "name": "Минск",
    "admin1": "Минская область",
    "country": "Беларусь",
    "latitude": 53.9,
    "longitude": 27.5667,
}

VALID_CURRENT = {
    "temperature_2m": 18.4,
    "apparent_temperature": 17.2,
    "weather_code": 3,
    "wind_speed_10m": 4.6,
}


class FakeClock:
    def __init__(self):
        self.epoch = 1000.0
        self.monotonic = 50.0

    def time(self) -> float:
        return self.epoch

    def monotonic_time(self) -> float:
        return self.monotonic

    def advance(self, seconds: float) -> None:
        self.epoch += float(seconds)
        self.monotonic += float(seconds)


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = exc_type
        _ = exc
        _ = tb

    def read(self) -> bytes:
        return self.payload


def _new_service(clock: FakeClock | None = None) -> WeatherService:
    clock = clock or FakeClock()

    return WeatherService(
        time_func=clock.time,
        monotonic_func=clock.monotonic_time,
    )


def _set_payloads(service: WeatherService, payloads: list[dict[str, Any]]) -> None:
    iterator = iter(payloads)

    def fake_get_json(base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        _ = base_url
        _ = params
        return next(iterator)

    service._get_json = fake_get_json


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

    service = _new_service()
    snapshot = service.get_operation_telemetry()

    check(
        "INITIAL TELEMETRY",
        {
            "has_attempt": snapshot.has_attempt,
            "last_outcome": snapshot.last_outcome,
            "last_error": snapshot.last_error,
        },
        {
            "has_attempt": False,
            "last_outcome": "",
            "last_error": "",
        },
    )

    clock = FakeClock()
    service = _new_service(clock)
    payloads = [
        {"results": [VALID_PLACE]},
        {"current": VALID_CURRENT},
    ]
    iterator = iter(payloads)

    def successful_get_json(base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        _ = base_url
        _ = params
        clock.advance(0.1)
        return next(iterator)

    service._get_json = successful_get_json
    result = service.get_current_weather("Минск")
    snapshot = service.get_operation_telemetry()

    check(
        "SUCCESSFUL WEATHER QUERY",
        {
            "place": result.place,
            "temperature_c": result.temperature_c,
            "apparent_temperature_c": result.apparent_temperature_c,
            "wind_speed_ms": result.wind_speed_ms,
            "weather_code": result.weather_code,
            "description": result.description,
            "last_outcome": snapshot.last_outcome,
            "last_attempt_at": snapshot.last_attempt_at,
            "last_duration_ms": snapshot.last_duration_ms,
            "consecutive_failures": snapshot.consecutive_failures,
        },
        {
            "place": "Минск, Минская область, Беларусь",
            "temperature_c": 18.4,
            "apparent_temperature_c": 17.2,
            "wind_speed_ms": 4.6,
            "weather_code": 3,
            "description": "пасмурно",
            "last_outcome": OUTCOME_SUCCESS,
            "last_attempt_at": 1000.2,
            "last_duration_ms": 200,
            "consecutive_failures": 0,
        },
    )

    service = _new_service()
    _set_payloads(
        service,
        [
            {"results": [VALID_PLACE]},
            {
                "current": {
                    "temperature_2m": 18.4,
                    "apparent_temperature": 17.2,
                    "weather_code": 3,
                }
            },
        ],
    )
    raised = False

    try:
        service.get_current_weather("Минск")
    except WeatherResponseError:
        raised = True

    snapshot = service.get_operation_telemetry()

    check(
        "MISSING REQUIRED FIELD FAILS",
        {
            "raised": raised,
            "last_outcome": snapshot.last_outcome,
            "last_error": snapshot.last_error,
            "consecutive_failures": snapshot.consecutive_failures,
        },
        {
            "raised": True,
            "last_outcome": OUTCOME_FAILURE,
            "last_error": "Weather response field is missing: wind_speed_10m",
            "consecutive_failures": 1,
        },
    )

    service = _new_service()
    _set_payloads(
        service,
        [
            {"results": [VALID_PLACE]},
            {"current": []},
        ],
    )
    raised = False

    try:
        service.get_current_weather("Минск")
    except WeatherResponseError:
        raised = True

    check(
        "INVALID CURRENT OBJECT FAILS",
        raised,
        True,
    )

    service = _new_service()
    service._get_json = lambda base_url, params: {}
    raised = False

    try:
        service.get_current_weather("Минск")
    except WeatherLocationNotFoundError:
        raised = True

    snapshot = service.get_operation_telemetry()

    check(
        "CITY NOT FOUND DOES NOT DEGRADE SERVICE",
        {
            "raised": raised,
            "has_attempt": snapshot.has_attempt,
            "last_outcome": snapshot.last_outcome,
        },
        {
            "raised": True,
            "has_attempt": False,
            "last_outcome": "",
        },
    )

    service = _new_service()
    raised = False

    try:
        service.get_current_weather("")
    except ValueError:
        raised = True

    snapshot = service.get_operation_telemetry()

    check(
        "EMPTY CITY DOES NOT CHANGE TELEMETRY",
        {
            "raised": raised,
            "has_attempt": snapshot.has_attempt,
        },
        {
            "raised": True,
            "has_attempt": False,
        },
    )

    clock = FakeClock()
    service = _new_service(clock)

    def failing_get_json(base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        _ = base_url
        _ = params
        clock.advance(0.25)
        raise TimeoutError("weather timeout")

    service._get_json = failing_get_json
    raised = False

    try:
        service.get_current_weather("Минск")
    except TimeoutError:
        raised = True

    snapshot = service.get_operation_telemetry()

    check(
        "TRANSPORT FAILURE IS RECORDED",
        {
            "raised": raised,
            "last_outcome": snapshot.last_outcome,
            "last_error": snapshot.last_error,
            "last_duration_ms": snapshot.last_duration_ms,
            "consecutive_failures": snapshot.consecutive_failures,
        },
        {
            "raised": True,
            "last_outcome": OUTCOME_FAILURE,
            "last_error": "weather timeout",
            "last_duration_ms": 250,
            "consecutive_failures": 1,
        },
    )

    payloads = [
        {"results": [VALID_PLACE]},
        {"current": VALID_CURRENT},
    ]
    iterator = iter(payloads)
    service._get_json = lambda base_url, params: next(iterator)
    service.get_current_weather("Минск")
    snapshot = service.get_operation_telemetry()

    check(
        "SUCCESS AFTER FAILURE RESETS CURRENT ERROR",
        {
            "last_outcome": snapshot.last_outcome,
            "last_error": snapshot.last_error,
            "consecutive_failures": snapshot.consecutive_failures,
            "has_last_failure": snapshot.last_failure_at is not None,
        },
        {
            "last_outcome": OUTCOME_SUCCESS,
            "last_error": "",
            "consecutive_failures": 0,
            "has_last_failure": True,
        },
    )

    service = _new_service()

    with patch(
        "modules.weather_service.urlopen",
        return_value=FakeResponse(b"[]"),
    ):
        raised = False

        try:
            service._get_json("https://example.test", {})
        except WeatherResponseError:
            raised = True

    check(
        "NON OBJECT JSON REJECTED",
        raised,
        True,
    )

    service = _new_service()

    with patch(
        "modules.weather_service.urlopen",
        return_value=FakeResponse(b"{broken"),
    ):
        raised = False

        try:
            service._get_json("https://example.test", {})
        except WeatherResponseError:
            raised = True

    check(
        "INVALID JSON REJECTED",
        raised,
        True,
    )

    service = _new_service()

    with patch(
        "modules.weather_service.urlopen",
        return_value=FakeResponse(b'{"error": true, "reason": "quota exceeded"}'),
    ):
        error_text = ""

        try:
            service._get_json("https://example.test", {})
        except WeatherResponseError as e:
            error_text = str(e)

    check(
        "API ERROR PAYLOAD REJECTED",
        error_text,
        "quota exceeded",
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