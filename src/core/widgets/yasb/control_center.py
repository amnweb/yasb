from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout

from core.utils.qobject import is_valid_qobject
from core.utils.utilities import PopupWidget
from core.utils.win32.utils import get_widget_monitor_hwnd
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

type SectionWidget = (
    SystemControlsSectionWidget
    | QuickActionsSectionWidget
    | SlidersSectionWidget
    | PowerSectionWidget
    | MediaSectionWidget
)


class ControlCenterWidget(BaseWidget):
    validation_schema = ControlCenterConfig

    def __init__(self, config: ControlCenterConfig):
        super().__init__(class_name=f"control-center-widget {config.class_name}")
        self.config = config

        self.dialog: PopupWidget | None = None
        self._section_widgets: dict[str, SectionWidget] = {}
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

        self._output_service: AudioOutputService | None = None
        if (sliders.show and sliders.volume.show_slider) or "toggle_mute" in action_ids:
            output_service = AudioOutputService()
            output_service.register_widget(self)
            self.destroyed.connect(lambda: output_service.unregister_widget(self))
            self._output_service = output_service

        self._input_service: AudioInputService | None = None
        if (sliders.show and sliders.microphone.show_slider) or "toggle_mic_mute" in action_ids:
            input_service = AudioInputService()
            input_service.register_widget(self)
            self.destroyed.connect(lambda: input_service.unregister_widget(self))
            self._input_service = input_service

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.register_callback("toggle_menu", self._toggle_menu)

        self.callback_left = self.config.callbacks.on_left
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_right = self.config.callbacks.on_right

    @property
    def _hmonitor(self) -> int | None:
        return get_widget_monitor_hwnd(self)

    def _on_brightness_service_changed(self, hmonitor: int, brightness: int | None):
        if not self.dialog or not is_valid_qobject(self.dialog) or not self.dialog.isVisible():
            return
        sliders = self._section_widgets.get("sliders")
        if isinstance(sliders, SlidersSectionWidget) and is_valid_qobject(sliders):
            sliders.update_brightness(hmonitor, brightness)

    def _toggle_menu(self):
        if self.dialog and is_valid_qobject(self.dialog) and self.dialog.isVisible():
            self.dialog.hide_animated()
        else:
            self._show_menu()

    def _show_menu(self):
        dialog = self.dialog
        if not (dialog and is_valid_qobject(dialog)):
            dialog = PopupWidget(
                parent=self,
                blur=self.config.popup.blur,
                round_corners=self.config.popup.round_corners,
                round_corners_type=self.config.popup.round_corners_type,
                border_color=self.config.popup.border_color,
                persistent=True,
            )
            self.dialog = dialog
            dialog.setProperty("class", "control-center-menu")
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            for section_name in self.config.sections_order:
                section_config, builder = self._sections[section_name]
                if section_config.show:
                    widget = builder(dialog)
                    self._section_widgets[section_name] = widget
                    layout.addWidget(widget)

        dialog.setPosition(
            alignment=self.config.popup.alignment,
            direction=self.config.popup.direction,
            offset_left=self.config.popup.offset_left,
            offset_top=self.config.popup.offset_top,
        )
        dialog.show()
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

    def _build_system_controls_section(self, parent: PopupWidget) -> SystemControlsSectionWidget:
        return SystemControlsSectionWidget(
            parent,
            self.config.sections.system_controls,
            self._refresh_popup_state,
            self.config.tooltip,
        )

    def _build_quick_actions_section(self, parent: PopupWidget) -> QuickActionsSectionWidget:
        return QuickActionsSectionWidget(
            parent,
            self.config.sections.quick_actions,
            self._refresh_popup_state,
            self._output_service,
            self._input_service,
            self.config.tooltip,
        )

    def _build_sliders_section(self, parent: PopupWidget) -> SlidersSectionWidget:
        return SlidersSectionWidget(
            parent,
            self.config.sections.sliders,
            self._refresh_popup_state,
            self._output_service,
            self._input_service,
            self._brightness_service,
            self._hmonitor,
            self.config.tooltip,
        )

    def _build_power_section(self, parent: PopupWidget) -> PowerSectionWidget:
        return PowerSectionWidget(
            parent,
            self.config.sections.power,
        )

    def _build_media_section(self, parent: PopupWidget) -> MediaSectionWidget:
        return MediaSectionWidget(
            parent,
            self.config.sections.media,
        )

    def on_output_volume_changed(self) -> None:
        self._refresh_audio_state()

    def on_input_volume_changed(self) -> None:
        self._refresh_audio_state()

    def _refresh_audio_state(self) -> None:
        if not self.dialog or not is_valid_qobject(self.dialog) or not self.dialog.isVisible():
            return

        for section_name in ("sliders", "quick_actions"):
            widget = self._section_widgets.get(section_name)
            if widget is not None and is_valid_qobject(widget):
                try:
                    widget.refresh_state()
                except Exception:
                    pass

    def on_output_device_changed(self) -> None:
        self._reinitialize_audio()

    def on_input_device_changed(self) -> None:
        self._reinitialize_microphone()

    def _reinitialize_audio(self):
        self._refresh_popup_state()

    def _reinitialize_microphone(self):
        self._refresh_popup_state()
