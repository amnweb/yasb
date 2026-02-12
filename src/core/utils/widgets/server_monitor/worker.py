import logging
import socket
import ssl
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

from PyQt6.QtCore import QThread, pyqtSignal

from settings import DEBUG


class ServerCheckWorker(QThread):
    status_updated = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.servers: list[str] = []
        self.ssl_check: bool = True
        self.ssl_verify: bool = True
        self.timeout: int = 5
        self.running = True

    def set_servers(self, servers: list[str], ssl_verify: bool, ssl_check: bool, timeout: int) -> None:
        self.servers = servers
        self.ssl_check = ssl_check
        self.ssl_verify = ssl_verify
        self.timeout = timeout

    def stop(self) -> None:
        self.running = False
        self.wait()

    def run(self) -> None:
        if not self.running:
            return

        server_statuses: list[dict] = []

        for server in self.servers:
            if not self.running:
                break

            status = self.check_single_server(server, self.ssl_verify, self.ssl_check, self.timeout)
            server_statuses.append(status)

        self.status_updated.emit(server_statuses)

    def check_single_server(self, server: str, ssl_verify: bool, ssl_check: bool, timeout: int) -> dict:
        ping_result = self.ping_server(server, ssl_verify, ssl_check, timeout)
        if DEBUG:
            logging.debug(f"Server: {server} - {ping_result}")
        return {
            "name": server,
            "ssl": ping_result["ssl"],
            "response_time": f"{ping_result['response_time']}ms" if ping_result["response_time"] else None,
            "response_code": ping_result["response_code"],
            "status": ping_result["status"],
        }

    def ping_server(self, server: str, ssl_verify: bool, ssl_check: bool, timeout: int) -> dict:
        """Check server availability and collect status information."""
        http_status = None
        response_time = None
        final_hostname = server
        url = f"https://{server}" if ssl_check else f"http://{server}"

        # Configure SSL context if needed
        context = ssl.create_default_context() if not ssl_verify else None
        if context:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        try:
            start_time = datetime.now()
            request = urllib.request.Request(url, method="GET")

            try:
                with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                    http_status = response.status
                    parsed_url = urlparse(response.url)
                    final_hostname = parsed_url.netloc or server
            except urllib.error.HTTPError as e:
                http_status = e.code

            if http_status is not None:
                response_time = int((datetime.now() - start_time).total_seconds() * 1000)

        except OSError:
            pass

        status = "Online" if http_status is not None and http_status < 500 else "Offline"

        # Only attempt SSL expiry checks when online.
        ssl_days = self.check_ssl_expiry(final_hostname, timeout) if (ssl_check and status == "Online") else None

        return {"status": status, "response_time": response_time, "response_code": http_status, "ssl": ssl_days}

    def check_ssl_expiry(self, hostname: str, timeout: int) -> int | None:
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    exp_date = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
                    return (exp_date - datetime.now()).days
        except OSError:
            return None
