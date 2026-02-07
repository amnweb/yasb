import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel

from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.utils.widgets.obs.obs_client import ObsWebSocketClient, ObsWorker
from core.validation.widgets.yasb.obs import ObsConfig
from core.widgets.base import BaseWidget


class ObsWidget(BaseWidget):
    validation_schema = ObsConfig

    _opacity_timer: QTimer | None = None
    _time_timer: QTimer | None = None
    _subscribers: list = []

    def __init__(self, config: ObsConfig):
        super().__init__(class_name="obs-widget")

        self._icons = config.icons.model_dump()
        self._connection = config.connection.model_dump()
        self._hide_when_not_recording = config.hide_when_not_recording
        self._blinking_icon = config.blinking_icon
        self._show_record_time = config.show_record_time
        self._show_virtual_cam = config.show_virtual_cam
        self._show_studio_mode = config.show_studio_mode
        self._show_stream = config.show_stream
        self._show_stream_time = config.show_stream_time
        self._show_scene_name = config.show_scene_name
        self._show_stream_stats = config.show_stream_stats
        self._tooltip = config.tooltip
        self._is_recording = False
        self._is_paused = False
        self._is_streaming = False
        self._is_stream_starting = False
        self._is_stream_stopping = False
        self._virtual_cam_active = False
        self._studio_mode_active = False
        self._opacity_low = False

        # Local time tracking (base_ms + timestamp for local computation)
        self._record_base_ms: int = 0
        self._record_base_time: float = 0.0
        self._stream_base_ms: int = 0
        self._stream_base_time: float = 0.0
        self._record_sync_counter: int = 0
        self._stream_sync_counter: int = 0
        self._prev_stream_bytes: int = 0

        self.client: ObsWebSocketClient | None = None
        self.worker: ObsWorker | None = None

        self._init_ui()
        self._init_callbacks()
        self._init_worker()

    def _init_ui(self):
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        self.widget_layout.addWidget(self._widget_container)

        # Record button
        self._record_btn = QLabel(self._icons["stopped"])
        self._record_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._record_btn.setProperty("class", "icon record stopped")
        self._record_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._record_btn.mousePressEvent = lambda e: (
            self.toggle_record() if e.button() == Qt.MouseButton.LeftButton else None
        )
        if self._tooltip:
            set_tooltip(self._record_btn, "Toggle Recording", position="top")
        self._opacity_effect = QGraphicsOpacityEffect(self._record_btn)
        self._opacity_effect.setOpacity(1.0)
        self._record_btn.setGraphicsEffect(self._opacity_effect)
        self._widget_container_layout.addWidget(self._record_btn)

        # Virtual cam button
        self._virtual_cam_btn = QLabel(self._icons["virtual_cam_off"])
        self._virtual_cam_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._virtual_cam_btn.setProperty("class", "icon virtual-cam off")
        self._virtual_cam_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._virtual_cam_btn.mousePressEvent = lambda e: (
            self.toggle_virtual_cam() if e.button() == Qt.MouseButton.LeftButton else None
        )
        if self._tooltip:
            set_tooltip(self._virtual_cam_btn, "Toggle Virtual Camera", position="top")
        self._widget_container_layout.addWidget(self._virtual_cam_btn)
        if not self._show_virtual_cam:
            self._virtual_cam_btn.hide()

        # Studio mode button
        self._studio_mode_btn = QLabel(self._icons["studio_mode_off"])
        self._studio_mode_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._studio_mode_btn.setProperty("class", "icon studio-mode off")
        self._studio_mode_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._studio_mode_btn.mousePressEvent = lambda e: (
            self.toggle_studio_mode() if e.button() == Qt.MouseButton.LeftButton else None
        )
        if self._tooltip:
            set_tooltip(self._studio_mode_btn, "Toggle Studio Mode", position="top")
        self._widget_container_layout.addWidget(self._studio_mode_btn)
        if not self._show_studio_mode:
            self._studio_mode_btn.hide()

        # Stream button
        self._stream_btn = QLabel(self._icons["streaming_stopped"])
        self._stream_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stream_btn.setProperty("class", "icon stream off")
        self._stream_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._stream_btn.mousePressEvent = lambda e: (
            self.toggle_stream() if e.button() == Qt.MouseButton.LeftButton else None
        )
        if self._tooltip:
            set_tooltip(self._stream_btn, "Toggle Stream", position="top")
        self._stream_opacity_effect = QGraphicsOpacityEffect(self._stream_btn)
        self._stream_opacity_effect.setOpacity(1.0)
        self._stream_btn.setGraphicsEffect(self._stream_opacity_effect)
        self._widget_container_layout.addWidget(self._stream_btn)
        if not self._show_stream:
            self._stream_btn.hide()

        # Record time label
        self._time_label = QLabel()
        self._time_label.setProperty("class", "label record-time")
        self._widget_container_layout.addWidget(self._time_label)
        self._time_label.hide()

        # Stream time label
        self._stream_time_label = QLabel()
        self._stream_time_label.setProperty("class", "label stream-time")
        self._widget_container_layout.addWidget(self._stream_time_label)
        self._stream_time_label.hide()

        # Scene name label
        self._scene_label = QLabel()
        self._scene_label.setProperty("class", "label scene-name")
        self._widget_container_layout.addWidget(self._scene_label)
        if not self._show_scene_name:
            self._scene_label.hide()

        # Stream stats label (bitrate / dropped frames)
        self._stream_stats_label = QLabel()
        self._stream_stats_label.setProperty("class", "label stream-stats")
        self._widget_container_layout.addWidget(self._stream_stats_label)
        self._stream_stats_label.hide()

        if self._hide_when_not_recording:
            self.hide()

    def _init_callbacks(self):
        self.register_callback("toggle_record", self.toggle_record)
        self.register_callback("start_record", lambda: self.client and self.client.send("StartRecord"))
        self.register_callback("stop_record", lambda: self.client and self.client.send("StopRecord"))
        self.register_callback("pause_record", self.pause_recording)
        self.register_callback("resume_record", self.resume_recording)
        self.register_callback("toggle_record_pause", self.toggle_record_pause)
        self.register_callback("toggle_virtual_cam", self.toggle_virtual_cam)
        self.register_callback("toggle_studio_mode", self.toggle_studio_mode)
        self.register_callback("toggle_stream", self.toggle_stream)
        self.register_callback("start_stream", lambda: self.client and self.client.send("StartStream"))
        self.register_callback("stop_stream", lambda: self.client and self.client.send("StopStream"))

    def _init_worker(self):
        self.worker = ObsWorker.get_instance(self._connection)

        # Connect signals BEFORE starting worker to avoid race condition
        self.worker.connection_signal.connect(self._on_connection)
        self.worker.state_signal.connect(self._on_state)
        self.worker.stream_signal.connect(self._on_stream_state)
        self.worker.virtual_cam_signal.connect(self._on_virtual_cam)
        self.worker.studio_mode_signal.connect(self._on_studio_mode)
        self.worker.scene_signal.connect(self._on_scene_changed)

        if not self.worker.isRunning():
            self.worker.start()

        # Always check if already connected (signal may have been missed)
        if self.worker._connected and self.worker.client and self.worker.client.connected:
            self._on_connection(True)

        # Shared timers
        if ObsWidget._opacity_timer is None:
            ObsWidget._opacity_timer = QTimer()
            ObsWidget._opacity_timer.setInterval(500)
            ObsWidget._opacity_timer.timeout.connect(ObsWidget._on_opacity_tick)

        if ObsWidget._time_timer is None:
            ObsWidget._time_timer = QTimer()
            ObsWidget._time_timer.setInterval(1000)
            ObsWidget._time_timer.timeout.connect(ObsWidget._on_time_tick)

        ObsWidget._subscribers.append(self)

    # Signal handlers
    def _on_connection(self, connected: bool):
        if connected:
            self.client = self.worker.client if self.worker else None
            self._refresh_status()
        else:
            self.client = None
            self._stop_timers()
            if self._hide_when_not_recording:
                self.hide()

    def _on_state(self, data: dict):
        active, paused = self._parse_state(data)
        self._update_record_ui(active, paused)

    def _on_virtual_cam(self, active: bool):
        if self._virtual_cam_btn:
            self._virtual_cam_active = active
            self._virtual_cam_btn.setText(self._icons["virtual_cam_on" if active else "virtual_cam_off"])
            self._virtual_cam_btn.setProperty("class", f"icon virtual-cam {'on' if active else 'off'}")
            refresh_widget_style(self._virtual_cam_btn)

    def _on_studio_mode(self, enabled: bool):
        if self._studio_mode_btn:
            self._studio_mode_active = enabled
            self._studio_mode_btn.setText(self._icons["studio_mode_on" if enabled else "studio_mode_off"])
            self._studio_mode_btn.setProperty("class", f"icon studio-mode {'on' if enabled else 'off'}")
            refresh_widget_style(self._studio_mode_btn)

    def _on_scene_changed(self, scene_name: str):
        if self._scene_label and self._show_scene_name:
            self._scene_label.setText(scene_name)
            self._scene_label.show()

    def _on_stream_state(self, data: dict):
        state = str(data.get("outputState", "")).upper()
        active = data.get("outputActive", False)
        if "STARTING" in state:
            self._update_stream_ui(active=False, starting=True, stopping=False)
        elif "STOPPING" in state:
            self._update_stream_ui(active=False, starting=False, stopping=True)
        elif "STARTED" in state or "RECONNECTED" in state:
            self._update_stream_ui(active=True, starting=False, stopping=False)
        else:
            self._update_stream_ui(active=active, starting=False, stopping=False)

    # Actions
    def toggle_record(self):
        if not self.client:
            return
        if self._is_recording or self._is_paused:
            self.client.send("StopRecord")
            if self._time_label:
                self._time_label.setText("")
        else:
            self.client.send("StartRecord")

    def pause_recording(self):
        if self.client and self._is_recording:
            self.client.send("PauseRecord")

    def resume_recording(self):
        if self.client and self._is_paused:
            self.client.send("ResumeRecord")

    def toggle_record_pause(self):
        if not self.client:
            return
        if self._is_recording:
            self.client.send("PauseRecord")
        elif self._is_paused:
            self.client.send("ResumeRecord")

    def toggle_virtual_cam(self):
        if self.client:
            self.client.send("ToggleVirtualCam")

    def toggle_studio_mode(self):
        if self.client:
            self.client.send("SetStudioModeEnabled", {"studioModeEnabled": not self._studio_mode_active})

    def toggle_stream(self):
        if not self.client:
            return
        if self._is_stream_starting or self._is_stream_stopping:
            return
        if self._is_streaming:
            self.client.send("StopStream")
        else:
            self.client.send("StartStream")

    # Status refresh
    def _refresh_status(self):
        if not self.client:
            return
        try:
            data = self.client.call("GetRecordStatus")
            active, paused = self._parse_state(data)
            self._update_record_ui(active, paused)
            self._update_time(data)
        except Exception:
            pass

        if self._show_virtual_cam:
            try:
                result = self.client.call("GetVirtualCamStatus")
                self._on_virtual_cam(result.get("outputActive", False))
            except Exception:
                pass

        if self._show_studio_mode:
            try:
                result = self.client.call("GetStudioModeEnabled")
                self._on_studio_mode(result.get("studioModeEnabled", False))
            except Exception:
                pass

        if self._show_stream:
            try:
                result = self.client.call("GetStreamStatus")
                self._update_stream_ui(result.get("outputActive", False))
                self._update_stream_time(result)
                if self._show_stream_stats and result.get("outputActive", False):
                    self._update_stream_stats(result)
            except Exception:
                pass

        if self._show_scene_name:
            try:
                result = self.client.call("GetCurrentProgramScene")
                scene_name = result.get("sceneName", result.get("currentProgramSceneName", ""))
                self._on_scene_changed(scene_name)
            except Exception:
                pass

    def _update_record_ui(self, active: bool, paused: bool):
        self._is_recording = active and not paused
        self._is_paused = paused

        if paused:
            # Freeze the duration at current computed value
            if self._record_base_time > 0:
                elapsed = int((time.monotonic() - self._record_base_time) * 1000)
                self._record_base_ms = self._record_base_ms + elapsed
                self._record_base_time = time.monotonic()
            self._record_btn.setText(self._icons["paused"])
            self._record_btn.setProperty("class", "icon record paused")
            self._start_time_timer()
            self._stop_opacity_timer()
            if self._time_label and self._show_record_time:
                self._time_label.show()
        elif active:
            self._record_btn.setText(self._icons["recording"])
            self._record_btn.setProperty("class", "icon record recording")
            if self._record_base_time == 0.0:
                self._record_base_time = time.monotonic()
            self._start_time_timer()
            if self._blinking_icon:
                self._start_opacity_timer()
            if self._time_label and self._show_record_time:
                self._time_label.show()
        else:
            self._record_btn.setText(self._icons["stopped"])
            self._record_btn.setProperty("class", "icon record stopped")
            self._record_base_ms = 0
            self._record_base_time = 0.0
            self._record_sync_counter = 0
            self._stop_timers()
            if self._time_label:
                self._time_label.setText("")
                self._time_label.hide()

        refresh_widget_style(self._record_btn)

        if self._hide_when_not_recording:
            self.show() if (active or paused) else self.hide()

    def _update_time(self, data: dict):
        if not self._time_label:
            return
        duration_ms = data.get("outputDuration", 0)
        if duration_ms:
            self._record_base_ms = duration_ms
            self._record_base_time = time.monotonic()
            self._time_label.setText(self._format_duration(duration_ms))

    def _update_stream_ui(self, active: bool, starting: bool = False, stopping: bool = False):
        self._is_streaming = active
        self._is_stream_starting = starting
        self._is_stream_stopping = stopping
        if self._stream_btn:
            if starting:
                self._stream_btn.setText(self._icons["streaming"])
                self._stream_btn.setProperty("class", "icon stream starting")
            elif stopping:
                self._stream_btn.setText(self._icons["streaming_stopped"])
                self._stream_btn.setProperty("class", "icon stream stopping")
            elif active:
                self._stream_btn.setText(self._icons["streaming"])
                self._stream_btn.setProperty("class", "icon stream on")
            else:
                self._stream_btn.setText(self._icons["streaming_stopped"])
                self._stream_btn.setProperty("class", "icon stream off")
            refresh_widget_style(self._stream_btn)
        if active or starting:
            if self._blinking_icon:
                self._start_opacity_timer()
            if active:
                if self._stream_base_time == 0.0:
                    self._stream_base_ms = 0
                    self._stream_base_time = time.monotonic()
                self._start_time_timer()
                if self._stream_time_label and self._show_stream_time:
                    self._stream_time_label.show()
        else:
            self._stream_base_ms = 0
            self._stream_base_time = 0.0
            self._stream_sync_counter = 0
            self._prev_stream_bytes = 0
            if self._stream_time_label:
                self._stream_time_label.setText("")
                self._stream_time_label.hide()
            if self._stream_stats_label:
                self._stream_stats_label.setText("")
                self._stream_stats_label.hide()
            if not active and not starting:
                self._stream_opacity_effect.setOpacity(1.0)

    def _update_stream_time(self, data: dict):
        if not self._stream_time_label:
            return
        duration_ms = data.get("outputDuration", 0)
        if duration_ms:
            self._stream_base_ms = duration_ms
            self._stream_base_time = time.monotonic()
            self._stream_time_label.setText(self._format_duration(duration_ms))

    def _update_stream_stats(self, data: dict):
        if not self._stream_stats_label or not self._show_stream_stats:
            return
        current_bytes = data.get("outputBytes", 0)
        delta_bytes = current_bytes - self._prev_stream_bytes
        self._prev_stream_bytes = current_bytes
        # delta_bytes per ~1 second tick -> convert to kbps
        kbps = (delta_bytes * 8) / 1000 if delta_bytes > 0 else 0
        skipped = data.get("outputSkippedFrames", 0)
        total = data.get("outputTotalFrames", 0)
        self._stream_stats_label.setText(f"{kbps:.0f} kbps {skipped}/{total} dropped")
        self._stream_stats_label.show()

    @staticmethod
    def _format_duration(ms: int) -> str:
        total_seconds = ms // 1000
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _parse_state(self, data: dict) -> tuple[bool, bool]:
        state = data.get("outputState")
        if state:
            s = str(state).upper()
            if "PAUSED" in s:
                return True, True
            if any(x in s for x in ("STARTED", "RESUMED", "STARTING")):
                return True, False
            return False, False
        return bool(data.get("outputActive")), bool(data.get("outputPaused"))

    # Timers
    def _start_opacity_timer(self):
        if ObsWidget._opacity_timer and not ObsWidget._opacity_timer.isActive():
            ObsWidget._opacity_timer.start()

    def _stop_opacity_timer(self):
        self._opacity_effect.setOpacity(1.0)
        self._stream_opacity_effect.setOpacity(1.0)
        if not any(
            (s._is_recording or s._is_streaming or s._is_stream_starting) and s._blinking_icon
            for s in ObsWidget._subscribers
        ):
            if ObsWidget._opacity_timer:
                ObsWidget._opacity_timer.stop()

    def _start_time_timer(self):
        needs_time = self._show_record_time or self._show_stream_time or self._show_stream_stats
        if needs_time and ObsWidget._time_timer and not ObsWidget._time_timer.isActive():
            ObsWidget._time_timer.start()

    def _stop_timers(self):
        self._stop_opacity_timer()
        needs_time = any(
            ((s._is_recording or s._is_paused) and s._show_record_time)
            or (s._is_streaming and (s._show_stream_time or s._show_stream_stats))
            for s in ObsWidget._subscribers
        )
        if not needs_time:
            if ObsWidget._time_timer:
                ObsWidget._time_timer.stop()

    @staticmethod
    def _on_opacity_tick():
        for s in ObsWidget._subscribers:
            if s._blinking_icon:
                s._opacity_low = not s._opacity_low
                opacity = 0.6 if s._opacity_low else 1.0
                if s._is_recording:
                    s._opacity_effect.setOpacity(opacity)
                if s._is_streaming or s._is_stream_starting:
                    s._stream_opacity_effect.setOpacity(opacity)

    @staticmethod
    def _on_time_tick():
        now = time.monotonic()
        for s in ObsWidget._subscribers:
            if (s._is_recording or s._is_paused) and s._show_record_time:
                s._record_sync_counter += 1
                if s._is_paused:
                    # When paused, just display stored base (doesn't advance)
                    s._time_label.setText(ObsWidget._format_duration(s._record_base_ms))
                else:
                    elapsed = int((now - s._record_base_time) * 1000)
                    s._time_label.setText(ObsWidget._format_duration(s._record_base_ms + elapsed))
                # Resync with OBS every 30 seconds
                if s._record_sync_counter >= 30:
                    s._record_sync_counter = 0
                    s._resync_record_time()
            if s._is_streaming and s._show_stream_time:
                s._stream_sync_counter += 1
                elapsed = int((now - s._stream_base_time) * 1000)
                s._stream_time_label.setText(ObsWidget._format_duration(s._stream_base_ms + elapsed))
                # Resync with OBS every 30 seconds
                if s._stream_sync_counter >= 30:
                    s._stream_sync_counter = 0
                    s._resync_stream_time()
            if s._is_streaming and s._show_stream_stats:
                s._refresh_stream_stats()

    def _resync_record_time(self):
        if not self.client:
            return
        try:
            data = self.client.call("GetRecordStatus")
            duration_ms = data.get("outputDuration", 0)
            if duration_ms:
                self._record_base_ms = duration_ms
                self._record_base_time = time.monotonic()
        except Exception:
            pass

    def _resync_stream_time(self):
        if not self.client:
            return
        try:
            result = self.client.call("GetStreamStatus")
            duration_ms = result.get("outputDuration", 0)
            if duration_ms:
                self._stream_base_ms = duration_ms
                self._stream_base_time = time.monotonic()
        except Exception:
            pass

    def _refresh_stream_stats(self):
        if not self.client:
            return
        try:
            result = self.client.call("GetStreamStatus")
            self._update_stream_stats(result)
        except Exception:
            pass

    def closeEvent(self, event):
        if self in ObsWidget._subscribers:
            ObsWidget._subscribers.remove(self)

        if self.worker:
            try:
                self.worker.connection_signal.disconnect(self._on_connection)
                self.worker.state_signal.disconnect(self._on_state)
                self.worker.stream_signal.disconnect(self._on_stream_state)
                self.worker.virtual_cam_signal.disconnect(self._on_virtual_cam)
                self.worker.studio_mode_signal.disconnect(self._on_studio_mode)
                self.worker.scene_signal.disconnect(self._on_scene_changed)
            except Exception:
                pass
            ObsWorker.release_instance()

            if not ObsWidget._subscribers:
                if ObsWidget._opacity_timer:
                    ObsWidget._opacity_timer.stop()
                    ObsWidget._opacity_timer = None
                if ObsWidget._time_timer:
                    ObsWidget._time_timer.stop()
                    ObsWidget._time_timer = None

        event.accept()
