# pyright: reportPrivateUsage=false

import logging
import time
from collections.abc import Coroutine
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QBuffer, QIODevice, QSize, QUrl
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.services.media import media as media_module
from core.services.media.art import MEDIA_ART_PROVIDER, MediaArtProvider, art_url, keep_art
from core.services.media.media import MediaInfo, MediaService, _Playback, _Timeline
from core.services.media.now_playing import NowPlaying
from core.services.volume import output as output_module
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.audio import FakeAudioService
from tests.support.qt import wait


def no_thread(_service: MediaService) -> None:
    pass


def no_aumid(_pid: int) -> str:
    return ""


@pytest.fixture
def service(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> MediaService:
    """A service whose thread never reaches Windows; the tests run the media thread's part themselves."""
    monkeypatch.setattr(MediaService, "_run", no_thread)
    monkeypatch.setattr(MediaService, "_instance", None)
    return MediaService.instance()


def add(service: MediaService, app_id: str, **fields: Any) -> None:
    service._players[app_id] = MediaInfo(app_id, app_id.title(), f"{app_id}.exe", **fields)


def playback(**changes: Any) -> _Playback:
    fields: dict[str, Any] = {
        "playing": True,
        "rate": 1.0,
        "can_play_pause": True,
        "can_previous": True,
        "can_next": True,
        "can_seek": True,
        "can_shuffle": False,
        "can_repeat": False,
        "shuffle": False,
        "repeat": "none",
    }
    return _Playback(**(fields | changes))


def png(width: int, height: int) -> bytes:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data().data())


class Session:
    """Stands in for a WinRT media session, accepting or refusing a seek."""

    def __init__(self, accept: bool) -> None:
        self.accept = accept
        self.ticks: list[int] = []

    def try_change_playback_position_async(self, ticks: int) -> Coroutine[Any, Any, bool]:
        self.ticks.append(ticks)

        async def answer() -> bool:
            return self.accept

        return answer()


def test_the_position_moves_only_while_playing_and_stops_at_the_end():
    player = MediaInfo("a", "A", "a.exe", playing=True, position=10, position_time=995, rate=2, duration=100)
    assert player.position_at(1000) == 20
    assert replace(player, playing=False).position_at(1000) == 10
    assert replace(player, duration=15).position_at(1000) == 15
    assert replace(player, position_time=0).position_at(1000) == 10


def test_an_older_or_unset_timeline_does_not_move_the_position(service: MediaService):
    add(service, "a")
    service._apply_timeline("a", _Timeline(30, 2000, 100))
    service._apply_timeline("a", _Timeline(10, 1500, 100))
    # WinRT's unset DateTime, 1601-01-01
    service._apply_timeline("a", _Timeline(50, -11644473600, 100))
    player = service._players["a"]
    assert (player.position, player.position_time, player.duration) == (30, 2000, 100)


def test_pausing_keeps_the_position_reached(service: MediaService, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(media_module, "time", SimpleNamespace(time=lambda: 1010.0))
    add(service, "a", playing=True, position=10, position_time=1000, duration=100)
    service._apply_playback("a", playback(playing=False, can_shuffle=True, repeat="list"))
    player = service._players["a"]
    assert (player.playing, player.position, player.position_time) == (False, 20, 1010)
    assert (player.can_shuffle, player.repeat) == (True, "list")


def test_a_player_already_playing_when_first_seen_keeps_the_time_it_played(
    service: MediaService, monkeypatch: pytest.MonkeyPatch
):
    # Chrome reports position 0 from when the video started, and only the time since then moves it
    def timeline(_session: Any) -> _Timeline:
        return _Timeline(0, 1000, 600)

    def playing(_session: Any) -> _Playback:
        return playback()

    monkeypatch.setattr(media_module, "time", SimpleNamespace(time=lambda: 1065.0))
    monkeypatch.setattr(media_module, "_read_timeline", timeline)
    monkeypatch.setattr(media_module, "_read_playback", playing)
    add(service, "chrome")
    service._sessions["chrome"] = cast(Any, object())
    service._snapshot("chrome")
    assert service._players["chrome"].position_at(1065.0) == 65


def test_the_player_follows_windows_until_one_is_picked(service: MediaService):
    for app_id in ("a", "b", "c"):
        add(service, app_id)
    service._select("b", follow_system=True)
    assert service._current == "b"
    service._switch(1)
    assert service._current == "c"
    # A player opening or closing keeps the pick
    service._select("a", follow_system=False)
    assert service._current == "c"
    # The picked player closed
    del service._players["c"]
    service._select("a", follow_system=False)
    assert service._current == "a"
    service._switch(-1)
    assert service._current == "b"


def test_a_seek_moves_the_position_once_the_player_accepts_it(service: MediaService, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(media_module, "time", SimpleNamespace(time=lambda: 500.0))
    for accept, expected in ((False, (1, 100)), (True, (42.5, 500.0))):
        add(service, "a", position=1, position_time=100, duration=300)
        session = Session(accept)
        service._sessions["a"] = cast(Any, session)
        service._loop.run_until_complete(service._seek("a", 42.5))
        player = service._players["a"]
        assert session.ticks == [425_000_000]
        assert (player.position, player.position_time) == expected


class FailingSession:
    """Stands in for a WinRT media session whose properties can't be read."""

    def __init__(self, winerror: int) -> None:
        self.winerror = winerror

    def try_get_media_properties_async(self) -> Coroutine[Any, Any, Any]:
        async def fail() -> Any:
            raise OSError(None, "failed", None, self.winerror)

        return fail()


def test_only_a_player_that_is_still_starting_is_not_an_error(service: MediaService, caplog: pytest.LogCaptureFixture):
    for winerror, level in ((media_module.NOT_READY, logging.DEBUG), (-2147467259, logging.ERROR)):
        add(service, "music", title="Before")
        service._sessions["music"] = cast(Any, FailingSession(winerror))
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="WindowsMedia"):
            service._loop.run_until_complete(service._sync_properties("music"))
        assert [record.levelno for record in caplog.records if record.name == "WindowsMedia"] == [level]
        assert service._players["music"].title == "Before"


def test_now_playing_shows_the_current_player_and_ticks_only_while_playing(service: MediaService):
    now_playing = NowPlaying()
    assert now_playing.property("available") is False
    add(
        service,
        "spotify",
        title="Song",
        artist="Band",
        playing=True,
        position=5,
        position_time=time.time(),
        duration=200,
        can_seek=True,
        art=png(8, 8),
        art_revision=3,
    )
    service._current = "spotify"
    service._publish()
    wait(10)
    assert (now_playing.property("title"), now_playing.property("artist")) == ("Song", "Band")
    assert now_playing.property("thumbnail") == art_url(3)
    assert now_playing.property("canSeek") and now_playing._ticker.isActive()
    assert 5 <= now_playing.property("position") < 6

    service._players["spotify"] = replace(service._players["spotify"], playing=False)
    service._publish()
    wait(10)
    assert not now_playing._ticker.isActive()

    now_playing.setProperty("positionInterval", 10)
    assert now_playing.property("positionInterval") == 50


def test_the_art_provider_serves_the_kept_art_scaled():
    provider = MediaArtProvider()
    keep_art({7: png(64, 32)})
    image, size = provider.requestImage("7", QSize(16, 16))
    assert (size, image.size()) == (QSize(64, 32), QSize(16, 8))
    keep_art({})
    image, _size = provider.requestImage("7", QSize(16, 16))
    assert image.isNull()


def test_the_widget_shows_the_title_and_finds_the_players_audio(service: MediaService, monkeypatch: pytest.MonkeyPatch):
    audio = FakeAudioService()
    monkeypatch.setattr(output_module, "AudioOutputService", lambda: audio)
    monkeypatch.setattr(output_module, "get_aumid_for_process", no_aumid)
    add(service, "spotify", title="Song", artist="Band")
    service._current = "spotify"
    service._publish()

    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    engine.addImageProvider(MEDIA_ART_PROVIDER, MediaArtProvider())
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Media" / "Media.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(10)
    widget.setProperty("showArtist", False)
    assert widget.property("label") == "Song"

    widget.setProperty("showArtist", True)
    assert widget.property("label") == "Song - Band"

    [audio_output] = [child for child in widget.children() if isinstance(child, output_module.AudioOutput)]
    audio_output.refreshApps()
    app = widget.property("app")
    app = app.toVariant() if hasattr(app, "toVariant") else app
    assert app["name"] == "Spotify"
    sip.delete(widget)


def test_the_widget_takes_no_space_without_a_player(service: MediaService, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(output_module, "AudioOutputService", FakeAudioService)
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    engine.addImageProvider(MEDIA_ART_PROVIDER, MediaArtProvider())
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Media" / "Media.qml")))
    widget = component.createWithInitialProperties({"hideEmpty": True})
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(10)
    # So the bar leaves no gap where it would be
    assert not widget.property("shown") and widget.property("implicitWidth") == 0
    sip.delete(widget)
