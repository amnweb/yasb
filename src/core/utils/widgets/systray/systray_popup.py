import ctypes

from PyQt6.QtCore import QEvent, QPoint, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget

from core.utils.widgets.systray.systray_widget import DropWidget, IconWidget
from core.utils.win32.bindings import user32
from core.utils.win32.win32_accent import Blur

# Win32 detect physical mouse button state
_GetAsyncKeyState = user32.GetAsyncKeyState
_GetAsyncKeyState.argtypes = [ctypes.c_int]
_GetAsyncKeyState.restype = ctypes.c_short


def _is_mouse_pressed() -> bool:
    return bool(
        (_GetAsyncKeyState(0x01) & 0x8000)  # VK_LBUTTON
        or (_GetAsyncKeyState(0x02) & 0x8000)  # VK_RBUTTON
        or (_GetAsyncKeyState(0x04) & 0x8000)  # VK_MBUTTON
    )


class SystrayPopup(QWidget):
    """Popup grid window for unpinned systray icons."""

    closed = pyqtSignal()

    def __init__(self, parent, toggle_btn, popup_config, icons_per_row: int, label_collapsed: str = ""):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._toggle_btn = toggle_btn
        self._popup_config = popup_config
        self._label_collapsed = label_collapsed
        self._blur = getattr(popup_config, "blur", True)
        self._round_corners = popup_config.round_corners
        self._round_corners_type = popup_config.round_corners_type
        self._border_color = popup_config.border_color
        self._is_closing = False

        # Inner frame for styling
        self._popup_content = QFrame(self)

        # Grid drop container
        self._grid_widget = DropWidget(grid_cols=icons_per_row)
        self._grid_widget.setProperty("class", "systray-popup")

        outer = QVBoxLayout()
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._grid_widget)
        self.setLayout(outer)

        # Fade animation
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(80)
        self._fade_animation.finished.connect(self._on_animation_finished)

        # Watch timer for native mouse-poll (context-menu interaction)
        self._watch_ticks = 0
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(60)
        self._watch_timer.timeout.connect(self._on_watch_tick)

        self.closed.connect(self._on_popup_closed)

    @property
    def grid_widget(self) -> DropWidget:
        return self._grid_widget

    @property
    def is_visible(self) -> bool:
        return self.isVisible() and not self._is_closing

    def add_icon(self, icon: IconWidget):
        self._grid_widget.add_icon_to_grid(icon)

    def toggle(self, label_expanded: str):
        if self._is_closing:
            return
        self.hide_animated() if self.is_visible else self.open(label_expanded)

    def open(self, label_expanded: str):
        self._grid_widget.relayout_grid()
        self.adjustSize()
        self._set_position(
            alignment=self._popup_config.alignment,
            direction=self._popup_config.direction,
            offset_left=self._popup_config.offset_left,
            offset_top=self._popup_config.offset_top,
        )
        self.show()
        self._toggle_btn.setChecked(True)
        self._toggle_btn.setText(label_expanded)

    def relayout_grid(self):
        self._grid_widget.relayout_grid()
        if self.isVisible():
            self._grid_widget.updateGeometry()
            self.adjustSize()

    def sort_unpinned(self, sorted_icons: list[IconWidget]):
        self._grid_widget.relayout_grid(sorted_icons)
        if self.isVisible():
            self._grid_widget.updateGeometry()
            self.adjustSize()

    def _set_position(self, alignment="left", direction="down", offset_left=0, offset_top=0):
        self._pos_args = (alignment, direction, offset_left, offset_top)

        btn = self._toggle_btn
        parent = self.parent()
        if not btn or not parent:
            return

        # Vertical offset from bar (parent), same as other popup widgets
        # Horizontal align relative to the toggle button
        # We need to mess with this because we want to center the popup below the button.
        btn_origin = btn.mapToGlobal(QPoint(0, 0))
        bar_origin = parent.mapToGlobal(QPoint(0, 0))

        if direction == "up":
            y = bar_origin.y() - self.height() - offset_top
        else:
            y = bar_origin.y() + parent.height() + offset_top

        x = btn_origin.x() + offset_left

        if alignment == "right":
            x = btn_origin.x() + btn.width() - self.width() + offset_left
        elif alignment == "center":
            x = btn_origin.x() + (btn.width() - self.width()) // 2 + offset_left

        screen = QApplication.screenAt(btn.mapToGlobal(btn.rect().center()))
        if screen:
            sg = screen.geometry()
            x = max(sg.left(), min(x, sg.right() - self.width()))
            y = max(sg.top(), min(y, sg.bottom() - self.height()))

        self.move(QPoint(x, y))

    def setProperty(self, name, value):
        super().setProperty(name, value)
        if name == "class":
            self._popup_content.setProperty(name, value)

    def _popup_rect(self) -> QRect:
        return QRect(self.mapToGlobal(QPoint(0, 0)), self.size())

    def showEvent(self, event):
        if self._blur:
            Blur(
                self.winId(),
                Acrylic=False,
                DarkMode=False,
                RoundCorners=self._round_corners,
                RoundCornersType=self._round_corners_type,
                BorderColor=self._border_color,
            )

        self._is_closing = False
        try:
            if self._fade_animation.state() == QPropertyAnimation.State.Running:
                self._fade_animation.stop()
        except Exception:
            pass

        self.setWindowOpacity(0.0)
        super().showEvent(event)
        self.activateWindow()

        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()

    def hide_animated(self):
        """Hide with a fade-out animation."""
        if self._is_closing:
            return
        # Update button state immediately
        self._toggle_btn.setChecked(False)
        if self._label_collapsed:
            self._toggle_btn.setText(self._label_collapsed)
        try:
            if self._fade_animation.state() == QPropertyAnimation.State.Running:
                self._fade_animation.stop()
        except Exception:
            pass

        current_opacity = self.windowOpacity()
        if current_opacity <= 0.0:
            current_opacity = 1.0
            self.setWindowOpacity(1.0)

        self._is_closing = True
        self._fade_animation.setStartValue(current_opacity)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.start()

    def _on_animation_finished(self):
        if self._is_closing:
            QWidget.hide(self)
            self._is_closing = False

    def hideEvent(self, event):
        self._watch_timer.stop()
        if self._is_closing:
            try:
                from core.global_state import get_autohide_owner_for_widget

                mgr = get_autohide_owner_for_widget(self)._autohide_manager
                if mgr._hide_timer:
                    mgr._hide_timer.start(mgr._autohide_delay)
            except Exception:
                pass
        super().hideEvent(event)
        self.closed.emit()

    def closeEvent(self, event):
        event.ignore()
        self.hide_animated()

    def _on_popup_closed(self):
        self._toggle_btn.setChecked(False)
        if self._label_collapsed:
            self._toggle_btn.setText(self._label_collapsed)

    def resizeEvent(self, event):
        self._popup_content.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "_pos_args"):
            self._set_position(*self._pos_args)
        super().resizeEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() != QEvent.Type.ActivationChange or self._is_closing:
            return
        if self.isActiveWindow():
            self._watch_timer.stop()
        elif IconWidget._drag_in_progress:
            pass  # Suppress close during drag-and-drop
        elif self._toggle_btn and self._toggle_btn.rect().contains(self._toggle_btn.mapFromGlobal(QCursor.pos())):
            # User clicked the toggle button let the button's clicked handler decide
            pass
        elif self._popup_rect().contains(QCursor.pos()):
            self._watch_ticks = 0
            self._watch_timer.start()
        else:
            self.hide_animated()

    def _on_watch_tick(self):
        self._watch_ticks += 1
        if self._is_closing or self.isActiveWindow() or IconWidget._drag_in_progress:
            self._watch_timer.stop()
            return
        if self._watch_ticks >= 3 and _is_mouse_pressed():
            if not self._popup_rect().contains(QCursor.pos()):
                self._watch_timer.stop()
                self.hide_animated()
