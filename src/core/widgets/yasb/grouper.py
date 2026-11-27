import json
import logging
from collections.abc import Callable, Mapping
from typing import Any, cast, override

from PyQt6.QtCore import QEvent, QObject, QThread
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPushButton

from core.utils.system import app_data_path
from core.utils.widget_builder import WidgetBuilder
from core.utils.win32.utils import get_widget_monitor_hwnd
from core.validation.widgets.yasb.grouper import GrouperWidgetConfig
from core.widgets.base import BaseWidget

# Collapsed state of each grouper, keyed by screen and widget name, so it survives restarts
STATE_FILE = "grouper_state.json"


class GrouperWidget(BaseWidget):
    validation_schema = GrouperWidgetConfig
    # Track and prevent duplicate listener threads across multiple Grouper instances
    _started_listener_classes: set[type] = set()
    _listener_threads: dict[type, Any] = {}
    _listener_refcounts: dict[type, int] = {}

    def __init__(self, config: GrouperWidgetConfig, widget_configs: Mapping[str, Any] | None = None):
        super().__init__(class_name=config.class_name)
        self.config = config
        self._widget_configs = widget_configs or {}
        self._hide_empty = self.config.hide_empty
        # Use collapse_options structure
        self._collapse_options = self.config.collapse_options
        self._collapsed = self._collapse_options.enabled
        self._exclude_widgets = self._collapse_options.exclude_widgets
        self._widgets_list = self.config.widgets
        self._child_widgets: list[BaseWidget] = []
        self._child_widget_names: dict[BaseWidget, str] = {}
        self._local_listeners: set[type[QThread]] = set()
        self._state_restored = False

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)

        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "container")

        self._collapse_button = None
        if self._collapsed:
            self._collapse_button = QPushButton()
            self._collapse_button.setProperty("class", "grouper-button")
            self._expanded_icon = self._collapse_options.expanded_label
            self._collapsed_icon = self._collapse_options.collapsed_label
            self._collapse_button.setText(self._collapsed_icon)
            self._collapse_button.setFlat(True)

            if self._collapse_options.label_position.lower() == "left":
                self._widget_container_layout.addWidget(self._collapse_button)
            self._collapse_button.clicked.connect(self._toggle_collapsed)

        self.widget_layout.addWidget(self._widget_container)

        # Register keybinding callback
        self.register_callback("toggle_collapse", self._toggle_collapsed)

        self._create_child_widgets()

        if self._collapsed and self._collapse_options.label_position.lower() == "right":
            self._widget_container_layout.addWidget(self._collapse_button)

    def _create_child_widgets(self):
        try:
            widget_builder = WidgetBuilder(self._widget_configs)

            for widget_name in self._widgets_list:
                child_widget = None
                try:
                    child_widget = widget_builder.build_widget(widget_name)
                    if child_widget:
                        # Propagate bar context to child widgets so they behave like top-level widgets
                        try:
                            child_widget.bar_id = self.bar_id
                            child_widget.monitor_hwnd = self.monitor_hwnd
                            child_widget.parent_layout_type = self.parent_layout_type
                        except Exception:
                            pass
                        self._child_widgets.append(child_widget)
                        self._child_widget_names[child_widget] = widget_name  # Store mapping

                        # Override setVisible to respect collapsed state
                        if self._collapse_button:
                            original_setVisible = child_widget.setVisible

                            def make_visibility_overrides(widget_name: str, original: Callable[[bool], None]):
                                def setVisible_override(visible: bool) -> None:
                                    # If collapsed and not excluded, force hidden
                                    if self._collapsed and widget_name not in self._exclude_widgets:
                                        original(False)
                                    else:
                                        original(visible)

                                def show_override() -> None:
                                    # If collapsed and not excluded, don't show
                                    if self._collapsed and widget_name not in self._exclude_widgets:
                                        original(False)
                                    else:
                                        original(True)

                                def hide_override() -> None:
                                    original(False)

                                return setVisible_override, show_override, hide_override

                            setVisible, show, hide = make_visibility_overrides(widget_name, original_setVisible)
                            child_widget.setVisible = setVisible
                            child_widget.show = show
                            child_widget.hide = hide

                        self._widget_container_layout.addWidget(child_widget)
                    else:
                        logging.warning("GrouperWidget failed to create child widget '%s'", widget_name)
                except Exception as e:
                    logging.error("GrouperWidget error creating child widget '%s': %s", widget_name, e)
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
            logging.error("GrouperWidget error initializing child widgets: %s", e)

    def _propagate_bar_context(self) -> None:
        """Propagate bar context to existing child widgets."""
        try:
            monitor_hwnd = get_widget_monitor_hwnd(self)
            if monitor_hwnd is None:
                return
            for cw in self._child_widgets:
                try:
                    cw.bar_id = self.bar_id
                    cw.monitor_hwnd = monitor_hwnd
                    cw.screen_name = self.screen_name
                    cw.parent_layout_type = self.parent_layout_type
                except Exception:
                    pass
        except Exception:
            logging.error("GrouperWidget failed to propagate bar context to child widgets")

    @override
    def showEvent(self, a0: QShowEvent | None) -> None:
        self._propagate_bar_context()
        # widget_name and screen_name are only set after construction, so restore on the first show
        if not self._state_restored:
            self._state_restored = True
            self._restore_collapsed_state()
        if self._hide_empty:
            self._update_grouper_visibility()
        super().showEvent(a0)

    @override
    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if self._hide_empty and a1 is not None and a0 in self._child_widgets:
            if a1.type() in (QEvent.Type.Show, QEvent.Type.ShowToParent, QEvent.Type.Hide, QEvent.Type.HideToParent):
                try:
                    self._update_grouper_visibility()
                except RuntimeError:
                    pass

        return super().eventFilter(a0, a1)

    def _update_grouper_visibility(self):
        try:
            if not self._hide_empty:
                return

            pruned_children: list[BaseWidget] = []
            any_visible = False

            for child in self._child_widgets:
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

    def _toggle_collapsed(self):
        self._set_collapsed(not self._collapsed)
        self._save_collapsed_state()

    def _set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        if self._collapse_button:
            if self._collapsed:
                self._collapse_button.setText(self._collapsed_icon)
            else:
                self._collapse_button.setText(self._expanded_icon)
        self._apply_collapsed_state()

    def _state_key(self) -> str | None:
        # Only groupers with a collapse button have a state worth remembering
        if not self._collapse_button or not self.widget_name or not self.screen_name:
            return None
        return f"{self.screen_name}:{self.widget_name}"

    @staticmethod
    def _load_saved_states() -> dict[str, bool]:
        try:
            with open(app_data_path(STATE_FILE), encoding="utf-8") as f:
                data: object = json.load(f)
        except FileNotFoundError:
            return {}
        except OSError, ValueError:
            logging.warning("GrouperWidget failed to read %s, ignoring it", STATE_FILE)
            return {}
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in cast(dict[str, object], data).items() if isinstance(v, bool)}

    def _restore_collapsed_state(self) -> None:
        key = self._state_key()
        if key is None:
            return
        collapsed = self._load_saved_states().get(key)
        if collapsed is not None and collapsed != self._collapsed:
            self._set_collapsed(collapsed)

    def _save_collapsed_state(self) -> None:
        key = self._state_key()
        if key is None:
            return
        states = self._load_saved_states()
        states[key] = self._collapsed
        try:
            with open(app_data_path(STATE_FILE), "w", encoding="utf-8") as f:
                json.dump(states, f, indent=2)
        except OSError:
            logging.warning("GrouperWidget failed to save %s", STATE_FILE)

    def _apply_collapsed_state(self):
        # Hide or show children based on collapse state, respecting exclude_widgets
        if self._collapsed:
            for child in list(self._child_widgets):
                widget_name = self._child_widget_names.get(child)
                if widget_name and widget_name in self._exclude_widgets:
                    child.setVisible(True)
                else:
                    child.setVisible(False)
            if self._hide_empty:
                self.setVisible(True)
        else:
            for child in list(self._child_widgets):
                child.setVisible(True)
            if self._hide_empty:
                self._update_grouper_visibility()

    def _handle_child_destroyed(self, obj: QObject | None = None) -> None:
        try:
            self._child_widgets = [child for child in self._child_widgets if child is not obj]
            self._update_grouper_visibility()
        except Exception:
            logging.error("GrouperWidget failed to handle child widget destruction")
