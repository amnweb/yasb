import logging
import re
from enum import StrEnum, auto

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from core.utils.glazewm.client import GlazewmClient, Monitor
from core.utils.win32.utilities import get_monitor_hwnd
from core.validation.widgets.glazewm.workspaces import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG

logger = logging.getLogger("glazewm_workspaces")

if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.CRITICAL)


class WorkspaceStatus(StrEnum):
    EMPTY = auto()
    POPULATED = auto()
    ACTIVE = auto()


class GlazewmWorkspaceButton(QPushButton):
    def __init__(
        self,
        workspace_name: str,
        client: GlazewmClient,
        display_name: str | None = None,
        populated_label: str | None = None,
        empty_label: str | None = None,
    ):
        super().__init__()
        self.setProperty("class", "ws-btn")
        self.glazewm_client = client
        self.workspace_name = workspace_name
        self.display_name = display_name
        self.populated_label = populated_label
        self.empty_label = empty_label
        self.is_displayed = False
        self.workspace_window_count = 0
        self.status = WorkspaceStatus.EMPTY
        self.clicked.connect(self._activate_workspace)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._update_status()

    def update(self):
        self._update_status()
        self._update_label()
        self.setProperty("class", f"ws-btn {self.status.value}")
        self.setStyleSheet("")

    def _activate_workspace(self):
        self.glazewm_client.activate_workspace(self.workspace_name)

    def _update_status(self):
        if self.is_displayed:
            self.status = WorkspaceStatus.ACTIVE
        elif self.workspace_window_count > 0 and not self.is_displayed:
            self.status = WorkspaceStatus.POPULATED
        else:
            self.status = WorkspaceStatus.EMPTY

    def _update_label(self):
        replacements = {
            "name": str(self.workspace_name or ""),
            "display_name": str(self.display_name or ""),
        }
        # Label priority: YASB config -> display_name from GlazeWM -> name from GlazeWM
        populated_label = self.populated_label or self.display_name or self.workspace_name
        empty_label = self.empty_label or self.display_name or self.workspace_name
        # Replace placeholders if any exist
        populated_label = populated_label.format_map(replacements)
        empty_label = empty_label.format_map(replacements)
        if self.status == WorkspaceStatus.ACTIVE:
            if self.workspace_window_count > 0:
                self.setText(populated_label)
            else:
                self.setText(empty_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.POPULATED:
            self.setText(populated_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.EMPTY:
            self.setText(empty_label)
        else:
            logger.warning(f"Unknown workspace status: {self.status}")


class GlazewmWorkspacesWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        offline_label: str,
        populated_label: str,
        empty_label: str,
        hide_empty_workspaces: bool,
        hide_if_offline: bool,
        glazewm_server_uri: str,
    ):
        super().__init__(class_name="glazewm-workspaces")
        self.label_offline = offline_label
        self.populated_label = populated_label
        self.empty_label = empty_label
        self.glazewm_server_uri = glazewm_server_uri
        self.hide_empty_workspaces = hide_empty_workspaces
        self.hide_if_offline = hide_if_offline
        self.workspaces: dict[str, GlazewmWorkspaceButton] = {}

        self.workspace_container_layout = QHBoxLayout()
        self.workspace_container_layout.setSpacing(0)
        self.workspace_container_layout.setContentsMargins(0, 0, 0, 0)

        self.workspace_container: QWidget = QWidget()
        self.workspace_container.setLayout(self.workspace_container_layout)
        self.workspace_container.setProperty("class", "widget-container")
        self.workspace_container.setVisible(False)

        self.offline_text = QLabel(self.label_offline)
        self.offline_text.setProperty("class", "offline-status")

        self.widget_layout.addWidget(self.offline_text)
        self.widget_layout.addWidget(self.workspace_container)

        self.offline_text.setVisible(True)

        self.monitor_hwnd = get_monitor_hwnd(int(QWidget.winId(self)))

        self.glazewm_client = GlazewmClient(
            self.glazewm_server_uri,
            [
                "sub -e workspace_activated workspace_deactivated workspace_updated focus_changed focused_container_moved",
                "query monitors",
            ],
        )
        self.glazewm_client.glazewm_connection_status.connect(self._update_connection_status)
        self.glazewm_client.workspaces_data_processed.connect(self._update_workspaces)
        self.glazewm_client.connect()

    def _update_connection_status(self, status: bool):
        self.workspace_container.setVisible(status)
        self.offline_text.setVisible(not status if not self.hide_if_offline else False)

    def _update_workspaces(self, message: list[Monitor]):
        # Find the target monitor
        current_mon = next((m for m in message if m.hwnd == self.monitor_hwnd), None)
        if not current_mon:
            return

        for workspace in current_mon.workspaces:
            # Get or create workspace button if it's not present
            if (btn := self.workspaces.get(workspace.name)) is None:
                btn = self.workspaces[workspace.name] = GlazewmWorkspaceButton(
                    workspace.name,
                    self.glazewm_client,
                    display_name=workspace.display_name,
                    populated_label=self.populated_label,
                    empty_label=self.empty_label,
                )

            # Update workspace state
            btn.workspace_name = workspace.name
            btn.display_name = workspace.display_name
            btn.workspace_window_count = workspace.num_windows
            btn.is_displayed = workspace.is_displayed

        def natural_sort_key(s, _nsre=re.compile(r"(\d+)")):
            return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]

        # Insert the new widget if it's not present
        for i, ws_name in enumerate(sorted(self.workspaces.keys(), key=natural_sort_key)):
            if self.workspace_container_layout.indexOf(self.workspaces[ws_name]) != i:
                self.workspace_container_layout.insertWidget(i, self.workspaces[ws_name])

        # Update workspaces
        current_ws_names = {ws.name for ws in current_mon.workspaces}
        for btn in self.workspaces.values():
            if btn.workspace_name not in current_ws_names:
                btn.is_displayed = False
                btn.workspace_window_count = 0
                btn.setHidden(self.hide_empty_workspaces)
            btn.update()
