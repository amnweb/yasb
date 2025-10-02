import json
import logging
import traceback
from datetime import datetime
from random import randint
from typing import Any

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

HEADER = (b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0")
CACHE_CONTROL = (b"Cache-Control", b"no-cache")


class BadRequestError(Exception):
    pass


class HostNotFoundError(Exception):
    pass


class WeatherDataFetcher(QObject):
    """Fetches and processes weather data from a URL."""

    finished = pyqtSignal(dict)

    _cached_url = None
    _instance: "WeatherDataFetcher|None" = None

    @classmethod
    def get_instance(cls, parent: QObject, url: QUrl, timeout: int):
        if cls._cached_url == url and cls._instance is not None:
            return cls._instance
        cls._cached_url = url
        cls._instance = WeatherDataFetcher(parent, url, timeout)
        return cls._instance

    def __init__(self, parent: QObject, url: QUrl, timeout: int):
        super().__init__(parent)
        self.started = False
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self.handle_response)  # type: ignore[reportUnknownMemberType]
        self._fetch_weather_data_timer = QTimer(self)
        self._fetch_weather_data_timer.timeout.connect(self.make_request)  # type: ignore[reportUnknownMemberType]
        self._url = url
        self._timeout = timeout
        self._weather_cache: dict[str, Any] = {}

    def start(self):
        # To not make two or more requests at the same time
        QTimer.singleShot(randint(200, 600), self.make_request)  # type: ignore[reportUnknownMemberType]
        self._fetch_weather_data_timer.start(self._timeout)
        self.started = True

    def make_request(self, url: QUrl | None = None):
        if url is None:
            url = self._url
        request = QNetworkRequest(url)
        request.setRawHeader(*HEADER)
        request.setRawHeader(*CACHE_CONTROL)
        self._manager.get(request)

    def handle_response(self, reply: QNetworkReply):
        try:
            error = reply.error()
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if error == QNetworkReply.NetworkError.NoError:
                logging.info(f"Fetching new weather data at {datetime.now()}")
                data = json.loads(reply.readAll().data().decode())
                self.finished.emit(data)
                reply.deleteLater()
                return
            elif error == QNetworkReply.NetworkError.HostNotFoundError:
                raise HostNotFoundError("No internet connection or host not found. Unable to fetch weather.")
            elif status in {400, 401, 403}:
                data = json.loads(reply.readAll().data().decode())
                raise BadRequestError(f"Weather response error {status}: {data['error']['message']}")
            else:
                raise Exception(f"Weather response error {status}: {error.name} {error.value}.")
        except json.JSONDecodeError as e:
            logging.error(f"Weather API invalid JSON response: {e}")
        except (BadRequestError, HostNotFoundError) as e:
            logging.error(e)
        except Exception as e:
            logging.error(f"{e}\n{traceback.format_exc()}")
        self.finished.emit({})
        reply.deleteLater()


class IconFetcher(QObject):
    """Fetches and caches icons from a list of URLs."""

    finished = pyqtSignal()

    _instance: "IconFetcher|None" = None

    @classmethod
    def get_instance(cls, parent: QObject):
        if cls._instance is not None:
            return cls._instance
        cls._instance = IconFetcher(parent)
        return cls._instance

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._pending_icons: set[str] = set()
        self._icon_cache: dict[str, bytes] = {}

    def fetch_icons(self, icon_urls: list[str]):
        for url in icon_urls:
            if url in self._icon_cache and self._icon_cache[url]:
                continue
            if url in self._pending_icons:
                continue
            self._pending_icons.add(url)
            request = QNetworkRequest(QUrl(url))
            request.setRawHeader(*HEADER)
            request.setRawHeader(*CACHE_CONTROL)
            reply = self._manager.get(request)
            reply.finished.connect(lambda reply=reply, url=url: self._handle_reply(reply, url))  # type: ignore
        if len(self._pending_icons) == 0:
            self.finished.emit()

    def _handle_reply(self, reply: QNetworkReply, url: str):
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll().data()
                if not data:
                    raise Exception(f"Failed to fetch icon {url}: No data received")
                self._icon_cache[url] = data
                self._pending_icons.discard(url)
            else:
                raise Exception(f"Failed to fetch icon {url}: {reply.error().name} {reply.error().value}")
        except Exception as e:
            logging.warning(e)
        finally:
            if len(self._pending_icons) == 0:
                self.finished.emit()
            reply.deleteLater()

    def get_icon(self, url: str) -> bytes:
        return self._icon_cache.get(url, b"")

    def set_icon(self, url: str, data: bytes):
        self._icon_cache[url] = data
