import logging
from typing import Any

from pycaw.api.audioclient import ISimpleAudioVolume
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from core.services.volume.service import AudioOutputService, AudioSessionInfo
from core.utils.icons.image_provider import icon_url
from core.utils.icons.service import IconService
from core.utils.icons.sources import ProcessIcon
from core.utils.qml import qml_property
from core.utils.win32.aumid import get_aumid_for_process
from core.utils.win32.bindings.user32 import user32
from core.utils.win32.utils import get_app_name_from_pid


def _app_label(process_name: str) -> str:
    return process_name.removesuffix(".exe").replace(".", " ").title()


def _clamp(value: int) -> int:
    return max(0, min(value, 100))


class AudioOutput(QObject):
    """The default output device and its volume, the other output devices, and the apps playing sound."""

    volumeChanged = pyqtSignal()
    deviceChanged = pyqtSignal()
    appsChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._service = AudioOutputService()
        self._volume = 0
        self._muted = False
        self._apps: list[dict[str, Any]] = []
        self._app_volumes: list[ISimpleAudioVolume] = []
        self._read_volume()
        IconService.instance().icons_changed.connect(self._on_icons_changed)
        service = self._service
        service.register_widget(self)
        self.destroyed.connect(lambda *_: service.unregister_widget(self))

    def on_output_volume_changed(self) -> None:
        self._read_volume()
        self.volumeChanged.emit()

    def on_output_device_changed(self) -> None:
        self._read_volume()
        self.deviceChanged.emit()
        self.volumeChanged.emit()
        if self._apps:
            self.refreshApps()

    def _read_volume(self) -> None:
        volume = self._service.get_volume_interface()
        try:
            self._volume = round(volume.GetMasterVolumeLevelScalar() * 100) if volume else 0
            self._muted = bool(volume.GetMute()) if volume else False
        except Exception as e:
            logging.debug("Could not read the volume: %s", e)

    @qml_property(bool, notify=deviceChanged)
    def available(self) -> bool:
        return self._service.get_volume_interface() is not None

    @qml_property(str, notify=deviceChanged)
    def deviceName(self) -> str:
        speakers = self._service.get_speakers()
        return (speakers.FriendlyName or "") if speakers else ""

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

    # [{key, pid, name, process, appId, volume, muted, icon}], read by refreshApps()
    @qml_property("QVariantList", notify=appsChanged)
    def apps(self) -> list[dict[str, Any]]:
        return self._apps

    @pyqtSlot(int)
    def setVolume(self, value: int) -> None:
        volume = self._service.get_volume_interface()
        if volume is None:
            return
        try:
            volume.SetMasterVolumeLevelScalar(_clamp(value) / 100, None)
        except Exception as e:
            logging.error("Could not set the volume: %s", e)
            return
        self._volume = _clamp(value)
        self.volumeChanged.emit()

    @pyqtSlot(bool)
    def setMuted(self, muted: bool) -> None:
        volume = self._service.get_volume_interface()
        if volume is None:
            return
        try:
            volume.SetMute(int(muted), None)
        except Exception as e:
            logging.error("Could not mute: %s", e)
            return
        self._muted = muted
        self.volumeChanged.emit()

    @pyqtSlot()
    def toggleMute(self) -> None:
        self.setMuted(not self._muted)

    @pyqtSlot(str)
    def setDevice(self, device_id: str) -> None:
        self._service.set_default_device(device_id)

    @pyqtSlot()
    def refreshApps(self) -> None:
        sessions = self._service.get_active_audio_sessions(get_app_name_from_pid, _app_label)
        self._app_volumes = [session["volume_interface"] for session in sessions]
        self._apps = [self._app(key, session) for key, session in enumerate(sessions)]
        self.appsChanged.emit()

    def _app(self, key: int, session: AudioSessionInfo) -> dict[str, Any]:
        try:
            volume = round(session["volume_interface"].GetMasterVolume() * 100)
            muted = bool(session["volume_interface"].GetMute())
        except Exception:
            volume, muted = 0, False
        pid = session["pid"]
        return {
            "key": key,
            "pid": pid,
            "name": session["app_name"],
            "process": session["name"],
            "appId": get_aumid_for_process(pid) or "",
            "volume": volume,
            "muted": muted,
            "icon": icon_url(ProcessIcon(pid), IconService.instance().revision),
        }

    def _on_icons_changed(self) -> None:
        # The provider answered with a blank icon while it loaded, so the new revision makes QML ask again
        if self._apps:
            for app in self._apps:
                app["icon"] = icon_url(ProcessIcon(app["pid"]), IconService.instance().revision)
            self.appsChanged.emit()

    # A slider that sets this already shows the value, and a new apps list would rebuild it mid-drag
    @pyqtSlot(int, int)
    def setAppVolume(self, key: int, value: int) -> None:
        if 0 <= key < len(self._app_volumes):
            try:
                self._app_volumes[key].SetMasterVolume(_clamp(value) / 100, None)
                self._apps[key]["volume"] = _clamp(value)
            except Exception as e:
                logging.error("Could not set the volume of %s: %s", self._apps[key]["name"], e)

    @pyqtSlot(int, bool)
    def setAppMuted(self, key: int, muted: bool) -> None:
        if 0 <= key < len(self._app_volumes):
            try:
                self._app_volumes[key].SetMute(int(muted), None)
            except Exception as e:
                logging.error("Could not mute %s: %s", self._apps[key]["name"], e)
                return
            self._apps[key]["muted"] = muted
            self.appsChanged.emit()

    @pyqtSlot()
    def beep(self) -> None:
        user32.MessageBeep(0)
