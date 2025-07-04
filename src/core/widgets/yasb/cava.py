import atexit
import logging
import os
import shutil
import struct
import subprocess
import textwrap
import threading

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from core.utils.utilities import app_data_path
from core.validation.widgets.yasb.cava import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class CavaBar(QWidget):
    def __init__(self, cava_widget):
        super().__init__()
        self._cava_widget = cava_widget
        self.setFixedHeight(self._cava_widget._height)
        self.setFixedWidth(
            self._cava_widget._bars_number * (self._cava_widget._bar_width + self._cava_widget._bar_spacing)
        )
        self.setContentsMargins(0, 0, 0, 0)

    def paintEvent(self, event):
        painter = QPainter(self)
        left_margin = self._cava_widget._bar_spacing // 2
        for i, sample in enumerate(self._cava_widget.samples):
            x = left_margin + i * (self._cava_widget._bar_width + self._cava_widget._bar_spacing)
            # Compute height and enforce minimum height of self._cava_widget._min_height
            computed_height = int(sample * self._cava_widget._height)
            height = max(self._cava_widget._min_height, computed_height)
            y = self._cava_widget._height - height
            if height > 0:
                if self._cava_widget._gradient == 1 and self._cava_widget.colors:
                    gradient = QLinearGradient(0, 1, 0, 0)
                    gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
                    stop_step = 1.0 / (len(self._cava_widget.colors) - 1)
                    for idx, color in enumerate(self._cava_widget.colors):
                        gradient.setColorAt(idx * stop_step, color)
                    painter.fillRect(x, y, self._cava_widget._bar_width, height, gradient)
                else:
                    painter.fillRect(x, y, self._cava_widget._bar_width, height, self._cava_widget.foreground_color)


class CavaWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    samplesUpdated = pyqtSignal(list)

    def __init__(
        self,
        bar_height: int,
        min_bar_height: int,
        bars_number: int,
        output_bit_format: str,
        orientation: str,
        bar_spacing: int,
        bar_width: int,
        sleep_timer: int,
        sensitivity: int,
        lower_cutoff_freq: int,
        higher_cutoff_freq: int,
        framerate: int,
        noise_reduction: float,
        mono_option: str,
        reverse: int,
        waveform: int,
        channels: str,
        foreground: str,
        gradient: bool,
        gradient_color_1: str,
        gradient_color_2: str,
        gradient_color_3: str,
        monstercat: int,
        waves: int,
        hide_empty: bool,
        container_padding: dict[str, int],
        callbacks: dict[str, str],
    ):
        super().__init__(class_name="cava-widget")
        # Widget configuration
        self._height = bar_height
        self._min_height = min_bar_height
        self._bars_number = bars_number
        self._output_bit_format = output_bit_format
        self._orientation = orientation
        self._bar_spacing = bar_spacing
        self._bar_width = bar_width
        self._sleep_timer = sleep_timer
        self._sensitivity = sensitivity
        self._lower_cutoff_freq = lower_cutoff_freq
        self._higher_cutoff_freq = higher_cutoff_freq
        self._framerate = framerate
        self._noise_reduction = noise_reduction
        self._mono_option = mono_option
        self._reverse = reverse
        self._waveform = waveform
        self._channels = channels
        self._foreground = foreground
        self._gradient = gradient
        self._gradient_color_1 = gradient_color_1
        self._gradient_color_2 = gradient_color_2
        self._gradient_color_3 = gradient_color_3
        self._monstercat = monstercat
        self._waves = waves
        self._hide_empty = hide_empty
        self._padding = container_padding
        self._hide_cava_widget = True
        self._stop_cava = False

        # Set up samples and colors
        self.samples = [0] * self._bars_number
        self.colors = []

        # Construct container layout
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        self.widget_layout.addWidget(self._widget_container)

        # Check if cava is available
        if shutil.which("cava") is None:
            error_label = QLabel("Cava not installed")
            self._widget_container_layout.addWidget(error_label)
            return

        # Add the custom bar frame
        self._bar_frame = CavaBar(self)
        self._widget_container_layout.addWidget(self._bar_frame)

        self.register_callback("reload_cava", self._reload_cava)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]

        # Connect signal and start audio processing
        self.samplesUpdated.connect(self.on_samples_updated)
        self.destroyed.connect(self.stop_cava)
        self.start_cava()

        # Set up auto-hide timer for silence
        if self._hide_empty and self._sleep_timer > 0:
            self.hide()
            self._hide_timer = QTimer(self)
            self._hide_timer.setInterval(self._sleep_timer * 1000)
            self._hide_timer.timeout.connect(self.hide_bar_frame)

        if QApplication.instance():
            QApplication.instance().aboutToQuit.connect(self.stop_cava)
        atexit.register(self.stop_cava)

    def _reload_cava(self):
        """Stop current cava process and start a new one"""
        try:
            self.stop_cava()

            self.samples = [0] * self._bars_number

            QTimer.singleShot(500, self.start_cava)

            if self._hide_empty and self._sleep_timer > 0:
                if hasattr(self, "_hide_timer"):
                    self._hide_timer.stop()
                self._hide_cava_widget = True
                self.show()
        except Exception as e:
            logging.error(f"Error reloading cava: {e}")

    def stop_cava(self) -> None:
        self._stop_cava = True
        if hasattr(self, "_cava_process") and self._cava_process.poll() is None:
            try:
                self._cava_process.terminate()
                self._cava_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._cava_process.kill()
        if hasattr(self, "thread_cava") and self.thread_cava.is_alive():
            if threading.current_thread() != self.thread_cava:
                self.thread_cava.join(timeout=2)

    def initialize_colors(self) -> None:
        self.foreground_color = QColor(self._foreground)
        if self._gradient == 1:
            for color_str in [self._gradient_color_1, self._gradient_color_2, self._gradient_color_3]:
                try:
                    self.colors.append(QColor(color_str))
                except Exception as e:
                    logging.error(f"Error setting gradient color '{color_str}': {e}")

    def on_samples_updated(self, new_samples: list) -> None:
        try:
            self.samples = new_samples
        except Exception:
            return
        if any(val != 0 for val in new_samples):
            try:
                if self._hide_empty and self._sleep_timer > 0:
                    if self._hide_cava_widget:
                        self.show()
                        self._hide_cava_widget = False
                    self._hide_timer.start()
                self._bar_frame.update()
            except Exception as e:
                logging.error(f"Error updating cava widget: {e}")

    def hide_bar_frame(self) -> None:
        self.hide()
        self._hide_cava_widget = True

    def start_cava(self) -> None:
        # Reset stop flag to allow new process to start
        self._stop_cava = False

        # Build configuration file, temp config file will be created in %temp% directory
        config_template = textwrap.dedent(f"""\
        # Cava config auto-generated by YASB
        [general]
        bars = {self._bars_number}
        bar_spacing = {self._bar_spacing}
        bar_width = {self._bar_width}
        sleep_timer = {self._sleep_timer}
        sensitivity = {self._sensitivity}
        lower_cutoff_freq = {self._lower_cutoff_freq}
        higher_cutoff_freq = {self._higher_cutoff_freq}
        framerate = {self._framerate}
        noise_reduction = {self._noise_reduction}
        [output]
        method = raw
        bit_format = {self._output_bit_format}
        orientation = {self._orientation}
        channels = {self._channels}
        mono_option = {self._mono_option}
        reverse = {self._reverse}
        waveform = {self._waveform}
        [color]
        foreground = '{self._foreground}'
        gradient = {self._gradient}
        gradient_color_1 = '{self._gradient_color_1}'
        gradient_color_2 = '{self._gradient_color_2}'
        gradient_color_3 = '{self._gradient_color_3}'
        [smoothing]
        monstercat = {self._monstercat}
        waves = {self._waves}
        """)

        self.initialize_colors()

        # Determine byte type settings for reading audio data
        if self._output_bit_format == "16bit":
            bytetype, bytesize, bytenorm = ("H", 2, 65535)
        else:
            bytetype, bytesize, bytenorm = ("B", 1, 255)

        def process_audio():
            cava_config_path = None
            try:
                cava_config_path = app_data_path("yasb_cava_config")
                with open(cava_config_path, "w") as config_file:
                    config_file.write(config_template)
                    config_file.flush()

                self._cava_process = subprocess.Popen(
                    ["cava", "-p", cava_config_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

                chunk = bytesize * self._bars_number
                fmt = bytetype * self._bars_number

                while not self._stop_cava:
                    try:
                        data = self._cava_process.stdout.read(chunk)
                        if len(data) < chunk:
                            break
                        samples = [val / bytenorm for val in struct.unpack(fmt, data)]
                        self.samplesUpdated.emit(samples)
                    except Exception as e:
                        logging.error(f"Error reading cava data: {e}")
                        break

            except Exception as e:
                logging.error(f"Error starting cava process: {e}")
            finally:
                # Clean up config file
                if cava_config_path and os.path.exists(cava_config_path):
                    try:
                        os.unlink(cava_config_path)
                    except:
                        pass

        # Wait for previous thread to finish if it exists
        if hasattr(self, "thread_cava") and self.thread_cava.is_alive():
            self.thread_cava.join(timeout=1)

        self.thread_cava = threading.Thread(target=process_audio, daemon=True)
        self.thread_cava.start()
