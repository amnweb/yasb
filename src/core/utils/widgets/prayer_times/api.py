import json
import logging
import traceback
from typing import Callable

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

HEADER = (b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0")


class PrayerTimesDataFetcher(QObject):
    """Fetches Islamic prayer times from the Aladhan API."""

    finished = pyqtSignal(dict)

    def __init__(self, parent: QObject, url_factory: Callable[[], str], timeout_ms: int):
        """
        Args:
            parent: Qt parent object.
            url_factory: A callable that returns the current API URL string.
                         Called on every request so the date is always today.
            timeout_ms: Interval between automatic re-fetches, in milliseconds.
        """
        super().__init__(parent)
        self.started = False
        self._url_factory = url_factory
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._handle_response)
        self._timer = QTimer(self)
        self._timer.setInterval(timeout_ms)
        self._timer.timeout.connect(self.make_request)

    def start(self) -> None:
        """Begin periodic fetching. The first request fires immediately."""
        self.make_request()
        self._timer.start()
        self.started = True

    def make_request(self) -> None:
        """Make a single API request using the current URL from url_factory."""
        url = QUrl(self._url_factory())
        if not url.isValid():
            logging.error("Prayer times: built an invalid URL 窶・check latitude/longitude settings.")
            return
        request = QNetworkRequest(url)
        request.setRawHeader(*HEADER)
        self._manager.get(request)

    def _handle_response(self, reply: QNetworkReply) -> None:
        try:
            error = reply.error()
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if error == QNetworkReply.NetworkError.NoError:
                raw = reply.readAll().data().decode("utf-8", errors="replace")
                data = json.loads(raw)
                if data.get("code") == 200:
                    self.finished.emit(data)
                else:
                    logging.error(f"Prayer times API returned non-200 code: {data.get('code')} 窶・{data.get('status')}")
                    self.finished.emit({})
            elif error == QNetworkReply.NetworkError.HostNotFoundError:
                logging.warning("Prayer times: no internet connection or host not found.")
                self.finished.emit({})
            else:
                logging.error(f"Prayer times API network error {status}: {error}")
                self.finished.emit({})
        except json.JSONDecodeError as e:
            logging.error(f"Prayer times: invalid JSON in response: {e}")
            self.finished.emit({})
        except Exception as e:
            logging.error(f"Prayer times: unexpected error: {e}\n{traceback.format_exc()}")
            self.finished.emit({})
        finally:
            reply.deleteLater()
