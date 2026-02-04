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
        self._tooltip = config.tooltip
        self._is_recording = False
        self._is_paused = False
        self._virtual_cam_active = False
        self._studio_mode_active = False
        self._opacity_low = False

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

        # Record time label
        self._time_label = QLabel()
        self._time_label.setProperty("class", "label record-time")
        self._widget_container_layout.addWidget(self._time_label)
        self._time_label.hide()

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

    def _init_worker(self):
        self.worker = ObsWorker.get_instance(self._connection)
        if not self.worker.isRunning():
            self.worker.start()

        self.worker.connection_signal.connect(self._on_connection)
        self.worker.state_signal.connect(self._on_state)
        self.worker.virtual_cam_signal.connect(self._on_virtual_cam)
        self.worker.studio_mode_signal.connect(self._on_studio_mode)

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

    def _update_record_ui(self, active: bool, paused: bool):
        self._is_recording = active and not paused
        self._is_paused = paused

        if paused:
            self._record_btn.setText(self._icons["paused"])
            self._record_btn.setProperty("class", "icon record paused")
            self._start_time_timer()
            self._stop_opacity_timer()
            if self._time_label and self._show_record_time:
                self._time_label.show()
        elif active:
            self._record_btn.setText(self._icons["recording"])
            self._record_btn.setProperty("class", "icon record recording")
            self._start_time_timer()
            if self._blinking_icon:
                self._start_opacity_timer()
            if self._time_label and self._show_record_time:
                self._time_label.show()
        else:
            self._record_btn.setText(self._icons["stopped"])
            self._record_btn.setProperty("class", "icon record stopped")
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
        timecode = data.get("outputTimecode", "")
        if timecode:
            self._time_label.setText(timecode.split(".")[0] if "." in timecode else timecode)

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
        if not any(s._is_recording and s._blinking_icon for s in ObsWidget._subscribers):
            if ObsWidget._opacity_timer:
                ObsWidget._opacity_timer.stop()

    def _start_time_timer(self):
        if self._show_record_time and ObsWidget._time_timer and not ObsWidget._time_timer.isActive():
            ObsWidget._time_timer.start()

    def _stop_timers(self):
        self._stop_opacity_timer()
        if not any((s._is_recording or s._is_paused) and s._show_record_time for s in ObsWidget._subscribers):
            if ObsWidget._time_timer:
                ObsWidget._time_timer.stop()

    @staticmethod
    def _on_opacity_tick():
        for s in ObsWidget._subscribers:
            if s._is_recording and s._blinking_icon:
                s._opacity_low = not s._opacity_low
                s._opacity_effect.setOpacity(0.6 if s._opacity_low else 1.0)

    @staticmethod
    def _on_time_tick():
        for s in ObsWidget._subscribers:
            if (s._is_recording or s._is_paused) and s._show_record_time:
                s._refresh_status()

    def closeEvent(self, event):
        if self in ObsWidget._subscribers:
            ObsWidget._subscribers.remove(self)

        if self.worker:
            try:
                self.worker.connection_signal.disconnect(self._on_connection)
                self.worker.state_signal.disconnect(self._on_state)
                self.worker.virtual_cam_signal.disconnect(self._on_virtual_cam)
                self.worker.studio_mode_signal.disconnect(self._on_studio_mode)
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
