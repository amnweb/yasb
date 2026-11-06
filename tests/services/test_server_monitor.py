# pyright: reportPrivateUsage=false

import socket
import ssl
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QMetaObject, QObject, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.qml_types import register_qml_types
from core.services.server_monitor import service
from core.services.server_monitor.worker import _build_url, _cert_not_after, check_server
from core.widget_files import find_widget_file
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait

CERT_UTC_TIME = """-----BEGIN CERTIFICATE-----
MIIBfDCCASOgAwIBAgIUMjrADyaY5iIAU7ePKJABQXd2RKgwCgYIKoZIzj0EAwIw
FDESMBAGA1UEAwwJbG9jYWxob3N0MB4XDTI2MTAyMTE3MDcwMFoXDTM2MTAxODE3
MDcwMFowFDESMBAGA1UEAwwJbG9jYWxob3N0MFkwEwYHKoZIzj0CAQYIKoZIzj0D
AQcDQgAE03uMq90gjUVPQKYlT6ca3qE3USJ1mGM9EzKQZo+Djv6UZ5gZfaS7fERS
BAydVize0ZCdgbhdzNPBn7EPNvtZb6NTMFEwHQYDVR0OBBYEFNJHOjUWeNF/5KOq
HNbLdEdjIvNHMB8GA1UdIwQYMBaAFNJHOjUWeNF/5KOqHNbLdEdjIvNHMA8GA1Ud
EwEB/wQFMAMBAf8wCgYIKoZIzj0EAwIDRwAwRAIgSHBY2PgSYX0oYck6MLMw8LnN
lZGeyDXHHHJrKIZIbV8CICWvOjsmoY8SI+WR+nCm8BDf9/VDWMUx9d7vMjMjAwVm
-----END CERTIFICATE-----
"""

CERT_UTC_TIME_KEY = """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg05RNDNGQqQt4DGUy
XR3QIsUyfXVXAdVmoKIKzKrGkvChRANCAATTe4yr3SCNRU9ApiVPpxreoTdRInWY
Yz0TMpBmj4OO/pRnmBl9pLt8RFIEDJ1WLN7RkJ2BuF3M08GfsQ82+1lv
-----END PRIVATE KEY-----
"""

CERT_UTC_TIME_EXPIRY = datetime(2036, 10, 18, 17, 7, tzinfo=UTC)

CERT_GENERALIZED_TIME = """-----BEGIN CERTIFICATE-----
MIIBfzCCASWgAwIBAgIUeDWowk2rXmYNzam/yxlviMagL/4wCgYIKoZIzj0EAwIw
FDESMBAGA1UEAwwJbG9jYWxob3N0MCAXDTI2MTAyMTE3MDcwMFoYDzIwNTIxMDI0
MTcwNzAwWjAUMRIwEAYDVQQDDAlsb2NhbGhvc3QwWTATBgcqhkjOPQIBBggqhkjO
PQMBBwNCAASSgx6u597+Q9wK7TmEijx1E/BYiSOlzz73HLyC4l3aVfxLWR5yT095
JD2qyNZNrHUpO39f0Zsho37nt34nPHowo1MwUTAdBgNVHQ4EFgQUdKikJ4vhyKk9
eqtCym/CnctqSsgwHwYDVR0jBBgwFoAUdKikJ4vhyKk9eqtCym/CnctqSsgwDwYD
VR0TAQH/BAUwAwEB/zAKBggqhkjOPQQDAgNIADBFAiATq0IeBAB2Os11gz4hu1N1
Iu+uW8QAIs92WViR/q+wXAIhAK6RiyCaBy1cwy5eokWzUFKTt82YDlyn1yzP0q4a
vaLy
-----END CERTIFICATE-----
"""


class _Handler(BaseHTTPRequestHandler):
    user_agent = ""
    redirect_to = ""

    def do_GET(self) -> None:
        _Handler.user_agent = self.headers.get("User-Agent", "")
        if self.path == "/redirect":
            self.send_response(301)
            self.send_header("Location", _Handler.redirect_to)
        else:
            self.send_response(int(self.path.strip("/") or 200))
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


def _serve(server: ThreadingHTTPServer) -> Iterator[int]:
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


@pytest.fixture
def http_port() -> Iterator[int]:
    yield from _serve(ThreadingHTTPServer(("127.0.0.1", 0), _Handler))


@pytest.fixture
def https_port(tmp_path: Path) -> Iterator[int]:
    cert = tmp_path / "localhost.pem"
    cert.write_text(CERT_UTC_TIME + CERT_UTC_TIME_KEY)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    yield from _serve(server)


@pytest.mark.parametrize(
    ("pem", "expected"),
    [
        (CERT_UTC_TIME, CERT_UTC_TIME_EXPIRY),
        (CERT_GENERALIZED_TIME, datetime(2052, 10, 24, 17, 7, tzinfo=UTC)),
    ],
    ids=["utc_time", "generalized_time"],
)
def test_cert_expiry_is_read_from_raw_certificate(pem: str, expected: datetime):
    assert _cert_not_after(ssl.PEM_cert_to_DER_cert(pem)) == expected


@pytest.mark.parametrize(
    ("server", "ssl_check", "expected"),
    [
        ("example.com", True, "https://example.com"),
        ("example.com", False, "http://example.com"),
        ("example.com:8443", True, "https://example.com:8443"),
        (
            "localhost:8080/health?next=https://example.com",
            False,
            "http://localhost:8080/health?next=https://example.com",
        ),
        ("[::1]:8080/health", False, "http://[::1]:8080/health"),
        ("http://192.168.1.5:8080", True, "http://192.168.1.5:8080"),
        ("https://example.com", False, "https://example.com"),
    ],
)
def test_url_keeps_its_own_scheme(server: str, ssl_check: bool, expected: str):
    assert _build_url(server, ssl_check) == expected


@pytest.mark.parametrize(
    ("server", "ssl_check"),
    [
        ("http://127.0.0.1:{port}", True),
        ("127.0.0.1:{port}", False),
    ],
)
def test_http_server_on_custom_port_is_online(http_port: int, server: str, ssl_check: bool):
    status = check_server("Local server", server.format(port=http_port), True, ssl_check, 5)

    assert status["status"] == "Online"
    assert status["response_code"] == 200
    assert status["url"] == f"http://127.0.0.1:{http_port}"
    assert status["ssl"] is None


@pytest.mark.parametrize(("code", "expected"), [(404, "Online"), (500, "Offline")])
def test_only_server_errors_count_as_offline(http_port: int, code: int, expected: str):
    status = check_server("Local server", f"http://127.0.0.1:{http_port}/{code}", True, True, 5)

    assert status["status"] == expected
    assert status["response_code"] == code


def test_closed_port_is_offline():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    status = check_server("Local server", f"http://127.0.0.1:{port}", True, True, 1)

    assert status["status"] == "Offline"
    assert status["response_code"] is None


def test_ipv6_loopback_with_a_custom_port():
    class IPv6Server(ThreadingHTTPServer):
        address_family = socket.AF_INET6

    try:
        server = IPv6Server(("::1", 0), _Handler)
    except OSError as exc:
        pytest.skip(f"IPv6 loopback is unavailable: {exc}")

    for port in _serve(server):
        status = check_server("Local server", f"http://[::1]:{port}/200", True, True, 2)
        assert status["status"] == "Online"
        assert status["response_code"] == 200


def test_request_does_not_send_python_user_agent(http_port: int):
    check_server("Local server", f"http://127.0.0.1:{http_port}", True, True, 5)

    assert _Handler.user_agent
    assert not _Handler.user_agent.startswith("Python-urllib")


def test_self_signed_cert_shows_ssl_days_without_verify(https_port: int):
    status = check_server("Local server", f"127.0.0.1:{https_port}", False, True, 5)

    assert status["status"] == "Online"
    assert status["url"] == f"https://127.0.0.1:{https_port}"
    assert status["ssl"] == (CERT_UTC_TIME_EXPIRY - datetime.now(UTC)).days


def test_self_signed_cert_is_offline_with_verify(https_port: int):
    status = check_server("Local server", f"127.0.0.1:{https_port}", True, True, 5)

    assert status["status"] == "Offline"
    assert status["ssl"] is None


def test_ssl_check_off_skips_ssl_days(https_port: int):
    status = check_server("Local server", f"https://127.0.0.1:{https_port}", False, False, 5)

    assert status["status"] == "Online"
    assert status["ssl"] is None


def test_http_url_redirected_to_https_skips_ssl_days(http_port: int, https_port: int):
    _Handler.redirect_to = f"https://127.0.0.1:{https_port}/"

    status = check_server("Local server", f"http://127.0.0.1:{http_port}/redirect", False, True, 5)

    assert status["status"] == "Online"
    assert status["response_code"] == 200
    assert status["ssl"] is None


def test_qml_widgets_share_checks_and_offline_toasts(
    qapp: QGuiApplication, http_port: int, monkeypatch: pytest.MonkeyPatch
):
    messages: list[str] = []
    threads: list[int] = []
    main_thread = threading.get_ident()
    check_started = threading.Event()
    resume_check = threading.Event()

    class Toast:
        def show(self, _icon: str, title: str, message: str) -> None:
            assert title == "Server Monitor"
            assert threading.get_ident() == main_thread
            messages.append(message)

    def check(name: str, url: str, ssl_verify: bool, ssl_check: bool, timeout: int):
        threads.append(threading.get_ident())
        check_started.set()
        if not resume_check.wait(5):
            raise RuntimeError("Test timed out waiting to resume the check")
        return check_server(name, url, ssl_verify, ssl_check, timeout)

    monkeypatch.setattr(service, "ToastNotifier", Toast)
    monkeypatch.setattr(service, "check_server", check)
    monkeypatch.setattr(service, "_network_disconnected", lambda: True)
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    path = find_widget_file("ServerMonitor")
    assert path is not None
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
    options: dict[str | None, Any] = {
        "servers": [
            {"name": "Invalid port", "url": "http://localhost:invalid"},
            {"name": "Local server", "url": f"http://localhost:{http_port}"},
            f"http://127.0.0.1:{http_port}/500",
        ],
        "notifyOffline": True,
        "timeout": 1,
    }
    first = component.createWithInitialProperties(options)
    second = component.createWithInitialProperties(options)
    assert isinstance(first, QQuickItem) and isinstance(second, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    try:
        for _ in range(100):
            if check_started.is_set():
                break
            wait(20)
        assert check_started.is_set()
        popup = first.findChild(QObject, "menu")
        assert popup is not None and popup.property("reveal") == 0
        QMetaObject.invokeMethod(first, "togglePopup")
        wait(220)
        assert popup.property("reveal") == 1
        window = next(
            window for window in qapp.topLevelWindows() if window.title() == "Server Monitor" and window.isVisible()
        )
        assert isinstance(window, QQuickWindow)
        content = window.contentItem()
        assert content is not None
        loading_bar = find_item(content, "loadingBar")
        assert loading_bar is not None and loading_bar.isVisible()

        resume_check.set()
        for _ in range(250):
            if first.property("results") and second.property("results"):
                break
            wait(20)
        assert first.property("summary") == "1 online · 2 offline", first.property("results")
        assert second.property("summary") == first.property("summary")
        assert len(threads) == 3 and main_thread not in threads
        assert messages == ["2 server(s) are offline"]
        assert not loading_bar.isVisible()
        row = find_item(content, "serverRow1")
        assert row is not None and row.height() > 0
        checked = find_item(content, "checked")
        assert checked is not None and checked.property("text").startswith("Checked at ")
        QMetaObject.invokeMethod(first, "togglePopup")
        assert popup.property("closing") and window.isVisible()
        wait(220)
        assert popup.property("reveal") == 0 and not window.isVisible()
    finally:
        resume_check.set()
        sip.delete(first)
        sip.delete(second)
