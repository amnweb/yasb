# pyright: reportPrivateUsage=false

import socket
import ssl
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from core.widgets.services.server_monitor.worker import ServerCheckWorker, _build_url, _cert_not_after

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
def worker(qapp: QApplication) -> ServerCheckWorker:
    return ServerCheckWorker()


@pytest.fixture
def http_port() -> Iterator[int]:
    yield from _serve(ThreadingHTTPServer(("127.0.0.1", 0), _Handler))


@pytest.fixture
def https_port(tmp_path: Path) -> Iterator[int]:
    cert = tmp_path / "localhost.pem"
    cert.write_text(CERT_UTC_TIME + CERT_UTC_TIME_KEY)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
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
def test_http_server_on_custom_port_is_online(worker: ServerCheckWorker, http_port: int, server: str, ssl_check: bool):
    status = worker.check_single_server(server.format(port=http_port), True, ssl_check, 5)

    assert status["status"] == "Online"
    assert status["response_code"] == 200
    assert status["url"] == f"http://127.0.0.1:{http_port}"
    assert status["ssl"] is None


@pytest.mark.parametrize(("code", "expected"), [(404, "Online"), (500, "Offline")])
def test_only_server_errors_count_as_offline(worker: ServerCheckWorker, http_port: int, code: int, expected: str):
    status = worker.check_single_server(f"http://127.0.0.1:{http_port}/{code}", True, True, 5)

    assert status["status"] == expected
    assert status["response_code"] == code


def test_closed_port_is_offline(worker: ServerCheckWorker):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    status = worker.check_single_server(f"http://127.0.0.1:{port}", True, True, 1)

    assert status["status"] == "Offline"
    assert status["response_code"] is None


def test_request_does_not_send_python_user_agent(worker: ServerCheckWorker, http_port: int):
    worker.check_single_server(f"http://127.0.0.1:{http_port}", True, True, 5)

    assert _Handler.user_agent
    assert not _Handler.user_agent.startswith("Python-urllib")


def test_self_signed_cert_shows_ssl_days_without_verify(worker: ServerCheckWorker, https_port: int):
    status = worker.check_single_server(f"127.0.0.1:{https_port}", False, True, 5)

    assert status["status"] == "Online"
    assert status["url"] == f"https://127.0.0.1:{https_port}"
    assert status["ssl"] == (CERT_UTC_TIME_EXPIRY - datetime.now(UTC)).days


def test_self_signed_cert_is_offline_with_verify(worker: ServerCheckWorker, https_port: int):
    status = worker.check_single_server(f"127.0.0.1:{https_port}", True, True, 5)

    assert status["status"] == "Offline"
    assert status["ssl"] is None


def test_ssl_check_off_skips_ssl_days(worker: ServerCheckWorker, https_port: int):
    status = worker.check_single_server(f"https://127.0.0.1:{https_port}", False, False, 5)

    assert status["status"] == "Online"
    assert status["ssl"] is None


def test_http_url_redirected_to_https_skips_ssl_days(worker: ServerCheckWorker, http_port: int, https_port: int):
    _Handler.redirect_to = f"https://127.0.0.1:{https_port}/"

    status = worker.check_single_server(f"http://127.0.0.1:{http_port}/redirect", False, True, 5)

    assert status["status"] == "Online"
    assert status["response_code"] == 200
    assert status["ssl"] is None
