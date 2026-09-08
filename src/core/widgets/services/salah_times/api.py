"""City search via the free Open-Meteo geocoding API.

Returns latitude, longitude, ISO country code and IANA timezone for a place,
which is everything the widget needs to add a location (no API key required).
Uses Qt's networking so requests stay on the Qt event loop, matching the
open_meteo widget's approach.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

logger = logging.getLogger("salah_times")

_HEADER = (b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) YASB SalahTimes")
_CACHE_CONTROL = (b"Cache-Control", b"no-cache")
_GEOCODING_BASE_URL = "https://geocoding-api.open-meteo.com/v1/search"


class GeocodingFetcher(QObject):
    """Searches for locations using the Open-Meteo Geocoding API."""

    results_ready = pyqtSignal(list)

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._handle_response)
        self._country_filter: str | None = None

    def search(self, query: str, count: int = 20) -> None:
        if not query or len(query.strip()) < 2:
            self.results_ready.emit([])
            return

        # Allow a trailing 2-letter country code to filter, e.g. "London, GB".
        self._country_filter = None
        match = re.search(r"^(.*?)(?:,\s*|\s+)([A-Za-z]{2})$", query.strip())
        if match:
            query = match.group(1).strip()
            self._country_filter = match.group(2).upper()

        url = QUrl(
            f"{_GEOCODING_BASE_URL}"
            f"?name={QUrl.toPercentEncoding(query).data().decode()}"
            f"&count={count}"
            f"&language=en"
            f"&format=json"
        )
        request = QNetworkRequest(url)
        request.setRawHeader(*_HEADER)
        request.setRawHeader(*_CACHE_CONTROL)
        self._manager.get(request)

    def _handle_response(self, reply: QNetworkReply) -> None:
        results: list[dict[str, Any]] = []
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = json.loads(reply.readAll().data().decode())
                raw = data.get("results", []) or []
                if self._country_filter:
                    results = [r for r in raw if r.get("country_code", "").upper() == self._country_filter]
                else:
                    results = raw
            else:
                logger.warning("Geocoding search failed: %s", reply.error().name)
        except json.JSONDecodeError as e:
            logger.error("Geocoding invalid JSON: %s", e)
        except Exception as e:
            logger.error("Geocoding error: %s", e)
        finally:
            self._country_filter = None
            self.results_ready.emit(results)
            reply.deleteLater()
