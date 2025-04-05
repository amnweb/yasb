import subprocess
import logging
import json
from contextlib import suppress
from typing import Optional

def add_index(dictionary: dict, dictionary_index: int) -> dict:
    dictionary['index'] = dictionary_index
    return dictionary


class KomorebiClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(KomorebiClient, cls).__new__(cls)
        return cls._instance

    def __init__(
            self,
            komorebic_path: str = "komorebic.exe",
            timeout_secs: float = 0.5
    ):
        if hasattr(self, "_komorebi_initialized"):
            return
        self._komorebi_initialized = True

        super().__init__()
        self._timeout_secs = timeout_secs
        self._komorebic_path = komorebic_path
        self._previous_poll_offline = False
        self._previous_mouse_follows_focus = False

    def query_state(self) -> Optional[dict]:
        try:
            output = subprocess.check_output(
                [self._komorebic_path, "state"],
                timeout=self._timeout_secs,
                shell=True
            )
            return json.loads(output)
        except subprocess.TimeoutExpired as e:
            logging.error(f"Komorebi state query timed out in {self._timeout_secs} seconds")
        except (json.JSONDecodeError, subprocess.CalledProcessError):
            return None

    def get_screens(self, state: dict) -> list:
        return state['monitors']['elements']

    def get_screen_by_hwnd(self, state: dict, screen_hwnd: int) -> Optional[dict]:
        for i, screen in enumerate(self.get_screens(state)):
            if screen.get('id', None) == screen_hwnd:
                return add_index(screen, i)

    def get_workspaces(self, screen: dict) -> list:
        return [add_index(workspace, i) for i, workspace in enumerate(screen['workspaces']['elements'])]

    def get_workspace_by_index(self, screen: dict, workspace_index: int) -> Optional[dict]:
        try:
            return self.get_workspaces(screen)[workspace_index]
        except IndexError:
            return None

    def get_focused_workspace(self, screen: dict) -> Optional[dict]:
        try:
            focused_workspace_index = screen['workspaces']['focused']
            focused_workspace = self.get_workspace_by_index(screen, focused_workspace_index)
            focused_workspace['index'] = focused_workspace_index
            return focused_workspace
        except (KeyError, TypeError):
            return None

    def get_num_windows(self, workspace: dict) -> bool:
        floating = workspace.get('floating_windows', [])
        if isinstance(floating, dict):
            if floating.get('elements', []):
                return True
        elif floating:
            return True

        for container in workspace['containers']['elements']:
            if container.get('windows', {}).get('elements', []):
                return True

        return False

 
    
    def get_workspace_by_window_hwnd(self, workspaces: list[Optional[dict]], window_hwnd: int) -> Optional[dict]:
        for i, workspace in enumerate(workspaces):

            for floating_window in workspace['floating_windows']:
                if floating_window['hwnd'] == window_hwnd:
                    return add_index(workspace, i)

            if ('containers' not in workspace) or ('elements' not in workspace['containers']):
                continue

            for container in workspace['containers']['elements']:
                if ('windows' not in container) or ('elements' not in container['windows']):
                    continue

                for managed_window in container['windows']['elements']:
                    if managed_window['hwnd'] == window_hwnd:
                        return add_index(workspace, i)

    def activate_workspace(self, m_idx: int, ws_idx: int, wait: bool = False) -> None:
        p = subprocess.Popen([self._komorebic_path, "focus-monitor-workspace", str(m_idx), str(ws_idx)], shell=True)
        if wait:
            p.wait()

    def next_workspace(self) -> None:
        try:
            subprocess.Popen([self._komorebic_path, "cycle-workspace", "next"], shell=True)
        except subprocess.SubprocessError:
            logging.exception("Failed to cycle komorebi workspace")

    def prev_workspace(self) -> None:
        try:
            subprocess.Popen([self._komorebic_path, "cycle-workspace", "prev"], shell=True)
        except subprocess.SubprocessError:
            logging.exception("Failed to cycle komorebi workspace")

    def toggle_focus_mouse(self) -> None:
        try:
            subprocess.Popen([self._komorebic_path, "toggle-focus-follows-mouse"], shell=True)
        except subprocess.SubprocessError:
            logging.exception("Failed to toggle focus-follows-mouse")

    def change_layout(self, m_idx: int, ws_idx: int, layout: str) -> None:
        try:
            subprocess.Popen([self._komorebic_path, "workspace-layout", str(m_idx), str(ws_idx), layout], shell=True)
        except subprocess.SubprocessError:
            logging.exception(f"Failed to change layout of currently active workspace to {layout}")

    def flip_layout(self, direction: str) -> None:
        try:
            subprocess.Popen(
                [self._komorebic_path, "flip-layout", direction],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True
            )
        except subprocess.SubprocessError:
            pass

    def flip_layout_horizontal(self) -> None:
        self.flip_layout("horizontal")

    def flip_layout_vertical(self) -> None:
        self.flip_layout("vertical")

    def flip_layout_horizontal_and_vertical(self) -> None:
        self.flip_layout("horizontal-and-vertical")

    def toggle(self, toggle_type: str, wait: bool = False) -> None:
        try:
            command = f'"{self._komorebic_path}" focus-monitor-at-cursor && "{self._komorebic_path}" toggle-{toggle_type}'
            p = subprocess.Popen(command, shell=True)

            if wait:
                p.wait()
        except subprocess.SubprocessError:
            logging.exception(f"Failed to toggle {toggle_type} for currently active workspace")

    def wait_until_subscribed_to_pipe(self, pipe_name: str):
        proc = subprocess.Popen(
            [self._komorebic_path, "subscribe", pipe_name],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        _stdout, stderr = proc.communicate()

        return stderr, proc