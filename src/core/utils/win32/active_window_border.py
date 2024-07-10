import logging
from PyQt6.QtWidgets import QWidget, QFrame
from PyQt6.QtCore import pyqtSignal, Qt
from core.event_service import EventService
from core.utils.win32.windows import WinEvent
from core.utils.win32.utilities import get_hwnd_info, get_window_extended_frame_bounds, is_window_maximised

IGNORED_CLASSES = ['']
IGNORED_TITLES = ['']
IGNORED_PROCS = ['SearchHost.exe']

BORDER_WIDTH = 10
BORDER_RADIUS = 9
BORDER_STYLE = "solid"
BORDER_COLOUR = "red"
BORDER_OFFSET = int(BORDER_WIDTH / 2)
HIDE_ON_MAXIMISE = True


class ActiveWindowBorder(QWidget):
    update_active_border = pyqtSignal(int, WinEvent)
    hide_active_border = pyqtSignal(int, WinEvent)

    def __init__(self):
        super().__init__()
        self._event_service = EventService()
        self._curr_hwnd = None
        self._curr_event_info = {}
        self.setWindowFlag(Qt.WindowType.Tool)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoChildEventsForParent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoChildEventsFromChildren)

        self.setGeometry(self.screen().virtualGeometry())

        self.frame = QFrame(self)
        self.frame.setGeometry(0, 0, self.geometry().width(), self.geometry().height())
        self.frame.setStyleSheet(
            f"border: {BORDER_WIDTH}px {BORDER_STYLE} {BORDER_COLOUR}; border-radius: {BORDER_RADIUS}px;"
        )
        self.frame.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.frame.hide()

        self.update_active_border.connect(self._update_active_border)
        self.hide_active_border.connect(self._hide_active_border)

        self._event_service.register_event(WinEvent.EventSystemForeground, self.update_active_border)
        self._event_service.register_event(WinEvent.EventSystemMoveSizeStart, self.hide_active_border)
        self._event_service.register_event(WinEvent.EventSystemMoveSizeEnd, self.update_active_border)
        self._event_service.register_event(WinEvent.EventObjectReorder, self.update_active_border)
        self.show()

    def _ignored_hwnd(self) -> bool:
        return self._curr_event_info['title'] in IGNORED_TITLES \
            or self._curr_event_info['class_name'] in IGNORED_CLASSES \
            or self._curr_event_info['process']['name'] in IGNORED_PROCS

    def _hide_active_border(self, hwnd: int,  _event: WinEvent):
        self._curr_hwnd = hwnd
        self._curr_event_info = get_hwnd_info(hwnd)
        self.frame.hide()

    def _update_active_border(self, hwnd: int, _event: WinEvent):
        self._curr_hwnd = hwnd
        self._curr_event_info = get_hwnd_info(hwnd)

        if not self._ignored_hwnd():
            if is_window_maximised(self._curr_hwnd) and HIDE_ON_MAXIMISE:
                self.frame.hide()
            else:
                self._update_active_window_rect()

    def _update_active_window_rect(self):
        try:
            win_rect = self._curr_event_info['rect']
            frame_bounds_rect = get_window_extended_frame_bounds(self._curr_hwnd)
            pixel_ratio = self.screen().devicePixelRatio()
            virtual_geo = self.screen().virtualGeometry()

            x = int(win_rect['x'] / pixel_ratio)
            y = int(win_rect['y'] / pixel_ratio)
            w = int(win_rect['width'] / pixel_ratio)
            h = int(win_rect['height'] / pixel_ratio)

            x_offset = int((win_rect['x'] - frame_bounds_rect['x']) / pixel_ratio)
            y_offset = int((win_rect['y'] - frame_bounds_rect['y']) / pixel_ratio)
            w_offset = int((win_rect['width'] - frame_bounds_rect['width']) / pixel_ratio)
            h_offset = int((win_rect['height'] - frame_bounds_rect['height']) / pixel_ratio)

            x -= x_offset
            y -= y_offset
            w -= w_offset
            h -= h_offset

            if virtual_geo.x() < 0:
                x -= virtual_geo.x()

            if virtual_geo.y() < 0:
                y -= virtual_geo.y()

            self.frame.setGeometry(
                x - BORDER_OFFSET,
                y - BORDER_OFFSET,
                w + BORDER_WIDTH,
                h + BORDER_WIDTH
            )
        except Exception:
            logging.exception(f"Failed to update active window border for hwnd {self._curr_hwnd}")

        if self.frame.isHidden():
            self.frame.show()
