import logging

from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.bar_helper import GlobalState
from core.utils.qobject import is_valid_qobject
from core.utils.tooltip import set_tooltip
from core.utils.win32.bindings import user32
from core.utils.win32.utils import apply_qmenu_style
from core.widgets.services.brightness.service import BrightnessService


class SlidersSectionWidget(QFrame):
    """Brightness, volume, and microphone sliders with optional source selectors."""

    def __init__(
        self,
        parent: QWidget,
        config: object,
        refresh_popup: object,
        audio_services: dict[str, object],
        brightness_service: BrightnessService | None,
        hmonitor: int | None,
        tooltip: bool = False,
    ):
        super().__init__(parent)
        self.config = config
        self.refresh_popup = refresh_popup
        self._audio_services = audio_services
        self._brightness_service = brightness_service
        self._hmonitor = hmonitor
        self._tooltip = tooltip
        self.setProperty("class", "section sliders")

        self._volume_slider: QSlider | None = None
        self._volume_value_label: QLabel | None = None
        self._volume_source_btn: QPushButton | None = None
        self._volume_source_menu: QMenu | None = None
        self._microphone_slider: QSlider | None = None
        self._microphone_value_label: QLabel | None = None
        self._microphone_source_btn: QPushButton | None = None
        self._microphone_source_menu: QMenu | None = None
        self._brightness_slider: QSlider | None = None
        self._brightness_value_label: QLabel | None = None
        self._brightness_source_btn: QPushButton | None = None
        self._brightness_source_menu: QMenu | None = None
        self._selected_brightness_hmonitor: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if config.volume.show_slider:
            layout.addWidget(
                self._create_slider_row(
                    "volume",
                    config.volume,
                    self._on_volume_slider_changed,
                )
            )
        if config.microphone.show_slider:
            layout.addWidget(
                self._create_slider_row(
                    "microphone",
                    config.microphone,
                    self._on_microphone_slider_changed,
                )
            )
        if config.brightness.show_slider:
            brightness_row = self._create_slider_row(
                "brightness",
                config.brightness,
                self._on_brightness_slider_changed,
            )
            if brightness_row is not None:
                layout.addWidget(brightness_row)

    def _get_brightness_target(self) -> int | None:
        if self._selected_brightness_hmonitor is not None:
            return self._selected_brightness_hmonitor
        if self._hmonitor:
            return self._hmonitor
        if self._brightness_service:
            monitors = self._brightness_service.get_monitors()
            if monitors:
                return monitors[0][0]
        return None

    def _get_brightness_value(self) -> int | None:
        if not self._brightness_service:
            return None
        target = self._get_brightness_target()
        if target is None:
            return None
        return self._brightness_service.get_brightness(target)

    def _set_brightness_value(self, value: int):
        if not self._brightness_service:
            return
        target = self._get_brightness_target()
        if target is None:
            return
        self._brightness_service.set_brightness(target, value)

    def _get_volume_interface(self):
        service = self._audio_services.get("output")
        return service.get_volume_interface() if service else None

    def _get_microphone_interface(self):
        service = self._audio_services.get("input")
        return service.get_microphone_interface() if service else None

    def _create_slider_row(self, key: str, slider_config, callback) -> QWidget | None:
        row = QFrame(self)
        row.setProperty("class", f"slider {key}")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        icon_label = QLabel(slider_config.icon, row)
        icon_label.setProperty("class", "icon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(icon_label)

        slider = QSlider(Qt.Orientation.Horizontal, row)
        slider.setProperty("class", "slider-control")
        slider.setRange(0, 100)
        slider.setMouseTracking(True)
        slider.installEventFilter(self)
        initial_value, initial_text = self._get_slider_initial_state(key)
        slider.setValue(initial_value)
        slider.valueChanged.connect(callback)
        if key == "volume":
            slider.sliderReleased.connect(self._on_volume_slider_released)
        layout.addWidget(slider, 1)

        value_label = QLabel(initial_text, row)
        value_label.setProperty("class", "value")
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(value_label)

        if slider_config.show_source_selector:
            source_btn = QPushButton(slider_config.source_selector_icon, row)
            source_btn.setProperty("class", "source-selector")
            source_btn.setFlat(True)
            if key == "volume":
                source_btn.clicked.connect(self._show_volume_source_menu)
                if self._tooltip:
                    set_tooltip(source_btn, "Select output device", position="top")
                self._volume_source_btn = source_btn
            elif key == "microphone":
                source_btn.clicked.connect(self._show_microphone_source_menu)
                if self._tooltip:
                    set_tooltip(source_btn, "Select input device", position="top")
                self._microphone_source_btn = source_btn
            elif key == "brightness":
                source_btn.clicked.connect(self._show_brightness_source_menu)
                if self._tooltip:
                    set_tooltip(source_btn, "Select monitor", position="top")
                self._brightness_source_btn = source_btn
            layout.addWidget(source_btn)

        if key == "volume":
            self._volume_slider = slider
            self._volume_value_label = value_label
        elif key == "microphone":
            self._microphone_slider = slider
            self._microphone_value_label = value_label
        elif key == "brightness":
            self._brightness_slider = slider
            self._brightness_value_label = value_label
        return row

    def _get_slider_initial_state(self, key: str) -> tuple[int, str]:
        if key == "brightness":
            brightness = self._get_brightness_value()
            return (brightness if brightness is not None else 0, f"{brightness if brightness is not None else 0}%")
        if key == "volume":
            interface = self._get_volume_interface()
            if interface is None:
                return (0, "0%")
            try:
                value = round(interface.GetMasterVolumeLevelScalar() * 100)
                return (value, f"{value}%")
            except Exception:
                return (0, "0%")
        if key == "microphone":
            interface = self._get_microphone_interface()
            if interface is None:
                return (0, "0%")
            try:
                value = round(interface.GetMasterVolumeLevelScalar() * 100)
                return (value, f"{value}%")
            except Exception:
                return (0, "0%")
        return (0, "0%")

    def _on_brightness_slider_changed(self, value: int):
        self._set_brightness_value(value)
        if self._brightness_value_label is not None:
            self._brightness_value_label.setText(f"{value}%")

    def _on_volume_slider_released(self):
        try:
            user32.MessageBeep(0)
        except Exception as e:
            logging.debug("Failed to play volume sound: %s", e)

    def _on_volume_slider_changed(self, value: int):
        interface = self._get_volume_interface()
        if interface is None:
            return
        interface.SetMasterVolumeLevelScalar(value / 100, None)
        if value > 0 and interface.GetMute():
            interface.SetMute(False, None)
            self.refresh_popup()
            return
        if self._volume_value_label is not None:
            self._volume_value_label.setText(f"{value}%")

    def _on_microphone_slider_changed(self, value: int):
        interface = self._get_microphone_interface()
        if interface is None:
            return
        interface.SetMasterVolumeLevelScalar(value / 100, None)
        if value > 0 and interface.GetMute():
            interface.SetMute(False, None)
            self.refresh_popup()
            return
        if self._microphone_value_label is not None:
            self._microphone_value_label.setText(f"{value}%")

    def _show_volume_source_menu(self):
        if (
            self._volume_source_menu
            and is_valid_qobject(self._volume_source_menu)
            and self._volume_source_menu.isVisible()
        ):
            self._volume_source_menu.close()
            return

        service = self._audio_services.get("output")
        if not service:
            return

        devices = service.get_all_devices()
        if not devices:
            return

        menu = self._create_context_menu()
        current_default = service.get_default_device_id()

        for device_id, device_name in devices:
            action = menu.addAction(device_name)
            action.setCheckable(True)
            action.setChecked(device_id == current_default)
            action.triggered.connect(lambda checked=False, did=device_id: self._set_volume_source(did))

        self._volume_source_menu = menu
        btn = self._volume_source_btn
        if btn:
            pos = btn.mapToGlobal(QPoint(btn.width() - menu.sizeHint().width(), btn.height()))
            btn.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
            btn.update()
            menu.popup(pos)

    def _set_volume_source(self, device_id: str):
        service = self._audio_services.get("output")
        if not service:
            return
        if service.set_default_device(device_id):
            self.refresh_popup()

    def _show_microphone_source_menu(self):
        if (
            self._microphone_source_menu
            and is_valid_qobject(self._microphone_source_menu)
            and self._microphone_source_menu.isVisible()
        ):
            self._microphone_source_menu.close()
            return

        service = self._audio_services.get("input")
        if not service:
            return

        devices = service.get_all_devices()
        if not devices:
            return

        menu = self._create_context_menu()
        current_default = service.get_default_device_id()

        for device_id, device_name in devices:
            action = menu.addAction(device_name)
            action.setCheckable(True)
            action.setChecked(device_id == current_default)
            action.triggered.connect(lambda checked=False, did=device_id: self._set_microphone_source(did))

        self._microphone_source_menu = menu
        btn = self._microphone_source_btn
        if btn:
            pos = btn.mapToGlobal(QPoint(btn.width() - menu.sizeHint().width(), btn.height()))
            btn.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
            btn.update()
            menu.popup(pos)

    def _set_microphone_source(self, device_id: str):
        service = self._audio_services.get("input")
        if not service:
            return
        if service.set_default_device(device_id):
            self.refresh_popup()

    def _show_brightness_source_menu(self):
        if (
            self._brightness_source_menu
            and is_valid_qobject(self._brightness_source_menu)
            and self._brightness_source_menu.isVisible()
        ):
            self._brightness_source_menu.close()
            return

        if not self._brightness_service:
            return

        monitors = self._brightness_service.get_monitors()
        if len(monitors) < 2:
            return

        menu = self._create_context_menu()
        current = self._get_brightness_target()

        for index, (hmonitor, name) in enumerate(monitors):
            label = self._brightness_service.get_monitor_subtitle(hmonitor, index)
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(hmonitor == current)
            action.triggered.connect(lambda checked=False, hmon=hmonitor: self._set_brightness_source(hmon))

        self._brightness_source_menu = menu
        btn = self._brightness_source_btn
        if btn:
            pos = btn.mapToGlobal(QPoint(btn.width() - menu.sizeHint().width(), btn.height()))
            btn.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
            btn.update()
            menu.popup(pos)

    def _set_brightness_source(self, hmonitor: int):
        if self._selected_brightness_hmonitor == hmonitor:
            return
        self._selected_brightness_hmonitor = hmonitor
        self.refresh_popup()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and obj in (
            self._volume_slider,
            self._microphone_slider,
            self._brightness_slider,
        ):
            slider: QSlider = obj
            step = 1 if event.angleDelta().y() > 0 else -1
            slider.setValue(slider.value() + step)
            return True
        return super().eventFilter(obj, event)

    def refresh_state(self) -> None:
        if self._volume_slider is not None:
            interface = self._get_volume_interface()
            disabled = interface is None
            row = self._volume_slider.parent()
            row.setProperty("class", "slider volume disabled" if disabled else "slider volume")
            self._volume_slider.setEnabled(not disabled)
            if not disabled:
                try:
                    val = round(interface.GetMasterVolumeLevelScalar() * 100)
                    self._volume_slider.blockSignals(True)
                    self._volume_slider.setValue(val)
                    self._volume_slider.blockSignals(False)
                    if self._volume_value_label is not None:
                        self._volume_value_label.setText(f"{val}%")
                except Exception:
                    pass

        if self._microphone_slider is not None:
            interface = self._get_microphone_interface()
            disabled = interface is None
            row = self._microphone_slider.parent()
            row.setProperty("class", "slider microphone disabled" if disabled else "slider microphone")
            self._microphone_slider.setEnabled(not disabled)
            if not disabled:
                try:
                    val = round(interface.GetMasterVolumeLevelScalar() * 100)
                    self._microphone_slider.blockSignals(True)
                    self._microphone_slider.setValue(val)
                    self._microphone_slider.blockSignals(False)
                    if self._microphone_value_label is not None:
                        self._microphone_value_label.setText(f"{val}%")
                except Exception:
                    pass

        if self._brightness_slider is not None:
            brightness = self._get_brightness_value()
            disabled = brightness is None
            row = self._brightness_slider.parent()
            row.setProperty("class", "slider brightness disabled" if disabled else "slider brightness")
            self._brightness_slider.setEnabled(not disabled)
            val = brightness if brightness is not None else 0
            self._brightness_slider.blockSignals(True)
            self._brightness_slider.setValue(val)
            self._brightness_slider.blockSignals(False)
            if self._brightness_value_label is not None:
                self._brightness_value_label.setText(f"{val}%")

    def update_brightness(self, hmonitor: int, brightness: int) -> None:
        if self._brightness_slider is None:
            return
        if self._get_brightness_target() != hmonitor:
            return
        row = self._brightness_slider.parent()
        row.setProperty("class", "slider brightness")
        self._brightness_slider.setEnabled(True)
        self._brightness_slider.blockSignals(True)
        self._brightness_slider.setValue(brightness)
        self._brightness_slider.blockSignals(False)
        if self._brightness_value_label is not None:
            self._brightness_value_label.setText(f"{brightness}%")

    def _create_context_menu(self) -> QMenu:
        menu = QMenu(self.window())
        apply_qmenu_style(menu)
        menu.setProperty("class", "context-menu dark" if GlobalState.is_dark() else "context-menu")
        return menu
