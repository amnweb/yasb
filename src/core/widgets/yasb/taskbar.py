"""
Note: This is probably not the best way to do this, but debouncing the events is the only way to prevent high CPU usage.
Need to find a better way to do this.
"""
import logging
from settings import DEBUG
from core.widgets.base import BaseWidget
from core.utils.win32.windows import WinEvent
from core.event_service import EventService
from PyQt6.QtGui import QPixmap, QImage, QCursor
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from core.validation.widgets.yasb.taskbar import VALIDATION_SCHEMA
from core.utils.win32.utilities import get_hwnd_info
from PIL import Image
import win32gui
from core.utils.win32.app_icons import get_window_icon
import win32con

try:
    from core.utils.win32.event_listener import SystemEventListener
except ImportError:
    SystemEventListener = None
    logging.warning("Failed to load Win32 System Event Listener")
    
class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
        
class TaskbarWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    update_event = pyqtSignal(int, WinEvent)
    event_listener = SystemEventListener

    def __init__(
            self,
            icon_size: int,
            ignore_apps: dict[str, list[str]]
    ):
        super().__init__(class_name="taskbar-widget")

        self.icon_label = QLabel()
        self._label_icon_size = icon_size

        self._ignore_apps = ignore_apps
        self._win_info = None
        self._update_retry_count = 0
        
        self.dpi = self.screen().devicePixelRatio() 
        self._icon_cache = dict()
        self.window_buttons = {}
        self._event_service = EventService()
        
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        
        self.update_event.connect(self._on_update_event)
        self._event_service.register_event(WinEvent.EventSystemForeground, self.update_event)
        self._event_service.register_event(WinEvent.EventObjectFocus, self.update_event)
        self._event_service.register_event(WinEvent.EventObjectDestroy, self.update_event)

        # Debounce timers
        self._debounce_timer_focus = QTimer()
        self._debounce_timer_focus.setSingleShot(True)
        self._debounce_timer_focus.timeout.connect(self._process_debounced_focus_event)
        self._debounced_focus_event = None

        self._debounce_timer_foreground = QTimer()
        self._debounce_timer_foreground.setSingleShot(True)
        self._debounce_timer_foreground.timeout.connect(self._process_debounced_foreground_event)
        self._debounced_foreground_event = None

    def _on_update_event(self, hwnd: int, event: WinEvent) -> None:
        if event == WinEvent.EventObjectFocus:
            self._debounced_focus_event = (hwnd, event)
            if not self._debounce_timer_focus.isActive():
                self._debounce_timer_focus.start(100)
        elif event == WinEvent.EventSystemForeground:
            self._debounced_foreground_event = (hwnd, event)
            if not self._debounce_timer_foreground.isActive():
                self._debounce_timer_foreground.start(100)
        else:
            self._process_event(hwnd, event)

    def _process_debounced_focus_event(self):
        if self._debounced_focus_event:
            hwnd, event = self._debounced_focus_event
            self._process_event(hwnd, event)
            self._debounced_focus_event = None

    def _process_debounced_foreground_event(self):
        if self._debounced_foreground_event:
            hwnd, event = self._debounced_foreground_event
            self._process_event(hwnd, event)
            self._debounced_foreground_event = None

    def _process_event(self, hwnd: int, event: WinEvent) -> None:
        win_info = get_hwnd_info(hwnd)
        
        if (not win_info or not hwnd or
                not win_info['title'] or
                win_info['title'] in self._ignore_apps['titles'] or
                win_info['class_name'] in self._ignore_apps['classes'] or
                win_info['process']['name'] in self._ignore_apps['processes']):
            return 
        self._update_label(hwnd, win_info, event)

    def _update_label(self, hwnd: int, win_info: dict, event: WinEvent) -> None:
        visible_windows = self.get_visible_windows(hwnd, win_info, event)
        existing_hwnds = set(self.window_buttons.keys())
        new_icons = []
        removed_hwnds = []

        for title, hwnd, icon, process in visible_windows:
            if hwnd not in self.window_buttons and icon is not None:
                self.window_buttons[hwnd] = (title, icon, hwnd, process)
                new_icons.append((title, icon, hwnd, process))
            elif hwnd in existing_hwnds:
                existing_hwnds.remove(hwnd)

        # Collect hwnds for windows that are no longer visible
        for hwnd in existing_hwnds:
            removed_hwnds.append(hwnd)
            del self.window_buttons[hwnd]

        # Remove icons for windows that are no longer visible
        for i in reversed(range(self._widget_container_layout.count())):
            widget = self._widget_container_layout.itemAt(i).widget()
            if widget != self.icon_label:
                hwnd = widget.property("hwnd")
                if hwnd in removed_hwnds:
                    self._widget_container_layout.removeWidget(widget)
                    widget.deleteLater()

        # Add new icons
        for title, icon, hwnd, process in new_icons:
            icon_label = ClickableLabel()
            icon_label.setProperty("class", "app-icon")
            icon_label.setPixmap(icon)
            icon_label.setToolTip(title)
            icon_label.setProperty("hwnd", hwnd)
            icon_label.clicked.connect(lambda hwnd=hwnd: self.bring_to_foreground(hwnd))
            icon_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._widget_container_layout.addWidget(icon_label)
            
    def _get_app_icon(self, hwnd: int, title:str, process: dict, event: WinEvent) -> None:
        try:
            if hwnd != win32gui.GetForegroundWindow():
                return
            pid = process["pid"]
            
            if event != WinEvent.WinEventOutOfContext:
                self._update_retry_count = 0

            if (hwnd, title, pid) in self._icon_cache:
                icon_img = self._icon_cache[(hwnd, title, pid)]
            else:
                icon_img = get_window_icon(hwnd, self.dpi)
                if icon_img:
                    icon_img = icon_img.resize((int(self._label_icon_size * self.dpi), int(self._label_icon_size * self.dpi)), Image.LANCZOS).convert("RGBA")
                else:
                    # UWP apps I hate it
                    if process["name"] == "ApplicationFrameHost.exe":
                        if self._update_retry_count < 10:
                            self._update_retry_count += 1
                            QTimer.singleShot(500, lambda: self._get_app_icon(hwnd, title, process, WinEvent.WinEventOutOfContext))
                            return
                        else:
                            self._update_retry_count = 0
                if not DEBUG:
                    self._icon_cache[(hwnd, title, pid)] = icon_img
            if icon_img:
                qimage = QImage(icon_img.tobytes(), icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimage)
            else:
                pixmap = None
            return pixmap
        except Exception:
            if DEBUG:
                logging.exception(f"Failed to get icons for window with HWND {hwnd} emitted by event {event}")
            
            
    def get_visible_windows(self, hwnd: int, win_info: dict, event: WinEvent) -> None:
        process = win_info['process']
        def is_window_visible_on_taskbar(hwnd):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                if not (ex_style & win32con.WS_EX_TOOLWINDOW):
                    return True
            return False

        visible_windows = []
        
        def enum_windows_proc(hwnd, lParam):
            if is_window_visible_on_taskbar(hwnd):
                title = win32gui.GetWindowText(hwnd)
                icon = self._get_app_icon(hwnd, title, process, event)
                visible_windows.append((title, hwnd, icon ,process))
            return True
        win32gui.EnumWindows(enum_windows_proc, None)
        return visible_windows
    
    
    def bring_to_foreground(self, hwnd):
        if not win32gui.IsWindow(hwnd):
            logging.warning(f"Invalid window handle: {hwnd}")
            return

        # Check if the window is minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(hwnd)