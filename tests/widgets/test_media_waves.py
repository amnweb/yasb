# pyright: reportPrivateUsage=false

from typing import Any, cast

import pytest
from PIL import Image
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.widgets.services.media.waves import LayeredWaveCanvas, choose_wave_palette, wave_profile


@pytest.mark.parametrize(
    "color, expected",
    [
        ("#379cff", "blue"),
        ("#24d8d0", "cyan"),
        ("#ed9900", "orange"),
        ("#50bb75", "green"),
        ("#000000", "blue"),
        ("#eeeeee", "blue"),
    ],
)
def test_palette_uses_only_the_four_fixed_choices(color: str, expected: str):
    assert choose_wave_palette(Image.new("RGB", (100, 100), color)) == expected
    assert choose_wave_palette(None) == "blue"


def test_layer_shapes_are_smooth_distinct_and_taper_at_the_playback_marker():
    profiles: list[list[float]] = []
    for layer in range(3):
        values = [wave_profile(index / 48, layer, 0.8, 0.5) for index in range(49)]
        assert values[0] == values[-1] == 0
        assert all(0 <= value <= 1 for value in values)
        assert max(values) > 0.25
        assert max(abs(a - b) for a, b in zip(values, values[1:])) < 0.15
        profiles.append(values)
    assert profiles[0] != profiles[1] != profiles[2]


def test_wave_paint_has_three_cached_gradients_and_visible_color_variation(qapp: QApplication):
    canvas = LayeredWaveCanvas(200, 28)
    try:
        canvas.set_palette("orange")
        canvas.set_samples([0.4] * 80)
        canvas.show()
        qapp.processEvents()
        brushes = canvas._brushes()
        assert len(brushes) == 3 and canvas._brushes() is brushes
        image = canvas.grab().toImage()  # generated offscreen canvas, no desktop capture
        colors = {image.pixelColor(x, y).rgb() for x in range(20, 180, 3) for y in range(8, 27)}
        assert len(colors) > 20
        canvas.set_palette("cyan")
        assert canvas._brushes() is not brushes
        assert canvas.palette_name == "cyan"
    finally:
        canvas.hide()
        canvas.deleteLater()


def test_wave_animates_without_progress_or_new_audio_and_stops_when_hidden(qapp: QApplication):
    canvas = LayeredWaveCanvas(200, 28)
    ticks: list[bool] = []
    wait = cast(Any, QTest.qWait)  # PyQt6's stub incorrectly marks static QTest helpers as instance methods.

    def tick() -> None:
        ticks.append(True)

    canvas._animation_timer.timeout.connect(tick)
    try:
        canvas.set_samples([0.4] * 80)
        canvas.show()
        qapp.processEvents()
        assert canvas._animation_timer.isActive()
        first = canvas.grab().toImage()
        wait(160)
        second = canvas.grab().toImage()
        assert len(ticks) >= 5
        assert first != second
        assert 0 < canvas._energy <= canvas._target_energy
        canvas.hide()
        assert not canvas._animation_timer.isActive()
        count = len(ticks)
        wait(40)
        assert len(ticks) == count
    finally:
        canvas.hide()
        canvas.deleteLater()
