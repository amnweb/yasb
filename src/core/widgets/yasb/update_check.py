import logging
import re
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.update_check import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from core.event_service import EventService

try:
    from core.utils.widgets.update_check import UpdateCheckService
except ImportError:
    UpdateCheckService = None
    logging.warning("Failed to load UpdateCheckService Event Listener")

class UpdateCheckWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    event_listener = UpdateCheckService
    windows_update_signal = pyqtSignal(object)
    winget_update_signal = pyqtSignal(object)

    def __init__(
        self,
        windows_update: dict[str, str],
        winget_update: dict[str, str]
    ):
        super().__init__(class_name="update-check-widget")
        self._event_service = EventService()

        self._windows_update = windows_update
        self._winget_update = winget_update

        self._window_update_enabled = self._windows_update['enabled']
        self._windows_update_label = self._windows_update['label']

        self._winget_update_enabled = self._winget_update['enabled']
        self._winget_update_label = self._winget_update['label']

        self.windows_update_data = 0
        self.winget_update_data = 0

        # Use the main layout directly
        self._create_dynamically_label(self._winget_update_label, self._windows_update_label)

        self.windows_update_signal.connect(self._on_windows_update_signal)
        self._event_service.register_event("windows_update", self.windows_update_signal)

        self.winget_update_signal.connect(self._on_winget_update_signal)
        self._event_service.register_event("winget_update", self.winget_update_signal)

        self.check_and_hide()
        self._update_label('winget', 0, [])
        self._update_label('windows', 0, [])

    def _create_dynamically_label(self, windows_label: str, winget_label: str):
        def process_content(label_text, label_type):
            # Create a new container for each set of labels
            container = QWidget()
            container_layout = QHBoxLayout()
            container_layout.setSpacing(0)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(container_layout)
            class_name = "windows" if label_type == "windows" else "winget"
            container.setProperty("class", f"widget-container {class_name}")
            self.widget_layout.addWidget(container)
            # Initially hide the container
            container.hide()
            # Split label text into parts, separating only span tags
            label_parts = re.split(r'(<span.*?>.*?</span>)', label_text)
            label_parts = [part for part in label_parts if part]
            widgets = []

            for part in label_parts:
                part = part.strip()
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
                container_layout.addWidget(label)
                widgets.append(label)

            return container, widgets

        if self._winget_update_enabled:
            self._winget_container, self._widget_widget = process_content(self._winget_update_label, "winget")
        if self._window_update_enabled:
            self._windows_container, self._widget_windows = process_content(self._windows_update_label, "windows")

    def _update_label(self, widget_type, data, names):
        if widget_type == 'winget':
            active_widgets = self._widget_widget
            active_label_content = self._winget_update_label
            container = self._winget_container
        elif widget_type == 'windows':
            active_widgets = self._widget_windows
            active_label_content = self._windows_update_label
            container = self._windows_container
        else:
            return

        label_parts = re.split(r'(<span.*?>.*?</span>)', active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0
        if data == 0:
            container.hide()
            return
        container.show()
        for part in label_parts:
            part = part.strip()
            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if '<span' in part and '</span>' in part:
                    # This part is an icon
                    icon = re.sub(r'<span.*?>|</span>', '', part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    # This part is text, replace {count} with actual data
                    formatted_text = part.format(count=data)
                    active_widgets[widget_index].setText(formatted_text)
                active_widgets[widget_index].setToolTip("\n".join(names))
                active_widgets[widget_index].setStyleSheet("""QToolTip { padding:4px;color: #cdd6f4;font-size:12px; background-color: #1e1e2e; border: 1px solid #313244;border-radius: 8px; }""")
                widget_index += 1

    def _on_windows_update_signal(self, data):
        self.windows_update_data = data['count']
        self._update_label('windows', self.windows_update_data, data['names'])
        self.check_and_hide()

    def _on_winget_update_signal(self, data):
        self.winget_update_data = data['count']
        self._update_label('winget', self.winget_update_data, data['names'])
        self.check_and_hide()

    def check_and_hide(self):
        if self.windows_update_data == 0 and self.winget_update_data == 0:
            self.hide()
        else:
            self.show()