import logging

import win32con
from PyQt6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QWidget

from core.bar_helper import AutoHideManager, BarContextMenu, FullscreenManager, OsThemeManager
from core.event_service import EventService
from core.utils.utilities import is_valid_percentage_str, percent_to_float
from core.utils.win32.bindings import user32
from core.utils.win32.utilities import get_monitor_hwnd
from core.utils.win32.win32_accent import Blur
from core.validation.bar import BAR_DEFAULTS
from settings import APP_BAR_TITLE

try:
    from core.utils.win32 import app_bar

    IMPORT_APP_BAR_MANAGER_SUCCESSFUL = True
except ImportError:
    IMPORT_APP_BAR_MANAGER_SUCCESSFUL = False


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
        widget_config: dict = None,
        init: bool = False,
        class_name: str = BAR_DEFAULTS["class_name"],
        context_menu: bool = BAR_DEFAULTS["context_menu"],
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
        self._align = self._alignment["align"]
        self._window_flags = window_flags
        self._dimensions = dimensions
        self._padding = padding
        self._animation = animation
        self._context_menu = context_menu
        self._layouts = layouts
        self._autohide_bar = self._window_flags["auto_hide"]
        self._widgets = widgets  # Store widgets reference for context menu
        self._widget_config_map = widget_config or {}
        self._is_auto_width = str(dimensions["width"]).lower() == "auto"
        self._current_auto_width = 0
        self._os_theme_manager = None
        self._fullscreen_manager = None
        self._autohide_manager = None
        self._target_screen = bar_screen

        self.screen_name = self._target_screen.name()
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

        # Initialize the OS theme manager
        try:
            self._os_theme_manager = OsThemeManager(self._bar_frame, self)
            self._os_theme_manager.update_theme_class()
        except Exception as e:
            logging.error(f"Failed to initialize theme manager: {e}")
            self._os_theme_manager = None

        # Initialize fullscreen manager
        if self._window_flags["hide_on_fullscreen"] and self._window_flags["always_on_top"]:
            try:
                self._fullscreen_manager = FullscreenManager(self, self)
            except Exception as e:
                logging.error(f"Failed to initialize fullscreen manager: {e}")
                self._fullscreen_manager = None

        self.position_bar(init)
        self.monitor_hwnd = get_monitor_hwnd(int(self.winId()))

        self._add_widgets(widgets)

        if self._is_auto_width:
            self._bar_frame.installEventFilter(self)
            QTimer.singleShot(0, self._sync_auto_width)

        if not self._window_flags["windows_app_bar"]:
            try:
                hwnd = int(self.winId())
                exStyle = user32.GetWindowLongPtrW(hwnd, win32con.GWL_EXSTYLE)
                user32.SetWindowLongPtrW(hwnd, win32con.GWL_EXSTYLE, exStyle | win32con.WS_EX_NOACTIVATE)
            except Exception:
                pass

        if blur_effect["enabled"]:
            Blur(
                self.winId(),
                Acrylic=blur_effect["acrylic"],
                DarkMode=blur_effect["dark_mode"],
                RoundCorners=blur_effect["round_corners"],
                RoundCornersType=blur_effect["round_corners_type"],
                BorderColor=blur_effect["border_color"],
            )

        self._target_screen.geometryChanged.connect(self.on_geometry_changed, Qt.ConnectionType.QueuedConnection)

        self.handle_bar_management.connect(self._handle_bar_management)
        self._event_service.register_event("handle_bar_cli", self.handle_bar_management)

        # Initialize autohide manager
        if self._window_flags["auto_hide"]:
            self._autohide_manager = AutoHideManager(self, self)
            self._autohide_manager.setup_autohide()

        self.show()

    @property
    def bar_id(self) -> str:
        return self._bar_id

    def on_geometry_changed(self, geo: QRect) -> None:
        logging.info(
            f"Screen geometry changed. Updating position for bar {self._bar_name} on screen {self._target_screen.name()}"
        )
        self.position_bar()

        if self._autohide_manager and self._autohide_manager.is_enabled():
            self._autohide_manager.setup_detection_zone()

        if self._is_auto_width:
            QTimer.singleShot(0, self._sync_auto_width)

    def try_add_app_bar(self, scale_screen_height=False) -> None:
        if self.app_bar_manager:
            self.app_bar_manager.create_appbar(
                self.winId().__int__(),
                self.app_bar_edge,
                self._dimensions["height"] + self._padding["top"] + self._padding["bottom"],
                self._target_screen,
                scale_screen_height,
                self._bar_name,
            )

    def try_remove_app_bar(self) -> None:
        if self.app_bar_manager:
            self.app_bar_manager.remove_appbar()

    def bar_pos(self, bar_w: int, bar_h: int, screen_w: int, screen_h: int) -> tuple[int, int]:
        screen_x = self._target_screen.geometry().x()
        screen_y = self._target_screen.geometry().y()

        if self._align == "center" or self._alignment.get("center", False):
            available_x = screen_x + self._padding["left"]
            available_width = screen_w - self._padding["left"] - self._padding["right"]
            if bar_w >= available_width:
                x = available_x
            else:
                x = int(available_x + (available_width - bar_w) / 2)
        elif self._align == "right":
            x = int(screen_x + screen_w - bar_w - self._padding["right"])
            min_x = screen_x + self._padding["left"]
            if x < min_x:
                x = min_x
        else:
            x = int(screen_x + self._padding["left"])
            max_x = screen_x + screen_w - bar_w - self._padding["right"]
            if x > max_x:
                x = max_x

        if self._alignment["position"] == "bottom":
            y = int(screen_y + screen_h - bar_h - self._padding["bottom"])
        else:
            y = int(screen_y + self._padding["top"])

        return x, y

    def position_bar(self, init=False) -> None:
        bar_width = self._dimensions["width"]
        bar_height = self._dimensions["height"]

        screen_width = self._target_screen.geometry().width()
        screen_height = self._target_screen.geometry().height()

        scale_state = self._target_screen.devicePixelRatio() > 1.0

        if self._is_auto_width:
            if self._bar_frame.layout() is not None:
                bar_width = self._update_auto_width()
            else:
                bar_width = 0

        elif is_valid_percentage_str(str(self._dimensions["width"])):
            percent = percent_to_float(self._dimensions["width"])
            bar_width = int(screen_width * percent)

        # Ensure bar width does not exceed screen width
        available_width = screen_width - self._padding["left"] - self._padding["right"]
        if bar_width > available_width:
            bar_width = available_width

        bar_x, bar_y = self.bar_pos(bar_width, bar_height, screen_width, screen_height)

        self.setGeometry(bar_x, bar_y, bar_width, bar_height)
        self._bar_frame.setGeometry(0, 0, bar_width, bar_height)
        self.try_add_app_bar(scale_screen_height=scale_state)

    def _update_auto_width(self) -> int:
        """Calculate the current auto width based on the layout's size hint."""
        layout = self._bar_frame.layout()
        if layout:
            layout.activate()

        requested = max(self._bar_frame.sizeHint().width(), 0)
        available = self._target_screen.geometry().width() - self._padding["left"] - self._padding["right"]
        new_width = min(requested, available)
        self._current_auto_width = new_width
        return new_width

    def _apply_auto_width(self, new_width: int) -> None:
        """Resize and reposition the bar using the supplied auto width."""
        if new_width < 0:
            return

        bar_height = self._dimensions["height"]
        screen_geometry = self._target_screen.geometry()
        bar_x, bar_y = self.bar_pos(
            new_width,
            bar_height,
            screen_geometry.width(),
            screen_geometry.height(),
        )

        self.setGeometry(bar_x, bar_y, new_width, bar_height)
        self._bar_frame.setGeometry(0, 0, new_width, bar_height)

    def _sync_auto_width(self) -> None:
        """Ensure auto width matches the layout after a DPI/geometry."""
        previous_width = self._current_auto_width
        new_width = self._update_auto_width()

        if new_width != previous_width or self.width() != new_width:
            self._apply_auto_width(new_width)

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

        # Start fullscreen monitoring when bar is shown
        if self._fullscreen_manager and not hasattr(self, "_fullscreen_monitoring_started"):
            self._fullscreen_manager.start_monitoring()
            self._fullscreen_monitoring_started = True

    def closeEvent(self, event):
        if self._fullscreen_manager:
            self._fullscreen_manager.stop_monitoring()
        if self._autohide_manager:
            self._autohide_manager.cleanup()
        self.try_remove_app_bar()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.PaletteChange:
            if self._os_theme_manager:
                self._os_theme_manager.update_theme_class()
        super().changeEvent(event)

    def eventFilter(self, obj, event):
        if self._is_auto_width and obj == self._bar_frame and event.type() == QEvent.Type.LayoutRequest:
            previous_width = self._current_auto_width
            new_width = self._update_auto_width()
            if new_width != previous_width:
                self._apply_auto_width(new_width)

        return super().eventFilter(obj, event)

    def hide(self):
        if self.isVisible() and self._animation["enabled"]:
            self.hide_bar()
        else:
            super().hide()

    def _handle_bar_management(self, action, screen_name):
        current_screen_matches = not screen_name or self._target_screen.name() == screen_name
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

    def contextMenuEvent(self, event):
        """Handle right-click context menu"""
        if not self._context_menu:
            return

        widget_at_pos = self.childAt(event.pos())
        # If the click is on a widget, ignore the context menu
        if widget_at_pos and widget_at_pos != self._bar_frame and widget_at_pos != self:
            parent_widget = widget_at_pos
            while parent_widget and parent_widget != self:
                if hasattr(parent_widget, "parent_layout_type"):
                    event.ignore()
                    return
                parent_widget = parent_widget.parent()

        BarContextMenu(
            parent=self,
            bar_name=self._bar_name,
            widgets=self._widgets,
            widget_config_map=self._widget_config_map,
            autohide_bar=self._autohide_bar,
        ).show(event.pos())
