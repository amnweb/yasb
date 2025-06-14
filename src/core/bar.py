import logging

import win32gui
from PyQt6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QScreen
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QWidget

from core.event_service import EventService
from core.utils.utilities import is_valid_percentage_str, percent_to_float
from core.utils.win32.blurWindow import Blur
from core.utils.win32.utilities import get_monitor_hwnd
from core.validation.bar import BAR_DEFAULTS
from settings import APP_BAR_TITLE

try:
    from core.utils.win32 import app_bar

    IMPORT_APP_BAR_MANAGER_SUCCESSFUL = True
except ImportError:
    IMPORT_APP_BAR_MANAGER_SUCCESSFUL = False


class AutoHideZone(QFrame):
    """A transparent zone at the edge of the screen to detect when to show the bar"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setWindowOpacity(0.01)

    def enterEvent(self, event):
        # Show the parent bar when mouse enters detection zone
        if self.parent():
            self.parent()._show_bar()


class Bar(QWidget):
    handle_bar_management = pyqtSignal(str, str)

    def __init__(
        self,
        bar_id: str,
        bar_name: str,
        bar_screen: QScreen,
        stylesheet: str,
        widgets: dict[str, list],
        layouts: dict[str, dict[str, bool | str]],
        init: bool = False,
        class_name: str = BAR_DEFAULTS["class_name"],
        alignment: dict = BAR_DEFAULTS["alignment"],
        blur_effect: dict = BAR_DEFAULTS["blur_effect"],
        animation: dict = BAR_DEFAULTS["animation"],
        window_flags: dict = BAR_DEFAULTS["window_flags"],
        dimensions: dict = BAR_DEFAULTS["dimensions"],
        padding: dict = BAR_DEFAULTS["padding"],
    ):
        super().__init__()
        self._event_service = EventService()
        self.hide()
        self.setScreen(bar_screen)
        self._bar_id = bar_id
        self._bar_name = bar_name
        self._alignment = alignment
        self._window_flags = window_flags
        self._dimensions = dimensions
        self._padding = padding
        self._animation = animation
        self._is_dark_theme = None
        self._layouts = layouts

        self.screen_name = self.screen().name()
        self.app_bar_edge = (
            app_bar.AppBarEdge.Top if self._alignment["position"] == "top" else app_bar.AppBarEdge.Bottom
        )

        if self._window_flags["windows_app_bar"] and IMPORT_APP_BAR_MANAGER_SUCCESSFUL:
            self.app_bar_manager = app_bar.Win32AppBar()
        else:
            self.app_bar_manager = None

        self.setWindowTitle(APP_BAR_TITLE)
        self.setStyleSheet(stylesheet)
        self.setWindowFlag(Qt.WindowType.Tool)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        if self._window_flags["always_on_top"]:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        self._bar_frame = QFrame(self)
        self._bar_frame.setProperty("class", f"bar {class_name}")
        self.update_theme_class()

        self.position_bar(init)
        self.monitor_hwnd = get_monitor_hwnd(int(self.winId()))
        self._add_widgets(widgets)

        if blur_effect["enabled"]:
            Blur(
                self.winId(),
                Acrylic=blur_effect["acrylic"],
                DarkMode=blur_effect["dark_mode"],
                RoundCorners=blur_effect["round_corners"],
                RoundCornersType=blur_effect["round_corners_type"],
                BorderColor=blur_effect["border_color"],
            )

        self.screen().geometryChanged.connect(self.on_geometry_changed, Qt.ConnectionType.QueuedConnection)

        self.handle_bar_management.connect(self._handle_bar_management)
        self._event_service.register_event("handle_bar_cli", self.handle_bar_management)

        self._autohide_bar = self._window_flags["auto_hide"]

        if self._autohide_bar:
            self._autohide_delay = 400  # default delay before hiding the bar
            self._detection_zone_height = (
                1 + self._padding["top"] if self._alignment["position"] == "top" else 1 + self._padding["bottom"]
            )

            self._detection_zone = AutoHideZone(self)

            self._hide_timer = QTimer(self)
            self._hide_timer.setSingleShot(True)
            self._hide_timer.timeout.connect(self._hide_bar)

            self.installEventFilter(self)
            # If the bar is initialized with auto-hide, set up the detection zone after a short delay
            QTimer.singleShot(1000, self._setup_autohide_zone)

        self.show()

    @property
    def bar_id(self) -> str:
        return self._bar_id

    def on_geometry_changed(self, geo: QRect) -> None:
        logging.info(f"Screen geometry changed. Updating position for bar ({self.bar_id})")
        self.position_bar()

        if self._autohide_bar:
            self._setup_autohide_zone()

    def try_add_app_bar(self, scale_screen_height=False) -> None:
        if self.app_bar_manager:
            self.app_bar_manager.create_appbar(
                self.winId().__int__(),
                self.app_bar_edge,
                self._dimensions["height"] + self._padding["top"] + self._padding["bottom"],
                self.screen(),
                scale_screen_height,
            )

    def closeEvent(self, event):
        self.try_remove_app_bar()

    def try_remove_app_bar(self) -> None:
        if self.app_bar_manager:
            self.app_bar_manager.remove_appbar()

    def bar_pos(self, bar_w: int, bar_h: int, screen_w: int, screen_h: int) -> tuple[int, int]:
        screen_x = self.screen().geometry().x()
        screen_y = self.screen().geometry().y()
        x = int(screen_x + (screen_w / 2) - (bar_w / 2)) if self._alignment["center"] else screen_x

        if self._alignment["position"] == "bottom":
            y = int(screen_y + screen_h - bar_h - self._padding["bottom"])
        else:
            y = screen_y

        return x, y

    def position_bar(self, init=False) -> None:
        bar_width = self._dimensions["width"]
        bar_height = self._dimensions["height"]

        screen_width = self.screen().geometry().width()
        screen_height = self.screen().geometry().height()

        scale_state = self.screen().devicePixelRatio() > 1.0

        if is_valid_percentage_str(str(self._dimensions["width"])):
            bar_width = int(
                screen_width * percent_to_float(self._dimensions["width"])
                - self._padding["left"]
                - self._padding["right"]
            )
        bar_x, bar_y = self.bar_pos(bar_width, bar_height, screen_width, screen_height)
        bar_x = bar_x + self._padding["left"]

        if self._alignment["position"] == "top":
            bar_y = bar_y + self._padding["top"]

        self.setGeometry(bar_x, bar_y, bar_width, bar_height)
        self._bar_frame.setGeometry(0, 0, bar_width, bar_height)
        self.try_add_app_bar(scale_screen_height=scale_state)

    def _add_widgets(self, widgets: dict[str, list] = None):
        bar_layout = QGridLayout()
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        for column_num, layout_type in enumerate(["left", "center", "right"]):
            config = self._layouts[layout_type]
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout_container = QFrame()
            layout_container.setProperty("class", f"container container-{layout_type}")

            # Add widgets
            if layout_type in widgets:
                for widget in widgets[layout_type]:
                    widget.parent_layout_type = layout_type
                    widget.bar_id = self.bar_id
                    widget.monitor_hwnd = self.monitor_hwnd
                    layout.addWidget(widget, 0)

            if config["alignment"] == "left" and config["stretch"]:
                layout.addStretch(1)

            elif config["alignment"] == "right" and config["stretch"]:
                layout.insertStretch(0, 1)

            elif config["alignment"] == "center" and config["stretch"]:
                layout.insertStretch(0, 1)
                layout.addStretch(1)

            layout_container.setLayout(layout)
            bar_layout.addWidget(layout_container, 0, column_num)

        self._bar_frame.setLayout(bar_layout)

    def show_bar(self):
        self.setWindowOpacity(0.0)
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(self._animation["duration"])
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.opacity_animation.start()

    def hide_bar(self):
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(self._animation["duration"])
        self.opacity_animation.setStartValue(1.0)
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.opacity_animation.finished.connect(self._on_hide_bar_finished)
        self.opacity_animation.start()

    def _on_hide_bar_finished(self):
        super().hide()
        self.setWindowOpacity(1.0)

    def showEvent(self, event):
        super().showEvent(event)
        if self._animation["enabled"]:
            try:
                self.show_bar()

            except AttributeError:
                logging.error("Animation not initialized.")
        if (
            not hasattr(self, "_fullscreen_timer")
            and self._window_flags["hide_on_fullscreen"]
            and self._window_flags["always_on_top"]
        ):
            self._fullscreen_timer = QTimer(self)
            self._fullscreen_timer.setInterval(500)
            self._fullscreen_timer.timeout.connect(self.is_foreground_fullscreen)
            self._fullscreen_timer.start()

    def hide(self):
        if self.isVisible() and self._animation["enabled"]:
            self.hide_bar()
        else:
            super().hide()

    def is_foreground_fullscreen(self):
        """Check if the active foreground window is in fullscreen mode."""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return

        class_name = win32gui.GetClassName(hwnd)
        if class_name in ("Progman", "WorkerW", "XamlWindow"):
            return
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        window_rect = (left, top, right - left, bottom - top)

        screen_geometry = self.screen().geometry()
        screen_rect = (screen_geometry.x(), screen_geometry.y(), screen_geometry.width(), screen_geometry.height())

        self.dpi = self.screen().devicePixelRatio()
        scaled_screen_rect = screen_rect[:2] + tuple(round(dim * self.dpi) for dim in screen_rect[2:])
        is_fullscreen = window_rect == scaled_screen_rect
        if getattr(self, "_prev_fullscreen_state", None) == is_fullscreen:
            return

        self._prev_fullscreen_state = is_fullscreen
        if is_fullscreen and self.isVisible():
            self.hide()
        elif not is_fullscreen and not self.isVisible():
            self.show()

    def detect_os_theme(self) -> bool:
        try:
            import winreg

            with winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER) as registry:
                with winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    return value == 0
        except Exception as e:
            logging.error(f"Failed to determine Windows theme: {e}")
            return False

    def update_theme_class(self):
        if not hasattr(self, "_bar_frame"):
            return

        is_dark_theme = self.detect_os_theme()
        if is_dark_theme != self._is_dark_theme:
            class_property = self._bar_frame.property("class")
            if is_dark_theme:
                class_property += " dark"
            else:
                class_property = class_property.replace(" dark", "")
            self._bar_frame.setProperty("class", class_property)
            update_styles(self._bar_frame)
            self._is_dark_theme = is_dark_theme

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.PaletteChange:
            self.update_theme_class()
        super().changeEvent(event)

    def _handle_bar_management(self, action, screen_name):
        current_screen_matches = not screen_name or self.screen().name() == screen_name
        if current_screen_matches:
            if action == "show":
                self.show()
            elif action == "hide":
                self.hide()
            elif action == "toggle":
                if self.isVisible():
                    self.hide()
                else:
                    self.show()

    def _setup_autohide_zone(self):
        """Position and configure the autohide detection zone"""
        screen_geometry = self.screen().geometry()

        if self._alignment["position"] == "top":
            self._detection_zone.setGeometry(
                screen_geometry.x(), screen_geometry.y(), screen_geometry.width(), self._detection_zone_height
            )
        else:
            self._detection_zone.setGeometry(
                screen_geometry.x(),
                screen_geometry.y() + screen_geometry.height() - self._detection_zone_height,
                screen_geometry.width(),
                self._detection_zone_height,
            )

        # Start autohide timer
        self._hide_timer.start(self._autohide_delay)

    def _show_bar(self):
        """Show the bar when mouse hovers over detection zone"""
        if not self.isVisible() and self._autohide_bar:
            self.show()

    def _hide_bar(self):
        """Hide the bar and show detection zone"""
        if self._autohide_bar and self.isVisible():
            self.hide()
            self._detection_zone.show()
            self._detection_zone.raise_()

    def eventFilter(self, watched, event):
        """Filter events to detect mouse movement"""
        if watched == self and self._autohide_bar:
            if event.type() == QEvent.Type.Enter:
                # Mouse entered the bar, stop hide timer
                self._hide_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                # Mouse left the bar, start hide timer
                cursor_pos = QCursor.pos()
                bar_geometry = self.geometry()
                # Only start timer if mouse is really outside the bar
                if not bar_geometry.contains(cursor_pos):
                    self._hide_timer.start(self._autohide_delay)
        return super().eventFilter(watched, event)


def update_styles(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    for child in widget.findChildren(QWidget):
        child.style().unpolish(child)
        child.style().polish(child)
