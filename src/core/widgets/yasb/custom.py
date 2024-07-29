import re
import subprocess
import json
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.custom import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt

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

        self._create_dynamically_label(self._label_content, self._label_alt_content)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("exec_custom", self._exec_callback)

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "exec_custom"

        if exec_options['run_once']:
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


    def _create_dynamically_label(self, content: str, content_alt: str):
        def process_content(content, is_alt=False):
            label_parts = re.split('(<span.*?>.*?</span>)', content)
            #label_parts = [part for part in label_parts if part]
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
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
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
        
    def _truncate_label(self, label):
        if self._label_max_length and len(label) > self._label_max_length:
            return label[:self._label_max_length] + "..."

        return label

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split('(<span.*?>.*?</span>)', active_label_content)
        #label_parts = [part for part in label_parts if part]
        widget_index = 0

        try:
         
            for part in label_parts:
                part = part.strip()
                if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                    if '<span' in part and '</span>' in part:
                        # Ensure the icon is correctly set
                        icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                        active_widgets[widget_index].setText(icon)
                    else:
                        active_widgets[widget_index].setText(self._truncate_label(part.format(data=self._exec_data)))
                    widget_index += 1
 
        except Exception:
            active_widgets[widget_index].setText(self._truncate_label(part))

    def _exec_callback(self):
        self._exec_data = None

        if self._exec_cmd:
            proc = subprocess.Popen(self._exec_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=False)
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
