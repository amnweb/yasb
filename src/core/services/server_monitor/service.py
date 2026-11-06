import logging
import os
from dataclasses import dataclass
from threading import Event
from typing import Any, ClassVar, cast

from PyQt6.QtCore import QDateTime, QObject, pyqtProperty, pyqtSignal, pyqtSlot
from winrt.windows.networking.connectivity import NetworkConnectivityLevel, NetworkInformation

from core.app.windows.toast import ToastNotifier
from core.services.server_monitor.worker import ServerStatus, check_server
from core.utils.feed import Feed
from core.utils.worker import run_in_worker
from settings import SCRIPT_PATH

logger = logging.getLogger("server_monitor")


@dataclass(frozen=True)
class ServerSettings:
    servers: tuple[tuple[str, str], ...]
    ssl_verify: bool
    ssl_check: bool
    timeout: int
    interval: int
    ssl_warning: int
    notify_offline: bool
    notify_ssl: bool


@dataclass
class CheckResult:
    servers: list[ServerStatus]
    disconnected: bool


def _network_disconnected() -> bool:
    try:
        return all(
            profile.get_network_connectivity_level() == NetworkConnectivityLevel.NONE
            for profile in NetworkInformation.get_connection_profiles()
        )
    except OSError, RuntimeError:
        logger.debug("Could not read Windows network connectivity", exc_info=True)
        return False


def _check(settings: ServerSettings, stopped: Event) -> CheckResult:
    results: list[ServerStatus] = []
    for name, url in settings.servers:
        if stopped.is_set():
            return CheckResult(results, False)
        results.append(check_server(name, url, settings.ssl_verify, settings.ssl_check, settings.timeout))

    # A failed request alone cannot distinguish a down server from a disconnected PC.
    disconnected = (
        settings.notify_offline
        and not stopped.is_set()
        and all(server["response_code"] is None for server in results)
        and _network_disconnected()
    )
    return CheckResult(results, disconnected)


class ServerCheckFeed(Feed[ServerSettings]):
    _feeds: ClassVar[dict[Any, Any]] = {}

    def __init__(self, key: ServerSettings) -> None:
        super().__init__(key)
        self.results: list[ServerStatus] = []
        self.updated = QDateTime()
        self._stopped = Event()
        self._timer.start(0)

    def _user_destroyed(self) -> None:
        if self._users == 1:
            self._stopped.set()
        super()._user_destroyed()

    @pyqtSlot()
    def fetch(self) -> None:
        if self.loading or self._stopped.is_set():
            return
        self._timer.stop()
        self.loading = True
        self.error = ""
        self.changed.emit()
        key, stopped = self.key, self._stopped
        run_in_worker(lambda: _check(key, stopped), self._receive, "Could not check servers.")

    def _receive(self, result: object, error: str) -> None:
        if self._stopped.is_set():
            return
        self.loading = False
        self.error = error
        self._timer.start(self.key.interval * 1000)
        if isinstance(result, CheckResult):
            self.results = result.servers
            self.updated = QDateTime.currentDateTime()
            self._notify(result)
        self.changed.emit()

    def _notify(self, result: CheckResult) -> None:
        offline = sum(server["status"] == "Offline" for server in result.servers)
        messages: list[str] = []
        if self.key.notify_offline and offline and not result.disconnected:
            messages.append(f"{offline} server(s) are offline")
        if self.key.notify_ssl and any(
            (days := server["ssl"]) is not None and days < self.key.ssl_warning for server in result.servers
        ):
            messages.append("Some servers have SSL certificates expiring soon")
        if messages:
            try:
                toaster = ToastNotifier()
                icon = os.path.join(SCRIPT_PATH, "assets", "images", "app_transparent.png")
                for message in messages:
                    toaster.show(icon, "Server Monitor", message)
            except OSError, RuntimeError:
                logger.warning("Could not show Server Monitor notification", exc_info=True)


class ServerChecks(QObject):
    changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._feed: ServerCheckFeed | None = None

    @pyqtProperty("QVariantList", notify=changed)
    def results(self) -> list[ServerStatus]:
        return self._feed.results if self._feed else []

    @pyqtProperty(bool, notify=changed)
    def loading(self) -> bool:
        return self._feed.loading if self._feed else False

    @pyqtProperty(bool, notify=changed)
    def configured(self) -> bool:
        return self._feed is not None

    @pyqtProperty(str, notify=changed)
    def error(self) -> str:
        return self._feed.error if self._feed else ""

    @pyqtProperty(QDateTime, notify=changed)
    def updated(self) -> QDateTime:
        return self._feed.updated if self._feed else QDateTime()

    @pyqtSlot("QVariantList", bool, bool, int, int, int, bool, bool)
    def configure(
        self,
        servers: list[Any],
        ssl_verify: bool,
        ssl_check: bool,
        timeout: int,
        interval: int,
        ssl_warning: int,
        notify_offline: bool,
        notify_ssl: bool,
    ) -> None:
        entries: list[tuple[str, str]] = []
        for server in servers:
            if isinstance(server, str) and (url := server.strip()):
                entries.append((url, url))
            elif isinstance(server, dict):
                entry = cast(dict[str, Any], server)
                raw_url = entry.get("url")
                if isinstance(raw_url, str) and (url := raw_url.strip()):
                    name = entry.get("name")
                    entries.append((name.strip() if isinstance(name, str) and name.strip() else url, url))

        key = ServerSettings(
            tuple(entries),
            ssl_verify,
            ssl_check,
            max(1, min(timeout, 30)),
            max(10, min(interval, 36000)),
            max(1, min(ssl_warning, 365)),
            notify_offline,
            notify_ssl,
        )
        if self._feed is not None:
            if self._feed.key == key:
                return
            self._feed.changed.disconnect(self.changed)
            self._feed.leave(self)
        self._feed = ServerCheckFeed.join(key, self) if entries else None
        if self._feed is not None:
            self._feed.changed.connect(self.changed)
        self.changed.emit()

    @pyqtSlot()
    def refresh(self) -> None:
        if self._feed is not None:
            self._feed.fetch()
