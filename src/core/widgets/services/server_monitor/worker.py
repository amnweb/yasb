import http.client
import logging
import socket
import ssl
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any, override
from urllib.parse import urlsplit

from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger("server_monitor")

_DER_EXPLICIT_VERSION = 0xA0
_DER_UTC_TIME = 0x17


def _build_url(server: str, ssl_check: bool) -> str:
    if "://" in server:
        return server
    return f"{'https' if ssl_check else 'http'}://{server}"


def _ssl_context(verify: bool) -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    if not verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _read_tlv(data: bytes, pos: int) -> tuple[int, int, int]:
    tag = data[pos]
    length = data[pos + 1]
    pos += 2
    if length & 0x80:
        size = length & 0x7F
        length = int.from_bytes(data[pos : pos + size], "big")
        pos += size
    return tag, pos, pos + length


def _cert_not_after(der: bytes) -> datetime:
    _, pos, _ = _read_tlv(der, 0)
    _, pos, _ = _read_tlv(der, pos)
    tag, _, end = _read_tlv(der, pos)
    if tag == _DER_EXPLICIT_VERSION:
        pos = end
    # X.509 TBSCertificate: serialNumber, signature, issuer, then validity (notBefore, notAfter)
    for _ in range(3):
        _, _, pos = _read_tlv(der, pos)
    _, pos, _ = _read_tlv(der, pos)
    _, _, pos = _read_tlv(der, pos)
    tag, start, end = _read_tlv(der, pos)
    fmt = "%y%m%d%H%M%SZ" if tag == _DER_UTC_TIME else "%Y%m%d%H%M%SZ"
    return datetime.strptime(der[start:end].decode("ascii"), fmt).replace(tzinfo=UTC)


class ServerCheckWorker(QThread):
    status_updated = pyqtSignal(list)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.servers: list[dict[str, Any]] = []
        self.ssl_check: bool = True
        self.ssl_verify: bool = True
        self.timeout: int = 5
        self.running = True

    def set_servers(self, servers: list[dict[str, Any]], ssl_verify: bool, ssl_check: bool, timeout: int) -> None:
        self.servers = servers
        self.ssl_check = ssl_check
        self.ssl_verify = ssl_verify
        self.timeout = timeout

    def stop(self) -> None:
        self.running = False
        self.wait(2000)

    def _has_internet(self) -> bool:
        """Check if internet is available."""
        test_servers = [
            ("8.8.8.8", 53),  # Google DNS
            ("1.1.1.1", 53),  # Cloudflare DNS
        ]
        for host, port in test_servers:
            try:
                sock = socket.create_connection((host, port), timeout=3)
                sock.close()
                return True
            except OSError:
                continue
        return False

    @override
    def run(self) -> None:
        if not self.running:
            return

        if not self._has_internet():
            logger.warning("No internet connection detected, skipping server checks")
            server_statuses: list[dict[str, Any]] = [
                {
                    "url": _build_url(s["url"], self.ssl_check),
                    "name": s["name"],
                    "status": "Offline",
                    "response_time": None,
                    "response_code": None,
                    "ssl": None,
                    "no_internet": True,
                }
                for s in self.servers
            ]
            self.status_updated.emit(server_statuses)
            return

        server_statuses = []

        for server in self.servers:
            if not self.running:
                break

            status = self.check_single_server(server["url"], self.ssl_verify, self.ssl_check, self.timeout)
            status["name"] = server["name"]
            server_statuses.append(status)

        self.status_updated.emit(server_statuses)

    def check_single_server(self, server: str, ssl_verify: bool, ssl_check: bool, timeout: int) -> dict[str, Any]:
        url = _build_url(server, ssl_check)
        ping_result = self.ping_server(url, ssl_verify, ssl_check, timeout)

        return {
            "url": url,
            "ssl": ping_result["ssl"],
            "response_time": f"{ping_result['response_time']}ms" if ping_result["response_time"] else None,
            "response_code": ping_result["response_code"],
            "status": ping_result["status"],
            "no_internet": ping_result.get("no_internet", False),
        }

    def ping_server(self, url: str, ssl_verify: bool, ssl_check: bool, timeout: int) -> dict[str, Any]:
        """Check server availability and collect status information."""
        http_status = None
        response_time = None
        final_url = url
        context = _ssl_context(ssl_verify)

        try:
            start_time = datetime.now()
            request = urllib.request.Request(url, method="GET", headers={"User-Agent": "YASB Server Monitor"})

            try:
                with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                    http_status = response.status
                    final_url = response.url
            except urllib.error.HTTPError as e:
                http_status = e.code
                final_url = e.url

            if http_status is not None:
                response_time = int((datetime.now() - start_time).total_seconds() * 1000)

        except OSError as e:
            reason = str(e).lower()
            if "getaddrinfo" in reason or "name or service not known" in reason:
                logger.debug("Server '%s' is unreachable", url)
                return {
                    "status": "Offline",
                    "response_time": None,
                    "response_code": None,
                    "ssl": None,
                    "no_internet": True,
                }
            elif "timed out" in reason:
                logger.debug("Server '%s' is unreachable: connection timed out", url)
            else:
                logger.debug("Server '%s' is unreachable: connection failed", url)
        except ValueError, http.client.HTTPException:
            logger.debug("Server '%s' is unreachable: invalid URL or response", url)

        status = "Online" if http_status is not None and http_status < 500 else "Offline"

        # Only attempt SSL expiry checks when online.
        ssl_days = None
        final = urlsplit(final_url)
        if ssl_check and status == "Online" and urlsplit(url).scheme == "https" and final.hostname:
            ssl_days = self.check_ssl_expiry(final.hostname, final.port or 443, ssl_verify, timeout)

        return {
            "status": status,
            "response_time": response_time,
            "response_code": http_status,
            "ssl": ssl_days,
            "no_internet": False,
        }

    def check_ssl_expiry(self, hostname: str, port: int, ssl_verify: bool, timeout: int) -> int | None:
        try:
            context = _ssl_context(ssl_verify)
            with socket.create_connection((hostname, port), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    der = ssock.getpeercert(binary_form=True)
            if not der:
                return None
            return (_cert_not_after(der) - datetime.now(UTC)).days
        except OSError as e:
            reason = str(e).lower()
            if "getaddrinfo" in reason or "name or service not known" in reason:
                logger.debug("SSL check skipped for '%s'", hostname)
            else:
                logger.debug("SSL check failed for '%s': connection error", hostname)
            return None
        except ValueError, IndexError:
            logger.debug("SSL check failed for '%s': unreadable certificate", hostname)
            return None
