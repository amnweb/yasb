import atexit
import logging
import os
import shutil
import struct
import subprocess
import threading

from PyQt6.QtCore import QPointF, QRectF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel

from core.utils.utilities import app_data_path
from core.validation.widgets.yasb.cava import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class CavaBar(QFrame):
    def __init__(self, cava_widget):
        super().__init__()
        self._dpr = None
        self._cava_widget = cava_widget
        self.setFixedHeight(self._cava_widget._height)
        self.setFixedWidth(
            self._cava_widget._bars_number
            * (
                self._cava_widget._bar_width
                + (
                    self._cava_widget._bar_spacing
                    if self._cava_widget._bar_type == "bars_mirrored" or self._cava_widget._bar_type == "bars"
                    else 0
                )
            )
        )
        self.setContentsMargins(0, 0, 0, 0)

    def _device_pixel_ratio(self, painter) -> float:
        """Return device pixel ratio for the painter's device."""
        if self._dpr is not None:
            return self._dpr

        try:
            dev = painter.device()
            dpr = float(dev.devicePixelRatioF())
        except Exception:
            dpr = 1.0

        self._dpr = dpr if dpr > 0 else 1.0
        return self._dpr

    def _get_fade_opacity(self, x_position):
        """Calculate opacity based on position for edge fade effect."""
        fade_left = self._cava_widget._edge_fade_left
        fade_right = self._cava_widget._edge_fade_right

        if fade_left <= 0 and fade_right <= 0:
            return 1.0

        widget_width = self.width()

        if fade_left > 0 and fade_right > 0:
            # Both sides have fade - cap each to half width to prevent overlap
            max_fade_width = widget_width / 2
            effective_fade_left = min(fade_left, max_fade_width)
            effective_fade_right = min(fade_right, max_fade_width)
        else:
            # Only one side has fade - allow it to use full width if needed
            effective_fade_left = min(fade_left, widget_width) if fade_left > 0 else 0
            effective_fade_right = min(fade_right, widget_width) if fade_right > 0 else 0

        # Left edge fade (0 to effective_fade_left)
        if effective_fade_left > 0 and x_position <= effective_fade_left:
            return max(0.0, x_position / effective_fade_left)

        # Right edge fade (widget_width - effective_fade_right to widget_width)
        elif effective_fade_right > 0 and x_position >= widget_width - effective_fade_right:
            return max(0.0, (widget_width - x_position) / effective_fade_right)

        # Middle area - full opacity
        return 1.0

    def paintEvent(self, event):
        """Draw the cava bars according to the selected style."""
        painter = QPainter(self)

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        except Exception:
            pass

        if self._cava_widget._bar_type == "bars_mirrored":
            self.draw_bars_mirrored(painter)
        elif self._cava_widget._bar_type == "waves":
            self.draw_waves(painter)
        elif self._cava_widget._bar_type == "waves_mirrored":
            self.draw_waves_mirrored(painter)
        else:
            self.draw_bars(painter)

    def draw_bars(self, painter):
        """Draw traditional bar visualization"""
        dpr = self._device_pixel_ratio(painter)

        bar_w_px = max(1, round(self._cava_widget._bar_width * dpr))
        bar_s_px = max(0, round(self._cava_widget._bar_spacing * dpr))
        left_margin_px = round((self._cava_widget._bar_spacing / 2.0) * dpr)

        for i, sample in enumerate(self._cava_widget.samples):
            min_height_logical = float(self._cava_widget._min_height) / dpr
            computed_height = sample * float(self._cava_widget._height)
            height = max(min_height_logical, computed_height)
            if height > 0.0:
                x_px = left_margin_px + i * (bar_w_px + bar_s_px)
                y_px = max(0, round((float(self._cava_widget._height) - height) * dpr))
                h_px = max(1, round(height * dpr))

                rx = x_px / dpr
                ry = y_px / dpr
                rw = bar_w_px / dpr
                rh = h_px / dpr

                if self._cava_widget._gradient == 1 and self._cava_widget.colors:
                    gradient = QLinearGradient(0, 1, 0, 0)
                    gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
                    stop_step = 1.0 / (len(self._cava_widget.colors) - 1)
                    for idx, color in enumerate(self._cava_widget.colors):
                        gradient.setColorAt(idx * stop_step, color)

                    if self._cava_widget._edge_fade_left > 0 or self._cava_widget._edge_fade_right > 0:
                        fade_opacity = self._get_fade_opacity(rx + rw / 2)
                        painter.setOpacity(fade_opacity)

                    painter.fillRect(QRectF(rx, ry, rw, rh), gradient)
                else:
                    if self._cava_widget._edge_fade_left > 0 or self._cava_widget._edge_fade_right > 0:
                        fade_opacity = self._get_fade_opacity(rx + rw / 2)
                        painter.setOpacity(fade_opacity)

                    painter.fillRect(QRectF(rx, ry, rw, rh), self._cava_widget.foreground_color)

    def draw_bars_mirrored(self, painter):
        """Draw mirrored bar visualization"""
        if not self._cava_widget.samples:
            return
        dpr = self._device_pixel_ratio(painter)
        width = self.width()
        height = float(self._cava_widget._height)
        samples = self._cava_widget.samples
        center_y = height / 2.0

        band_w_px = max(1, round(self._cava_widget._bar_width * dpr))
        band_s_px = max(0, round(self._cava_widget._bar_spacing * dpr))

        total_w_px = max(1, round(float(width) * dpr))
        bars_count = len(samples)
        total_bars_width_px = bars_count * band_w_px + max(0, (bars_count - 1)) * band_s_px
        left_margin_px = max(0, (total_w_px - total_bars_width_px) // 2)

        # Precompute brushes (single gradient instance reused)
        if self._cava_widget._gradient == 1 and self._cava_widget.colors:
            stop_step = 1.0 / (len(self._cava_widget.colors) - 1)
            gradient_upper = QLinearGradient(0, 1, 0, 0)
            gradient_upper.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
            gradient_lower = QLinearGradient(0, 0, 0, 1)
            gradient_lower.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
            for idx, color in enumerate(self._cava_widget.colors):
                gradient_upper.setColorAt(idx * stop_step, color)
                gradient_lower.setColorAt(idx * stop_step, color)
            brush_upper = gradient_upper
            brush_lower = gradient_lower
        else:
            brush_upper = brush_lower = self._cava_widget.foreground_color

        for i, sample in enumerate(samples):
            ux_px = left_margin_px + i * (band_w_px + band_s_px)

            min_height_logical = float(self._cava_widget._min_height) / dpr
            full_height_logical = max(min_height_logical, sample * float(self._cava_widget._height))

            full_h_px = round(full_height_logical * dpr)
            if full_h_px <= 0:
                continue

            up_px = full_h_px // 2
            down_px = full_h_px - up_px

            uy_px = max(0, round(center_y * dpr) - up_px)
            if up_px > 0:
                if self._cava_widget._edge_fade_left > 0 or self._cava_widget._edge_fade_right > 0:
                    fade_opacity = self._get_fade_opacity(ux_px / dpr + (band_w_px / dpr) / 2)
                    painter.setOpacity(fade_opacity)

                painter.fillRect(QRectF(ux_px / dpr, uy_px / dpr, band_w_px / dpr, up_px / dpr), brush_upper)

            ly_px = round(center_y * dpr)
            if down_px > 0:
                max_h_px = round(height * dpr)
                if ly_px + down_px > max_h_px:
                    down_px = max(0, max_h_px - ly_px)
                if down_px > 0:
                    if self._cava_widget._edge_fade_left > 0 or self._cava_widget._edge_fade_right > 0:
                        fade_opacity = self._get_fade_opacity(ux_px / dpr + (band_w_px / dpr) / 2)
                        painter.setOpacity(fade_opacity)

                    painter.fillRect(QRectF(ux_px / dpr, ly_px / dpr, band_w_px / dpr, down_px / dpr), brush_lower)

    def draw_waves(self, painter, radius=1):
        """Draw wave visualization."""
        if not self._cava_widget.samples:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        dpr = self._device_pixel_ratio(painter)

        height = float(self._cava_widget._height)
        samples = self._cava_widget.samples

        if self._cava_widget._gradient == 1 and self._cava_widget.colors:
            stop_step = 1.0 / (len(self._cava_widget.colors) - 1)
            gradient = QLinearGradient(0, 1, 0, 0)
            gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
            for idx, color in enumerate(self._cava_widget.colors):
                gradient.setColorAt(idx * stop_step, color)
            brush = gradient
        else:
            brush = self._cava_widget.foreground_color

        n = len(samples)
        if n == 0:
            return

        def smooth(i: int) -> float:
            start = max(0, i - radius)
            end = min(n, i + radius + 1)
            window = samples[start:end]
            return sum(window) / len(window) if window else 0.0

        widget_w = float(self.width())
        step = widget_w / max(1, n)
        points = []
        min_h_logical = float(self._cava_widget._min_height) / dpr
        for i in range(n):
            cx = i * step + step / 2.0
            val = max(min_h_logical, smooth(i) * height)
            top = max(0.0, height - val)
            points.append(QPointF(cx, top))

        path = QPainterPath()
        bottom = height
        path.moveTo(points[0].x(), bottom)
        path.lineTo(points[0])
        for p in points[1:]:
            path.lineTo(p)
        path.lineTo(points[-1].x(), bottom)
        path.closeSubpath()

        if self._cava_widget._edge_fade_left > 0 or self._cava_widget._edge_fade_right > 0:
            # Draw wave in strips with varying opacity
            widget_width = self.width()
            widget_height = int(height)  # Convert to int for setClipRect
            strip_width = 1  # 1 pixel wide strips for smooth fade

            for x in range(int(widget_width)):
                opacity = self._get_fade_opacity(x)
                if opacity > 0:
                    painter.setOpacity(opacity)
                    # Create a clip rect for this strip
                    painter.setClipRect(x, 0, strip_width, widget_height)
                    painter.fillPath(path, brush)

            # Reset clipping and opacity
            painter.setClipRect(0, 0, int(widget_width), widget_height)
            painter.setOpacity(1.0)
        else:
            # No fade effect - use simple fillPath for efficiency
            painter.fillPath(path, brush)

    def draw_waves_mirrored(self, painter, radius=1):
        """Draw a mirrored wave visualization."""
        if not self._cava_widget.samples:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        dpr = self._device_pixel_ratio(painter)
        height = float(self._cava_widget._height)
        samples = self._cava_widget.samples
        center_y = height / 2.0

        if self._cava_widget._gradient == 1 and self._cava_widget.colors:
            colors_len = len(self._cava_widget.colors)
            stop_step = 1.0 / (colors_len - 1) if colors_len > 1 else 1.0
            gradient = QLinearGradient(0, 0, 0, 1)
            gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
            for idx, color in enumerate(self._cava_widget.colors):
                s = idx * stop_step
                pos_top = max(0.0, 0.5 - s * 0.5)
                pos_bottom = min(1.0, 0.5 + s * 0.5)
                gradient.setColorAt(pos_top, color)
                gradient.setColorAt(pos_bottom, color)
            fill_brush = gradient
        else:
            fill_brush = self._cava_widget.foreground_color

        n = len(samples)
        if n == 0:
            return

        def smooth(i: int) -> float:
            start = max(0, i - radius)
            end = min(n, i + radius + 1)
            window = samples[start:end]
            return sum(window) / len(window) if window else 0.0

        widget_w = float(self.width())
        step = widget_w / max(1, n)

        top_points = []
        bottom_points = []
        min_h_logical = float(self._cava_widget._min_height) / dpr
        for i in range(n):
            cx = i * step + step / 2.0
            val = max(min_h_logical, smooth(i) * height / 2.0)
            top_y = max(0.0, center_y - val)
            bottom_y = min(height, center_y + val)
            top_points.append(QPointF(cx, top_y))
            bottom_points.append(QPointF(cx, bottom_y))

        combined = QPainterPath()
        combined.moveTo(top_points[0].x(), center_y)
        combined.lineTo(top_points[0])
        for p in top_points[1:]:
            combined.lineTo(p)
        for p in reversed(bottom_points):
            combined.lineTo(p)
        combined.closeSubpath()

        if self._cava_widget._edge_fade_left > 0 or self._cava_widget._edge_fade_right > 0:
            # Draw wave in strips with varying opacity
            widget_width = self.width()
            widget_height = int(height)  # Convert to int for setClipRect
            strip_width = 1  # 1 pixel wide strips for smooth fade

            for x in range(int(widget_width)):
                opacity = self._get_fade_opacity(x)
                if opacity > 0:
                    painter.setOpacity(opacity)
                    # Create a clip rect for this strip
                    painter.setClipRect(x, 0, strip_width, widget_height)
                    painter.fillPath(combined, fill_brush)

            # Reset clipping and opacity
            painter.setClipRect(0, 0, int(widget_width), widget_height)
            painter.setOpacity(1.0)
        else:
            # No fade effect - use simple fillPath for efficiency
            painter.fillPath(combined, fill_brush)


class CavaWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    samplesUpdated = pyqtSignal(list)
    _instance_counter = 0  # Class variable to track instances

    def __init__(
        self,
        class_name: str,
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
        bar_type: str,
        edge_fade: int | list[int],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
    ):
        super().__init__(class_name=f"cava-widget {class_name}")
        # Assign unique instance ID
        CavaWidget._instance_counter += 1
        self._instance_id = CavaWidget._instance_counter

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
        self._bar_type = bar_type

        # Parse edge_fade parameter - support both integer and [left, right] formats
        if isinstance(edge_fade, list) and len(edge_fade) == 2:
            self._edge_fade_left = edge_fade[0]
            self._edge_fade_right = edge_fade[1]
        else:
            # Single value applies to both sides
            self._edge_fade_left = edge_fade
            self._edge_fade_right = edge_fade

        # Set up samples and colors
        self.samples = [0] * self._bars_number
        self.colors = []

        # Construct container layout
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )
        self._widget_container = QFrame()
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
        self.colors.clear()
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
                if not color_str:
                    continue
                try:
                    c = QColor(color_str)
                    if not c.isValid():
                        logging.error(f"Invalid gradient color specified: {color_str}")
                    self.colors.append(c)
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

        # Build configuration file, temp config file will be created in YASB TEMP directory
        lines = []
        lines.append("# Cava config auto-generated by YASB")
        lines.append("[general]")
        lines.append(f"bars = {self._bars_number}")
        lines.append(f"bar_spacing = {self._bar_spacing}")
        lines.append(f"bar_width = {self._bar_width}")
        lines.append(f"sleep_timer = {self._sleep_timer}")
        lines.append(f"sensitivity = {self._sensitivity}")
        lines.append(f"lower_cutoff_freq = {self._lower_cutoff_freq}")
        lines.append(f"higher_cutoff_freq = {self._higher_cutoff_freq}")
        lines.append(f"framerate = {self._framerate}")
        lines.append("")
        lines.append("[output]")
        lines.append("method = raw")
        lines.append(f"bit_format = {self._output_bit_format}")
        lines.append(f"orientation = {self._orientation}")
        lines.append(f"channels = {self._channels}")
        lines.append(f"mono_option = {self._mono_option}")
        lines.append(f"reverse = {self._reverse}")
        lines.append(f"waveform = {self._waveform}")
        lines.append("")
        lines.append("[color]")
        lines.append(f"foreground = '{self._foreground}'")
        lines.append(f"gradient = {self._gradient}")
        if getattr(self, "_gradient_color_1", None):
            lines.append(f"gradient_color_1 = '{self._gradient_color_1}'")
        if getattr(self, "_gradient_color_2", None):
            lines.append(f"gradient_color_2 = '{self._gradient_color_2}'")
        if getattr(self, "_gradient_color_3", None):
            lines.append(f"gradient_color_3 = '{self._gradient_color_3}'")
        lines.append("")
        lines.append("[smoothing]")
        lines.append(f"monstercat = {self._monstercat}")
        lines.append(f"waves = {self._waves}")
        lines.append(f"noise_reduction = {self._noise_reduction}")

        config_template = "\n".join(lines) + "\n"

        self.initialize_colors()

        # Determine byte type settings for reading audio data
        if self._output_bit_format == "16bit":
            bytetype, bytesize, bytenorm = ("H", 2, 65535)
        else:
            bytetype, bytesize, bytenorm = ("B", 1, 255)

        def process_audio():
            cava_config_path = None
            try:
                cava_config_path = app_data_path(f"yasb_cava_config_{self._instance_id}")
                with open(cava_config_path, "w") as config_file:
                    config_file.write(config_template)
                    config_file.flush()

                self._cava_process = subprocess.Popen(
                    ["cava", "-p", cava_config_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
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
