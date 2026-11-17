"""Public/local network details with persistent cache and non-blocking lookups."""

import json
import socket
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, cast

from PyQt6.QtCore import QObject, pyqtSignal

from core.utils.system import app_data_path
from core.widgets.services.traffic.network_api import NetworkAPI

INFO_FIELDS = (
    "IP address",
    "IP local",
    "Continent",
    "Country",
    "Region",
    "City",
    "Location",
    "ISP",
    "Organization",
    "Timezone",
    "Currency",
)


def local_ip(interface: str) -> str:
    if interface.lower() != "auto":
        return NetworkAPI.get_interface_ip(interface) or ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            # UDP connect chooses a route locally; it sends no packet.
            connection.connect(("1.1.1.1", 80))
            return connection.getsockname()[0]
    except OSError:
        return ""


def parse_public_info(data: dict[str, Any]) -> dict[str, str]:
    if data.get("success") is False or not data.get("ip"):
        raise ValueError("Public IP lookup unavailable")
    connection = data.get("connection")
    connection = cast(dict[str, Any], connection) if isinstance(connection, dict) else {}
    timezone = data.get("timezone")
    timezone = cast(dict[str, Any], timezone).get("id") if isinstance(timezone, dict) else timezone
    currency = data.get("currency")
    currency = cast(dict[str, Any], currency).get("code") if isinstance(currency, dict) else currency
    values = {
        "IP address": data.get("ip"),
        "Continent": data.get("continent"),
        "Country": data.get("country"),
        "Region": data.get("region"),
        "City": data.get("city"),
        "Location": f"{data['latitude']}, {data['longitude']}"
        if data.get("latitude") is not None and data.get("longitude") is not None
        else "",
        "ISP": connection.get("isp"),
        "Organization": connection.get("org"),
        "Timezone": timezone,
        "Currency": currency,
    }
    return {key: str(value) if value is not None else "" for key, value in values.items()}


class NetworkInfoService(QObject):
    changed = pyqtSignal(dict, str)

    def __init__(self, interface: str, ttl: int = 300, parent: QObject | None = None, cache_path: Path | None = None):
        super().__init__(parent)
        self.interface = interface
        self.ttl = ttl
        self.cache_path = cache_path or app_data_path("network_info_cache.json")
        self._lock = threading.Lock()
        self._busy = False
        self._timestamp = 0.0
        self._retry_after = 0.0
        self._data: dict[str, str] = {}
        self.status = ""
        try:
            cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(cached.get("data"), dict) and isinstance(cached.get("timestamp"), (int, float)):
                self._data = {
                    key: str(value) for key, value in cached["data"].items() if key in INFO_FIELDS and value is not None
                }
                self._timestamp = float(cached["timestamp"])
        except OSError, ValueError, TypeError, AttributeError:
            pass

    def snapshot(self) -> dict[str, str]:
        with self._lock:
            data = dict(self._data)
        data["IP local"] = local_ip(self.interface)
        return data

    @staticmethod
    def _request(url: str) -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"User-Agent": "YASB-Network-Info/2.0"})
        with urllib.request.urlopen(request, timeout=4) as response:
            data = json.load(response)
        if not isinstance(data, dict):
            raise ValueError("Invalid network information response")
        return cast(dict[str, Any], data)

    def refresh(self, force: bool = False) -> None:
        address = local_ip(self.interface)
        now = time.time()
        with self._lock:
            same_network = self._data.get("IP local") == address
            fresh = same_network and bool(self._data.get("IP address")) and 0 <= now - self._timestamp < self.ttl
            self._data["IP local"] = address
            start = not self._busy and (force or (not fresh and now >= self._retry_after))
            if start:
                self._busy = True
                self.status = "Updating..."
            data, status = dict(self._data), self.status
        self._emit(data, status)
        if start:
            threading.Thread(target=self._run, name="yasb-network-info", daemon=True).start()

    def _emit(self, data: dict[str, str], status: str) -> None:
        try:
            self.changed.emit(data, status)
        except RuntimeError:
            pass  # The bar can be reloaded while a bounded HTTP request finishes.

    def _publish(self, data: dict[str, str]) -> None:
        now = time.time()
        with self._lock:
            self._data = dict(data)
            self._timestamp = now
            self.status = ""
        temporary = self.cache_path.with_name(f"{self.cache_path.name}.{threading.get_ident()}.tmp")
        try:
            temporary.write_text(json.dumps({"timestamp": now, "data": data}), encoding="utf-8")
            temporary.replace(self.cache_path)
        except OSError:
            pass
        self._emit(dict(data), "")

    def _run(self) -> None:
        try:
            data = parse_public_info(self._request("https://ipwho.is/"))
            data["IP local"] = local_ip(self.interface)
            with self._lock:
                previous = dict(self._data)
            if data["IP address"] == previous.get("IP address") and not data.get("Currency"):
                data["Currency"] = previous.get("Currency", "")
            self._publish(data)
            if not data.get("Currency"):
                try:
                    extra = self._request("https://ipapi.co/json/")
                    if extra.get("ip") == data["IP address"] and extra.get("currency"):
                        self._publish(dict(data, Currency=str(extra["currency"])))
                except OSError, ValueError, TypeError:
                    pass
        except OSError, ValueError, TypeError:
            with self._lock:
                self.status = (
                    "Saved information (offline)" if self._data.get("IP address") else "Public information unavailable."
                )
                self._retry_after = time.time() + 60
                data, status = dict(self._data), self.status
            self._emit(data, status)
        finally:
            with self._lock:
                self._busy = False
