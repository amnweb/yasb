import http.client
import logging
import re
import socket
import ssl
import urllib.error
import urllib.request
from datetime import UTC, datetime
from time import perf_counter
from typing import TypedDict
from urllib.parse import urlsplit

logger = logging.getLogger("server_monitor")

_DER_EXPLICIT_VERSION = 0xA0
_DER_UTC_TIME = 0x17
_EXPLICIT_SCHEME = re.compile(r"^[a-z][a-z\d+.-]*://", re.IGNORECASE)


class ServerStatus(TypedDict):
    url: str
    name: str
    status: str
    response_time: int | None
    response_code: int | None
    ssl: int | None


def _build_url(server: str, ssl_check: bool) -> str:
    server = server.strip()
    if _EXPLICIT_SCHEME.match(server):
        return server
    return f"{'https' if ssl_check else 'http'}://{server.removeprefix('//')}"


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


def check_server(name: str, server: str, ssl_verify: bool, ssl_check: bool, timeout: int) -> ServerStatus:
    url = _build_url(server, ssl_check)
    result: ServerStatus = {
        "url": url,
        "name": name,
        "status": "Offline",
        "response_time": None,
        "response_code": None,
        "ssl": None,
    }
    try:
        target = urlsplit(url)
        if target.scheme not in ("http", "https") or not target.hostname:
            raise ValueError("Expected an HTTP or HTTPS URL with a host")
        if target.port == 0:
            raise ValueError("Port must be between 1 and 65535")
        context = _ssl_context(ssl_verify)
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": "YASB Server Monitor"})
        start = perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                code, final_url = response.getcode(), response.geturl()
        except urllib.error.HTTPError as response:
            with response:
                code, final_url = response.code, response.url
    except (OSError, ValueError, http.client.HTTPException) as exc:
        logger.debug("Server '%s' is unreachable: %s", url, exc)
        return result

    if code is None:
        return result
    result["response_time"] = int((perf_counter() - start) * 1000)
    result["response_code"] = code
    if code < 500:
        result["status"] = "Online"
        if ssl_check and target.scheme == "https":
            result["ssl"] = _check_ssl_expiry(final_url, context, timeout)
    return result


def _check_ssl_expiry(url: str, context: ssl.SSLContext, timeout: int) -> int | None:
    try:
        target = urlsplit(url)
        if target.scheme != "https" or not target.hostname:
            return None
        with socket.create_connection((target.hostname, target.port or 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=target.hostname) as ssock:
                der = ssock.getpeercert(binary_form=True)
        if der:
            return (_cert_not_after(der) - datetime.now(UTC)).days
    except (OSError, ValueError, IndexError) as exc:
        logger.debug("SSL check failed for '%s': %s", url, exc)
    return None
