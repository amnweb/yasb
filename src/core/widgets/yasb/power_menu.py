import datetime

import psutil
from PyQt6 import QtCore, QtGui
from PyQt6.QtCore import QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QStyle, QStyleOption, QVBoxLayout, QWidget

from core.config import get_stylesheet
from core.event_service import EventService
from core.utils.utilities import add_shadow, is_windows_10
from core.utils.widgets.power_menu.power_commands import PowerOperations
from core.utils.win32.blurWindow import Blur
from core.utils.win32.utilities import get_foreground_hwnd, set_foreground_hwnd
from core.validation.widgets.yasb.power_menu import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


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


class OverlayWidget(BaseStyledWidget, AnimatedWidget):
    def __init__(self, animation_duration, uptime):
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
        formatted_uptime = " ".join(uptime_parts)
        self.label_boot.setText(f"Uptime {formatted_uptime}")


class PowerMenuWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    handle_widget_cli = pyqtSignal(str, str)

    def __init__(
        self,
        label: str,
        uptime: bool,
        blur: bool,
        blur_background: bool,
        animation_duration: int,
        button_row: int,
        container_padding: dict[str, int],
        buttons: dict[str, list[str]],
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(0, class_name="power-menu-widget")

        self.buttons = buttons
        self.blur = blur
        self.uptime = uptime
        self.blur_background = blur_background
        self.animation_duration = animation_duration
        self.button_row = button_row
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self._button = ClickableLabel(label)
        self._button.setProperty("class", "label power-button")
        self._button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._button.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add_shadow(self._button, self._label_shadow)
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        # Initialize container

        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        self._widget_container_layout.addWidget(self._button)

        self._button.clicked.connect(self.show_main_window)
        self.main_window = None

        self._popup_from_cli = False
        self._previous_hwnd = None

        self._event_service = EventService()
        self.handle_widget_cli.connect(self._handle_widget_cli)
        self._event_service.register_event("handle_widget_cli", self.handle_widget_cli)

    def _handle_widget_cli(self, widget: str, screen: str):
        """Handle widget CLI commands"""
        if widget == "powermenu":
            current_screen = self.window().screen() if self.window() else None
            current_screen_name = current_screen.name() if current_screen else None
            if not screen or (current_screen_name and screen.lower() == current_screen_name.lower()):
                self._popup_from_cli = True
                self.show_main_window()

    def show_main_window(self):
        if self.main_window and self.main_window.isVisible():
            self.main_window.fade_out()
            self.main_window.overlay.fade_out()
            if self._previous_hwnd:
                set_foreground_hwnd(self._previous_hwnd)
                self._previous_hwnd = None
        else:
            if getattr(self, "_popup_from_cli", False):
                self._previous_hwnd = get_foreground_hwnd()
                self._popup_from_cli = False
            self.main_window = MainWindow(
                self._button,
                self.uptime,
                self.blur,
                self.blur_background,
                self.animation_duration,
                self.button_row,
                self.buttons,
            )
            self.main_window.overlay.fade_in()
            self.main_window.overlay.show()
            self.main_window.show()
            self.main_window.activateWindow()
            self.main_window.setFocus()


class MainWindow(BaseStyledWidget, AnimatedWidget):
    def __init__(self, parent_button, uptime, blur, blur_background, animation_duration, button_row, buttons):
        super(MainWindow, self).__init__(animation_duration)

        self.overlay = OverlayWidget(animation_duration, uptime)
        self.parent_button = parent_button
        self.button_row = button_row  # Store button_row as instance attribute

        # Add focus policy to allow keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Initialize variables to track focused button
        self.buttons_list = []
        self.current_focus_index = -1

        self.setProperty("class", "power-menu-popup")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.buttons_info = []
        for button_name, button_info in buttons.items():
            action_method_name = f"{button_name}_action"
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

            # Store buttons in a list for navigation
            self.buttons_list.append(button)

            # Only add icon label if icon is not empty or None
            if icon:
                icon_label = QLabel(f"{icon}", self)
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
                Acrylic=True if is_windows_10() else False,
                DarkMode=False,
                RoundCorners=False,
                BorderColor="None",
            )
        if blur_background:
            Blur(
                self.overlay.winId(),
                Acrylic=True if is_windows_10() else False,
                DarkMode=False,
                RoundCorners=False,
                BorderColor="None",
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
            for child in source.findChildren(QLabel):
                child.style().unpolish(child)
                child.style().polish(child)
        elif event.type() == QtCore.QEvent.Type.Leave and isinstance(source, QPushButton):
            source.setProperty("class", f"button {source.property('class').split()[1]}")
            source.style().unpolish(source)
            source.style().polish(source)
            for child in source.findChildren(QLabel):
                child.style().unpolish(child)
                child.style().polish(child)
        return super(MainWindow, self).eventFilter(source, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_action()
            event.accept()  # Mark event as handled
        elif event.key() == Qt.Key.Key_Right:
            self.navigate_focus(1)
            event.accept()  # Mark event as handled
        elif event.key() == Qt.Key.Key_Left:
            self.navigate_focus(-1)
            event.accept()  # Mark event as handled
        elif event.key() == Qt.Key.Key_Down:
            self.navigate_focus(self.button_row)  # Move down by one row
            event.accept()  # Mark event as handled
        elif event.key() == Qt.Key.Key_Up:
            self.navigate_focus(-self.button_row)  # Move up by one row
            event.accept()  # Mark event as handled
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            # Trigger click on the focused button
            if 0 <= self.current_focus_index < len(self.buttons_list):
                self.buttons_list[self.current_focus_index].click()
                event.accept()  # Mark event as handled
        else:
            super(MainWindow, self).keyPressEvent(event)

    def navigate_focus(self, step):
        """Navigate button focus by step."""
        if not self.buttons_list:
            return

        total_buttons = len(self.buttons_list)

        # If no button is currently focused, start with the appropriate first button
        if self.current_focus_index < 0 or self.current_focus_index >= total_buttons:
            if step > 0:
                # When pressing right or down arrow with no selection, select the first button
                new_index = 0
            elif step < 0:
                # When pressing left or up arrow with no selection, select the last button
                new_index = total_buttons - 1
            else:
                # Default to first button
                new_index = 0
        else:
            # Normal navigation with existing selection
            current = self.current_focus_index

            if step == 1:  # Right
                new_index = (current + 1) % total_buttons
            elif step == -1:  # Left
                new_index = (current - 1) % total_buttons
            elif step == self.button_row or step == -self.button_row:  # Up/Down - vertical movement
                # Calculate the current row and column
                current_row = current // self.button_row
                current_col = current % self.button_row

                # Determine total rows
                total_rows = (total_buttons + self.button_row - 1) // self.button_row

                if step == self.button_row:  # Down
                    # Move to next row, same column
                    new_row = (current_row + 1) % total_rows
                else:  # Up
                    # Move to previous row, same column
                    new_row = (current_row - 1) % total_rows

                # Calculate new index
                new_index = new_row * self.button_row + current_col

                # If we've moved to a partial row and the column is beyond its bounds
                if new_index >= total_buttons:
                    if step == self.button_row:
                        # When moving down to an out-of-bounds position, wrap to first row
                        new_index = current_col
                    else:
                        # When moving up to an out-of-bounds position, use last valid button
                        new_index = total_buttons - 1
            else:
                new_index = current  # No change

        new_index = max(0, min(new_index, total_buttons - 1))
        self.set_focused_button(new_index)

    def set_focused_button(self, index):
        """Set focus to the button at the given index."""
        if not self.buttons_list:
            return

        # Safety check - ensure index is valid
        if index < 0 or index >= len(self.buttons_list):
            return

        # Update our internal tracking
        self.current_focus_index = index

        # First, remove hover from all buttons
        for i, button in enumerate(self.buttons_list):
            # Parse class components
            class_parts = button.property("class").split()
            # Remove any hover class if present
            if "hover" in class_parts:
                class_parts.remove("hover")
            # Set class without hover
            clean_class = " ".join(class_parts)
            button.setProperty("class", clean_class)
            button.style().unpolish(button)
            button.style().polish(button)

        # Then apply hover to the selected button
        current_button = self.buttons_list[self.current_focus_index]
        current_class = current_button.property("class")

        # Add hover class
        hover_class = f"{current_class} hover"
        current_button.setProperty("class", hover_class)
        current_button.style().unpolish(current_button)
        current_button.style().polish(current_button)

        self.setFocus()

    def showEvent(self, event):
        """Override show event to set focus."""
        super(MainWindow, self).showEvent(event)
        # Set focus to the window and first button when shown
        self.setFocus()
        self.current_focus_index = -1

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
