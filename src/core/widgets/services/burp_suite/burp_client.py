"""Burp Suite detection and REST API health probing for the Burp Suite widget.

Burp Suite is detected by enumerating top-level window titles (it always sets a
``Burp Suite ...`` title), which also reveals the edition. When the REST API is
enabled, the service URL root (``GET http://host:port/``) is probed: it responds
with ``{"burp_status": "ready"}`` and requires no API key, making it a safe,
read-only health check. All work runs off the UI thread in a QThread.
"""

import json
import logging
import urllib.request

import win32gui
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("burp_suite")

# Window-title fragments mapped to a short edition label, checked in order.
_EDITIONS: list[tuple[str, str]] = [
    ("professional", "Pro"),
    ("community", "Community"),
    ("enterprise", "Enterprise"),
    ("dast", "DAST"),
]

# Returned states, ordered by increasing "liveness".
STATE_OFFLINE = "offline"
STATE_RUNNING = "running"
STATE_READY = "ready"


def _find_burp_window_title() -> str | None:
    """Return the title of the first visible Burp Suite window, or None."""
    titles: list[str] = []

    def _collect(hwnd: int, _lparam: int) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and "burp suite" in title.lower():
                titles.append(title)
        return True

    try:
        win32gui.EnumWindows(_collect, 0)
    except Exception as e:
        logger.debug("window enumeration failed: %s", e)
    return titles[0] if titles else None


def _edition_from_title(title: str) -> str:
    lowered = title.lower()
    for fragment, label in _EDITIONS:
        if fragment in lowered:
            return label
    return "Suite"


def _rest_api_ready(host: str, port: int) -> bool:
    """Probe the REST API service root. True only when Burp reports ``ready``."""
    url = f"http://{host}:{port}/"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("burp_status") == "ready"
    except Exception as e:
        logger.debug("REST API probe failed: %s", e)
        return False


def probe_burp(rest_enabled: bool, host: str, port: int) -> dict[str, object]:
    """Build a status record describing the current Burp Suite state."""
    title = _find_burp_window_title()
    if title is None:
        return {"state": STATE_OFFLINE, "edition": "", "rest_ready": False}

    edition = _edition_from_title(title)
    rest_ready = rest_enabled and _rest_api_ready(host, port)
    state = STATE_READY if rest_ready else STATE_RUNNING
    return {"state": state, "edition": edition, "rest_ready": rest_ready}


class BurpStatusWorker(QThread):
    """Runs window enumeration + the (blocking) REST probe off the UI thread."""

    status_ready = pyqtSignal(dict)

    def __init__(self, rest_enabled: bool, host: str, port: int, parent: object = None):
        super().__init__(parent)
        self._rest_enabled = rest_enabled
        self._host = host
        self._port = port

    def run(self) -> None:
        self.status_ready.emit(probe_burp(self._rest_enabled, self._host, self._port))
