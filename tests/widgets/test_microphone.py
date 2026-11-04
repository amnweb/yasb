from types import SimpleNamespace
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QUrl
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.microphone import input as input_module
from core.widgets.services.microphone.input import AudioInput
from settings import QML_IMPORT_PATH
from tests.support.audio import FakeVolume
from tests.support.qt import find_item, wait


class FakeInputService:
    """Stands in for AudioInputService, so the tests never touch the real microphone."""

    def __init__(self) -> None:
        self.volume: FakeVolume | None = FakeVolume(0.4)
        self.listeners: list[Any] = []
        self.default = "headset"

    def register_widget(self, widget: Any) -> None:
        self.listeners.append(widget)

    def unregister_widget(self, widget: Any) -> None:
        self.listeners.remove(widget)

    def get_microphone_interface(self) -> FakeVolume | None:
        return self.volume

    def get_microphone(self) -> SimpleNamespace | None:
        return SimpleNamespace(FriendlyName="Headset") if self.volume else None

    def get_all_devices(self) -> list[tuple[str, str | None]]:
        return [("headset", "Headset"), ("webcam", "Webcam")]

    def get_default_device_id(self) -> str:
        return self.default

    def set_default_device(self, device_id: str) -> bool:
        self.default = device_id
        return True


@pytest.fixture
def service(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> FakeInputService:
    service = FakeInputService()
    monkeypatch.setattr(input_module, "AudioInputService", lambda: service)
    return service


def test_the_level_device_and_devices_come_from_the_service(service: FakeInputService):
    audio = AudioInput()
    assert (audio.property("volume"), audio.property("muted"), audio.property("deviceName")) == (40, False, "Headset")
    assert audio.property("available") is True
    assert [(device["name"], device["current"]) for device in audio.property("devices")] == [
        ("Headset", True),
        ("Webcam", False),
    ]
    audio.setDevice("webcam")
    assert service.default == "webcam"


def test_the_microphone_mutes_at_zero_and_unmutes_above_it(service: FakeInputService):
    audio = AudioInput()
    audio.setVolume(-5)
    assert service.volume is not None
    assert (service.volume.level, service.volume.muted, audio.property("muted")) == (0.0, True, True)
    audio.setVolume(150)
    assert (service.volume.level, service.volume.muted, audio.property("volume")) == (1.0, False, 100)
    audio.toggleMute()
    assert service.volume.muted and audio.property("muted")


def test_changes_from_windows_reach_the_widget(service: FakeInputService):
    audio = AudioInput()
    volume_changes: list[bool] = []
    device_changes: list[bool] = []
    audio.volumeChanged.connect(lambda: volume_changes.append(True))
    audio.deviceChanged.connect(lambda: device_changes.append(True))
    assert service.volume is not None
    service.volume.level, service.volume.muted = 0.75, True
    for listener in service.listeners:
        listener.on_input_volume_changed()
    assert (audio.property("volume"), audio.property("muted")) == (75, True) and volume_changes

    service.volume = FakeVolume(0.2)
    for listener in service.listeners:
        listener.on_input_device_changed()
    assert (audio.property("volume"), audio.property("muted")) == (20, False) and device_changes


def test_without_a_microphone_nothing_is_set(service: FakeInputService):
    service.volume = None
    audio = AudioInput()
    assert (audio.property("available"), audio.property("deviceName"), audio.property("volume")) == (False, "", 0)
    audio.setVolume(50)
    audio.toggleMute()
    assert (audio.property("volume"), audio.property("muted")) == (0, False)


def test_the_service_forgets_a_widget_once_qml_deleted_it(service: FakeInputService):
    audio = AudioInput()
    assert service.listeners == [audio]
    sip.delete(audio)
    assert service.listeners == []


def test_the_bar_icon_shows_muted_and_a_missing_microphone(service: FakeInputService):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect_warnings)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Microphone" / "Microphone.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(10)
    icon = find_item(widget, "icon")
    assert icon is not None
    widget.setProperty("icon", "on")
    widget.setProperty("mutedIcon", "off")
    assert icon.property("text") == "on"
    audio = widget.findChild(AudioInput)
    assert audio is not None
    audio.setMuted(True)
    assert icon.property("text") == "off"
    audio.setMuted(False)
    service.volume = None
    for listener in service.listeners:
        listener.on_input_device_changed()
    assert icon.property("text") == "off"
    assert not warnings
    sip.delete(widget)
