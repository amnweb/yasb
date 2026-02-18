import ctypes
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass

from PyQt6.QtWidgets import QApplication

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_PORT
from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.constants import PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_TERMINATE, TH32CS_SNAPPROCESS
from core.utils.win32.structs import PROCESSENTRY32

_DEFAULT_APP_ICON_PNG: str | None = None


def _get_quick_launch_icons_dir() -> str:
    icons_dir = os.path.join(tempfile.gettempdir(), "yasb_quick_launch_icons")
    try:
        os.makedirs(icons_dir, exist_ok=True)
    except Exception:
        pass
    return icons_dir


def _get_default_app_icon_png() -> str:
    """Return a cached default Windows application icon PNG path, or ""."""

    global _DEFAULT_APP_ICON_PNG
    if _DEFAULT_APP_ICON_PNG is not None:
        return _DEFAULT_APP_ICON_PNG

    try:
        import win32api
        import win32con
        import win32gui

        from core.utils.win32.app_icons import hicon_to_image

        icons_dir = _get_quick_launch_icons_dir()
        default_png = os.path.join(icons_dir, "_default_app.png")
        if os.path.isfile(default_png):
            _DEFAULT_APP_ICON_PNG = default_png
            return default_png

        size = win32api.GetSystemMetrics(win32con.SM_CXICON)
        hicon = win32gui.LoadImage(0, win32con.IDI_APPLICATION, win32con.IMAGE_ICON, size, size, win32con.LR_SHARED)
        if hicon:
            img = hicon_to_image(hicon)
            if img is not None:
                img.save(default_png, format="PNG")
                _DEFAULT_APP_ICON_PNG = default_png
                return default_png
    except Exception:
        pass

    _DEFAULT_APP_ICON_PNG = ""
    return ""


def _get_process_exe_path(pid: int) -> str:
    """Return full exe path for PID using QueryFullProcessImageNameW, or ""."""

    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return ""
    try:
        size = ctypes.c_ulong(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return str(buf.value)
    except Exception:
        return ""
    finally:
        kernel32.CloseHandle(h)
    return ""


def _safe_filename_stem(value: str) -> str:
    stem = value.strip().strip(".")
    if not stem:
        return "icon"
    # Windows-safe-ish: replace most common invalid characters.
    for ch in '<>:"/\\|?*':
        stem = stem.replace(ch, "_")
    return stem


def _get_cached_exe_icon_png(exe_path: str) -> str:
    """Extract and cache an exe icon to PNG. Returns PNG path or ""."""

    exe_path = (exe_path or "").strip()
    if not exe_path or not os.path.isfile(exe_path):
        return ""

    try:
        import hashlib

        import win32gui

        from core.utils.win32.app_icons import hicon_to_image

        icons_dir = _get_quick_launch_icons_dir()
        path_hash = hashlib.md5(exe_path.lower().encode("utf-8", errors="ignore")).hexdigest()[:10]
        base = _safe_filename_stem(os.path.splitext(os.path.basename(exe_path))[0])
        cached_png = os.path.join(icons_dir, f"{base}_{path_hash}_0.png")
        if os.path.isfile(cached_png):
            return cached_png

        # ExtractIconEx returns ([large...], [small...])
        large, small = win32gui.ExtractIconEx(exe_path, 0, 1)
        hicon = 0
        if large:
            hicon = large[0]
        elif small:
            hicon = small[0]
        if not hicon:
            return ""

        try:
            img = hicon_to_image(hicon)
            if img is None:
                return ""
            try:
                img.save(cached_png, format="PNG")
            except Exception:
                return ""
            return cached_png
        finally:
            try:
                if large:
                    for hi in large:
                        win32gui.DestroyIcon(hi)
                if small:
                    for hi in small:
                        win32gui.DestroyIcon(hi)
            except Exception:
                pass
    except Exception:
        return ""


@dataclass(frozen=True)
class _NetstatEntry:
    protocol: str  # tcp/udp
    local: str
    local_port: int | None
    foreign: str
    foreign_port: int | None
    state: str
    pid: int | None


def _terminate_process(pid: int) -> bool:
    h = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not h:
        return False
    try:
        return bool(kernel32.TerminateProcess(h, 1))
    finally:
        kernel32.CloseHandle(h)


def _enumerate_processes() -> dict[int, str]:
    """Return {pid: exe_name} for all running processes."""

    proc_map: dict[int, str] = {}
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == ctypes.wintypes.HANDLE(-1).value:
        return proc_map
    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return proc_map
        while True:
            proc_map[int(entry.th32ProcessID)] = str(entry.szExeFile)
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return proc_map


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
            logging.debug(f"Port Viewer: netstat failed: {e}")
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

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._tcp_listening_only: bool = bool(self.config.get("tcp_listening_only", True))
        self._include_established: bool = bool(self.config.get("include_established", False))

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query_raw = self.get_query_text(text)
        query = query_raw.strip()
        if not query:
            return [
                ProviderResult(
                    title="Port Viewer",
                    description="e.g. pv 80, pv tcp 443, pv chrome, pv kill 80",
                    icon_char=ICON_PORT,
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
            pid_to_name = _enumerate_processes()
        except Exception as e:
            logging.debug(f"Port Viewer: process enumeration failed: {e}")
            pid_to_name = {}

        pid_to_icon: dict[int, str] = {}

        entries = _read_netstat()
        if not entries:
            return [
                ProviderResult(
                    title="No ports found",
                    description="netstat returned no results or failed to run",
                    icon_char=ICON_PORT,
                    provider=self.name,
                )
            ]

        results: list[ProviderResult] = []

        default_icon = _get_default_app_icon_png()

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

                icon_path = default_icon
                if pid is not None and pid > 0:
                    if pid not in pid_to_icon:
                        exe_path = _get_process_exe_path(pid)
                        pid_to_icon[pid] = _get_cached_exe_icon_png(exe_path) if exe_path else ""
                    icon_path = pid_to_icon.get(pid, "") or default_icon

                results.append(
                    ProviderResult(
                        title=title,
                        description=description,
                        icon_path=icon_path,
                        icon_char="",
                        provider=self.name,
                        action_data={"mode": "kill", "pid": pid, "proc": proc_display},
                    )
                )
            else:
                title = f"{e.protocol.upper()} {e.local}"
                if proc:
                    title += f"  ({proc})"
                desc_bits = []
                if e.state:
                    desc_bits.append(e.state)
                if pid is not None:
                    desc_bits.append(f"PID {pid}")
                if e.foreign and e.foreign != "*:*":
                    desc_bits.append(f"→ {e.foreign}")
                description = ", ".join(desc_bits)
                copy_text = f"{e.protocol.upper()} {e.local} {e.state} PID {pid} {proc}".strip()

                icon_path = default_icon
                if pid is not None and pid > 0:
                    if pid not in pid_to_icon:
                        exe_path = _get_process_exe_path(pid)
                        pid_to_icon[pid] = _get_cached_exe_icon_png(exe_path) if exe_path else ""
                    icon_path = pid_to_icon.get(pid, "") or default_icon

                results.append(
                    ProviderResult(
                        title=title,
                        description=description,
                        icon_path=icon_path,
                        icon_char="",
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
                    icon_char=ICON_PORT,
                    provider=self.name,
                )
            ]

        return results

    def execute(self, result: ProviderResult) -> bool:
        mode = result.action_data.get("mode", "")
        if mode == "copy":
            text = result.action_data.get("text", "")
            try:
                clipboard = QApplication.clipboard()
                if clipboard and text:
                    clipboard.setText(text)
            except Exception as e:
                logging.debug(f"Port Viewer: clipboard copy failed: {e}")
            return False

        if mode == "kill":
            pid = result.action_data.get("pid")
            if pid is None:
                return False
            try:
                ok = _terminate_process(int(pid))
                if ok:
                    logging.info(f"Port Viewer: terminated PID {pid}")
                else:
                    logging.debug(f"Port Viewer: failed to terminate PID {pid}")
            except Exception as e:
                logging.debug(f"Port Viewer: terminate failed: {e}")
            return False

        return False
