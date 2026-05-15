#!/usr/bin/env python3
"""Fetch current weather data for a city using the Open-Meteo API (no API key required).

Usage:
    python execution/fetch_weather.py --city "London" --output .tmp/weather_result.json
    python execution/fetch_weather.py --city "London" --output .tmp/weather_result.json --mock
"""

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MAX_RESPONSE_SIZE = 10 * 1024 * 1024


def _error_exit(code: str, message: str) -> None:
    """Emit structured JSON error to stdout and exit non-zero."""
    print(json.dumps({"status": "error", "error_code": code, "message": message}))
    sys.exit(1)


def _safe_path(path_str: str) -> Path:
    """Validate that a path resolves under PROJECT_ROOT/.tmp/."""
    allowed = (PROJECT_ROOT / ".tmp").resolve()
    resolved = Path(path_str).resolve()
    if not (str(resolved).startswith(str(allowed) + os.sep) or resolved == allowed):
        _error_exit("path_violation", f"Path must be under {allowed} — got {resolved}")
    return resolved


def _atomic_write(path: Path, content: str) -> None:
    """Write atomically via temp file + os.replace()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _geocode(city: str) -> dict:
    """Look up city coordinates via Open-Meteo Geocoding API."""
    try:
        resp = requests.get(
            GEOCODING_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        _error_exit("network_error", f"Geocoding request failed: {e}")

    if resp.status_code != 200:
        _error_exit("geocoding_error", f"Geocoding API returned status {resp.status_code}")
    if len(resp.content) > MAX_RESPONSE_SIZE:
        _error_exit("response_too_large", "Geocoding response exceeded size limit")

    data = resp.json()
    results = data.get("results")
    if not results:
        _error_exit("city_not_found", f"No results found for city: {city}")

    return results[0]


def _fetch_forecast(lat: float, lon: float) -> dict:
    """Fetch current weather from Open-Meteo Forecast API."""
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            },
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        _error_exit("network_error", f"Forecast request failed: {e}")

    if resp.status_code != 200:
        _error_exit("forecast_error", f"Forecast API returned status {resp.status_code}")
    if len(resp.content) > MAX_RESPONSE_SIZE:
        _error_exit("response_too_large", "Forecast response exceeded size limit")

    return resp.json()


def run(args: argparse.Namespace) -> dict:
    """Core logic. Returns a result dict for structured output."""
    if args.mock:
        log.info("Mock mode — returning static sample data")
        return {
            "status": "success",
            "mock": True,
            "note": "Static mock data — values do not vary by city",
            "city": "London",
            "country": "United Kingdom",
            "latitude": 51.5085,
            "longitude": -0.1257,
            "current": {
                "temperature_2m": 15.2,
                "apparent_temperature": 13.8,
                "relative_humidity_2m": 72,
                "weather_code": 3,
                "wind_speed_10m": 12.5,
            },
        }

    location = _geocode(args.city)
    log.info("Found: %s, %s (%.2f, %.2f)", location["name"], location.get("country", ""), location["latitude"], location["longitude"])

    forecast = _fetch_forecast(location["latitude"], location["longitude"])
    current = forecast.get("current", {})

    return {
        "status": "success",
        "city": location["name"],
        "country": location.get("country", ""),
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "current": current,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch current weather for a city.")
    parser.add_argument("--city", required=True, help="City name to look up")
    parser.add_argument("--output", required=True, help="Output JSON path (must be under .tmp/)")
    parser.add_argument("--mock", action="store_true", help="Return mock data without external calls")
    args = parser.parse_args()

    output_path = _safe_path(args.output)
    result = run(args)
    _atomic_write(output_path, json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
