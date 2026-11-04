from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from core.events.service import EventService
from core.utils.qml import qml_property
from core.widgets.services.dnd.dnd_api import DndService

# What each mode turns to on a cycle
NEXT_MODE = {"disabled": "priority", "priority": "alarms", "alarms": "disabled"}


class DoNotDisturb(QObject):
    """Windows' do not disturb: "disabled", "priority" or "alarms", and "unknown" where Windows has none."""

    statusChanged = pyqtSignal()
    # From EventService, which Windows' callback emits on its own thread
    _status_event = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._status = "unknown"
        self._status_event.connect(self._on_status)
        events = EventService()
        signal = self._status_event
        events.register_event("dnd_status_changed", signal)
        self.destroyed.connect(lambda *_: events.unregister_event("dnd_status_changed", signal))
        DndService.initialize_wnf_listener()
        # Reading do not disturb asks another process, so it waits until the bar is up
        self._read_timer = QTimer(self)
        self._read_timer.setSingleShot(True)
        self._read_timer.setInterval(0)
        self._read_timer.timeout.connect(lambda: self._on_status(DndService.get_status()))
        self._read_timer.start()

    @qml_property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @qml_property(bool, notify=statusChanged)
    def available(self) -> bool:
        return self._status != "unknown"

    @qml_property(bool, notify=statusChanged)
    def active(self) -> bool:
        return self._status in ("priority", "alarms")

    def _on_status(self, status: str) -> None:
        if status != self._status:
            self._status = status
            self.statusChanged.emit()

    @pyqtSlot(str)
    def setStatus(self, mode: str) -> None:
        if not self.available or mode not in DndService.MODES:
            return
        DndService.set_status(mode)
        self._on_status(mode)

    # Off turns to mode, priority or alarms; on turns off
    @pyqtSlot(str)
    def toggle(self, mode: str) -> None:
        self.setStatus(mode if self._status == "disabled" else "disabled")

    @pyqtSlot()
    def cycle(self) -> None:
        if self.available:
            self.setStatus(NEXT_MODE[self._status])
