import logging
from settings import APP_BAR_TITLE
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QGridLayout, QFrame
from PyQt6.QtGui import QScreen
from PyQt6.QtCore import Qt, QRect, QEvent, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from core.utils.utilities import is_valid_percentage_str, percent_to_float
from core.utils.win32.utilities import get_monitor_hwnd
from core.validation.bar import BAR_DEFAULTS
from core.utils.win32.blurWindow import Blur
import win32gui

try:
    from core.utils.win32 import app_bar
    IMPORT_APP_BAR_MANAGER_SUCCESSFUL = True
except ImportError:
    IMPORT_APP_BAR_MANAGER_SUCCESSFUL = False

class Bar(QWidget):
    def __init__(
            self,
            bar_id: str,
            bar_name: str,
            bar_screen: QScreen,
            stylesheet: str,
            widgets: dict[str, list],
            init: bool = False,
            class_name: str = BAR_DEFAULTS['class_name'],
            alignment: dict = BAR_DEFAULTS['alignment'],
            blur_effect: dict = BAR_DEFAULTS['blur_effect'],
            animation: dict = BAR_DEFAULTS['animation'],
            window_flags: dict = BAR_DEFAULTS['window_flags'],
            dimensions: dict = BAR_DEFAULTS['dimensions'],
            padding: dict = BAR_DEFAULTS['padding']
    ):
        super().__init__()
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
        
        self.screen_name = self.screen().name()
        self.app_bar_edge = (
            app_bar.AppBarEdge.Top
            if self._alignment['position'] == "top"
            else app_bar.AppBarEdge.Bottom
        )

        if self._window_flags['windows_app_bar'] and IMPORT_APP_BAR_MANAGER_SUCCESSFUL:
            self.app_bar_manager = app_bar.Win32AppBar()
        else:
            self.app_bar_manager = None

        self.setWindowTitle(APP_BAR_TITLE)
        self.setStyleSheet(stylesheet)
        self.setWindowFlag(Qt.WindowType.Tool)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose) 
        
        if self._window_flags['always_on_top']:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

        self._bar_frame = QFrame(self)
        self._bar_frame.setProperty("class", f"bar {class_name}")
        self.update_theme_class()
        
        self.position_bar(init)
        self.monitor_hwnd = get_monitor_hwnd(int(self.winId()))
        self._add_widgets(widgets)
        
        if blur_effect['enabled']:
            Blur(
                self.winId(),
                Acrylic=blur_effect['acrylic'],
                DarkMode=blur_effect['dark_mode'],
                RoundCorners=blur_effect['round_corners'],
                RoundCornersType=blur_effect['round_corners_type'],
                BorderColor=blur_effect['border_color']
            )

        self.screen().geometryChanged.connect(self.on_geometry_changed, Qt.ConnectionType.QueuedConnection)
        if self._animation['enabled']:
            self.animation_bar()
        self.show()
        

    @property
    def bar_id(self) -> str:
        return self._bar_id

    def on_geometry_changed(self, geo: QRect) -> None:
        logging.info(f"Screen geometry changed. Updating position for bar ({self.bar_id})")
        self.position_bar()

    def try_add_app_bar(self, scale_screen_height=False) -> None:
        if self.app_bar_manager:
            self.app_bar_manager.create_appbar(
                self.winId().__int__(),
                self.app_bar_edge,
                self._dimensions['height'] + self._padding['top'] + self._padding['bottom'],
                self.screen(),
                scale_screen_height
            )
            
    def closeEvent(self, event):
        self.try_remove_app_bar()

    def try_remove_app_bar(self) -> None:
        if self.app_bar_manager:
            self.app_bar_manager.remove_appbar()

    def bar_pos(self, bar_w: int, bar_h: int, screen_w: int, screen_h: int) -> tuple[int, int]:
        screen_x = self.screen().geometry().x()
        screen_y = self.screen().geometry().y()
        x = int(screen_x + (screen_w / 2) - (bar_w / 2))if self._alignment['center'] else screen_x
        y = int(screen_y + screen_h - bar_h) if self._alignment['position'] == "bottom" else screen_y
        return x, y

    def position_bar(self, init=False) -> None:
        bar_width = self._dimensions['width']
        bar_height = self._dimensions['height']

        screen_width = self.screen().geometry().width()
        screen_height = self.screen().geometry().height()

        if is_valid_percentage_str(str(self._dimensions['width'])):
            bar_width = int(screen_width * percent_to_float(self._dimensions['width']) - self._padding['left'] - self._padding['right'])
        bar_x, bar_y = self.bar_pos(bar_width, bar_height, screen_width, screen_height)
        bar_x = bar_x + self._padding['left'] 
        bar_y = bar_y + self._padding['top']
        self.setGeometry(bar_x, bar_y, bar_width, bar_height)
        self._bar_frame.setGeometry(
            0,
            0,
            bar_width,
            bar_height
        )
        self.try_add_app_bar(scale_screen_height=True)
        
    def _add_widgets(self, widgets: dict[str, list] = None):
        bar_layout = QGridLayout()
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        for column_num, layout_type in enumerate(['left', 'center', 'right']):
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout_container = QFrame()
            layout_container.setProperty("class", f"container container-{layout_type}")

            if layout_type in ["center", "right"]:
                layout.addStretch()

            for widget in widgets[layout_type]:
               
                widget.parent_layout_type = layout_type
                widget.bar_id = self.bar_id
                widget.monitor_hwnd = self.monitor_hwnd
                layout.addWidget(widget, 0)

            if layout_type in ["left", "center"]:
                layout.addStretch()

            layout_container.setLayout(layout)
            bar_layout.addWidget(layout_container, 0, column_num)
 
        self._bar_frame.setLayout(bar_layout)
        
        
    def animation_bar(self):
        self.final_pos = self.pos()
        if self._alignment['position'] == "top":
            self.initial_pos = QPoint(self.final_pos.x(), self.final_pos.y() - self.height())
        else:
            screen_height = self.screen().geometry().height()
            self.initial_pos = QPoint(self.final_pos.x(), self.final_pos.y() + screen_height)
        self.move(self.initial_pos)
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(self._animation['duration'])
        self.animation.setStartValue(self.initial_pos)
        self.animation.setEndValue(self.final_pos)
        self.animation.setEasingCurve(QEasingCurve.Type.OutExpo)
        
        
    def showEvent(self, event):
        super().showEvent(event)
        if self._animation['enabled']:
            try:
                self.animation.start()
            except AttributeError:
                logging.error("Animation not initialized.")
        if not hasattr(self, "_fullscreen_timer") and self._window_flags['hide_on_fullscreen'] and self._window_flags['always_on_top']:
            self._fullscreen_timer = QTimer(self)
            self._fullscreen_timer.setInterval(500)
            self._fullscreen_timer.timeout.connect(self.is_foreground_fullscreen)
            self._fullscreen_timer.start()


    def is_foreground_fullscreen(self):
        # Get the active window's handle using win32gui
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return
        hwnd_class_name = win32gui.GetClassName(hwnd)
     
        # Check if the foreground window is the desktop
        if hwnd_class_name in ["Progman", "WorkerW"]:
            return
        # Get the window rectangle: (left, top, right, bottom) then convert to (x, y, width, height)
        rect = win32gui.GetWindowRect(hwnd)
        window_rect = (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1])
 
        # Get the primary screen geometry
        screen_geometry = self.screen().geometry()
        screen_rect = (
            screen_geometry.x(),
            screen_geometry.y(),
            screen_geometry.width(),
            screen_geometry.height()
        )

        # Determine fullscreen state
        is_fullscreen = (window_rect == screen_rect)
        # Cache the previous state so we only update if it changes
        if hasattr(self, "_prev_fullscreen_state") and self._prev_fullscreen_state == is_fullscreen:
            return
        self._prev_fullscreen_state = is_fullscreen
        # Update visibility only when necessary
        if is_fullscreen:
            if self.isVisible():
                self.hide()
        else:
            if not self.isVisible():
                self.show() 


    def detect_os_theme(self) -> bool:
        try:
            import winreg
            with winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER) as registry:
                with winreg.OpenKey(registry, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
                    value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
                    return value == 0
        except Exception as e:
            logging.error(f"Failed to determine Windows theme: {e}")
            return False
        
    
    def update_theme_class(self):
        if not hasattr(self, '_bar_frame'):
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
        
def update_styles(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    for child in widget.findChildren(QWidget):
        child.style().unpolish(child)
        child.style().polish(child)