import logging
from settings import APP_BAR_TITLE, DEBUG
from core.utils.win32.windows import WinEvent
from core.widgets.base import BaseWidget
from core.event_service import EventService
from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from core.validation.widgets.yasb.active_window import VALIDATION_SCHEMA
from core.utils.win32.utilities import get_hwnd_info
from PIL import Image
import win32gui
from core.utils.win32.app_icons import get_window_icon
from core.utils.widgets.animation_manager import AnimationManager
import atexit

IGNORED_TITLES = ['', ' ', 'FolderView', 'Program Manager', 'python3', 'pythonw3', 'YasbBar', 'Search', 'Start', 'yasb']
IGNORED_CLASSES = ['WorkerW', 'TopLevelWindowForOverflowXamlIsland', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd']
IGNORED_PROCESSES = ['SearchHost.exe', 'komorebi.exe', 'yasb.exe']
IGNORED_YASB_TITLES = [APP_BAR_TITLE]
IGNORED_YASB_CLASSES = [
    'Qt662QWindowIcon',
    'Qt662QWindowIcon',
    'Qt662QWindowToolSaveBits',
    'Qt662QWindowToolSaveBits'
]

try:
    from core.utils.win32.event_listener import SystemEventListener
except ImportError:
    SystemEventListener = None
    logging.warning("Failed to load Win32 System Event Listener")


class ActiveWindowWidget(BaseWidget):
    foreground_change = pyqtSignal(int, WinEvent)
    window_name_change = pyqtSignal(int, WinEvent)
    focus_change_workspaces = pyqtSignal(str)
    validation_schema = VALIDATION_SCHEMA
    event_listener = SystemEventListener

    def __init__(
            self,
            label: str,
            label_alt: str,
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
    ):
        super().__init__(class_name="active-window-widget")
        self._win_info = None
        self._show_alt = False
        self._label = label
        self._label_alt = label_alt
        self._active_label = label
        self._label_no_window = label_no_window
        self._label_icon = label_icon
        self._label_icon_size = label_icon_size
        self.dpi = self.screen().devicePixelRatio() 
        self._monitor_exclusive = monitor_exclusive
        self._max_length = max_length
        self._max_length_ellipsis = max_length_ellipsis
        self._event_service = EventService()
        self._update_retry_count = 0
        self._animation = animation
        self._padding = container_padding
         # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        
        
        self._window_title_text = QLabel()
        self._window_title_text.setProperty("class", "label")
        self._window_title_text.setText(self._label_no_window)
       
        if self._label_icon:
            self._window_icon_label = QLabel()
            self._window_icon_label.setProperty("class", "label icon")
            self._window_icon_label.setText(self._label_no_window)

        self._ignore_window = ignore_window
        self._ignore_window['classes'] += IGNORED_CLASSES
        self._ignore_window['processes'] += IGNORED_PROCESSES
        self._ignore_window['titles'] += IGNORED_TITLES
        self._icon_cache = dict()
        if self._label_icon:
            self._widget_container_layout.addWidget(self._window_icon_label)
        self._widget_container_layout.addWidget(self._window_title_text)
        self.register_callback("toggle_label", self._toggle_title_text)
        if not callbacks:
            callbacks = {
                "on_left": "toggle_label",
                "on_middle": "do_nothing",
                "on_right": "toggle_label"
            }

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']

        self.foreground_change.connect(self._on_focus_change_event)
        self._event_service.register_event(WinEvent.EventSystemForeground, self.foreground_change)
        self._event_service.register_event(WinEvent.EventSystemMoveSizeEnd, self.foreground_change)

        self.window_name_change.connect(self._on_window_name_change_event)
        self._event_service.register_event(WinEvent.EventObjectNameChange, self.window_name_change)
        self._event_service.register_event(WinEvent.EventObjectStateChange, self.window_name_change)

        self.focus_change_workspaces.connect(self._on_focus_change_workspaces)
        self._event_service.register_event("workspace_update", self.focus_change_workspaces)
        
        atexit.register(self._stop_events)

    def _stop_events(self) -> None:
        self._event_service.clear()
        
    def _on_focus_change_workspaces(self, event: str) -> None:
        # Temporary fix for MoveWindow event from Komorebi: MoveWindow event is not sending enough data to know on which monitor the window is being moved also animation is a problem and because of that we are using singleShot to try catch the window after the animation is done and this will run only on MoveWindow event
        if event in ['Hide', 'Destroy']:
            self.hide()
            return
        hwnd = win32gui.GetForegroundWindow()
        if hwnd != 0:
            self._on_focus_change_event(hwnd, WinEvent.WinEventOutOfContext)
            if self._update_retry_count < 3 and event in ['MoveWindow']:
                self._update_retry_count += 1
                QTimer.singleShot(200, lambda: self._on_focus_change_event(hwnd, WinEvent.WinEventOutOfContext))
                return
            else:
                self._update_retry_count = 0
        else:
            self.hide()
            
        
    def _toggle_title_text(self) -> None:
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self._show_alt = not self._show_alt
        self._active_label = self._label_alt if self._show_alt else self._label
        self._update_text()

    def _on_focus_change_event(self, hwnd: int, event: WinEvent) -> None:
         
        win_info = get_hwnd_info(hwnd)
        if (not win_info or not hwnd or
                not win_info['title'] or
                win_info['title'] in IGNORED_YASB_TITLES or
                win_info['class_name'] in IGNORED_YASB_CLASSES):
            return

        monitor_name = win_info['monitor_info'].get('device', None)

        if self._monitor_exclusive and self.screen().name() != monitor_name and win_info.get('monitor_hwnd', 'Unknown') != self.monitor_hwnd:
            self.hide() 
        else:
            self._update_window_title(hwnd, win_info, event)
            
        # Check if the window title is in the list of ignored titles
        if(win_info['title'] in IGNORED_TITLES):
            self.hide()

    def _on_window_name_change_event(self, hwnd: int, event: WinEvent) -> None:
        if self._win_info and hwnd == self._win_info["hwnd"]:
            self._on_focus_change_event(hwnd, event)

    def _update_window_title(self, hwnd: int, win_info: dict, event: WinEvent) -> None:
        try:
            if hwnd != win32gui.GetForegroundWindow():
                return
            title = win_info['title']
            process = win_info['process']
            pid = process["pid"]
            class_name = win_info['class_name']

            if self._label_icon:
                if event != WinEvent.WinEventOutOfContext:
                    self._update_retry_count = 0
                if (hwnd, title, pid) in self._icon_cache:
                    icon_img = self._icon_cache[(hwnd, title, pid)]
                else:
                    icon_img = get_window_icon(hwnd, self.dpi)
                    if icon_img:
                        icon_img = icon_img.resize((int(self._label_icon_size * self.dpi), int(self._label_icon_size * self.dpi)), Image.LANCZOS).convert("RGBA")
                    else:
                        # UWP apps might need a moment to start under ApplicationFrameHost
                        # So we delay the detection, but only do it once.
                        if process["name"] == "ApplicationFrameHost.exe":
                            if self._update_retry_count < 10:
                                self._update_retry_count += 1
                                QTimer.singleShot(500, lambda: self._update_window_title(hwnd, win_info, WinEvent.WinEventOutOfContext))
                                return
                            else:
                                self._update_retry_count = 0

                    if not DEBUG:
                        self._icon_cache[(hwnd, title, pid)] = icon_img
                if icon_img:
                    qimage = QImage(icon_img.tobytes(), icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
                    self.pixmap = QPixmap.fromImage(qimage)
                else:
                    self.pixmap = None


            if (title.strip() in self._ignore_window['titles'] or
                    class_name in self._ignore_window['classes'] or
                    process in self._ignore_window['processes']):
                return
            else:
                if self._max_length and len(win_info['title']) > self._max_length:
                    truncated_title = f"{win_info['title'][:self._max_length]}{self._max_length_ellipsis}"
                    win_info['title'] = truncated_title
                    self._window_title_text.setText(self._label_no_window)
                    if self._label_icon:
                        self._window_icon_label.setText(self._label_no_window)
                    
                self._win_info = win_info
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