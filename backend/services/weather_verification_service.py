import json
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Tuple


_WEATHER_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _is_weather_related(incident_type: str, text: str) -> bool:
    merged = f"{incident_type} {text}".lower()
    keywords = [
        "flood",
        "rain",
        "storm",
        "cyclone",
        "weather",
        "landslide",
        "water logging",
        "cloudburst",
    ]
    return any(keyword in merged for keyword in keywords)


def _cache_key(latitude: float, longitude: float) -> str:
    return f"{round(latitude, 2)}:{round(longitude, 2)}"


def _read_cache(latitude: float, longitude: float) -> Dict[str, Any]:
    key = _cache_key(latitude, longitude)
    entry = _WEATHER_CACHE.get(key)
    if not entry:
        return {}
    expires_at, payload = entry
    if expires_at <= time.time():
        _WEATHER_CACHE.pop(key, None)
        return {}
    return payload


def _write_cache(latitude: float, longitude: float, payload: Dict[str, Any], ttl_seconds: int = 600) -> None:
    key = _cache_key(latitude, longitude)
    _WEATHER_CACHE[key] = (time.time() + ttl_seconds, payload)


def _fetch_open_meteo(latitude: float, longitude: float, timeout_seconds: int = 4) -> Dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "rain,precipitation,weather_code,temperature_2m,wind_speed_10m",
            "timezone": "auto",
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{query}"
    req = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    current = payload.get("current") or {}
    return {
        "provider": "open-meteo",
        "rain": float(current.get("rain", 0) or 0),
        "precipitation": float(current.get("precipitation", 0) or 0),
        "weather_code": int(current.get("weather_code", 0) or 0),
        "temperature_c": float(current.get("temperature_2m", 0) or 0),
        "wind_speed_kmh": float(current.get("wind_speed_10m", 0) or 0),
    }


def _confirmation_score(weather: Dict[str, Any]) -> float:
    rain = float(weather.get("rain", 0) or 0)
    precipitation = float(weather.get("precipitation", 0) or 0)
    code = int(weather.get("weather_code", 0) or 0)

    severe_codes = {61, 63, 65, 80, 81, 82, 95, 96, 99}
    if rain >= 2.0 or precipitation >= 3.0 or code in severe_codes:
        return 1.0
    if rain > 0 or precipitation > 0:
        return 0.6
    return 0.0


def verify_weather(
    latitude: float,
    longitude: float,
    incident_type: str,
    text: str,
) -> Dict[str, Any]:
    if not _is_weather_related(incident_type, text):
        return {
            "weather_relevant": False,
            "confirmation_score": 0.5,
            "status": "skipped_non_weather_incident",
            "source": "not_applicable",
            "weather": {},
        }

    try:
        weather = _fetch_open_meteo(latitude, longitude)
        _write_cache(latitude, longitude, weather)
        return {
            "weather_relevant": True,
            "confirmation_score": _confirmation_score(weather),
            "status": "live",
            "source": "open-meteo",
            "weather": weather,
            "used_cache": False,
        }
    except Exception as exc:
        cached = _read_cache(latitude, longitude)
        if cached:
            return {
                "weather_relevant": True,
                "confirmation_score": _confirmation_score(cached),
                "status": "cached",
                "source": "cache",
                "weather": cached,
                "used_cache": True,
                "error": str(exc),
            }
        return {
            "weather_relevant": True,
            "confirmation_score": 0.5,
            "status": "unavailable_fallback",
            "source": "fallback",
            "weather": {},
            "used_cache": False,
            "error": str(exc),
        }
