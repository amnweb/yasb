import logging
from settings import APP_BAR_TITLE
from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QGridLayout, QFrame
from PyQt6.QtGui import QScreen
from PyQt6.QtCore import Qt, QRect
from core.utils.utilities import is_valid_percentage_str, percent_to_float
from core.utils.win32.utilities import get_monitor_hwnd
from core.validation.bar import BAR_DEFAULTS
from BlurWindow.blurWindow import GlobalBlur
 
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

        self.screen_name = self.screen().name()
        self.app_bar_edge = app_bar.AppBarEdge.Top \
            if self._alignment['position'] == "top" \
            else app_bar.AppBarEdge.Bottom

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

        self.position_bar(init)
        self.monitor_hwnd = get_monitor_hwnd(int(self.winId()))
        self._add_widgets(widgets)
        
        if blur_effect['enabled']:
            GlobalBlur(
                self.winId(),
                Acrylic=blur_effect['acrylic'],
                Dark=blur_effect['dark'],
                QWidget=self
            )

        self.screen().geometryChanged.connect(self.on_geometry_changed, Qt.ConnectionType.QueuedConnection)

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

        screen_scale = self.screen().devicePixelRatio()
        screen_width = self.screen().geometry().width()
        screen_height = self.screen().geometry().height()
 
        # Fix for non-primary display Windows OS scaling on app startup
        should_downscale_screen_geometry = (
            init and
            len(QApplication.screens()) > 1 and
            screen_scale >= 2.0 and
            QApplication.primaryScreen() != self.screen()
        )

        if should_downscale_screen_geometry:
            screen_width = screen_width / screen_scale
            screen_height = screen_height / screen_scale

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

        self.try_add_app_bar(scale_screen_height=not should_downscale_screen_geometry)
        
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