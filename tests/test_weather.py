import json

import httpx

from daneel.tools import ToolRegistry
from daneel.tools.weather import create_weather_tool


def mock_weather_client(
    geocoding: dict | None = None, forecast: dict | None = None
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if "geocoding" in str(request.url):
            body = geocoding if geocoding is not None else {"results": []}
        else:
            body = forecast if forecast is not None else {}
        return httpx.Response(200, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_weather_tool_is_exposed_in_ollama_schema() -> None:
    schema = ToolRegistry([create_weather_tool()]).as_schema()

    assert schema[0]["function"]["name"] == "get_weather"
    assert schema[0]["function"]["parameters"]["required"] == ["location"]


async def test_weather_tool_returns_daily_forecast() -> None:
    geocoding = {
        "results": [
            {
                "name": "Ostrogozhsk",
                "country": "Russia",
                "latitude": 50.87,
                "longitude": 39.42,
            }
        ]
    }
    forecast = {
        "daily": {
            "time": ["2026-11-25", "2026-11-26"],
            "temperature_2m_max": [0.2, -0.8],
            "temperature_2m_min": [-1.2, -3.1],
            "precipitation_probability_max": [73, 100],
            "wind_speed_10m_max": [8.1, 7.9],
        }
    }
    client = mock_weather_client(geocoding, forecast)
    tool = create_weather_tool(client)

    try:
        result = await tool.run({"location": "Острогожск"})
    finally:
        await client.aclose()

    assert tool.name == "get_weather"
    assert not tool.requires_confirmation
    assert "Ostrogozhsk" in result
    assert "today (2026-11-25)" in result
    assert "tomorrow (2026-11-26)" in result
    assert "-3°C" in result
    assert "100%" in result


async def test_weather_tool_reports_unknown_location() -> None:
    client = mock_weather_client()
    tool = create_weather_tool(client)

    try:
        result = await tool.run({"location": "Nowhere"})
    finally:
        await client.aclose()

    assert result.startswith("Location not found")


async def test_weather_tool_reports_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    tool = create_weather_tool(client)

    try:
        result = await tool.run({"location": "Ostrogozhsk"})
    finally:
        await client.aclose()

    assert result.startswith("Weather lookup failed")
