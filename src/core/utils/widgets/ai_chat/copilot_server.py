"""
Copilot CLI server management for AI Chat widget.
"""

import atexit
import logging
import os
import subprocess
import threading
from typing import Any

_CLI_SERVER_PROCESSES: dict[int, subprocess.Popen] = {}  # port -> process
_CLI_SERVER_LOCK = threading.Lock()
_ACTIVE_CLIENTS: list = []


def _build_hidden_console_args() -> dict[str, Any]:
    if os.name != "nt" or not hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {}
    creationflags = subprocess.CREATE_NO_WINDOW
    startupinfo = None
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        if hasattr(subprocess, "STARTF_USESHOWWINDOW"):
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    kwargs: dict[str, Any] = {"creationflags": creationflags}
    if startupinfo is not None:
        kwargs["startupinfo"] = startupinfo
    return kwargs


def _normalize_url(cli_url: str | None) -> str | None:
    if not cli_url:
        return None
    value = cli_url.strip()
    if not value:
        return None
    if value.startswith("http://"):
        value = value.removeprefix("http://")
    elif value.startswith("https://"):
        value = value.removeprefix("https://")
    return value


def _parse_url(cli_url: str) -> tuple[str, int] | None:
    if not cli_url:
        return None
    parts = cli_url.split(":")
    if len(parts) != 2:
        return None
    host = parts[0] or "localhost"
    try:
        port = int(parts[1])
    except ValueError:
        return None
    if port <= 0 or port > 65535:
        return None
    return (host, port)


def copilot_cli_server(cli_url: str | None) -> str | None:
    normalized = _normalize_url(cli_url)
    if not normalized:
        return None

    parsed = _parse_url(normalized)
    if not parsed:
        logging.warning("Copilot CLI URL is invalid: %s", normalized)
        return normalized

    host, port = parsed
    if host not in {"localhost", "127.0.0.1"}:
        return normalized

    with _CLI_SERVER_LOCK:
        # Check if server for this port is already running
        existing = _CLI_SERVER_PROCESSES.get(port)
        if existing is not None and existing.poll() is None:
            return normalized

        cli_path = os.environ.get("COPILOT_CLI_PATH", "copilot")
        args = [cli_path, "--server", "--log-level", "info", "--port", str(port)]
        try:
            process = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=dict(os.environ),
                **_build_hidden_console_args(),
            )
            _CLI_SERVER_PROCESSES[port] = process
        except Exception as exc:
            logging.error("Failed to start Copilot CLI server on port %d: %s", port, exc)

    return normalized


def register_client(client) -> None:
    """Register an active Copilot client for cleanup on shutdown."""
    if client not in _ACTIVE_CLIENTS:
        _ACTIVE_CLIENTS.append(client)


def unregister_client(client) -> None:
    """Unregister a Copilot client."""
    if client in _ACTIVE_CLIENTS:
        _ACTIVE_CLIENTS.remove(client)


def shutdown_server() -> None:
    # Close all active clients first to prevent connection reset errors
    for client in list(_ACTIVE_CLIENTS):
        try:
            client.close()
        except Exception:
            pass
    _ACTIVE_CLIENTS.clear()

    with _CLI_SERVER_LOCK:
        for port, process in list(_CLI_SERVER_PROCESSES.items()):
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=3)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        _CLI_SERVER_PROCESSES.clear()


atexit.register(shutdown_server)
