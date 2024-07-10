import subprocess
import json
from PyQt6.QtWidgets import QLabel
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.custom import VALIDATION_SCHEMA


class CustomWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            label: str,
            label_alt: str,
            label_max_length: int,
            exec_options: dict,
            callbacks: dict,
            class_name: str
    ):
        super().__init__(exec_options['run_interval'], class_name=f"custom-widget {class_name}")
        self._label_max_length = label_max_length
        self._exec_data = None
        self._exec_cmd = exec_options['run_cmd'].split(" ") if exec_options.get('run_cmd', False) else None
        self._exec_return_type = exec_options['return_format']

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt

        self._label = QLabel()
        self._label_alt = QLabel()
        self._label.setProperty("class", "label")
        self._label_alt.setProperty("class", "label alt")
        self.widget_layout.addWidget(self._label)
        self.widget_layout.addWidget(self._label_alt)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("exec_custom", self._exec_callback)

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "exec_custom"

        self._label.show()
        self._label_alt.hide()
        self._update_label()

        if exec_options['run_once']:
            self._exec_callback()
        else:
            self.start_timer()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label

        if self._show_alt_label:
            self._label.hide()
            self._label_alt.show()
        else:
            self._label.show()
            self._label_alt.hide()

        self._update_label()

    def _truncate_label(self, label):
        if self._label_max_length and len(label) > self._label_max_length:
            return label[:self._label_max_length] + "..."

        return label

    def _update_label(self):
        active_label = self._label_alt if self._show_alt_label else self._label
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content

        try:
            active_label.setText(self._truncate_label(active_label_content.format(data=self._exec_data)))
        except Exception:
            active_label.setText(self._truncate_label(active_label_content))

    def _exec_callback(self):
        self._exec_data = None

        if self._exec_cmd:
            proc = subprocess.Popen(self._exec_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
            output = proc.stdout.read()

            if self._exec_return_type == "json":
                self._exec_data = json.loads(output)
            else:
                self._exec_data = output.decode('utf-8').strip()

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
        subprocess.Popen([cmd, *cmd_args] if cmd_args else [cmd], shell=True)
