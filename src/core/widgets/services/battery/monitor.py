from datetime import timedelta
from typing import Any

import humanize
from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from core.widgets.services.battery.battery_api import POWER_TIME_UNKNOWN, POWER_TIME_UNLIMITED, BatteryAPI, BatteryData

MIN_INTERVAL_MS = 1000
MAX_INTERVAL_MS = 60000


def time_left(seconds: int) -> tuple[str, str]:
    """The time left as H:MM:SS and in words, or "" when there is no estimate."""
    if seconds < 0:
        return "", ""
    delta = timedelta(seconds=seconds)
    return str(delta), humanize.naturaldelta(delta)


def battery_info(data: BatteryData) -> dict[str, Any]:
    clock, natural = time_left(data.time_remaining)
    return {
        "percent": data.percent,
        "charging": data.is_charging,
        "pluggedIn": data.power_plugged,
        "timeRemaining": data.time_remaining,
        "timeUnlimited": data.time_remaining == POWER_TIME_UNLIMITED,
        "timeUnknown": data.time_remaining == POWER_TIME_UNKNOWN,
        "timeText": clock,
        "timeNatural": natural,
        # The extended values are null when the battery does not report them
        "rate": data.rate,
        "voltage": data.voltage,
        "capacity": data.capacity,
        "fullCapacity": data.full_capacity,
        "designedCapacity": data.designed_capacity,
        "temperature": data.temperature,
        "cycleCount": data.cycle_count,
        "health": data.health_percent,
        "chemistry": data.chemistry,
    }


EMPTY = battery_info(BatteryData(0, False, False, POWER_TIME_UNKNOWN, *([None] * 9)))


class BatteryMonitor(QObject):
    dataChanged = pyqtSignal()
    updateIntervalChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._update_interval = 5000
        self._available = False
        self._data = EMPTY

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)

        # QML sets updateInterval after creating the object, so the first read waits until that is done
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(0)
        self._start_timer.timeout.connect(self._start)
        self._start_timer.start()

    @pyqtProperty(bool, notify=dataChanged)
    def available(self) -> bool:
        return self._available

    @pyqtProperty("QVariantMap", notify=dataChanged)
    def data(self) -> dict[str, Any]:
        return self._data

    def _get_update_interval(self) -> int:
        return self._update_interval

    def _set_update_interval(self, value: int) -> None:
        value = max(MIN_INTERVAL_MS, min(value, MAX_INTERVAL_MS))
        if value == self._update_interval:
            return
        self._update_interval = value
        self.updateIntervalChanged.emit()
        if self._timer.isActive():
            self._timer.start(value)

    updateInterval = pyqtProperty(int, _get_update_interval, _set_update_interval, notify=updateIntervalChanged)

    def _start(self) -> None:
        self.refresh()
        self._timer.start(self._update_interval)

    @pyqtSlot()
    def refresh(self) -> None:
        status = BatteryAPI.instance().get_status()
        available = status is not None
        data = battery_info(status) if status is not None else EMPTY
        if available == self._available and data == self._data:
            return
        self._available = available
        self._data = data
        self.dataChanged.emit()
