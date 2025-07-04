import math
import os
import platform
import re
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, cast, override

import psutil
from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, pyqtSlot
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
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QLabel, QMenu, QWidget
from winrt.windows.data.xml.dom import XmlDocument
from winrt.windows.ui.notifications import ToastNotification, ToastNotificationManager

from core.utils.win32.blurWindow import Blur


def app_data_path(filename: str = None) -> Path:
    """
    Get the Yasb local data folder (creating it if it doesn't exist),
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
        return "Yasb"


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

        # Create the inner frame
        self._popup_content = QFrame(self)

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
        self.activateWindow()
        super().showEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            global_pos = event.globalPosition().toPoint()

            # Check if click is inside popup
            if self.geometry().contains(global_pos):
                return super().eventFilter(obj, event)

            # Check if click is inside any visible QMenu child
            for menu in self.findChildren(QMenu):
                menu_global_geom = menu.geometry().translated(menu.mapToGlobal(QPoint(0, 0)))
                if menu.isVisible() and menu_global_geom.contains(global_pos):
                    return super().eventFilter(obj, event)

            # Otherwise, close all open QMenus first
            for menu in self.findChildren(QMenu):
                if menu.isVisible():
                    menu.close()

            if not self.geometry().contains(global_pos):
                self.hide()
                self.deleteLater()
                return True
        return super().eventFilter(obj, event)

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)

        try:
            bar_el = self.parent()
            while bar_el and not hasattr(bar_el, "_autohide_bar"):
                bar_el = bar_el.parent()

            if bar_el and bar_el._autohide_manager and bar_el._autohide_manager.is_enabled():
                # Check if parent needs autohide
                if bar_el._autohide_manager.is_enabled():
                    # Get current cursor position
                    from PyQt6.QtGui import QCursor

                    cursor_pos = QCursor.pos()
                    # If mouse is outside the bar, start the hide timer
                    if not bar_el.geometry().contains(cursor_pos):
                        if bar_el._autohide_manager._hide_timer:
                            bar_el._autohide_manager._hide_timer.start(bar_el._autohide_manager._autohide_delay)
        except Exception:
            pass

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
            separator (str): The separator between the text and the scrolling label (default: " ").
            label_padding (int): The padding around the text (default: 1).
            ease_slope (int): The slope of the easing function (default: 20).
            ease_pos (float): The position of the easing function (default: 0.8).
            ease_min_value (float): The minimum value of the easing function (default: 0.5).
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

        self._separator = ""
        if self._style not in {self.Style.BOUNCE, self.Style.BOUNCE_EASE}:
            self._separator = options.get("separator", " ")

        self._label_padding_chars = ""
        if self._style in {self.Style.BOUNCE, self.Style.BOUNCE_EASE}:
            self._label_padding_chars = " " * options.get("label_padding", 1)

        self._max_width = max_width
        self._margin = self.contentsMargins()
        self._bounce_direction = -1
        self._offset = 0

        self._text = text
        self.setText(self._text)

        self._scroll_timer = QTimer(self)
        self._scroll_timer.timeout.connect(self._scroll_text)  # pyright: ignore[reportUnknownMemberType]
        self._update_text_metrics()
        self._scroll_timer.start(self._update_interval)

    def _ease(
        self,
        offset: int,
        max_offset: int,
        slope: int = 20,
        pos: float = 0.8,
        min_value: float = 0.5,
    ) -> float:
        """
        Ease function for scrolling labels in bounce ease mode
        Returns a value between 0 and 1 based on the offset and max_offset.
        Demo: https://www.desmos.com/calculator/j7eamemxzi
        """
        x = abs(2 * (offset / max_offset) - 1 if max_offset else 0)
        return (1 + math.tanh(-slope * (x - pos))) * (1 - min_value) / 2 + min_value

    @override
    def setText(self, a0: str | None):
        super().setText(a0)
        self._offset = 0
        self._text = ""
        if a0 is not None:
            self._text = self._label_padding_chars + a0 + self._separator + self._label_padding_chars
            self._static_text = QStaticText(self._text)
            self._static_text.prepare(QTransform(), self.font())
        self._update_text_metrics()
        self._scroll_text()  # scroll once to avoid flickering

    @pyqtSlot()
    def _scroll_text(self):
        if self._style == ScrollingLabel.Style.SCROLL_LEFT:
            self._offset += 1
        elif self._style == ScrollingLabel.Style.SCROLL_RIGHT:
            self._offset -= 1
        elif self._style in {ScrollingLabel.Style.BOUNCE, ScrollingLabel.Style.BOUNCE_EASE}:
            label_width = self.width() - self._margin.left() - self._margin.right()
            if self._text_bb_width <= label_width:
                self._offset = (self._text_width - label_width) // 2  # center the text
            else:
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

    def _update_text_metrics(self):
        self.ensurePolished()
        self._margin = self.contentsMargins()
        self._font_metrics = QFontMetrics(self.font())
        self._text_width = max(self._font_metrics.horizontalAdvance(self._text), 1)
        self._text_bb_width = self._font_metrics.boundingRect(self._text).width()
        self._text_y = (self.height() + self._font_metrics.ascent() - self._font_metrics.descent() + 1) // 2
        if self._max_width:
            self.setMaximumWidth(self._font_metrics.averageCharWidth() * self._max_width)

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
            extra_text = x - self._text_width
            painter.drawStaticText(extra_text, text_y, self._static_text)
            while x < self._margin.left() + content_rect.width():
                painter.drawStaticText(x, text_y, self._static_text)
                x += self._text_width
        elif self._style == ScrollingLabel.Style.SCROLL_RIGHT:
            extra_text = x + self._text_width
            painter.drawStaticText(extra_text, text_y, self._static_text)
            while x > self._margin.left() - self._text_width:
                painter.drawStaticText(x, text_y, self._static_text)
                x -= self._text_width
        elif self._style in {ScrollingLabel.Style.BOUNCE, ScrollingLabel.Style.BOUNCE_EASE}:
            x = self._margin.left() - self._offset
            painter.drawStaticText(x, text_y, self._static_text)

    def sizeHint(self) -> QSize:
        self._update_text_metrics()
        b_rect = self._font_metrics.boundingRect(self._text)
        width = max(1, b_rect.width() + self._margin.left() + self._margin.right())
        height = max(1, b_rect.height() + self._margin.top() + self._margin.bottom())
        return QSize(min(self.maximumWidth(), width), min(self.maximumHeight(), height))

    @override
    def resizeEvent(self, a0: QResizeEvent | None):
        super().resizeEvent(a0)
        self._update_text_metrics()


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
