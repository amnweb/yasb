import logging
from typing import Any

from PyQt6.QtWidgets import QHBoxLayout, QWidget

from core.config import get_config
from core.utils.utilities import add_shadow
from core.utils.widget_builder import WidgetBuilder
from core.validation.widgets.yasb.grouper import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class GrouperWidget(BaseWidget):
    validation_schema: dict[str, Any] = VALIDATION_SCHEMA

    def __init__(
        self,
        class_name: str,
        container_padding: dict[str, int],
        widgets: list[str] = [],
        container_shadow: dict = None,
    ):
        super().__init__(class_name=class_name)
        self._padding = container_padding
        self._container_shadow = container_shadow
        self._widgets_list = widgets
        self._child_widgets = []
        
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
       
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "container")
        add_shadow(self._widget_container, self._container_shadow)

        self.widget_layout.addWidget(self._widget_container)

        self._create_child_widgets()

    def _create_child_widgets(self):
        try:
            config = get_config()
            widets_config = config.get('widgets', {})

            widget_builder = WidgetBuilder(widets_config)
            
            for widget_name in self._widgets_list:
                try:
                    child_widget = widget_builder._build_widget(widget_name)
                    if child_widget:
                        self._child_widgets.append(child_widget)
                        self._widget_container_layout.addWidget(child_widget)
                    else:
                        logging.warning(f"GrouperWidget: Failed to create child widget '{widget_name}'")
                except Exception as e:
                    logging.error(f"GrouperWidget: Error creating child widget '{widget_name}': {e}")
            widget_builder.raise_alerts_if_errors_present()
        except Exception as e:
            logging.error(f"GrouperWidget: Error initializing child widgets: {e}")
