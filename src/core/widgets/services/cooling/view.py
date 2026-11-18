from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from core.utils.tooltip import set_tooltip
from core.widgets.services.cooling.libre import FanReading


def rpm_text(value: float | None) -> str:
    return f"{value:.0f} RPM" if value is not None else "\u2014"


class CoolingSection(QFrame):
    """Use the same two-column stat cards as the surrounding native popup."""

    def __init__(self, sensor_map: dict[str, str] | None = None):
        super().__init__()
        self.setProperty("class", "cooling-section")
        self.sensor_map = sensor_map or {}
        self.values: dict[str, QLabel] = {}
        self._signature: tuple[tuple[str, str], ...] = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        title = QLabel("Cooling")
        title.setProperty("class", "cooling-title")
        layout.addWidget(title)
        cards = QFrame()
        cards.setProperty("class", "stats")
        self.grid = QGridLayout(cards)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(0)
        layout.addWidget(cards)

    def update_readings(self, readings: tuple[FanReading, ...]) -> None:
        by_id = {item.sensor_id: item for item in readings}
        if self.sensor_map:
            items = [
                (label, label, by_id[identifier].rpm if identifier in by_id else None)
                for label, identifier in self.sensor_map.items()
            ]
        else:
            items = [(item.sensor_id, item.name, item.rpm) for item in readings]
        if not items:
            items = [("unavailable", "Fan speed", None)]
        signature = tuple((key, name) for key, name, _ in items)
        if signature != self._signature:
            self._signature = signature
            while self.grid.count():
                item = self.grid.takeAt(0)
                if item is not None and (widget := item.widget()) is not None:
                    widget.hide()
                    widget.deleteLater()
            self.values = {}
            for index, (key, name, _) in enumerate(items):
                card = QFrame()
                card.setProperty("class", "stat-item")
                column = QVBoxLayout(card)
                column.setContentsMargins(0, 0, 0, 0)
                column.setSpacing(0)
                caption = QLabel(name)
                caption.setTextFormat(Qt.TextFormat.PlainText)
                caption.setProperty("class", "stat-label")
                value = QLabel("\u2014")
                value.setProperty("class", "stat-value")
                alignment = Qt.AlignmentFlag.AlignRight if index % 2 else Qt.AlignmentFlag.AlignLeft
                caption.setAlignment(alignment)
                value.setAlignment(alignment)
                column.addWidget(caption)
                column.addWidget(value)
                self.grid.addWidget(card, index // 2, index % 2)
                self.values[key] = value
        for key, _, rpm in items:
            self.values[key].setText(rpm_text(rpm))
            identifier = self.sensor_map.get(key, key)
            if identifier in by_id:
                set_tooltip(self.values[key], f"{by_id[identifier].hardware_name}\n{identifier}")
