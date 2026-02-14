import logging
import re
from enum import StrEnum, auto
from typing import override

from PIL import Image
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QCursor, QImage, QMouseEvent, QPixmap, QShowEvent, QWheelEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from core.utils.utilities import add_shadow, refresh_widget_style
from core.utils.widgets.glazewm.client import GlazewmClient, Monitor, Window, Workspace
from core.utils.win32.app_icons import get_window_icon
from core.utils.win32.utilities import get_monitor_hwnd, get_process_info
from core.validation.widgets.glazewm.workspaces import GlazewmWorkspacesConfig
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
        config: GlazewmWorkspacesConfig,
        display_name: str | None = None,
    ):
        super().__init__()
        self.setProperty("class", "ws-btn")
        self.glazewm_client = client
        self.config = config
        self.workspace_name = workspace_name
        self.display_name = display_name
        self.monitor_exclusive = config.monitor_exclusive
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
        is_populated = self.workspace_window_count > 0
        if self.is_focused:
            self.status = WorkspaceStatus.FOCUSED_POPULATED if is_populated else WorkspaceStatus.FOCUSED_EMPTY
        elif self.monitor_exclusive and self.is_displayed:
            self.status = WorkspaceStatus.ACTIVE_POPULATED if is_populated else WorkspaceStatus.ACTIVE_EMPTY
        else:
            self.status = WorkspaceStatus.POPULATED if is_populated else WorkspaceStatus.EMPTY

    def _update_label(self):
        replacements = {
            "name": str(self.workspace_name or ""),
            "display_name": str(self.display_name or ""),
        }
        # Label priority: YASB config -> display_name from GlazeWM -> name from GlazeWM
        populated_label = self.config.populated_label or self.display_name or self.workspace_name
        empty_label = self.config.empty_label or self.display_name or self.workspace_name
        active_populated_label = self.config.active_populated_label or self.display_name or self.workspace_name
        active_empty_label = self.config.active_empty_label or self.display_name or self.workspace_name
        # have focused_ label variants fall back to equivalent active_ label variants if they are set (preserves previous functionality)
        focused_populated_label = (
            self.config.focused_populated_label or active_populated_label or self.display_name or self.workspace_name
        )
        focused_empty_label = (
            self.config.focused_empty_label or active_empty_label or self.display_name or self.workspace_name
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
        config: GlazewmWorkspacesConfig,
        display_name: str | None = None,
        windows: list[Window] | None = None,
    ):
        super().__init__()
        self.setProperty("class", "ws-btn")
        self.glazewm_client = client
        self.workspace_name = workspace_name
        self.display_name = display_name
        self.parent_widget = parent_widget
        self.config = config
        self.monitor_exclusive = config.monitor_exclusive
        self.is_displayed = False
        self.is_focused = False
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
        add_shadow(self.text_label, self.config.label_shadow.model_dump())

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
        populated_label = self.config.populated_label or self.display_name or self.workspace_name
        empty_label = self.config.empty_label or self.display_name or self.workspace_name
        active_populated_label = self.config.active_populated_label or self.display_name or self.workspace_name
        active_empty_label = self.config.active_empty_label or self.display_name or self.workspace_name
        # have focused_ label variants fall back to equivalent active_ label variants if they are set (preserves previous functionality)
        focused_populated_label = (
            self.config.focused_populated_label or active_populated_label or self.display_name or self.workspace_name
        )
        focused_empty_label = (
            self.config.focused_empty_label or active_empty_label or self.display_name or self.workspace_name
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
        is_populated = self.workspace_window_count > 0
        if self.is_focused:
            self.status = WorkspaceStatus.FOCUSED_POPULATED if is_populated else WorkspaceStatus.FOCUSED_EMPTY
        elif self.monitor_exclusive and self.is_displayed:
            self.status = WorkspaceStatus.ACTIVE_POPULATED if is_populated else WorkspaceStatus.ACTIVE_EMPTY
        else:
            self.status = WorkspaceStatus.POPULATED if is_populated else WorkspaceStatus.EMPTY

    def _get_all_windows_in_workspace(self) -> list[Window]:
        windows = self.windows or []

        if self.config.app_icons.hide_floating:
            return [window for window in windows if not window.is_floating]
        return windows

    def _get_all_icons_in_workspace(self) -> dict[int, QPixmap | None]:
        windows = self._get_all_windows_in_workspace()
        self._unique_pids = set()
        return {window.handle: self._get_app_icon(window) for window in windows}

    def _get_app_icon(self, window: Window, ignore_cache: bool = False) -> QPixmap | None:
        try:
            hwnd = window.handle
            process = get_process_info(hwnd)
            pid = process["pid"]

            if self.config.app_icons.hide_duplicates:
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
                            int(self.config.app_icons.size * self.dpi),
                            int(self.config.app_icons.size * self.dpi),
                        ),
                        Image.LANCZOS,
                    ).convert("RGBA")
                    qimage = QImage(
                        icon_img.tobytes(),
                        icon_img.width,
                        icon_img.height,
                        QImage.Format.Format_RGBA8888,
                    )
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

        if not self.config.app_icons.enabled_active and self.status == WorkspaceStatus.ACTIVE_POPULATED:
            icons_list = []
        elif (
            (not self.config.app_icons.enabled_active and self.config.app_icons.enabled_focused is None)
            or self.config.app_icons.enabled_focused is False
        ) and self.status == WorkspaceStatus.FOCUSED_POPULATED:
            icons_list = []
        elif not self.config.app_icons.enabled_populated and self.status == WorkspaceStatus.POPULATED:
            icons_list = []
        else:
            icons_list = [icon for icon in self.icons.values() if icon is not None]
            if self.config.app_icons.max_icons > 0:
                icons_list = icons_list[: self.config.app_icons.max_icons]

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
                add_shadow(icon_label, self.config.label_shadow.model_dump())
                self.icon_labels.append(icon_label)

        curr_icon_count = len(icons_list)

        if self.config.app_icons.hide_label and len(self.icon_labels) > 0:
            self.text_label.hide()
        else:
            self.text_label.show()

        if curr_icon_count < prev_icon_count:
            if self.config.animation and self._animation_initialized:
                self._animate_buttons()

    def _animate_buttons(self, duration=200, step=30):
        # Store the initial width if not already stored (to enable reverse animations)
        if not hasattr(self, "_initial_width"):
            self._initial_width = self.width()

        self._current_width = self.width()
        target_width = self.sizeHint().width()
        if (
            not self.config.app_icons.enabled_active
            and (self.config.app_icons.enabled_focused == None or not self.config.app_icons.enabled_focused)
            and self.config.app_icons.enabled_populated
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
    validation_schema = GlazewmWorkspacesConfig

    def __init__(self, config: GlazewmWorkspacesConfig):
        super().__init__(class_name="glazewm-workspaces")
        self.config = config
        self.workspaces: dict[str, GlazewmWorkspaceButton | GlazewmWorkspaceButtonWithIcons] = {}

        self.monitor_handle: int | None = None
        self.workspace_container_layout = QHBoxLayout()
        self.workspace_container_layout.setSpacing(0)
        self.workspace_container_layout.setContentsMargins(0, 0, 0, 0)

        self.workspace_container = QFrame()
        self.workspace_container.setLayout(self.workspace_container_layout)
        self.workspace_container.setProperty("class", "widget-container")
        self.workspace_container.setVisible(False)

        self.offline_text = QLabel(self.config.offline_label)
        self.offline_text.setProperty("class", "offline-status")

        add_shadow(self.workspace_container, self.config.container_shadow.model_dump())

        self.widget_layout.addWidget(self.offline_text)
        self.widget_layout.addWidget(self.workspace_container)

        self.glazewm_client = GlazewmClient(
            self.config.glazewm_server_uri,
            [
                "sub -e workspace_activated workspace_deactivated workspace_updated focus_changed focused_container_moved",
                "query monitors",
            ],
        )
        self.glazewm_client.glazewm_connection_status.connect(self._update_connection_status)  # type: ignore
        self.glazewm_client.workspaces_data_processed.connect(self._update_workspaces)  # type: ignore
        self.icon_cache = dict()
        self.workspace_app_icons_enabled = (
            self.config.app_icons.enabled_populated
            or self.config.app_icons.enabled_active
            or self.config.app_icons.enabled_focused
        )

    @override
    def showEvent(self, a0: QShowEvent | None):
        super().showEvent(a0)
        self.monitor_handle = get_monitor_hwnd(int(QWidget.winId(self)))
        self.glazewm_client.connect()

    @pyqtSlot(bool)
    def _update_connection_status(self, status: bool):
        self.workspace_container.setVisible(status)
        self.offline_text.setVisible(not status if not self.config.hide_if_offline else False)

    @pyqtSlot(list)
    def _update_workspaces(self, message: list[Monitor]):
        current_mon = next((m for m in message if m.hwnd == self.monitor_handle), None)
        if not current_mon:
            return

        global_focused_ws: str | None = None
        all_workspaces: dict[str, Workspace] = {}

        for mon in message:
            for workspace in mon.workspaces:
                all_workspaces[workspace.name] = workspace
                if workspace.focus:
                    global_focused_ws = workspace.name

        if self.config.monitor_exclusive:
            workspace_source = {workspace.name: workspace for workspace in current_mon.workspaces}
        else:
            workspace_source = {workspace.name: workspace for workspace in all_workspaces.values()}

        for workspace in workspace_source.values():
            if (btn := self.workspaces.get(workspace.name)) is None:
                if self.workspace_app_icons_enabled:
                    btn = self.workspaces[workspace.name] = GlazewmWorkspaceButtonWithIcons(
                        workspace.name,
                        self.glazewm_client,
                        parent_widget=self,
                        config=self.config,
                        display_name=workspace.display_name,
                        windows=workspace.windows,
                    )
                else:
                    btn = self.workspaces[workspace.name] = GlazewmWorkspaceButton(
                        workspace.name,
                        self.glazewm_client,
                        config=self.config,
                        display_name=workspace.display_name,
                    )
                add_shadow(btn, self.config.btn_shadow.model_dump())

            btn.monitor_exclusive = self.config.monitor_exclusive
            btn.workspace_name = workspace.name
            btn.display_name = workspace.display_name
            btn.workspace_window_count = workspace.num_windows
            btn.is_displayed = workspace.is_displayed
            btn.is_focused = btn.workspace_name == global_focused_ws if global_focused_ws else workspace.focus
            if self.workspace_app_icons_enabled:
                btn.windows = workspace.windows

        for i, ws_name in enumerate(sorted(self.workspaces.keys(), key=natural_sort_key)):
            if self.workspace_container_layout.indexOf(self.workspaces[ws_name]) != i:
                self.workspace_container_layout.insertWidget(i, self.workspaces[ws_name])

        current_ws_names = set(workspace_source.keys())

        for btn in self.workspaces.values():
            btn.monitor_exclusive = self.config.monitor_exclusive
            is_current_ipc_workspace = btn.workspace_name in current_ws_names

            if is_current_ipc_workspace:
                workspace = workspace_source[btn.workspace_name]
                btn.display_name = workspace.display_name
                btn.workspace_window_count = workspace.num_windows
                btn.is_displayed = workspace.is_displayed
                btn.is_focused = btn.workspace_name == global_focused_ws if global_focused_ws else workspace.focus
                if self.workspace_app_icons_enabled:
                    btn.windows = workspace.windows
            else:
                workspace = all_workspaces.get(btn.workspace_name)
                btn.is_displayed = False
                btn.workspace_window_count = 0
                btn.is_focused = False
                if self.workspace_app_icons_enabled:
                    btn.windows = []

            is_focused = btn.is_focused

            if not self.config.monitor_exclusive:
                if is_current_ipc_workspace or is_focused:
                    btn.setHidden(False)
                else:
                    btn.setHidden(True)
            else:
                if is_current_ipc_workspace:
                    btn.setHidden(False)
                else:
                    btn.setHidden(True)

            btn.update_button()

    def _get_active_workspace(
        self,
    ) -> GlazewmWorkspaceButton | GlazewmWorkspaceButtonWithIcons | None:
        for btn in self.workspaces.values():
            if btn.status in (
                WorkspaceStatus.ACTIVE_EMPTY,
                WorkspaceStatus.ACTIVE_POPULATED,
            ):
                return btn
        return None

    def wheelEvent(self, event: QWheelEvent):
        if not self.config.enable_scroll_switching:
            return
        direction = event.angleDelta().y()
        if self.config.reverse_scroll_direction:
            direction = -direction
        if direction < 0:
            if self.config.monitor_exclusive:
                self.glazewm_client.focus_next_workspace()
            else:
                self.glazewm_client.focus_next_workspace_global()
        elif direction > 0:
            if self.config.monitor_exclusive:
                self.glazewm_client.focus_prev_workspace()
            else:
                self.glazewm_client.focus_prev_workspace_global()
