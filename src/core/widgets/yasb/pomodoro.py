import logging
import os
import re
import time

from PyQt6.QtCore import QPropertyAnimation, QRectF, Qt, QTimer, pyqtProperty
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.utils.utilities import PopupWidget, ToastNotifier, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.pomodoro import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import SCRIPT_PATH


class PomodoroWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        label_alt: str,
        work_duration: int,
        break_duration: int,
        long_break_duration: int,
        long_break_interval: int,
        auto_start_breaks: bool,
        auto_start_work: bool,
        sound_notification: bool,
        show_notification: bool,
        session_target: int,
        hide_on_break: bool,
        icons: dict,
        animation: dict,
        container_padding: dict,
        callbacks: dict,
        menu: dict,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name="pomodoro-widget")

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._work_duration = work_duration * 60
        self._break_duration = break_duration * 60
        self._long_break_duration = long_break_duration * 60
        self._long_break_interval = long_break_interval
        self._auto_start_breaks = auto_start_breaks
        self._auto_start_work = auto_start_work
        self._sound_notification = sound_notification
        self._show_notification = show_notification
        self._session_target = session_target
        self._hide_on_break = hide_on_break
        self._icons = icons
        self._animation = animation
        self._padding = container_padding
        self._menu_config = menu
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        # Initialize state
        self._is_running = False
        self._is_break = False
        self._is_paused = False
        self._is_long_break = False
        self._remaining_time = self._work_duration
        self._elapsed_time = 0
        self._session_count = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_timer)

        self._last_update_time = None

        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )

        # Initialize container
        self._widget_container = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        self.register_callback("toggle_timer", self._toggle_timer)
        self.register_callback("reset_timer", self._reset_timer)
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        self._update_label()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content
        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        remaining_str = self._format_time(self._remaining_time)
        status = "Paused" if self._is_paused else "Break" if self._is_break else "Work"
        class_name = "paused" if self._is_paused else "break" if self._is_break else "work"

        label_options = {
            "{remaining}": remaining_str,
            "{status}": status,
            "{session}": str(self._session_count + 1),
            "{total_sessions}": str(self._session_target) if self._session_target > 0 else "∞",
            "{icon}": self._get_current_icon(),
        }

        for part in label_parts:
            part = part.strip()
            if part:
                formatted_text = part
                for option, value in label_options.items():
                    formatted_text = formatted_text.replace(option, str(value))
                if "<span" in part and "</span>" in part:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        active_widgets[widget_index].setText(formatted_text)
                        base_class = active_widgets[widget_index].property("class").split()[0]
                        active_widgets[widget_index].setProperty("class", f"{base_class} {class_name}")
                        active_widgets[widget_index].setStyleSheet("")
                else:
                    if widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                        alt_class = "alt" if self._show_alt_label else ""
                        active_widgets[widget_index].setText(formatted_text)
                        base_class = "label"
                        active_widgets[widget_index].setProperty("class", f"{base_class} {alt_class} {class_name}")
                        active_widgets[widget_index].setStyleSheet("")
                widget_index += 1

    def _get_current_icon(self):
        if self._is_paused:
            return self._icons["paused"]
        elif self._is_break:
            return self._icons["break"]
        else:
            return self._icons["work"]

    def _toggle_timer(self):
        if self._is_running:
            self._pause_timer()
        else:
            self._start_timer()

    def _start_timer(self):
        self._is_running = True
        self._is_paused = False
        self._last_update_time = time.time()
        self._timer.start(1000)
        self._update_label()

        try:
            if hasattr(self, "_dialog") and self._dialog is not None and self._dialog.isVisible():
                self._toggle_button.setText("Pause")
                self._toggle_button.setProperty("class", "button pause")
                self._toggle_button.style().unpolish(self._toggle_button)
                self._toggle_button.style().polish(self._toggle_button)
        except RuntimeError:
            pass

    def _pause_timer(self):
        self._is_running = False
        self._is_paused = True
        self._timer.stop()
        self._update_label()

        try:
            if hasattr(self, "_dialog") and self._dialog is not None and self._dialog.isVisible():
                self._toggle_button.setText("Start")
                self._toggle_button.setProperty("class", "button start")
                self._toggle_button.style().unpolish(self._toggle_button)
                self._toggle_button.style().polish(self._toggle_button)
                self._progress_gauge.setStatusText(f"Paused\n{self._format_time(self._remaining_time)}")
        except RuntimeError:
            pass

    def _reset_timer(self):
        self._is_running = False
        self._is_paused = False
        self._is_break = False
        self._timer.stop()
        self._remaining_time = self._work_duration
        self._elapsed_time = 0
        self._update_label()
        try:
            if hasattr(self, "_dialog") and self._dialog is not None and self._dialog.isVisible():
                self._progress_gauge.setBreakMode(False)
                self._progress_gauge.setMaximum(self._work_duration)
                self._progress_gauge.setValue(0, skip_animation=True)
                self._progress_gauge.setStatusText(f"Work\n{self._format_time(self._work_duration)}")

                self._toggle_button.setText("Start")
                self._toggle_button.setProperty("class", "button start")
                self._toggle_button.style().unpolish(self._toggle_button)
                self._toggle_button.style().polish(self._toggle_button)
        except RuntimeError:
            pass

    def _update_timer(self):
        if self._is_running:
            self._remaining_time = max(0, self._remaining_time - 1)
            self._elapsed_time += 1

        if self._remaining_time <= 0:
            self._timer_completed()

        self._update_label()

        try:
            if hasattr(self, "_dialog") and self._dialog is not None and self._dialog.isVisible():
                if self._is_break:
                    max_value = self._long_break_duration if self._is_long_break else self._break_duration
                    current_value = max_value - self._remaining_time
                else:
                    max_value = self._work_duration
                    current_value = max_value - self._remaining_time

                if hasattr(self, "_progress_gauge"):
                    self._progress_gauge.setMaximum(max_value)
                    self._progress_gauge.setValue(int(current_value))
                    self._progress_gauge.setBreakMode(self._is_break)
                    status_text = "Break" if self._is_break else "Work"
                    self._progress_gauge.setStatusText(f"{status_text}\n{self._format_time(self._remaining_time)}")
                    self._session_label.setText(
                        f"Session: {self._session_count + 1}"
                        + (f"/{self._session_target}" if self._session_target > 0 else "")
                    )
        except RuntimeError:
            pass

    def _timer_completed(self, notification=True):
        self._timer.stop()
        self._is_running = False

        if self._sound_notification and notification:
            self._play_notification_sound()

        if self._show_notification and notification:
            self._show_desktop_notification()

        if self._is_break:
            # Break completed, start work session
            self._is_break = False
            self._remaining_time = self._work_duration

            if self._hide_on_break:
                self.setVisible(True)

            self._update_label()

            try:
                if hasattr(self, "_dialog") and self._dialog is not None and self._dialog.isVisible():
                    self._progress_gauge.setBreakMode(False)
                    self._progress_gauge.setMaximum(self._work_duration)
                    self._progress_gauge.setValue(0, skip_animation=True)
                    self._progress_gauge.setStatusText(f"Work\n{self._format_time(self._work_duration)}")
            except RuntimeError:
                pass

            if self._auto_start_work:
                self._start_timer()
        else:
            # Work completed, increment session count
            self._session_count += 1

            if self._session_count > 0 and self._session_count % self._long_break_interval == 0:
                self._is_long_break = True
                self._remaining_time = self._long_break_duration
            else:
                self._is_long_break = False
                self._remaining_time = self._break_duration

            self._is_break = True
            self._update_label()

            try:
                if hasattr(self, "_dialog") and self._dialog is not None and self._dialog.isVisible():
                    max_value = self._long_break_duration if self._is_long_break else self._break_duration
                    self._progress_gauge.setBreakMode(True)
                    self._progress_gauge.setMaximum(max_value)
                    self._progress_gauge.setValue(0, skip_animation=True)
                    self._progress_gauge.setStatusText(f"Break\n{self._format_time(self._remaining_time)}")
            except RuntimeError:
                pass

            if self._hide_on_break:
                self.setVisible(False)

            if self._auto_start_breaks:
                self._start_timer()

    def _play_notification_sound(self):
        try:
            import winsound

            sound = os.path.join(SCRIPT_PATH, "assets", "sound", "notification01.wav")
            winsound.PlaySound(sound, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            logging.error(f"Failed to play notification sound: {e}")

    def _show_desktop_notification(self):
        try:
            self._icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_transparent.png")
            title = "Pomodoro Timer"
            message = "Break time!" if not self._is_break else "Work time!"
            toaster = ToastNotifier()
            toaster.show(self._icon_path, title, message)
        except Exception as e:
            logging.warning(f"Failed to show desktop notification: {e}")

    def _toggle_menu(self):
        self.show_menu()

    def show_menu(self):
        self._dialog = PopupWidget(
            self,
            self._menu_config["blur"],
            self._menu_config["round_corners"],
            self._menu_config["round_corners_type"],
            self._menu_config["border_color"],
        )

        self._dialog.setProperty("class", "pomodoro-menu")

        # Main layout for the popup
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 14, 12, 14)

        # Header widget
        header_widget = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 8)
        header_widget.setLayout(header_layout)

        # Add header title
        title_label = QLabel("Pomodoro Timer")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignCenter)
        title_label.setProperty("class", "header")
        header_layout.addWidget(title_label)

        layout.addWidget(header_widget)

        if self._is_break:
            max_value = self._long_break_duration if self._is_long_break else self._break_duration
            current_value = max_value - self._remaining_time
        else:
            max_value = self._work_duration
            current_value = max_value - self._remaining_time

        # Replace progress bar with circular progress
        self._progress_gauge = CircularProgressWidget(config=self._menu_config)
        self._progress_gauge.setMaximum(max_value)
        self._progress_gauge.setValue(int(current_value), skip_animation=True)
        self._progress_gauge.setBreakMode(self._is_break)  # Set correct mode

        # Set the status text directly on the circular widget
        status_text = "Paused" if self._is_paused else ("Break" if self._is_break else "Work")

        self._progress_gauge.setStatusText(f"{status_text}\n{self._format_time(self._remaining_time)}")
        self._status_label = self._progress_gauge._status_label

        layout.addWidget(self._progress_gauge)

        # Info widget only for session count now
        info_widget = QWidget()
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_widget.setLayout(info_layout)

        # Session count
        self._session_label = QLabel(
            f"Session: {self._session_count + 1}" + (f"/{self._session_target}" if self._session_target > 0 else "")
        )
        self._session_label.setProperty("class", "session")
        self._session_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self._session_label)

        layout.addWidget(info_widget)

        # Control buttons
        button_widget = QWidget()
        button_layout = QHBoxLayout()
        button_widget.setLayout(button_layout)

        # Start/Pause button
        self._toggle_button = QPushButton("Pause" if self._is_running else "Start")
        self._toggle_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._toggle_button.setProperty("class", "button " + ("pause" if self._is_running else "start"))
        self._toggle_button.clicked.connect(self._toggle_timer)
        button_layout.addWidget(self._toggle_button)

        # Reset button
        reset_button = QPushButton("Reset")
        reset_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        reset_button.setProperty("class", "button reset")
        reset_button.clicked.connect(self._reset_timer)
        button_layout.addWidget(reset_button)

        # Skip button (to next phase)
        skip_button = QPushButton("Skip")
        skip_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        skip_button.setProperty("class", "button skip")
        skip_button.clicked.connect(self._skip_to_next_phase)
        button_layout.addWidget(skip_button)

        layout.addWidget(button_widget)

        self._dialog.setLayout(layout)

        self._dialog.adjustSize()
        self._dialog.setPosition(
            alignment=self._menu_config["alignment"],
            direction=self._menu_config["direction"],
            offset_left=self._menu_config["offset_left"],
            offset_top=self._menu_config["offset_top"],
        )
        self._dialog.show()

    def _format_time(self, seconds):
        # For shorter durations (60 minutes or less), show minutes:seconds
        if seconds < 3600:
            minutes, seconds = divmod(seconds, 60)
            return f"{int(minutes):02d}:{int(seconds):02d}"
        # For longer durations (more than 60 minutes), show hours:minutes
        else:
            hours, remainder = divmod(seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            return f"{int(hours):02d}:{int(minutes):02d}"

    def _skip_to_next_phase(self):
        self._remaining_time = 0
        self._timer_completed(notification=False)


class CircularProgressWidget(QWidget):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self._value = 0
        self._maximum = 0

        self._background_color = config["circle_background_color"]
        self._progress_color = config["circle_work_progress_color"]
        self._break_color = config["circle_break_progress_color"]
        self._thickness = config["circle_thickness"]
        self._size = config["circle_size"]
        self._animation_duration = 400

        self._is_break = False  # Default to work mode

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setProperty("class", "status")
        self._layout.addWidget(self._status_label)

        self._animation = QPropertyAnimation(self, b"animationValue")
        self._animation.setDuration(self._animation_duration)
        self._animation.valueChanged.connect(self.update)

        self.setMinimumSize(self._size, self._size)

    def getAnimationValue(self):
        return self._value

    def setAnimationValue(self, value):
        self._value = value
        self.update()

    animationValue = pyqtProperty(float, getAnimationValue, setAnimationValue)

    def setMaximum(self, maximum):
        self._maximum = maximum
        self.update()

    def setValue(self, value, skip_animation=False):
        if value == self._value:
            return

        if skip_animation:
            self._animation.stop()
            self._value = value
            self.update()
            return

        self._animation.stop()
        self._animation.setStartValue(self._value)
        self._animation.setEndValue(value)
        self._animation.start()

    def setStatusText(self, text):
        self._status_label.setText(text)

    def setBreakMode(self, is_break):
        self._is_break = is_break
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        draw_size = min(width, height) - (self._thickness * 2)
        rect = QRectF((width - draw_size) / 2, (height - draw_size) / 2, draw_size, draw_size)

        background_pen = QPen(QColor(self._background_color), self._thickness)
        background_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(background_pen)
        painter.drawEllipse(rect)

        if self._maximum > 0:
            progress_angle = int(360 * self._value / self._maximum)
            color = self._break_color if self._is_break else self._progress_color
            progress_pen = QPen(QColor(color), self._thickness)
            progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(progress_pen)
            painter.drawArc(rect, 90 * 16, -progress_angle * 16)
