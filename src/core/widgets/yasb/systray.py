import json
import logging
import re
import threading
from typing import Any, override
from uuid import UUID

from PyQt6.QtCore import (
    QPoint,
    Qt,
    QThread,
    QTimer,
    pyqtSlot,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLayout,
    QMenu,
    QPushButton,
)

from core.utils.utilities import add_shadow, app_data_path, refresh_widget_style
from core.utils.widgets.systray.systray_monitor import IconData, SystrayMonitor
from core.utils.widgets.systray.systray_widget import DropWidget, IconState, IconWidget
from core.utils.win32.bindings import IsWindow
from core.utils.win32.constants import (
    NIF_GUID,
    NIF_ICON,
    NIF_INFO,
    NIF_MESSAGE,
    NIF_STATE,
    NIF_TIP,
)
from core.utils.win32.utilities import apply_qmenu_style
from core.validation.widgets.yasb.systray import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget

logger = logging.getLogger("systray_widget")

BATTERY_ICON_GUID = UUID("7820ae75-23e3-4229-82c1-e41cb67d5b9c")
VOLUME_ICON_GUID = UUID("7820ae73-23e3-4229-82c1-e41cb67d5b9c")
NETWORK_GUID = UUID("7820ae74-23e3-4229-82c1-e41cb67d5b9c")


class SystrayMonitorThread(QThread):
    """Separate thread to run SystrayMonitorClient"""

    def __init__(self, client: SystrayMonitor):
        super().__init__()
        self.client = client

    @override
    def run(self):
        threading.current_thread().name = "SystrayMonitor"
        logger.debug("Systray thread is starting...")
        self.client.run()


class SystrayWidget(BaseWidget):
    validation_schema: dict[str, Any] = VALIDATION_SCHEMA
    _systray_instance = None
    _systray_thread = None
    _tasks_service_instance = None
    _tasks_thread = None

    @classmethod
    def get_client_instance(cls):
        """
        Since we don't want multiple systray monitors,
        as they will just bounce messages between each other and cause issues,
        we create a single instance of the SystrayMonitor and use it for all widgets.
        """
        if cls._systray_instance is None:
            cls._systray_instance = SystrayMonitor()
            cls._systray_thread = SystrayMonitorThread(cls._systray_instance)

        return (
            cls._systray_instance,
            cls._systray_thread,
        )

    def __init__(
        self,
        class_name: str,
        label_collapsed: str,
        label_expanded: str,
        label_position: str,
        icon_size: int,
        pin_click_modifier: str,
        show_unpinned: bool,
        show_unpinned_button: bool,
        show_battery: bool,
        show_volume: bool,
        show_network: bool,
        tooltip: bool,
        container_padding: dict[str, int],
        container_shadow: dict[str, Any],
        unpinned_shadow: dict[str, Any],
        pinned_shadow: dict[str, Any],
        unpinned_vis_btn_shadow: dict[str, Any],
        btn_shadow: dict[str, Any],
    ):
        super().__init__(class_name=class_name)
        self.label_collapsed = label_collapsed
        self.label_expanded = label_expanded
        self.label_position = label_position if label_position in {"left", "right"} else "left"
        self.icon_size = icon_size
        self.show_unpinned = show_unpinned
        self.show_unpinned_button = show_unpinned_button
        self.container_padding = container_padding
        self.container_shadow = container_shadow
        self.unpinned_shadow = unpinned_shadow
        self.pinned_shadow = pinned_shadow
        self.unpinned_vis_btn_shadow = unpinned_vis_btn_shadow
        self.btn_shadow = btn_shadow

        self.filtered_guids: set[UUID] = set()
        if not show_battery:
            self.filtered_guids.add(BATTERY_ICON_GUID)
        if not show_volume:
            self.filtered_guids.add(VOLUME_ICON_GUID)
        if not show_network:
            self.filtered_guids.add(NETWORK_GUID)

        IconWidget.icon_size = icon_size
        IconWidget.enable_tooltips = tooltip
        IconWidget.pin_modifier_key = {
            "ctrl": Qt.KeyboardModifier.ControlModifier,
            "alt": Qt.KeyboardModifier.AltModifier,
            "shift": Qt.KeyboardModifier.ShiftModifier,
        }.get(pin_click_modifier.lower(), Qt.KeyboardModifier.AltModifier)

        self.icons: list[IconWidget] = []
        self.current_state: dict[str, IconState] = {}
        self.screen_id: str | None = None

        # This timer will check if icons are still valid and have actual process attached
        self.icon_check_timer = QTimer(self)
        self.icon_check_timer.timeout.connect(self.check_icons)
        self.icon_check_timer.start(5000)

        self.sort_timer = QTimer(self)
        self.sort_timer.timeout.connect(self.sort_icons)
        self.sort_timer.setSingleShot(True)

        self.pinned_vis_check_timer = QTimer(self)
        self.pinned_vis_check_timer.timeout.connect(self.update_pinned_widget_visibility)
        self.pinned_vis_check_timer.setSingleShot(True)

        self.widget_container_layout = QHBoxLayout()
        self.widget_container_layout.setSpacing(0)
        self.widget_container_layout.setContentsMargins(
            self.container_padding["left"],
            self.container_padding["top"],
            self.container_padding["right"],
            self.container_padding["bottom"],
        )

        self.widget_container = QFrame(self)
        self.widget_container.setLayout(self.widget_container_layout)
        self.widget_container.setProperty("class", "widget-container")

        self.unpinned_vis_btn = QPushButton(self)
        self.unpinned_vis_btn.setCheckable(True)
        self.unpinned_vis_btn.clicked.connect(self.toggle_unpinned_widget_visibility)
        self.unpinned_vis_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.unpinned_vis_btn.customContextMenuRequested.connect(self.show_context_menu)

        self.unpinned_widget = DropWidget(self)
        self.unpinned_layout = self.unpinned_widget.main_layout

        self.pinned_widget = DropWidget(self)
        self.pinned_widget.setMinimumWidth(16)
        self.pinned_layout = self.pinned_widget.main_layout

        self.pinned_widget.setProperty("class", "pinned-container")
        self.pinned_widget.setProperty("forceshow", False)
        self.unpinned_widget.setProperty("class", "unpinned-container")
        self.unpinned_vis_btn.setProperty("class", "unpinned-visibility-btn")

        self.unpinned_widget.drag_started.connect(self.on_drag_started)
        self.unpinned_widget.drag_ended.connect(self.on_drag_ended)
        self.pinned_widget.drag_started.connect(self.on_drag_started)
        self.pinned_widget.drag_ended.connect(self.on_drag_ended)

        add_shadow(self.widget_container, self.container_shadow)
        add_shadow(self.unpinned_widget, self.unpinned_shadow)
        add_shadow(self.pinned_widget, self.pinned_shadow)
        add_shadow(self.unpinned_vis_btn, self.unpinned_vis_btn_shadow)

        self.widget_container_layout.addWidget(self.unpinned_widget)
        self.widget_container_layout.addWidget(self.pinned_widget)

        if self.label_position == "left":
            self.widget_container_layout.insertWidget(0, self.unpinned_vis_btn)
        else:
            self.widget_container_layout.insertWidget(-1, self.unpinned_vis_btn)

        self.widget_layout.addWidget(self.widget_container)

        self.unpinned_vis_btn.setVisible(self.show_unpinned_button)

        QTimer.singleShot(0, self.setup_client)
        QTimer.singleShot(0, self.set_containers_visibility)

    def show_context_menu(self, pos: QPoint):
        """Show the context menu for the unpinned visibility button"""
        menu = QMenu(self.window())
        menu.setProperty("class", "context-menu")
        apply_qmenu_style(menu)
        menu.setContentsMargins(0, 0, 0, 0)
        menu.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        refresh_action = menu.addAction("Refresh Systray")
        if not refresh_action:
            return
        refresh_action.triggered.connect(self.refresh_systray)

        def _on_menu_about_to_hide():
            from core.global_state import get_autohide_owner_for_widget

            try:
                mgr = get_autohide_owner_for_widget(self)._autohide_manager  # type: ignore
                if mgr._hide_timer:  # type: ignore
                    mgr._hide_timer.start(mgr._autohide_delay)  # type: ignore
            except Exception:
                pass

        menu.aboutToHide.connect(_on_menu_about_to_hide)
        menu.popup(self.unpinned_vis_btn.mapToGlobal(pos))
        try:
            menu.activateWindow()
        except Exception:
            pass

    def refresh_systray(self):
        """Refresh the icons by sending a message to the tray monitor"""
        SystrayMonitor.send_taskbar_created()
        logger.debug("Systray icons refreshed")

    def setup_client(self):
        """Setup the tray monitor client and connect signals"""
        self.load_state()
        systray_client, systray_thread = SystrayWidget.get_client_instance()
        systray_client.icon_modified.connect(self.on_icon_modified)
        systray_client.icon_deleted.connect(self.on_icon_deleted)

        app_inst = QApplication.instance()
        if app_inst is not None:
            app_inst.aboutToQuit.connect(self.save_state)
            app_inst.aboutToQuit.connect(self._cleanup_threads)

        if systray_thread is not None and not systray_thread.isRunning():
            systray_thread.start()
            systray_thread.started.connect(self.on_thread_started)

    @classmethod
    def _cleanup_threads(cls):
        """Cleanup destroy Win32 message loop threads before app quit"""
        try:
            if cls._systray_instance is not None:
                cls._systray_instance.destroy()

            if cls._tasks_service_instance is not None:
                cls._tasks_service_instance.destroy()
        except Exception as e:
            logger.debug(f"Error during thread cleanup: {e}")

    def set_containers_visibility(self):
        """Update the containers visibility based on the show_unpinned_button setting"""
        self.unpinned_vis_btn.setChecked(self.show_unpinned)
        self.unpinned_vis_btn.setText(self.label_expanded if self.show_unpinned else self.label_collapsed)
        self.unpinned_widget.setVisible(self.show_unpinned or not self.show_unpinned_button)

    def on_thread_started(self):
        logger.debug("Systray thread started")
        QTimer.singleShot(200, SystrayMonitor.send_taskbar_created)

    @pyqtSlot()
    def on_drag_started(self):
        """Handle drag started signal for drag-and-drop functionality"""
        # Always show pinned widget during drag operations
        self.update_pinned_widget_visibility(force_show=True)

    @pyqtSlot()
    def on_drag_ended(self):
        """Handle drag ended signal for drag-and-drop functionality"""
        # Update visibility based on content
        self.update_pinned_widget_visibility()

    @pyqtSlot(IconData)
    def on_icon_modified(self, data: IconData):
        """Handle icon modified signal sent by the tray monitor"""
        if data.guid in self.filtered_guids:
            return
        icon = self.find_icon(data.guid, data.hWnd, data.uID)
        if icon is None:
            icon = IconWidget()
            icon.data = IconData()
            icon.pinned_changed.connect(self.on_icon_pinned_changed)
            icon.icon_moved.connect(self.on_icon_moved)
            self.icons.append(icon)

            # Check if the saved data exists for the icon by uuid and exe path
            id = str(data.guid) if data.guid is not None else data.exe_path
            saved_data = self.current_state.get(
                id,
                self.current_state.get(
                    data.exe_path,
                    IconState(index=-1, is_pinned=False),
                ),
            )
            add_shadow(icon, self.btn_shadow)

            # Place the new icon in the correct layout and index
            icon.is_pinned = saved_data.is_pinned
            if saved_data.is_pinned:
                self.pinned_layout.addWidget(icon)
            else:
                self.unpinned_layout.addWidget(icon)

            # After a short delay (if no new icons are added) - re-sort the icons once
            self.sort_timer.start(1000)
        self.update_icon_data(icon.data, data)
        icon.update_icon()
        icon.setHidden(data.uFlags & NIF_STATE != 0 and data.dwState == 1)
        self.pinned_vis_check_timer.start(300)

    @pyqtSlot(IconData)
    def on_icon_deleted(self, data: IconData) -> None:
        """Handles the icon deleted signal sent by the tray monitor"""
        icon = self.find_icon(data.guid, data.hWnd, data.uID)
        if icon is not None:
            self.icons.remove(icon)
            icon.deleteLater()
            self.pinned_vis_check_timer.start(300)

    @pyqtSlot(object)
    def on_icon_pinned_changed(self, icon: IconWidget):
        """Handles the icon pinned changed signal sent when user [Mod]+Clicks on the icon"""
        if icon.parent() is self.unpinned_widget:
            self.pinned_layout.addWidget(icon)
            icon.is_pinned = True
        else:
            self.unpinned_layout.addWidget(icon)
            icon.is_pinned = False
        # NOTE: This is needed to force-update the layout for that widget
        # otherwise, the widget will not show up in the layout immediately
        # and update_current_state will fail
        icon.show()
        self.unpinned_widget.refresh_styles()
        self.pinned_widget.refresh_styles()
        self.save_state()
        self.update_pinned_widget_visibility()

    @pyqtSlot(object)
    def on_icon_moved(self, icon: IconWidget):
        """Handle icon moved signal"""
        if icon.parent() is self.unpinned_widget:
            icon.is_pinned = False
        else:
            icon.is_pinned = True
        self.unpinned_widget.refresh_styles()
        self.pinned_widget.refresh_styles()
        self.save_state()

    def find_icon(self, uuid: UUID | None, hwnd: int, uID: int) -> IconWidget | None:
        """Find an icon by its uuid or hwnd and uID"""
        if uuid is not None:
            for icon in self.icons:
                if icon.data is None or icon.data.guid is None:
                    continue
                if icon.data.guid == uuid:
                    return icon
        for icon in self.icons:
            if icon.data is None:
                continue
            if icon.data.hWnd == hwnd and icon.data.uID == uID:
                return icon

    def check_icons(self):
        """Check if any icons are still valid and have actual process attached"""
        icons_changed = False
        for icon in self.icons[:]:
            if icon.data is not None and not IsWindow(icon.data.hWnd):
                self.icons.remove(icon)
                icon.deleteLater()
                icons_changed = True

        if icons_changed:
            self.pinned_vis_check_timer.start(300)

    def update_icon_data(self, old_data: IconData | None, new_data: IconData):
        """Update the icon data with the new data received from the tray monitor"""
        if old_data is None:
            return

        direct_attributes = [
            "message_type",
            "hWnd",
            "uID",
            "uFlags",
            "icon_image",
            "exe",
            "exe_path",
        ]
        for attr in direct_attributes:
            if attr in ("hWnd", "uID"):
                continue
            setattr(old_data, attr, getattr(new_data, attr))
        old_data.hWnd = new_data.hWnd or old_data.hWnd
        old_data.uID = new_data.uID or old_data.uID
        if 0 < new_data.uVersion <= 4:
            old_data.uVersion = new_data.uVersion

        flag_dependent_attrs = {
            NIF_MESSAGE: ["uCallbackMessage"],
            NIF_ICON: ["hIcon"],
            NIF_TIP: ["szTip"],
            NIF_STATE: ["dwState", "dwStateMask"],
            NIF_GUID: ["guid"],
            NIF_INFO: ["dwInfoFlags", "szInfoTitle", "szInfo", "uTimeout"],
        }

        for flag, attrs in flag_dependent_attrs.items():
            if new_data.uFlags & flag:
                for attr in attrs:
                    setattr(old_data, attr, getattr(new_data, attr))

    def is_layout_empty(self, layout: QHBoxLayout):
        """Check if a layout has any visible widgets."""
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and (w := item.widget()) and not w.isHidden():
                return False
        return True

    def update_pinned_widget_visibility(self, force_show: bool = False):
        """
        Update the visibility of the pinned widget based on its content.
        If force_show is True, the widget will be shown regardless of content.
        """
        is_empty = self.is_layout_empty(self.pinned_layout)
        self.pinned_widget.setVisible(not is_empty or force_show)
        if force_show and is_empty:
            logger.debug(f"Is empty: {is_empty}, force show: {force_show}")
            self.pinned_widget.setProperty("forceshow", True)
            refresh_widget_style(self.pinned_widget)
        elif self.pinned_widget.property("forceshow") and not is_empty:
            logger.debug(f"Is empty: {is_empty}, force show: {force_show}")
            self.pinned_widget.setProperty("forceshow", False)
            refresh_widget_style(self.pinned_widget)

    def toggle_unpinned_widget_visibility(self):
        """On button click, toggle the visibility of the unpinned widget."""
        if self.unpinned_vis_btn.isChecked():
            self.unpinned_widget.setVisible(True)
            self.unpinned_vis_btn.setText(self.label_expanded)
        else:
            self.unpinned_widget.setVisible(False)
            self.unpinned_vis_btn.setText(self.label_collapsed)

    def sort_icons(self):
        """Sorts pinned and unpinned widgets based on their state index"""
        unpinned = self.get_widgets_from_layout(self.unpinned_layout)
        pinned = self.get_widgets_from_layout(self.pinned_layout)

        def get_sort_index(widget: IconWidget):
            if widget.data is None:
                return 9999
            if widget.data.guid is not None:
                index = self.current_state.get(str(widget.data.guid))
            else:
                index = self.current_state.get(widget.data.exe_path)
            return index.index if index is not None else 9999

        unpinned.sort(key=get_sort_index)
        pinned.sort(key=get_sort_index)
        for w in unpinned:
            self.unpinned_layout.insertWidget(unpinned.index(w), w)
        for w in pinned:
            self.pinned_layout.insertWidget(pinned.index(w), w)
        self.update_current_state()

    def update_current_state(self):
        widgets_state: dict[str, Any] = {}
        for w in self.icons:
            if w.data is None or w.isHidden():
                continue
            index = self.unpinned_layout.indexOf(w)
            if index == -1:
                index = self.pinned_layout.indexOf(w)
            uuid = None if w.data.guid is None else str(w.data.guid)
            widgets_state[uuid or w.data.exe_path] = IconState(
                is_pinned=w.is_pinned,
                index=index,
            )
        self.current_state |= widgets_state

    def save_state(self):
        """Save the current icon position and pinned state to disk."""
        self.update_current_state()
        logger.debug("Saving state to disk")

        self.get_screen_id()
        file_path = app_data_path(f"systray_state_{self.screen_id}.json")
        logger.debug(f"Saving state to {file_path}")
        saved_state: dict[str, Any] = {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                saved_state = json.load(f)
        except json.JSONDecodeError:
            logger.debug("State file decode error. Ignoring.")
        except FileNotFoundError:
            logger.debug("State file not found.")
        # Merging the saved state with current state before saving it to disk
        new_state = saved_state | {k: v.__dict__ for k, v in self.current_state.items()}
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(new_state, indent=2))

    def load_state(self):
        """Load the saved icon position and pinned state from disk."""
        self.get_screen_id()
        file_path = app_data_path(f"systray_state_{self.screen_id}.json")
        logger.debug(f"Loading state from {file_path}")
        self.current_state = {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                state = json.load(f)
                for k, v in state.items():
                    self.current_state[k] = IconState.from_dict(v)
        except json.JSONDecodeError:
            logger.debug("State file decode error. Ignoring.")
        except FileNotFoundError:
            logger.debug("State file not found.")

    def get_screen_id(self):
        """Get the screen id for the current systray widget instance"""
        screen = self.screen()
        if screen is not None:
            raw_id = f"{screen.manufacturer()}{screen.name()}{screen.serialNumber()}".upper()
            self.screen_id = re.sub(r"\W+", "", raw_id)
            return self.screen_id

    def get_widgets_from_layout(self, layout: QLayout) -> list[IconWidget]:
        """Get all the widgets from a layout."""
        widgets: list[IconWidget] = []
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item is not None and (w := item.widget()) and isinstance(w, IconWidget):
                widgets.append(w)
        return widgets
