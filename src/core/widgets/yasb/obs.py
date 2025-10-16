import logging

from obswebsocket import events, obsws, requests
from PyQt6.QtCore import Q_ARG, QMetaObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel

from core.utils.utilities import refresh_widget_style
from core.validation.widgets.yasb.obs import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG

# Set OBS WebSocket logger to WARNING
obs_logger = logging.getLogger("obswebsocket")

if DEBUG:
    obs_logger.setLevel(logging.INFO)
else:
    obs_logger.setLevel(logging.ERROR)


class ObsWorker(QThread):
    connection_signal = pyqtSignal(bool)
    state_signal = pyqtSignal(dict)

    def __init__(self, connection_params, parent=None):
        super().__init__(parent)
        self._connection = connection_params
        self.running = True
        self.ws = None

    def run(self):
        while self.running:
            try:
                self.ws = obsws(
                    self._connection["host"], self._connection["port"], self._connection["password"], authreconnect=2
                )
                self.ws.connect()
                self.connection_signal.emit(True)
                self.ws.register(self.on_event)
                # Keep thread alive but not busy
                while self.running:
                    self.msleep(100)
            except Exception as e:
                if DEBUG:
                    logging.error(f"OBS connection error: {e}")
                self.connection_signal.emit(False)
                self.msleep(1000)  # Retry delay

    def stop(self):
        self.running = False
        if self.ws:
            try:
                self.ws.disconnect()
            except:
                pass
        self.wait()

    def on_event(self, event):
        if isinstance(event, events.RecordStateChanged):
            self.state_signal.emit(event.datain)


class ObsWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        icons: dict[str, str],
        connection: dict[str, str],
        hide_when_not_recording: bool,
        blinking_icon: bool,
        container_padding: dict,
    ):
        super().__init__(class_name="obs-widget")
        self._icons = icons
        self._connection = connection
        self._hide_when_not_recording = hide_when_not_recording
        self._blinking_icon = blinking_icon
        self._padding = container_padding
        self.is_recording = False

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )

        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")

        self.record_button = QLabel()
        self.record_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.record_button.setText(self._icons["stopped"])
        self.record_button.setProperty("class", "stopped")

        self.opacity_effect = QGraphicsOpacityEffect()
        self.record_button.setGraphicsEffect(self.opacity_effect)

        self._widget_container_layout.addWidget(self.record_button)

        self.widget_layout.addWidget(self._widget_container)
        self.hide_widget()
        # Connect button click to slot
        self.record_button.mousePressEvent = self.on_record_button_click
        self.worker = None
        self.start_connection()

        # Initialize timer for blinking
        self.blink_timer = QTimer()
        if self._blinking_icon:
            self.blink_timer.timeout.connect(self.blink_record_button)
        self.blink_state = False

    def update_button_state(self):
        try:
            response = self.ws.call(requests.GetRecordStatus())
            if "outputState" in response.datain:
                self.update_button(response.datain["outputState"])
            else:
                self.update_button(False)
        except Exception:
            if DEBUG:
                logging.error("Error while updating OBS button state")

    def update_button(self, state):
        if state in {"OBS_WEBSOCKET_OUTPUT_STARTED", "OBS_WEBSOCKET_OUTPUT_RESUMED"}:
            self.is_recording = True
            self.record_button.setText(self._icons["recording"])
            self.record_button.setProperty("class", "recording")
            self.show_widget()
            QMetaObject.invokeMethod(self.blink_timer, "start", Q_ARG(int, 200))
        elif state == "OBS_WEBSOCKET_OUTPUT_PAUSED":
            self.is_recording = False
            self.record_button.setText(self._icons["paused"])
            self.record_button.setProperty("class", "paused")
            self.show_widget()
            QMetaObject.invokeMethod(self.blink_timer, "stop")
        else:
            self.is_recording = False
            self.record_button.setText(self._icons["stopped"])
            self.record_button.setProperty("class", "stopped")
            self.hide_widget()
            QMetaObject.invokeMethod(self.blink_timer, "stop")

        refresh_widget_style(self.record_button)
        self.record_button.update()
        self.record_button.repaint()

    def blink_record_button(self):
        if self.is_recording:
            self.blink_state = not self.blink_state
            if self.blink_state:
                self.opacity_effect.setOpacity(1.0)
            else:
                self.opacity_effect.setOpacity(0.4)
            self.record_button.update()
            self.record_button.repaint()
        else:
            self.opacity_effect.setOpacity(1.0)

    def stop_recording(self):
        if self.worker and self.worker.ws:
            try:
                self.worker.ws.call(requests.StopRecord())
                self.update_button_state()
            except Exception:
                logging.error("Error while stopping recording")

    def start_connection(self):
        if self.worker:
            self.worker.stop()
        self.worker = ObsWorker(self._connection)
        self.worker.connection_signal.connect(self.handle_connection)
        self.worker.state_signal.connect(self.handle_state_change)
        self.worker.start()

    def handle_connection(self, connected):
        if connected:
            if DEBUG:
                logging.info("Connected to OBS WebSocket")
            self.update_button_state()
        else:
            self.hide_widget()

    def handle_state_change(self, event_data):
        if "outputState" in event_data:
            self.update_button(event_data["outputState"])
        else:
            self.update_button(False)

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop()
        event.accept()

    def on_record_button_click(self, event):
        if self.is_recording:
            self.stop_recording()

    def show_widget(self):
        self.show()

    def hide_widget(self):
        if self._hide_when_not_recording:
            self.hide()
