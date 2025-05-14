from functools import lru_cache
import platform
import re
from typing import Any, cast

from winrt.windows.data.xml.dom import XmlDocument
from winrt.windows.ui.notifications import (
    ToastNotification,
    ToastNotificationManager,
)

import psutil
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QColor, QScreen
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QLabel, QWidget

from core.utils.win32.blurWindow import Blur

from PIL import Image, ImageOps, ImageEnhance, ImageColor
import colorsys

def is_windows_10() -> bool:
    version = platform.version()
    return bool(re.match(r'^10\.0\.1\d{4}$', version))

def is_process_running(process_name: str) -> bool:
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"] == process_name:
            return True
    return False

def percent_to_float(percent: str) -> float:
    return float(percent.strip('%')) / 100.0

def is_valid_percentage_str(s: str) -> bool:
    return s.endswith("%") and len(s) <= 4 and s[:-1].isdigit()

def get_screen_by_name(screen_name: str) -> QScreen:
    return next(filter(lambda scr: screen_name in scr.name(), QApplication.screens()), None)


def add_shadow(el: QWidget, options: dict[str, Any]) -> None:
    """"Add a shadow effect to a given element."""
    if not options["enabled"]:
        return

    shadow_effect = QGraphicsDropShadowEffect(el)
    shadow_effect.setOffset(options["offset"][0], options["offset"][1])
    shadow_effect.setBlurRadius(options["radius"])

    color = options["color"]
    if color.startswith('#'):
        color = color.lstrip('#')
        # Handle hex with alpha (#RRGGBBAA format)
        if len(color) == 8:
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            a = int(color[6:8], 16)
            shadow_effect.setColor(QColor(r, g, b, a))
        else:
            # Regular hex color without alpha
            shadow_effect.setColor(QColor('#' + color))
    else:
        # Named colors like "black", "red", etc.
        shadow_effect.setColor(QColor(color))

    el.setGraphicsEffect(shadow_effect)

def build_widget_label(self, content: str, content_alt: str = None, content_shadow: dict = None):
    def process_content(content, is_alt=False):
        label_parts = re.split('(<span.*?>.*?</span>)', content)
        label_parts = [part for part in label_parts if part]
        widgets = []
        for part in label_parts:
            part = part.strip()
            if not part:
                continue
            if '<span' in part and '</span>' in part:
                class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                class_result = class_name.group(2) if class_name else 'icon'
                icon = re.sub(r'<span.*?>|</span>', '', part).strip()
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
    import winreg
    import sys
    import os
    from pathlib import Path
    from settings import APP_ID

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"SOFTWARE\\Classes\\AppUserModelId\\{APP_ID}")
        winreg.CloseKey(key)
        return APP_ID
    except:
        if getattr(sys, 'frozen', False):
            # Check if YASB is installed via Scoop and if so, return the path to the executable
            # This is a workaround for the issue where the registry key doesn't exist to return the correct App name and icon
            scoop_shortcut = os.path.join(
                    os.environ.get('APPDATA', ''), 
                    "Microsoft", "Windows", "Start Menu", "Programs", "Scoop Apps", "YASB.lnk"
                )
            if Path(scoop_shortcut).exists():
                return sys.executable
        # Fallback to the default AppUserModelID
        return 'Yasb'

def recolor_icon(
    img: Image.Image,
    hex_color: str,
    highlight_strength: float,
    shadow_strength: float,
    glare_threshold: int = 235,
    min_glare_ratio: float = 0.1,
    histogram_bins: int = 20,
    brightness_range: float = 255.0,
) -> Image.Image:
    """
    Applies a color overlay to an image while preserving its shading and highlights.
    Args:
        img: Pillow image to recolor.
        hex_color: Target color in hex format.
        glare_threshold: Brightness cutoff (0-255) above which pixels are considered highlights and excluded from histogram analysis.
        min_glare_ratio: Minimum fraction of pixels that must be below glare_threshold to enable highlight filtering. If fewer pixels qualify, all pixels are used.
        histogram_bins: Number of bins for brightness histogram analysis. Higher values provide more precise brightness detection but may be affected by noise.
        brightness_range: Maximum brightness value (0-255) used for histogram normalization. Controls the scaling of brightness differences.
        highlight_strength: Controls how much the bright areas retain their original brightness (0.0-1.0). Higher values preserve more highlights.
        shadow_strength: Controls how much the dark areas retain their original darkness (0.0-1.0). Higher values preserve more shadows.
    Returns:
        Image.Image: Recolored copy of the input image.
    """
    # Copy and convert to RGBA
    result = img.convert('RGBA').copy()
    pixels = result.load()
    w, h = result.size

    # Target color HLS
    tr, tg, tb = ImageColor.getrgb(hex_color)
    target_h, target_l, target_s = colorsys.rgb_to_hls(tr / 255, tg / 255, tb / 255)

    # Collect brightness of non-transparent pixels
    brightness_vals = []
    non_transparent = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            bval = 0.299 * r + 0.587 * g + 0.114 * b
            brightness_vals.append(bval)
            non_transparent.append((x, y, bval, a))

    # Filter out glare pixels for histogram
    valid_brightness = [b for b in brightness_vals if b < glare_threshold]
    if len(valid_brightness) < min_glare_ratio * len(brightness_vals):
        valid_brightness = brightness_vals

    # Histogram
    bins = [0] * histogram_bins
    bin_width = brightness_range / histogram_bins
    for b in valid_brightness:
        idx = min(histogram_bins - 1, int(b / bin_width))
        bins[idx] += 1
    most_common_bin = bins.index(max(bins))
    center_b = (most_common_bin + 0.5) * bin_width

    # Apply recoloring
    for x, y, bval, a in non_transparent:
        delta = (bval - center_b) / (brightness_range / 2)
        # Apply different gradient intensity based on whether it's lighter or darker
        if delta > 0:
            adjusted_delta = delta * highlight_strength
        else:
            adjusted_delta = delta * shadow_strength
        new_l = max(0.0, min(1.0, target_l + adjusted_delta))
        nr, ng, nb = colorsys.hls_to_rgb(target_h, new_l, target_s)
        pixels[x, y] = (int(nr * 255), int(ng * 255), int(nb * 255), a)

    return result

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
    def __init__(self, parent=None, blur=False, round_corners=False, round_corners_type="normal", border_color="None"):
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

    def setPosition(self, alignment='left', direction='down', offset_left=0, offset_top=0):
        """
        Position the popup relative to its parent widget.
        Args:
            alignment (str): Where to align the popup - 'left', 'right', or 'center'
            direction (str): Whether popup appears above ('up') or below ('down') the parent
            offset_left (int): Horizontal offset in pixels
            offset_top (int): Vertical offset in pixels
        """
        parent = cast(QWidget, self.parent()) # parent should be a QWidget
        if not parent:
            return

        widget_global_pos = parent.mapToGlobal(QPoint(offset_left, parent.height() + offset_top))

        if direction == 'up':
            global_y = parent.mapToGlobal(QPoint(0, 0)).y() - self.height() - offset_top
            widget_global_pos = QPoint(parent.mapToGlobal(QPoint(0, 0)).x() + offset_left, global_y)

        if alignment == 'left':
            global_position = widget_global_pos
        elif alignment == 'right':
            global_position = QPoint(
                widget_global_pos.x() + parent.width() - self.width(),
                widget_global_pos.y()
            )
        elif alignment == 'center':
            global_position = QPoint(
                widget_global_pos.x() + (parent.width() - self.width()) // 2,
                widget_global_pos.y()
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
        separator.setProperty('class', 'separator')
        separator.setStyleSheet('border:none')
        layout.addWidget(separator)

    def showEvent(self, event):
        if self._blur:
            Blur(
                self.winId(),
                Acrylic=True if is_windows_10() else False,
                DarkMode=False,
                RoundCorners=False if is_windows_10() else self._round_corners,
                RoundCornersType=self._round_corners_type,
                BorderColor=self._border_color
            )
        self.activateWindow() 
        super().showEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            global_pos = event.globalPosition().toPoint()
            if not self.geometry().contains(global_pos):
                self.hide()
                self.deleteLater()
                return True
        return super().eventFilter(obj, event)

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)

    def resizeEvent(self, event):
        self._popup_content.setGeometry(0, 0, self.width(), self.height())
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

    def show(self, icon_path: str, title: str, message: str, duration: str="short") -> None:
        # refer to https://learn.microsoft.com/en-us/uwp/schemas/tiles/toastschema/schema-root
        xml = XmlDocument()
        xml.load_xml(f"""
        <toast activationType="protocol" duration="{duration}">
            <visual>
                <binding template="ToastGeneric">
                    <image placement="appLogoOverride" hint-crop="circle" src="{icon_path}"/>
                    <text>{title}</text>
                    <text>{message}</text>
                </binding>
            </visual>
        </toast>
        """)
        notification = ToastNotification(xml)
        self.toaster.show(notification)

class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
