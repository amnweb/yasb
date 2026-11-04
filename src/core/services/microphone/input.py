import logging
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from core.services.microphone.service import AudioInputService
from core.utils.qml import qml_property


def _clamp(value: int) -> int:
    return max(0, min(value, 100))


class AudioInput(QObject):
    """The default microphone and its level, and the other microphones."""

    volumeChanged = pyqtSignal()
    deviceChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._service = AudioInputService()
        self._volume = 0
        self._muted = False
        self._read_volume()
        service = self._service
        service.register_widget(self)
        self.destroyed.connect(lambda *_: service.unregister_widget(self))

    def on_input_volume_changed(self) -> None:
        self._read_volume()
        self.volumeChanged.emit()

    def on_input_device_changed(self) -> None:
        self._read_volume()
        self.deviceChanged.emit()
        self.volumeChanged.emit()

    def _read_volume(self) -> None:
        volume = self._service.get_microphone_interface()
        try:
            self._volume = round(volume.GetMasterVolumeLevelScalar() * 100) if volume else 0
            self._muted = bool(volume.GetMute()) if volume else False
        except Exception as e:
            logging.debug("Could not read the microphone level: %s", e)

    @qml_property(bool, notify=deviceChanged)
    def available(self) -> bool:
        return self._service.get_microphone_interface() is not None

    @qml_property(str, notify=deviceChanged)
    def deviceName(self) -> str:
        microphone = self._service.get_microphone()
        return (microphone.FriendlyName or "") if microphone else ""

    # [{id, name, current}]
    @qml_property("QVariantList", notify=deviceChanged)
    def devices(self) -> list[dict[str, Any]]:
        current = self._service.get_default_device_id()
        return [
            {"id": device_id, "name": name or "", "current": device_id == current}
            for device_id, name in self._service.get_all_devices()
        ]

    # 0 to 100
    @qml_property(int, notify=volumeChanged)
    def volume(self) -> int:
        return self._volume

    @qml_property(bool, notify=volumeChanged)
    def muted(self) -> bool:
        return self._muted

    # The microphone mutes at 0 and unmutes above it
    @pyqtSlot(int)
    def setVolume(self, value: int) -> None:
        volume = self._service.get_microphone_interface()
        if volume is None:
            return
        try:
            volume.SetMasterVolumeLevelScalar(_clamp(value) / 100, None)
        except Exception as e:
            logging.error("Could not set the microphone level: %s", e)
            return
        self._volume = _clamp(value)
        if self._muted != (self._volume == 0):
            self.setMuted(self._volume == 0)
        self.volumeChanged.emit()

    @pyqtSlot(bool)
    def setMuted(self, muted: bool) -> None:
        volume = self._service.get_microphone_interface()
        if volume is None:
            return
        try:
            volume.SetMute(int(muted), None)
        except Exception as e:
            logging.error("Could not mute the microphone: %s", e)
            return
        self._muted = muted
        self.volumeChanged.emit()

    @pyqtSlot()
    def toggleMute(self) -> None:
        self.setMuted(not self._muted)

    @pyqtSlot(str)
    def setDevice(self, device_id: str) -> None:
        self._service.set_default_device(device_id)
