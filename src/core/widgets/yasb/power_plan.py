import logging
import re

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from core.events.service import EventService
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.utils.win32.structs import GUID
from core.validation.widgets.yasb.power_plan import PowerPlanConfig
from core.widgets.base import BaseWidget
from core.widgets.services.power_plan.power_plan_api import PowerPlanInfo, PowerPlanService


class PowerPlanWidget(BaseWidget):
    validation_schema = PowerPlanConfig

    power_plan_changed_signal = pyqtSignal()

    def __init__(self, config: PowerPlanConfig) -> None:
        super().__init__(class_name=f"power-plan-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False

        self._plans: list[PowerPlanInfo] = []
        self._active_guid: GUID | None = None
        self._active_plan_name: str = "Unknown"
        self._plan_class_name: str = "unknown"

        self._event_service = EventService()

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_menu", self._show_menu)
        self.register_callback("toggle_label", self._toggle_label)
        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        PowerPlanService.initialize_listener()

        self.power_plan_changed_signal.connect(self._on_power_plan_changed)
        self._event_service.register_event("power_plan_changed", self.power_plan_changed_signal)

        self._fetch_and_refresh()

    def _on_power_plan_changed(self) -> None:
        """Receive a power plan change notification and re-query Windows on the main thread."""
        self._fetch_and_refresh()

    def _fetch_and_refresh(self) -> None:
        """Query current power plans from Windows and refresh the label."""
        try:
            plans, active_guid = PowerPlanService.instance().get_power_plans()
            self._apply_plan_data(plans, active_guid)
        except Exception as exc:
            logging.error("Error fetching power plans: %s", exc)

    def _apply_plan_data(self, plans: list[PowerPlanInfo], active_guid: GUID | None) -> None:
        """Store plan data and update the label."""
        svc = PowerPlanService.instance()
        if self._active_guid and active_guid and svc.guids_equal(self._active_guid, active_guid):
            return

        self._plans = plans
        self._active_guid = active_guid
        self._active_plan_name = "Unknown"
        self._plan_class_name = "unknown"

        if active_guid:
            svc = PowerPlanService.instance()
            for plan in plans:
                if svc.guids_equal(plan.guid, active_guid):
                    self._active_plan_name = plan.name

                    plan_guid_str = str(plan.guid).lower()
                    print(plan_guid_str)
                    if plan.name in self.config.class_map:
                        self._plan_class_name = self.config.class_map[plan.name]
                    elif plan_guid_str in self.config.class_map:
                        self._plan_class_name = self.config.class_map[plan_guid_str]
                    else:
                        self._plan_class_name = plan.name.replace(" ", "-").lower()
                    break

        self._update_label()

    def _toggle_label(self) -> None:
        """Toggle between main and alt labels."""
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self) -> None:
        """Render the current plan name into the label widgets."""
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        label_options = {"{active_plan}": self._active_plan_name}

        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                    active_widgets[widget_index].setText(formatted_text)
                    alt_class = "alt" if self._show_alt_label else ""
                    base_class = "icon" if "<span" in part else f"label {alt_class}"
                    active_widgets[widget_index].setProperty("class", f"{base_class} {self._plan_class_name}")
                    refresh_widget_style(active_widgets[widget_index])
                widget_index += 1

    def _show_menu(self) -> None:
        """Show the power plan selection popup."""

        self._popup_menu = PopupWidget(
            self,
            self.config.menu.blur,
            self.config.menu.round_corners,
            self.config.menu.round_corners_type,
            self.config.menu.border_color,
        )
        self._popup_menu.setProperty("class", "power-plan-menu")

        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        frame.setProperty("class", "menu-content")

        frame_layout = QVBoxLayout()
        frame_layout.setSpacing(0)
        frame_layout.setContentsMargins(0, 0, 0, 0)

        svc = PowerPlanService.instance()
        for plan in self._plans:
            btn = QPushButton(plan.name)
            is_active = self._active_guid is not None and svc.guids_equal(plan.guid, self._active_guid)
            btn.setProperty("class", "button active" if is_active else "button")
            btn.clicked.connect(lambda checked, g=plan.guid, n=plan.name: self._change_plan(g, n))
            frame_layout.addWidget(btn)

        frame.setLayout(frame_layout)
        main_layout.addWidget(frame)

        self._popup_menu.setLayout(main_layout)
        self._popup_menu.adjustSize()
        self._popup_menu.setPosition(
            self.config.menu.alignment,
            self.config.menu.direction,
            self.config.menu.offset_left,
            self.config.menu.offset_top,
        )
        self._popup_menu.show()

    def _change_plan(self, guid: GUID, name: str) -> None:
        """Activate a power plan chosen from the popup menu."""
        self._popup_menu.hide()

        svc = PowerPlanService.instance()
        if self._active_guid and svc.guids_equal(guid, self._active_guid):
            return

        try:
            result = svc.set_power_plan(guid)
            if result == 0:
                plans, active_guid = svc.get_power_plans()
                self._apply_plan_data(plans, active_guid)
                EventService().emit_event("power_plan_changed")
            else:
                logging.error("Failed to change power plan. Error code: %s", result)
        except Exception as exc:
            logging.error("Error changing power plan: %s", exc)
