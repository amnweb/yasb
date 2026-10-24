# pyright: reportPrivateUsage=false

import time

import pytest
from PyQt6.QtWidgets import QApplication, QWidget

from core.validation.widgets.yasb.lyrics import LyricsWidgetConfig
from core.widgets.services.lyrics.engine import SyncEngine
from core.widgets.services.lyrics.lyrics_popup import LyricsPopup, PopupProgressBar, _wave_profile
from core.widgets.services.lyrics.models import Hit, Line, Lyrics, Word
from core.widgets.services.lyrics.session import PlaybackSnapshot, TrackInfo


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def test_popup_progress_bar_styles(qapp: QApplication) -> None:
    bar = PopupProgressBar()
    assert bar._style == "line"
    assert bar.height() == bar._LINE_HEIGHT

    bar.set_style("wave")
    assert bar._style == "wave"
    assert bar.height() == bar._WAVE_HEIGHT
    assert bar._pad == bar._WAVE_THUMB_R + 2.0


def test_popup_duration_fallback_and_progress(qapp: QApplication) -> None:
    cfg = LyricsWidgetConfig()
    popup = LyricsPopup(QWidget(), cfg)
    engine = SyncEngine()

    track = TrackInfo(title="Blinding Lights", artist="The Weeknd", duration_ms=None)
    snap = PlaybackSnapshot(position_ms=105000, rate=1.0, status="playing", wall_time=time.time())
    engine.update_snapshot(snap)

    lyrics = Lyrics(
        lines=[Line(start_ms=0, end_ms=5000, text="test"), Line(start_ms=190000, end_ms=194430, text="outro")]
    )
    hit = Hit(
        source="LrcLib",
        trust=50,
        lyrics=lyrics,
        instrumental=False,
        title="Blinding Lights",
        artist="The Weeknd",
        duration_s=200.0,
    )

    popup.sync_data(track=track, hits=[hit], hit_index=0, active_lyrics=lyrics, engine=engine, state="synced")

    assert popup._resolve_duration() == 200000
    assert popup._total_label.text() == "3:20"
    assert abs(popup._progress_bar._fraction - (105000 / 200000)) < 1e-4
    assert popup._progress_bar._seekable is True


def test_popup_duration_fallback_to_span_when_no_duration_s(qapp: QApplication) -> None:
    cfg = LyricsWidgetConfig()
    popup = LyricsPopup(QWidget(), cfg)
    engine = SyncEngine()

    track = TrackInfo(title="Unknown Track", artist="Unknown", duration_ms=None)
    snap = PlaybackSnapshot(position_ms=60000, rate=1.0, status="playing", wall_time=time.time())
    engine.update_snapshot(snap)

    lyrics = Lyrics(
        lines=[Line(start_ms=0, end_ms=5000, text="test"), Line(start_ms=180000, end_ms=185000, text="outro")]
    )
    hit = Hit(
        source="LrcLib",
        trust=50,
        lyrics=lyrics,
        instrumental=False,
        title="Unknown Track",
        artist="Unknown",
        duration_s=None,
    )

    popup.sync_data(track=track, hits=[hit], hit_index=0, active_lyrics=lyrics, engine=engine, state="synced")

    assert popup._resolve_duration() == 185000
    assert popup._total_label.text() == "3:05"
    assert abs(popup._progress_bar._fraction - (60000 / 185000)) < 1e-4
    assert popup._progress_container.isHidden() is False
    assert popup._progress_bar.isHidden() is False


def test_popup_hides_progress_bar_when_duration_fails_all_attempts(qapp: QApplication) -> None:
    cfg = LyricsWidgetConfig()
    popup = LyricsPopup(QWidget(), cfg)
    popup.show()
    engine = SyncEngine()

    track = TrackInfo(title="Live Stream", artist="Radio", duration_ms=None)
    snap = PlaybackSnapshot(position_ms=12000, rate=1.0, status="playing", wall_time=time.time())
    engine.update_snapshot(snap)

    popup.sync_data(track=track, hits=[], hit_index=0, active_lyrics=None, engine=engine, state="not-found")

    assert popup._resolve_duration() == 0
    assert popup._progress_container.isHidden() is True
    assert popup._progress_bar.isHidden() is True
    assert popup._progress_container.isVisible() is False
    assert popup._progress_bar.isVisible() is False


def test_wave_travels_forward_and_dies_down() -> None:
    for layer in range(3):
        assert _wave_profile(0.0, 1.5, layer) == 0.0
        assert _wave_profile(1.0, 1.5, layer) == 0.0

    t0_samples = [_wave_profile(u / 200, 0.0, 0) for u in range(201)]
    t1_samples = [_wave_profile(u / 200, 0.3, 0) for u in range(201)]

    peak0 = max(range(len(t0_samples)), key=lambda i: t0_samples[i])
    peak1 = max(range(len(t1_samples)), key=lambda i: t1_samples[i])
    assert peak1 > peak0

    mid_avg = sum(_wave_profile(0.4, p * 0.1, 0) for p in range(50)) / 50.0
    front_avg = sum(_wave_profile(0.95, p * 0.1, 0) for p in range(50)) / 50.0
    assert front_avg < mid_avg * 0.25


def test_lyrics_full_width_wrapping(qapp: QApplication) -> None:
    cfg = LyricsWidgetConfig()
    cfg.popup.width = 950
    popup = LyricsPopup(QWidget(), cfg)
    popup.show()

    text = "Y tú no ve' que lo hago porque te amo"
    words = [Word(i * 100, (i + 1) * 100, w + " ") for i, w in enumerate(text.split())]
    line = Line(start_ms=0, end_ms=5000, text=text, words=words)
    lyrics = Lyrics(lines=[line])
    engine = SyncEngine()
    engine.set_lyrics(lyrics, total_duration_ms=60000)
    track = TrackInfo(title="Test", artist="Artist", duration_ms=60000)

    popup.sync_data(track=track, hits=[], hit_index=0, active_lyrics=lyrics, engine=engine, state="synced")

    assert len(popup._row_widgets) >= 1
    row_w = popup._row_widgets[0]
    expected_wrap = max(180, min(926 - 48, int((926 - 16) * 0.88)))
    assert row_w.wrap_width == expected_wrap
    assert len(row_w._sub_lines) == 1, f"Expected 1 line but got: {row_w._sub_lines}"
    assert row_w._sub_lines[0][0] == text


def test_lyrics_balanced_wrapping_algorithms(qapp: QApplication) -> None:
    from PyQt6.QtGui import QFont, QFontMetrics

    from core.widgets.services.lyrics.lyrics_popup import wrap_karaoke_words, wrap_plain_text

    f = QFont()
    f.setPointSizeF(13.0)
    fm = QFontMetrics(f)

    long_text = "De estar en la línea de fuego y de meter la mano"
    words = [Word(i * 100, (i + 1) * 100, w + " ") for i, w in enumerate(long_text.split())]

    total_w = fm.horizontalAdvance(long_text)
    max_w = int(total_w * 0.58)

    k_lines = wrap_karaoke_words(long_text, words, max_w, fm)
    p_lines = wrap_plain_text(long_text, max_w, fm)

    assert len(k_lines) == 2, f"Expected 2 karaoke lines, got: {k_lines}"
    assert len(p_lines) == 2, f"Expected 2 plain lines, got: {p_lines}"
    assert len(k_lines[0][1]) > 1
    assert len(k_lines[1][1]) > 1
    assert len(p_lines[0].split()) > 1
    assert len(p_lines[1].split()) > 1


def test_karaoke_label_scale_clamping(qapp: QApplication) -> None:
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QPainter, QPixmap

    from core.widgets.services.lyrics.karaoke_label import KaraokeLabel

    label = KaraokeLabel()
    label.resize(300, 40)
    label.setText("Sample lyric line that is long")

    pixmap = QPixmap(300, 40)
    painter = QPainter(pixmap)
    rect = QRectF(0, 0, 300, 40)

    label._paint_layer(
        painter,
        rect=rect,
        text="Sample lyric line that is long",
        words=None,
        total_w=280.0,
        wipe_x=0.0,
        karaoke_enabled=False,
        dx=0.0,
        dy=0.0,
        scale=2.0,
        opacity=1.0,
        clip_rect=None,
    )
    painter.end()
