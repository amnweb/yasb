from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from core.utils.qobject import is_valid_qobject
from core.utils.utilities import PopupWidget
from core.validation.widgets.yasb.control_center import ControlCenterConfig
from core.widgets.base import BaseWidget
from core.widgets.services.brightness.service import BrightnessService
from core.widgets.services.control_center.sections.media import MediaSectionWidget
from core.widgets.services.control_center.sections.power import PowerSectionWidget
from core.widgets.services.control_center.sections.quick_actions import QuickActionsSectionWidget
from core.widgets.services.control_center.sections.sliders import SlidersSectionWidget
from core.widgets.services.control_center.sections.system_controls import SystemControlsSectionWidget
from core.widgets.services.microphone.service import AudioInputService
from core.widgets.services.volume.service import AudioOutputService


class ControlCenterWidget(BaseWidget):
    validation_schema = ControlCenterConfig

    def __init__(self, config: ControlCenterConfig):
        super().__init__(class_name=f"control-center-widget {config.class_name}")
        self.config = config

        self.dialog = None
        self._section_widgets: dict[str, QWidget] = {}
        self._sections = {
            "system_controls": (config.sections.system_controls, self._build_system_controls_section),
            "quick_actions": (config.sections.quick_actions, self._build_quick_actions_section),
            "sliders": (config.sections.sliders, self._build_sliders_section),
            "power": (config.sections.power, self._build_power_section),
            "media": (config.sections.media, self._build_media_section),
        }

        sliders = config.sections.sliders
        actions = config.sections.quick_actions.actions
        action_ids = {a.id for a in actions}

        self._brightness_service = (
            BrightnessService.instance() if sliders.show and sliders.brightness.show_slider else None
        )
        if self._brightness_service is not None:
            self._brightness_service.brightness_changed.connect(self._on_brightness_service_changed)

        self._output_service = None
        if (sliders.show and sliders.volume.show_slider) or "toggle_mute" in action_ids:
            self._output_service = AudioOutputService()
            self._output_service.register_widget(self)
            self.destroyed.connect(lambda: self._output_service.unregister_widget(self))

        self._input_service = None
        if (sliders.show and sliders.microphone.show_slider) or "toggle_mic_mute" in action_ids:
            self._input_service = AudioInputService()
            self._input_service.register_widget(self)
            self.destroyed.connect(lambda: self._input_service.unregister_widget(self))

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_menu", self._toggle_menu)

        self.callback_left = self.config.callbacks.on_left
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_right = self.config.callbacks.on_right

    @property
    def _hmonitor(self) -> int | None:
        return self.monitor_hwnd

    def _audio_services(self) -> dict[str, object]:
        return {
            "output": self._output_service,
            "input": self._input_service,
        }

    def _on_brightness_service_changed(self, hmonitor: int, brightness: int):
        if not self.dialog or not is_valid_qobject(self.dialog) or not self.dialog.isVisible():
            return
        sliders = self._section_widgets.get("sliders")
        if is_valid_qobject(sliders):
            sliders.update_brightness(hmonitor, brightness)

    def _toggle_menu(self):
        if self.dialog and is_valid_qobject(self.dialog) and self.dialog.isVisible():
            self.dialog.hide_animated()
        else:
            self._show_menu()

    def _show_menu(self):
        if not (self.dialog and is_valid_qobject(self.dialog)):
            self.dialog = PopupWidget(
                parent=self,
                blur=self.config.popup.blur,
                round_corners=self.config.popup.round_corners,
                round_corners_type=self.config.popup.round_corners_type,
                border_color=self.config.popup.border_color,
                persistent=True,
            )
            self.dialog.setProperty("class", "control-center-menu")
            layout = QVBoxLayout(self.dialog)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            for section_name in self.config.sections_order:
                section_config, builder = self._sections[section_name]
                if section_config.show:
                    widget = builder()
                    self._section_widgets[section_name] = widget
                    layout.addWidget(widget)

        self.dialog.setPosition(
            alignment=self.config.popup.alignment,
            direction=self.config.popup.direction,
            offset_left=self.config.popup.offset_left,
            offset_top=self.config.popup.offset_top,
        )
        self.dialog.show()
        self._refresh_popup_state()

    def _refresh_popup_state(self):
        if not self.dialog or not is_valid_qobject(self.dialog) or not self.dialog.isVisible():
            return

        for widget in self._section_widgets.values():
            if is_valid_qobject(widget):
                try:
                    widget.refresh_state()
                except Exception:
                    pass

        if self._brightness_service is not None:
            self._brightness_service.refresh_now()

    def _build_system_controls_section(self) -> QWidget:
        return SystemControlsSectionWidget(
            self.dialog,
            self.config.sections.system_controls,
            self._refresh_popup_state,
            self.config.tooltip,
        )

    def _build_quick_actions_section(self) -> QWidget:
        return QuickActionsSectionWidget(
            self.dialog,
            self.config.sections.quick_actions,
            self._refresh_popup_state,
            self._audio_services(),
            self.config.tooltip,
        )

    def _build_sliders_section(self) -> QWidget:
        return SlidersSectionWidget(
            self.dialog,
            self.config.sections.sliders,
            self._refresh_popup_state,
            self._audio_services(),
            self._brightness_service,
            self._hmonitor,
            self.config.tooltip,
        )

    def _build_power_section(self) -> QWidget:
        return PowerSectionWidget(
            self.dialog,
            self.config.sections.power,
        )

    def _build_media_section(self) -> QWidget:
        return MediaSectionWidget(
            self.dialog,
            self.config.sections.media,
        )

    def _reinitialize_audio(self):
        self._refresh_popup_state()

    def _reinitialize_microphone(self):
        self._refresh_popup_state()
