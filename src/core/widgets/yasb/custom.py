import json
import re
import subprocess
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from core.utils.tooltip import set_tooltip
from core.utils.win32.system_function import function_map
from core.validation.widgets.yasb.custom import CustomConfig
from core.widgets.base import BaseWidget

type JsonValue = dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None


class CustomWorker(QObject):
    finished = pyqtSignal()
    data_ready = pyqtSignal(object)

    def __init__(
        self,
        cmd: str | None,
        use_shell: bool,
        encoding: str | None,
        return_type: str,
        hide_empty: bool,
    ):
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
            output, _ = proc.communicate()
            if self.return_type == "json":
                try:
                    exec_data = json.loads(output)
                except json.JSONDecodeError:
                    exec_data = None
            else:
                text = output if isinstance(output, str) else output.decode("utf-8")
                exec_data = text.strip()

        if self._is_running:
            try:
                self.data_ready.emit(exec_data)
                self.finished.emit()
            except RuntimeError:
                pass


class CustomWidget(BaseWidget):
    validation_schema = CustomConfig

    def __init__(self, config: CustomConfig):
        super().__init__(config.exec_options.run_interval, class_name=f"custom-widget {config.class_name}")
        self.config = config
        self._exec_data: JsonValue = None
        self._exec_cmd = self.config.exec_options.run_cmd
        self._show_alt_label = False
        self._worker = None  # Keep reference to worker for cleanup

        # Construct container
        self._init_container()
        self.build_widget_label(
            self.config.label, self.config.label_alt, label_placeholder=self.config.label_placeholder
        )

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("exec_custom", self._exec_callback)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_timer = "exec_custom"

        if self.config.exec_options.run_once:
            self._exec_callback()
        else:
            self.start_timer()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _truncate_label(self, label: str) -> str:
        if self.config.label_max_length and len(label) > self.config.label_max_length:
            return label[: self.config.label_max_length] + "..."
        return label

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        widget_index = 0
        part = ""
        try:
            for part in label_parts:
                part = part.strip()
                if part and widget_index < len(active_widgets):
                    if "<span" in part and "</span>" in part:
                        icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                        active_widgets[widget_index].setText(icon)
                    else:
                        active_widgets[widget_index].setText(self._truncate_label(part.format(data=self._exec_data)))
                    if self.config.exec_options.hide_empty:
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
        if not self.config.tooltip:
            return

        tooltip_text = None

        # If custom tooltip_label provided, use it with formatting
        if self.config.tooltip_label:
            try:
                if self.config.exec_options.run_cmd:
                    tooltip_text = self.config.tooltip_label.format(data=self._exec_data)
                else:
                    tooltip_text = self.config.tooltip_label

            except KeyError, AttributeError, TypeError, IndexError:
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
                self._exec_cmd,
                self.config.exec_options.use_shell,
                self.config.exec_options.encoding,
                self.config.exec_options.return_format,
                self.config.exec_options.hide_empty,
            )
            worker_thread = threading.Thread(target=self._worker.run)
            self._worker.data_ready.connect(self._handle_exec_data)
            self._worker.finished.connect(self._worker.deleteLater)
            worker_thread.start()
        else:
            self._update_label()

    def _handle_exec_data(self, exec_data: JsonValue) -> None:
        self._exec_data = exec_data
        self._update_label()

    def _cb_execute_subprocess(self, cmd: str, *cmd_args: str):
        # Overrides the default 'exec' callback from BaseWidget to allow for data formatting
        args: list[str] = list(cmd_args)
        if self._exec_data:
            args = []
            for cmd_arg in cmd_args:
                try:
                    args.append(cmd_arg.format(data=self._exec_data))
                except KeyError:
                    args.append(cmd_arg)
        if cmd in function_map:
            function_map[cmd]()
        else:
            subprocess.Popen(
                [cmd, *args],
                shell=self.config.exec_options.use_shell,
                encoding=self.config.exec_options.encoding,
            )
