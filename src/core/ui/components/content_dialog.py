from enum import IntEnum

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.ui.components.button import Button
from core.ui.theme import FONT_FAMILIES, get_tokens, theme_key
from core.utils.win32.backdrop import enable_blur

_MIN_W, _MAX_W = 320, 548
_MIN_H, _MAX_H = 184, 756
_PAD = 24
_BTN_SPACING = 8
_TITLE_MB = 12
_OPEN_OPACITY_MS = 167
_OPEN_SLIDE_MS = 250
_CLOSE_MS = 83
_SLIDE_OFFSET = 10


class ContentDialogResult(IntEnum):
    NONE = 0
    PRIMARY = 1
    SECONDARY = 2


class ContentDialogButton(IntEnum):
    NONE = 0
    PRIMARY = 1
    SECONDARY = 2
    CLOSE = 3


class _SmokeLayer(QWidget):
    """Semi-transparent overlay on the parent."""

    clicked = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._opacity = 0.0

    @pyqtProperty(float)
    def smoke_opacity(self) -> float:
        return self._opacity

    @smoke_opacity.setter
    def smoke_opacity(self, value: float) -> None:
        self._opacity = value
        self.update()

    def paintEvent(self, _event) -> None:
        if self._opacity > 0:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(0, 0, 0, int(76 * self._opacity)))
            painter.end()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        event.accept()


class ContentDialog(QWidget):
    """ContentDialog using DWM blur for shadow and rounded corners.

    Usage::

        dlg = ContentDialog(
            parent=parent_widget,
            title="Save your work?",
            content="Unsaved changes will be lost.",
            primary_button_text="Save",
            secondary_button_text="Don't Save",
            close_button_text="Cancel",
            default_button=ContentDialogButton.PRIMARY,
        )
        dlg.primary_button_click.connect(on_save)
        dlg.show_dialog()
    """

    primary_button_click = pyqtSignal()
    secondary_button_click = pyqtSignal()
    close_button_click = pyqtSignal()
    opened = pyqtSignal()
    closed = pyqtSignal(ContentDialogResult)

    def __init__(
        self,
        parent: QWidget,
        title: str = "",
        content: str = "",
        primary_button_text: str = "",
        secondary_button_text: str = "",
        close_button_text: str = "",
        default_button: ContentDialogButton = ContentDialogButton.NONE,
    ) -> None:
        super().__init__(
            parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.0)
        self._result = ContentDialogResult.NONE
        self._default_button = default_button
        self._is_closing = False
        self._host = parent
        self._smoke: _SmokeLayer | None = None
        self._natural_w = _MIN_W
        self._natural_h = _MIN_H
        self._center_y = 0
        self._theme_key = theme_key()
        self._anim: QParallelAnimationGroup | None = None
        self._slide_offset_val = 0

        # Root layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._container = QWidget(self)
        self._container.setObjectName("cd_bg")
        root_layout.addWidget(self._container)

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Top section (title + body)
        self._top = QFrame(self._container)
        self._top.setObjectName("cd_top")
        top_layout = QVBoxLayout(self._top)
        top_layout.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        top_layout.setSpacing(0)

        title_font = QFont()
        title_font.setFamilies(list(FONT_FAMILIES))
        title_font.setPixelSize(20)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title_label = QLabel(title, self._top)
        self._title_label.setFont(title_font)
        self._title_label.setWordWrap(True)
        self._title_label.setContentsMargins(0, 0, 0, _TITLE_MB)
        self._title_label.setVisible(bool(title))
        top_layout.addWidget(self._title_label)

        content_font = QFont()
        content_font.setFamilies(list(FONT_FAMILIES))
        content_font.setPixelSize(14)
        self._content_label = QLabel(content, self._top)
        self._content_label.setFont(content_font)
        self._content_label.setWordWrap(True)
        self._content_label.setVisible(bool(content))
        top_layout.addWidget(self._content_label)

        self._custom_content: QWidget | None = None
        self._content_slot = QVBoxLayout()
        self._content_slot.setContentsMargins(0, 0, 0, 0)
        top_layout.addLayout(self._content_slot)

        top_layout.addStretch(1)
        container_layout.addWidget(self._top, 1)

        # Button bar
        self._btn_bar = QFrame(self._container)
        self._btn_bar.setObjectName("cd_btns")
        btn_layout = QHBoxLayout(self._btn_bar)
        btn_layout.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        btn_layout.setSpacing(_BTN_SPACING)

        self._primary_btn = self._secondary_btn = self._close_btn = None
        for text, attr, button_id in [
            (primary_button_text, "_primary_btn", ContentDialogButton.PRIMARY),
            (secondary_button_text, "_secondary_btn", ContentDialogButton.SECONDARY),
            (close_button_text, "_close_btn", ContentDialogButton.CLOSE),
        ]:
            if not text:
                continue
            variant = "accent" if default_button == button_id else "default"
            btn = Button(text, variant=variant, parent=self._btn_bar)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(32)
            setattr(self, attr, btn)
            btn_layout.addWidget(btn)

        if self._primary_btn:
            self._primary_btn.clicked.connect(self._on_primary)
        if self._secondary_btn:
            self._secondary_btn.clicked.connect(self._on_secondary)
        if self._close_btn:
            self._close_btn.clicked.connect(self._on_close)

        self._btn_bar.setVisible(bool(primary_button_text or secondary_button_text or close_button_text))
        container_layout.addWidget(self._btn_bar, 0)

        self.setMinimumSize(_MIN_W, _MIN_H)
        self.setMaximumSize(_MAX_W, _MAX_H)
        self._container.setMinimumSize(_MIN_W, _MIN_H)
        self._container.setMaximumSize(_MAX_W, _MAX_H)

        self._apply_styles()
        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def set_title(self, text: str) -> None:
        self._title_label.setText(text)
        self._title_label.setVisible(bool(text))

    def set_content(self, text: str) -> None:
        self._content_label.setText(text)
        self._content_label.setVisible(bool(text))

    def set_content_widget(self, widget: QWidget) -> None:
        if self._custom_content is not None:
            self._content_slot.removeWidget(self._custom_content)
            self._custom_content.setParent(None)
        self._custom_content = widget
        self._content_label.setVisible(False)
        self._content_slot.addWidget(widget)

    @property
    def result(self) -> ContentDialogResult:
        return self._result

    @property
    def primary_button(self) -> Button | None:
        return self._primary_btn

    @property
    def secondary_button(self) -> Button | None:
        return self._secondary_btn

    @property
    def close_button(self) -> Button | None:
        return self._close_btn

    def _compute_size(self) -> None:
        """Compute dialog width from unwrapped text, then height from wrapped text via QFontMetrics."""
        # Width: temporarily unwrap to get natural single-line width
        self._content_label.setWordWrap(False)
        self._title_label.setWordWrap(False)
        unwrapped_hint = self._container.sizeHint()
        self._content_label.setWordWrap(True)
        self._title_label.setWordWrap(True)
        self._natural_w = min(max(unwrapped_hint.width(), _MIN_W), _MAX_W)

        # Height: measure wrapped text with QFontMetrics.boundingRect
        label_w = self._natural_w - _PAD * 2
        wrap_flags = Qt.TextFlag.TextWordWrap
        top_h = _PAD
        if self._title_label.text():
            title_rect = self._title_label.fontMetrics().boundingRect(
                QRect(0, 0, label_w, 0), wrap_flags, self._title_label.text()
            )
            top_h += title_rect.height() + _TITLE_MB
        if self._content_label.text():
            content_rect = self._content_label.fontMetrics().boundingRect(
                QRect(0, 0, label_w, 0), wrap_flags, self._content_label.text()
            )
            top_h += content_rect.height()
        top_h += _PAD
        btn_h = self._btn_bar.sizeHint().height()
        self._natural_h = min(max(top_h + btn_h, _MIN_H), _MAX_H)

        self.setFixedSize(self._natural_w, self._natural_h)
        self._container.setFixedSize(self._natural_w, self._natural_h)

    def show_dialog(self) -> None:
        parent = self._host

        self._smoke = _SmokeLayer(parent)
        self._smoke.setGeometry(parent.rect())
        self._smoke.show()
        self._smoke.raise_()
        parent.installEventFilter(self)

        self._compute_size()
        self._position_center(0)

        enable_blur(
            int(self.winId()),
            DarkMode=True,
            RoundCorners=True,
            RoundCornersType="normal",
            BorderColor="system",
        )

        self.show()
        self.activateWindow()
        self._play_open()

    def hide_dialog(self) -> None:
        if self._is_closing:
            return
        self._is_closing = True
        self._play_close()

    @pyqtProperty(int)
    def slide_offset(self) -> int:
        return self._slide_offset_val

    @slide_offset.setter
    def slide_offset(self, value: int) -> None:
        self._slide_offset_val = value
        self._position_center(value)

    def _position_center(self, y_offset: int = 0) -> None:
        if self._host is None:
            return
        centre = self._host.mapToGlobal(self._host.rect().center())
        x = centre.x() - self._natural_w // 2
        y = centre.y() - self._natural_h // 2 + y_offset
        self.move(x, y)
        self._center_y = centre.y() - self._natural_h // 2

    def eventFilter(self, obj, event) -> bool:
        if obj is self._host and event.type() == QEvent.Type.Resize:
            if self._smoke:
                self._smoke.setGeometry(self._host.rect())
            self._position_center(0)
        return super().eventFilter(obj, event)

    def _play_open(self) -> None:
        group = QParallelAnimationGroup(self)

        slide_anim = QPropertyAnimation(self, b"slide_offset")
        slide_anim.setDuration(_OPEN_SLIDE_MS)
        slide_anim.setStartValue(_SLIDE_OFFSET)
        slide_anim.setEndValue(0)
        slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(slide_anim)

        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(_OPEN_OPACITY_MS)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        group.addAnimation(opacity_anim)

        smoke_anim = QPropertyAnimation(self._smoke, b"smoke_opacity")
        smoke_anim.setDuration(_OPEN_OPACITY_MS)
        smoke_anim.setStartValue(0.0)
        smoke_anim.setEndValue(1.0)
        group.addAnimation(smoke_anim)

        group.finished.connect(self.opened.emit)
        self._anim = group
        group.start()

    def _play_close(self) -> None:
        group = QParallelAnimationGroup(self)

        opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(_CLOSE_MS)
        opacity_anim.setStartValue(1.0)
        opacity_anim.setEndValue(0.0)
        group.addAnimation(opacity_anim)

        smoke_anim = QPropertyAnimation(self._smoke, b"smoke_opacity")
        smoke_anim.setDuration(_CLOSE_MS)
        smoke_anim.setStartValue(1.0)
        smoke_anim.setEndValue(0.0)
        group.addAnimation(smoke_anim)

        group.finished.connect(self._on_close_finished)
        self._anim = group
        group.start()

    def _on_close_finished(self) -> None:
        if self._host:
            self._host.removeEventFilter(self)
        if self._smoke:
            self._smoke.hide()
            self._smoke.setParent(None)
            self._smoke = None
        self.closed.emit(self._result)
        self.hide()
        self._is_closing = False

    def _on_primary(self) -> None:
        self._result = ContentDialogResult.PRIMARY
        self.primary_button_click.emit()
        self.hide_dialog()

    def _on_secondary(self) -> None:
        self._result = ContentDialogResult.SECONDARY
        self.secondary_button_click.emit()
        self.hide_dialog()

    def _on_close(self) -> None:
        self._result = ContentDialogResult.NONE
        self.close_button_click.emit()
        self.hide_dialog()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._on_close()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            match self._default_button:
                case ContentDialogButton.PRIMARY if self._primary_btn:
                    self._on_primary()
                case ContentDialogButton.SECONDARY if self._secondary_btn:
                    self._on_secondary()
                case ContentDialogButton.CLOSE if self._close_btn:
                    self._on_close()
        else:
            super().keyPressEvent(event)

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._apply_styles()

    def _apply_styles(self) -> None:
        tokens = get_tokens()
        bg = tokens["solid_bg_base"]
        self._container.setStyleSheet(f"#cd_bg {{ background: {bg} }}")
        self._top.setStyleSheet(
            f"#cd_top {{ background: {tokens['layer_alt']}; border-bottom: 1px solid {tokens['card_stroke_default']}; }}"
        )
        self._btn_bar.setStyleSheet(f"#cd_btns {{ background: {bg}; }}")
        self._title_label.setStyleSheet(f"color: {tokens['text_primary']}")
        self._content_label.setStyleSheet(f"color: {tokens['text_primary']}")
