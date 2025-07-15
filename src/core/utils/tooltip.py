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
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel

from core.config import get_stylesheet


class CustomToolTip(QFrame):
    """Custom tooltip widget with enhanced styling and fade effects."""

    _tooltip_stylesheet = None  # Class-level cache for tooltip CSS
    _active_tooltip = None  # Class-level reference to the currently visible tooltip

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self._opacity = 0.0
        self._slide_offset = 0
        self._base_pos = None
        # Create label for text content
        self.label = QLabel()
        self.label.setProperty("class", "tooltip")

        # cast to int for margins
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.label)
        self.apply_stylesheet()
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

        # Timer to auto-hide tooltip
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.start_fade_out)

        self._fade_out_done = False
        self._slide_out_done = False

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
        self.update()

    opacity = pyqtProperty(float, get_opacity, set_opacity)

    def get_slide_offset(self):
        return self._slide_offset

    def set_slide_offset(self, offset):
        self._slide_offset = offset
        if self._base_pos:
            self.move(self._base_pos.x(), self._base_pos.y() + int(offset))

    slide_offset = pyqtProperty(float, get_slide_offset, set_slide_offset)

    def show_tooltip(self, text, pos, widget_geometry=None, duration=None):
        """Show tooltip centered below or above the widget."""
        # Hide any previous tooltip immediately
        if CustomToolTip._active_tooltip and CustomToolTip._active_tooltip is not self:
            CustomToolTip._active_tooltip.hide()
        CustomToolTip._active_tooltip = self
        self.label.setText(text)
        self.adjustSize()
        if widget_geometry:
            screen = QGuiApplication.screenAt(widget_geometry.center())
            if not screen:
                screen = QGuiApplication.primaryScreen()
            screen_geometry = screen.geometry()
            tooltip_width = self.width()
            tooltip_height = self.height()
            bar_top = widget_geometry.top()
            bar_bottom = widget_geometry.bottom()
            bar_center_x = widget_geometry.center().x()
            # Center tooltip horizontally to widget
            x = bar_center_x - (tooltip_width // 2)
            # Decide above or below bar
            if abs(bar_top - screen_geometry.top()) < 10:
                y = bar_bottom + 5
            elif abs(bar_bottom - screen_geometry.bottom()) < 10:
                y = bar_top - tooltip_height - 5
            else:
                space_below = screen_geometry.bottom() - bar_bottom
                space_above = bar_top - screen_geometry.top()
                if space_below >= tooltip_height + 5:
                    y = bar_bottom + 5
                elif space_above >= tooltip_height + 5:
                    y = bar_top - tooltip_height - 5
                else:
                    y = bar_bottom + 5
            # Clamp x to screen
            if x + tooltip_width > screen_geometry.right():
                x = screen_geometry.right() - tooltip_width
            if x < screen_geometry.left():
                x = screen_geometry.left()
            # Clamp y to screen
            if y + tooltip_height > screen_geometry.bottom():
                y = screen_geometry.bottom() - tooltip_height
            if y < screen_geometry.top():
                y = screen_geometry.top()
            self._base_pos = QPoint(x, y)
            self.move(x, y)
        else:
            # if widget_geometry is not provided or we not able to calculate a valid position
            return
        self._start_animations(fade_in=True)
        self.show()
        # Start the hide timer if a duration is specified
        if duration:
            self.hide_timer.start(duration)

    def calculate_optimal_position(self, cursor_pos, widget_geometry=None):
        """Calculate optimal tooltip position based on screen boundaries, cursor position, and widget geometry."""
        screen = QGuiApplication.screenAt(cursor_pos)
        if not screen:
            screen = QGuiApplication.primaryScreen()
        screen_geometry = screen.geometry()
        tooltip_size = self.size()
        # Default: below cursor
        x = cursor_pos.x() - (tooltip_size.width() // 2)
        y = cursor_pos.y() + 20
        if widget_geometry:
            if cursor_pos.y() >= widget_geometry.bottom():
                y = widget_geometry.bottom() + 5
            elif cursor_pos.y() <= widget_geometry.top():
                y = widget_geometry.top() - tooltip_size.height() - 5
            else:
                space_below = screen_geometry.bottom() - widget_geometry.bottom()
                space_above = widget_geometry.top() - screen_geometry.top()
                if space_below >= tooltip_size.height() or space_below > space_above:
                    y = widget_geometry.bottom() + 5
                else:
                    y = widget_geometry.top() - tooltip_size.height() - 5
        # Clamp x within screen
        if x + tooltip_size.width() > screen_geometry.right():
            x = screen_geometry.right() - tooltip_size.width()
        if x < screen_geometry.left():
            x = screen_geometry.left()
        # Clamp y within screen, always prefer below if not enough space above
        if y + tooltip_size.height() > screen_geometry.bottom():
            y = cursor_pos.y() - tooltip_size.height() - 20
        if y < screen_geometry.top():
            # If not enough space above, force below
            y = min(cursor_pos.y() + 20, screen_geometry.bottom() - tooltip_size.height())
        return QPoint(x, y)

    def start_fade_out(self):
        self._start_animations(fade_in=False)

    def _start_animations(self, fade_in=True):
        """Helper to start both fade and slide animations together."""
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

    def show(self):
        super().show()

    def hide(self):
        super().hide()

    def _on_fade_out_anim_finished(self):
        self._fade_out_done = True
        self._maybe_hide()

    def _on_slide_out_anim_finished(self):
        self._slide_out_done = True
        self._maybe_hide()

    def _maybe_hide(self):
        if self._fade_out_done and self._slide_out_done:
            self.hide()


class TooltipEventFilter(QObject):
    """Event filter that shows/hides a custom tooltip with delay."""

    def __init__(self, widget, tooltip_text, delay: int, parent=None):
        super().__init__(parent)
        self.widget = widget
        self.tooltip_text = tooltip_text
        self.tooltip = CustomToolTip()
        self.hover_delay = delay
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

    def _on_hover_timer(self):
        if self._mouse_inside:
            self.show_tooltip()

    def show_tooltip(self):
        widget_rect = self.widget.rect()
        widget_global_top_left = self.widget.mapToGlobal(QPoint(0, 0))
        global_geometry = widget_rect.translated(widget_global_top_left)
        if not self.widget.isVisible() or widget_rect.width() == 0 or widget_rect.height() == 0:
            cursor_pos = QCursor.pos()
            self.tooltip.show_tooltip(self.tooltip_text, cursor_pos, None)
        else:
            self.tooltip.show_tooltip(self.tooltip_text, global_geometry.center(), global_geometry)
        self.hide_timer.stop()
        if not self._app_event_filter_installed:
            QGuiApplication.instance().installEventFilter(self)
            self._app_event_filter_installed = True
        self._mouse_inside = True
        self.poll_timer.start()

    def _hide_tooltip(self):
        if self.tooltip.isVisible():
            self.tooltip.start_fade_out()
        if self._app_event_filter_installed:
            QGuiApplication.instance().removeEventFilter(self)
            self._app_event_filter_installed = False
        self._mouse_inside = False
        self.poll_timer.stop()

    def _poll_mouse(self):
        pos = QCursor.pos()
        widget_rect = self.widget.rect()
        widget_global_top_left = self.widget.mapToGlobal(QPoint(0, 0))
        global_geometry = widget_rect.translated(widget_global_top_left)
        inside = global_geometry.contains(pos)
        if inside:
            if self.hide_timer.isActive():
                self.hide_timer.stop()
            self._mouse_inside = True
        else:
            if not self.hide_timer.isActive():
                self.hide_timer.start(10)
            self._mouse_inside = False

    def eventFilter(self, obj, event):
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
        if event.type() == QEvent.Type.MouseMove and self.tooltip.isVisible():
            self._poll_mouse()
        return super().eventFilter(obj, event)


def set_tooltip(widget, text, delay=400):
    """Set a tooltip to a widget in a declarative way.

    Args:
        widget: The widget to attach the tooltip to.
        text: The tooltip text.
        delay: Tooltip delay in ms, tooltip will show after this delay, default is 400ms.
    """
    if not text:
        return
    # Remove any existing tooltip event filter
    if hasattr(widget, "_tooltip_filter"):
        widget.removeEventFilter(widget._tooltip_filter)
    event_filter = TooltipEventFilter(widget, text, delay, widget)
    widget.setMouseTracking(True)
    widget.installEventFilter(event_filter)
    widget._tooltip_filter = event_filter
