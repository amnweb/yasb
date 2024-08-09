import logging
import re
import subprocess
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QFrame, QLabel
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtCore import QTimer, QThread, Qt
from typing import Union


class BaseWidget(QWidget):
    validation_schema: dict = None
    event_listener: QThread = None

    def __init__(
            self,
            timer_interval: int = None,
            class_name: str = ""
    ):
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

    def register_callback(self, callback_name, fn):
        self.callbacks[callback_name] = fn

    def start_timer(self):
        if self.timer_interval and self.timer_interval > 0:
            self.timer.timeout.connect(self._timer_callback)
            self.timer.start(self.timer_interval)

        self.timer.singleShot(0, self._timer_callback)

    def _handle_mouse_events(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._run_callback(self.callback_left)
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._run_callback(self.callback_middle)
        elif event.button() == Qt.MouseButton.RightButton:
            self._run_callback(self.callback_right)

    def _run_callback(self, callback_str: Union[str, list]):
        if " " in callback_str:
            callback_args = list(map(lambda x: x.strip('\"'), re.findall(r'".+?"|[^ ]+', callback_str)))
            callback_type = callback_args[0]
            callback_args = callback_args[1:]
        else:
            callback_type = callback_str
            callback_args = []

        is_valid_callback = callback_type in self.callbacks.keys()
        self.callback = self.callbacks[callback_type if is_valid_callback else 'default']

        try:
            self.callbacks[callback_type](*callback_args)
        except Exception:
            logging.exception(f"Failed to execute callback of type '{callback_type}' with args: {callback_args}")

    def _timer_callback(self):
        self._run_callback(self.callback_timer)

    def _cb_execute_subprocess(self, cmd: str, *cmd_args: list[str]):
        subprocess.Popen([cmd, *cmd_args] if cmd_args else [cmd], shell=True)

    def _cb_do_nothing(self):
        pass

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content)
            label_parts = [part for part in label_parts if part]
            widgets = []
            for part in label_parts:
                part = part.strip()  # Remove any leading/trailing whitespace
                if not part:
                    continue
                if '<span' in part and '</span>' in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else 'icon'
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                    label.hide()
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                label.setText("Loading")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
                else:
                    label.show()
            return widgets

        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)
