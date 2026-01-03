import math
import os
import platform
import re
from datetime import datetime, timezone
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, TypeGuard, cast, override

import psutil
from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, QPoint, QPropertyAnimation, QRect, QSize, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import (
    QColor,
    QFontMetrics,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QScreen,
    QStaticText,
    QTransform,
)
from PyQt6.QtWidgets import QApplication, QDialog, QFrame, QGraphicsDropShadowEffect, QLabel, QMenu, QWidget
from winrt.windows.data.xml.dom import XmlDocument
from winrt.windows.ui.notifications import ToastNotification, ToastNotificationManager

from core.utils.win32.win32_accent import Blur


def is_valid_qobject[T](obj: T | None) -> TypeGuard[T]:
    """Check if the object is a valid QObject with specific type"""
    return obj is not None and isinstance(obj, QObject) and not sip.isdeleted(obj)


def app_data_path(filename: str = None) -> Path:
    """
    Get the YASB local data folder (creating it if it doesn't exist),
    or a file path inside it if filename is provided.
    """
    folder = Path(os.environ["LOCALAPPDATA"]) / "YASB"
    folder.mkdir(parents=True, exist_ok=True)
    if filename is not None:
        return folder / filename
    return folder


def is_windows_10() -> bool:
    version = platform.version()
    return bool(re.match(r"^10\.0\.1\d{4}$", version))


def detect_architecture() -> tuple[str, str] | None:
    """Detect the system architecture for build purposes.

    Returns:
        Tuple of (display_name, msi_suffix): ("ARM64", "aarch64") or ("x64", "x64"), or None if unknown
    """
    try:
        machine = platform.machine().lower()

        # Check for ARM64
        if machine in ["arm64", "aarch64"]:
            return ("ARM64", "aarch64")

        # Check for x64
        if machine in ["amd64", "x86_64", "x64"]:
            return ("x64", "x64")

        # Fallback: check if running on 64-bit Windows
        if platform.architecture()[0] == "64bit":
            return ("x64", "x64")

        return None
    except Exception:
        return None


def get_architecture() -> str | None:
    """Get the build architecture from BUILD_CONSTANTS.

    Returns:
        Architecture string from frozen build, or None if not frozen/built
    """
    try:
        from BUILD_CONSTANTS import ARCHITECTURE  # type: ignore[import-not-found]

        return ARCHITECTURE
    except ImportError:
        return None


def get_relative_time(iso_timestamp: str) -> str:
    """
    Convert an ISO 8601 timestamp to a human-readable relative time string.

    Args:
        iso_timestamp: ISO 8601 formatted timestamp (e.g., "2024-11-01T12:00:00Z")

    Returns:
        A relative time string (e.g., "3 days ago", "2 weeks ago", "just now")
        Returns empty string if timestamp is invalid or empty.

    Examples:
        >>> get_relative_time("2024-11-07T12:00:00Z")
        "just now"
        >>> get_relative_time("2024-11-04T12:00:00Z")
        "3 days ago"
    """
    if not iso_timestamp:
        return ""

    try:
        # Parse ISO 8601 timestamp
        updated = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - updated

        seconds = diff.total_seconds()
        minutes = seconds / 60
        hours = minutes / 60
        days = hours / 24
        weeks = days / 7
        months = days / 30
        years = days / 365

        if seconds < 60:
            return "just now"
        elif minutes < 60:
            m = int(minutes)
            return f"{m} minute{'s' if m != 1 else ''} ago"
        elif hours < 24:
            h = int(hours)
            return f"{h} hour{'s' if h != 1 else ''} ago"
        elif days < 7:
            d = int(days)
            return f"{d} day{'s' if d != 1 else ''} ago"
        elif weeks < 4:
            w = int(weeks)
            return f"{w} week{'s' if w != 1 else ''} ago"
        elif months < 12:
            mo = int(months)
            return f"{mo} month{'s' if mo != 1 else ''} ago"
        else:
            y = int(years)
            return f"{y} year{'s' if y != 1 else ''} ago"
    except Exception:
        return ""


def is_process_running(process_name: str) -> bool:
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] == process_name:
            return True
    return False


def percent_to_float(percent: str) -> float:
    return float(percent.strip("%")) / 100.0


def is_valid_percentage_str(s: str) -> bool:
    return s.endswith("%") and len(s) <= 4 and s[:-1].isdigit()


def get_screen_by_name(screen_name: str) -> QScreen:
    return next(filter(lambda scr: screen_name in scr.name(), QApplication.screens()), None)


def add_shadow(el: QWidget, options: dict[str, Any]) -> None:
    """ "Add a shadow effect to a given element."""
    if not options["enabled"]:
        return

    shadow_effect = QGraphicsDropShadowEffect(el)
    shadow_effect.setOffset(options["offset"][0], options["offset"][1])
    shadow_effect.setBlurRadius(options["radius"])

    color = options["color"]
    if color.startswith("#"):
        color = color.lstrip("#")
        # Handle hex with alpha (#RRGGBBAA format)
        if len(color) == 8:
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            a = int(color[6:8], 16)
            shadow_effect.setColor(QColor(r, g, b, a))
        else:
            # Regular hex color without alpha
            shadow_effect.setColor(QColor("#" + color))
    else:
        # Named colors like "black", "red", etc.
        shadow_effect.setColor(QColor(color))

    el.setGraphicsEffect(shadow_effect)


def refresh_widget_style(*widgets: QWidget) -> None:
    """Refresh the style of the given widgets."""
    for widget in widgets:
        if widget is None or not is_valid_qobject(widget):
            continue
        style = widget.style()
        if not style:
            continue
        try:
            style.unpolish(widget)
            style.polish(widget)
        except Exception:
            pass


def build_widget_label(self, content: str, content_alt: str = None, content_shadow: dict = None):
    def process_content(content, is_alt=False):
        label_parts = re.split("(<span.*?>.*?</span>)", content)
        label_parts = [part for part in label_parts if part]
        widgets = []
        for part in label_parts:
            part = part.strip()
            if not part:
                continue
            if "<span" in part and "</span>" in part:
                class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                class_result = class_name.group(2) if class_name else "icon"
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                label = QLabel(icon)
                label.setProperty("class", class_result)
            else:
                label = QLabel(part)
                label.setProperty("class", "label alt" if is_alt else "label")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            if content_shadow:
                add_shadow(label, content_shadow)
            self._widget_container_layout.addWidget(label)
            widgets.append(label)
            if is_alt:
                label.hide()
            else:
                label.show()
        return widgets

    self._widgets = process_content(content)
    if content_alt:
        self._widgets_alt = process_content(content_alt, is_alt=True)


def build_progress_widget(self, options: dict[str, Any]) -> None:
    """Builds a circular progress widget based on the provided options."""
    if not options["enabled"]:
        return

    from core.utils.widgets.circular_progress_bar import CircularProgressBar, CircularProgressWidget

    self.progress_data = CircularProgressBar(
        parent=self,
        size=options["size"],
        thickness=options["thickness"],
        color=options["color"],
        background_color=options["background_color"],
        animation=options["animation"],
    )
    self.progress_widget = CircularProgressWidget(self.progress_data)
    return self.progress_widget


@lru_cache(maxsize=1)
def get_app_identifier():
    """Returns AppUserModelID regardless of installation location"""
    import os
    import sys
    import winreg
    from pathlib import Path

    from settings import APP_ID

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SOFTWARE\\Classes\\AppUserModelId\\{APP_ID}")
        winreg.CloseKey(key)
        return APP_ID
    except:
        if getattr(sys, "frozen", False):
            # Check if YASB is installed via Scoop and if so, return the path to the executable
            # This is a workaround for the issue where the registry key doesn't exist to return the correct App name and icon
            scoop_shortcut = os.path.join(
                os.environ.get("APPDATA", ""),
                "Microsoft",
                "Windows",
                "Start Menu",
                "Programs",
                "Scoop Apps",
                "YASB.lnk",
            )
            if Path(scoop_shortcut).exists():
                return sys.executable
        # Fallback to the default AppUserModelID
        return "YASB"


class PopupWidget(QWidget):
    """
    A custom popup widget that can be used to create a frameless, translucent window.
    This widget can be used to create custom popups with various styles and effects.
    Attributes:
        _blur (bool): Whether to apply a blur effect to the popup.
        _round_corners (bool): Whether to round the corners of the popup.
        _round_corners_type (str): Type of round corners to apply.
        _border_color (str): Color of the border.
    Methods:
        setProperty(name, value): Set a property for the popup widget.
        setPosition(alignment, direction, offset_left, offset_top): Position the popup relative to its parent widget.
        showEvent(event): Handle the show event for the popup.
        eventFilter(obj, event): Filter events to detect clicks outside the popup.
        hideEvent(event): Handle the hide event for the popup.
        resizeEvent(event): Handle the resize event for the popup.
    """

    def __init__(
        self,
        parent: QWidget,
        blur: bool = False,
        round_corners: bool = False,
        round_corners_type: str = "normal",
        border_color: str = "None",
    ):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._blur = blur
        self._round_corners = round_corners
        self._round_corners_type = round_corners_type
        self._border_color = border_color
        self._parent = parent
        self._suspend_close = False
        # We need bar_id for global_state autohide manager
        self.bar_id = getattr(self._parent, "bar_id", None)
        # Create the inner frame
        self._popup_content = QFrame(self)

        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(80)
        self._fade_animation.finished.connect(self._on_animation_finished)

        self._is_closing = False

        QApplication.instance().installEventFilter(self)

    def setProperty(self, name, value):
        super().setProperty(name, value)
        if name == "class":
            self._popup_content.setProperty(name, value)

    def setPosition(self, alignment="left", direction="down", offset_left=0, offset_top=0):
        """
        Position the popup relative to its parent widget.
        Args:
            alignment (str): Where to align the popup - 'left', 'right', or 'center'
            direction (str): Whether popup appears above ('up') or below ('down') the parent
            offset_left (int): Horizontal offset in pixels
            offset_top (int): Vertical offset in pixels
        """
        # store the arguments for later use
        # this is needed to reposition the popup when resized
        self._pos_args = (alignment, direction, offset_left, offset_top)

        parent = cast(QWidget, self.parent())  # parent should be a QWidget
        if not parent:
            return

        widget_global_pos = parent.mapToGlobal(QPoint(offset_left, parent.height() + offset_top))

        if direction == "up":
            global_y = parent.mapToGlobal(QPoint(0, 0)).y() - self.height() - offset_top
            widget_global_pos = QPoint(parent.mapToGlobal(QPoint(0, 0)).x() + offset_left, global_y)

        if alignment == "left":
            global_position = widget_global_pos
        elif alignment == "right":
            global_position = QPoint(widget_global_pos.x() + parent.width() - self.width(), widget_global_pos.y())
        elif alignment == "center":
            global_position = QPoint(
                widget_global_pos.x() + (parent.width() - self.width()) // 2, widget_global_pos.y()
            )
        else:
            global_position = widget_global_pos

        # Determine screen where the parent is
        screen = QApplication.screenAt(parent.mapToGlobal(parent.rect().center()))
        if screen:
            screen_geometry = screen.geometry()
            # Ensure the popup fits horizontally
            x = max(screen_geometry.left(), min(global_position.x(), screen_geometry.right() - self.width()))
            # Ensure the popup fits vertically
            y = max(screen_geometry.top(), min(global_position.y(), screen_geometry.bottom() - self.height()))
            global_position = QPoint(x, y)
        self.move(global_position)

    def _add_separator(self, layout):
        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setProperty("class", "separator")
        separator.setStyleSheet("border:none")
        layout.addWidget(separator)

    def _on_animation_finished(self):
        """Handle animation completion."""
        if self._is_closing:
            try:
                super().hide()
                self.deleteLater()
            except Exception:
                pass

    def hide_animated(self):
        """Hide the popup with animation."""
        if self._is_closing:
            return
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

    def hide(self):
        """Hide the popup immediately without animation."""
        try:
            if self._fade_animation.state() == QPropertyAnimation.State.Running:
                self._fade_animation.stop()
        except Exception:
            pass

        self._is_closing = True
        try:
            super().hide()
            self.deleteLater()
        except Exception:
            pass

    def closeEvent(self, event):
        """Override close event to use animation."""
        event.ignore()  # Ignore the default close behavior
        self.hide_animated()

    def showEvent(self, event):
        if self._blur:
            Blur(
                self.winId(),
                Acrylic=True if is_windows_10() else False,
                DarkMode=False,
                RoundCorners=False if is_windows_10() else self._round_corners,
                RoundCornersType=self._round_corners_type,
                BorderColor=self._border_color,
            )

        # Reset closing state and stop any ongoing fade animation
        self._is_closing = False
        try:
            if self._fade_animation.state() == QPropertyAnimation.State.Running:
                self._fade_animation.stop()
        except Exception:
            pass

        # Set initial opacity and show
        self.setWindowOpacity(0.0)

        super().showEvent(event)

        self.activateWindow()
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()

    def eventFilter(self, obj, event):
        if not isinstance(obj, QObject):
            return False
        if self._suspend_close:
            return super().eventFilter(obj, event)
        if event.type() == QEvent.Type.MouseButtonPress:
            global_pos = event.globalPosition().toPoint()

            # Check if click is inside popup
            try:
                popup_global_geom = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
            except Exception:
                popup_global_geom = self.geometry()
            if popup_global_geom.contains(global_pos):
                return super().eventFilter(obj, event)

            # Check if click is inside any visible QMenu or QDialog (file dialogs, etc.)
            try:
                for w in QApplication.topLevelWidgets():
                    if isinstance(w, (QMenu, QDialog)) and w.isVisible() and w is not self:
                        try:
                            w_global_geom = QRect(w.mapToGlobal(QPoint(0, 0)), w.size())
                            if w_global_geom.contains(global_pos):
                                return super().eventFilter(obj, event)
                        except Exception:
                            continue
            except Exception:
                pass

            # Otherwise, close all open QMenus first
            for menu in self.findChildren(QMenu):
                if menu.isVisible():
                    menu.close()

            self.hide_animated()
            return True
        return super().eventFilter(obj, event)

    def set_auto_close_enabled(self, enabled: bool):
        """Enable/disable auto-close behavior when clicking outside."""
        self._suspend_close = not enabled

    def hideEvent(self, event):
        if self._is_closing:
            QApplication.instance().removeEventFilter(self)

            try:
                # Restart autohide timer if applicable
                from core.global_state import get_autohide_owner_for_widget

                mgr = get_autohide_owner_for_widget(self)._autohide_manager
                if mgr._hide_timer:
                    mgr._hide_timer.start(mgr._autohide_delay)
            except Exception:
                pass

        super().hideEvent(event)

    def resizeEvent(self, event):
        # reset geometry
        self._popup_content.setGeometry(0, 0, self.width(), self.height())
        # reposition if we've already called setPosition()
        if hasattr(self, "_pos_args"):
            alignment, direction, offset_left, offset_top = self._pos_args
            self.setPosition(alignment, direction, offset_left, offset_top)

        super().resizeEvent(event)


class ToastNotifier:
    """
    A class to show toast notifications using the Windows Toast Notification API.
    Methods:
        show(icon_path, title, message, duration):
    """

    def __init__(self):
        self.manager = ToastNotificationManager.get_default()
        self.toaster = self.manager.create_toast_notifier_with_id(get_app_identifier())

    def show(
        self,
        icon_path: str,
        title: str,
        message: str,
        duration: str = "short",
        launch_url: str = None,
        scenario: str = None,
    ) -> None:
        # refer to https://learn.microsoft.com/en-us/uwp/schemas/tiles/toastschema/schema-root
        scenario = ' scenario="reminder"' if scenario else ""
        actions = (
            f"""
            <actions>
                <action
                    content="Download &amp; Install"
                    activationType="protocol"
                    arguments="{launch_url}"/>
            </actions>
            """
            if launch_url
            else ""
        )
        xml = XmlDocument()
        xml.load_xml(f"""
        <toast activationType="protocol" duration="{duration}"{scenario}>
            <visual>
                <binding template="ToastGeneric">
                    <image placement="appLogoOverride" hint-crop="circle" src="{icon_path}"/>
                    <text>{title}</text>
                    <text>{message}</text>
                </binding>
            </visual>
            {actions}
        </toast>
        """)
        notification = ToastNotification(xml)
        self.toaster.show(notification)


class ScrollingLabel(QLabel):
    """
    A QLabel that scrolls its text based on a speed parameter.
    Compatible with the default QtCSS styling.

    Args:
        parent (QWidget): The parent widget.
        text (str): The text to display.
        max_width (int): The maximum width of the label in characters.
        options (dict[str, Any]): A dictionary of options for the scrolling label.
            update_interval_ms (int): The frequency of the scrolling update in ms (default: 33).
            style (ScrollingLabel.Style): The style of scrolling (default: ScrollingLabel.Style.SCROLL).
            separator (str): The separator between the text (only added if scrolling occurs).
            label_padding (int): The padding around the text (default: 1).
            ease_slope (int): The slope of the easing function (default: 20).
            ease_pos (float): The position of the easing function (default: 0.8).
            ease_min_value (float): The minimum value of the easing function (default: 0.5).
            always_scroll (bool): If True, scroll/right modes always scroll.
                                     If False (default), only scroll if text is wider than the label.
    """

    class Style(StrEnum):
        SCROLL_LEFT = "left"
        SCROLL_RIGHT = "right"
        BOUNCE = "bounce"
        BOUNCE_EASE = "bounce-ease"

    def __init__(
        self,
        parent: QWidget | None = None,
        text: str = "",
        max_width: int | None = None,
        options: dict[str, Any] | None = None,
    ):
        super().__init__(parent)
        if options is None:
            options = {}
        self._update_interval: int = max(min(options.get("update_interval_ms", 33), 1000), 4)
        self._ease_slope: int = options.get("ease_slope", 20)
        self._ease_pos: float = options.get("ease_pos", 0.8)
        self._ease_min: float = max(min(options.get("ease_min_value", 0.5), 1), 0.2)
        self._style = ScrollingLabel.Style(options.get("style", "left"))
        self._always_scroll: bool = options.get("always_scroll", False)

        self._separator_str = ""
        if self._style not in {self.Style.BOUNCE, self.Style.BOUNCE_EASE}:
            self._separator_str = options.get("separator", " ")

        self._label_padding_chars = ""
        if self._style in {self.Style.BOUNCE, self.Style.BOUNCE_EASE}:
            self._label_padding_chars = " " * options.get("label_padding", 1)

        self._max_width = max_width
        self._margin = self.contentsMargins()
        self._bounce_direction = -1
        self._offset = 0
        self._scrolling_needed = False

        # Store the original, un-padded/un-separated text
        self._raw_text = text
        self._text = ""  # Will be built by _build_text_and_metrics

        # Initialize metrics and text
        self._font_metrics = QFontMetrics(self.font())
        self._build_text_and_metrics()

        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._scroll_text)
        self._scroll_timer.start(self._update_interval)

    def _ease(self, offset: int, max_offset: int, slope: int = 20, pos: float = 0.8, min_value: float = 0.5) -> float:
        """
        Ease function for scrolling labels in bounce ease mode
        Returns a value between `min_value` and 1.0 based on the offset.
        The value is 1.0 at the center and drops to `min_value` at the ends.
        Demo: https://www.desmos.com/calculator/j7eamemxzi
        """
        x = abs(2 * (offset / max_offset) - 1 if max_offset else 0)
        return (1 + math.tanh(-slope * (x - pos))) * (1 - min_value) / 2 + min_value

    @override
    def setText(self, a0: str | None):
        super().setText(a0)
        self._offset = 0
        self._raw_text = a0 or ""

        # Re-build text, re-calculate metrics, and check for scrolling
        self._build_text_and_metrics()
        # Update offset immediately based on new state
        self._scroll_text()

    def _build_text_and_metrics(self):
        """
        Builds the final text string and updates all text metrics.
        This resolves the dependency between scrolling state and the separator.
        """
        self.ensurePolished()
        self._margin = self.contentsMargins()
        self._font_metrics = QFontMetrics(self.font())

        label_width = self.width() - self._margin.left() - self._margin.right()

        # First, determine scrolling state based on raw text
        base_text = self._label_padding_chars + self._raw_text + self._label_padding_chars
        base_bb_width = self._font_metrics.boundingRect(base_text).width()
        text_is_wider = base_bb_width > label_width

        if self._style in {ScrollingLabel.Style.SCROLL_LEFT, ScrollingLabel.Style.SCROLL_RIGHT}:
            self._scrolling_needed = self._always_scroll or text_is_wider
        elif self._style in {ScrollingLabel.Style.BOUNCE, ScrollingLabel.Style.BOUNCE_EASE}:
            self._scrolling_needed = text_is_wider
        else:
            self._scrolling_needed = False

        # Build the final text string based on scrolling state
        if self._scrolling_needed and self._style in {
            ScrollingLabel.Style.SCROLL_LEFT,
            ScrollingLabel.Style.SCROLL_RIGHT,
        }:
            # Add separator only if scrolling
            self._text = self._label_padding_chars + self._raw_text + self._separator_str + self._label_padding_chars
        else:
            # No separator if not scrolling or bounce mode
            self._text = self._label_padding_chars + self._raw_text + self._label_padding_chars

        # Prepare QStaticText and update metrics based on final text
        self._static_text = QStaticText(self._text)
        self._static_text.prepare(QTransform(), self.font())

        self._text_width = max(self._font_metrics.horizontalAdvance(self._text), 1)
        self._text_bb_width = self._font_metrics.boundingRect(self._text).width()
        self._text_y = (self.height() + self._font_metrics.ascent() - self._font_metrics.descent() + 1) // 2

        if self._max_width:
            self.setMaximumWidth(self._font_metrics.averageCharWidth() * self._max_width)

    @pyqtSlot()
    def _scroll_text(self):
        """Update the offset based on the state calculated in _build_text_and_metrics()"""
        if not self._scrolling_needed:
            label_width = self.width() - self._margin.left() - self._margin.right()
            if self._style in {ScrollingLabel.Style.BOUNCE, ScrollingLabel.Style.BOUNCE_EASE}:
                self._offset = (self._text_width - label_width) // 2  # Center the text
            else:
                self._offset = 0  # Reset to left-aligned

            # For bounce-ease, reset interval when not scrolling
            if self._style == ScrollingLabel.Style.BOUNCE_EASE:
                self._scroll_timer.setInterval(self._update_interval)
        else:  # Scrolling is needed
            if self._style == ScrollingLabel.Style.SCROLL_LEFT:
                self._offset += 1
            elif self._style == ScrollingLabel.Style.SCROLL_RIGHT:
                self._offset -= 1
            elif self._style in {ScrollingLabel.Style.BOUNCE, ScrollingLabel.Style.BOUNCE_EASE}:
                label_width = self.width() - self._margin.left() - self._margin.right()
                max_offset = self._text_width - label_width
                if self._style == ScrollingLabel.Style.BOUNCE_EASE:
                    easing_factor = self._ease(
                        self._offset,
                        max_offset,
                        self._ease_slope,
                        self._ease_pos,
                        self._ease_min,
                    )
                    new_interval = int(self._update_interval * 1 / easing_factor)
                    self._scroll_timer.setInterval(new_interval)
                self._offset += self._bounce_direction
                if self._offset >= max_offset:
                    self._offset = max_offset
                    self._bounce_direction = -1
                elif self._offset <= 0:
                    self._offset = 0
                    self._bounce_direction = 1
        if self.isVisible():
            self.update()

    @override
    def paintEvent(self, a0: QPaintEvent | None):
        painter = QPainter(self)

        content_rect = QRect(
            self._margin.left(),
            self._margin.top(),
            self.width() - self._margin.left() - self._margin.right(),
            self.height() - self._margin.top() - self._margin.bottom(),
        )
        painter.setClipRect(content_rect)

        x = self._margin.left() - self._offset
        text_y = self._text_y - self._font_metrics.ascent()

        if self._style == ScrollingLabel.Style.SCROLL_LEFT:
            if self._scrolling_needed:
                extra_text = x - self._text_width
                painter.drawStaticText(extra_text, text_y, self._static_text)
                while x < self._margin.left() + content_rect.width():
                    painter.drawStaticText(x, text_y, self._static_text)
                    x += self._text_width
            else:
                painter.drawStaticText(self._margin.left(), text_y, self._static_text)

        elif self._style == ScrollingLabel.Style.SCROLL_RIGHT:
            if self._scrolling_needed:
                extra_text = x + self._text_width
                painter.drawStaticText(extra_text, text_y, self._static_text)
                while x > self._margin.left() - self._text_width:
                    painter.drawStaticText(x, text_y, self._static_text)
                    x -= self._text_width
            else:
                painter.drawStaticText(self._margin.left(), text_y, self._static_text)

        elif self._style in {ScrollingLabel.Style.BOUNCE, ScrollingLabel.Style.BOUNCE_EASE}:
            x = self._margin.left() - self._offset
            painter.drawStaticText(x, text_y, self._static_text)

    def sizeHint(self) -> QSize:
        # Use metrics we already have if possible.
        if not hasattr(self, "_font_metrics"):
            self._font_metrics = QFontMetrics(self.font())
        if not hasattr(self, "_margin"):
            self._margin = self.contentsMargins()

        # Calculate hint based on raw text + padding, not the final text
        base_text = self._label_padding_chars + self._raw_text + self._label_padding_chars
        b_rect = self._font_metrics.boundingRect(base_text)

        width = max(1, b_rect.width() + self._margin.left() + self._margin.right())
        height = max(1, b_rect.height() + self._margin.top() + self._margin.bottom())
        return QSize(min(self.maximumWidth(), width), min(self.maximumHeight(), height))

    @override
    def resizeEvent(self, a0: QResizeEvent | None):
        super().resizeEvent(a0)
        # Re-build text, re-calculate metrics, and check for scrolling
        self._build_text_and_metrics()
        # Update offset immediately based on new state
        self._scroll_text()


class Singleton(type):
    """Singleton metaclass for regular python classes"""

    _instances: dict[Any, Any] = {}
    _lock = Lock()

    def __call__(cls, *args: Any, **kwargs: Any):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]


class QSingleton(type(QObject)):
    """Singleton metaclass for Qt classes"""

    _instances: dict[Any, Any] = {}
    _lock = Lock()

    def __call__(cls, *args: Any, **kwargs: Any):
        with cls._lock:
            if cls not in cls._instances or sip.isdeleted(cls._instances[cls]):
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]
