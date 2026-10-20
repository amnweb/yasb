from PyQt6.QtWidgets import QLabel

from yasb_api import BaseWidget, WidgetConfig, set_tooltip

from .text import greeting


class HelloConfig(WidgetConfig):
    name: str = "world"
    tooltip: bool = True


class HelloWidget(BaseWidget):
    validation_schema = HelloConfig

    def __init__(self, config: HelloConfig):
        super().__init__(class_name="plugin-hello")
        self.label = QLabel(greeting(config.name))
        self.label.setProperty("class", "label")
        self.widget_layout.addWidget(self.label)
        if config.tooltip:
            set_tooltip(self.label, "Loaded from a YASB plugin")
