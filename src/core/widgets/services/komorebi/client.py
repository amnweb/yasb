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
        self._previous_poll_offline = False
        self._previous_mouse_follows_focus = False

    @property
    def komorebic_path(self) -> str:
        return self._komorebic_path

    @property
    def timeout_secs(self) -> float:
        return self._timeout_secs

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

    def get_num_windows(self, workspace: KomorebiNode) -> bool:
        floating = workspace.get("floating_windows", [])
        floating_node = as_node(floating)
        if floating_node is not None:
            if floating_node.get("elements", []):
                return True
        elif floating:
            return True

        for container in workspace["containers"]["elements"]:
            if container.get("windows", {}).get("elements", []):
                return True

        if isinstance(workspace["monocle_container"], dict):
            return True

        if isinstance(workspace["maximized_window"], dict):
            return True
        return False

    def get_workspace_by_window_hwnd(self, workspaces: list[KomorebiNode], window_hwnd: int) -> KomorebiNode | None:
        for i, workspace in enumerate(workspaces):
            for floating_window in self.get_floating_windows(workspace):
                if floating_window["hwnd"] == window_hwnd:
                    return add_index(workspace, i)

            if ("containers" not in workspace) or ("elements" not in workspace["containers"]):
                continue

            for container in workspace["containers"]["elements"]:
                if ("windows" not in container) or ("elements" not in container["windows"]):
                    continue

                for managed_window in container["windows"]["elements"]:
                    if managed_window["hwnd"] == window_hwnd:
                        return add_index(workspace, i)

    def activate_workspace(self, m_idx: int, ws_idx: int, wait: bool = False) -> None:
        args = [self._komorebic_path, "focus-monitor-workspace", str(m_idx), str(ws_idx)]
        if wait:
            try:
                subprocess.run(
                    args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW
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

    def next_workspace(self) -> None:
        try:
            subprocess.Popen(
                [self._komorebic_path, "cycle-workspace", "next"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.SubprocessError, FileNotFoundError:
            logging.exception("Failed to cycle komorebi workspace")

    def prev_workspace(self) -> None:
        try:
            subprocess.Popen(
                [self._komorebic_path, "cycle-workspace", "previous"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.SubprocessError, FileNotFoundError:
            logging.exception("Failed to cycle komorebi workspace")

    def toggle_focus_mouse(self) -> None:
        try:
            subprocess.Popen(
                [self._komorebic_path, "toggle-focus-follows-mouse", "--implementation", "windows"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.SubprocessError, FileNotFoundError:
            logging.exception("Failed to toggle focus-follows-mouse")

    def change_layout(self, m_idx: int, ws_idx: int, layout: str) -> None:
        try:
            subprocess.Popen(
                [self._komorebic_path, "workspace-layout", str(m_idx), str(ws_idx), layout],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.SubprocessError, FileNotFoundError:
            logging.exception("Failed to change layout of currently active workspace to %s", layout)

    def flip_layout(self, direction: str) -> None:
        try:
            subprocess.Popen(
                [self._komorebic_path, "flip-layout", direction],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.SubprocessError, FileNotFoundError:
            pass

    def flip_layout_horizontal(self) -> None:
        self.flip_layout("horizontal")

    def flip_layout_vertical(self) -> None:
        self.flip_layout("vertical")

    def flip_layout_horizontal_and_vertical(self) -> None:
        self.flip_layout("horizontal-and-vertical")

    def toggle(self, toggle_type: str, wait: bool = False) -> None:
        try:
            command = (
                f'"{self._komorebic_path}" focus-monitor-at-cursor && "{self._komorebic_path}" toggle-{toggle_type}'
            )
            if wait:
                subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            else:
                subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.SubprocessError, FileNotFoundError:
            logging.exception("Failed to toggle %s for currently active workspace", toggle_type)

    def wait_until_subscribed_to_pipe(self, pipe_name: str):
        args = [self._komorebic_path, "subscribe", pipe_name]
        try:
            proc = subprocess.run(args, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except FileNotFoundError as e:
            proc = subprocess.CompletedProcess(args, 1, b"", f"{self._komorebic_path}: {e.strerror}".encode())
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

    def get_container_by_index(self, workspace: KomorebiNode, container_index: int) -> KomorebiNode | None:
        try:
            return self.get_containers(workspace)[container_index]
        except IndexError:
            return None

    def get_focused_container(self, workspace: KomorebiNode, get_monocle: bool = True) -> KomorebiNode | None:
        if get_monocle:
            monocle_container = self.get_monocle_container(workspace)
            if monocle_container:
                return monocle_container
        try:
            focused_container_index = workspace["containers"]["focused"]
            focused_container = self.get_container_by_index(workspace, focused_container_index)
            if focused_container is None:
                return None
            focused_container["index"] = focused_container_index
            return focused_container
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

    def get_window_by_index(self, container: KomorebiNode, window_index: int) -> KomorebiNode | None:
        try:
            return self.get_windows(container)[window_index]
        except IndexError:
            return None

    def get_focused_window(self, container: KomorebiNode) -> KomorebiNode | None:
        try:
            focused_window_index = container["windows"]["focused"]
            focused_window = self.get_window_by_index(container, focused_window_index)
            if focused_window is None:
                return None
            focused_window["index"] = focused_window_index
            return focused_window
        except KeyError, TypeError:
            return None

    def get_floating_windows(self, workspace: KomorebiNode) -> list[KomorebiNode]:
        floating = as_node(workspace.get("floating_windows"))
        if floating is None:
            return []
        elements = as_list(floating.get("elements"))
        if elements is None:
            return []
        return [add_index(window, i) for i, window in enumerate(elements)]

    def get_focused_floating_window(self, workspace: KomorebiNode) -> KomorebiNode | None:
        try:
            focused_window_index: int = workspace["floating_windows"]["focused"]
            return self.get_floating_windows(workspace)[focused_window_index]
        except KeyError, TypeError, IndexError:
            return None

    def focus_stack_window(self, w_idx: int) -> None:
        try:
            subprocess.Popen(
                [self._komorebic_path, "focus-stack-window", str(w_idx)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.SubprocessError, FileNotFoundError:
            logging.exception("Failed to focus stack window")

    def next_stack_window(self) -> None:
        try:
            subprocess.Popen(
                [self._komorebic_path, "cycle-stack", "next"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.SubprocessError, FileNotFoundError:
            logging.exception("Failed to cycle komorebi stack")

    def prev_stack_window(self) -> None:
        try:
            subprocess.Popen(
                [self._komorebic_path, "cycle-stack", "previous"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.SubprocessError, FileNotFoundError:
            logging.exception("Failed to cycle komorebi stack")
