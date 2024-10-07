import logging
import threading
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.obs import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget, QGraphicsOpacityEffect
from PyQt6.QtGui import QCursor
from PyQt6.QtCore import Qt, QTimer, QMetaObject, Q_ARG
from obswebsocket import obsws, requests, events
from settings import DEBUG

# Set OBS WebSocket logger to WARNING
obs_logger = logging.getLogger('obswebsocket')

if DEBUG:
    obs_logger.setLevel(logging.INFO)
else:
    obs_logger.setLevel(logging.WARNING)
    
class ObsWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
            self,
            icons: dict[str, str],
            connection: dict[str, str],
            hide_when_not_recording: bool,
            blinking_icon: bool,
            container_padding: dict
    ):
        super().__init__(class_name="obs-widget")
        self._icons = icons
        self._connection = connection
        self._hide_when_not_recording = hide_when_not_recording
        self._blinking_icon = blinking_icon
        self._padding = container_padding
        self.is_recording = False
        
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
        
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        
        self.record_button = QLabel()
        self.record_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.record_button.setText(self._icons["stopped"])
        self.record_button.setProperty("class", "stopped")

        self._widget_container_layout.addWidget(self.record_button)
        
        self.widget_layout.addWidget(self._widget_container)
        self.hide_widget()
        # Connect button click to slot
        self.record_button.mousePressEvent = self.on_record_button_click
        self.start_connection()

        # Initialize timer for blinking
        self.blink_timer = QTimer()
        if self._blinking_icon:
            self.blink_timer.timeout.connect(self.blink_record_button)
        self.blink_state = False
        
        self.opacity_effect = QGraphicsOpacityEffect()
        self.record_button.setGraphicsEffect(self.opacity_effect)
        
        
    def obs_connect(self):
        self.ws = obsws(self._connection['host'], self._connection['port'], self._connection['password'], authreconnect=2)
        try:
            self.ws.connect()
            if DEBUG:
                logging.info("Connected to OBS WebSocket")
            self.ws.register(self.on_event)
            self.update_button_state()
             
        except Exception:
            if DEBUG:
                logging.error(f"Failed to connect to OBS WebSocket")
            self.hide_widget()  
        
        
    def update_button_state(self):
        try:
            response = self.ws.call(requests.GetRecordStatus())
            if 'outputState' in response.datain:
                self.update_button(response.datain['outputState'])
            else:
                self.update_button(False)
        except Exception as e:
            logging.error("Error while updating OBS button state")


    def update_button(self, state):
        if state in {"OBS_WEBSOCKET_OUTPUT_STARTED", "OBS_WEBSOCKET_OUTPUT_RESUMED"}:
            self.is_recording = True
            self.record_button.setText(self._icons["recording"])
            self.record_button.setProperty("class", "recording")
            self.show_widget()
            QMetaObject.invokeMethod(self.blink_timer, "start", Q_ARG(int, 250)) 
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
        
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)
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

    def on_event(self, event):
        if isinstance(event, events.RecordStateChanged):
            event_data = event.datain
            if 'outputState' in event_data:
                self.update_button(event_data['outputState'])
            else:
                self.update_button(False)
       
    def closeEvent(self, event):
        try:
            self.ws.disconnect()
            self.hide_widget()
        except Exception:
            logging.error("Error while disconnecting from OBS WebSocket")
        event.accept()


    def stop_recording(self):
        try:
            response = self.ws.call(requests.StopRecord())
            self.update_button_state()
        except Exception:
            logging.error("Error while stopping recording")

    def start_connection(self):
        threading.Thread(target=self.obs_connect).start()
 
    def on_record_button_click(self, event):
        if self.is_recording:
            self.stop_recording()

    def show_widget(self):
        self.show()

    def hide_widget(self):
        if self._hide_when_not_recording:
            self.hide()