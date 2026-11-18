# pyright: reportPrivateUsage=false

import asyncio
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from PIL import Image
from PyQt6.QtCore import QEvent, QObject, Qt, pyqtSignal
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QSlider

from core.validation.widgets.yasb.media import MediaWidgetConfig
from core.widgets.services.media import popup as popup_module
from core.widgets.services.media import volume as volume_module
from core.widgets.services.media.media import SessionState, WindowsMedia
from core.widgets.services.media.popup import MediaSessionsPopup, time_text
from core.widgets.services.media.volume import AppVolumeController
from core.widgets.yasb.media import MediaWidget


def state(app_id: str, title: str, current: bool = False) -> SessionState:
    item = SessionState(app_id)
    item.title = title
    item.artist = "Artist"
    item.is_current = current
    item.is_playing = True
    item.playback_ready = True
    item.timeline_enabled = True
    item.duration = 200
    item.current_pos = 50
    return item


class FakeMedia(QObject):
    media_data_changed = pyqtSignal(dict)
    current_session_changed = pyqtSignal()
    media_properties_changed = pyqtSignal()
    timeline_info_changed = pyqtSignal()
    playback_info_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.control_session = AsyncMock()
        self.prev = Mock()
        self.play_pause = Mock()
        self.next = Mock()


class FakeVisualizer(QFrame):
    def __init__(self, config: Any):
        super().__init__()
        self.config = config
        self.setFixedSize(40, 20)

    def set_palette(self, name: str) -> None:
        self.palette_name = name


@pytest.fixture
def widget(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[MediaWidget]:
    import core.widgets.yasb.media as widget_module

    service = FakeMedia()
    monkeypatch.setattr(widget_module, "WindowsMedia", Mock(return_value=service))
    monkeypatch.setattr(popup_module, "AudioVisualizerWidget", FakeVisualizer)
    volumes = Mock(spec=AppVolumeController)
    volumes.snapshot.return_value = (60, False)
    monkeypatch.setattr(popup_module, "AppVolumeController", Mock(return_value=volumes))
    instance = MediaWidget(
        MediaWidgetConfig.model_validate(
            {
                "media_menu": {
                    "layout": "compact",
                    "show_all_sessions": True,
                    "pinnable": True,
                    "show_visualizer": True,
                    "show_volume_slider": True,
                    "show_source": False,
                    "blur": False,
                    "round_corners": False,
                    "thumbnail_size": 88,
                }
            }
        )
    )
    service.media_data_changed.emit(
        {"chrome": state("chrome.exe", "Video", True), "player": state("player.exe", "Song")}
    )
    yield instance
    if hasattr(instance, "dialog"):
        instance.dialog.hide()
        instance.dialog.deleteLater()
    instance.deleteLater()


def open_popup(widget: MediaWidget) -> MediaSessionsPopup:
    widget.show_menu()
    assert isinstance(widget.dialog, MediaSessionsPopup)
    return widget.dialog


def test_native_cards_update_without_rebuilding_or_changing_selection(widget: MediaWidget):
    popup = open_popup(widget)
    assert set(popup.cards) == {"chrome", "player"}
    chrome = popup.cards["chrome"]
    assert chrome.elapsed.text() == "0:50" and chrome.remaining.text() == "−2:30"
    assert chrome.progress.value() == 250
    widget.all_sessions["chrome"].title = "New video"
    widget.all_sessions["chrome"].current_pos = 100
    popup.refresh(widget.all_sessions)
    assert popup.cards["chrome"] is chrome
    assert chrome.title.text() == "New video"
    assert chrome.progress.value() == 500
    assert widget.current_session is widget.all_sessions["chrome"]
    assert not hasattr(widget, "_seeking")  # compact mode never uses legacy popup state
    widget._update_interpolated_position()


def test_card_buttons_target_their_own_session_and_seek_does_not_snap_back(
    widget: MediaWidget, monkeypatch: pytest.MonkeyPatch
):
    popup = open_popup(widget)
    command = Mock()
    monkeypatch.setattr(popup, "command", command)
    card = popup.cards["player"]
    card.play.click()
    command.assert_called_with("player", "play_pause")
    card.previous.click()
    command.assert_called_with("player", "prev")
    card.next_track.click()
    command.assert_called_with("player", "next")
    card._begin_seek()
    card.progress.setValue(750)
    card.update_state(card.state)
    assert card.progress.value() == 750
    card._finish_seek()
    command.assert_called_with("player", "seek", 150)
    assert widget.current_session is widget.all_sessions["chrome"]


def test_session_removal_and_empty_state_keep_popup_open(widget: MediaWidget):
    popup = open_popup(widget)
    removed = popup.cards["chrome"]
    popup.refresh({"player": widget.all_sessions["player"]})
    assert set(popup.cards) == {"player"}
    assert not removed.isVisible()
    popup.refresh({})
    assert popup.empty.isVisible() and popup.isVisible()


def test_single_session_option_and_unsupported_controls(widget: MediaWidget):
    widget.config.media_menu.show_all_sessions = False
    popup = open_popup(widget)
    assert set(popup.cards) == {"chrome"}
    card = popup.cards["chrome"]
    card.state.controls_next_enabled = False
    card.state.timeline_enabled = False
    card.state.is_playing = False
    card.update_state(card.state)
    assert not card.next_track.isEnabled()
    assert not card.timeline.isVisible()
    assert card.visualizer is not None and not card.visualizer.isVisible()


def test_pin_and_volume_controls_keep_the_native_popup_open(widget: MediaWidget):
    popup = open_popup(widget)
    card = popup.cards["chrome"]
    assert card.visualizer is not None
    assert card.visualizer.config.bars.count == 8
    card.volume.setValue(45)
    cast(Any, popup.volumes).set_volume.assert_called_with("chrome.exe", 45)
    card.mute.click()
    cast(Any, popup.volumes).toggle_mute.assert_called_with("chrome.exe")
    assert popup.isVisible()
    popup._pin_buttons[0][0].click()
    popup.event(QEvent(QEvent.Type.WindowDeactivate))
    assert popup.is_pinned and popup.isVisible()
    popup.hide()
    assert not popup.volume_timer.isActive()


def test_unavailable_volume_is_disabled_and_text_is_not_html(widget: MediaWidget):
    popup = open_popup(widget)
    cast(Any, popup.volumes).snapshot.return_value = None
    popup.update_volumes()
    card = popup.cards["chrome"]
    assert not card.volume.isEnabled() and not card.mute.isEnabled()
    assert card.volume_value.text() == "—"
    card.state.title = "<b>Title</b>"
    card.state.thumbnail = Image.new("RGBA", (120, 60), "blue")
    card.update_state(card.state)
    assert card.title.textFormat() == Qt.TextFormat.PlainText
    assert card.thumbnail.pixmap() is not None


def test_card_contents_fit_their_boxes_and_many_sessions_scroll(widget: MediaWidget, qapp: QApplication):
    popup = open_popup(widget)
    popup.setStyleSheet("""
        .header { padding: 14px 16px; }
        .media-session-card { margin: 6px 16px; padding: 12px; border: 1px solid #292929; }
        .title { font-size: 14px; }
        .artist, .volume-value { font-size: 12px; }
        .btn { min-width: 24px; max-width: 24px; padding: 0; }
        .mute-button { min-width: 20px; max-width: 20px; padding: 0; }
        .playback-time { font-size: 10px; }
    """)
    popup.refresh({str(i): state(f"app{i}.exe", "A long title " * 20) for i in range(12)})
    qapp.processEvents()
    popup._fit_content()
    qapp.processEvents()
    assert popup.height() <= widget.config.media_menu.max_height
    scrollbar = popup.sessions_scroll.verticalScrollBar()
    assert scrollbar is not None and scrollbar.maximum() > 0
    for card in popup.cards.values():
        bounds = card.rect().adjusted(16, 6, -16, -6)
        for child in [*card.findChildren(QLabel), *card.findChildren(QSlider)]:
            rect = child.rect().translated(child.mapTo(card, child.rect().topLeft()))
            assert bounds.contains(rect), (child.property("class"), bounds, rect)


@pytest.mark.parametrize(
    "seconds, expected", [(0, "0:00"), (65, "1:05"), (3661, "1:01:01"), (-10, "0:00"), (float("nan"), "0:00")]
)
def test_time_format(seconds: float, expected: str):
    assert time_text(seconds) == expected


def test_commands_use_requested_player_and_ignore_removed_or_unsupported_sessions():
    chrome = state("chrome.exe", "Video", True)
    player = state("player.exe", "Song")
    chrome.session = cast(Any, SimpleNamespace(try_toggle_play_pause_async=AsyncMock()))
    player.session = cast(
        Any,
        SimpleNamespace(
            try_toggle_play_pause_async=AsyncMock(),
            try_change_playback_position_async=AsyncMock(),
            try_skip_next_async=AsyncMock(),
        ),
    )
    fake = cast(
        WindowsMedia,
        SimpleNamespace(
            _trackers={"chrome": chrome, "player": player}, _smtc_lock=threading.RLock(), _interpolate_and_emit=Mock()
        ),
    )
    asyncio.run(WindowsMedia.control_session(fake, "player", "play_pause"))
    cast(Any, player.session).try_toggle_play_pause_async.assert_awaited_once()
    cast(Any, chrome.session).try_toggle_play_pause_async.assert_not_awaited()
    asyncio.run(WindowsMedia.control_session(fake, "player", "seek", 999))
    cast(Any, player.session).try_change_playback_position_async.assert_awaited_once_with(200 * 10_000_000)
    player.controls_next_enabled = False
    asyncio.run(WindowsMedia.control_session(fake, "player", "next"))
    asyncio.run(WindowsMedia.control_session(fake, "removed", "next"))
    cast(Any, player.session).try_skip_next_async.assert_not_awaited()
    assert chrome.is_current and not player.is_current


def test_volume_targets_application_sessions_and_never_system_master(monkeypatch: pytest.MonkeyPatch):
    volume_a = Mock()
    volume_a.GetMasterVolume.return_value = 0.7
    volume_a.GetMute.return_value = False
    volume_b = Mock()
    sessions = [
        SimpleNamespace(Process=SimpleNamespace(pid=1, name=lambda: "chrome.exe"), SimpleAudioVolume=volume_a),
        SimpleNamespace(Process=SimpleNamespace(pid=2, name=lambda: "player.exe"), SimpleAudioVolume=volume_b),
    ]
    monkeypatch.setattr(volume_module.AudioUtilities, "GetAllSessions", Mock(return_value=sessions))
    monkeypatch.setattr(volume_module, "get_aumid_for_process", Mock(return_value=""))
    controller = AppVolumeController()
    controller.refresh({"chrome.exe", "player.exe"})
    assert controller.snapshot("chrome.exe") == (70, False)
    controller.set_volume("chrome.exe", 35)
    volume_a.SetMasterVolume.assert_called_once_with(0.35, None)
    volume_a.SetMute.assert_called_once_with(False, None)
    volume_b.SetMasterVolume.assert_not_called()
    controller.toggle_mute("chrome.exe")
    volume_a.SetMute.assert_called_with(True, None)


def test_ambiguous_browser_volume_is_not_bound_to_the_wrong_web_app(monkeypatch: pytest.MonkeyPatch):
    session = SimpleNamespace(Process=SimpleNamespace(pid=1, name=lambda: "chrome.exe"), SimpleAudioVolume=Mock())
    monkeypatch.setattr(volume_module.AudioUtilities, "GetAllSessions", Mock(return_value=[session]))
    monkeypatch.setattr(volume_module, "get_aumid_for_process", Mock(return_value=""))
    monkeypatch.setattr(volume_module, "get_process_name_for_aumid", Mock(return_value="chrome.exe"))
    controller = AppVolumeController()
    controller.refresh({"web.app.one", "web.app.two"})
    assert controller.snapshot("web.app.one") is None
    assert controller.snapshot("web.app.two") is None


def test_default_configuration_keeps_the_existing_popup():
    menu = MediaWidgetConfig().media_menu
    assert menu.layout == "default" and not menu.show_all_sessions and not menu.pinnable


def test_repeated_bar_click_closes_without_creating_another_popup(widget: MediaWidget):
    popup = open_popup(widget)
    widget.show_menu()
    assert widget.dialog is popup
    assert popup._is_closing


def test_real_inside_clicks_do_not_dismiss_the_popup(widget: MediaWidget, monkeypatch: pytest.MonkeyPatch):
    popup = open_popup(widget)
    monkeypatch.setattr(popup, "command", Mock())
    card = popup.cards["chrome"]
    # PyQt6's stub mistakenly declares this static helper as an instance method.
    mouse_click = cast(Any, QTest.mouseClick)
    mouse_click(card.play, Qt.MouseButton.LeftButton)
    mouse_click(card.volume, Qt.MouseButton.LeftButton)
    mouse_click(card.progress, Qt.MouseButton.LeftButton)
    assert popup.isVisible() and not popup._is_closing


def test_popup_keeps_configured_width_and_right_aligned_pin_after_updates(widget: MediaWidget, qapp: QApplication):
    popup = open_popup(widget)
    popup.setStyleSheet("""
        .media-menu { min-width: 360px; }
        .header { padding: 14px 16px; }
        .media-session-card { margin: 6px 16px; padding: 12px; }
    """)
    for _ in range(3):
        popup.refresh(widget.all_sessions)
        qapp.processEvents()
        assert popup.width() == widget.config.media_menu.width
        assert popup.header.width() >= popup.width() - 2
        pin = popup._pin_buttons[0][0]
        assert pin.mapTo(popup, pin.rect().topRight()).x() >= popup.width() - 20


def test_failed_or_non_finite_seek_does_not_move_the_timeline():
    player = state("player.exe", "Song")
    player.session = cast(Any, SimpleNamespace(try_change_playback_position_async=AsyncMock(return_value=False)))
    fake = cast(WindowsMedia, SimpleNamespace(_trackers={"player": player}, _smtc_lock=threading.RLock()))
    asyncio.run(WindowsMedia.control_session(fake, "player", "seek", float("inf")))
    cast(Any, player.session).try_change_playback_position_async.assert_not_awaited()
    asyncio.run(WindowsMedia.control_session(fake, "player", "seek", 90))
    assert player.last_snapshot_pos == 0


def test_popup_dispatches_without_switching_current_session(widget: MediaWidget):
    popup = open_popup(widget)

    async def dispatch():
        popup.command("player", "play_pause")
        await asyncio.sleep(0)

    asyncio.run(dispatch())
    cast(Any, widget.media).control_session.assert_awaited_once_with("player", "play_pause", None)
    assert widget.current_session is widget.all_sessions["chrome"]


def test_actual_visualizer_uses_shared_capture_and_solid_blue(
    widget: MediaWidget, qapp: QApplication, monkeypatch: pytest.MonkeyPatch
):
    import core.widgets.yasb.audio_visualizer as visualizer_module

    class Capture(QObject):
        frame_ready = pyqtSignal()
        audio_started = pyqtSignal()
        audio_stopped = pyqtSignal()
        idle_timeout = pyqtSignal(str)
        format_changed = pyqtSignal(int)
        sample_rate = 48000
        is_active = False
        attach = Mock()
        detach = Mock()
        set_reader_visible = Mock()

    capture = Capture()
    monkeypatch.setattr(visualizer_module.AudioVisualizerCaptureService, "instance", Mock(return_value=capture))
    monkeypatch.setattr(popup_module, "AudioVisualizerWidget", visualizer_module.AudioVisualizerWidget)
    popup = open_popup(widget)
    popup.setStyleSheet(".native-media-menu .audio-visualizer-canvas { qproperty-fillbrush: #4cc2ff; }")
    qapp.processEvents()
    assert capture.attach.call_count == 2
    for card in popup.cards.values():
        assert card.visualizer is not None
        assert len(card.visualizer._canvas.samples) == 8
        assert card.visualizer._canvas.fillbrush.color().name() == "#4cc2ff"
    popup.hide()
    capture.set_reader_visible.assert_called_with(False)

    from core.validation.widgets.yasb.audio_visualizer import AudioVisualizerConfig
    from core.widgets.services.media.artwork import ProgressWaveVisualizer
    from core.widgets.services.media.waves import LayeredWaveCanvas

    wave = ProgressWaveVisualizer(AudioVisualizerConfig.model_validate({"style": "waves", "height": 28}))
    host = QFrame()
    wave.setParent(host)
    try:
        wave.setMinimumWidth(0)
        host.show()
        wave.resize(74, 28)
        wave.set_palette("orange")
        wave.show()
        qapp.processEvents()
        assert isinstance(wave._canvas, LayeredWaveCanvas)
        assert wave._canvas.width() == 74
        assert wave._canvas.palette_name == "orange"
    finally:
        wave.hide()
        wave.deleteLater()
        host.hide()
        host.deleteLater()


@pytest.fixture
def artwork_popup(widget: MediaWidget, monkeypatch: pytest.MonkeyPatch) -> MediaSessionsPopup:
    from core.widgets.services.media import artwork

    monkeypatch.setattr(artwork, "ProgressWaveVisualizer", FakeVisualizer)
    widget.config.media_menu.layout = "artwork"
    widget.config.media_menu.width = 380
    popup = open_popup(widget)
    popup.setStyleSheet("""
        .media-session-card.artwork-session-card { margin: 0; padding: 0; border: none; background: transparent; }
        .artwork-session-card .btn { min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px; padding: 0; }
        .artwork-session-card .mute-button, .volume-dropdown-button { min-width: 26px; max-width: 26px; padding: 0; }
        .media-volume-dropdown { background: #191919; border: 1px solid #292929; }
    """)
    popup._fit_content()
    return popup


def test_artwork_controls_follow_reference_order_and_overlay_stays_inside_panel(
    artwork_popup: MediaSessionsPopup, qapp: QApplication
):
    from core.widgets.services.media.artwork import ArtworkMediaSessionCard

    qapp.processEvents()
    card = artwork_popup.cards["chrome"]
    assert isinstance(card, ArtworkMediaSessionCard)
    assert card.title.text() == "Video · Artist"
    assert card.remaining.text() == "03:20" and card.elapsed.text() == "00:50"
    assert not card.thumbnail.isVisible() and not card.artist.isVisible()
    assert (
        card.mute.mapTo(card, card.mute.rect().center()).x()
        < card.previous.mapTo(card, card.previous.rect().center()).x()
    )
    assert (
        card.volume_button.mapTo(card, card.volume_button.rect().center()).x()
        > card.next_track.mapTo(card, card.next_track.rect().center()).x()
    )
    assert not card.volume_dropdown.isVisible()
    click = cast(Any, QTest.mouseClick)
    click(card.volume_button, Qt.MouseButton.LeftButton)
    assert card.volume_dropdown.isVisible()
    assert artwork_popup.rect().contains(card.volume_dropdown.geometry())
    click(card.volume, Qt.MouseButton.LeftButton)
    assert artwork_popup.isVisible() and not artwork_popup._is_closing
    click(card.title, Qt.MouseButton.LeftButton)
    assert not card.volume_dropdown.isVisible() and artwork_popup.isVisible()


def test_artwork_background_covers_card_and_is_cached_between_timeline_updates(
    artwork_popup: MediaSessionsPopup, qapp: QApplication
):
    from core.widgets.services.media.artwork import ArtworkMediaSessionCard

    card = artwork_popup.cards["chrome"]
    assert isinstance(card, ArtworkMediaSessionCard)
    card.state.thumbnail = Image.new("RGBA", (100, 100), "red")
    card.update_state(card.state)
    qapp.processEvents()
    assert card.surface.artwork is not None
    key = card.surface.artwork.cacheKey()
    image = card.surface.grab().toImage()  # synthetic offscreen widget, never the desktop
    for y in (5, card.surface.height() - 6):
        pixel = image.pixelColor(image.width() // 2, y)
        assert pixel.red() > 50 and pixel.green() < 10
    card.state.current_pos = 100
    card.update_state(card.state)
    assert card.surface.artwork.cacheKey() == key
    assert card.wave.clip.width() == round(card.wave.width() * 0.5)


def test_only_one_volume_dropdown_and_closing_or_removing_a_session_cleans_up(artwork_popup: MediaSessionsPopup):
    from core.widgets.services.media.artwork import ArtworkMediaSessionCard

    cards = list(artwork_popup.cards.values())
    assert all(isinstance(card, ArtworkMediaSessionCard) for card in cards)
    first, second = cast(list[ArtworkMediaSessionCard], cards)
    first.volume_button.click()
    assert first.volume_dropdown.isVisible()
    second.volume_button.click()
    assert not first.volume_dropdown.isVisible() and second.volume_dropdown.isVisible()
    artwork_popup.refresh({"chrome": first.state})
    assert not second.volume_dropdown.isVisible()
    first.volume_button.click()
    artwork_popup.hide()
    assert not first.volume_dropdown.isVisible()


def test_small_artwork_session_fits_popup_and_wave_ends_at_slider_handle(
    artwork_popup: MediaSessionsPopup, qapp: QApplication
):
    from core.widgets.services.media.artwork import ArtworkMediaSessionCard

    qapp.processEvents()
    artwork_popup._fit_content()
    qapp.processEvents()
    assert artwork_popup.width() == 380
    for card in artwork_popup.cards.values():
        assert isinstance(card, ArtworkMediaSessionCard)
        card.wave_track.fit_to_slider()
        surface = card.surface
        assert artwork_popup.rect().contains(
            surface.rect().translated(surface.mapTo(artwork_popup, surface.rect().topLeft()))
        )
        for child in [*surface.findChildren(QLabel), *surface.findChildren(QSlider)]:
            if child.isVisible():
                assert surface.rect().contains(child.rect().translated(child.mapTo(surface, child.rect().topLeft())))
        assert surface.height() <= 210
        assert card.wave.clip.width() == round(card.wave.width() * card.progress.value() / 1000)
        assert card.wave_track.rect().contains(card.progress.geometry())


def test_wave_palette_is_only_sampled_when_artwork_changes(
    artwork_popup: MediaSessionsPopup, monkeypatch: pytest.MonkeyPatch
):
    from core.widgets.services.media import artwork

    choose = Mock(wraps=artwork.choose_wave_palette)
    monkeypatch.setattr(artwork, "choose_wave_palette", choose)
    card = artwork_popup.cards["chrome"]
    card.update_state(card.state)
    card.update_state(card.state)
    choose.assert_not_called()
    card.state.thumbnail = Image.new("RGB", (30, 30), "orange")
    card.update_state(card.state)
    card.state.current_pos += 1
    card.update_state(card.state)
    choose.assert_called_once()
