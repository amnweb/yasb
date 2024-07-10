import logging
import time
import json
import uuid
import win32pipe
import win32file
import pywintypes
from PyQt6.QtCore import QThread
from core.event_enums import KomorebiEvent
from core.event_service import EventService
from core.utils.komorebi.client import KomorebiClient

KOMOREBI_PIPE_BUFF_SIZE = 64 * 1024
KOMOREBI_PIPE_NAME = "yasb"

class KomorebiEventListener(QThread):

    def __init__(
            self,
            pipe_name: str = KOMOREBI_PIPE_NAME,
            buffer_size: int = KOMOREBI_PIPE_BUFF_SIZE
    ):
        super().__init__()
        self._komorebic = KomorebiClient()
        self._app_running = True
        self.pipe_name = f"{pipe_name}-{uuid.uuid1()}"
        self.buffer_size = buffer_size
        self.event_service = EventService()
        self.pipe = None

    def __str__(self):
        return "Komorebi Event Listener"

    def _create_pipe(self) -> None:
        open_mode = win32pipe.PIPE_ACCESS_DUPLEX
        pipe_mode = win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT
        max_instances = 1
        buffer_size_in = self.buffer_size
        buffer_size_out = self.buffer_size
        default_timeout_ms = 0
        security_attributes = None
        self.pipe = win32pipe.CreateNamedPipe(
            f"\\\\.\\pipe\\{self.pipe_name}",
            open_mode,
            pipe_mode,
            max_instances,
            buffer_size_in,
            buffer_size_out,
            default_timeout_ms,
            security_attributes
        )
        logging.info(f"Created named pipe {self.pipe_name}")

    def run(self):
        while self._app_running:
            try:
                self._create_pipe()
                self._wait_until_komorebi_online()

                while self._app_running:
                    try:
                        buffer, bytes_to_read, result = win32pipe.PeekNamedPipe(self.pipe, 1)
                        if not bytes_to_read:
                            time.sleep(0.05)
                            continue

                        result, data = win32file.ReadFile(self.pipe, bytes_to_read, None)

                        if not data.strip():
                            continue

                        try:
                            event_message = json.loads(data.decode("utf-8"))
                            event = event_message['event']
                            state = event_message['state']

                            if event and state:
                                self._emit_event(event, state)
                        except (KeyError, ValueError):
                            logging.exception(f"Failed to parse komorebi state. Received data: {data}")
                    except pywintypes.error as e:
                        if e.winerror == 109:  # ERROR_BROKEN_PIPE
                            logging.warning(f"Pipe has been ended: {e}")
                            break
                        else:
                            logging.exception(f"Unexpected error occurred: {e}")
            except (BaseException, Exception):
                logging.exception(f"Komorebi has disconnected from the named pipe {self.pipe_name}")
            finally:
                if self.pipe:
                    win32file.CloseHandle(self.pipe)
                self.event_service.emit_event(KomorebiEvent.KomorebiDisconnect)
                logging.info("Attempting to reconnect...")
                time.sleep(5)

    def stop(self):
        self._app_running = False

    def _emit_event(self, event: dict, state: dict) -> None:
        self.event_service.emit_event(KomorebiEvent.KomorebiUpdate, event, state)

        if event['type'] in KomorebiEvent:
            self.event_service.emit_event(KomorebiEvent[event['type']], event, state)

    def _wait_until_komorebi_online(self):
        logging.info(f"Waiting for Komorebi to subscribe to named pipe {self.pipe_name}")
        stderr, proc = self._komorebic.wait_until_subscribed_to_pipe(self.pipe_name)
       
        if stderr:
            #logging.warning(f"Komorebi failed to subscribe named pipe. Waiting for subscription: {stderr.decode('utf-8')}")
             logging.warning(f"Komorebi failed to subscribe named pipe. Waiting for subscription...")   

        while self._app_running and proc.returncode != 0: 
            time.sleep(10)
            stderr, proc = self._komorebic.wait_until_subscribed_to_pipe(self.pipe_name)

        win32pipe.ConnectNamedPipe(self.pipe, None)
        logging.info(f"Komorebi connected to named pipe: {self.pipe_name}")
        state = self._komorebic.query_state()

        while self._app_running and state is None:
            logging.error(
                "Failed to retrieve komorebi state before starting event listener: None returned. "
                "Retrying in 1 second... Is komorebi online and its binaries added to $PATH?"
            )
            time.sleep(1)
            state = self._komorebic.query_state()

        self.event_service.emit_event(KomorebiEvent.KomorebiConnect, state)
