import logging
import re
import subprocess
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from core.events.service import EventService
from core.utils.utilities import add_shadow
from core.utils.win32.system_function import function_map
from core.widgets.registry import register_widget_class


class BaseWidget(QWidget):
    validation_schema: dict[str, Any] | type[BaseModel] | None = None
    event_listener: QThread = None

    _hotkey_signal = pyqtSignal(str, str, str)

    def __init_subclass__(cls, **kwargs: Any):
        """Register the widget class with the registry"""
        super().__init_subclass__(**kwargs)
        register_widget_class(cls)

    def __init__(self, timer_interval: int = None, class_name: str = ""):
        super().__init__()
        self._widget_frame = QFrame()
        self._widget_frame_layout = QHBoxLayout()
        self.widget_layout = QHBoxLayout()
        self.timer_interval = timer_interval
        self.bar = None
        self.bar_id = None
        self.monitor_hwnd = None
        self.widget_name = None  # Set by WidgetBuilder after construction
        self.screen_name = None  # Set by BarManager when bar is created
        self._hotkey_enabled = True  # Set to False by BarManager for duplicate widgets

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

        self.callback_default: str | list[str] = "default"
        self.callback_timer: str | list[str] = "default"
        self.callback_left: str | list[str] = self.callback_default
        self.callback_middle: str | list[str] = self.callback_default
        self.callback_right: str | list[str] = self.callback_default

        self._event_service = EventService()
        self._hotkey_signal.connect(self._handle_hotkey_event)
        self._event_service.register_event("handle_widget_hotkey", self._hotkey_signal)

    def _handle_hotkey_event(self, widget_name: str, action: str, target_screen: str) -> None:
        """
        Handle incoming hotkey events.
        """
        if not self._hotkey_enabled:
            return

        # Check if this event is for our widget (by config name)
        if widget_name != self.widget_name:
            return

        # Only respond if screens match exactly
        if not target_screen or self.screen_name != target_screen:
            return

        # Execute the callback
        if action:
            self._run_callback(action)

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

    def _run_callback(self, callback_str: str | list):
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
            logging.exception("Failed to execute callback of type '%s' with args: %s", callback_type, callback_args)

    def _timer_callback(self):
        self._run_callback(self.callback_timer)

    def _cb_execute_subprocess(self, cmd: str, *cmd_args: list[str]):
        if cmd in function_map:
            function_map[cmd]()
        else:
            subprocess.Popen([cmd, *cmd_args] if cmd_args else [cmd], shell=True)

    def _cb_do_nothing(self):
        pass

    def _init_container(self, container_shadow: dict[str, Any] | None = None):
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        if container_shadow:
            add_shadow(self._widget_container, container_shadow)
        self.widget_layout.addWidget(self._widget_container)
        self._widgets: list[QLabel] = []
        self._widgets_alt: list[QLabel] = []

    def build_widget_label(
        self,
        content: str,
        content_alt: str | None = None,
        content_shadow: dict[str, Any] | None = None,
    ):
        def process_content(content: str, is_alt: bool = False) -> list[QLabel]:
            label_parts = re.split("(<span.*?>.*?</span>)", content)
            label_parts = [part for part in label_parts if part]
            widgets: list[QLabel] = []
            for part in label_parts:
                part = part.strip()
                if not part:
                    continue
                if "<span" in part and "</span>" in part:
                    class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    class_result = class_name.group(2) if class_name else "icon"
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    label = QLabel(icon)
                    label.setProperty("class", class_result)
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label alt" if is_alt else "label")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setCursor(Qt.CursorShape.PointingHandCursor)
                if content_shadow:
                    add_shadow(label, content_shadow)
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
                else:
                    label.show()
            return widgets

        self._widgets = process_content(content)
        if content_alt:
            self._widgets_alt = process_content(content_alt, is_alt=True)
