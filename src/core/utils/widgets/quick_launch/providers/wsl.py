import logging
import re
import subprocess
import threading
from typing import Any

from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import (
    ICON_WARNING,
    ICON_WSL,
    ICON_WSL_ONLINE,
    ICON_WSL_RUNNING,
    ICON_WSL_STOPPED,
)

_WSL_EXE = "wsl.exe"
_NO_WINDOW = subprocess.CREATE_NO_WINDOW
_WSL_NOT_INSTALLED_EXIT_CODE = 50


def _decode(raw: bytes) -> str:
    for enc in ("utf-16", "utf-8", "cp1252"):
        try:
            return raw.decode(enc).strip()
        except UnicodeDecodeError, LookupError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def _is_wsl_installed() -> bool:
    """Return True only if WSL is installed."""
    try:
        proc = subprocess.run(
            [_WSL_EXE, "--status"],
            capture_output=True,
            timeout=5,
            creationflags=_NO_WINDOW,
        )
        return proc.returncode != _WSL_NOT_INSTALLED_EXIT_CODE
    except Exception:
        return False


def _run_wsl(*args: str, timeout: int = 8) -> tuple[int, str]:
    """Run wsl.exe with args. Returns (returncode, stdout). returncode=-1 on exception."""
    try:
        proc = subprocess.run(
            [_WSL_EXE, *args],
            capture_output=True,
            timeout=timeout,
            creationflags=_NO_WINDOW,
        )
        return proc.returncode, _decode(proc.stdout)
    except subprocess.TimeoutExpired:
        logging.debug("WSL provider: timed out: %s", args)
        return -1, ""
    except Exception as exc:
        logging.debug("WSL provider: command failed: %s", exc)
        return -1, ""


def _list_installed() -> list[dict[str, Any]]:
    """Return installed distros parsed from `wsl --list --verbose`."""
    returncode, out = _run_wsl("--list", "--verbose")
    # Non-zero exit means no distros or WSL error return empty cleanly
    if returncode != 0 or not out:
        return []
    clean = out.replace("\x00", "")
    lines = [l for l in clean.splitlines() if l.strip()]
    distros: list[dict[str, Any]] = []
    for line in lines[1:]:  # skip header row
        parts = re.split(r"\s{2,}", line.strip())
        if not parts or not parts[0]:
            continue
        name = parts[0]
        is_default = False
        if name.startswith("*"):
            is_default = True
            name = name[1:].strip()
        distros.append(
            {
                "name": name,
                "state": parts[1] if len(parts) > 1 else "Unknown",
                "version": parts[2] if len(parts) > 2 else "",
                "is_default": is_default,
            }
        )
    return distros


def _list_online() -> list[dict[str, Any]]:
    """Return online-installable distros from `wsl --list --online`."""
    _, out = _run_wsl("--list", "--online", timeout=15)
    if not out:
        return []
    clean = out.replace("\x00", "")
    distros: list[dict[str, Any]] = []
    for line in clean.splitlines():
        l = line.strip()
        if not l:
            continue
        # Skip header/instruction lines
        if l.startswith("The following is a list"):
            continue
        if l.startswith("Install using"):
            continue
        if l.upper().startswith("NAME"):
            continue
        parts = re.split(r"\s{2,}", l)
        if not parts or not parts[0]:
            continue
        name = parts[0].strip()
        friendly = parts[1].strip() if len(parts) > 1 else name
        distros.append({"name": name, "friendly": friendly})
    return distros


class WslProvider(BaseProvider):
    """Browse and manage WSL distributions."""

    name = "wsl"
    display_name = "WSL"
    input_placeholder = "Search WSL distributions..."
    icon = ICON_WSL

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        cfg = config or {}
        self._show_online: bool = bool(cfg.get("show_online", True))

        # Data state
        self._installed: list[dict[str, Any]] = []
        self._online: list[dict[str, Any]] = []
        self._load_error: str | None = None

        # Loading state
        self._fetching = False
        self._loaded = False
        self._pending: set[str] = set()  # distros currently transitioning (start/stop)

    def _fetch_in_background(self) -> None:
        """Full load shows loader while running (used on first open)."""

        def _do_load() -> None:
            try:
                if not _is_wsl_installed():
                    self._load_error = "not_installed"
                    return
                self._installed = _list_installed()
                self._load_error = None
                if self._show_online:
                    installed_names = {d["name"].lower() for d in self._installed}
                    online = _list_online()
                    self._online = [d for d in online if d["name"].lower() not in installed_names]
            except Exception as exc:
                logging.debug("WSL provider: load error: %s", exc)
                self._load_error = str(exc)
            finally:
                self._fetching = False
                self._loaded = True
                self._emit_refresh()

        self._fetching = True
        threading.Thread(target=_do_load, daemon=True).start()

    def on_deactivate(self) -> None:
        self._loaded = False
        self._fetching = False
        self._pending = set()
        self._installed = []
        self._online = []
        self._load_error = None

    def _emit_refresh(self) -> None:
        if self.request_refresh:
            try:
                self.request_refresh()
            except Exception:
                pass

    @staticmethod
    def _open_terminal(*cmd: str) -> None:
        """Open a new terminal window."""
        try:
            subprocess.Popen(["wt.exe", *cmd])
        except FileNotFoundError:
            try:
                subprocess.Popen(["cmd.exe", "/k", *cmd], creationflags=subprocess.CREATE_NEW_CONSOLE)
            except Exception as exc:
                logging.debug("WSL provider: open_terminal failed: %s", exc)
        except Exception as exc:
            logging.debug("WSL provider: open_terminal failed: %s", exc)

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        # First call start background load and show loader
        if not self._loaded:
            if not self._fetching:
                self._fetch_in_background()
            return [
                ProviderResult(
                    title="Loading WSL distributions...",
                    description="Please wait",
                    icon_char=ICON_WSL,
                    provider=self.name,
                    is_loading=True,
                )
            ]

        # WSL not installed on this machine
        if self._load_error == "not_installed":
            return [
                ProviderResult(
                    title="WSL is not installed",
                    description="Press Enter to run: wsl --install",
                    icon_char=ICON_WARNING,
                    provider=self.name,
                    action_data={"action": "wsl_install"},
                )
            ]

        # Commands timed out (WSL installed but not responding)
        if self._load_error == "timeout":
            return [
                ProviderResult(
                    title="WSL timed out",
                    description="WSL is installed but not responding",
                    icon_char=ICON_WARNING,
                    provider=self.name,
                )
            ]

        # Generic error
        if self._load_error:
            return [
                ProviderResult(
                    title="WSL error",
                    description=self._load_error,
                    icon_char=ICON_WARNING,
                    provider=self.name,
                )
            ]

        query = self.get_query_text(text).strip().lower()
        results: list[ProviderResult] = []

        installed = self._installed
        if query:
            installed = [d for d in installed if query in d["name"].lower()]

        if self._installed:
            results.append(ProviderResult(title="Installed Distributions", provider=self.name, is_separator=True))

        for d in installed:
            state = d["state"]
            is_running = state.lower() == "running"
            is_pending = d["name"] in self._pending
            version_part = f" · WSL{d['version']}" if d["version"] else ""
            badge = " · Default" if d["is_default"] else ""
            enter_hint = "Stop" if is_running else "Start"
            results.append(
                ProviderResult(
                    title=d["name"],
                    description=f"{state}{version_part}{badge} · Enter to {enter_hint}",
                    icon_char=ICON_WSL_RUNNING if is_running else ICON_WSL_STOPPED,
                    provider=self.name,
                    id=f"installed:{d['name']}",
                    is_loading=is_pending,
                    action_data={
                        "action": "toggle",
                        "name": d["name"],
                        "state": state,
                        "is_default": d["is_default"],
                    },
                )
            )

        if not self._installed and not query:
            results.append(
                ProviderResult(
                    title="No distributions installed",
                    description="Install one from the list below",
                    icon_char=ICON_WSL,
                    provider=self.name,
                )
            )

        if self._show_online:
            online = self._online
            if query:
                online = [d for d in online if query in d["name"].lower() or query in d["friendly"].lower()]
            if online:
                results.append(ProviderResult(title="Available Online", provider=self.name, is_separator=True))
                for d in online:
                    results.append(
                        ProviderResult(
                            title=d["name"],
                            description=d["friendly"],
                            icon_char=ICON_WSL_ONLINE,
                            provider=self.name,
                            id=f"online:{d['name']}",
                            action_data={"action": "install", "name": d["name"]},
                        )
                    )

        if not results or all(r.is_separator for r in results):
            return [
                ProviderResult(
                    title="No WSL distributions found",
                    description="Try a different search term",
                    icon_char=ICON_WSL,
                    provider=self.name,
                )
            ]

        return results

    def execute(self, result: ProviderResult) -> bool | None:
        action = result.action_data.get("action")
        name = result.action_data.get("name", "")
        if action == "wsl_install":
            self._run_wsl_install()
            return True
        if action == "toggle":
            state = result.action_data.get("state", "").lower()
            if state == "running":
                self._transition_distro(name, ("--terminate", name), "Stopped")
            else:
                self._transition_distro(
                    name, ("-d", name, "-e", "sh", "-c", "nohup sleep infinity > /dev/null 2>&1 &"), "Running"
                )
            return False
        if action == "install":
            self._install_distro(name)
            return True
        return None

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        if result.action_data.get("action") != "toggle":
            return []
        state = result.action_data.get("state", "").lower()
        is_default = result.action_data.get("is_default", False)
        actions: list[ProviderMenuAction] = []
        if state == "running":
            actions.append(ProviderMenuAction(id="open_shell", label="Open shell"))
            actions.append(ProviderMenuAction(id="stop", label="Stop", separator_before=True))
        else:
            actions.append(ProviderMenuAction(id="start", label="Start"))
            actions.append(ProviderMenuAction(id="open_shell", label="Open shell"))
        if not is_default:
            actions.append(ProviderMenuAction(id="set_default", label="Set as default", separator_before=True))
        actions.append(
            ProviderMenuAction(id="unregister", label="Unregister (remove) distribution", separator_before=True)
        )
        return actions

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        name = result.action_data.get("name", "")
        if action_id == "open_shell":
            self._launch_distro(name)
            return ProviderMenuActionResult(close_popup=True)
        if action_id == "start":
            self._transition_distro(
                name, ("-d", name, "-e", "sh", "-c", "nohup sleep infinity > /dev/null 2>&1 &"), "Running"
            )
            return ProviderMenuActionResult()
        if action_id == "stop":
            self._transition_distro(name, ("--terminate", name), "Stopped")
            return ProviderMenuActionResult()
        if action_id == "set_default":
            self._run_cmd_then_reload("--set-default", name)
            return ProviderMenuActionResult(refresh_results=True)
        if action_id == "unregister":
            self._run_cmd_then_reload("--unregister", name)
            return ProviderMenuActionResult(refresh_results=True)
        return ProviderMenuActionResult()

    def _run_wsl_install(self) -> None:
        """Open a new terminal and run wsl --install."""
        self._open_terminal("cmd.exe", "/k", "wsl --install")

    def _launch_distro(self, name: str) -> None:
        self._open_terminal("wsl.exe", "-d", name)

    def _install_distro(self, name: str) -> None:
        self._open_terminal("cmd.exe", "/k", f"wsl.exe --install -d {name}")

    def _run_cmd_then_reload(self, *wsl_args: str) -> None:
        """Run a wsl command (set-default, unregister) then do a full reload."""
        self._loaded = False
        self._fetching = True

        def _do() -> None:
            try:
                _run_wsl(*wsl_args)
            finally:
                self._fetching = False
                self._loaded = False
                self._emit_refresh()

        threading.Thread(target=_do, daemon=True).start()

    def _transition_distro(self, name: str, wsl_args: tuple, new_state: str) -> None:
        """Run a wsl command for one distro, show per-row loader, update state in-place."""
        self._pending.add(name)
        self._emit_refresh()  # show spinner

        def _do() -> None:
            try:
                _run_wsl(*wsl_args, timeout=15)
                for d in self._installed:
                    if d["name"] == name:
                        d["state"] = new_state
                        break
            except Exception as exc:
                logging.debug("WSL provider: transition failed for %s: %s", name, exc)
            finally:
                self._pending.discard(name)
                self._emit_refresh()

        threading.Thread(target=_do, daemon=True).start()
