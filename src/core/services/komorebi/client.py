import json
import logging
import subprocess
from typing import Any, cast

type KomorebiNode = dict[str, Any]


def as_node(value: object) -> KomorebiNode | None:
    return cast(KomorebiNode, value) if isinstance(value, dict) else None


def as_list(value: object) -> list[Any] | None:
    return cast(list[Any], value) if isinstance(value, list) else None


def add_index(dictionary: KomorebiNode, dictionary_index: int) -> KomorebiNode:
    dictionary["index"] = dictionary_index
    return dictionary


class KomorebiClient:
    _instance: KomorebiClient | None = None

    def __new__(cls, *args: Any, **kwargs: Any) -> KomorebiClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, komorebic_path: str = "komorebic.exe", timeout_secs: float = 0.5):
        if hasattr(self, "_komorebi_initialized"):
            return
        self._komorebi_initialized = True

        super().__init__()
        self._timeout_secs = timeout_secs
        self._komorebic_path = komorebic_path

    def query_state(self) -> KomorebiNode | None:
        try:
            # Capture stderr to avoid raw komorebic panics leaking to console
            output = subprocess.check_output(
                [self._komorebic_path, "state"],
                timeout=self._timeout_secs,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return json.loads(output)
        except subprocess.TimeoutExpired:
            logging.error("Komorebi state query timed out in %s seconds", self._timeout_secs)
        except json.JSONDecodeError, subprocess.CalledProcessError, FileNotFoundError:
            return None

    def get_screens(self, state: KomorebiNode) -> list[KomorebiNode]:
        return state["monitors"]["elements"]

    def get_screen_by_hwnd(self, state: KomorebiNode, screen_hwnd: int) -> KomorebiNode | None:
        for i, screen in enumerate(self.get_screens(state)):
            if screen.get("id", None) == screen_hwnd:
                return add_index(screen, i)

    def get_workspaces(self, screen: KomorebiNode) -> list[KomorebiNode]:
        return [add_index(workspace, i) for i, workspace in enumerate(screen["workspaces"]["elements"])]

    def get_workspace_by_index(self, screen: KomorebiNode, workspace_index: int) -> KomorebiNode | None:
        try:
            return self.get_workspaces(screen)[workspace_index]
        except IndexError:
            return None

    def get_focused_workspace(self, screen: KomorebiNode) -> KomorebiNode | None:
        try:
            focused_workspace_index = screen["workspaces"]["focused"]
            focused_workspace = self.get_workspace_by_index(screen, focused_workspace_index)
            if focused_workspace is None:
                return None
            focused_workspace["index"] = focused_workspace_index
            return focused_workspace
        except KeyError, TypeError:
            return None

    def activate_workspace(self, m_idx: int, ws_idx: int, wait: bool = False) -> None:
        args = [self._komorebic_path, "focus-monitor-workspace", str(m_idx), str(ws_idx)]
        if wait:
            try:
                subprocess.run(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=self._timeout_secs,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except subprocess.SubprocessError, FileNotFoundError:
                logging.exception("Failed to activate komorebi workspace")
        else:
            try:
                subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except subprocess.SubprocessError, FileNotFoundError:
                logging.exception("Failed to activate komorebi workspace (spawn)")

    def wait_until_subscribed_to_pipe(self, pipe_name: str):
        args = [self._komorebic_path, "subscribe", pipe_name]
        try:
            proc = subprocess.run(
                args, capture_output=True, timeout=self._timeout_secs, creationflags=subprocess.CREATE_NO_WINDOW
            )
        except FileNotFoundError as e:
            proc = subprocess.CompletedProcess(args, 1, b"", f"{self._komorebic_path}: {e.strerror}".encode())
        except subprocess.TimeoutExpired:
            proc = subprocess.CompletedProcess(args, 1, b"", b"Komorebi subscription timed out.")
        return proc.stderr, proc

    def get_containers(self, workspace: KomorebiNode, get_monocle: bool = True) -> list[KomorebiNode]:
        containers = [add_index(container, i) for i, container in enumerate(workspace["containers"]["elements"])]
        monocle_container = self.get_monocle_container(workspace)
        if get_monocle and monocle_container:
            containers.append(monocle_container)
        return containers

    def get_monocle_container(self, workspace: KomorebiNode) -> KomorebiNode | None:
        try:
            monocle_container = workspace["monocle_container"]
            return as_node(monocle_container)
        except KeyError, TypeError:
            return None

    def get_windows(self, container: KomorebiNode | None) -> list[KomorebiNode]:
        if not isinstance(container, dict):
            return []
        windows = as_node(container.get("windows"))
        if windows is None:
            return []
        elements = as_list(windows.get("elements"))
        if elements is None:
            return []
        return [add_index(window, i) for i, window in enumerate(elements)]

    def get_floating_windows(self, workspace: KomorebiNode) -> list[KomorebiNode]:
        floating = workspace.get("floating_windows")
        ring = as_node(floating)
        elements = as_list(ring.get("elements") if ring is not None else floating)
        if elements is None:
            return []
        return [add_index(window, i) for i, window in enumerate(elements)]
