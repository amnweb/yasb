import sys
import subprocess
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QStyleOption, QStyle
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import Qt, QPropertyAnimation, pyqtSignal, QCoreApplication
from BlurWindow.blurWindow import GlobalBlur
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.power_menu import VALIDATION_SCHEMA
from core.config import get_stylesheet_path

class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

class PowerMenuWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(self, label: str, blur: bool, icons: dict[str, str]):
        super().__init__(0, class_name="system-widget")
        
        self.icons = icons  # Store the icons dictionary
        self.blur = blur
        
        self._button = ClickableLabel(label)
        self._button.setProperty("class", "label power-button")
        self.widget_layout.addWidget(self._button)
        self._button.clicked.connect(self.show_main_window)
        self.main_window = None

    def show_main_window(self):
        if self.main_window and self.main_window.isVisible():
            self.main_window.fade_out()
        else:
            self.main_window = MainWindow(self._button, self.icons, self.blur)
            self.main_window.show()

class MainWindow(QWidget):
    def __init__(self, parent_button, icons, blur):
        super(MainWindow, self).__init__()

        self.blur = blur
        self.icon_signout = icons['signout']
        self.icon_lock = icons['lock']
        self.icon_sleep = icons['sleep']
        self.icon_restart = icons['restart']
        self.icon_shutdown = icons['shutdown']
        self.icon_cancel = icons['cancel']

        self.setProperty("class", "power-button-widget")

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Create layout for buttons
        main_layout = QVBoxLayout()
        button_layout1 = QHBoxLayout()
        button_layout2 = QHBoxLayout()

        if self.blur:
            GlobalBlur(self.winId(),Dark=True)


        # Button labels and icons with their corresponding actions
        buttons_info = [
            (self.icon_signout, 'Sign out', self.signout, "signout"),
            (self.icon_lock, 'Lock', self.lock, "lock"),
            (self.icon_sleep, 'Sleep', self.sleep, "sleep"),
            (self.icon_restart, 'Restart', self.restart, "restart"),
            (self.icon_shutdown, 'Shut Down', self.shutdown, "shutdown"),
            (self.icon_cancel, 'Cancel', self.cancel, "cancel")
        ]
        # Create buttons with icons and text
        for i, (icon, label, action, class_name) in enumerate(buttons_info):
            button = QPushButton(self)
            button.setProperty("class", f"shutdown-buttons {class_name}")
            # Create a layout for the button content
            button_layout = QVBoxLayout(button)
            # Create QLabel for the icon
            icon_label = QLabel(f'{icon}', self)
            icon_label.setProperty("class", "shutdown-icons")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setTextFormat(Qt.TextFormat.RichText)
            # Create QLabel for the text
            text_label = QLabel(label, self)
            text_label.setProperty("class", "shutdown-label")
            text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Add labels to the button layout
            button_layout.addWidget(icon_label)
            button_layout.addWidget(text_label)
            if i < 3:
                button_layout1.addWidget(button)
            else:
                button_layout2.addWidget(button)
            button.clicked.connect(action)  # Connect the button click to its action
            # Install event filter for hover events
            button.installEventFilter(self)

        main_layout.addLayout(button_layout1)
        main_layout.addLayout(button_layout2)
        self.setLayout(main_layout)
        self.apply_stylesheet(self, get_stylesheet_path())
        # Adjust size to fit the contents
        self.adjustSize()
        # Center the window on the screen
        self.center_on_screen()
        # Start fade-in animation
        self.fade_in()

    def center_on_screen(self):
        screen_geometry = QApplication.primaryScreen().geometry()
        window_geometry = self.geometry()
        x = (screen_geometry.width() - window_geometry.width()) // 2
        y = (screen_geometry.height() - window_geometry.height()) // 2
        self.move(x, y)

    def fade_in(self):
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.start()

    def fade_out(self):
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.finished.connect(self.close)
        self.animation.start()
    
    def apply_stylesheet(self, app, path):
        with open(path, "r") as f:
            stylesheet = f.read()
            app.setStyleSheet(stylesheet)

    def paintEvent(self, event):
        option = QStyleOption()
        option.initFrom(self)
        painter = QtGui.QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.Type.Enter and isinstance(source, QPushButton):
            source.setProperty("class", f"shutdown-buttons {source.property('class').split()[1]} hover")
            source.style().unpolish(source)
            source.style().polish(source)
        elif event.type() == QtCore.QEvent.Type.Leave and isinstance(source, QPushButton):
            source.setProperty("class", f"shutdown-buttons {source.property('class').split()[1]}")
            source.style().unpolish(source)
            source.style().polish(source)
        return super(MainWindow, self).eventFilter(source, event)
    
    def signout(self):
        self.hide()
        QCoreApplication.exit(0)
        subprocess.Popen("shutdown /l", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)

    def lock(self):
        self.hide()
        subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)

    def sleep(self):
        self.hide()
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState Sleep", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)

    def restart(self):
        self.hide()
        QCoreApplication.exit(0)
        subprocess.Popen("shutdown /r /f /t 0", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)

    def shutdown(self):
        self.hide()
        QCoreApplication.exit(0)
        subprocess.Popen("shutdown /s /t 0", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
        # try:
        #     self.hide()
        #     QCoreApplication.exit(0)
        #     process = subprocess.run(["shutdown", "/s", "/t", "0"])
        # except subprocess.CalledProcessError as e:
        #     print(f"An error occurred: {e}")          
        # subprocess.Popen("shutdown /s /t 60", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
        # self.hide()
        # sys.exit()

    def cancel(self):
        self.fade_out()
