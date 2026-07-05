from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict
from urllib.parse import urlencode
from urllib.request import urlopen


@dataclass
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

    def _get_json(self, base_url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{base_url}?{urlencode(params)}"
        with urlopen(url, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))

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

        def add(v: str) -> None:
            v = str(v or "").strip()
            if v and v.lower() not in seen:
                seen.add(v.lower())
                variants.append(v)

        add(city)

        c = city.lower()

        # Частый случай: "амстердаме" -> "амстердам", "берлине" -> "берлин"
        if c.endswith("е") and len(city) > 3:
            stem = city[:-1]
            add(stem)
            add(stem + "а")
            add(stem + "я")

        # Мягкий fallback для форм на "и"
        if c.endswith("и") and len(city) > 3:
            stem = city[:-1]
            add(stem)
            add(stem + "а")
            add(stem + "я")

        return variants

    def _find_place(self, city: str) -> Dict[str, Any]:
        last_error: Exception | None = None

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

            results = geo.get("results") or []
            if results:
                return results[0]

        if last_error is not None:
            raise last_error

        raise RuntimeError(f"City not found: {city}")

    def get_current_weather(self, city: str) -> WeatherResult:
        city = str(city or "").strip()
        if not city:
            raise ValueError("City is empty")

        place = self._find_place(city)
        latitude = place["latitude"]
        longitude = place["longitude"]

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

        current = forecast.get("current") or {}
        weather_code = int(current.get("weather_code", -1))

        return WeatherResult(
            place=self._format_place(place),
            temperature_c=float(current.get("temperature_2m", 0.0)),
            apparent_temperature_c=float(current.get("apparent_temperature", 0.0)),
            wind_speed_ms=float(current.get("wind_speed_10m", 0.0)),
            weather_code=weather_code,
            description=self._weather_description(weather_code),
        )