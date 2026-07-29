from __future__ import annotations

import json
import math
import time

from dataclasses import dataclass
from typing import Any, Callable, Dict
from urllib.parse import urlencode
from urllib.request import urlopen

from modules.core.operation_telemetry import OperationTelemetry, OperationTelemetrySnapshot


class WeatherServiceError(RuntimeError):
    pass


class WeatherLocationNotFoundError(WeatherServiceError):
    pass


class WeatherResponseError(WeatherServiceError):
    pass


@dataclass(frozen=True)
class WeatherResult:
    place: str
    temperature_c: float
    apparent_temperature_c: float
    wind_speed_ms: float
    weather_code: int
    description: str


class WeatherService:
    GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    _WMO_RU: Dict[int, str] = {
        0: "ясно",
        1: "в основном ясно",
        2: "переменная облачность",
        3: "пасмурно",
        45: "туман",
        48: "изморозевый туман",
        51: "слабая морось",
        53: "морось",
        55: "сильная морось",
        56: "слабая ледяная морось",
        57: "ледяная морось",
        61: "небольшой дождь",
        63: "дождь",
        65: "сильный дождь",
        66: "слабый ледяной дождь",
        67: "ледяной дождь",
        71: "слабый снег",
        73: "снег",
        75: "сильный снег",
        77: "снежные зёрна",
        80: "небольшой ливень",
        81: "ливень",
        82: "сильный ливень",
        85: "слабый снежный заряд",
        86: "сильный снежный заряд",
        95: "гроза",
        96: "гроза с градом",
        99: "сильная гроза с градом",
    }

    def __init__(
        self,
        *,
        request_timeout_sec: float = 8.0,
        health_ttl_sec: float = 1800.0,
        time_func: Callable[[], float] = time.time,
        monotonic_func: Callable[[], float] = time.monotonic,
    ):
        self._request_timeout_sec = max(0.1, float(request_timeout_sec))
        self._health_ttl_sec = max(1.0, float(health_ttl_sec))
        self._monotonic_func = monotonic_func
        self._telemetry = OperationTelemetry(time_func=time_func)

    @property
    def health_ttl_sec(self) -> float:
        return self._health_ttl_sec

    def get_operation_telemetry(self) -> OperationTelemetrySnapshot:
        return self._telemetry.snapshot()

    def _duration_ms(self, started_at: float) -> int:
        elapsed = max(0.0, float(self._monotonic_func()) - float(started_at))
        return int(round(elapsed * 1000.0))

    def _get_json(self, base_url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{base_url}?{urlencode(params)}"

        with urlopen(url, timeout=self._request_timeout_sec) as response:
            raw = response.read().decode("utf-8")

        try:
            payload = json.loads(raw)
        except Exception as e:
            raise WeatherResponseError(f"Invalid weather JSON: {e}") from e

        if not isinstance(payload, dict):
            raise WeatherResponseError("Weather API response is not an object")

        if payload.get("error") is True:
            reason = str(payload.get("reason") or "Weather API returned an error").strip()
            raise WeatherResponseError(reason)

        return payload

    def _require_float(self, payload: Dict[str, Any], key: str) -> float:
        if key not in payload:
            raise WeatherResponseError(f"Weather response field is missing: {key}")

        value = payload.get(key)

        if isinstance(value, bool):
            raise WeatherResponseError(f"Weather response field is not numeric: {key}")

        try:
            number = float(value)
        except (TypeError, ValueError) as e:
            raise WeatherResponseError(f"Weather response field is not numeric: {key}") from e

        if not math.isfinite(number):
            raise WeatherResponseError(f"Weather response field is not finite: {key}")

        return number

    def _coordinates(self, place: Dict[str, Any]) -> tuple[float, float]:
        latitude = self._require_float(place, "latitude")
        longitude = self._require_float(place, "longitude")

        if not -90.0 <= latitude <= 90.0:
            raise WeatherResponseError("Weather latitude is outside the valid range")

        if not -180.0 <= longitude <= 180.0:
            raise WeatherResponseError("Weather longitude is outside the valid range")

        return latitude, longitude

    def _weather_description(self, code: int) -> str:
        return self._WMO_RU.get(int(code), "неизвестная погода")

    def _format_place(self, item: Dict[str, Any]) -> str:
        parts = []
        name = str(item.get("name") or "").strip()
        admin1 = str(item.get("admin1") or "").strip()
        country = str(item.get("country") or "").strip()

        if name:
            parts.append(name)
        if admin1 and admin1.lower() != name.lower():
            parts.append(admin1)
        if country:
            parts.append(country)

        return ", ".join(parts) if parts else "выбранном городе"

    def _city_variants(self, city: str) -> list[str]:
        city = str(city or "").strip()
        if not city:
            return []

        variants: list[str] = []
        seen: set[str] = set()

        def add(value: str) -> None:
            value = str(value or "").strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                variants.append(value)

        add(city)
        city_lower = city.lower()

        if city_lower.endswith("е") and len(city) > 3:
            stem = city[:-1]
            add(stem)
            add(stem + "а")
            add(stem + "я")

        if city_lower.endswith("и") and len(city) > 3:
            stem = city[:-1]
            add(stem)
            add(stem + "а")
            add(stem + "я")

        return variants

    def _find_place(self, city: str) -> Dict[str, Any]:
        last_error: Exception | None = None
        valid_response_received = False

        for variant in self._city_variants(city):
            try:
                geo = self._get_json(
                    self.GEO_URL,
                    {
                        "name": variant,
                        "count": 1,
                        "language": "ru",
                    },
                )
            except Exception as e:
                last_error = e
                continue

            results = geo.get("results")

            if results is None:
                valid_response_received = True
                continue

            if not isinstance(results, list):
                last_error = WeatherResponseError("Geocoding response field 'results' is not a list")
                continue

            valid_response_received = True

            if not results:
                continue

            place = results[0]

            if not isinstance(place, dict):
                last_error = WeatherResponseError("Geocoding result is not an object")
                continue

            try:
                self._coordinates(place)
            except WeatherResponseError as e:
                last_error = e
                continue

            return place

        if valid_response_received:
            raise WeatherLocationNotFoundError(f"City not found: {city}")

        if last_error is not None:
            raise last_error

        raise WeatherLocationNotFoundError(f"City not found: {city}")

    def get_current_weather(self, city: str) -> WeatherResult:
        city = str(city or "").strip()
        if not city:
            raise ValueError("City is empty")

        started_at = float(self._monotonic_func())

        try:
            place = self._find_place(city)
            latitude, longitude = self._coordinates(place)

            forecast = self._get_json(
                self.FORECAST_URL,
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                    "wind_speed_unit": "ms",
                    "timezone": "auto",
                },
            )

            current = forecast.get("current")
            if not isinstance(current, dict):
                raise WeatherResponseError("Weather response field is missing or invalid: current")

            temperature_c = self._require_float(current, "temperature_2m")
            apparent_temperature_c = self._require_float(current, "apparent_temperature")
            wind_speed_ms = self._require_float(current, "wind_speed_10m")
            weather_code_value = self._require_float(current, "weather_code")

            if not weather_code_value.is_integer():
                raise WeatherResponseError("Weather response field is not an integer: weather_code")

            weather_code = int(weather_code_value)
            result = WeatherResult(
                place=self._format_place(place),
                temperature_c=temperature_c,
                apparent_temperature_c=apparent_temperature_c,
                wind_speed_ms=wind_speed_ms,
                weather_code=weather_code,
                description=self._weather_description(weather_code),
            )
        except WeatherLocationNotFoundError:
            raise
        except Exception as e:
            self._telemetry.record_failure(e, duration_ms=self._duration_ms(started_at))
            raise

        self._telemetry.record_success(duration_ms=self._duration_ms(started_at))
        return result