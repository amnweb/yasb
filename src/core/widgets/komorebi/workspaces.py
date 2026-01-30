import logging
from contextlib import suppress
from typing import Dict, List, Literal

from PIL import Image
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QImage, QMouseEvent, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from core.event_enums import KomorebiEvent
from core.event_service import EventService
from core.utils.utilities import add_shadow, refresh_widget_style
from core.utils.widgets.komorebi.animation import KomorebiAnimation
from core.utils.widgets.komorebi.client import KomorebiClient
from core.utils.win32.app_icons import get_window_icon
from core.utils.win32.utilities import get_monitor_hwnd, get_process_info
from core.validation.widgets.komorebi.workspaces import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG

try:
    from core.utils.widgets.komorebi.event_listener import KomorebiEventListener
except ImportError:
    KomorebiEventListener = None
    logging.warning("Failed to load Komorebi Event Listener")

WorkspaceStatus = Literal["EMPTY", "POPULATED", "ACTIVE"]
WORKSPACE_STATUS_EMPTY: WorkspaceStatus = "EMPTY"
WORKSPACE_STATUS_POPULATED: WorkspaceStatus = "POPULATED"
WORKSPACE_STATUS_ACTIVE: WorkspaceStatus = "ACTIVE"


class WorkspaceButton(QPushButton):
    def __init__(
        self,
        workspace_index: int,
        parent_widget: "WorkspaceWidget",
        label: str = None,
        active_label: str = None,
        populated_label: str = None,
        animation: bool = False,
    ):
        super().__init__()
        self._animation_initialized = False
        self.komorebic = KomorebiClient()
        self.workspace_index = workspace_index
        self.parent_widget = parent_widget
        self.status = WORKSPACE_STATUS_EMPTY
        self.setProperty("class", "ws-btn")
        self.default_label = label if label else str(workspace_index + 1)
        self.active_label = active_label if active_label else self.default_label
        self.populated_label = populated_label if populated_label else self.default_label
        self.setText(self.default_label)
        self.clicked.connect(self.activate_workspace)
        self._animation = animation
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.hide()

    def update_visible_buttons(self):
        visible_buttons = [btn for btn in self.parent_widget._workspace_buttons if btn.isVisible()]
        for index, button in enumerate(visible_buttons):
            current_class = button.property("class")
            new_class = " ".join([cls for cls in current_class.split() if not cls.startswith("button-")])
            new_class = f"{new_class} button-{index + 1}"
            button.setProperty("class", new_class)
            button.setStyleSheet("")

    def update_and_redraw(self, status: WorkspaceStatus, lock_width: bool = False):
        # Lock current visual width so style/class changes don't cause a jump
        prev_width = self.width() if lock_width else None
        self.status = status
        self.setProperty("class", f"ws-btn {status.lower()}")
        if status == WORKSPACE_STATUS_ACTIVE:
            self.setText(self.active_label)
        elif status == WORKSPACE_STATUS_POPULATED:
            self.setText(self.populated_label)
        else:
            self.setText(self.default_label)
        refresh_widget_style(self)
        if lock_width and prev_width is not None:
            self.setFixedWidth(prev_width)

    def activate_workspace(self):
        try:
            self.komorebic.activate_workspace(self.parent_widget._komorebi_screen["index"], self.workspace_index)
        except Exception:
            logging.exception(f"Failed to focus workspace at index {self.workspace_index}")


class WorkspaceButtonWithIcons(QFrame):
    def __init__(
        self,
        workspace_index: int,
        parent_widget: "WorkspaceWidget",
        label: str = None,
        active_label: str = None,
        populated_label: str = None,
        animation: bool = False,
    ):
        super().__init__()
        self._animation_initialized = False
        self.komorebic = KomorebiClient()
        self.workspace_index = workspace_index
        self.parent_widget = parent_widget
        self.status = WORKSPACE_STATUS_EMPTY
        self.setProperty("class", "ws-btn")
        self.default_label = label if label else str(workspace_index + 1)
        self.active_label = active_label if active_label else self.default_label
        self.populated_label = populated_label if populated_label else self.default_label
        self._animation = animation
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.button_layout = QHBoxLayout(self)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(0)

        self.text_label = QLabel(self.default_label)
        self.text_label.setProperty("class", "label")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.button_layout.addWidget(self.text_label)
        add_shadow(self.text_label, self.parent_widget._label_shadow)

        self.icons = {}
        self.icon_labels = []
        self.hide()
        self.update_icons()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.activate_workspace()

    def update_visible_buttons(self):
        visible_buttons = [btn for btn in self.parent_widget._workspace_buttons if btn.isVisible()]
        for index, button in enumerate(visible_buttons):
            current_class = button.property("class")
            new_class = " ".join([cls for cls in current_class.split() if not cls.startswith("button-")])
            new_class = f"{new_class} button-{index + 1}"
            button.setProperty("class", new_class)
            button.setStyleSheet("")

    def update_and_redraw(self, status: WorkspaceStatus, lock_width: bool = False):
        prev_width = self.width() if lock_width else None
        self.status = status
        self.setProperty("class", f"ws-btn {status.lower()}")
        if status == WORKSPACE_STATUS_ACTIVE:
            self.text_label.setText(self.active_label)
        elif status == WORKSPACE_STATUS_POPULATED:
            self.text_label.setText(self.populated_label)
        else:
            self.text_label.setText(self.default_label)
        refresh_widget_style(self)
        if lock_width and prev_width is not None:
            self.setFixedWidth(prev_width)

    def update_icons(self, icons: Dict[int, QPixmap] = None, update_width: bool = True):
        if icons:
            self.icons.update(icons)
        else:
            self.icons = self.parent_widget._get_all_icons_in_workspace(self.workspace_index)

        if (
            not self.parent_widget._workspace_app_icons["enabled_active"]
            and self.workspace_index == self.parent_widget._curr_workspace_index
        ):
            icons_list = []
        elif (
            not self.parent_widget._workspace_app_icons["enabled_populated"]
            and self.workspace_index != self.parent_widget._curr_workspace_index
        ):
            icons_list = []
        else:
            icons_list = [icon for icon in self.icons.values() if icon is not None]
            if self.parent_widget._workspace_app_icons["max_icons"] > 0:
                icons_list = icons_list[: self.parent_widget._workspace_app_icons["max_icons"]]

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
                add_shadow(icon_label, self.parent_widget._label_shadow)
                self.icon_labels.append(icon_label)

        curr_icon_count = len(icons_list)

        if self.parent_widget._workspace_app_icons["hide_label"] and len(self.icon_labels) > 0:
            self.text_label.hide()
        else:
            self.text_label.show()

        if curr_icon_count < prev_icon_count and update_width:
            if self.parent_widget._animation and self._animation_initialized:
                # Delegate width animation to central animator (use defaults)
                KomorebiAnimation.animate_width(self)

    def update_icon_by_hwnd(self, hwnd: int):
        if hwnd in self.icons.keys():
            pixmap = self.parent_widget._get_app_icon(hwnd, self.workspace_index, ignore_cache=True)
            if pixmap:
                self.update_icons(icons={hwnd: pixmap})

    def activate_workspace(self):
        try:
            self.komorebic.activate_workspace(self.parent_widget._komorebi_screen["index"], self.workspace_index)
        except Exception:
            logging.exception(f"Failed to focus workspace at index {self.workspace_index}")


class WorkspaceWidget(BaseWidget):
    k_signal_connect = pyqtSignal(dict)
    k_signal_update = pyqtSignal(dict, dict)
    k_signal_disconnect = pyqtSignal()
    validation_schema = VALIDATION_SCHEMA
    event_listener = KomorebiEventListener

    def __init__(
        self,
        label_offline: str,
        label_workspace_btn: str,
        label_workspace_active_btn: str,
        label_workspace_populated_btn: str,
        label_default_name: str,
        label_float_override: str,
        toggle_workspace_layer: dict,
        hide_if_offline: bool,
        label_zero_index: bool,
        hide_empty_workspaces: bool,
        app_icons: dict,
        container_padding: dict,
        animation: bool,
        enable_scroll_switching: bool,
        reverse_scroll_direction: bool,
        btn_shadow: dict = None,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="komorebi-workspaces")
        self._event_service = EventService()
        self._komorebic = KomorebiClient()
        self._label_workspace_btn = label_workspace_btn
        self._label_workspace_active_btn = label_workspace_active_btn
        self._label_workspace_populated_btn = label_workspace_populated_btn
        self._label_default_name = label_default_name
        self._label_float_override = label_float_override
        self._toggle_workspace_layer = toggle_workspace_layer
        self._label_zero_index = label_zero_index
        self._workspace_app_icons = app_icons
        self._workspace_app_icons_enabled = (
            self._workspace_app_icons["enabled_populated"] or self._workspace_app_icons["enabled_active"]
        )
        self._hide_if_offline = hide_if_offline
        self._padding = container_padding
        self._animation = animation
        self._btn_shadow = btn_shadow
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._komorebi_screen = None
        self._komorebi_workspaces = []
        self._prev_workspace_index = None
        self._curr_workspace_index = None
        self._prev_num_windows_in_workspaces = []
        self._curr_num_windows_in_workspaces = []
        self._workspace_buttons: list[WorkspaceButton] = []
        self._hide_empty_workspaces = hide_empty_workspaces
        self._workspace_focus_events = [
            KomorebiEvent.CycleFocusWorkspace.value,
            KomorebiEvent.CycleFocusMonitor.value,
            KomorebiEvent.FocusMonitorWorkspaceNumber.value,
            KomorebiEvent.FocusMonitorNumber.value,
            KomorebiEvent.FocusWorkspaceNumber.value,
            KomorebiEvent.ToggleWorkspaceLayer.value,
        ]
        self._update_buttons_event_watchlist = [
            KomorebiEvent.EnsureWorkspaces.value,
            KomorebiEvent.Manage.value,
            KomorebiEvent.MoveContainerToWorkspaceNumber.value,
            KomorebiEvent.NewWorkspace.value,
            KomorebiEvent.ReloadConfiguration.value,
            KomorebiEvent.SendContainerToMonitorNumber.value,
            KomorebiEvent.SendContainerToWorkspaceNumber.value,
            KomorebiEvent.Unmanage.value,
            KomorebiEvent.WatchConfiguration.value,
            KomorebiEvent.WorkspaceName.value,
            KomorebiEvent.Cloak.value,
        ]
        # Disable default mouse event handling inherited from BaseWidget
        self.mousePressEvent = None
        if self._hide_if_offline:
            self.hide()
        # Status text shown when komorebi state can't be retrieved
        self._offline_text = QLabel()
        self._offline_text.setText(label_offline)
        add_shadow(self._offline_text, self._label_shadow)
        self._offline_text.setProperty("class", "offline-status")
        # Construct container which holds workspace buttons
        self._workspace_container_layout = QHBoxLayout()
        self._workspace_container_layout.setSpacing(0)
        self._workspace_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._workspace_container_layout.addWidget(self._offline_text)
        self._workspace_container = QFrame()
        self._workspace_container.setLayout(self._workspace_container_layout)
        self._workspace_container.setProperty("class", "widget-container")
        add_shadow(self._workspace_container, self._container_shadow)
        self._workspace_container.hide()
        self.widget_layout.addWidget(self._offline_text)
        self.widget_layout.addWidget(self._workspace_container)

        self.float_override_label = QLabel()
        self.float_override_label.setText(self._label_float_override)
        self.float_override_label.setProperty("class", "float-override")
        add_shadow(self.float_override_label, self._label_shadow)
        self.float_override_label.hide()
        self.widget_layout.addWidget(self.float_override_label)

        if self._toggle_workspace_layer["enabled"]:
            self.workspace_layer_label = QLabel()
            self.workspace_layer_label.setProperty("class", "workspace-layer")
            add_shadow(self.workspace_layer_label, self._label_shadow)
            self.widget_layout.addWidget(self.workspace_layer_label)

        self._enable_scroll_switching = enable_scroll_switching
        self._reverse_scroll_direction = reverse_scroll_direction
        self._icon_cache = dict()
        self.dpi = None

        self._register_signals_and_events()

    def _register_signals_and_events(self):
        self.k_signal_connect.connect(self._on_komorebi_connect_event)
        self.k_signal_update.connect(self._on_komorebi_update_event)
        self.k_signal_disconnect.connect(self._on_komorebi_disconnect_event)
        self._event_service.register_event(KomorebiEvent.KomorebiConnect, self.k_signal_connect)
        self._event_service.register_event(KomorebiEvent.KomorebiDisconnect, self.k_signal_disconnect)
        self._event_service.register_event(KomorebiEvent.KomorebiUpdate, self.k_signal_update)
        try:
            self.destroyed.connect(self._on_destroyed)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_destroyed(self, *args):
        try:
            self._event_service.unregister_event(KomorebiEvent.KomorebiConnect, self.k_signal_connect)
            self._event_service.unregister_event(KomorebiEvent.KomorebiDisconnect, self.k_signal_disconnect)
            self._event_service.unregister_event(KomorebiEvent.KomorebiUpdate, self.k_signal_update)
        except Exception:
            pass

    def _reset(self):
        self._komorebi_state = None
        self._komorebi_screen = None
        self._komorebi_workspaces = []
        self._curr_workspace_index = None
        self._prev_workspace_index = None
        self._workspace_buttons = []
        self._clear_container_layout()

    def _on_komorebi_connect_event(self, state: dict) -> None:
        self._reset()
        self._hide_offline_status()
        if self._update_komorebi_state(state):
            self._add_or_update_buttons()
        if self._hide_if_offline:
            self.show()

    def _on_komorebi_disconnect_event(self) -> None:
        self._show_offline_status()
        if self._hide_if_offline:
            self.hide()

    def _on_komorebi_update_event(self, event: dict, state: dict) -> None:
        if self._update_komorebi_state(state):
            # Update icons in workspace buttons (must be done before animation)
            if self._workspace_app_icons_enabled:
                try:
                    if event["type"] in ["ToggleFloat"]:
                        self._workspace_buttons[self._curr_workspace_index].update_icons()
                    if self._has_active_workspace_index_changed():
                        self._workspace_buttons[self._prev_workspace_index].update_icons(update_width=False)
                        self._workspace_buttons[self._curr_workspace_index].update_icons(update_width=False)
                    for i in range(len(self._komorebi_workspaces)):
                        if self._prev_num_windows_in_workspaces[i] != self._curr_num_windows_in_workspaces[i]:
                            self._workspace_buttons[i].update_icons()
                        elif event["type"] in [KomorebiEvent.TitleUpdate.value]:
                            hwnd = event["content"][1]["hwnd"]
                            self._workspace_buttons[i].update_icon_by_hwnd(hwnd)
                except (IndexError, TypeError):
                    pass

            if event["type"] == KomorebiEvent.MoveWorkspaceToMonitorNumber.value:
                if event["content"] != self._komorebi_screen["index"]:
                    workspaces = self._komorebic.get_workspaces(self._komorebi_screen)
                    screen_workspace_indexes = list(map(lambda ws: ws["index"], workspaces))
                    button_workspace_indexes = list(map(lambda ws: ws.workspace_index, self._workspace_buttons))
                    unknown_indexes = set(button_workspace_indexes) - set(screen_workspace_indexes)
                    if len(unknown_indexes) >= 0:
                        for workspace_index in unknown_indexes:
                            self._try_remove_workspace_button(workspace_index)
                self._add_or_update_buttons()
            elif event["type"] in self._workspace_focus_events or self._has_active_workspace_index_changed():
                # send workspace_update event to active_window widgets
                self._event_service.emit_event("workspace_update", event["type"])
                try:
                    prev_workspace_button = self._workspace_buttons[self._prev_workspace_index]
                    self._update_button(prev_workspace_button)
                    new_workspace_button = self._workspace_buttons[self._curr_workspace_index]
                    self._update_button(new_workspace_button)
                except (IndexError, TypeError):
                    self._add_or_update_buttons()
            elif event["type"] in self._update_buttons_event_watchlist:
                self._add_or_update_buttons()

            # Update workspace button if number of windows in workspace changes
            for i in range(len(self._komorebi_workspaces)):
                if (
                    self._prev_num_windows_in_workspaces[i] != self._curr_num_windows_in_workspaces[i]
                    and self._curr_num_windows_in_workspaces[i] == 0
                ):
                    self._update_button(self._workspace_buttons[i])

            # Remove workspace button if workspace is closed
            if event["type"] == KomorebiEvent.CloseWorkspace.value:
                workspaces = self._komorebic.get_workspaces(self._komorebi_screen)
                screen_workspace_indexes = list(map(lambda ws: ws["index"], workspaces))
                button_workspace_indexes = list(map(lambda ws: ws.workspace_index, self._workspace_buttons))
                unknown_indexes = set(button_workspace_indexes) - set(screen_workspace_indexes)
                if len(unknown_indexes) >= 0:
                    for workspace_index in unknown_indexes:
                        self._try_remove_workspace_button(workspace_index)
                    self._add_or_update_buttons()

            if event["type"] == KomorebiEvent.FocusChange.value:
                self._get_workspace_layer(self._curr_workspace_index)

            # Show float override label if float override is active
            if state.get("float_override") and self._label_float_override:
                self.float_override_label.show()
            else:
                self.float_override_label.hide()

        # send workspace_update event to active_window widgets
        if event["type"] in ["MoveWindow", "Show", "Hide", "Destroy"]:
            self._event_service.emit_event("workspace_update", event["type"])

    def _clear_container_layout(self):
        for i in reversed(range(self._workspace_container_layout.count())):
            old_workspace_widget = self._workspace_container_layout.itemAt(i).widget()
            self._workspace_container_layout.removeWidget(old_workspace_widget)
            old_workspace_widget.setParent(None)

    def _update_komorebi_state(self, komorebi_state: dict) -> bool:
        try:
            self._screen_hwnd = get_monitor_hwnd(int(QWidget.winId(self)))
            self._komorebi_state = komorebi_state
            if self._komorebi_state:
                self._komorebi_screen = self._komorebic.get_screen_by_hwnd(self._komorebi_state, self._screen_hwnd)
                self._komorebi_workspaces = self._komorebic.get_workspaces(self._komorebi_screen)
                focused_workspace = self._get_focused_workspace()
                if focused_workspace:
                    self._prev_workspace_index = self._curr_workspace_index
                    self._curr_workspace_index = focused_workspace["index"]

                self._curr_num_windows_in_workspaces = self._curr_num_windows_in_workspaces[
                    : len(self._komorebi_workspaces)
                ] + [0] * (len(self._komorebi_workspaces) - len(self._curr_num_windows_in_workspaces))
                self._prev_num_windows_in_workspaces = self._curr_num_windows_in_workspaces.copy()
                for i in range(len(self._komorebi_workspaces)):
                    windows = self._get_all_windows_in_workspace(i)
                    self._curr_num_windows_in_workspaces[i] = len(windows) if windows else 0

                return True
        except TypeError:
            return False

    def _get_focused_workspace(self):
        return self._komorebic.get_focused_workspace(self._komorebi_screen)

    def _has_active_workspace_index_changed(self):
        return self._prev_workspace_index != self._curr_workspace_index

    def _get_workspace_new_status(self, workspace) -> WorkspaceStatus:
        if self._curr_workspace_index == workspace["index"]:
            return WORKSPACE_STATUS_ACTIVE
        elif self._komorebic.get_num_windows(workspace) > 0:
            return WORKSPACE_STATUS_POPULATED
        else:
            return WORKSPACE_STATUS_EMPTY

    def _get_workspace_layer(self, workspace_index: int) -> None:
        """
        This function is used to get the workspace layer by index. (toggle-workspace-layer)
        Also updates the label's CSS class based on current layer.
        """
        if self._toggle_workspace_layer["enabled"]:
            workspace = self._komorebic.get_workspace_by_index(self._komorebi_screen, workspace_index)
            if workspace and "layer" in workspace:
                # Set base class plus layer-specific class
                layer_type = workspace["layer"].lower()  # Either "tiling" or "floating"
                self.workspace_layer_label.setProperty("class", f"workspace-layer {layer_type}")

                # Set appropriate label text
                if workspace["layer"] == "Tiling":
                    self.workspace_layer_label.setText(self._toggle_workspace_layer["tiling_label"])
                elif workspace["layer"] == "Floating":
                    self.workspace_layer_label.setText(self._toggle_workspace_layer["floating_label"])
                refresh_widget_style(self.workspace_layer_label)
            else:
                self.workspace_layer_label.setProperty("class", "workspace-layer")
                self.workspace_layer_label.setText("")
                refresh_widget_style(self.workspace_layer_label)

    def _update_button(self, workspace_btn: WorkspaceButton) -> None:
        self._refresh_button_labels(workspace_btn)
        workspace_index = workspace_btn.workspace_index
        workspace = self._komorebic.get_workspace_by_index(self._komorebi_screen, workspace_index)
        workspace_status = self._get_workspace_new_status(workspace)
        if self._hide_empty_workspaces and workspace_status == WORKSPACE_STATUS_EMPTY:
            workspace_btn.hide()
        else:
            workspace_btn.show()
            if workspace_btn.status != workspace_status:
                # First-time setup apply state without animation to avoid initial jump
                if not workspace_btn._animation_initialized or not self._animation:
                    workspace_btn.update_and_redraw(workspace_status)
                else:
                    KomorebiAnimation.animate_state_transition(workspace_btn, workspace_status)
            workspace_btn.update_visible_buttons()
        self._get_workspace_layer(workspace_index)
        workspace_btn._animation_initialized = True

    def _refresh_button_labels(self, workspace_btn: WorkspaceButton) -> None:
        # Workspace names can change dynamically (e.g. via `komorebic workspace-name`).
        # Refresh cached button labels so the UI reflects the latest state.
        try:
            default_label, active_label, populated_label = self._get_workspace_label(workspace_btn.workspace_index)
        except Exception:
            return

        if (
            getattr(workspace_btn, "default_label", None) == default_label
            and getattr(workspace_btn, "active_label", None) == active_label
            and getattr(workspace_btn, "populated_label", None) == populated_label
        ):
            return

        workspace_btn.default_label = default_label
        workspace_btn.active_label = active_label
        workspace_btn.populated_label = populated_label
        # Keep current status, only update displayed text.
        workspace_btn.update_and_redraw(workspace_btn.status)

    def _add_or_update_buttons(self) -> None:
        buttons_added = False
        for workspace_index, _ in enumerate(self._komorebi_workspaces):
            try:
                button = self._workspace_buttons[workspace_index]
                self._update_button(button)
            except IndexError:
                button = self._try_add_workspace_button(workspace_index)
                buttons_added = True

        if buttons_added:
            self._workspace_buttons.sort(key=lambda btn: btn.workspace_index)
            self._clear_container_layout()
            for workspace_btn in self._workspace_buttons:
                self._workspace_container_layout.addWidget(workspace_btn)
                self._update_button(workspace_btn)
                add_shadow(workspace_btn, self._btn_shadow)

    def _get_workspace_label(self, workspace_index):
        workspace = self._komorebic.get_workspace_by_index(self._komorebi_screen, workspace_index)
        monitor_index = self._komorebi_screen["index"]
        ws_index = workspace_index if self._label_zero_index else workspace_index + 1
        ws_monitor_index = monitor_index if self._label_zero_index else monitor_index + 1
        ws_raw_name = None
        try:
            ws_raw_name = workspace.get("name") if isinstance(workspace, dict) else None
        except Exception:
            ws_raw_name = None

        ws_name = ws_raw_name or self._label_default_name.format(index=ws_index, monitor_index=ws_monitor_index)
        default_label = self._label_workspace_btn.format(name=ws_name, index=ws_index, monitor_index=ws_monitor_index)
        active_label = self._label_workspace_active_btn.format(
            name=ws_name, index=ws_index, monitor_index=ws_monitor_index
        )
        populated_label = self._label_workspace_populated_btn.format(
            name=ws_name, index=ws_index, monitor_index=ws_monitor_index
        )
        return default_label, active_label, populated_label

    def _try_add_workspace_button(self, workspace_index: int) -> WorkspaceButton:
        workspace_button_indexes = [ws_btn.workspace_index for ws_btn in self._workspace_buttons]
        if workspace_index not in workspace_button_indexes:
            default_label, active_label, populated_label = self._get_workspace_label(workspace_index)
            if self._workspace_app_icons_enabled:
                workspace_btn = WorkspaceButtonWithIcons(
                    workspace_index, self, default_label, active_label, populated_label, self._animation
                )
            else:
                workspace_btn = WorkspaceButton(
                    workspace_index, self, default_label, active_label, populated_label, self._animation
                )
            self._workspace_buttons.append(workspace_btn)
            return workspace_btn

    def _try_remove_workspace_button(self, workspace_index: int) -> None:
        with suppress(IndexError):
            workspace_button = self._workspace_buttons[workspace_index]
            workspace_button.hide()

    def _show_offline_status(self):
        self._offline_text.show()
        self._workspace_container.hide()
        if self._toggle_workspace_layer["enabled"]:
            self.workspace_layer_label.hide()

    def _hide_offline_status(self):
        self._offline_text.hide()
        self._workspace_container.show()
        if self._toggle_workspace_layer["enabled"]:
            self.workspace_layer_label.show()

    def wheelEvent(self, event):
        """Handle mouse wheel events to switch workspaces."""
        if not self._enable_scroll_switching or not self._komorebi_screen:
            return

        delta = event.angleDelta().y()
        # Determine direction (consider reverse_scroll_direction setting)
        direction = -1 if (delta > 0) != self._reverse_scroll_direction else 1

        workspaces = self._komorebic.get_workspaces(self._komorebi_screen)
        if not workspaces:
            return

        current_idx = self._curr_workspace_index
        num_workspaces = len(workspaces)
        next_idx = (current_idx + direction) % num_workspaces
        try:
            self._komorebic.activate_workspace(self._komorebi_screen["index"], next_idx)
        except Exception:
            logging.exception(f"Failed to switch to workspace at index {next_idx}")

    def _get_all_windows_in_workspace(self, workspace_index: int) -> List[dict] | None:
        workspace = self._komorebi_workspaces[workspace_index]
        containers = self._komorebic.get_containers(workspace, get_monocle=True)
        windows_in_workspace = []
        for container in containers:
            windows = self._komorebic.get_windows(container)
            windows_in_workspace.extend(windows)
        floating_windows = [container for container in workspace["floating_windows"]["elements"]]
        if not self._workspace_app_icons["hide_floating"]:
            windows_in_workspace.extend(floating_windows)
        return windows_in_workspace

    def _get_all_icons_in_workspace(self, workspace_index: int) -> List[QPixmap] | None:
        windows_in_workspace = self._get_all_windows_in_workspace(workspace_index)
        self._unique_pids = set()
        pixmaps = {
            window["hwnd"]: self._get_app_icon(window["hwnd"], workspace_index) for window in windows_in_workspace
        }
        try:
            existing_pixmaps = self._workspace_buttons[workspace_index].icons
            for hwnd, pixmap in pixmaps.items():
                if pixmap is None and hwnd in existing_pixmaps:
                    pixmaps[hwnd] = existing_pixmaps[hwnd]
        except IndexError:
            pass
        return pixmaps

    def _get_app_icon(self, hwnd: int, workspace_index: int, ignore_cache: bool = False) -> QPixmap | None:
        try:
            process = get_process_info(hwnd)
            pid = process["pid"]

            if self._workspace_app_icons["hide_duplicates"]:
                if pid not in self._unique_pids:
                    self._unique_pids.add(pid)
                else:
                    return None

            self.dpi = self.screen().devicePixelRatio()
            cache_key = (hwnd, self.dpi)

            if cache_key in self._icon_cache and not ignore_cache:
                icon_img = self._icon_cache[cache_key]
            else:
                icon_img = get_window_icon(hwnd)

            if icon_img:
                icon_img = icon_img.resize(
                    (
                        int(self._workspace_app_icons["size"] * self.dpi),
                        int(self._workspace_app_icons["size"] * self.dpi),
                    ),
                    Image.LANCZOS,
                ).convert("RGBA")
                self._icon_cache[cache_key] = icon_img
                qimage = QImage(icon_img.tobytes(), icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimage)
                pixmap.setDevicePixelRatio(self.dpi)
                return pixmap
            else:
                return None
        except Exception:
            if DEBUG:
                logging.exception(f"Failed to get icons for window with HWND {hwnd}")
            return None
