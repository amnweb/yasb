# pyright: reportPrivateUsage=false

import math
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.services.audio_visualizer import levels as levels_module
from core.services.audio_visualizer.levels import AudioLevels
from core.services.audio_visualizer.spectrum import FFT_SIZE, SpectrumSource
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import wait

# A loud mix of a low and a high tone
TONE = SpectrumSource().magnitudes([0.6 * math.sin(i * 0.05) + 0.3 * math.sin(i * 0.9) for i in range(FFT_SIZE)])


class FakeCaptureService(QObject):
    frame_ready = pyqtSignal()
    audio_started = pyqtSignal()
    audio_stopped = pyqtSignal()
    format_changed = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.sample_rate = 48000
        self.is_active = False
        self.calls: list[tuple[Any, ...]] = []

    def attach(self, framerate: int, channels: frozenset[str]) -> None:
        self.calls.append(("attach", framerate, channels))

    def detach(self, framerate: int, channels: frozenset[str], visible: bool) -> None:
        self.calls.append(("detach", framerate, channels, visible))

    def set_reader_visible(self, visible: bool) -> None:
        self.calls.append(("visible", visible))

    def magnitudes(self, _channel: str) -> list[float]:
        return TONE if self.is_active else [0.0] * len(TONE)

    def play(self, frames: int = 20) -> None:
        self.is_active = True
        self.audio_started.emit()
        for _ in range(frames):
            self.frame_ready.emit()
            wait(17)

    def stop(self) -> None:
        self.is_active = False
        self.audio_stopped.emit()


@pytest.fixture
def capture(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> FakeCaptureService:
    service = FakeCaptureService()
    sources: list[str] = []

    class Capture:
        @staticmethod
        def instance(source: str = "auto") -> FakeCaptureService:
            sources.append(source)
            return service

    monkeypatch.setattr(levels_module, "AudioVisualizerCaptureService", Capture)
    service.sources = sources  # type: ignore[attr-defined]
    return service


def make_levels(**options: Any) -> AudioLevels:
    levels = AudioLevels()
    for name, value in options.items():
        levels.setProperty(name, value)
    wait(5)
    return levels


def test_options_set_after_creation_start_one_claim(capture: FakeCaptureService):
    levels = make_levels(source="Speakers", bands=32, monoChannel="left", framerate=30)
    assert capture.sources == ["Speakers"]  # type: ignore[attr-defined]
    assert capture.calls == [("attach", 30, frozenset({"left"}))]
    assert levels.property("levels") == [0.0] * 32
    sip.delete(levels)
    assert capture.calls[-1] == ("detach", 30, frozenset({"left"}), True)


def test_audio_raises_the_bands_and_silence_walks_them_back_down(capture: FakeCaptureService):
    levels = make_levels(bands=24, idleAfter=100)
    assert not levels.property("playing")
    capture.play()
    playing = levels.property("levels")
    assert levels.property("playing")
    assert len(playing) == 24 and max(playing) > 0.3 and all(0 <= value <= 1 for value in playing)

    capture.stop()
    wait(1500)
    assert levels.property("levels") == [0.0] * 24
    assert not levels.property("playing")


def test_stereo_splits_the_bands_and_mirrors_the_left_half(capture: FakeCaptureService):
    levels = make_levels(bands=25, stereo=True)
    assert capture.calls == [("attach", 60, frozenset({"left", "right"}))]
    capture.play()
    values = levels.property("levels")
    # 13 left bands, highs to bass, then 12 right bands, bass to highs
    assert len(values) == 25
    assert values[12] == pytest.approx(values[13], abs=0.05)


def test_reverse_flips_mono(capture: FakeCaptureService):
    normal = make_levels(bands=16)
    flipped = make_levels(bands=16, reverse=True)
    capture.play()
    assert flipped.property("levels") == pytest.approx(list(reversed(normal.property("levels"))), abs=0.05)


def test_off_screen_stops_the_analysis_but_still_reports_playing(capture: FakeCaptureService):
    levels = make_levels(bands=8)
    capture.play(frames=5)
    levels.setProperty("running", False)
    assert capture.calls[-1] == ("visible", False)
    assert levels.property("levels") == [0.0] * 8
    capture.play(frames=5)
    assert levels.property("levels") == [0.0] * 8
    assert levels.property("playing")


def test_changing_an_option_claims_the_stream_again(capture: FakeCaptureService):
    levels = make_levels(bands=8)
    levels.setProperty("stereo", True)
    wait(5)
    assert capture.calls == [
        ("attach", 60, frozenset({"average"})),
        ("detach", 60, frozenset({"average"}), True),
        ("attach", 60, frozenset({"left", "right"})),
    ]
    assert len(levels.property("levels")) == 8


def load_widget(**options: Any) -> tuple[QQuickItem, QQuickWindow, list[str], QQmlEngine]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect)
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "AudioVisualizer" / "AudioVisualizer.qml"))
    )
    # Set here rather than taken from the widget's defaults, which are free to change
    initial: dict[str | None, Any] = {
        "graphHeight": 14,
        "hideIdle": False,
        "mirror": False,
        "barCount": 24,
        "barWidth": 2,
        "barGap": 4,
        "dotCount": 24,
        "dotSize": 2,
        "dotGap": 4,
        "waveWidth": 80,
        **options,
    }
    widget = component.createWithInitialProperties(initial)
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    window = QQuickWindow()
    widget.setParentItem(window.contentItem())
    wait(10)
    return widget, window, warnings, engine


def class_name(item: QObject) -> str:
    meta = item.metaObject()
    return (meta.className() or "") if meta is not None else ""


def drawn(widget: QQuickItem) -> list[QQuickItem]:
    """The bars, or the dot columns, inside the graph."""
    [graph] = [item for item in widget.childItems() if item.width() > 0]
    return [
        item for item in graph.childItems() if class_name(item).startswith(("QQuickRectangle_QML", "QQuickItem_QML"))
    ]


@pytest.mark.parametrize(
    ("style", "width"), [("bars", 24 * 6), ("dots", 24 * 6), ("waves", 80)], ids=["bars", "dots", "waves"]
)
def test_every_style_draws_without_warnings(capture: FakeCaptureService, style: str, width: int):
    widget, window, warnings, _engine = load_widget(style=style, edgeFade=[8, 4], mirror=True)
    assert widget.property("implicitWidth") == width
    assert widget.property("implicitHeight") == 14
    capture.play(frames=5)
    if style == "waves":
        [outline] = [child for child in widget.findChildren(QObject) if class_name(child) == "QQuickPathSvg"]
        # A closed outline curving through the 16 points of an 80 pixel wave, top and mirrored bottom
        path = outline.property("path")
        assert path.startswith("M0 ") and path.count("Q") == 2 * 15 and path.endswith(" Z ")
    else:
        assert len(drawn(widget)) == 24
    assert not warnings
    sip.delete(widget)
    sip.delete(window)


def test_bars_follow_the_levels_on_whole_physical_pixels(capture: FakeCaptureService):
    widget, window, warnings, _engine = load_widget(barCount=8, barWidth=2, barGap=2)
    bars = drawn(widget)
    assert [bar.x() for bar in bars] == [1, 5, 9, 13, 17, 21, 25, 29]
    assert {bar.height() for bar in bars} == {1}  # a resting line while silent
    capture.play()
    assert max(bar.height() for bar in bars) > 4
    assert all(bar.y() + bar.height() == 14 for bar in bars)
    assert not warnings
    sip.delete(widget)
    sip.delete(window)


def test_hide_idle_takes_no_space_until_audio_plays(capture: FakeCaptureService):
    widget, window, _, _engine = load_widget(hideIdle=True, hideIdleAfter=100)
    assert widget.property("implicitWidth") == 0 and not widget.isVisible()
    assert capture.calls[-1] == ("visible", False)
    capture.play(frames=2)
    assert widget.property("implicitWidth") == 24 * 6
    capture.stop()
    wait(300)
    assert widget.property("implicitWidth") == 0 and not widget.isVisible()
    sip.delete(widget)
    sip.delete(window)
