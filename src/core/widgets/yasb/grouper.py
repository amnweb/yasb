import logging
from typing import Any

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout

from core.config import get_config
from core.utils.utilities import add_shadow
from core.utils.widget_builder import WidgetBuilder
from core.validation.widgets.yasb.grouper import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class GrouperWidget(BaseWidget):
    validation_schema: dict[str, Any] = VALIDATION_SCHEMA
    # Track and prevent duplicate listener threads across multiple Grouper instances
    _started_listener_classes: set[type] = set()
    _listener_threads: dict[type, Any] = {}
    _listener_refcounts: dict[type, int] = {}

    def __init__(
        self,
        class_name: str,
        container_padding: dict[str, int],
        widgets: list[str] = [],
        container_shadow: dict = None,
        hide_empty: bool = False,
    ):
        super().__init__(class_name=class_name)
        self._padding = container_padding
        self._container_shadow = container_shadow
        self._hide_empty = hide_empty
        self._widgets_list = widgets
        self._child_widgets = []
        self._local_listeners = set()

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )

        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "container")
        add_shadow(self._widget_container, self._container_shadow)

        self.widget_layout.addWidget(self._widget_container)

        self._create_child_widgets()

    def _create_child_widgets(self):
        try:
            config = get_config()
            widets_config = config.get("widgets", {})

            widget_builder = WidgetBuilder(widets_config)

            for widget_name in self._widgets_list:
                child_widget = None
                try:
                    child_widget = widget_builder._build_widget(widget_name)
                    if child_widget:
                        # Propagate bar context to child widgets so they behave like top-level widgets
                        try:
                            child_widget.bar_id = self.bar_id
                            child_widget.monitor_hwnd = self.monitor_hwnd
                            child_widget.parent_layout_type = getattr(self, "parent_layout_type", None)
                        except Exception:
                            pass
                        self._child_widgets.append(child_widget)
                        self._widget_container_layout.addWidget(child_widget)
                    else:
                        logging.warning(f"GrouperWidget failed to create child widget '{widget_name}'")
                except Exception as e:
                    logging.error(f"GrouperWidget error creating child widget '{widget_name}': {e}")
                if self._hide_empty and child_widget:
                    try:
                        child_widget.installEventFilter(self)
                        child_widget.destroyed.connect(self._handle_child_destroyed)
                    except Exception:
                        logging.error(
                            "GrouperWidget failed to install visibility event filter on child widget '%s'",
                            widget_name,
                        )
            widget_builder.raise_alerts_if_errors_present()
        except Exception as e:
            logging.error(f"GrouperWidget error initializing child widgets: {e}")

    def _propagate_bar_context(self) -> None:
        """Propagate bar context to existing child widgets."""
        try:
            for cw in self._child_widgets:
                try:
                    cw.bar_id = self.bar_id
                    cw.monitor_hwnd = self.monitor_hwnd
                    cw.parent_layout_type = getattr(self, "parent_layout_type", None)
                except Exception:
                    pass
        except Exception:
            logging.error("GrouperWidget failed to propagate bar context to child widgets")

    def showEvent(self, event):
        self._propagate_bar_context()
        if self._hide_empty:
            self._update_grouper_visibility()
        super().showEvent(event)

    def eventFilter(self, obj, event):
        if self._hide_empty and obj in self._child_widgets:
            if event.type() in (QEvent.Type.Show, QEvent.Type.ShowToParent, QEvent.Type.Hide, QEvent.Type.HideToParent):
                try:
                    self._update_grouper_visibility()
                except RuntimeError:
                    pass

        return super().eventFilter(obj, event)

    def _update_grouper_visibility(self):
        try:
            if not self._hide_empty:
                return

            pruned_children: list[Any] = []
            any_visible = False

            for child in self._child_widgets:
                if child is None:
                    continue
                try:
                    if not child.isHidden():
                        any_visible = True
                    pruned_children.append(child)
                except RuntimeError:
                    continue

            self._child_widgets = pruned_children

            try:
                self.setVisible(any_visible)
            except RuntimeError:
                pass
        except Exception:
            logging.error("GrouperWidget failed to update visibility based on child widgets")

    def _handle_child_destroyed(self, obj=None):
        try:
            if obj in self._child_widgets:
                self._child_widgets.remove(obj)
            self._update_grouper_visibility()
        except Exception:
            logging.error("GrouperWidget failed to handle child widget destruction")
