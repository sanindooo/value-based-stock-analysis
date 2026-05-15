# Directive: Check Weather

## Goal

Fetch current weather data for a given city and save it to `.tmp/`. This is the starter example that demonstrates the DOE pattern — use it as a reference when building your own directive + script pairs.

## When to Use

When the user asks for current weather information for a city. Also useful as a test to verify the DOE framework is working correctly in a new project.

## Inputs

- City name (provided by user)

## Outputs

- `.tmp/weather_result.json` — current weather data including temperature, humidity, and wind speed

## Workflow

### Step 1: Fetch Weather

```bash
python execution/fetch_weather.py --city "City Name" --output .tmp/weather_result.json
```

The script uses the Open-Meteo API (free, no API key required). It geocodes the city name to coordinates, then fetches current weather.

To test without making network requests:

```bash
python execution/fetch_weather.py --city "London" --output .tmp/weather_result.json --mock
```

### Step 2: Report

Read `.tmp/weather_result.json` and present a summary to the user. Key fields: `current.temperature_2m`, `current.relative_humidity_2m`, `current.wind_speed_10m`.

## Edge Cases

| Situation | Handling |
|-----------|----------|
| City not found | Script returns error JSON with `city_not_found` code — report to user |
| Network timeout | Script returns error JSON with `timeout` code — suggest retrying |
| Ambiguous city name | Script returns the top geocoding result — clarify with user if needed |

## Notes & Learnings
