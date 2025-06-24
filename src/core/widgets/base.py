import logging
import re
import subprocess
from typing import Callable, Union

from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QWidget

from core.utils.win32.system_function import function_map


class BaseWidget(QWidget):
    validation_schema: dict = None
    event_listener: QThread = None

    def __init__(self, timer_interval: int = None, class_name: str = ""):
        super().__init__()
        self._widget_frame = QFrame()
        self._widget_frame_layout = QHBoxLayout()
        self.widget_layout = QHBoxLayout()
        self.timer_interval = timer_interval
        self.bar = None
        self.bar_id = None
        self.monitor_hwnd = None

        if class_name:
            self._widget_frame.setProperty("class", f"widget {class_name}")
        else:
            self._widget_frame.setProperty("class", "widget")

        self.timer = QTimer(self)
        self.mousePressEvent = self._handle_mouse_events

        self.widget_layout.setSpacing(0)
        self.widget_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_frame_layout.setSpacing(0)
        self._widget_frame_layout.setContentsMargins(0, 0, 0, 0)

        # Wrap widgets in a widget frame with class name 'widget'
        self._widget_frame.setLayout(self.widget_layout)
        self._widget_frame_layout.addWidget(self._widget_frame)
        self.setLayout(self._widget_frame_layout)

        self.callbacks = dict()
        self.register_callback("default", self._cb_do_nothing)
        self.register_callback("do_nothing", self._cb_do_nothing)
        self.register_callback("exec", self._cb_execute_subprocess)

        self.callback_default: Union[str, list[str]] = "default"
        self.callback_timer: Union[str, list[str]] = "default"
        self.callback_left: Union[str, list[str]] = self.callback_default
        self.callback_middle: Union[str, list[str]] = self.callback_default
        self.callback_right: Union[str, list[str]] = self.callback_default

    def register_callback(self, callback_name: str, fn: Callable[[], None]):
        self.callbacks[callback_name] = fn

    def start_timer(self):
        if self.timer_interval and self.timer_interval > 0:
            self.timer.timeout.connect(self._timer_callback)
            self.timer.start(self.timer_interval)
        self._timer_callback()

    def _handle_mouse_events(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._run_callback(self.callback_left)
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._run_callback(self.callback_middle)
        elif event.button() == Qt.MouseButton.RightButton:
            self._run_callback(self.callback_right)

    def _run_callback(self, callback_str: Union[str, list]):
        if " " in callback_str:
            callback_args = list(map(lambda x: x.strip('"'), re.findall(r'".+?"|[^ ]+', callback_str)))
            callback_type = callback_args[0]
            callback_args = callback_args[1:]
        else:
            callback_type = callback_str
            callback_args = []

        is_valid_callback = callback_type in self.callbacks.keys()
        self.callback = self.callbacks[callback_type if is_valid_callback else "default"]

        try:
            self.callbacks[callback_type](*callback_args)
        except Exception:
            logging.exception(f"Failed to execute callback of type '{callback_type}' with args: {callback_args}")

    def _timer_callback(self):
        self._run_callback(self.callback_timer)

    def _cb_execute_subprocess(self, cmd: str, *cmd_args: list[str]):
        if cmd in function_map:
            function_map[cmd]()
        else:
            subprocess.Popen([cmd, *cmd_args] if cmd_args else [cmd], shell=True)

    def _cb_do_nothing(self):
        pass
