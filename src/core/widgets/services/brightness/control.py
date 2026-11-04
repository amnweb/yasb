from datetime import datetime, time
from typing import Any, override

from PyQt6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QWindow

from core.utils.qml import qml_property
from core.utils.win32.bindings.user32 import MonitorFromWindow
from core.widgets.services.brightness.service import BrightnessService

ROLES = ["monitor", "name", "subtitle", "brightness", "contrast"]


def is_night(now: time, start: time, end: time) -> bool:
    """Whether now falls between start and end, which may cross midnight."""
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


class DisplayList(QAbstractListModel):
    """Display rows keyed by monitor. Values change in place, so a slider being dragged is never rebuilt."""

    countChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    @override
    def roleNames(self) -> dict[int, QByteArray]:
        return {Qt.ItemDataRole.UserRole + i: QByteArray(name.encode()) for i, name in enumerate(ROLES)}

    @override
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    @override
    def data(self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not 0 <= index.row() < len(self._rows) or not 0 <= role - Qt.ItemDataRole.UserRole < len(ROLES):
            return None
        return self._rows[index.row()][ROLES[role - Qt.ItemDataRole.UserRole]]

    @qml_property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._rows)

    @property
    def rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def update(self, rows: list[dict[str, Any]]) -> None:
        if [row["monitor"] for row in rows] != [row["monitor"] for row in self._rows]:
            self.beginResetModel()
            self._rows = [dict(row) for row in rows]
            self.endResetModel()
            self.countChanged.emit()
            return
        for index, row in enumerate(rows):
            if self._rows[index] != row:
                self._rows[index] = dict(row)
                self.dataChanged.emit(self.index(index), self.index(index))


class DisplayBrightness(QObject):
    """Brightness of the display a window is on, and brightness and contrast of every display YASB can control."""

    changed = pyqtSignal()
    settingsChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window: QWindow | None = None
        self._hmonitor: int | None = None
        self._poll_interval = 60
        self._service: BrightnessService | None = None
        self._displays = DisplayList(self)
        # Start after QML applies the poll interval
        self._start_timer = QTimer(self)
        self._start_timer.setSingleShot(True)
        self._start_timer.setInterval(0)
        self._start_timer.timeout.connect(self._start)
        self._start_timer.start()

    def _start(self) -> None:
        self._service = BrightnessService.instance(self._poll_interval)
        self._service.brightness_changed.connect(self._on_changed)
        self._service.contrast_changed.connect(self._on_changed)
        self._update()
        self.changed.emit()

    def _get_window(self) -> QWindow | None:
        return self._window

    def _set_window(self, window: QWindow | None) -> None:
        if window is self._window:
            return
        if self._window is not None:
            self._window.screenChanged.disconnect(self._find_display)
        self._window = window
        if window is not None:
            window.screenChanged.connect(self._find_display)
        self.settingsChanged.emit()
        self._find_display()

    # The window whose display the brightness belongs to, usually the bar's
    window = pyqtProperty(QWindow, _get_window, _set_window, notify=settingsChanged)

    def _get_poll_interval(self) -> int:
        return self._poll_interval

    def _set_poll_interval(self, value: int) -> None:
        if value != self._poll_interval:
            self._poll_interval = value
            self.settingsChanged.emit()

    # Seconds between reads of external monitors, 0 for none. The first widget's value is used
    pollInterval = pyqtProperty(int, _get_poll_interval, _set_poll_interval, notify=settingsChanged)

    # 0 to 100, -1 while unknown or where the display can't be controlled
    @qml_property(int, notify=changed)
    def brightness(self) -> int:
        value = self._service.get_brightness(self._hmonitor) if self._service and self._hmonitor else None
        return -1 if value is None else value

    @qml_property(bool, notify=changed)
    def available(self) -> bool:
        return self.brightness >= 0

    # [{monitor, name, subtitle, brightness, contrast}], contrast -1 where the display has none
    @qml_property(QObject, constant=True)
    def displays(self) -> DisplayList:
        return self._displays

    def _find_display(self, *_: Any) -> None:
        hmonitor = MonitorFromWindow(int(self._window.winId())) if self._window is not None else None
        if hmonitor != self._hmonitor:
            self._hmonitor = hmonitor or None
            self.changed.emit()

    def _on_changed(self, hmonitor: int, _value: Any) -> None:
        self._update()
        if hmonitor == self._hmonitor:
            self.changed.emit()

    def _update(self) -> None:
        service = self._service
        if service is None:
            return
        rows: list[dict[str, Any]] = []
        for index, (hmonitor, name) in enumerate(service.get_monitors()):
            brightness = service.get_brightness(hmonitor)
            contrast = service.get_contrast(hmonitor) if service.supports_contrast(hmonitor) else None
            rows.append(
                {
                    "monitor": hmonitor,
                    "name": name,
                    "subtitle": service.get_monitor_subtitle(hmonitor, index),
                    "brightness": -1 if brightness is None else brightness,
                    "contrast": -1 if contrast is None else contrast,
                }
            )
        self._displays.update(rows)

    @pyqtSlot(int)
    def setBrightness(self, value: int) -> None:
        if self._service is not None and self._hmonitor and self.available:
            self._service.set_brightness(self._hmonitor, value)

    @pyqtSlot(int, int)
    def setDisplayBrightness(self, display: int, value: int) -> None:
        if self._service is not None:
            self._service.set_brightness(display, value)

    @pyqtSlot(int, int)
    def setDisplayContrast(self, display: int, value: int) -> None:
        if self._service is not None:
            self._service.set_contrast(display, value)
            self._update()

    # Reads external monitors again, which may have changed from their own buttons
    @pyqtSlot()
    def refresh(self) -> None:
        if self._service is not None:
            self._service.refresh_now()

    # Times as hh:mm
    @pyqtSlot(str, str, result="bool")
    def isNight(self, start: str, end: str) -> bool:
        try:
            return is_night(datetime.now().time(), time.fromisoformat(start), time.fromisoformat(end))
        except ValueError:
            return False
