from collections.abc import Iterator

import pytest
from PyQt6.QtCore import QObject, QPoint, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication

from core.utils.utilities import wheel_delta
from core.validation.widgets.yasb.brightness import BrightnessConfig
from core.widgets.yasb import brightness as brightness_widget
from core.widgets.yasb.brightness import BrightnessWidget

# One notch of a standard mouse wheel
NOTCH = 120


def _wheel(x: int = 0, y: int = 0) -> QWheelEvent:
    return QWheelEvent(
        QPointF(),
        QPointF(),
        QPoint(),
        QPoint(x, y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def test_vertical_scroll_is_unchanged():
    assert wheel_delta(_wheel(y=NOTCH)) > 0
    assert wheel_delta(_wheel(y=-NOTCH)) < 0


def test_horizontal_scroll_right_increases():
    # Qt reports scrolling right as negative x
    assert wheel_delta(_wheel(x=-NOTCH)) > 0
    assert wheel_delta(_wheel(x=NOTCH)) < 0


def test_vertical_scroll_wins_when_both_move():
    assert wheel_delta(_wheel(x=-NOTCH, y=-NOTCH)) < 0


def test_invert_flips_both_directions():
    assert wheel_delta(_wheel(y=NOTCH), invert=True) < 0
    assert wheel_delta(_wheel(x=-NOTCH), invert=True) < 0


def test_no_movement_is_zero():
    assert wheel_delta(_wheel()) == 0


class _FakeService(QObject):
    """Stands in for BrightnessService, which starts threads that talk to real monitors."""

    brightness_changed = pyqtSignal(int, object)
    contrast_changed = pyqtSignal(int, object)

    @classmethod
    def instance(cls, ddc_poll_interval: int = 60) -> _FakeService:
        return cls()


class _FakeBrightness(BrightnessWidget):
    """Reads and writes a plain value instead of a monitor."""

    level = 50
    writes: list[int]

    def get_brightness(self) -> int | None:
        return self.level

    def set_brightness(self, value: int):
        self.writes.append(value)


@pytest.fixture
def brightness(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[_FakeBrightness]:
    monkeypatch.setattr(brightness_widget, "BrightnessService", _FakeService)
    widget = _FakeBrightness(BrightnessConfig.model_validate({"scroll_step": 5}))
    widget.writes = []
    yield widget
    widget.close()


def test_brightness_follows_horizontal_scroll(brightness: _FakeBrightness):
    brightness.wheelEvent(_wheel(x=-NOTCH))
    brightness.wheelEvent(_wheel(x=NOTCH))

    assert brightness.writes == [55, 45]


def test_brightness_ignores_scroll_without_movement(brightness: _FakeBrightness):
    # This used to lower the brightness
    brightness.wheelEvent(_wheel())

    assert brightness.writes == []
