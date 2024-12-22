import logging
from PyQt6.QtWidgets import QPushButton, QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QCursor
from typing import Literal
from contextlib import suppress
from core.utils.win32.utilities import get_monitor_hwnd
from core.event_service import EventService
from core.event_enums import KomorebiEvent
from core.widgets.base import BaseWidget
from core.utils.komorebi.client import KomorebiClient
from core.validation.widgets.komorebi.workspaces import VALIDATION_SCHEMA

try:
    from core.utils.komorebi.event_listener import KomorebiEventListener
except ImportError:
    KomorebiEventListener = None
    logging.warning("Failed to load Komorebi Event Listener")

WorkspaceStatus = Literal["EMPTY", "POPULATED", "ACTIVE"]
WORKSPACE_STATUS_EMPTY: WorkspaceStatus = "EMPTY"
WORKSPACE_STATUS_POPULATED: WorkspaceStatus = "POPULATED"
WORKSPACE_STATUS_ACTIVE: WorkspaceStatus = "ACTIVE"

class WorkspaceButton(QPushButton):

    def __init__(self, workspace_index: int, parent_widget: 'WorkspaceWidget', label: str = None, active_label: str = None, populated_label: str = None, animation: bool = False):
        super().__init__()
        self.komorebic = KomorebiClient()
        self.workspace_index = workspace_index
        self.parent_widget = parent_widget
        self.status = WORKSPACE_STATUS_EMPTY
        self.setProperty("class", f"ws-btn")
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
            new_class = ' '.join([cls for cls in current_class.split() if not cls.startswith('button-')])
            new_class = f"{new_class} button-{index + 1}"
            button.setProperty("class", new_class)
            button.setStyleSheet('')
 
            
    def update_and_redraw(self, status: WorkspaceStatus):
        self.status = status
        self.setProperty("class", f"ws-btn {status.lower()}")
        if status == WORKSPACE_STATUS_ACTIVE:
            self.setText(self.active_label)
        elif status == WORKSPACE_STATUS_POPULATED:
            self.setText(self.populated_label)
        else:
            self.setText(self.default_label)
        self.setStyleSheet('')


    def activate_workspace(self):
        try:
            self.komorebic.activate_workspace(self.workspace_index)
            if self._animation:
                self.animate_buttons()
        except Exception:
            logging.exception(f"Failed to focus workspace at index {self.workspace_index}")

    def animate_buttons(self, duration=200, step=120):
        #Store the initial width if not already stored
        #we need this to animate the width back to the initial width
        if not hasattr(self, '_initial_width'):
            self._initial_width = self.width()

        self._current_width = self.width()
        target_width = self.sizeHint().width()

        step_duration = int(duration / step)
        width_increment = (target_width - self._current_width) / step

        self._current_step = 0

        def update_width():
            if self._current_step < step:
                self._current_width += width_increment
                self.setFixedWidth(int(self._current_width))
                self._current_step += 1
            else:
                self._animation_timer.stop()
                self.setFixedWidth(target_width)

        # Stop any existing timer before starting a new one to prevent conflicts
        if hasattr(self, '_animation_timer') and self._animation_timer.isActive():
            self._animation_timer.stop()

        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(update_width)
        self._animation_timer.start(step_duration)
        
        
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
            hide_if_offline: bool,
            label_zero_index: bool,
            hide_empty_workspaces: bool,
            container_padding: dict,
            animation: bool
    ):
        super().__init__(class_name="komorebi-workspaces")
        self._event_service = EventService()
        self._komorebic = KomorebiClient()
        self._label_workspace_btn = label_workspace_btn
        self._label_workspace_active_btn = label_workspace_active_btn
        self._label_workspace_populated_btn = label_workspace_populated_btn
        self._label_default_name = label_default_name
        self._label_float_override = label_float_override
        self._label_zero_index = label_zero_index
        self._hide_if_offline = hide_if_offline
        self._padding = container_padding
        self._animation = animation
        self._komorebi_screen = None
        self._komorebi_workspaces = []
        self._prev_workspace_index = None
        self._curr_workspace_index = None
        self._workspace_buttons: list[WorkspaceButton] = []
        self._hide_empty_workspaces = hide_empty_workspaces
        self._workspace_focus_events = [
            KomorebiEvent.CycleFocusWorkspace.value,
            KomorebiEvent.CycleFocusMonitor.value,
            KomorebiEvent.FocusMonitorWorkspaceNumber.value,
            KomorebiEvent.FocusMonitorNumber.value,
            KomorebiEvent.FocusWorkspaceNumber.value
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
            #KomorebiEvent.CloseWorkspace.value
        ]
        # Disable default mouse event handling inherited from BaseWidget
        self.mousePressEvent = None
        if self._hide_if_offline:
            self.hide()
        # Status text shown when komorebi state can't be retrieved
        self._offline_text = QLabel()
        self._offline_text.setText(label_offline)
        self._offline_text.setProperty("class", "offline-status")
        # Construct container which holds workspace buttons
        self._workspace_container_layout: QHBoxLayout = QHBoxLayout()
        self._workspace_container_layout.setSpacing(0)
        self._workspace_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
        self._workspace_container_layout.addWidget(self._offline_text)
        self._workspace_container: QWidget = QWidget()
        self._workspace_container.setLayout(self._workspace_container_layout)
        self._workspace_container.setProperty("class", "widget-container")
        self._workspace_container.hide()
        self.widget_layout.addWidget(self._offline_text)
        self.widget_layout.addWidget(self._workspace_container)
        
        self.float_override_label = QLabel()
        self.float_override_label.setText(self._label_float_override)
        self.float_override_label.setProperty("class", "float-override")
        self.float_override_label.hide()
        self.widget_layout.addWidget(self.float_override_label)
        
        self._register_signals_and_events()

    def _register_signals_and_events(self):
        self.k_signal_connect.connect(self._on_komorebi_connect_event)
        self.k_signal_update.connect(self._on_komorebi_update_event)
        self.k_signal_disconnect.connect(self._on_komorebi_disconnect_event)
        self._event_service.register_event(KomorebiEvent.KomorebiConnect, self.k_signal_connect)
        self._event_service.register_event(KomorebiEvent.KomorebiDisconnect, self.k_signal_disconnect)
        self._event_service.register_event(KomorebiEvent.KomorebiUpdate, self.k_signal_update)

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
            if event['type'] == KomorebiEvent.MoveWorkspaceToMonitorNumber.value:
                if event['content'] != self._komorebi_screen['index']:
                    workspaces = self._komorebic.get_workspaces(self._komorebi_screen)
                    screen_workspace_indexes = list(map(lambda ws: ws['index'], workspaces))
                    button_workspace_indexes = list(map(lambda ws: ws.workspace_index, self._workspace_buttons))
                    unknown_indexes = set(button_workspace_indexes) - set(screen_workspace_indexes)
                    if len(unknown_indexes) >= 0:
                        for workspace_index in unknown_indexes:
                            self._try_remove_workspace_button(workspace_index)
                self._add_or_update_buttons()
            elif event['type'] in self._workspace_focus_events or self._has_active_workspace_index_changed():
                # send workspace_update event to active_window widgets
                self._event_service.emit_event("workspace_update",event['type'])
                try:
                    prev_workspace_button = self._workspace_buttons[self._prev_workspace_index]
                    self._update_button(prev_workspace_button)
                    new_workspace_button = self._workspace_buttons[self._curr_workspace_index]
                    self._update_button(new_workspace_button)
                except (IndexError, TypeError):
                    self._add_or_update_buttons()
            elif event['type'] in self._update_buttons_event_watchlist:
                self._add_or_update_buttons()

            # Remove workspace button if workspace is closed
            if event['type'] == KomorebiEvent.CloseWorkspace.value:
                workspaces = self._komorebic.get_workspaces(self._komorebi_screen)
                screen_workspace_indexes = list(map(lambda ws: ws['index'], workspaces))
                button_workspace_indexes = list(map(lambda ws: ws.workspace_index, self._workspace_buttons))
                unknown_indexes = set(button_workspace_indexes) - set(screen_workspace_indexes)
                if len(unknown_indexes) >= 0:
                    for workspace_index in unknown_indexes:
                        self._try_remove_workspace_button(workspace_index)
                    self._add_or_update_buttons()
                    
            # Show float override label if float override is active
            if state.get('float_override') and self._label_float_override:
                self.float_override_label.show()
            else:
                self.float_override_label.hide()
                
        # send workspace_update event to active_window widgets
        if event['type'] in ['MoveWindow', 'Show', 'Hide', 'Destroy']:
            self._event_service.emit_event("workspace_update",event['type'])

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
                    self._curr_workspace_index = focused_workspace['index']
                return True
        except TypeError:
            return False

    def _get_focused_workspace(self):
        return self._komorebic.get_focused_workspace(self._komorebi_screen)

    def _has_active_workspace_index_changed(self):
        return self._prev_workspace_index != self._curr_workspace_index

    def _get_workspace_new_status(self, workspace) -> WorkspaceStatus:
        if self._curr_workspace_index == workspace['index']:
            return WORKSPACE_STATUS_ACTIVE
        elif self._komorebic.get_num_windows(workspace) > 0:
            return WORKSPACE_STATUS_POPULATED
        else:
            return WORKSPACE_STATUS_EMPTY

    def _update_button(self, workspace_btn: WorkspaceButton) -> None:
        workspace_index = workspace_btn.workspace_index
        workspace = self._komorebic.get_workspace_by_index(self._komorebi_screen, workspace_index)
        workspace_status = self._get_workspace_new_status(workspace)
        if self._hide_empty_workspaces and workspace_status == WORKSPACE_STATUS_EMPTY:
            workspace_btn.hide()
        else:
            workspace_btn.show()
            if workspace_btn.status != workspace_status:
                workspace_btn.update_and_redraw(workspace_status)
                if self._animation:
                    workspace_btn.animate_buttons()
            workspace_btn.update_visible_buttons()

    def _add_or_update_buttons(self) -> None:
        buttons_added = False
        for workspace_index, workspace in enumerate(self._komorebi_workspaces):             
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
                
    def _get_workspace_label(self, workspace_index):
        workspace = self._komorebic.get_workspace_by_index(self._komorebi_screen, workspace_index)
        monitor_index = self._komorebi_screen['index']
        ws_index = workspace_index if self._label_zero_index else workspace_index + 1
        ws_monitor_index = monitor_index if self._label_zero_index else monitor_index + 1
        ws_name = workspace['name'] if workspace['name'] else self._label_default_name.format(
            index=ws_index,
            monitor_index=ws_monitor_index
        )
        default_label = self._label_workspace_btn.format(
            name=ws_name,
            index=ws_index,
            monitor_index=ws_monitor_index
        )
        active_label = self._label_workspace_active_btn.format(
            name=ws_name,
            index=ws_index,
            monitor_index=ws_monitor_index
        )
        populated_label = self._label_workspace_populated_btn.format(
            name=ws_name,
            index=ws_index,
            monitor_index=ws_monitor_index
        )
        return default_label, active_label, populated_label

    def _try_add_workspace_button(self, workspace_index: int) -> WorkspaceButton:
        workspace_button_indexes = [ws_btn.workspace_index for ws_btn in self._workspace_buttons]
        if workspace_index not in workspace_button_indexes:
            default_label, active_label, populated_label = self._get_workspace_label(workspace_index)
            workspace_btn = WorkspaceButton(workspace_index, self, default_label, active_label, populated_label, self._animation)
            self._workspace_buttons.append(workspace_btn)
            return workspace_btn

    def _try_remove_workspace_button(self, workspace_index: int) -> None:
        with suppress(IndexError):
            workspace_button = self._workspace_buttons[workspace_index]
            workspace_button.hide()

    def _show_offline_status(self):
        self._offline_text.show()
        self._workspace_container.hide()

    def _hide_offline_status(self):
        self._offline_text.hide()
        self._workspace_container.show()