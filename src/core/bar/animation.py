from typing import TYPE_CHECKING

from PyQt6.QtCore import QEasingCurve, QObject, QPropertyAnimation, QRect
from PyQt6.QtGui import QCursor, QGuiApplication

if TYPE_CHECKING:
    from core.bar.window import BarWindow


class BarAnimationManager(QObject):
    def __init__(self, bar: BarWindow, parent: QObject | None = None):
        super().__init__(parent)
        self.bar = bar
        self._animation: QPropertyAnimation | None = None
        self._target: QRect | None = None
        self._pending: str | None = None

    @property
    def _enabled(self) -> bool:
        return self.bar.config.animation.type != "none"

    def _running(self) -> bool:
        return self._animation is not None and self._animation.state() == QPropertyAnimation.State.Running

    def show_bar(self, initial: bool = False) -> None:
        if not self._enabled:
            self.bar.show()
            return
        if self._running():
            self._pending = "show"
            return
        self._pending = None
        # A slide on the first show flashes the DWM blur and shadow, so the first show always fades
        if initial or self.bar.config.animation.type == "fade":
            self._start_fade(True)
        else:
            self._start_slide(True)

    def hide_bar(self) -> None:
        if not self._enabled:
            self.bar.hide()
            return
        if self._running():
            self._pending = "hide"
            return
        self._pending = None
        if self.bar.config.animation.type == "fade":
            self._start_fade(False)
        else:
            self._start_slide(False)

    def _stop(self) -> None:
        if self._animation is not None and self._running():
            self._animation.stop()
        self._animation = None

    def _start_fade(self, show: bool) -> None:
        self._stop()
        self._animation = QPropertyAnimation(self.bar, b"opacity", self)
        self._animation.setDuration(self.bar.config.animation.duration)
        self._animation.setStartValue(0.0 if show else 1.0)
        self._animation.setEndValue(1.0 if show else 0.0)
        self._animation.setEasingCurve(QEasingCurve.Type.OutQuad if show else QEasingCurve.Type.InQuad)
        self._animation.finished.connect(self._on_show_finished if show else self._on_hide_finished)
        if show:
            self.bar.setOpacity(0.0)
            self.bar.show()
        self._animation.start()

    def _start_slide(self, show: bool) -> None:
        self._stop()
        self.bar.reposition()
        resting = self.bar.geometry()
        self._target = QRect(resting)

        screen = self.bar.screen()
        if screen is None:
            self._start_fade(show)
            return
        area = screen.geometry()
        hidden = QRect(resting)
        edge = self.bar.config.edge
        if edge == "top":
            hidden.moveTop(area.y() - resting.height())
        elif edge == "bottom":
            hidden.moveTop(area.y() + area.height())
        elif edge == "left":
            hidden.moveLeft(area.x() - resting.width())
        else:
            hidden.moveLeft(area.x() + area.width())

        # Sliding out of its own screen would show the bar on a screen stacked next to it. Clipping it
        # means resizing the window every frame, which smears the DWM blur and shadow, so those bars fade.
        if any(other.geometry().intersects(hidden) for other in QGuiApplication.screens()):
            self._start_fade(show)
            return

        vertical = self.bar.config.vertical
        start, end = (hidden, resting) if show else (resting, hidden)
        if show:
            self.bar.setPosition(hidden.topLeft())
        self._animation = QPropertyAnimation(self.bar, b"x" if vertical else b"y", self)
        self._animation.setDuration(self.bar.config.animation.duration)
        self._animation.setStartValue(start.x() if vertical else start.y())
        self._animation.setEndValue(end.x() if vertical else end.y())
        self._animation.setEasingCurve(QEasingCurve.Type.OutQuad if show else QEasingCurve.Type.InQuad)
        self._animation.finished.connect(self._on_show_finished if show else self._on_hide_finished)
        self._animation.start()
        if show and not self.bar.isVisible():
            self.bar.show()

    def _on_show_finished(self) -> None:
        if self._target is not None:
            self.bar.setGeometry(self._target)
        self._animation = None
        self._process_pending()

        autohide = self.bar.autohide_manager
        if autohide is not None and autohide.is_enabled():
            cursor = QCursor.pos()
            geometry = self.bar.geometry()
            if not geometry.contains(cursor) and not autohide.is_mouse_in_safe_zone(cursor, geometry):
                autohide.restart_hide_timer()

    def _on_hide_finished(self) -> None:
        self.bar.hide()
        self.bar.setOpacity(1.0)
        if self._target is not None:
            self.bar.setPosition(self._target.topLeft())
        self._animation = None
        self._process_pending()

    def _process_pending(self) -> None:
        action, self._pending = self._pending, None
        if action == "show" and not self.bar.isVisible():
            self.show_bar()
        elif action == "hide" and self.bar.isVisible():
            self.hide_bar()

    def cleanup(self) -> None:
        self._pending = None
        self._stop()
