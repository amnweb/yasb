import logging
import re
from collections.abc import Callable
from enum import StrEnum, auto
from functools import partial
from typing import override

from PyQt6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation, Qt, pyqtSlot
from PyQt6.QtGui import QMouseEvent, QPixmap, QShowEvent, QWheelEvent
from PyQt6.QtWidgets import QWIDGETSIZE_MAX, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from core.utils.icons.service import IconService, WindowIcon
from core.utils.utilities import refresh_widget_style
from core.utils.win32.utils import get_process_info, get_widget_monitor_hwnd
from core.validation.widgets.glazewm.workspaces import GlazewmWorkspacesConfig
from core.widgets.base import BaseWidget
from core.widgets.services.glazewm.client import GlazewmClient, Monitor, Window, Workspace

logger = logging.getLogger("glazewm_workspaces")


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


def animate_width(widget: QWidget, start: int, end: int, duration: int, on_finished: Callable[[], None] | None = None):
    """Animate a widget's maximum width, like the taskbar animates its buttons."""
    animation = QPropertyAnimation(widget, b"maximumWidth", widget)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setDuration(duration)
    animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def finished():
        widget.setProperty("ws_animation", None)
        widget.setMaximumWidth(QWIDGETSIZE_MAX)
        if on_finished:
            on_finished()

    animation.finished.connect(finished)
    widget.setProperty("ws_animation", animation)
    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


class GlazewmWorkspaceButton(QPushButton):
    def __init__(
        self,
        workspace_name: str,
        client: GlazewmClient,
        config: GlazewmWorkspacesConfig,
        display_name: str | None = None,
        parent_widget: QWidget | None = None,
    ):
        super().__init__(parent=parent_widget)
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
        self.setSizePolicy(QSizePolicy.Policy.Fixed, self.sizePolicy().verticalPolicy())
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
            logger.warning("Unknown workspace status: %s", self.status)


class GlazewmWorkspaceButtonWithIcons(QFrame):
    def __init__(
        self,
        workspace_name: str,
        client: GlazewmClient,
        parent_widget: GlazewmWorkspacesWidget,
        config: GlazewmWorkspacesConfig,
        display_name: str | None = None,
        windows: list[Window] | None = None,
    ):
        super().__init__(parent=parent_widget)
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
        self.workspace_window_count = 0
        self.windows = windows
        self._unique_pids: set[int] = set()

        self.setSizePolicy(QSizePolicy.Policy.Fixed, self.sizePolicy().verticalPolicy())

        self.button_layout = QHBoxLayout(self)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(0)

        self.text_label = QLabel(self.workspace_name, self)
        self.text_label.setProperty("class", "label")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.button_layout.addWidget(self.text_label)

        self.icons: dict[int, QPixmap | None] = {}
        # Keyed by window handle so an icon keeps its label when windows are added/removed
        self.icon_labels: dict[int, QLabel] = {}
        self.update_button()

    def update_button(self):
        # A button that is just appearing grows as a whole, so don't animate its icons too
        was_visible = self.isVisible()
        self._update_status()
        self._update_label()
        self.update_icons(animate=was_visible)
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
            logger.warning("Unknown workspace status: %s", self.status)

    @override
    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
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

    def _get_app_icon(self, window: Window) -> QPixmap | None:
        hwnd = window.handle
        try:
            process = get_process_info(hwnd)
            pid = process["pid"]

            if self.config.app_icons.hide_duplicates:
                if pid not in self._unique_pids:
                    self._unique_pids.add(pid)
                else:
                    return None

            screen = self.screen()
            if screen is None:
                return None
            self.dpi = screen.devicePixelRatio()
            return IconService.instance().get_icon(WindowIcon(hwnd), self.config.app_icons.size, self.dpi)

        except Exception:
            logging.debug("Failed to get icons for window with HWND %s", hwnd, exc_info=True)
            return None

    def update_icons(self, animate: bool = True):
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
            icons_list = [(hwnd, icon) for hwnd, icon in self.icons.items() if icon is not None]
            if self.config.app_icons.max_icons > 0:
                icons_list = icons_list[: self.config.app_icons.max_icons]

        animate = (
            animate
            and self.config.animation.enabled
            and self.isVisible()
            and not getattr(self.parent_widget, "_initial_population", True)
        )
        wanted = {hwnd for hwnd, _ in icons_list}
        # Windows moved between workspaces jump instead of shrinking out and growing in
        moved: set[int] = getattr(self.parent_widget, "_moved_hwnds", set())
        duration = self.config.animation.duration

        # Remove labels of windows that are gone, a still-growing one immediately like the taskbar does
        for hwnd in [hwnd for hwnd in self.icon_labels if hwnd not in wanted]:
            label = self.icon_labels.pop(hwnd)
            if animate and hwnd not in moved and label.property("ws_animation") is None:
                animate_width(label, label.width(), 0, duration, partial(self._remove_icon, label))
            else:
                self._remove_icon(label)

        # Add new labels and keep them in window order
        previous: QWidget = self.text_label
        for index, (hwnd, icon) in enumerate(icons_list):
            css_class = f"icon icon-{index + 1}"
            label = self.icon_labels.get(hwnd)
            if label is None:
                label = self._add_icon(hwnd, icon, css_class, previous, animate and hwnd not in moved)
            elif label.property("class") != css_class:
                # Replace a label that changed position, Qt doesn't re-apply CSS margins on a class change
                self._remove_icon(label)
                label = self._add_icon(hwnd, icon, css_class, previous, animate=False)
            else:
                label.setPixmap(icon)
            previous = label

        if self.config.app_icons.hide_label and len(self.icon_labels) > 0:
            self.text_label.hide()
        else:
            self.text_label.show()

    def _add_icon(self, hwnd: int, icon: QPixmap, css_class: str, after: QWidget, animate: bool) -> QLabel:
        label = self.icon_labels[hwnd] = QLabel(self)
        label.setProperty("class", css_class)
        label.setPixmap(icon)
        self.button_layout.insertWidget(self.button_layout.indexOf(after) + 1, label)
        if animate:
            label.setFixedWidth(0)
            animate_width(label, 0, label.sizeHint().width(), self.config.animation.duration)
        # Show now so the button's sizeHint() includes the icon right away
        label.show()
        return label

    def _remove_icon(self, label: QLabel) -> None:
        if (running := label.property("ws_animation")) is not None:
            running.stop()
        self.button_layout.removeWidget(label)
        label.hide()
        label.deleteLater()


class GlazewmWorkspacesWidget(BaseWidget):
    validation_schema = GlazewmWorkspacesConfig

    def __init__(self, config: GlazewmWorkspacesConfig):
        super().__init__(class_name="glazewm-workspaces")
        self.config = config
        self.workspaces: dict[str, GlazewmWorkspaceButton | GlazewmWorkspaceButtonWithIcons] = {}
        # Which workspace each window was in on the last update, to spot windows that moved
        self._window_workspaces: dict[int, str] = {}
        self._moved_hwnds: set[int] = set()
        # Skip animating the first batch of buttons so startup doesn't stutter
        self._initial_population = True

        self.monitor_handle: int | None = None
        self.workspace_container_layout = QHBoxLayout()
        self.workspace_container_layout.setSpacing(0)
        self.workspace_container_layout.setContentsMargins(0, 0, 0, 0)
        if self.config.animation.enabled:
            # Grow the container to fit its buttons first, so a growing icon doesn't squeeze the others
            self.workspace_container_layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetMinimumSize)

        self.workspace_container = QFrame(self)
        self.workspace_container.setLayout(self.workspace_container_layout)
        self.workspace_container.setProperty("class", "widget-container")
        self.workspace_container.setVisible(False)

        self.offline_text = QLabel(self.config.offline_label, self)
        self.offline_text.setProperty("class", "offline-status")

        self.widget_layout.addWidget(self.offline_text)
        self.widget_layout.addWidget(self.workspace_container)

        events = "workspace_activated workspace_deactivated workspace_updated focus_changed focused_container_moved"
        if self.config.animation.enabled:
            # Update as soon as a window opens or closes so its icon animates right away
            events += " window_managed window_unmanaged"
        self.glazewm_client = GlazewmClient(
            self.config.glazewm_server_uri,
            [
                f"sub -e {events}",
                "query monitors",
            ],
        )
        self.glazewm_client.glazewm_connection_status.connect(self._update_connection_status)  # type: ignore
        self.glazewm_client.workspaces_data_processed.connect(self._update_workspaces)  # type: ignore
        IconService.instance().icons_changed.connect(self._refresh_icons)
        self.workspace_app_icons_enabled = (
            self.config.app_icons.enabled_populated
            or self.config.app_icons.enabled_active
            or self.config.app_icons.enabled_focused
        )

    def _refresh_icons(self) -> None:
        for btn in self.workspaces.values():
            if isinstance(btn, GlazewmWorkspaceButtonWithIcons):
                btn.update_icons()

    @override
    def showEvent(self, a0: QShowEvent | None):
        super().showEvent(a0)
        self.monitor_handle = get_widget_monitor_hwnd(self)
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

        window_workspaces = {
            window.handle: workspace.name for workspace in all_workspaces.values() for window in workspace.windows
        }
        self._moved_hwnds = {
            hwnd for hwnd, name in window_workspaces.items() if self._window_workspaces.get(hwnd, name) != name
        }
        self._window_workspaces = window_workspaces

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
                        parent_widget=self,
                    )
                # Start hidden so the button grows in instead of popping in
                btn.setHidden(True)

            btn.monitor_exclusive = self.config.monitor_exclusive
            btn.workspace_name = workspace.name
            btn.display_name = workspace.display_name
            btn.workspace_window_count = workspace.num_windows
            btn.is_displayed = workspace.is_displayed
            btn.is_focused = btn.workspace_name == global_focused_ws if global_focused_ws else workspace.focus
            if isinstance(btn, GlazewmWorkspaceButtonWithIcons):
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
                if isinstance(btn, GlazewmWorkspaceButtonWithIcons):
                    btn.windows = workspace.windows
            else:
                workspace = all_workspaces.get(btn.workspace_name)
                btn.is_displayed = False
                btn.workspace_window_count = 0
                btn.is_focused = False
                if isinstance(btn, GlazewmWorkspaceButtonWithIcons):
                    btn.windows = []

            is_focused = btn.is_focused
            # Check before update_button(), which may unhide it
            was_shown = btn.isVisibleTo(self)
            btn.update_button()

            if not self.config.monitor_exclusive:
                visible = is_current_ipc_workspace or is_focused
            else:
                visible = is_current_ipc_workspace
            self._update_button_visibility(btn, visible, was_shown)

        self._initial_population = False

    def _update_button_visibility(self, btn: QWidget, visible: bool, was_shown: bool) -> None:
        """Show/hide a workspace button, growing/shrinking it like the taskbar does."""
        if not self.config.animation.enabled or self._initial_population:
            btn.setHidden(not visible)
            return

        running = btn.property("ws_animation")
        # A button that is mid-animation counts as shown if it is growing in
        shown = running.endValue() != 0 if running is not None else was_shown
        if visible == shown:
            if running is None:
                # Undo update_button() unhiding a button that should stay hidden
                btn.setHidden(not visible)
            return

        # Start from the current width, or from 0 if it was hidden
        if running is not None:
            start = btn.maximumWidth()
            running.stop()
        else:
            start = btn.width() if shown else 0
        btn.setMaximumWidth(start)
        btn.setHidden(False)

        duration = self.config.animation.duration
        if visible:
            animate_width(btn, start, btn.sizeHint().width(), duration)
        else:
            animate_width(btn, start, 0, duration, partial(btn.setHidden, True))

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

    @override
    def wheelEvent(self, a0: QWheelEvent | None) -> None:
        if a0 is None or not self.config.enable_scroll_switching:
            return
        direction = a0.angleDelta().y()
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
