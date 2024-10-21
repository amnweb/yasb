import sys
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QStyleOption, QStyle
from PyQt6 import QtCore, QtGui
from PyQt6.QtGui import QCursor
from PyQt6.QtCore import Qt, QPropertyAnimation, pyqtSignal
from core.utils.win32.blurWindow import Blur
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.power_menu import VALIDATION_SCHEMA
from core.config import get_stylesheet
from core.utils.win32.power import PowerOperations
import datetime
import psutil

class BaseStyledWidget(QWidget):
    def apply_stylesheet(self):
        stylesheet = get_stylesheet()
        self.setStyleSheet(stylesheet)
            
class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

class AnimatedWidget(QWidget):
    def __init__(self, animation_duration, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.animation_duration = animation_duration
        self.animation = QPropertyAnimation(self, b"windowOpacity")

    def fade_in(self):
        self.animation.setDuration(self.animation_duration)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()

    def fade_out(self):
        self.animation.setDuration(self.animation_duration)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.finished.connect(self.on_fade_out_finished)
        self.animation.start()

    def on_fade_out_finished(self):
        self.hide()

class OverlayWidget(BaseStyledWidget,AnimatedWidget):
    def __init__(self, animation_duration,uptime):
        super().__init__(animation_duration)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if uptime:
            self.boot_time()
            
 
    def update_geometry(self, screen_geometry):
        self.setGeometry(screen_geometry)
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        # Disable clicks behind overlay
        overlay_color = QtGui.QColor(0, 0, 0, 50)
        painter.fillRect(self.rect(), overlay_color)
        
    def boot_time(self):
        self.label_boot = QLabel(self)
        self.label_boot.setProperty("class", "uptime")
        self.label_boot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Set initial uptime display
        self.update_uptime_display()
        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.label_boot)
        self.setLayout(layout)
        # Apply the stylesheet here
        self.apply_stylesheet()
        # Start timer for live updates
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_uptime_display)
        self.timer.start(500)  

    def update_uptime_display(self):
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_parts = []
        if days > 0:
            uptime_parts.append(f"{days} day{'s' if days > 1 else ''}")
        if hours > 0:
            uptime_parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
        if minutes > 0:
            uptime_parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
        if seconds > 0:
            uptime_parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")
        formatted_uptime = ' '.join(uptime_parts)
        self.label_boot.setText(f'Uptime {formatted_uptime}')
 
        
class PowerMenuWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(self, label: str, uptime: bool, blur: bool, blur_background: bool, animation_duration: int, button_row: int, buttons: dict[str, list[str]]):
        super().__init__(0, class_name="power-menu-widget")
        
        self.buttons = buttons
        self.blur = blur
        self.uptime = uptime
        self.blur_background = blur_background
        self.animation_duration = animation_duration
        self.button_row = button_row

        self._button = ClickableLabel(label)
        self._button.setProperty("class", "label power-button")
        self._button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._button.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.widget_layout.addWidget(self._button)
        self._button.clicked.connect(self.show_main_window)
        self.main_window = None

    def show_main_window(self):
        if self.main_window and self.main_window.isVisible():
            self.main_window.fade_out()
            self.main_window.overlay.fade_out()
        else:
            self.main_window = MainWindow(self._button, self.uptime, self.blur, self.blur_background, self.animation_duration, self.button_row, self.buttons)
            self.main_window.overlay.fade_in()
            self.main_window.overlay.show()
            self.main_window.show()
            self.main_window.activateWindow()
            self.main_window.setFocus()
            

class MainWindow(BaseStyledWidget,AnimatedWidget):
    def __init__(self, parent_button, uptime,blur, blur_background, animation_duration, button_row, buttons):
        super(MainWindow, self).__init__(animation_duration)

        self.overlay = OverlayWidget(animation_duration,uptime)
        self.parent_button = parent_button

        self.setProperty("class", "power-menu-popup")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
 
        self.buttons_info = []
        for button_name, button_info in buttons.items():
            action_method_name = f'{button_name}_action'
            if hasattr(self, action_method_name):
                action_method = getattr(self, action_method_name)
            else:
                action_method = self.cancel_action  # Fallback to a cancel action
            icon, text = button_info
            self.buttons_info.append((icon, text, action_method, button_name))



        main_layout = QVBoxLayout()
        button_layout1 = QHBoxLayout()
        button_layout2 = QHBoxLayout()
        button_layout3 = QHBoxLayout()
        button_layout4 = QHBoxLayout()
         
        self.power_operations = PowerOperations(self, self.overlay)

        for i, (icon, label, action, class_name) in enumerate(self.buttons_info):
            button = QPushButton(self)
            button.setProperty("class", f"button {class_name}")
            button_layout = QVBoxLayout(button)

            # Only add icon label if icon is not empty or None
            if icon:
                icon_label = QLabel(f'{icon}', self)
                icon_label.setProperty("class", "icon")
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_label.setTextFormat(Qt.TextFormat.RichText)
                button_layout.addWidget(icon_label)

            text_label = QLabel(label, self)
            text_label.setProperty("class", "label")
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            button_layout.addWidget(text_label)

            if i < button_row:
                button_layout1.addWidget(button)
            elif i < (button_row * 2):
                button_layout2.addWidget(button)
            elif i < (button_row * 3):
                button_layout3.addWidget(button)
            else:
                button_layout4.addWidget(button)
            
            button.clicked.connect(action)
            button.installEventFilter(self)

        main_layout.addLayout(button_layout1)
        main_layout.addLayout(button_layout2)
        main_layout.addLayout(button_layout3)
        main_layout.addLayout(button_layout4)
        self.setLayout(main_layout)
        self.apply_stylesheet()
        self.adjustSize()
        self.center_on_screen()

        if blur:
            Blur(
                self.winId(),
                Acrylic=False,
                DarkMode=False,
                RoundCorners=False,
                BorderColor="None"
            )
        if blur_background:
            Blur(
                self.overlay.winId(),
                Acrylic=False,
                DarkMode=False,
                RoundCorners=False,
                BorderColor="None"
            )
 

        self.fade_in()

    def center_on_screen(self):
        screen = QApplication.screenAt(self.parent_button.mapToGlobal(QtCore.QPoint(0, 0)))
        if screen is None:
            screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        window_geometry = self.geometry()
        x = (screen_geometry.width() - window_geometry.width()) // 2 + screen_geometry.x()
        y = (screen_geometry.height() - window_geometry.height()) // 2 + screen_geometry.y()
        self.move(x, y)
        self.overlay.update_geometry(screen_geometry)  # Update overlay geometry to match screen
 

    def paintEvent(self, event):
        option = QStyleOption()
        option.initFrom(self)
        painter = QtGui.QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.Type.Enter and isinstance(source, QPushButton):
            source.setProperty("class", f"button {source.property('class').split()[1]} hover")
            source.style().unpolish(source)
            source.style().polish(source)
        elif event.type() == QtCore.QEvent.Type.Leave and isinstance(source, QPushButton):
            source.setProperty("class", f"button {source.property('class').split()[1]}")
            source.style().unpolish(source)
            source.style().polish(source)
        return super(MainWindow, self).eventFilter(source, event)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_action()
        super(MainWindow, self).keyPressEvent(event)
    
    def signout_action(self):
        self.power_operations.signout()

    def lock_action(self):
        self.power_operations.lock()

    def sleep_action(self):
        self.power_operations.sleep()

    def restart_action(self):
        self.power_operations.restart()

    def shutdown_action(self):
        self.power_operations.shutdown()

    def force_shutdown_action(self):
        self.power_operations.force_shutdown()

    def force_restart_action(self):
        self.power_operations.force_restart()

    def hibernate_action(self):
        self.power_operations.hibernate()

    def cancel_action(self):
        self.power_operations.cancel()
