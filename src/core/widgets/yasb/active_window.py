import atexit
import logging
import os
import re

import win32gui
from PIL import Image
from PyQt6.QtCore import QElapsedTimer, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.event_service import EventService
from core.utils.utilities import add_shadow
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.app_icons import get_window_icon
from core.utils.win32.utilities import get_hwnd_info
from core.utils.win32.windows import WinEvent
from core.validation.widgets.yasb.active_window import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import APP_BAR_TITLE

# Get the current process ID to exclude our own windows
CURRENT_PROCESS_ID = os.getpid()
# Define ignored titles, classes, and processes
IGNORED_TITLES = ["", " ", "FolderView", "Program Manager", "python3", "pythonw3", "YasbBar", "Search", "Start"]
IGNORED_CLASSES = [
    "WorkerW",
    "TopLevelWindowForOverflowXamlIsland",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow",
]
IGNORED_PROCESSES = ["SearchHost.exe", "komorebi.exe", "yasb.exe", "Flow.Launcher.exe"]
IGNORED_YASB_TITLES = [APP_BAR_TITLE]
DEBOUNCE_CLASSES = ["OperationStatusWindow"]
try:
    from core.utils.win32.event_listener import SystemEventListener
except ImportError:
    SystemEventListener = None
    logging.warning("Failed to load Win32 System Event Listener")


class ActiveWindowWidget(BaseWidget):
    foreground_change = pyqtSignal(int, WinEvent)
    window_name_change = pyqtSignal(int, WinEvent)
    window_destroy = pyqtSignal(int, WinEvent)
    focus_change_workspaces = pyqtSignal(str)
    validation_schema = VALIDATION_SCHEMA
    event_listener = SystemEventListener

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        callbacks: dict[str, str],
        label_no_window: str,
        label_icon: bool,
        label_icon_size: int,
        ignore_window: dict[str, list[str]],
        monitor_exclusive: bool,
        animation: dict[str, str],
        max_length: int,
        max_length_ellipsis: str,
        container_padding: dict[str, int],
        label_shadow: dict = None,
        container_shadow: dict = None,
        rewrite: list[dict] = None,
    ):
        super().__init__(class_name=f"active-window-widget {class_name}")
        self.dpi = None
        self._win_info = None
        self._tracked_hwnd = None
        self._show_alt = False
        self._label = label
        self._label_alt = label_alt
        self._active_label = label
        self._label_no_window = label_no_window
        self._label_icon = label_icon
        self._label_icon_size = label_icon_size
        self._monitor_exclusive = monitor_exclusive
        self._max_length = max_length
        self._max_length_ellipsis = max_length_ellipsis
        self._event_service = EventService()
        self._update_retry_count = 0
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._rewrite_rules = rewrite
        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        self._window_title_text = QLabel()
        self._window_title_text.setProperty("class", "label")
        self._window_title_text.setTextFormat(Qt.TextFormat.PlainText)
        self._window_title_text.setText(self._label_no_window)
        add_shadow(self._window_title_text, self._label_shadow)

        if self._label_icon:
            self._window_icon_label = QLabel()
            self._window_icon_label.setProperty("class", "label icon")
            self._window_icon_label.setText(self._label_no_window)
            add_shadow(self._window_icon_label, self._label_shadow)
        self._ignore_window = ignore_window
        self._ignore_window["classes"] += IGNORED_CLASSES
        self._ignore_window["processes"] += IGNORED_PROCESSES
        self._ignore_window["titles"] += IGNORED_TITLES
        self._icon_cache = dict()
        if self._label_icon:
            self._widget_container_layout.addWidget(self._window_icon_label)
        self._widget_container_layout.addWidget(self._window_title_text)
        self.register_callback("toggle_label", self._toggle_title_text)
        if not callbacks:
            callbacks = {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "toggle_label"}

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self.foreground_change.connect(self._on_focus_change_event)
        self._event_service.register_event(WinEvent.EventSystemForeground, self.foreground_change)
        self._event_service.register_event(WinEvent.EventSystemMoveSizeEnd, self.foreground_change)

        self.window_name_change.connect(self._on_window_name_change_event)
        self._event_service.register_event(WinEvent.EventObjectNameChange, self.window_name_change)
        self._event_service.register_event(WinEvent.EventObjectStateChange, self.window_name_change)

        self.window_destroy.connect(self._on_window_destroy_event)
        self._event_service.register_event(WinEvent.EventObjectDestroy, self.window_destroy)

        self.focus_change_workspaces.connect(self._on_focus_change_workspaces)
        self._event_service.register_event("workspace_update", self.focus_change_workspaces)

        # Parent timer to widget so it auto-stops/cleans up on deletion
        self._window_update_timer = QTimer(self)
        self._window_update_timer.setSingleShot(True)
        self._window_update_timer.timeout.connect(self._process_debounced_update)
        self._pending_window_update = None
        self._last_update_time = QElapsedTimer()
        self._last_update_time.start()

        self._update_throttle_ms = 250  # Minimum ms between updates for high-frequency classes

        atexit.register(self._stop_events)
        try:
            self.destroyed.connect(self._on_destroyed)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _on_destroyed(self, *args):
        try:
            # Unregister all events we registered
            self._event_service.unregister_event(WinEvent.EventSystemForeground, self.foreground_change)
            self._event_service.unregister_event(WinEvent.EventSystemMoveSizeEnd, self.foreground_change)
            self._event_service.unregister_event(WinEvent.EventObjectNameChange, self.window_name_change)
            self._event_service.unregister_event(WinEvent.EventObjectStateChange, self.window_name_change)
            self._event_service.unregister_event("workspace_update", self.focus_change_workspaces)
        except Exception:
            pass

    def _rewrite_filter(self, text: str) -> str:
        """Applies rewrite rules to the given text."""
        if not text or not self._rewrite_rules:
            return text

        result = text
        for rule in self._rewrite_rules:
            pattern, replacement, case = (rule.get(k, "") for k in ("pattern", "replacement", "case"))

            if not pattern or not replacement:
                continue

            try:
                result, count = re.subn(pattern, replacement, result)
                if count > 0:
                    transform = getattr(result, case, None)
                    if callable(transform):
                        result = transform()
            except re.error as e:
                logging.warning(f"Invalid regex pattern '{pattern}': {e}")
                continue

        return result

    def _set_no_window_or_hide(self) -> None:
        self._tracked_hwnd = None
        if self._label_no_window:
            self._window_title_text.setText(self._label_no_window)
            if self._label_icon:
                self._window_icon_label.hide()
        else:
            self.hide()

    def _stop_events(self) -> None:
        self._event_service.clear()

    def _on_focus_change_workspaces(self, event: str) -> None:
        # Temporary fix for MoveWindow event from Komorebi: MoveWindow event is not sending enough data to know on which monitor the window is being moved also animation is a problem and because of that we are using singleShot to try catch the window after the animation is done and this will run only on MoveWindow event
        if event in ["Hide", "Destroy"]:
            self.hide()
            return
        hwnd = win32gui.GetForegroundWindow()
        if hwnd != 0:
            self._on_focus_change_event(hwnd, WinEvent.WinEventOutOfContext)
            if self._update_retry_count < 3 and event in ["MoveWindow"]:
                self._update_retry_count += 1
                QTimer.singleShot(200, lambda: self._on_focus_change_event(hwnd, WinEvent.WinEventOutOfContext))
                return
            else:
                self._update_retry_count = 0
        else:
            self._set_no_window_or_hide()

    def _on_window_destroy_event(self, hwnd: int, event: WinEvent) -> None:
        """Handle top-level window destruction. Only react when the destroyed HWND matches the tracked window."""
        try:
            # If we don't have a tracked HWND or this destroy event doesn't match it ignore immediately
            if self._tracked_hwnd is None or hwnd != self._tracked_hwnd:
                return

            try:
                parent = win32gui.GetParent(hwnd)
                if parent and parent != 0:
                    return
            except Exception:
                pass

            fg = win32gui.GetForegroundWindow()
            if fg and fg != 0 and fg != hwnd:
                try:
                    fg_info = get_hwnd_info(fg)
                    if fg_info and fg_info.get("title") and fg_info.get("process"):
                        if fg_info["process"].get("pid") != CURRENT_PROCESS_ID:
                            self._on_focus_change_event(fg, WinEvent.WinEventOutOfContext)
                            return
                except Exception:
                    pass

            self._set_no_window_or_hide()
        except Exception:
            logging.exception(f"Failed handling destroy event for HWND {hwnd}")

    def _toggle_title_text(self) -> None:
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt = not self._show_alt
        self._active_label = self._label_alt if self._show_alt else self._label
        self._update_text()

    def _on_focus_change_event(self, hwnd: int, event: WinEvent) -> None:
        win_info = get_hwnd_info(hwnd)
        if (
            not win_info
            or not hwnd
            or not win_info["title"]
            or win_info["title"] in IGNORED_YASB_TITLES
            or win_info["process"]["pid"] == CURRENT_PROCESS_ID
        ):
            return

        monitor_name = win_info["monitor_info"].get("device", None)

        if (
            self._monitor_exclusive
            and self.screen().name() != monitor_name
            and win_info.get("monitor_hwnd", "Unknown") != self.monitor_hwnd
        ):
            self._set_no_window_or_hide()
        else:
            self._update_window_title(hwnd, win_info, event)

        # Check if the window title is in the list of ignored titles
        if win_info["title"] in IGNORED_TITLES:
            self._set_no_window_or_hide()

    def _on_window_name_change_event(self, hwnd: int, event: WinEvent) -> None:
        if not self._win_info or hwnd != self._win_info["hwnd"]:
            return

        if self._win_info["class_name"] in DEBOUNCE_CLASSES:
            if self._last_update_time.elapsed() < self._update_throttle_ms:
                # Store for later processing and return immediately
                self._pending_window_update = (hwnd, event)
                # If timer isn't already running, start it
                if not self._window_update_timer.isActive():
                    remaining_time = self._update_throttle_ms - self._last_update_time.elapsed()
                    self._window_update_timer.start(max(50, remaining_time))
                return

        # For regular windows, process normally
        self._process_window_update(hwnd, event)
        self._last_update_time.restart()

    def _process_debounced_update(self) -> None:
        """Process the throttled window update"""
        if self._pending_window_update:
            hwnd, event = self._pending_window_update
            self._pending_window_update = None
            self._process_window_update(hwnd, event)
            self._last_update_time.restart()

    def _process_window_update(self, hwnd: int, event: WinEvent) -> None:
        self._on_focus_change_event(hwnd, event)

    def _update_window_title(self, hwnd: int, win_info: dict, event: WinEvent) -> None:
        try:
            if hwnd != win32gui.GetForegroundWindow():
                return
            title = win_info["title"]
            process = win_info["process"]
            class_name = win_info["class_name"]

            if self._label_icon:
                cache_key = (hwnd, title, self.dpi)

                if cache_key in self._icon_cache:
                    icon_img = self._icon_cache[cache_key]
                else:
                    self.dpi = self.screen().devicePixelRatio()
                    icon_img = get_window_icon(hwnd)
                    if icon_img:
                        icon_img = icon_img.resize(
                            (int(self._label_icon_size * self.dpi), int(self._label_icon_size * self.dpi)),
                            Image.LANCZOS,
                        ).convert("RGBA")
                    if not process["name"] == "explorer.exe":
                        # Do not cache icons for explorer.exe windows
                        self._icon_cache[cache_key] = icon_img
                if icon_img:
                    qimage = QImage(icon_img.tobytes(), icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
                    self.pixmap = QPixmap.fromImage(qimage)
                    self.pixmap.setDevicePixelRatio(self.dpi)
                else:
                    self.pixmap = None

            if (
                title.strip() in self._ignore_window["titles"]
                or class_name in self._ignore_window["classes"]
                or process["name"] in self._ignore_window["processes"]
            ):
                win_info["title"] = ""
                return win_info["title"]
            else:
                if "title" in win_info and len(win_info["title"]) > 0:
                    win_info["title"] = self._rewrite_filter(win_info["title"])
                if "process" in win_info and "name" in win_info["process"]:
                    win_info["process"]["name"] = self._rewrite_filter(win_info["process"]["name"])

                if self._max_length and len(win_info["title"]) > self._max_length:
                    truncated_title = f"{win_info['title'][: self._max_length]}{self._max_length_ellipsis}"
                    win_info["title"] = truncated_title
                    self._window_title_text.setText(self._label_no_window)
                    if self._label_icon:
                        self._window_icon_label.hide()

                self._win_info = win_info
                try:
                    self._tracked_hwnd = int(hwnd) if hwnd else None
                except Exception:
                    self._tracked_hwnd = None
                self._update_text()

                if self._window_title_text.isHidden():
                    self._window_title_text.show()
                if self.isHidden():
                    self.show()
        except Exception:
            logging.exception(
                f"Failed to update active window title for window with HWND {hwnd} emitted by event {event}"
            )

    def _update_text(self):
        try:
            self._window_title_text.setText(self._active_label.format(win=self._win_info))
            if self._label_icon:
                if self.pixmap:
                    self._window_icon_label.show()
                    self._window_icon_label.setPixmap(self.pixmap)
                else:
                    self._window_icon_label.hide()
        except Exception:
            self._window_title_text.setText(self._active_label)
