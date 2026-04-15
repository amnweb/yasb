from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QRectF, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QApplication, QHBoxLayout, QLabel, QSizePolicy, QWidget

from core.ui.theme import get_tokens, theme_key

TRACK_W = 40
TRACK_H = 20
KNOB_MARGIN = 4
KNOB_RADIUS = (TRACK_H - KNOB_MARGIN * 2) / 2
_TRANSPARENT = QColor(0, 0, 0, 0)
_PROPS = ("knob_x", "track_color", "border_color", "knob_color", "knob_stretch")

# Token keys per checked state: (track, border, knob)
# None = transparent
_TOKEN_MAP = {
    True: ("accent_fill_default", None, "text_on_accent_primary"),
    False: (None, "control_strong_stroke_default", "text_primary"),
}


def _resolve(t: dict[str, str], key: str | None) -> QColor:
    return QColor(t[key]) if key else QColor(_TRANSPARENT)


class ToggleSwitch(QAbstractButton):
    """Custom toggle switch with animated transitions and theme reactivity."""

    _PAD = 1
    _PRESS_STRETCH = 3

    def __init__(
        self,
        checked: bool = False,
        label: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme_key = theme_key()
        self._build_colors(get_tokens())
        self._knob_x = float(TRACK_W - KNOB_MARGIN - KNOB_RADIUS * 2 if checked else KNOB_MARGIN)

        self._track_color = QColor(self._on_colors["track"] if checked else self._off_colors["track"])
        self._border_color = QColor(self._on_colors["border"] if checked else self._off_colors["border"])
        self._knob_color = QColor(self._on_colors["knob"] if checked else self._off_colors["knob"])
        self._knob_stretch = 0.0

        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(TRACK_W + self._PAD * 2, TRACK_H + self._PAD * 2)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._anim_group = QParallelAnimationGroup(self)
        for name in _PROPS:
            anim = QPropertyAnimation(self, name.encode())
            anim.setDuration(150)
            anim.setEasingCurve(QEasingCurve.Type.Linear)
            setattr(self, f"_anim_{name}", anim)
            self._anim_group.addAnimation(anim)

        if label is not None:
            self._label = label
        self.toggled.connect(self._on_toggled)
        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def _build_colors(self, t: dict[str, str]) -> None:
        self._on_colors = {
            "track": _resolve(t, _TOKEN_MAP[True][0]),
            "border": _resolve(t, _TOKEN_MAP[True][1]),
            "knob": _resolve(t, _TOKEN_MAP[True][2]),
        }
        self._off_colors = {
            "track": _resolve(t, _TOKEN_MAP[False][0]),
            "border": _resolve(t, _TOKEN_MAP[False][1]),
            "knob": _resolve(t, _TOKEN_MAP[False][2]),
        }

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._build_colors(get_tokens())
        self._anim_group.stop()
        colors = self._on_colors if self.isChecked() else self._off_colors
        self._track_color = QColor(colors["track"])
        self._border_color = QColor(colors["border"])
        self._knob_color = QColor(colors["knob"])
        self.update()

    # Animated properties

    @pyqtProperty(float)
    def knob_x(self) -> float:
        return self._knob_x

    @knob_x.setter
    def knob_x(self, value: float) -> None:
        self._knob_x = value
        self.update()

    @pyqtProperty(QColor)
    def track_color(self) -> QColor:
        return self._track_color

    @track_color.setter
    def track_color(self, value: QColor) -> None:
        self._track_color = value
        self.update()

    @pyqtProperty(QColor)
    def border_color(self) -> QColor:
        return self._border_color

    @border_color.setter
    def border_color(self, value: QColor) -> None:
        self._border_color = value
        self.update()

    @pyqtProperty(QColor)
    def knob_color(self) -> QColor:
        return self._knob_color

    @knob_color.setter
    def knob_color(self, value: QColor) -> None:
        self._knob_color = value
        self.update()

    @pyqtProperty(float)
    def knob_stretch(self) -> float:
        return self._knob_stretch

    @knob_stretch.setter
    def knob_stretch(self, value: float) -> None:
        self._knob_stretch = value
        self.update()

    def _on_toggled(self, checked: bool) -> None:
        on, off = self._on_colors, self._off_colors
        self._anim_group.stop()

        self._anim_knob_x.setStartValue(self._knob_x)
        self._anim_knob_x.setEndValue(float(TRACK_W - KNOB_MARGIN - KNOB_RADIUS * 2) if checked else float(KNOB_MARGIN))

        self._anim_track_color.setStartValue(self._track_color)
        self._anim_track_color.setEndValue(on["track"] if checked else off["track"])

        self._anim_border_color.setStartValue(self._border_color)
        self._anim_border_color.setEndValue(on["border"] if checked else off["border"])

        self._anim_knob_color.setStartValue(self._knob_color)
        self._anim_knob_color.setEndValue(on["knob"] if checked else off["knob"])

        self._anim_knob_stretch.setStartValue(self._knob_stretch)
        self._anim_knob_stretch.setEndValue(0.0)

        self._anim_group.start()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._knob_stretch = float(self._PRESS_STRETCH)
            self._stretch_left = self.isChecked()
            self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._knob_stretch > 0:
            self.setChecked(not self.isChecked())

    def paintEvent(self, _event) -> None:
        pad = self._PAD
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track
        track_rect = QRectF(pad, pad, TRACK_W, TRACK_H)
        p.setPen(QPen(self._border_color, 1.5))
        p.setBrush(self._track_color)
        p.drawRoundedRect(track_rect, TRACK_H / 2, TRACK_H / 2)

        # Knob
        knob_y = pad + KNOB_MARGIN
        knob_w = KNOB_RADIUS * 2 + self._knob_stretch
        knob_h = KNOB_RADIUS * 2
        knob_x = pad + self._knob_x
        if self._knob_stretch > 0 and getattr(self, "_stretch_left", False):
            knob_x -= self._knob_stretch

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._knob_color)
        p.drawRoundedRect(QRectF(knob_x, knob_y, knob_w, knob_h), knob_h / 2, knob_h / 2)

        p.end()


class ToggleSwitchWithLabel(QWidget):
    """Toggle switch with a text label. Exposes toggled signal.

    Args:
        text: Static label text. Ignored when *on_text*/*off_text* are set.
        on_text: Label shown when the switch is **on**.
        off_text: Label shown when the switch is **off**.
        checked: Initial state.
        parent: Parent widget.
    """

    def __init__(
        self,
        text: str = "",
        checked: bool = False,
        on_text: str | None = None,
        off_text: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_text = on_text
        self._off_text = off_text

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.switch = ToggleSwitch(checked=checked, parent=self)

        self._label: QLabel | None = None
        if on_text is not None and off_text is not None:
            self._label = QLabel(on_text if checked else off_text)
            self._label.setProperty("class", "body")
            layout.addWidget(self._label)
            self.switch.toggled.connect(self._update_label)
        elif text:
            self._label = QLabel(text)
            self._label.setProperty("class", "body")
            layout.addWidget(self._label)

        layout.addWidget(self.switch)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.toggled = self.switch.toggled

    def _update_label(self, checked: bool) -> None:
        if self._label and self._on_text is not None and self._off_text is not None:
            self._label.setText(self._on_text if checked else self._off_text)

    def isChecked(self) -> bool:
        return self.switch.isChecked()

    def setChecked(self, value: bool) -> None:
        self.switch.setChecked(value)
