import json
import re
import subprocess
import threading

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.tooltip import set_tooltip
from core.utils.utilities import add_shadow
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.system_function import function_map
from core.validation.widgets.yasb.custom import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class CustomWorker(QObject):
    finished = pyqtSignal()
    data_ready = pyqtSignal(object)

    def __init__(self, cmd, use_shell, encoding, return_type, hide_empty):
        super().__init__()
        self.cmd = cmd
        self.use_shell = use_shell
        self.encoding = encoding
        self.return_type = return_type
        self.hide_empty = hide_empty
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        exec_data = None
        if self.cmd and self._is_running:
            proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                shell=self.use_shell,
                encoding=self.encoding,
            )
            output = proc.stdout.read()
            if self.return_type == "json":
                try:
                    exec_data = json.loads(output)
                except json.JSONDecodeError:
                    exec_data = None
            else:
                exec_data = output.decode("utf-8").strip()

        if self._is_running:
            try:
                self.data_ready.emit(exec_data)
                self.finished.emit()
            except RuntimeError:
                pass


class CustomWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        label_placeholder: str,
        label_max_length: int,
        exec_options: dict,
        callbacks: dict,
        animation: dict[str, str],
        container_padding: dict[str, int],
        class_name: str,
        tooltip: bool = False,
        tooltip_label: str | None = None,
        label_shadow: dict | None = None,
        container_shadow: dict | None = None,
    ):
        super().__init__(exec_options["run_interval"], class_name=f"custom-widget {class_name}")
        self._label_max_length = label_max_length
        self._exec_data = None
        self._exec_cmd = exec_options["run_cmd"].split(" ") if exec_options.get("run_cmd", False) else None
        self._exec_return_type = exec_options["return_format"]
        self._exec_shell = exec_options["use_shell"]
        self._exec_encoding = exec_options["encoding"]
        self._hide_empty = exec_options["hide_empty"]
        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._label_placeholder = label_placeholder
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._tooltip = tooltip
        self._tooltip_label = tooltip_label
        self._worker = None  # Keep reference to worker for cleanup
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

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("exec_custom", self._exec_callback)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "exec_custom"

        self._create_dynamically_label(self._label_content, self._label_alt_content)

        if exec_options["run_once"]:
            self._exec_callback()
        else:
            self.start_timer()

    def _set_cursor(self, label):
        if any(cb != "do_nothing" for cb in [self.callback_left, self.callback_right, self.callback_middle]):
            label.setCursor(Qt.CursorShape.PointingHandCursor)

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split("(<span.*?>.*?</span>)", content)
            widgets = []
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
                    label.setText(self._label_placeholder)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._set_cursor(label)
                add_shadow(label, self._label_shadow)
                self._widget_container_layout.addWidget(label)
                widgets.append(label)
                if is_alt:
                    label.hide()
                else:
                    label.show()

            return widgets

        self._widgets = process_content(content)
        self._widgets_alt = process_content(content_alt, is_alt=True)

    def _truncate_label(self, label):
        if self._label_max_length and len(label) > self._label_max_length:
            return label[: self._label_max_length] + "..."
        return label

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        widget_index = 0
        try:
            for part in label_parts:
                part = part.strip()
                if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                    if "<span" in part and "</span>" in part:
                        icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                        active_widgets[widget_index].setText(icon)
                    else:
                        active_widgets[widget_index].setText(self._truncate_label(part.format(data=self._exec_data)))
                    if self._hide_empty:
                        if self._exec_data:
                            self.setVisible(True)
                            # active_widgets[widget_index].show()
                        else:
                            self.setVisible(False)
                            # active_widgets[widget_index].hide()
                    widget_index += 1
        except Exception:
            active_widgets[widget_index].setText(self._truncate_label(part))

        # Update tooltip if enabled
        self._update_tooltip()

    def _update_tooltip(self):
        """Update the tooltip text based on configuration and data."""
        if not self._tooltip or not self._exec_data:
            return

        tooltip_text = None

        # If custom tooltip_label provided, use it with formatting
        if self._tooltip_label:
            try:
                tooltip_text = self._tooltip_label.format(data=self._exec_data)
            except (KeyError, AttributeError, TypeError, IndexError):
                # If formatting fails, fall back to showing raw data
                tooltip_text = str(self._exec_data)
        else:
            tooltip_text = (
                json.dumps(self._exec_data, indent=2) if isinstance(self._exec_data, dict) else str(self._exec_data)
            )

        if tooltip_text:
            set_tooltip(self._widget_container, tooltip_text, delay=400)

    def _exec_callback(self):
        if self._exec_cmd:
            if self._worker:
                self._worker.stop()

            self._worker = CustomWorker(
                self._exec_cmd, self._exec_shell, self._exec_encoding, self._exec_return_type, self._hide_empty
            )
            worker_thread = threading.Thread(target=self._worker.run)
            self._worker.data_ready.connect(self._handle_exec_data)
            self._worker.finished.connect(self._worker.deleteLater)
            worker_thread.start()
        else:
            self._update_label()

    def _handle_exec_data(self, exec_data):
        self._exec_data = exec_data
        self._update_label()

    def _cb_execute_subprocess(self, cmd: str, *cmd_args: list[str]):
        # Overrides the default 'exec' callback from BaseWidget to allow for data formatting
        if self._exec_data:
            formatted_cmd_args = []
            for cmd_arg in cmd_args:
                try:
                    formatted_cmd_args.append(cmd_arg.format(data=self._exec_data))
                except KeyError:
                    formatted_cmd_args.append(cmd_args)
            cmd_args = formatted_cmd_args
        if cmd in function_map:
            function_map[cmd]()
        else:
            subprocess.Popen(
                [cmd, *cmd_args] if cmd_args else [cmd], shell=self._exec_shell, encoding=self._exec_encoding
            )
