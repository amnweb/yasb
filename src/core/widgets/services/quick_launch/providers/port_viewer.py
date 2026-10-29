import logging
import subprocess
from dataclasses import dataclass
from typing import Any

from PyQt6.QtGui import QGuiApplication

from core.utils.icons.service import ProcessIcon
from core.utils.process import terminate_process
from core.utils.win32.bindings.kernel32 import snapshot_processes
from core.widgets.services.quick_launch.base_provider import BaseProvider, ProviderResult
from core.widgets.services.quick_launch.providers.resources.icons import ICON_PORT


@dataclass(frozen=True)
class _NetstatEntry:
    protocol: str  # tcp/udp
    local: str
    local_port: int | None
    foreign: str
    foreign_port: int | None
    state: str
    pid: int | None


def _parse_host_port(endpoint: str) -> tuple[str, int | None]:
    endpoint = endpoint.strip()
    if not endpoint:
        return "", None
    # netstat uses [ipv6]:port for IPv6.
    if endpoint.startswith("[") and "]:" in endpoint:
        try:
            host, port_str = endpoint.rsplit(":", 1)
            return host, int(port_str)
        except Exception:
            return endpoint, None
    # IPv4 and wildcard: 0.0.0.0:80
    if ":" in endpoint:
        try:
            host, port_str = endpoint.rsplit(":", 1)
            return host, int(port_str)
        except Exception:
            return endpoint, None
    return endpoint, None


def _read_netstat() -> list[_NetstatEntry]:
    """Parse `netstat -ano` output."""

    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        # Fallback to default encoding
        try:
            out = subprocess.check_output(
                ["netstat", "-ano"],
                text=True,
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            logging.debug("Port Viewer: netstat failed: %s", e)
            return []

    entries: list[_NetstatEntry] = []
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        if not (line.startswith("TCP") or line.startswith("UDP")):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue

        proto = parts[0].lower()
        if proto == "tcp":
            # TCP local foreign state pid
            if len(parts) < 5:
                continue
            local = parts[1]
            foreign = parts[2]
            state = parts[3]
            pid_str = parts[4]
        else:
            # UDP local foreign pid
            local = parts[1]
            foreign = parts[2]
            state = ""
            pid_str = parts[3]

        _host, port = _parse_host_port(local)
        _f_host, f_port = _parse_host_port(foreign)
        try:
            pid = int(pid_str)
        except Exception:
            pid = None

        entries.append(
            _NetstatEntry(
                protocol=proto,
                local=local,
                local_port=port,
                foreign=foreign,
                foreign_port=f_port,
                state=state,
                pid=pid,
            )
        )

    return entries


class PortViewerProvider(BaseProvider):
    """View TCP/UDP ports (netstat) and optionally kill owning processes."""

    name = "port_viewer"
    display_name = "Port Viewer"
    input_placeholder = "Search open ports..."
    icon = ICON_PORT

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._tcp_listening_only: bool = bool(self.config.get("tcp_listening_only", True))
        self._include_established: bool = bool(self.config.get("include_established", False))

    def get_results(self, text: str, **kwargs: Any) -> list[ProviderResult]:
        query_raw = self.get_query_text(text)
        query = query_raw.strip()
        if not query:
            return [
                ProviderResult(
                    title="Port Viewer",
                    description="e.g. pv 80, pv tcp 443, pv chrome, pv kill 80",
                    icon_path=ICON_PORT,
                    provider=self.name,
                )
            ]

        tokens = [t for t in query.split() if t]
        tokens_lower = [t.lower() for t in tokens]

        kill_mode = False
        if tokens_lower and tokens_lower[0] in {"kill", "k"}:
            kill_mode = True
            tokens = tokens[1:]
            tokens_lower = tokens_lower[1:]

        proto = "all"
        if tokens_lower and tokens_lower[0] in {"tcp", "udp", "all"}:
            proto = tokens_lower[0]
            tokens = tokens[1:]
            tokens_lower = tokens_lower[1:]

        port_filter: int | None = None
        port_query: str | None = None
        pid_filter: int | None = None
        name_filter = ""

        # If kill_mode and first token is numeric, accept either PID or port.
        # If not kill_mode, numeric implies port.
        if tokens_lower:
            first = tokens_lower[0]
            if first.isdigit():
                val = int(first)
                if kill_mode:
                    # Heuristic: treat 1..65535 as port, otherwise as PID.
                    if 1 <= val <= 65535:
                        port_filter = val
                    elif val > 65535:
                        pid_filter = val
                else:
                    if 0 <= val <= 65535:
                        port_query = first
                tokens = tokens[1:]
                tokens_lower = tokens_lower[1:]

        if tokens_lower:
            name_filter = " ".join(tokens_lower).strip()

        try:
            pid_to_name = {process.pid: process.exe for process in snapshot_processes()}
        except Exception as e:
            logging.debug("Port Viewer: process enumeration failed: %s", e)
            pid_to_name = {}

        entries = _read_netstat()
        if not entries:
            return [
                ProviderResult(
                    title="No ports found",
                    description="netstat returned no results or failed to run",
                    icon_path=ICON_PORT,
                    provider=self.name,
                )
            ]

        results: list[ProviderResult] = []

        for e in entries:
            if proto != "all" and e.protocol != proto:
                continue

            # kill mode should include connected TCP rows so users can find a process by remote port too.
            # When filtering by name, show all connections (not just LISTENING).
            effective_include_established = self._include_established or bool(name_filter) or kill_mode
            effective_tcp_listening_only = self._tcp_listening_only and not name_filter

            if e.protocol == "tcp" and effective_tcp_listening_only and not effective_include_established:
                if e.state.upper() != "LISTENING":
                    continue
            if e.protocol == "tcp" and not effective_include_established and effective_tcp_listening_only is False:
                # If user explicitly wants non-listening TCP rows but doesn't include established, keep LISTENING only.
                if e.state and e.state.upper() != "LISTENING":
                    continue

            if pid_filter is not None and e.pid != pid_filter:
                continue
            # Port filtering:
            # - kill mode uses strict equality (safety)
            # - normal mode uses substring matching on the local port digits
            if port_filter is not None:
                # kill mode is strict equality (safety), but allow matching the foreign TCP port too.
                if e.local_port != port_filter:
                    if not (kill_mode and e.protocol == "tcp" and e.foreign_port == port_filter):
                        continue
            if port_query is not None:
                if e.local_port is None:
                    continue
                if port_query not in str(e.local_port):
                    continue

            pid = e.pid
            proc = pid_to_name.get(pid, "") if pid is not None else ""
            proc_display = proc or (f"PID {pid}" if pid is not None else "PID ?")

            if name_filter:
                hay = f"{proc_display} {e.local} {e.foreign} {e.protocol} {e.state}".lower()
                if name_filter not in hay:
                    continue

            if kill_mode:
                title = f"Kill {proc_display}"
                desc_bits = [e.protocol.upper(), e.local]
                if e.state:
                    desc_bits.append(e.state)
                if pid is not None:
                    desc_bits.append(f"PID {pid}")
                description = ", ".join(desc_bits)

                results.append(
                    ProviderResult(
                        title=title,
                        description=description,
                        icon_path="" if pid else ICON_PORT,
                        icon_source=ProcessIcon(pid) if pid else None,
                        provider=self.name,
                        action_data={"mode": "kill", "pid": pid, "proc": proc_display},
                    )
                )
            else:
                title = f"{e.protocol.upper()} {e.local}"
                if proc:
                    title += f"  ({proc})"
                desc_bits: list[str] = []
                if e.state:
                    desc_bits.append(e.state)
                if pid is not None:
                    desc_bits.append(f"PID {pid}")
                if e.foreign and e.foreign != "*:*":
                    desc_bits.append(f"-> {e.foreign}")
                description = ", ".join(desc_bits)
                copy_text = f"{e.protocol.upper()} {e.local} {e.state} PID {pid} {proc}".strip()

                results.append(
                    ProviderResult(
                        title=title,
                        description=description,
                        icon_path="" if pid else ICON_PORT,
                        icon_source=ProcessIcon(pid) if pid else None,
                        provider=self.name,
                        action_data={"mode": "copy", "text": copy_text},
                    )
                )

            if len(results) >= self.max_results:
                break

        if not results:
            return [
                ProviderResult(
                    title="No matching ports",
                    description="Try: pv 80, pv tcp 443, pv chrome, pv kill 80",
                    icon_path=ICON_PORT,
                    provider=self.name,
                )
            ]

        return results

    def execute(self, result: ProviderResult) -> bool:
        mode = result.action_data.get("mode", "")
        if mode == "copy":
            text = result.action_data.get("text", "")
            try:
                clipboard = QGuiApplication.clipboard()
                if clipboard and text:
                    clipboard.setText(text)
            except Exception as e:
                logging.debug("Port Viewer: clipboard copy failed: %s", e)
            return False

        if mode == "kill":
            pid = result.action_data.get("pid")
            if pid is None:
                return False
            try:
                ok = terminate_process(int(pid))
                if ok:
                    logging.info("Port Viewer: terminated PID %s", pid)
                else:
                    logging.debug("Port Viewer: failed to terminate PID %s", pid)
            except Exception as e:
                logging.debug("Port Viewer: terminate failed: %s", e)
            return False

        return False
