"""Weather tool backed by the public Open-Meteo APIs (no API key required)."""

from __future__ import annotations

import httpx

from .base import Arguments, FunctionTool

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_FIELDS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "wind_speed_10m_max",
)


def _value(items: list, index: int) -> float:
    """Return a numeric daily value, or zero when the API omits it."""
    if index >= len(items):
        return 0.0
    try:
        return float(items[index])
    except (TypeError, ValueError):
        return 0.0


def create_weather_tool(client: httpx.AsyncClient | None = None) -> FunctionTool:
    """Build a confirmed tool that resolves a city and returns its forecast."""

    async def runner(arguments: Arguments) -> str:
        location = str(arguments.get("location", "")).strip()
        if not location:
            return "Invalid location: empty value"

        owns_client = client is None
        http = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
        try:
            places = await http.get(
                GEOCODING_URL,
                params={
                    "name": location,
                    "count": 1,
                    "language": "ru",
                    "format": "json",
                },
            )
            places.raise_for_status()
            results = places.json().get("results") or []
            if not results:
                return f"Location not found: {location}"
            place = results[0]
            latitude = place["latitude"]
            longitude = place["longitude"]

            response = await http.get(
                FORECAST_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "daily": ",".join(DAILY_FIELDS),
                    "timezone": "auto",
                    "forecast_days": 2,
                },
            )
            response.raise_for_status()
            daily = response.json().get("daily") or {}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            return f"Weather lookup failed: {exc}"
        finally:
            if owns_client:
                await http.aclose()

        title = ", ".join(
            part
            for part in (place.get("name"), place.get("country"))
            if isinstance(part, str)
        )
        lines = [f"Weather forecast for {title or location}:"]
        times = daily.get("time") or []
        labels = ("today", "tomorrow")
        for index, date in enumerate(times):
            label = f"{labels[index]} ({date})" if index < len(labels) else date
            lines.append(
                f"{label}: max {_value(daily.get(DAILY_FIELDS[0]) or [], index):.0f}°C, "
                f"min {_value(daily.get(DAILY_FIELDS[1]) or [], index):.0f}°C, "
                f"precipitation {_value(daily.get(DAILY_FIELDS[2]) or [], index):.0f}%, "
                f"wind {_value(daily.get(DAILY_FIELDS[3]) or [], index):.0f} km/h"
            )
        if len(lines) == 1:
            lines.append("No daily forecast returned.")
        return "\n".join(lines)

    return FunctionTool(
        name="get_weather",
        description=(
            "Get today's and tomorrow's weather forecast for a city, including "
            "temperature, precipitation probability, and wind. Use for weather questions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name, optionally with a country",
                },
            },
            "required": ["location"],
        },
        runner=runner,
        requires_confirmation=True,
    )
