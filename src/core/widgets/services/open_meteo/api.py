import json
import logging
import traceback
import unicodedata
from typing import Any

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

logger = logging.getLogger("open_meteo")

HEADER = (b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0")
CACHE_CONTROL = (b"Cache-Control", b"no-cache")

# Open-Meteo API base URLs
FORECAST_BASE_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_BASE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# Hourly variables to request
HOURLY_VARS = "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,precipitation_probability,rain,snowfall"

# Daily variables to request
DAILY_VARS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "apparent_temperature_max,apparent_temperature_min,"
    "precipitation_sum,precipitation_probability_max,"
    "wind_speed_10m_max,wind_direction_10m_dominant,"
    "sunrise,sunset,uv_index_max"
)

# Current weather variables to request
CURRENT_VARS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "weather_code,wind_speed_10m,wind_direction_10m,"
    "is_day,precipitation,pressure_msl,cloud_cover"
)

# Search fields
REGION_FIELDS = ("admin3", "admin2", "admin1", "country", "country_code")


class OpenMeteoDataFetcher(QObject):
    """Fetches weather forecast data from the Open-Meteo API."""

    finished = pyqtSignal(dict)

    def __init__(
        self,
        parent: QObject,
        latitude: float,
        longitude: float,
        timeout: int,
        units: str = "metric",
        forecast_days: int = 7,
    ):
        super().__init__(parent)
        self.started = False
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._handle_response)

        self._fetch_timer = QTimer(self)
        self._fetch_timer.timeout.connect(self.make_request)
        self._timeout = timeout

        # Build the forecast URL
        temp_unit = "fahrenheit" if units == "imperial" else "celsius"
        wind_unit = "mph" if units == "imperial" else "kmh"

        self._url = QUrl(
            f"{FORECAST_BASE_URL}"
            f"?latitude={latitude}&longitude={longitude}"
            f"&hourly={HOURLY_VARS}"
            f"&daily={DAILY_VARS}"
            f"&current={CURRENT_VARS}"
            f"&timezone=auto"
            f"&forecast_days={forecast_days}"
            f"&temperature_unit={temp_unit}"
            f"&wind_speed_unit={wind_unit}"
        )

    def start(self, delayed: bool = False):
        """Start fetching weather data periodically."""
        if not delayed:
            QTimer.singleShot(200, self.make_request)
        self._fetch_timer.start(self._timeout)
        self.started = True

    def stop(self):
        """Stop fetching weather data."""
        self._fetch_timer.stop()
        self.started = False

    def make_request(self):
        """Make a single weather data request."""
        request = QNetworkRequest(self._url)
        request.setRawHeader(*HEADER)
        request.setRawHeader(*CACHE_CONTROL)
        self._manager.get(request)

    def _handle_response(self, reply: QNetworkReply):
        try:
            error = reply.error()
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if error == QNetworkReply.NetworkError.NoError:
                data = json.loads(reply.readAll().data().decode())
                self.finished.emit(data)
            elif error == QNetworkReply.NetworkError.HostNotFoundError:
                logger.error("No internet connection or host not found. Unable to fetch weather.")
                self.finished.emit({})
            elif status in {400, 401, 403}:
                data = json.loads(reply.readAll().data().decode())
                logger.error("Open-Meteo API error %s: %s", status, data.get("reason", "Unknown"))
                self.finished.emit({})
            else:
                logger.error("Open-Meteo response error %s: %s %s", status, error.name, error.value)
                self.finished.emit({})
        except json.JSONDecodeError as e:
            logger.error("Open-Meteo invalid JSON response: %s", e)
            self.finished.emit({})
        except Exception as e:
            logger.error("Open-Meteo fetch error: %s\n%s", e, traceback.format_exc())
            self.finished.emit({})
        finally:
            reply.deleteLater()


def fold(value: str) -> str:
    """Lowercase and strip accents for accent-insensitive matching."""
    stripped = unicodedata.normalize("NFKD", value)
    return "".join(c for c in stripped if not unicodedata.combining(c)).casefold()


class GeocodingFetcher(QObject):
    """Searches for locations using the Open-Meteo Geocoding API."""

    results_ready = pyqtSignal(list)

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._handle_response)

    def search(self, query: str, count: int = 100):
        """Search for locations matching the query string."""
        query = query.strip()
        if not query or len(query) < 3:
            self.results_ready.emit([])
            return

        name, _, region = query.partition(",")

        url = QUrl(
            f"{GEOCODING_BASE_URL}"
            f"?name={QUrl.toPercentEncoding(name.strip()).data().decode()}"
            f"&count={count}"
            f"&language=en"
            f"&format=json"
        )
        request = QNetworkRequest(url)
        request.setAttribute(QNetworkRequest.Attribute.User, fold(region.strip()))
        request.setRawHeader(*HEADER)
        request.setRawHeader(*CACHE_CONTROL)
        self._manager.get(request)

    def _handle_response(self, reply: QNetworkReply):
        results: list[dict[str, Any]] = []
        try:
            error = reply.error()
            if error == QNetworkReply.NetworkError.NoError:
                data = json.loads(reply.readAll().data().decode())
                results = data.get("results", [])
                region = reply.request().attribute(QNetworkRequest.Attribute.User)
                if region:
                    results = [
                        r for r in results if any(fold(r.get(f) or "").startswith(region) for f in self.REGION_FIELDS)
                    ]
            else:
                logger.warning("Geocoding search failed: %s", error.name)
        except json.JSONDecodeError as e:
            logger.error("Geocoding invalid JSON response: %s", e)
        except Exception as e:
            logger.error("Geocoding fetch error: %s", e)
        finally:
            self.results_ready.emit(results)
            reply.deleteLater()
