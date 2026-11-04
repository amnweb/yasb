import json
import logging
import unicodedata
from collections.abc import Callable
from typing import Any, cast

from PyQt6.QtCore import QUrl, QUrlQuery
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from settings import BUILD_VERSION

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT_MS = 20000

# Everything asked of Open-Meteo, by the name the forecast gives each value
CURRENT_FIELDS = {
    "temperature": "temperature_2m",
    "feelsLike": "apparent_temperature",
    "humidity": "relative_humidity_2m",
    "isDay": "is_day",
    "precipitation": "precipitation",
    "rain": "rain",
    "showers": "showers",
    "snowfall": "snowfall",
    "weatherCode": "weather_code",
    "cloudCover": "cloud_cover",
    "pressure": "pressure_msl",
    "windSpeed": "wind_speed_10m",
    "windDirection": "wind_direction_10m",
    "windGusts": "wind_gusts_10m",
}
HOURLY_FIELDS = {
    "temperature": "temperature_2m",
    "feelsLike": "apparent_temperature",
    "humidity": "relative_humidity_2m",
    "dewPoint": "dew_point_2m",
    "precipitationChance": "precipitation_probability",
    "precipitation": "precipitation",
    "rain": "rain",
    "showers": "showers",
    "snowfall": "snowfall",
    "weatherCode": "weather_code",
    "cloudCover": "cloud_cover",
    "pressure": "pressure_msl",
    "visibility": "visibility",
    "windSpeed": "wind_speed_10m",
    "windDirection": "wind_direction_10m",
    "windGusts": "wind_gusts_10m",
    "uvIndex": "uv_index",
    "isDay": "is_day",
}
DAILY_FIELDS = {
    "weatherCode": "weather_code",
    "high": "temperature_2m_max",
    "low": "temperature_2m_min",
    "feelsLikeHigh": "apparent_temperature_max",
    "feelsLikeLow": "apparent_temperature_min",
    "sunrise": "sunrise",
    "sunset": "sunset",
    "daylight": "daylight_duration",
    "uvIndex": "uv_index_max",
    "precipitation": "precipitation_sum",
    "rain": "rain_sum",
    "showers": "showers_sum",
    "snowfall": "snowfall_sum",
    "precipitationHours": "precipitation_hours",
    "precipitationChance": "precipitation_probability_max",
    "windSpeed": "wind_speed_10m_max",
    "windGusts": "wind_gusts_10m_max",
    "windDirection": "wind_direction_10m_dominant",
}
# Open-Meteo's unit names that read better shortened
UNIT_NAMES = {"mp/h": "mph", "inch": "in"}

# Fields of a geocoding result that the text after a comma is matched against, as in "Paris, Texas"
REGION_FIELDS = ("admin3", "admin2", "admin1", "country", "country_code")


def forecast_url(latitude: float, longitude: float, units: str, days: int) -> QUrl:
    imperial = units == "imperial"
    query = QUrlQuery()
    for name, value in (
        ("latitude", str(latitude)),
        ("longitude", str(longitude)),
        ("current", ",".join(CURRENT_FIELDS.values())),
        ("hourly", ",".join(HOURLY_FIELDS.values())),
        ("daily", ",".join(DAILY_FIELDS.values())),
        ("timezone", "auto"),
        ("forecast_days", str(days)),
        ("temperature_unit", "fahrenheit" if imperial else "celsius"),
        ("wind_speed_unit", "mph" if imperial else "kmh"),
        ("precipitation_unit", "inch" if imperial else "mm"),
    ):
        query.addQueryItem(name, value)
    url = QUrl(FORECAST_URL)
    url.setQuery(query)
    return url


def search_url(name: str, count: int, language: str) -> QUrl:
    query = QUrlQuery()
    for key, value in (
        ("name", QUrl.toPercentEncoding(name).data().decode()),
        ("count", str(count)),
        ("language", language),
        ("format", "json"),
    ):
        query.addQueryItem(key, value)
    url = QUrl(GEOCODING_URL)
    url.setQuery(query)
    return url


def fold(value: str) -> str:
    """Lowercase and without accents, so "Zurich" matches "Zürich"."""
    stripped = unicodedata.normalize("NFKD", value)
    return "".join(c for c in stripped if not unicodedata.combining(c)).casefold()


def in_region(place: dict[str, Any], region: str) -> bool:
    """Whether a geocoding result lies in the region typed after the comma, given folded."""
    return not region or any(fold(str(place.get(field) or "")).startswith(region) for field in REGION_FIELDS)


def read_reply(reply: QNetworkReply) -> tuple[Any, str]:
    """The reply's JSON and "", or None and what went wrong."""
    body = reply.readAll().data()
    try:
        data = json.loads(body) if body else None
    except ValueError:
        data = None
    error = reply.error()
    if error == QNetworkReply.NetworkError.NoError:
        return (data, "") if data is not None else (None, "Open-Meteo sent an answer YASB could not read.")
    status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
    reason = cast(dict[str, Any], data).get("reason") if isinstance(data, dict) else None
    logging.warning("Open-Meteo request failed: %s %s %s", error.name, status, reason or "")
    if reason:
        return None, f"Open-Meteo: {reason}"
    if status:
        return None, f"Open-Meteo returned HTTP {status}."
    return None, "Could not connect to Open-Meteo."


def get_json(network: QNetworkAccessManager, url: QUrl, done: Callable[[Any, str], None]) -> None:
    """Calls done(data, "") with what the URL returns, or done(None, error)."""
    request = QNetworkRequest(url)
    request.setRawHeader(b"User-Agent", f"YASB/{BUILD_VERSION}".encode())
    request.setTransferTimeout(TIMEOUT_MS)
    reply = network.get(request)
    if reply is None:
        done(None, "Could not connect to Open-Meteo.")
        return

    def finished() -> None:
        reply.deleteLater()
        try:
            done(*read_reply(reply))
        except RuntimeError:
            # Whoever asked was destroyed while Open-Meteo answered
            pass

    reply.finished.connect(finished)
