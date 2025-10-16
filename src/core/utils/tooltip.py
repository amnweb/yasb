import re

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from core.config import get_stylesheet


class CustomToolTip(QFrame):
    """Custom tooltip widget with enhanced styling and fade effects."""

    _tooltip_stylesheet = None  # Class-level cache for tooltip CSS
    _active_tooltip = None  # Class-level reference to the currently visible tooltip
    _tooltip_pool = []  # Pool of reusable tooltip instances
    _pool_size_limit = 5  # Maximum number of tooltips to keep in pool

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self._opacity = 0.0
        self._slide_offset = 0
        self._base_pos = None
        self._is_destroyed = False
        self._position = None  # 'top', 'bottom', or None for auto

        # Create label for text content
        self.label = QLabel()
        self.label.setProperty("class", "tooltip")

        # cast to int for margins
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.label)
        self.apply_stylesheet()

        self.fade_in_animation = None
        self.fade_out_animation = None
        self.slide_in_animation = None
        self.slide_out_animation = None

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.start_fade_out)

        self._fade_out_done = False
        self._slide_out_done = False

    def _ensure_animations_created(self):
        """Lazy initialization of animation objects to reduce memory usage."""
        if self.fade_in_animation is None:
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
    def get_or_create_tooltip(cls):
        """Get a tooltip from the pool or create a new one."""
        if cls._tooltip_pool:
            tooltip = cls._tooltip_pool.pop()
            tooltip._is_destroyed = False
            return tooltip
        return cls()

    @classmethod
    def return_to_pool(cls, tooltip):
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
        """Apply the tooltip stylesheet from the cached class-level variable."""
        if CustomToolTip._tooltip_stylesheet is None:
            stylesheet = get_stylesheet()
            extracted = self.extract_class_styles(stylesheet, ["tooltip"])
            if not extracted.strip():
                # Default style if class .tooltip is not found in the stylesheet
                extracted = (
                    ".tooltip {"
                    "background-color: #18191a;"
                    "border: 1px solid #36383a;"
                    "border-radius: 4px;"
                    "color: #a6adc8;"
                    "padding: 6px 12px;"
                    "font-size: 13px;"
                    "font-family: 'Segoe UI';"
                    "font-weight: 600;"
                    "margin-top: 4px;"
                    "}"
                )
            CustomToolTip._tooltip_stylesheet = extracted
        self.setStyleSheet(CustomToolTip._tooltip_stylesheet)

    def extract_class_styles(self, stylesheet, classes):
        pattern = re.compile(
            r"(\.({})\s*\{{[^}}]*\}})".format("|".join(re.escape(cls) for cls in classes)), re.MULTILINE
        )
        matches = pattern.findall(stylesheet)
        return "\n".join(match[0] for match in matches)

    def get_opacity(self):
        return self._opacity

    def set_opacity(self, opacity):
        self._opacity = opacity
        self.setWindowOpacity(opacity)

    opacity = pyqtProperty(float, get_opacity, set_opacity)

    def get_slide_offset(self):
        return self._slide_offset

    def set_slide_offset(self, offset):
        self._slide_offset = offset
        if self._base_pos:
            self.move(self._base_pos.x(), self._base_pos.y() + int(offset))

    slide_offset = pyqtProperty(float, get_slide_offset, set_slide_offset)

    def update_content(self, text):
        """Update tooltip content without hiding it."""
        if self.label.text() != text:
            self.label.setText(text)
            self.adjustSize()
            if self.isVisible() and self._base_pos:
                self.move(self._base_pos.x(), self._base_pos.y() + int(self._slide_offset))

    def _calculate_position(self, widget_geometry):
        """Calculate tooltip position based on widget geometry and screen bounds."""
        screen = QGuiApplication.screenAt(widget_geometry.center()) or QGuiApplication.primaryScreen()
        screen_geometry = screen.geometry()

        # Center horizontally on widget
        x = widget_geometry.center().x() - (self.width() // 2)

        # Position vertically based on preference
        space_below = screen_geometry.bottom() - widget_geometry.bottom()
        space_above = widget_geometry.top() - screen_geometry.top()

        if self._position == "top":
            # Force top position if there's space, otherwise fallback to bottom
            if space_above >= self.height() + 5:
                y = widget_geometry.top() - self.height() - 5
            else:
                y = widget_geometry.bottom() + 5
        elif self._position == "bottom":
            # Force bottom position if there's space, otherwise fallback to top
            if space_below >= self.height() + 5:
                y = widget_geometry.bottom() + 5
            else:
                y = widget_geometry.top() - self.height() - 5
        else:
            # Auto: prefer below, but above if no space
            if space_below >= self.height() + 5:
                y = widget_geometry.bottom() + 5
            elif space_above >= self.height() + 5:
                y = widget_geometry.top() - self.height() - 5
            else:
                y = widget_geometry.bottom() + 5  # Default to below

        # Clamp to screen bounds
        x = max(screen_geometry.left(), min(x, screen_geometry.right() - self.width()))
        y = max(screen_geometry.top(), min(y, screen_geometry.bottom() - self.height()))

        return QPoint(x, y)

    def show_tooltip(self, text, widget_geometry=None, duration=None):
        """Show tooltip centered below or above the widget."""
        if CustomToolTip._active_tooltip and CustomToolTip._active_tooltip is not self:
            CustomToolTip._active_tooltip.hide()
        CustomToolTip._active_tooltip = self

        self.label.setText(text)
        self.adjustSize()

        if widget_geometry:
            self._base_pos = self._calculate_position(widget_geometry)
            self.move(self._base_pos.x(), self._base_pos.y())
        else:
            return

        self._start_animations(fade_in=True)
        self.show()

        if duration:
            self.hide_timer.start(duration)

    def start_fade_out(self):
        self._start_animations(fade_in=False)

    def _start_animations(self, fade_in=True):
        """Helper to start both fade and slide animations together."""
        if self._is_destroyed:
            return

        # Ensure animations are created before using them
        self._ensure_animations_created()

        if fade_in:
            self.fade_out_animation.stop()
            self.slide_out_animation.stop()
            self.set_opacity(0.0)
            self.set_slide_offset(10)
            self.fade_in_animation.start()
            self.slide_in_animation.start()
        else:
            self.hide_timer.stop()
            self.fade_in_animation.stop()
            self.slide_in_animation.stop()
            self.fade_out_animation.setStartValue(self.windowOpacity())
            self.fade_out_animation.setEndValue(0.0)
            self.slide_out_animation.setStartValue(self._slide_offset)
            self.slide_out_animation.setEndValue(10)
            self._fade_out_done = False
            self._slide_out_done = False
            self.fade_out_animation.start()
            self.slide_out_animation.start()

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

    def __init__(self, widget, tooltip_text, delay: int, position=None, parent=None):
        super().__init__(parent)
        self.widget = widget
        self.tooltip_text = tooltip_text
        self.tooltip = None
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

    def cleanup(self):
        """Clean up resources when the event filter is no longer needed."""
        self.hide_timer.stop()
        self.poll_timer.stop()
        self.hover_timer.stop()

        if self._app_event_filter_installed:
            QGuiApplication.instance().removeEventFilter(self)
            self._app_event_filter_installed = False

        if self.tooltip and self.tooltip.isVisible():
            self.tooltip.start_fade_out()
        self.tooltip = None

    def _on_hover_timer(self):
        if self._mouse_inside:
            self.show_tooltip()

    def show_tooltip(self):
        if not self.tooltip:
            self.tooltip = CustomToolTip.get_or_create_tooltip()
            self.tooltip._position = self.position  # Set position preference

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
            self.tooltip.show_tooltip(self.tooltip_text, geometry)

        self.hide_timer.stop()
        if not self._app_event_filter_installed:
            QGuiApplication.instance().installEventFilter(self)
            self._app_event_filter_installed = True
        self._mouse_inside = True
        self.poll_timer.start()

    def update_tooltip_text(self, new_text):
        """Update tooltip text without hiding the tooltip if it's currently shown."""
        self.tooltip_text = new_text
        # If tooltip is currently visible, update its content immediately
        if self.tooltip and self.tooltip.isVisible():
            self.tooltip.update_content(new_text)

    def _hide_tooltip(self):
        if self.tooltip and self.tooltip.isVisible():
            self.tooltip.start_fade_out()
        if self._app_event_filter_installed:
            QGuiApplication.instance().removeEventFilter(self)
            self._app_event_filter_installed = False
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

    def eventFilter(self, obj, event):
        if not isinstance(obj, QObject):
            return False
        if obj is self.widget:
            if event.type() == QEvent.Type.Enter:
                self._mouse_inside = True
                self.hover_timer.start(self.hover_delay)
                self.hide_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                self.hover_timer.stop()
                if not self.hide_timer.isActive():
                    self.hide_timer.start(10)  # Always use 10ms for quick hide
                self._mouse_inside = False
            elif event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.FocusIn):
                self.hover_timer.stop()
                self.hide_timer.stop()
                self._hide_tooltip()
        # Application-wide mouse move
        if event.type() == QEvent.Type.MouseMove and self.tooltip and self.tooltip.isVisible():
            self._poll_mouse()
        return super().eventFilter(obj, event)


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

    if hasattr(widget, "_tooltip_filter"):
        widget._tooltip_filter.update_tooltip_text(text)
        # Update position if provided
        if position is not None:
            widget._tooltip_filter.position = position
    else:
        event_filter = TooltipEventFilter(widget, text, delay, position, widget)
        widget.setMouseTracking(True)
        widget.installEventFilter(event_filter)
        widget._tooltip_filter = event_filter
