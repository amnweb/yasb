from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.applications import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QApplication, QVBoxLayout
from PyQt6.QtCore import Qt
import os
import subprocess
import logging
from core.utils.win32.system_function import function_map

class ApplicationsWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(self, label: str, apps: dict[str, list[str]]):
        super().__init__(class_name="apps-widget")
        self._apps = apps
        self._label = ClickableLabel()
        self._update_label()

    def _update_label(self):
        for app_name, app_data in self._apps.items():
            if len(app_data) > 1:
                label = ClickableLabel(self)
                label.setProperty("class", f"label {app_name}")
                label.setText(app_data[0])
                label.data = app_data[1]  # Store the data to be executed
                self.widget_layout.addWidget(label)
                

    def execute_code(self, data):
        try:
            if data in function_map:
                function_map[data]()
            else:    
                subprocess.Popen(data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        except Exception as e:
            logging.error(f"Exception occurred: {str(e)} \"{data}\"")
 

class ClickableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.data = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.data:
            self.parent_widget.execute_code(self.data)
