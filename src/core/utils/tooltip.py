from collections.abc import Callable
from typing import Any, override

import PyQt6.QtCore as QtCore
from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from core.bar_helper import GlobalState
from core.utils.win32.backdrop import enable_blur

# pyqtProperty exists at runtime but is missing from the PyQt6 type stubs
pyqtProperty: Callable[..., Any] = getattr(QtCore, "pyqtProperty")


class CustomToolTip(QFrame):
    """Custom tooltip widget with enhanced styling and fade effects."""

    _active_tooltip: CustomToolTip | None = None  # Class-level reference to the currently visible tooltip
    _tooltip_pool: list[CustomToolTip] = []  # Pool of reusable tooltip instances
    _pool_size_limit = 5  # Maximum number of tooltips to keep in pool

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self._opacity = 0.0
        self._slide_offset: float = 0
        self._base_pos: QPoint | None = None
        self._is_destroyed = False
        self.position: str | None = None  # 'top', 'bottom', or None for auto

        # Create label for text content
        self.label = QLabel()
        self.label.setProperty("class", "tooltip dark" if GlobalState.is_dark() else "tooltip")

        # cast to int for margins
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self.label)
        self.apply_stylesheet()

        self.fade_in_animation: QPropertyAnimation | None = None
        self.fade_out_animation: QPropertyAnimation | None = None
        self.slide_in_animation: QPropertyAnimation | None = None
        self.slide_out_animation: QPropertyAnimation | None = None

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.start_fade_out)

        self._fade_out_done = False
        self._slide_out_done = False

    def _ensure_animations_created(
        self,
    ) -> tuple[QPropertyAnimation, QPropertyAnimation, QPropertyAnimation, QPropertyAnimation]:
        """Lazy initialization of animation objects to reduce memory usage."""
        if (
            self.fade_in_animation is None
            or self.fade_out_animation is None
            or self.slide_in_animation is None
            or self.slide_out_animation is None
        ):
            # Fade animation
            self.fade_in_animation = QPropertyAnimation(self, b"opacity")
            self.fade_in_animation.setDuration(200)
            self.fade_in_animation.setStartValue(0.0)
            self.fade_in_animation.setEndValue(1.0)
            self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

            self.fade_out_animation = QPropertyAnimation(self, b"opacity")
            self.fade_out_animation.setDuration(200)
            self.fade_out_animation.setStartValue(1.0)
            self.fade_out_animation.setEndValue(0.0)
            self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InCubic)
            self.fade_out_animation.finished.connect(self._on_fade_out_anim_finished)

            # Slide animation
            self.slide_in_animation = QPropertyAnimation(self, b"slide_offset")
            self.slide_in_animation.setDuration(200)
            self.slide_in_animation.setStartValue(10)
            self.slide_in_animation.setEndValue(0)
            self.slide_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

            self.slide_out_animation = QPropertyAnimation(self, b"slide_offset")
            self.slide_out_animation.setDuration(200)
            self.slide_out_animation.setStartValue(0)
            self.slide_out_animation.setEndValue(10)
            self.slide_out_animation.setEasingCurve(QEasingCurve.Type.InCubic)
            self.slide_out_animation.finished.connect(self._on_slide_out_anim_finished)
        return self.fade_in_animation, self.fade_out_animation, self.slide_in_animation, self.slide_out_animation

    def cleanup_animations(self):
        """Clean up animation objects to free memory."""
        if self.fade_in_animation is not None:
            self.fade_in_animation.stop()
            self.fade_in_animation.deleteLater()
            self.fade_in_animation = None

        if self.fade_out_animation is not None:
            self.fade_out_animation.stop()
            self.fade_out_animation.deleteLater()
            self.fade_out_animation = None

        if self.slide_in_animation is not None:
            self.slide_in_animation.stop()
            self.slide_in_animation.deleteLater()
            self.slide_in_animation = None

        if self.slide_out_animation is not None:
            self.slide_out_animation.stop()
            self.slide_out_animation.deleteLater()
            self.slide_out_animation = None

    @classmethod
    def get_or_create_tooltip(cls) -> CustomToolTip:
        """Get a tooltip from the pool or create a new one."""
        if cls._tooltip_pool:
            tooltip = cls._tooltip_pool.pop()
            tooltip._is_destroyed = False
            tooltip.label.setProperty("class", "tooltip dark" if GlobalState.is_dark() else "tooltip")
            tooltip.setStyleSheet(GlobalState.stylesheet())
            return tooltip
        return cls()

    @classmethod
    def return_to_pool(cls, tooltip: CustomToolTip) -> None:
        """Return a tooltip to the pool for reuse."""
        if len(cls._tooltip_pool) < cls._pool_size_limit and not tooltip._is_destroyed:
            tooltip.hide()
            tooltip.cleanup_animations()
            tooltip._is_destroyed = False
            cls._tooltip_pool.append(tooltip)
        else:
            tooltip._is_destroyed = True
            tooltip.cleanup_animations()
            tooltip.deleteLater()

    def apply_stylesheet(self):
        """Apply the tooltip stylesheet from GlobalState."""
        self.setStyleSheet(GlobalState.stylesheet())

    def get_opacity(self) -> float:
        return self._opacity

    def set_opacity(self, opacity: float) -> None:
        self._opacity = opacity
        self.setWindowOpacity(opacity)

    opacity: float = pyqtProperty(float, get_opacity, set_opacity)

    def get_slide_offset(self) -> float:
        return self._slide_offset

    def set_slide_offset(self, offset: float) -> None:
        self._slide_offset = offset
        if self._base_pos is not None:
            self.move(self._base_pos.x(), self._base_pos.y() + int(offset))

    slide_offset: float = pyqtProperty(float, get_slide_offset, set_slide_offset)

    def update_content(self, text: str) -> None:
        """Update tooltip content without hiding it."""
        if self.label.text() != text:
            self.label.setText(text)
            self.adjustSize()
            if self.isVisible() and self._base_pos is not None:
                self.move(self._base_pos.x(), self._base_pos.y() + int(self._slide_offset))

    def calculate_position(self, widget_geometry: QRect, top_level_geometry: QRect | None = None) -> QPoint:
        """Calculate tooltip position based on widget geometry and screen bounds."""
        if top_level_geometry is None:
            top_level_geometry = widget_geometry

        # Center horizontally on widget
        x = widget_geometry.center().x() - (self.width() // 2)

        # Get dynamic offset
        opts = GlobalState.tooltip_options()
        offset = opts.offset if opts else 5

        screen = QGuiApplication.screenAt(widget_geometry.center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return QPoint(x, top_level_geometry.bottom() + offset)
        screen_geometry = screen.geometry()

        # Position vertically based on top level window (Bar or Popup)
        space_below = screen_geometry.bottom() - top_level_geometry.bottom()
        space_above = top_level_geometry.top() - screen_geometry.top()

        if self.position == "top":
            # Force top position if there's space, otherwise fallback to bottom
            if space_above >= self.height() + offset:
                y = top_level_geometry.top() - self.height() - offset
            else:
                y = top_level_geometry.bottom() + offset
        elif self.position == "bottom":
            # Force bottom position if there's space, otherwise fallback to top
            if space_below >= self.height() + offset:
                y = top_level_geometry.bottom() + offset
            else:
                y = top_level_geometry.top() - self.height() - offset
        else:
            # Auto: prefer below, but above if no space
            if space_below >= self.height() + offset:
                y = top_level_geometry.bottom() + offset
            elif space_above >= self.height() + offset:
                y = top_level_geometry.top() - self.height() - offset
            else:
                y = top_level_geometry.bottom() + offset  # Default to below

        # Clamp to screen bounds
        x = max(screen_geometry.left(), min(x, screen_geometry.right() - self.width()))
        y = max(screen_geometry.top(), min(y, screen_geometry.bottom() - self.height()))

        return QPoint(x, y)

    @classmethod
    def hide_active(cls) -> None:
        if cls._active_tooltip is not None:
            cls._active_tooltip.hide()

    def show_tooltip(
        self,
        text: str,
        widget_geometry: QRect | None = None,
        top_level_geometry: QRect | None = None,
        duration: int | None = None,
    ) -> None:
        """Show tooltip centered below or above the widget."""
        if CustomToolTip._active_tooltip and CustomToolTip._active_tooltip is not self:
            CustomToolTip._active_tooltip.hide()
        CustomToolTip._active_tooltip = self

        self.label.setText(text)
        self.adjustSize()

        if widget_geometry is None or widget_geometry.isNull():
            return
        self._base_pos = self.calculate_position(widget_geometry, top_level_geometry)
        self.move(self._base_pos.x(), self._base_pos.y())

        self._start_animations(fade_in=True)
        self.show()

        opts = GlobalState.tooltip_options()
        if opts and opts.blur_effect and opts.blur_effect.enabled:
            blur_cfg = opts.blur_effect
            enable_blur(
                self.winId(),
                DarkMode=blur_cfg.dark_mode,
                RoundCorners=blur_cfg.round_corners,
                RoundCornersType=blur_cfg.round_corners_type,
                BorderColor=blur_cfg.border_color,
            )

        if duration:
            self.hide_timer.start(duration)

    def start_fade_out(self):
        self._start_animations(fade_in=False)

    def _start_animations(self, fade_in: bool = True) -> None:
        """Helper to start both fade and slide animations together."""
        if self._is_destroyed:
            return

        # Ensure animations are created before using them
        fade_in_animation, fade_out_animation, slide_in_animation, slide_out_animation = (
            self._ensure_animations_created()
        )

        if fade_in:
            fade_out_animation.stop()
            slide_out_animation.stop()
            self.set_opacity(0.0)
            self.set_slide_offset(10)
            fade_in_animation.start()
            slide_in_animation.start()
        else:
            self.hide_timer.stop()
            fade_in_animation.stop()
            slide_in_animation.stop()
            fade_out_animation.setStartValue(self.windowOpacity())
            fade_out_animation.setEndValue(0.0)
            slide_out_animation.setStartValue(self._slide_offset)
            slide_out_animation.setEndValue(10)
            self._fade_out_done = False
            self._slide_out_done = False
            fade_out_animation.start()
            slide_out_animation.start()

    def _on_fade_out_anim_finished(self):
        self._fade_out_done = True
        self._check_hide_complete()

    def _on_slide_out_anim_finished(self):
        self._slide_out_done = True
        self._check_hide_complete()

    def _check_hide_complete(self):
        if self._fade_out_done and self._slide_out_done:
            self.hide()
            if CustomToolTip._active_tooltip is self:
                CustomToolTip._active_tooltip = None
            CustomToolTip.return_to_pool(self)


class TooltipEventFilter(QObject):
    """Event filter that shows/hides a custom tooltip with delay."""

    def __init__(
        self,
        widget: QWidget,
        tooltip_text: str,
        delay: int,
        position: str | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.widget = widget
        self.tooltip_text = tooltip_text
        self.tooltip: CustomToolTip | None = None
        self.hover_delay = delay
        self.position = position  # 'top', 'bottom', or None for auto
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._hide_tooltip)
        self._app_event_filter_installed = False
        self._mouse_inside = False
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(50)
        self.poll_timer.timeout.connect(self._poll_mouse)
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self._on_hover_timer)

    def _remove_app_event_filter(self) -> None:
        if self._app_event_filter_installed:
            app = QGuiApplication.instance()
            if app is not None:
                app.removeEventFilter(self)
            self._app_event_filter_installed = False

    def cleanup(self):
        """Clean up resources when the event filter is no longer needed."""
        self.hide_timer.stop()
        self.poll_timer.stop()
        self.hover_timer.stop()

        self._remove_app_event_filter()

        if self.tooltip and self.tooltip.isVisible():
            self.tooltip.start_fade_out()
        self.tooltip = None

    def _on_hover_timer(self):
        if self._mouse_inside:
            self.show_tooltip()

    def show_tooltip(self):
        if not self.tooltip:
            self.tooltip = CustomToolTip.get_or_create_tooltip()
            self.tooltip.position = self.position  # Set position preference

        # Update content if tooltip is visible, otherwise show it
        if self.tooltip.isVisible():
            self.tooltip.update_content(self.tooltip_text)
        else:
            widget_rect = self.widget.rect()
            widget_global_pos = self.widget.mapToGlobal(QPoint(0, 0))
            global_geometry = widget_rect.translated(widget_global_pos)

            geometry = (
                global_geometry
                if (self.widget.isVisible() and widget_rect.width() > 0 and widget_rect.height() > 0)
                else None
            )
            top_level = self.widget.window()
            frame = (
                getattr(top_level, "bar_frame", None) if top_level and top_level.__class__.__name__ == "Bar" else None
            )
            if frame is not None:
                top_level_geometry: QRect = frame.click_rect().translated(frame.mapToGlobal(QPoint(0, 0)))
            else:
                top_level_geometry = global_geometry

            self.tooltip.show_tooltip(self.tooltip_text, geometry, top_level_geometry)

        self.hide_timer.stop()
        if not self._app_event_filter_installed:
            app = QGuiApplication.instance()
            if app is not None:
                app.installEventFilter(self)
            self._app_event_filter_installed = True
        self._mouse_inside = True
        self.poll_timer.start()

    def update_tooltip_text(self, new_text: str) -> None:
        """Update tooltip text without hiding the tooltip if it's currently shown."""
        self.tooltip_text = new_text
        # If tooltip is currently visible, update its content immediately
        if self.tooltip and self.tooltip.isVisible():
            self.tooltip.update_content(new_text)

    def _hide_tooltip(self):
        if self.tooltip and self.tooltip.isVisible():
            self.tooltip.start_fade_out()
        self._remove_app_event_filter()
        self._mouse_inside = False
        self.poll_timer.stop()
        # Clear reference to tooltip so it can be returned to pool
        self.tooltip = None

    def _poll_mouse(self):
        pos = QCursor.pos()
        widget_rect = self.widget.rect()
        widget_global_pos = self.widget.mapToGlobal(QPoint(0, 0))
        global_geometry = widget_rect.translated(widget_global_pos)

        if global_geometry.contains(pos):
            self.hide_timer.stop()
            self._mouse_inside = True
        else:
            if not self.hide_timer.isActive():
                self.hide_timer.start(10)
            self._mouse_inside = False

    @override
    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if not isinstance(a0, QObject) or a1 is None:
            return False
        if a0 is self.widget:
            if a1.type() == QEvent.Type.Enter:
                self._mouse_inside = True
                self.hover_timer.start(self.hover_delay)
                self.hide_timer.stop()
            elif a1.type() == QEvent.Type.Leave:
                self.hover_timer.stop()
                if not self.hide_timer.isActive():
                    self.hide_timer.start(10)  # Always use 10ms for quick hide
                self._mouse_inside = False
            elif a1.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.FocusIn):
                self.hover_timer.stop()
                self.hide_timer.stop()
                self._hide_tooltip()
        # Application-wide mouse move
        if a1.type() == QEvent.Type.MouseMove and self.tooltip and self.tooltip.isVisible():
            self._poll_mouse()
        return super().eventFilter(a0, a1)


def set_tooltip(widget: QWidget, text: str, delay: int = 400, position: str | None = None):
    """Set a tooltip to a widget in a declarative way.

    Args:
        widget: The widget to attach the tooltip to.
        text: The tooltip text.
        delay: Tooltip delay in ms, tooltip will show after this delay, default is 400ms.
        position: Optional position preference - 'top' or 'bottom'. If None, auto-positions based on available space.
    """
    if not text:
        return

    existing_filter = getattr(widget, "_tooltip_filter", None)
    if isinstance(existing_filter, TooltipEventFilter):
        existing_filter.update_tooltip_text(text)
        # Update position if provided
        if position is not None:
            existing_filter.position = position
    else:
        event_filter = TooltipEventFilter(widget, text, delay, position, widget)
        widget.setMouseTracking(True)
        widget.installEventFilter(event_filter)
        setattr(widget, "_tooltip_filter", event_filter)


def show_tooltip_now(widget: QWidget) -> None:
    tooltip_filter = getattr(widget, "_tooltip_filter", None)
    if isinstance(tooltip_filter, TooltipEventFilter):
        tooltip_filter.show_tooltip()
