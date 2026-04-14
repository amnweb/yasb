from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.ui.components.button import Button
from core.ui.theme import FONT_FAMILIES, get_tokens, theme_key
from core.utils.win32.backdrop import enable_blur

_WIDTH = 360
_PAD = 24
_BTN_SPACING = 8
_TITLE_MB = 12
_OPEN_MS = 167
_CLOSE_MS = 83
_FOCUS_LINE_H = 2


class _FocusLineEdit(QLineEdit):
    """QLineEdit with WinUI3 TextBox styling.

    Matches the three visual states from the WinUI3 TextBox XAML:
    - Rest: ControlFillColorDefault bg, bottom border = ControlStrongStroke
    - Hover: ControlFillColorSecondary bg
    - Focused: ControlFillColorInputActive bg, 2px accent line at bottom

    Border colours and backgrounds are set entirely via CSS from tokens.
    Only the focused 2px accent line is painted in paintEvent.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._focused = False
        self._accent_color = QColor()

    def set_accent_color(self, color: str) -> None:
        self._accent_color = QColor(color)
        self.update()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._focused = True
        self.update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._focused = False
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._focused:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = self.height() - _FOCUS_LINE_H
        pen = QPen(self._accent_color, _FOCUS_LINE_H)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(4, y, self.width() - 4, y)
        painter.end()


class InputDialog(QWidget):
    """Standalone input dialog using the UI design system.

    Appears as a top-level window at the cursor position with DWM blur
    and rounded corners. No smoke overlay.

    Usage::

        dlg = InputDialog(
            title="Rename",
            content="Enter a new name.",
            text="current value",
            primary_button_text="Save",
            close_button_text="Cancel",
        )
        dlg.accepted.connect(lambda text: print(text))
        dlg.show_dialog()
    """

    accepted = pyqtSignal(str)
    rejected = pyqtSignal()

    def __init__(
        self,
        title: str = "",
        content: str = "",
        text: str = "",
        placeholder: str = "",
        primary_button_text: str = "OK",
        close_button_text: str = "Cancel",
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowOpacity(0.0)
        self._is_closing = False
        self._theme_key = theme_key()
        self._anim: QPropertyAnimation | None = None

        # Root layout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._container = QWidget(self)
        self._container.setObjectName("id_bg")
        root.addWidget(self._container)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top section (title + content + input)
        self._top = QFrame(self._container)
        self._top.setObjectName("id_top")
        top_layout = QVBoxLayout(self._top)
        top_layout.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        top_layout.setSpacing(0)

        title_font = QFont()
        title_font.setFamilies(list(FONT_FAMILIES))
        title_font.setPixelSize(16)
        title_font.setWeight(QFont.Weight.DemiBold)
        self._title_label = QLabel(title, self._top)
        self._title_label.setFont(title_font)
        self._title_label.setWordWrap(True)
        self._title_label.setContentsMargins(0, 0, 0, _TITLE_MB)
        self._title_label.setVisible(bool(title))
        top_layout.addWidget(self._title_label)

        content_font = QFont()
        content_font.setFamilies(list(FONT_FAMILIES))
        content_font.setPixelSize(13)
        self._content_label = QLabel(content, self._top)
        self._content_label.setFont(content_font)
        self._content_label.setWordWrap(True)
        if content:
            self._content_label.setContentsMargins(0, 0, 0, 12)
        self._content_label.setVisible(bool(content))
        top_layout.addWidget(self._content_label)

        # Text input
        input_font = QFont()
        input_font.setFamilies(list(FONT_FAMILIES))
        input_font.setPixelSize(14)
        self._input = _FocusLineEdit(self._top)
        self._input.setFont(input_font)
        self._input.setText(text)
        self._input.setPlaceholderText(placeholder)
        self._input.selectAll()
        self._input.setFixedHeight(34)
        top_layout.addWidget(self._input)

        layout.addWidget(self._top)

        # Button bar
        self._btn_bar = QFrame(self._container)
        self._btn_bar.setObjectName("id_btns")
        btn_layout = QHBoxLayout(self._btn_bar)
        btn_layout.setContentsMargins(_PAD, _PAD, _PAD, _PAD)
        btn_layout.setSpacing(_BTN_SPACING)

        self._close_btn = Button(close_button_text, variant="default", parent=self._btn_bar)
        self._close_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._close_btn.setFixedHeight(32)
        self._close_btn.clicked.connect(self._on_close)
        btn_layout.addWidget(self._close_btn)

        self._primary_btn = Button(primary_button_text, variant="accent", parent=self._btn_bar)
        self._primary_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._primary_btn.setFixedHeight(32)
        self._primary_btn.clicked.connect(self._on_primary)
        btn_layout.addWidget(self._primary_btn)

        layout.addWidget(self._btn_bar)

        self.setFixedWidth(_WIDTH)
        self._container.setFixedWidth(_WIDTH)

        self._apply_styles()
        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    @property
    def text(self) -> str:
        return self._input.text()

    @property
    def input_widget(self) -> _FocusLineEdit:
        return self._input

    def show_dialog(self) -> None:
        self.adjustSize()
        self._container.adjustSize()
        pos = QCursor.pos()
        x = pos.x() - _WIDTH // 2
        y = pos.y() - self.height() // 2

        screen = QApplication.screenAt(pos)
        if screen is not None:
            geo = screen.availableGeometry()
            x = max(geo.x(), min(x, geo.x() + geo.width() - self.width()))
            y = max(geo.y(), min(y, geo.y() + geo.height() - self.height()))

        self.move(x, y)

        enable_blur(
            int(self.winId()),
            DarkMode=True,
            RoundCorners=True,
            RoundCornersType="normal",
            BorderColor="system",
        )

        self.show()
        self.activateWindow()
        self._input.setFocus()
        self._play_open()

    def hide_dialog(self) -> None:
        if self._is_closing:
            return
        self._is_closing = True
        self._play_close()

    def _play_open(self) -> None:
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(_OPEN_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim = anim
        anim.start()

    def _play_close(self) -> None:
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(_CLOSE_MS)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self._on_close_finished)
        self._anim = anim
        anim.start()

    def _on_close_finished(self) -> None:
        self.hide()
        self.close()

    def _on_primary(self) -> None:
        value = self._input.text().strip()
        if value:
            self.accepted.emit(value)
        self.hide_dialog()

    def _on_close(self) -> None:
        self.rejected.emit()
        self.hide_dialog()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._on_close()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_primary()
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
        self._container.setStyleSheet(f"#id_bg {{ background: {bg} }}")
        self._top.setStyleSheet(
            f"#id_top {{ background: {tokens['layer_alt']};"
            f" border-bottom: 1px solid {tokens['card_stroke_default']}; }}"
        )
        self._btn_bar.setStyleSheet(f"#id_btns {{ background: {bg}; }}")
        self._title_label.setStyleSheet(f"color: {tokens['text_primary']}")
        self._content_label.setStyleSheet(f"color: {tokens['text_secondary']}")
        self._input.setStyleSheet(
            f"QLineEdit {{ border: 1px solid transparent;"
            f" border-radius: 4px; background: {tokens['control_fill_default']};"
            f" color: {tokens['text_primary']}; padding: 4px 10px; }}"
            f" QLineEdit:hover {{ background: {tokens['control_fill_secondary']}; }}"
            f" QLineEdit:focus {{ background: {tokens['control_fill_input_active']};border: 1px solid {tokens['divider_stroke_default']} }}"
        )
        self._input.set_accent_color(tokens["accent_fill_default"])
