import time

from PyQt6.QtCore import QObject, QTimer, pyqtProperty, pyqtSignal, pyqtSlot

from core.services.media.art import art_url
from core.services.media.media import MediaInfo, MediaService, MediaState
from core.utils.qml import qml_property
from core.utils.win32.aumid import activate_app_by_aumid

MIN_POSITION_INTERVAL_MS = 50


class NowPlaying(QObject):
    """The player Windows shows as current, or the one picked with switchSession()."""

    playerChanged = pyqtSignal()
    positionChanged = pyqtSignal()
    positionIntervalChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._service = MediaService.instance()
        self._player: MediaInfo | None = None
        self._count = 0
        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self.positionChanged)
        self._service.changed.connect(self._on_changed)
        self._on_changed(self._service.state)

    @pyqtSlot(object)
    def _on_changed(self, state: MediaState) -> None:
        player = state.player
        if player == self._player and len(state.players) == self._count:
            return
        self._player = player
        self._count = len(state.players)
        self.playerChanged.emit()
        self.positionChanged.emit()
        if player is not None and player.playing and player.position_time > 0:
            self._ticker.start()
        else:
            self._ticker.stop()

    def _get_position_interval(self) -> int:
        return self._ticker.interval()

    def _set_position_interval(self, value: int) -> None:
        value = max(value, MIN_POSITION_INTERVAL_MS)
        if value != self._ticker.interval():
            self._ticker.setInterval(value)
            self.positionIntervalChanged.emit()

    # How often position updates while playing, in ms
    positionInterval = pyqtProperty(int, _get_position_interval, _set_position_interval, notify=positionIntervalChanged)

    @qml_property(bool, notify=playerChanged)
    def available(self) -> bool:
        return self._player is not None

    @qml_property(int, notify=playerChanged)
    def sessionCount(self) -> int:
        return self._count

    @qml_property(str, notify=playerChanged)
    def appId(self) -> str:
        return self._player.app_id if self._player else ""

    @qml_property(str, notify=playerChanged)
    def appName(self) -> str:
        return self._player.app_name if self._player else ""

    @qml_property(str, notify=playerChanged)
    def process(self) -> str:
        return self._player.process if self._player else ""

    @qml_property(str, notify=playerChanged)
    def title(self) -> str:
        return self._player.title if self._player else ""

    @qml_property(str, notify=playerChanged)
    def artist(self) -> str:
        return self._player.artist if self._player else ""

    @qml_property(str, notify=playerChanged)
    def albumTitle(self) -> str:
        return self._player.album if self._player else ""

    @qml_property(str, notify=playerChanged)
    def thumbnail(self) -> str:
        return art_url(self._player.art_revision) if self._player else ""

    @qml_property(bool, notify=playerChanged)
    def playing(self) -> bool:
        return self._player.playing if self._player else False

    # Seconds
    @qml_property(float, notify=positionChanged)
    def position(self) -> float:
        return self._player.position_at(time.time()) if self._player else 0.0

    @qml_property(float, notify=playerChanged)
    def duration(self) -> float:
        return self._player.duration if self._player else 0.0

    @qml_property(bool, notify=playerChanged)
    def canPlayPause(self) -> bool:
        return self._player.can_play_pause if self._player else False

    @qml_property(bool, notify=playerChanged)
    def canPrevious(self) -> bool:
        return self._player.can_previous if self._player else False

    @qml_property(bool, notify=playerChanged)
    def canNext(self) -> bool:
        return self._player.can_next if self._player else False

    @qml_property(bool, notify=playerChanged)
    def canSeek(self) -> bool:
        return bool(self._player and self._player.can_seek and self._player.duration > 0)

    @qml_property(bool, notify=playerChanged)
    def canShuffle(self) -> bool:
        return self._player.can_shuffle if self._player else False

    @qml_property(bool, notify=playerChanged)
    def canRepeat(self) -> bool:
        return self._player.can_repeat if self._player else False

    @qml_property(bool, notify=playerChanged)
    def shuffle(self) -> bool:
        return self._player.shuffle if self._player else False

    # "none", "track" or "list"
    @qml_property(str, notify=playerChanged)
    def repeat(self) -> str:
        return self._player.repeat if self._player else "none"

    @pyqtSlot()
    def playPause(self) -> None:
        if self._player:
            self._service.play_pause(self._player.app_id)

    @pyqtSlot()
    def previous(self) -> None:
        if self._player:
            self._service.previous(self._player.app_id)

    @pyqtSlot()
    def next(self) -> None:
        if self._player:
            self._service.next(self._player.app_id)

    @pyqtSlot(float)
    def seek(self, seconds: float) -> None:
        if self._player:
            self._service.seek(self._player.app_id, seconds)

    @pyqtSlot()
    def toggleShuffle(self) -> None:
        if self._player:
            self._service.toggle_shuffle(self._player.app_id)

    @pyqtSlot()
    def cycleRepeat(self) -> None:
        if self._player:
            self._service.cycle_repeat(self._player.app_id)

    @pyqtSlot(int)
    def switchSession(self, direction: int) -> None:
        self._service.switch(direction)

    @pyqtSlot()
    def openApp(self) -> None:
        if self._player:
            activate_app_by_aumid(self._player.app_id, fallback_process_name=self._player.process or None)
