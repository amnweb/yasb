import json
import logging
import re
import traceback
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
            f"&forecast_days=7"
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
                logger.info("Fetched new Open-Meteo weather data")
                data = json.loads(reply.readAll().data().decode())
                self.finished.emit(data)
            elif error == QNetworkReply.NetworkError.HostNotFoundError:
                logger.error("No internet connection or host not found. Unable to fetch weather.")
                self.finished.emit({})
            elif status in {400, 401, 403}:
                data = json.loads(reply.readAll().data().decode())
                logger.error(f"Open-Meteo API error {status}: {data.get('reason', 'Unknown')}")
                self.finished.emit({})
            else:
                logger.error(f"Open-Meteo response error {status}: {error.name} {error.value}")
                self.finished.emit({})
        except json.JSONDecodeError as e:
            logger.error(f"Open-Meteo invalid JSON response: {e}")
            self.finished.emit({})
        except Exception as e:
            logger.error(f"Open-Meteo fetch error: {e}\n{traceback.format_exc()}")
            self.finished.emit({})
        finally:
            reply.deleteLater()


class GeocodingFetcher(QObject):
    """Searches for locations using the Open-Meteo Geocoding API."""

    results_ready = pyqtSignal(list)

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._handle_response)
        self._current_country_filter: str | None = None

    def search(self, query: str, count: int = 100):
        """Search for locations matching the query string."""
        if not query or len(query.strip()) < 3:
            self.results_ready.emit([])
            return

        # Check for a trailing 2-letter country code
        self._current_country_filter = None
        match = re.search(r"^(.*?)(?:,\s*|\s+)([A-Za-z]{2})$", query.strip())
        if match:
            query = match.group(1).strip()
            self._current_country_filter = match.group(2).upper()

        url = QUrl(
            f"{GEOCODING_BASE_URL}"
            f"?name={QUrl.toPercentEncoding(query).data().decode()}"
            f"&count={count}"
            f"&language=en"
            f"&format=json"
        )
        request = QNetworkRequest(url)
        request.setRawHeader(*HEADER)
        request.setRawHeader(*CACHE_CONTROL)
        self._manager.get(request)

    def _handle_response(self, reply: QNetworkReply):
        results: list[dict[str, Any]] = []
        try:
            error = reply.error()
            if error == QNetworkReply.NetworkError.NoError:
                data = json.loads(reply.readAll().data().decode())
                raw_results: list[dict[str, Any]] = data.get("results", [])

                if self._current_country_filter:
                    # Filter results by the extracted 2-letter country code
                    results = [
                        r for r in raw_results if r.get("country_code", "").upper() == self._current_country_filter
                    ]
                else:
                    results = raw_results
            else:
                logger.warning(f"Geocoding search failed: {error.name}")
        except json.JSONDecodeError as e:
            logger.error(f"Geocoding invalid JSON response: {e}")
        except Exception as e:
            logger.error(f"Geocoding fetch error: {e}")
        finally:
            self._current_country_filter = None
            self.results_ready.emit(results)
            reply.deleteLater()
