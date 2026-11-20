import logging
import re

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.validation.widgets.yasb.wireless_battery import WirelessBatteryConfig
from core.widgets.base import BaseWidget
from core.widgets.services.wireless_battery.wireless_battery_api import (
    WirelessBatteryWorker,
    WirelessDevice,
)


class WirelessBatteryWidget(BaseWidget):
    """Shows the battery level of wireless mice, keyboards, headsets and controllers, read from BatteryHub."""

    validation_schema = WirelessBatteryConfig

    _instances: list[WirelessBatteryWidget] = []
    _worker: WirelessBatteryWorker | None = None

    def __init__(self, config: WirelessBatteryConfig):
        super().__init__(class_name=f"wireless-battery-widget {config.class_name}")
        self.config = config
        self._last_devices: list[WirelessDevice] | None = None
        self._device_frames: list[QFrame] = []

        self._init_container()
        self.register_callback("refresh", self._refresh)
        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        if self not in WirelessBatteryWidget._instances:
            WirelessBatteryWidget._instances.append(self)

        if WirelessBatteryWidget._worker is None:
            worker = WirelessBatteryWorker.get_instance(self.config.executable, self.config.update_interval)
            worker.data_ready.connect(WirelessBatteryWidget._on_data_ready)
            worker.error.connect(WirelessBatteryWidget._on_error)
            worker.start()
            WirelessBatteryWidget._worker = worker

        self.setVisible(not self.config.hide_when_empty)

    @classmethod
    def _on_data_ready(cls, devices: list[WirelessDevice]):
        for inst in cls._instances[:]:
            try:
                inst._last_devices = devices
                inst._render(devices)
            except RuntimeError:  # underlying Qt object already deleted
                cls._instances.remove(inst)

    @classmethod
    def _on_error(cls, message: str):
        logging.warning("Wireless battery widget: %s", message)

    def _refresh(self):
        if WirelessBatteryWidget._worker is not None:
            WirelessBatteryWidget._worker.refresh()

    # -- filtering / formatting -------------------------------------------------

    def _select(self, devices: list[WirelessDevice]) -> list[WirelessDevice]:
        names = [n.lower() for n in self.config.devices]
        kinds = {k.lower() for k in self.config.kinds}
        selected: list[WirelessDevice] = []
        for dev in devices:
            if not dev.connected and not self.config.show_disconnected:
                continue
            if kinds and dev.kind not in kinds:
                continue
            if names and not any(n in dev.name.lower() or n == dev.key.lower() for n in names):
                continue
            selected.append(dev)

        sort_by = self.config.sort_by
        if sort_by == "name":
            selected.sort(key=lambda d: d.name.lower())
        elif sort_by == "percent":
            selected.sort(key=lambda d: d.percent if d.percent is not None else 101)
        else:
            selected.sort(key=lambda d: (d.kind, d.name.lower()))
        return selected

    def _icon_for(self, dev: WirelessDevice) -> str:
        icons = self.config.icons
        if not dev.connected:
            return icons.disconnected
        if dev.charging:
            return icons.charging
        by_kind = {
            "mouse": icons.mouse,
            "keyboard": icons.keyboard,
            "headset": icons.headset,
            "gamepad": icons.gamepad,
            "phone": icons.phone,
            "microphone": icons.microphone,
        }
        return by_kind.get(dev.kind, icons.default)

    def _status_for(self, dev: WirelessDevice) -> str:
        if not dev.connected:
            return "disconnected"
        classes: list[str] = []
        if dev.charging:
            classes.append("charging")
        if dev.asleep:
            classes.append("asleep")
        if dev.percent is None:
            classes.append("unknown")
        elif dev.percent <= self.config.thresholds.critical:
            classes.append("critical")
        elif dev.percent <= self.config.thresholds.low:
            classes.append("low")
        else:
            classes.append("normal")
        return " ".join(classes)

    def _template_for(self, dev: WirelessDevice) -> str:
        if not dev.connected:
            return self.config.label_disconnected
        if dev.percent is None:
            return self.config.label_unknown
        if dev.charging and self.config.label_charging:
            return self.config.label_charging
        return self.config.label

    def _format(self, template: str, dev: WirelessDevice) -> str:
        try:
            return template.format(
                icon=self._icon_for(dev),
                percent=dev.percent if dev.percent is not None else "--",
                name=dev.name,
                kind=dev.kind,
                via=dev.via,
                level=dev.level,
                detail=dev.detail,
                millivolts=dev.millivolts if dev.millivolts is not None else "--",
                charging=dev.charging,
                asleep=dev.asleep,
                key=dev.key,
            )
        except KeyError, IndexError, ValueError:
            logging.exception("Invalid wireless battery label: %s", template)
            return template

    # -- rendering --------------------------------------------------------------

    def _clear(self):
        for frame in self._device_frames:
            self._widget_container_layout.removeWidget(frame)
            frame.deleteLater()
        self._device_frames = []

    def _render(self, devices: list[WirelessDevice]):
        selected = self._select(devices)
        self._clear()

        for dev in selected:
            frame = QFrame()
            frame.setProperty("class", f"device {dev.kind} {self._status_for(dev)}")
            layout = QHBoxLayout(frame)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            text = self._format(self._template_for(dev), dev)
            for part in re.split(r"(<span.*?>.*?</span>)", text):
                part = part.strip()
                if not part:
                    continue
                if "<span" in part and "</span>" in part:
                    class_match = re.search(r'class=(["\'])([^"\']+?)\1', part)
                    label = QLabel(re.sub(r"<span.*?>|</span>", "", part).strip())
                    label.setProperty("class", class_match.group(2) if class_match else "icon")
                else:
                    label = QLabel(part)
                    label.setProperty("class", "label")
                layout.addWidget(label)

            if self.config.tooltip:
                set_tooltip(frame, self._tooltip_text(dev))

            self._widget_container_layout.addWidget(frame)
            self._device_frames.append(frame)
            refresh_widget_style(frame)

        self.setVisible(bool(selected) or not self.config.hide_when_empty)

    @staticmethod
    def _tooltip_text(dev: WirelessDevice) -> str:
        lines = [dev.name or dev.key]
        if dev.via:
            lines.append(dev.via)
        if not dev.connected:
            lines.append("Disconnected")
        else:
            level = f"{dev.percent}%" if dev.percent is not None else (dev.level or "Unknown")
            lines.append(level + (" (charging)" if dev.charging else "") + (" (asleep)" if dev.asleep else ""))
        if dev.millivolts is not None:
            lines.append(f"{dev.millivolts} mV")
        return "\n".join(lines)
