"""Native Libre temperature widget with a shared history and pinnable stat popup."""

from functools import partial

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from core.utils.stat_popup import PinnablePopup, StatRow, build_stat_popup
from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, refresh_widget_style
from core.validation.widgets.yasb.temperature import TemperatureConfig
from core.widgets.base import BaseWidget
from core.widgets.services.temperature.graph import TemperatureGraph
from core.widgets.services.temperature.libre import TemperatureReading, TemperatureSnapshot, TemperatureWorker


def temperature_text(value: float | None) -> str:
    return f"{value:.0f} °C" if value is not None else "\u2014"


def sensor_priority(sensor: TemperatureReading) -> tuple[int, str]:
    name = sensor.name.casefold()
    if "tctl/tdie" in name or name in ("cpu package", "gpu core"):
        return (0, name)
    if "package" in name or name in ("core average", "gpu memory"):
        return (1, name)
    return (2, name)


class TemperatureWidget(BaseWidget):
    validation_schema = TemperatureConfig

    def __init__(self, config: TemperatureConfig):
        super().__init__(class_name=f"temperature-widget {config.class_name}")
        self.config = config
        self._selected_hardware: str | None = None
        self._selected_sensors: dict[str, str] = {}
        self._show_alt_label = False
        self._component_buttons: dict[str, QPushButton] = {}
        self._sensor_buttons: dict[str, QPushButton] = {}
        self._component_signature: tuple[tuple[str, str], ...] = ()
        self._sensor_signature: tuple[tuple[str, str], ...] = ()
        self._init_container()
        self.build_widget_label(config.label, config.label_alt)
        self.register_callback("toggle_menu", self._show_popup)
        self.register_callback("toggle_label", self._toggle_label)
        self.callback_left = config.callbacks.on_left
        self.callback_right = config.callbacks.on_right
        self.callback_middle = config.callbacks.on_middle
        self._worker = TemperatureWorker.get_instance(
            config.libre_host, config.libre_port, config.update_interval, config.history_seconds
        )
        self._snapshot = self._worker.latest
        self._worker.data_ready.connect(self._receive)
        self._receive(self._snapshot)
        if not self._worker.isRunning():
            self._worker.start()

    def _toggle_label(self) -> None:
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)

    def _components(self) -> dict[str, tuple[TemperatureReading, ...]]:
        groups: dict[str, list[TemperatureReading]] = {}
        for sensor in self._snapshot.sensors:
            groups.setdefault(sensor.hardware_id, []).append(sensor)
        return {identifier: tuple(sorted(sensors, key=sensor_priority)) for identifier, sensors in groups.items()}

    def _component_labels(self, groups: dict[str, tuple[TemperatureReading, ...]]) -> dict[str, str]:
        labels: dict[str, str] = {}
        counts = {"cpu": 0, "gpu": 0}
        for identifier, sensors in groups.items():
            kind = sensors[0].kind
            number = counts[kind]
            counts[kind] += 1
            fallback = "CPU" if kind == "cpu" and number == 0 else f"{kind.upper()} {number}"
            labels[identifier] = self.config.hardware_labels.get(identifier, fallback)
        return labels

    def _selected_sensor(self) -> TemperatureReading | None:
        groups = self._components()
        if not groups:
            return None
        if self._selected_hardware not in groups:
            self._selected_hardware = next(
                (key for key, items in groups.items() if items[0].kind == "cpu"), next(iter(groups))
            )
        sensors = groups[self._selected_hardware]
        identifier = self._selected_sensors.get(self._selected_hardware)
        selected = next((item for item in sensors if item.sensor_id == identifier), sensors[0])
        self._selected_sensors[self._selected_hardware] = selected.sensor_id
        return selected

    def _receive(self, snapshot: TemperatureSnapshot) -> None:
        self._snapshot = snapshot
        self._selected_sensor()
        labels = self._component_labels(self._components())
        summary = [
            f"{labels[item.hardware_id]} — {item.name}: {temperature_text(item.value)}" for item in snapshot.sensors
        ]
        set_tooltip(self, snapshot.status or "\n".join(summary) or "Temperatures")
        self._refresh_popup()

    def _select_hardware(self, identifier: str) -> None:
        self._selected_hardware = identifier
        self._selected_sensor()
        self._refresh_popup()

    def _select_sensor(self, identifier: str) -> None:
        if self._selected_hardware is not None:
            self._selected_sensors[self._selected_hardware] = identifier
            self._refresh_popup()

    @staticmethod
    def _clear(layout: QHBoxLayout | QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is not None and (widget := item.widget()) is not None:
                widget.hide()
                widget.deleteLater()

    def _refresh_popup(self) -> None:
        popup = PopupWidget.open_popup_for(self)
        if isinstance(popup, PinnablePopup) and popup.isVisible():
            self._render_popup(popup)

    def _render_popup(self, popup: PinnablePopup) -> None:
        groups = self._components()
        labels = self._component_labels(groups)
        ordered = sorted(groups, key=lambda key: (groups[key][0].kind != "cpu", labels[key]))
        signature = tuple((key, labels[key]) for key in ordered)
        if signature != self._component_signature:
            self._component_signature = signature
            self._clear(self._components_layout)
            self._component_buttons = {}
            for identifier in ordered:
                button = QPushButton(labels[identifier])
                button.setCheckable(True)
                button.setProperty("class", "component-button")
                set_tooltip(button, groups[identifier][0].hardware_name)
                button.clicked.connect(partial(self._select_hardware, identifier))
                self._components_layout.addWidget(button)
                self._component_buttons[identifier] = button
        selected = self._selected_sensor()
        sensors = groups.get(self._selected_hardware or "", ())
        sensor_signature = tuple((sensor.sensor_id, sensor.name) for sensor in sensors)
        if sensor_signature != self._sensor_signature:
            self._sensor_signature = sensor_signature
            self._clear(self._sensors_layout)
            self._sensor_buttons = {}
            for index, sensor in enumerate(sensors):
                text = sensor.name.removeprefix("GPU ").replace("Core (Tctl/Tdie)", "Tctl/Tdie")
                button = QPushButton(text[:24])
                button.setCheckable(True)
                button.setProperty("class", "sensor-button")
                set_tooltip(button, sensor.name)
                button.clicked.connect(partial(self._select_sensor, sensor.sensor_id))
                self._sensors_layout.addWidget(button, index // 3, index % 3)
                self._sensor_buttons[sensor.sensor_id] = button
        for identifier, button in self._component_buttons.items():
            button.setChecked(identifier == self._selected_hardware)
        for identifier, button in self._sensor_buttons.items():
            button.setChecked(selected is not None and identifier == selected.sensor_id)
        self._component_frame.setVisible(bool(groups))
        self._sensor_frame.setVisible(bool(sensors))
        self._detail.setText(selected.hardware_name if selected is not None else "")
        self._status.setText(self._snapshot.status)
        self._status.setVisible(bool(self._snapshot.status))
        history = self._snapshot.histories.get(selected.sensor_id, ()) if selected is not None else ()
        thresholds = self.config.thresholds.get(selected.sensor_id) if selected is not None else None
        self._graph.set_readings(history, self._snapshot.timestamp, self.config.history_seconds, thresholds)
        values = [value for _, value in history if value is not None]
        current = selected.value if selected is not None else None
        stats = popup.stat_labels
        stats["current"].setText(temperature_text(current))
        stats["minimum"].setText(temperature_text(min(values) if values else None))
        stats["maximum"].setText(temperature_text(max(values) if values else None))
        stats["range"].setText(f"{self._graph.minimum:g}–{self._graph.maximum:g} °C")
        css_class = "stat-value primary"
        if thresholds is not None and current is not None:
            if current >= thresholds.critical:
                css_class += " critical"
            elif current >= thresholds.warning:
                css_class += " warning"
        if stats["current"].property("class") != css_class:
            stats["current"].setProperty("class", css_class)
            refresh_widget_style(stats["current"])
        self._graph_title.setText(selected.name if selected is not None else "Temperature")
        popup.adjustSize()

    def _show_popup(self) -> None:
        if not self.config.menu.enabled:
            return
        existing = PopupWidget.open_popup_for(self)
        if isinstance(existing, PinnablePopup) and existing.isVisible():
            existing.hide_animated()
            return
        rows: list[StatRow] = [
            ("Temperature", "current", "\u2014", "Minimum", "minimum", "\u2014"),
            ("Maximum", "maximum", "\u2014", "Graph range", "range", "0–100 °C"),
        ]
        popup = build_stat_popup(
            self,
            self.config.menu,
            "temperature-popup",
            "Temperatures",
            (),
            rows,
            graph_class="temperature-graph",
            primary_stats=("current",),
        )
        layout = popup.layout()
        assert isinstance(layout, QVBoxLayout)
        self._graph = TemperatureGraph(self.config.menu.show_graph_grid)
        self._graph.setParent(popup)
        self._graph.setVisible(self.config.menu.show_graph)
        original = popup.graph
        if original is not None:
            container = original.parentWidget()
            if container is not None and (graph_layout := container.layout()) is not None:
                graph_layout.replaceWidget(original, self._graph)
                original.hide()
                original.deleteLater()
            popup.graph = self._graph
        self._component_frame = QFrame()
        self._component_frame.setProperty("class", "component-selector")
        self._components_layout = QHBoxLayout(self._component_frame)
        self._components_layout.setContentsMargins(16, 0, 16, 6)
        self._components_layout.setSpacing(6)
        self._sensor_frame = QFrame()
        self._sensor_frame.setProperty("class", "sensor-selector")
        self._sensors_layout = QGridLayout(self._sensor_frame)
        self._sensors_layout.setContentsMargins(16, 0, 16, 6)
        self._sensors_layout.setSpacing(6)
        self._detail = QLabel()
        self._detail.setProperty("class", "hardware-name")
        self._detail.setTextFormat(Qt.TextFormat.PlainText)
        self._detail.setWordWrap(True)
        self._detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._detail.setMaximumHeight(36)
        self._status = QLabel()
        self._status.setProperty("class", "status")
        self._status.setWordWrap(True)
        self._graph_title = QLabel()
        self._graph_title.setTextFormat(Qt.TextFormat.PlainText)
        self._graph_title.setProperty("class", "graph-title")
        for index, widget in enumerate(
            (self._component_frame, self._sensor_frame, self._detail, self._status, self._graph_title), start=1
        ):
            layout.insertWidget(index, widget)
        self._graph_title.setVisible(self.config.menu.show_graph)
        self._component_signature = ()
        self._sensor_signature = ()
        self._render_popup(popup)
        popup.ensurePolished()
        screen = self.screen()
        width = (
            min(self.config.menu.width, screen.availableGeometry().width() - 24) if screen else self.config.menu.width
        )
        popup.setFixedWidth(width)
        popup.adjustSize()
        popup.setPosition(
            self.config.menu.alignment,
            self.config.menu.direction,
            self.config.menu.offset_left,
            self.config.menu.offset_top,
        )
        popup.show()
