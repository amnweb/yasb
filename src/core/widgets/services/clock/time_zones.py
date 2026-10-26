import logging

from PyQt6.QtCore import QByteArray, QDateTime, QLocale, QObject, QTimeZone, pyqtSlot


class TimeZones(QObject):
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._reported: set[str] = set()

    def _zone(self, name: str) -> QTimeZone | None:
        if name in ("", "local"):
            return None
        zone = QTimeZone(QByteArray(name.encode()))
        if zone.isValid():
            return zone
        if name not in self._reported:
            self._reported.add(name)
            logging.warning("Unknown time zone '%s', showing local time instead", name)
        return None

    @pyqtSlot(str, str, str, result="QString")
    def format(self, zone: str, pattern: str, locale: str) -> str:
        now = QDateTime.currentDateTime()
        if (time_zone := self._zone(zone)) is not None:
            now = now.toTimeZone(time_zone)
        return (QLocale(locale) if locale else QLocale()).toString(now, pattern)
