# pyright: reportPrivateUsage=false

from types import SimpleNamespace

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QUrl
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.utils.icons.service import IconService
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.volume import output as output_module
from core.widgets.services.volume.output import AudioOutput
from settings import QML_IMPORT_PATH
from tests.support.audio import FakeAudioService
from tests.support.qt import find_item, wait


def aumid(pid: int) -> str:
    return f"App{pid}"


@pytest.fixture
def service(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> FakeAudioService:
    service = FakeAudioService()
    beeps: list[int] = []
    monkeypatch.setattr(output_module, "AudioOutputService", lambda: service)
    monkeypatch.setattr(output_module, "get_aumid_for_process", aumid)
    monkeypatch.setattr(output_module, "user32", SimpleNamespace(MessageBeep=beeps.append))
    return service


def test_the_volume_device_and_devices_come_from_the_service(service: FakeAudioService):
    audio = AudioOutput()
    assert (audio.property("volume"), audio.property("muted"), audio.property("deviceName")) == (30, False, "Speakers")
    assert [(device["name"], device["current"]) for device in audio.property("devices")] == [
        ("Headphones", False),
        ("Speakers", True),
    ]


def test_setting_the_volume_clamps_it_and_mute_toggles(service: FakeAudioService):
    audio = AudioOutput()
    audio.setVolume(150)
    assert (service.volume.level, audio.property("volume")) == (1.0, 100)
    audio.toggleMute()
    assert service.volume.muted and audio.property("muted")


def test_a_change_from_windows_reaches_the_widget(service: FakeAudioService):
    audio = AudioOutput()
    changes: list[bool] = []
    audio.volumeChanged.connect(lambda: changes.append(True))
    service.volume.level = 0.6
    for listener in service.listeners:
        listener.on_output_volume_changed()
    assert audio.property("volume") == 60 and changes


def test_apps_are_read_on_request_and_a_volume_drag_does_not_rebuild_them(service: FakeAudioService):
    audio = AudioOutput()
    assert audio.property("apps") == []
    audio.refreshApps()
    [app] = audio.property("apps")
    assert (app["name"], app["process"], app["appId"], app["volume"], app["muted"]) == (
        "Spotify",
        "spotify.exe",
        "App42",
        80,
        False,
    )

    rebuilt: list[bool] = []
    audio.appsChanged.connect(lambda: rebuilt.append(True))
    audio.setAppVolume(app["key"], 25)
    assert service.app_volume.level == 0.25 and not rebuilt
    audio.setAppMuted(app["key"], True)
    assert service.app_volume.muted and rebuilt and audio.property("apps")[0]["muted"]


def test_app_icons_ask_again_once_the_icon_service_loaded_them(service: FakeAudioService):
    audio = AudioOutput()
    audio.refreshApps()
    before = audio.property("apps")[0]["icon"]
    IconService.instance().icons_changed.emit()
    after = audio.property("apps")[0]["icon"]
    assert after != before


def test_a_widget_made_again_does_not_reuse_an_icon_url_from_before_the_icon_loaded(service: FakeAudioService):
    first = AudioOutput()
    first.refreshApps()
    # The provider answered this URL with a placeholder, which QML keeps in its cache
    placeholder = first.property("apps")[0]["icon"]
    IconService.instance().icons_changed.emit()
    # Like a bar reload, which makes the widgets again
    second = AudioOutput()
    second.refreshApps()
    assert second.property("apps")[0]["icon"] != placeholder


def test_the_service_forgets_a_widget_once_qml_deleted_it(service: FakeAudioService):
    audio = AudioOutput()
    assert service.listeners == [audio]
    sip.delete(audio)
    assert service.listeners == []


def test_the_widget_shows_the_level(service: FakeAudioService):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Volume" / "Volume.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(10)
    icon = find_item(widget, "icon")
    assert icon is not None
    # 30% is one wave
    assert icon.property("text") == "\ue993"
    sip.delete(widget)
