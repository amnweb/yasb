import logging
import re
from typing import Any

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication

from core.services.glazewm.client import GlazewmClient, Monitor, Workspace
from core.services.glazewm.connection import GlazewmConnection
from core.utils.icons.image_provider import window_icon_url
from core.utils.icons.service import IconService
from core.utils.win32.bindings.user32 import get_window_thread_process_id
from core.utils.win32.utils import screen_monitor

logger = logging.getLogger("glazewm_workspaces")

WORKSPACE_MESSAGES = [
    "sub -e workspace_activated workspace_deactivated workspace_updated focus_changed focused_container_moved "
    "window_managed window_unmanaged monitor_added monitor_removed monitor_updated user_config_changed",
    "query monitors",
]


def natural_sort_key(name: str) -> list[int | str]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def _setting(kind: type | str, name: str, notify: pyqtSignal) -> pyqtProperty[Any]:
    def get(model: GlazewmWorkspaceList) -> Any:
        return model.setting(name)

    def set_value(model: GlazewmWorkspaceList, value: Any) -> None:
        model.change_setting(name, value)

    return pyqtProperty(kind, get, set_value, notify=notify)


class GlazewmWorkspaceList(GlazewmConnection):
    dataChanged = pyqtSignal()
    settingsChanged = pyqtSignal()

    MESSAGES = WORKSPACE_MESSAGES

    screenName = _setting(str, "screenName", settingsChanged)
    monitorExclusive = _setting(bool, "monitorExclusive", settingsChanged)
    appIcons = _setting("QVariantMap", "appIcons", settingsChanged)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, Any] = {
            "screenName": "",
            "monitorExclusive": True,
            "appIcons": {},
        }
        self._monitors: list[Monitor] = []
        self._workspaces: list[dict[str, Any]] = []
        IconService.instance().icons_changed.connect(self._publish)

    def setting(self, name: str) -> Any:
        return self._settings[name]

    def change_setting(self, name: str, value: Any) -> None:
        if self._settings[name] == value:
            return
        self._settings[name] = value
        self.settingsChanged.emit()
        self._publish()

    @pyqtProperty("QVariantList", notify=dataChanged)
    def workspaces(self) -> list[dict[str, Any]]:
        return self._workspaces

    def _bind(self, client: GlazewmClient) -> None:
        client.workspaces_data_processed.connect(self._on_data)

    def _unbind(self, client: GlazewmClient) -> None:
        client.workspaces_data_processed.disconnect(self._on_data)

    def _reset(self) -> None:
        self._monitors = []
        self._publish()

    @pyqtSlot(list)
    def _on_data(self, monitors: list[Monitor]) -> None:
        self._monitors = monitors
        self._publish()

    def _publish(self) -> None:
        exclusive = self.setting("monitorExclusive")
        monitors = self._monitors
        if exclusive:
            screen_name = self.setting("screenName")
            if not screen_name and (screen := QGuiApplication.primaryScreen()) is not None:
                screen_name = screen.name()
            handle = screen_monitor(screen_name)
            monitors = [monitor for monitor in monitors if monitor.hwnd == handle]

        workspaces: list[dict[str, Any]] = []
        for monitor in monitors:
            for workspace in monitor.workspaces:
                populated = workspace.num_windows > 0
                prefix = "focused_" if workspace.focus else "active_" if exclusive and workspace.is_displayed else ""
                status = prefix + ("populated" if populated else "empty")
                workspaces.append(
                    {
                        "name": workspace.name,
                        "displayName": workspace.display_name or "",
                        "focused": workspace.focus,
                        "displayed": workspace.is_displayed,
                        "windowCount": workspace.num_windows,
                        "status": status,
                        "icons": self._icons(workspace, status),
                    }
                )
        workspaces.sort(key=lambda workspace: natural_sort_key(workspace["name"]))
        if workspaces != self._workspaces:
            self._workspaces = workspaces
            self.dataChanged.emit()

    def _icons(self, workspace: Workspace, status: str) -> list[dict[str, Any]]:
        options = self.setting("appIcons")
        enabled = options.get("enabledPopulated", False)
        if status.startswith("focused_"):
            enabled = options.get("enabledFocused")
            if enabled is None:
                enabled = options.get("enabledActive", False)
        elif status.startswith("active_"):
            enabled = options.get("enabledActive", False)
        if not enabled:
            return []

        icons: list[dict[str, Any]] = []
        pids: set[int] = set()
        revision = IconService.instance().revision
        maximum = max(0, options.get("maxIcons", 0))
        for window in workspace.windows:
            if not window.handle or (options.get("hideFloating") and window.is_floating):
                continue
            if options.get("hideDuplicates"):
                try:
                    _, pid = get_window_thread_process_id(window.handle)
                except Exception:
                    logger.debug("Failed to get the process for HWND %s", window.handle, exc_info=True)
                    pid = 0
                if pid and pid in pids:
                    continue
                if pid:
                    pids.add(pid)
            icons.append(
                {
                    "hwnd": window.handle,
                    "title": window.title or window.process_name or "",
                    "source": window_icon_url(window.handle, revision),
                }
            )
            if maximum and len(icons) >= maximum:
                break
        return icons

    @pyqtSlot(str)
    def activateWorkspace(self, name: str) -> None:
        if (client := self.client) is not None:
            client.activate_workspace(name)

    @pyqtSlot(int)
    def switchWorkspace(self, direction: int) -> None:
        if (client := self.client) is None or not direction:
            return
        if self.setting("monitorExclusive"):
            if direction > 0:
                client.focus_prev_workspace()
            else:
                client.focus_next_workspace()
        elif direction > 0:
            client.focus_prev_workspace_global()
        else:
            client.focus_next_workspace_global()
