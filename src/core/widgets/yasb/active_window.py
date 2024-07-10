import logging
from settings import APP_BAR_TITLE
from core.utils.win32.windows import WinEvent
from core.widgets.base import BaseWidget
from core.event_service import EventService
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel
from core.validation.widgets.yasb.active_window import VALIDATION_SCHEMA
from core.utils.win32.utilities import get_hwnd_info

IGNORED_TITLES = ['', ' ','FolderView','Program Manager','python3','pythonw3','WinLaunch','NxDock','YasbBar']
IGNORED_CLASSES = ['WorkerW','TopLevelWindowForOverflowXamlIsland','Shell_TrayWnd','Shell_SecondaryTrayWnd']
IGNORED_PROCESSES = ['SearchHost.exe','komorebi.exe']
IGNORED_YASB_TITLES = [APP_BAR_TITLE]
IGNORED_YASB_CLASSES = [
    'Qt620QWindowIcon',
    'Qt621QWindowIcon',
    'Qt620QWindowToolSaveBits',
    'Qt621QWindowToolSaveBits'
]

try:
    from core.utils.win32.event_listener import SystemEventListener
except ImportError:
    SystemEventListener = None
    logging.warning("Failed to load Win32 System Event Listener")


class ActiveWindowWidget(BaseWidget):

    foreground_change = pyqtSignal(int, WinEvent)
    window_name_change = pyqtSignal(int, WinEvent)
    validation_schema = VALIDATION_SCHEMA
    event_listener = SystemEventListener

    def __init__(
            self,
            label: str,
            label_alt: str,
            callbacks: dict[str, str],
            label_no_window: str,
            ignore_window: dict[str, list[str]],
            monitor_exclusive: bool,
            max_length: int,
            max_length_ellipsis: str
    ):
        super().__init__(class_name="active-window-widget")

        self._win_info = None
        self._show_alt = False
        self._label = label
        self._label_alt = label_alt
        self._active_label = label
        self._label_no_window = label_no_window
        self._monitor_exclusive = monitor_exclusive
        self._max_length = max_length
        self._max_length_ellipsis = max_length_ellipsis
        self._event_service = EventService()
        self._window_title_text = QLabel()
        self._window_title_text.setProperty("class", "label")
        self._window_title_text.setText(self._label_no_window)

        self._ignore_window = ignore_window
        self._ignore_window['classes'] += IGNORED_CLASSES
        self._ignore_window['processes'] += IGNORED_PROCESSES
        self._ignore_window['titles'] += IGNORED_TITLES

        self.widget_layout.addWidget(self._window_title_text)
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

        self.window_name_change.connect(self._on_window_name_change_event)
        self._event_service.register_event(WinEvent.EventObjectNameChange, self.window_name_change)

    def _toggle_title_text(self) -> None:
        self._show_alt = not self._show_alt
        self._active_label = self._label_alt if self._show_alt else self._label
        self._update_text()

    def _on_focus_change_event(self, hwnd: int, event: WinEvent) -> None:
        win_info = get_hwnd_info(hwnd)
        if (not win_info or not hwnd or
                not win_info['title'] or
                win_info['title'] in IGNORED_YASB_TITLES or
                win_info['class_name'] in IGNORED_YASB_CLASSES):
            self.hide()    
            return

        monitor_xpos = win_info['monitor_info'].get('rect', None).get('x', None)
        monitor_ypos = win_info['monitor_info'].get('rect', None).get('y', None)

        if (self._monitor_exclusive and 
           (self.screen().geometry().x() != monitor_xpos or self.screen().geometry().y() != monitor_ypos) or (win_info['title'] in IGNORED_TITLES or win_info['class_name'] in IGNORED_CLASSES)):
            self.hide()
        else:
            self.show()
            self._update_window_title(hwnd, win_info, event)

    def _on_window_name_change_event(self, hwnd: int, event: WinEvent) -> None:
        if self._win_info and hwnd == self._win_info["hwnd"]:
            self._on_focus_change_event(hwnd, event)
            
    def _update_window_title(self, hwnd: int, win_info: dict, event: WinEvent) -> None:
        
        try:
            title = win_info['title']
            process = win_info['process']['name']
            class_name = win_info['class_name']

            if (title.strip() in self._ignore_window['titles'] or
                    class_name in self._ignore_window['classes'] or
                    process in self._ignore_window['processes']):
                if not self._label_no_window:
                    return self._window_title_text.hide()
            else:
                if self._max_length and len(win_info['title']) > self._max_length:
                    truncated_title = f"{win_info['title'][:self._max_length]}{self._max_length_ellipsis}"
                    win_info['title'] = truncated_title
                    self._window_title_text.setText(self._label_no_window)

                self._win_info = win_info
                self._update_text()

                if self._window_title_text.isHidden():
                    self._window_title_text.show()
        except Exception:
            logging.exception(
                f"Failed to update active window title for window with HWND {hwnd} emitted by event {event}"
            )

    def _update_text(self):
        try:
            self._window_title_text.setText(self._active_label.format(win=self._win_info))
        except Exception:
            self._window_title_text.setText(self._active_label)