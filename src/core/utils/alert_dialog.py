import logging
import sys

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.ui.components.button import Button
from core.ui.components.text_block import TextBlock
from core.ui.theme import get_tokens, theme_key
from core.utils.win32.backdrop import enable_dwm_frame
from core.utils.win32.bindings import user32

_alert_dialogs: list[AlertDialog] = []


class AlertDialog(QWidget):
    closed = pyqtSignal()

    def __init__(
        self,
        title: str = "",
        message: str = "",
        informative_message: str = "",
        additional_details: str = "",
        rich_text: bool = False,
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._has_details = bool(additional_details)
        self._details_visible = False
        self._theme_key = theme_key()

        # ── build UI ──────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # Enforce strict size constraint so window automatically grows/shrinks
        root.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        # Container card — DWM handles corner radius
        self._container = QFrame(self)
        self._container.setObjectName("alert_bg")
        self._container.setFixedWidth(560)
        root.addWidget(self._container)

        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # -- content area (title + body + details) --
        self._content = QFrame(self._container)
        self._content.setObjectName("alert_content")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(4)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._title_label = TextBlock(title, variant="subtitle", parent=self._content)
        self._title_label.setWordWrap(True)
        self._title_label.setVisible(bool(title))
        content_layout.addWidget(self._title_label)
        content_layout.addSpacing(12)

        self._msg_label = TextBlock(message, variant="body", parent=self._content)
        self._msg_label.setWordWrap(True)
        if rich_text:
            self._msg_label.setTextFormat(Qt.TextFormat.RichText)
        content_layout.addWidget(self._msg_label)

        if informative_message:
            self._info_label = TextBlock(informative_message, variant="body-secondary", parent=self._content)
            self._info_label.setWordWrap(True)
            content_layout.addWidget(self._info_label)
        else:
            self._info_label = None

        self._details_wrapper = QWidget(self._content)
        details_layout = QVBoxLayout(self._details_wrapper)
        details_layout.setContentsMargins(0, 8, 0, 0)
        details_layout.setSpacing(0)

        self._details = QTextEdit(self._details_wrapper)
        self._details.setReadOnly(True)
        self._details.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._details.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._details.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._details.setMaximumHeight(100)
        if additional_details:
            self._details.setPlainText(additional_details)

        details_layout.addWidget(self._details)
        self._details_wrapper.setVisible(False)
        content_layout.addWidget(self._details_wrapper)
        container_layout.addWidget(self._content, 0)

        self._btn_bar = QFrame(self._container)
        self._btn_bar.setObjectName("alert_btns")
        button_layout = QHBoxLayout(self._btn_bar)
        button_layout.setContentsMargins(24, 24, 24, 24)

        self._details_btn: Button | None = None
        if additional_details:
            self._details_btn = Button("Show Details", variant="default", parent=self._btn_bar)
            self._details_btn.clicked.connect(self._toggle_details)
            button_layout.addWidget(self._details_btn)

        self._close_btn = Button("Close", variant="accent", parent=self._btn_bar)
        self._close_btn.clicked.connect(self._close)
        button_layout.addWidget(self._close_btn)

        container_layout.addWidget(self._btn_bar, 0)

        self._apply_styles()
        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._btn_bar.geometry().contains(event.pos()):
                return
            if wh := self.windowHandle():
                wh.startSystemMove()

    def show_dialog(self) -> None:
        self.setWindowOpacity(0.0)
        self._center_on_screen()

        target_pos = self.pos()
        start_pos = target_pos + QPoint(0, 20)
        self.move(start_pos)

        enable_dwm_frame(int(self.winId()))

        self.show()
        self.activateWindow()
        try:
            user32.MessageBeep(3)
        except Exception as e:
            logging.debug("Failed to play error sound: %s", e)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(120)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.Linear)

        self._pos_anim = QPropertyAnimation(self, b"pos")
        self._pos_anim.setDuration(120)
        self._pos_anim.setStartValue(start_pos)
        self._pos_anim.setEndValue(target_pos)
        self._pos_anim.setEasingCurve(QEasingCurve.Type.Linear)

        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(self._fade_anim)
        self._anim_group.addAnimation(self._pos_anim)
        self._anim_group.start()

    def _close(self) -> None:
        self.closed.emit()

        current_pos = self.pos()
        end_pos = current_pos - QPoint(0, 20)

        self._fade_out_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out_anim.setDuration(120)
        self._fade_out_anim.setStartValue(self.windowOpacity())
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.Linear)

        self._pos_out_anim = QPropertyAnimation(self, b"pos")
        self._pos_out_anim.setDuration(120)
        self._pos_out_anim.setStartValue(current_pos)
        self._pos_out_anim.setEndValue(end_pos)
        self._pos_out_anim.setEasingCurve(QEasingCurve.Type.Linear)

        self._out_anim_group = QParallelAnimationGroup(self)
        self._out_anim_group.addAnimation(self._fade_out_anim)
        self._out_anim_group.addAnimation(self._pos_out_anim)
        self._out_anim_group.finished.connect(self.close)
        self._out_anim_group.start()

    def _toggle_details(self) -> None:
        self._details_visible = not self._details_visible
        self._details_wrapper.setVisible(self._details_visible)
        if self._details_btn:
            self._details_btn.setText("Hide details" if self._details_visible else "Show Details")

    def _center_on_screen(self) -> None:
        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        if screen is None:
            return

        self.ensurePolished()
        self.adjustSize()

        centre = screen.geometry().center()
        self.move(
            centre.x() - self.width() // 2,
            centre.y() - self.height() // 2,
        )

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._apply_styles()

    def _apply_styles(self) -> None:
        tokens = get_tokens()
        bg = tokens["solid_bg_base"]
        layer_alt = tokens["layer_alt"]
        stroke = tokens["card_stroke_default"]
        text_secondary = tokens["text_secondary"]

        self._container.setStyleSheet(f"#alert_bg {{ background: {bg}; }}")
        self._content.setStyleSheet(f"#alert_content {{ background: {layer_alt}; border-bottom: 1px solid {stroke}; }}")
        self._btn_bar.setStyleSheet(f"#alert_btns {{ background: {bg}; }}")

        self._details.setStyleSheet(
            f"QTextEdit {{ background: {bg}; color: {text_secondary};"
            f"border: none; padding: 2px; border-radius: 4px;"
            f"font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px; }}"
        )


def raise_info_alert(
    title: str,
    msg: str,
    informative_msg: str,
    additional_details: str = None,
    rich_text: bool = False,
    exit_on_close: bool = False,
) -> None:
    """Show alert dialog.

    Args:
        title: Dialog title (bold heading).
        msg: Primary message body.
        informative_msg: Secondary hint (e.g. "Click 'Show Details'...").
        additional_details: If provided, a "Show more info" button
            appears that expands an inline details pane.
        rich_text: Treat *msg* as HTML.
        exit_on_close: Call ``sys.exit()`` when the dialog is dismissed.
    """
    dlg = AlertDialog(
        title=title,
        message=msg,
        informative_message=informative_msg,
        additional_details=additional_details or "",
        rich_text=rich_text,
    )
    dlg.closed.connect(lambda: _cleanup(dlg))
    if exit_on_close:
        dlg.closed.connect(lambda: sys.exit())
    _alert_dialogs.append(dlg)
    QTimer.singleShot(100, dlg.show_dialog)


def _cleanup(dialog: AlertDialog) -> None:
    try:
        _alert_dialogs.remove(dialog)
    except ValueError:
        pass
