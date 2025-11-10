import logging
import re
from enum import StrEnum, auto
from typing import Any, override

from PIL import Image
from PyQt6.QtCore import (
    Qt,
    QTimer,
    pyqtSlot,  # type: ignore
)
from PyQt6.QtGui import QCursor, QImage, QMouseEvent, QPixmap, QShowEvent, QWheelEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from core.utils.utilities import add_shadow, refresh_widget_style
from core.utils.widgets.glazewm.client import GlazewmClient, Monitor, Window
from core.utils.win32.app_icons import get_window_icon
from core.utils.win32.utilities import get_monitor_hwnd, get_process_info
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
    ACTIVE_EMPTY = auto()
    ACTIVE_POPULATED = auto()
    FOCUSED_EMPTY = auto()
    FOCUSED_POPULATED = auto()


def natural_sort_key(s: str, _nsre: re.Pattern[str] = re.compile(r"(\d+)")):
    """Sorts a string in the format '1-2-3' in natural order."""
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


class GlazewmWorkspaceButton(QPushButton):
    def __init__(
        self,
        workspace_name: str,
        client: GlazewmClient,
        display_name: str | None = None,
        populated_label: str | None = None,
        empty_label: str | None = None,
        active_populated_label: str | None = None,
        active_empty_label: str | None = None,
        focused_populated_label: str | None = None,
        focused_empty_label: str | None = None,
    ):
        super().__init__()
        self.setProperty("class", "ws-btn")
        self.glazewm_client = client
        self.workspace_name = workspace_name
        self.display_name = display_name
        self.populated_label = populated_label
        self.empty_label = empty_label
        self.active_populated_label = active_populated_label
        self.active_empty_label = active_empty_label
        self.focused_populated_label = focused_populated_label
        self.focused_empty_label = focused_empty_label
        self.is_displayed = False
        self.is_focused = False
        self.workspace_window_count = 0
        self.status = WorkspaceStatus.EMPTY
        self.clicked.connect(self._activate_workspace)  # type: ignore
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._update_status()

    def update_button(self):
        self._update_status()
        self._update_label()
        button_class = "ws-btn "
        # To maintain previous functionality, apply the equivalent active_ class to the focused_ workspace.
        if self.status.value == WorkspaceStatus.FOCUSED_POPULATED:
            button_class += WorkspaceStatus.ACTIVE_POPULATED + " " + self.status.value
        elif self.status.value == WorkspaceStatus.FOCUSED_EMPTY:
            button_class += WorkspaceStatus.ACTIVE_EMPTY + " " + self.status.value
        else:
            button_class += self.status.value
        self.setProperty("class", button_class)
        refresh_widget_style(self)

    @pyqtSlot()
    def _activate_workspace(self):
        self.glazewm_client.activate_workspace(self.workspace_name)

    def _update_status(self):
        if self.is_displayed:
            if self.is_focused:
                if self.workspace_window_count > 0:
                    self.status = WorkspaceStatus.FOCUSED_POPULATED
                else:
                    self.status = WorkspaceStatus.FOCUSED_EMPTY
            elif self.workspace_window_count > 0:
                self.status = WorkspaceStatus.ACTIVE_POPULATED
            else:
                self.status = WorkspaceStatus.ACTIVE_EMPTY
        elif self.workspace_window_count > 0:
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
        active_populated_label = self.active_populated_label or self.display_name or self.workspace_name
        active_empty_label = self.active_empty_label or self.display_name or self.workspace_name
        # have focused_ label variants fall back to equivalent active_ label variants if they are set (preserves previous functionality)
        focused_populated_label = (
            self.focused_populated_label or self.active_populated_label or self.display_name or self.workspace_name
        )
        focused_empty_label = (
            self.focused_empty_label or self.active_empty_label or self.display_name or self.workspace_name
        )
        # Replace placeholders if any exist
        populated_label = populated_label.format_map(replacements)
        empty_label = empty_label.format_map(replacements)
        active_populated_label = active_populated_label.format_map(replacements)
        active_empty_label = active_empty_label.format_map(replacements)
        focused_populated_label = focused_populated_label.format_map(replacements)
        focused_empty_label = focused_empty_label.format_map(replacements)
        if self.status == WorkspaceStatus.FOCUSED_POPULATED:
            self.setText(focused_populated_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.FOCUSED_EMPTY:
            self.setText(focused_empty_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.ACTIVE_POPULATED:
            self.setText(active_populated_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.ACTIVE_EMPTY:
            self.setText(active_empty_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.POPULATED:
            self.setText(populated_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.EMPTY:
            self.setText(empty_label)
        else:
            logger.warning(f"Unknown workspace status: {self.status}")


class GlazewmWorkspaceButtonWithIcons(QFrame):
    def __init__(
        self,
        workspace_name: str,
        client: GlazewmClient,
        parent_widget: "GlazewmWorkspacesWidget",
        display_name: str | None = None,
        populated_label: str | None = None,
        empty_label: str | None = None,
        active_populated_label: str | None = None,
        active_empty_label: str | None = None,
        focused_populated_label: str | None = None,
        focused_empty_label: str | None = None,
        windows: list[Window] | None = None,
    ):
        super().__init__()
        self.setProperty("class", "ws-btn")
        self.glazewm_client = client
        self.workspace_name = workspace_name
        self.display_name = display_name
        self.populated_label = populated_label
        self.empty_label = empty_label
        self.active_populated_label = active_populated_label
        self.active_empty_label = active_empty_label
        self.focused_populated_label = focused_populated_label
        self.focused_empty_label = focused_empty_label
        self.is_displayed = False
        self.is_focused = False
        self.parent_widget = parent_widget
        self.status = WorkspaceStatus.EMPTY
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._animation_initialized = False
        self.workspace_window_count = 0
        self.windows = windows

        self.button_layout = QHBoxLayout(self)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(0)

        self.text_label = QLabel(self.workspace_name)
        self.text_label.setProperty("class", "label")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.button_layout.addWidget(self.text_label)
        add_shadow(self.text_label, self.parent_widget.label_shadow)

        self.icons = {}
        self.icon_labels = []
        self.update_button()

    def update_button(self):
        self._update_status()
        self._update_label()
        self._update_icons()
        button_class = "ws-btn "
        # To maintain previous functionality, apply the equivalent active_ class to the focused_ workspace.
        if self.status.value == WorkspaceStatus.FOCUSED_POPULATED:
            button_class += WorkspaceStatus.ACTIVE_POPULATED + " " + self.status.value
        elif self.status.value == WorkspaceStatus.FOCUSED_EMPTY:
            button_class += WorkspaceStatus.ACTIVE_EMPTY + " " + self.status.value
        else:
            button_class += self.status.value
        self.setProperty("class", button_class)
        refresh_widget_style(self)
        # Even though the label class name, we still need to run this on the label to catch any different stylings we want to do when the status changes
        refresh_widget_style(self.text_label)

    def _update_label(self):
        replacements = {
            "name": str(self.workspace_name or ""),
            "display_name": str(self.display_name or ""),
        }
        # Label priority: YASB config -> display_name from GlazeWM -> name from GlazeWM
        populated_label = self.populated_label or self.display_name or self.workspace_name
        empty_label = self.empty_label or self.display_name or self.workspace_name
        active_populated_label = self.active_populated_label or self.display_name or self.workspace_name
        active_empty_label = self.active_empty_label or self.display_name or self.workspace_name
        # have focused_ label variants fall back to equivalent active_ label variants if they are set (preserves previous functionality)
        focused_populated_label = (
            self.focused_populated_label or self.active_populated_label or self.display_name or self.workspace_name
        )
        focused_empty_label = (
            self.focused_empty_label or self.active_empty_label or self.display_name or self.workspace_name
        )
        # Replace placeholders if any exist
        populated_label = populated_label.format_map(replacements)
        empty_label = empty_label.format_map(replacements)
        active_populated_label = active_populated_label.format_map(replacements)
        active_empty_label = active_empty_label.format_map(replacements)
        focused_populated_label = focused_populated_label.format_map(replacements)
        focused_empty_label = focused_empty_label.format_map(replacements)
        if self.status == WorkspaceStatus.FOCUSED_POPULATED:
            self.text_label.setText(focused_populated_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.FOCUSED_EMPTY:
            self.text_label.setText(focused_empty_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.ACTIVE_POPULATED:
            self.text_label.setText(active_populated_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.ACTIVE_EMPTY:
            self.text_label.setText(active_empty_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.POPULATED:
            self.text_label.setText(populated_label)
            self.setHidden(False)
        elif self.status == WorkspaceStatus.EMPTY:
            self.text_label.setText(empty_label)
        else:
            logger.warning(f"Unknown workspace status: {self.status}")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._activate_workspace()

    def _activate_workspace(self):
        self.glazewm_client.activate_workspace(self.workspace_name)

    def _update_status(self):
        if self.is_displayed:
            if self.is_focused:
                if self.workspace_window_count > 0:
                    self.status = WorkspaceStatus.FOCUSED_POPULATED
                else:
                    self.status = WorkspaceStatus.FOCUSED_EMPTY
            elif self.workspace_window_count > 0:
                self.status = WorkspaceStatus.ACTIVE_POPULATED
            else:
                self.status = WorkspaceStatus.ACTIVE_EMPTY
        elif self.workspace_window_count > 0:
            self.status = WorkspaceStatus.POPULATED
        else:
            self.status = WorkspaceStatus.EMPTY

    def _get_all_windows_in_workspace(self) -> list[Window] | None:
        windows = self.windows

        if self.parent_widget.workspace_app_icons["hide_floating"]:
            return [window for window in windows if not window.is_floating]
        return windows

    def _get_all_icons_in_workspace(self) -> list[QPixmap] | None:
        windows = self._get_all_windows_in_workspace()
        self._unique_pids = set()
        return {window.handle: self._get_app_icon(window) for window in windows}

    def _get_app_icon(self, window: Window, ignore_cache: bool = False) -> QPixmap | None:
        try:
            hwnd = window.handle
            process = get_process_info(hwnd)
            pid = process["pid"]

            if self.parent_widget.workspace_app_icons["hide_duplicates"]:
                if pid not in self._unique_pids:
                    self._unique_pids.add(pid)
                else:
                    return None

            self.dpi = self.screen().devicePixelRatio()
            cache_key = (hwnd, pid, self.dpi)

            if cache_key in self.parent_widget.icon_cache and not ignore_cache:
                return self.parent_widget.icon_cache[cache_key]
            else:
                icon_img = get_window_icon(hwnd)
                if icon_img:
                    icon_img = icon_img.resize(
                        (
                            int(self.parent_widget.workspace_app_icons["size"] * self.dpi),
                            int(self.parent_widget.workspace_app_icons["size"] * self.dpi),
                        ),
                        Image.LANCZOS,
                    ).convert("RGBA")
                    qimage = QImage(icon_img.tobytes(), icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
                    pixmap = QPixmap.fromImage(qimage)
                    pixmap.setDevicePixelRatio(self.dpi)
                    pixmap.glazewm_id = window.id
                    self.parent_widget.icon_cache[cache_key] = pixmap
                    return pixmap
                else:
                    return None

        except Exception:
            if DEBUG:
                logging.exception(f"Failed to get icons for window with HWND {hwnd}")
            return None

    def _update_icons(self):
        self.icons = self._get_all_icons_in_workspace()

        if (
            not self.parent_widget.workspace_app_icons["enabled_active"]
            and self.status == WorkspaceStatus.ACTIVE_POPULATED
        ):
            icons_list = []
        elif (
            (
                not self.parent_widget.workspace_app_icons["enabled_active"]
                and self.parent_widget.workspace_app_icons["enabled_focused"] is None
            )
            or self.parent_widget.workspace_app_icons["enabled_focused"] is False
        ) and self.status == WorkspaceStatus.FOCUSED_POPULATED:
            icons_list = []
        elif (
            not self.parent_widget.workspace_app_icons["enabled_populated"] and self.status == WorkspaceStatus.POPULATED
        ):
            icons_list = []
        else:
            icons_list = [icon for icon in self.icons.values() if icon is not None]
            if self.parent_widget.workspace_app_icons["max_icons"] > 0:
                icons_list = icons_list[: self.parent_widget.workspace_app_icons["max_icons"]]

        prev_icon_count = len(self.icon_labels)
        # Remove extra QLabel widgets if there are more than needed
        for extra_label in self.icon_labels[len(icons_list) :]:
            self.button_layout.removeWidget(extra_label)
            extra_label.setParent(None)
        self.icon_labels = self.icon_labels[: len(icons_list)]

        # Add or update icons
        for index, icon in enumerate(icons_list):
            if index < len(self.icon_labels):
                self.icon_labels[index].setPixmap(icon)
            else:
                icon_label = QLabel()
                icon_label.setProperty("class", f"icon icon-{index + 1}")
                icon_label.setPixmap(icon)
                self.button_layout.addWidget(icon_label)
                add_shadow(icon_label, self.parent_widget.label_shadow)
                self.icon_labels.append(icon_label)

        curr_icon_count = len(icons_list)

        if self.parent_widget.workspace_app_icons["hide_label"] and len(self.icon_labels) > 0:
            self.text_label.hide()
        else:
            self.text_label.show()

        if curr_icon_count < prev_icon_count:
            if self.parent_widget.animation and self._animation_initialized:
                self._animate_buttons()

    def _animate_buttons(self, duration=200, step=30):
        # Store the initial width if not already stored (to enable reverse animations)
        if not hasattr(self, "_initial_width"):
            self._initial_width = self.width()

        self._current_width = self.width()
        target_width = self.sizeHint().width()
        if (
            not self.parent_widget.workspace_app_icons["enabled_active"]
            and (
                self.parent_widget.workspace_app_icons["enabled_focused"] == None
                or not self.parent_widget.workspace_app_icons["enabled_focused"]
            )
            and self.parent_widget.workspace_app_icons["enabled_populated"]
        ):
            for icon_label in self.icon_labels:
                target_width += icon_label.sizeHint().width()

        step_duration = int(duration / step)
        width_increment = (target_width - self._current_width) / step
        self._current_step = 0

        def update_width():
            if self._current_step < step:
                self._current_width += width_increment
                self.setFixedWidth(int(self._current_width))
                self._current_step += 1
            else:
                # Animation done: stop timer and set to target exactly
                self._animation_timer.stop()
                self.setMinimumWidth(target_width)
                self.setMaximumWidth(16777215)

        # Stop any existing timer before starting a new one to prevent conflicts
        if hasattr(self, "_animation_timer") and self._animation_timer.isActive():
            self._animation_timer.stop()

        # Parent the timer to the widget to avoid potential memory leaks
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(update_width)
        self._animation_timer.start(step_duration)


class GlazewmWorkspacesWidget(BaseWidget):
    validation_schema: dict[str, Any] = VALIDATION_SCHEMA

    def __init__(
        self,
        offline_label: str,
        populated_label: str,
        empty_label: str,
        active_populated_label: str,
        active_empty_label: str,
        focused_populated_label: str,
        focused_empty_label: str,
        hide_empty_workspaces: bool,
        hide_if_offline: bool,
        container_padding: dict,
        glazewm_server_uri: str,
        enable_scroll_switching: bool,
        reverse_scroll_direction: bool,
        container_shadow: dict[str, Any],
        btn_shadow: dict[str, Any],
        app_icons: dict,
        animation: bool,
        label_shadow: dict = None,
    ):
        super().__init__(class_name="glazewm-workspaces")
        self.label_offline = offline_label
        self.populated_label = populated_label
        self.empty_label = empty_label
        self.active_populated_label = active_populated_label
        self.active_empty_label = active_empty_label
        self.focused_populated_label = focused_populated_label
        self.focused_empty_label = focused_empty_label
        self.glazewm_server_uri = glazewm_server_uri
        self.hide_empty_workspaces = hide_empty_workspaces
        self.hide_if_offline = hide_if_offline
        self._padding = container_padding
        self.container_shadow = container_shadow
        self.btn_shadow = btn_shadow
        self.workspaces: dict[str, GlazewmWorkspaceButton] = {}
        self.monitor_handle: int | None = None
        self._enable_scroll_switching = enable_scroll_switching
        self._reverse_scroll_direction = reverse_scroll_direction
        self.workspace_container_layout = QHBoxLayout()
        self.workspace_container_layout.setSpacing(0)
        self.workspace_container_layout.setContentsMargins(
            self._padding["left"],
            self._padding["top"],
            self._padding["right"],
            self._padding["bottom"],
        )

        self.workspace_container = QFrame()
        self.workspace_container.setLayout(self.workspace_container_layout)
        self.workspace_container.setProperty("class", "widget-container")
        self.workspace_container.setVisible(False)

        self.offline_text = QLabel(self.label_offline)
        self.offline_text.setProperty("class", "offline-status")

        add_shadow(self.workspace_container, self.container_shadow)

        self.widget_layout.addWidget(self.offline_text)
        self.widget_layout.addWidget(self.workspace_container)

        self.glazewm_client = GlazewmClient(
            self.glazewm_server_uri,
            [
                "sub -e workspace_activated workspace_deactivated workspace_updated focus_changed focused_container_moved",
                "query monitors",
            ],
        )
        self.glazewm_client.glazewm_connection_status.connect(self._update_connection_status)  # type: ignore
        self.glazewm_client.workspaces_data_processed.connect(self._update_workspaces)  # type: ignore
        self.icon_cache = dict()
        self.workspace_app_icons = app_icons
        self.animation = animation
        self.label_shadow = label_shadow
        self.workspace_app_icons_enabled = (
            self.workspace_app_icons["enabled_populated"]
            or self.workspace_app_icons["enabled_active"]
            or self.workspace_app_icons["enabled_focused"]
        )

    @override
    def showEvent(self, a0: QShowEvent | None):
        super().showEvent(a0)
        self.monitor_handle = get_monitor_hwnd(int(QWidget.winId(self)))
        self.glazewm_client.connect()

    @pyqtSlot(bool)
    def _update_connection_status(self, status: bool):
        self.workspace_container.setVisible(status)
        self.offline_text.setVisible(not status if not self.hide_if_offline else False)

    @pyqtSlot(list)
    def _update_workspaces(self, message: list[Monitor]):
        # Find the target monitor
        current_mon = next((m for m in message if m.hwnd == self.monitor_handle), None)
        if not current_mon:
            return
        for workspace in current_mon.workspaces:
            # Get or create workspace button if it's not present
            if (btn := self.workspaces.get(workspace.name)) is None:
                if self.workspace_app_icons_enabled:
                    btn = self.workspaces[workspace.name] = GlazewmWorkspaceButtonWithIcons(
                        workspace.name,
                        self.glazewm_client,
                        parent_widget=self,
                        display_name=workspace.display_name,
                        populated_label=self.populated_label,
                        empty_label=self.empty_label,
                        active_populated_label=self.active_populated_label,
                        active_empty_label=self.active_empty_label,
                        focused_populated_label=self.focused_populated_label,
                        focused_empty_label=self.focused_empty_label,
                        windows=workspace.windows,
                    )
                else:
                    btn = self.workspaces[workspace.name] = GlazewmWorkspaceButton(
                        workspace.name,
                        self.glazewm_client,
                        display_name=workspace.display_name,
                        populated_label=self.populated_label,
                        empty_label=self.empty_label,
                        active_populated_label=self.active_populated_label,
                        active_empty_label=self.active_empty_label,
                        focused_populated_label=self.focused_populated_label,
                        focused_empty_label=self.focused_empty_label,
                    )
                add_shadow(btn, self.btn_shadow)

            # Update workspace state
            btn.workspace_name = workspace.name
            btn.display_name = workspace.display_name
            btn.workspace_window_count = workspace.num_windows
            btn.is_displayed = workspace.is_displayed
            btn.is_focused = workspace.focus
            if self.workspace_app_icons_enabled:
                btn.windows = workspace.windows

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
            btn.update_button()

    def _get_active_workspace(self) -> GlazewmWorkspaceButton | None:
        for btn in self.workspaces.values():
            if btn.status in (WorkspaceStatus.ACTIVE_EMPTY, WorkspaceStatus.ACTIVE_POPULATED):
                return btn
        return None

    def wheelEvent(self, event: QWheelEvent):
        if not self._enable_scroll_switching:
            return
        direction = event.angleDelta().y()
        if self._reverse_scroll_direction:
            direction = -direction
        if direction < 0:
            self.glazewm_client.focus_next_workspace()
        elif direction > 0:
            self.glazewm_client.focus_prev_workspace()
