import json
import logging
import threading
import time
from ctypes import GetLastError
from typing import Callable

from win32con import (
    FILE_FLAG_OVERLAPPED,
    PIPE_ACCESS_DUPLEX,
    PIPE_READMODE_MESSAGE,
    PIPE_TYPE_MESSAGE,
    PIPE_WAIT,
)

from core.log import CLI_LOG_DATETIME, CLI_LOG_FORMAT, ColoredFormatter
from core.utils.win32.bindings import (
    CloseHandle,
    ConnectNamedPipe,
    CreateNamedPipe,
    DisconnectNamedPipe,
    ReadFile,
    WriteFile,
)
from core.utils.win32.constants import INVALID_HANDLE_VALUE
from settings import CLI_VERSION

CLI_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_cli"
LOG_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_log"
BUFSIZE = 65536

logger = logging.getLogger("cli_server")


def write_message(handle: int, msg_dict: dict[str, str]):
    try:
        data = json.dumps(msg_dict).encode("utf-8")
    except Exception as e:
        print(f"JSON encode error: {e}")
        print(f"Data: {msg_dict}")
        return False
    success = WriteFile(handle, data)
    return success


def read_message(handle: int) -> dict[str, str] | None:
    success, data = ReadFile(handle, BUFSIZE)
    if not success or len(data) == 0:
        return None
    try:
        messages: list[str] = []
        # This is needed in case there are multiple json objects in one data block
        for line in data.split(b"\0"):
            if not line.strip():
                continue
            json_object = json.loads(line.decode().strip())
            if json_object.get("type") == "DATA":
                messages.append(json_object.get("data"))
            else:
                # If it's ping/pong, just return the object as is
                return json_object
        return {"type": "DATA", "data": "\n".join(messages)}
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Data: {data}")
        return None


class PipeLogHandler(logging.Handler):
    """Custom logging handler to write log messages to a pipe"""

    def __init__(self, pipe_handle: int):
        super().__init__()
        self.pipe_handle = pipe_handle

    def emit(self, record: logging.LogRecord):
        """Emit a log record to the pipe"""
        # NOTE: Do not use logging prints here as it will create an infinite loop
        try:
            fmt = self.format(record)
            msg = json.dumps({"type": "DATA", "data": fmt}).encode("utf-8") + b"\0"
            success = WriteFile(self.pipe_handle, msg)
            if not success:
                print(f"PipeLogHandler emit failed. Err: {GetLastError()}")
        except OSError as e:
            print(f"PipeLogHandler emit failed: {e}")


class LogPipeServer:
    """
    Dedicated server for handling logging connections.
    This runs in its own thread to avoid blocking the main command pipe.
    """

    def __init__(self):
        self.stop_event = threading.Event()
        self.log_pipe_handle: int | None = None
        self.server_thread = None

    def start(self):
        """Start the logging pipe server"""
        self.stop_event.clear()
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.name = "LogPipeServer"
        self.server_thread.start()
        logger.info("Log pipe server started")

    def stop(self):
        """Stop the logging pipe server"""
        self.stop_event.set()
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=0.1)
            self.stop_event.clear()
        logger.info("Log pipe server stopped")

    def _run_server(self):
        """Run the logging pipe server loop"""
        while not self.stop_event.is_set():
            # Create a new pipe
            handle = CreateNamedPipe(
                LOG_SERVER_PIPE_NAME,
                PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
                PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
                10,
                BUFSIZE,
                BUFSIZE,
                0,
                None,
            )

            # Check the handle
            if handle == INVALID_HANDLE_VALUE:
                logger.error(f"Log pipe server failed to create handle. Err: {GetLastError()}")
                time.sleep(1)
                continue

            # Wait for a client to connect
            if not ConnectNamedPipe(handle):
                logger.error(f"Log pipe server failed to connect. Err: {GetLastError()}")
                DisconnectNamedPipe(handle)
                CloseHandle(handle)
                time.sleep(0.1)
                continue

            logger.debug("Log pipe server client connected")

            root_logger = logging.getLogger()
            handler = PipeLogHandler(handle)
            formatter = ColoredFormatter(CLI_LOG_FORMAT, datefmt=CLI_LOG_DATETIME)
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)

            while True:
                msg = read_message(handle)
                if msg is None:
                    logger.info(f"Client disconnected or read error. Err: {GetLastError()}")
                    time.sleep(0.1)
                    break

                if msg and msg.get("type") == "PING":
                    if not write_message(handle, {"type": "PONG"}):
                        logger.error(f"Write pong failed. Err: {GetLastError()}")
                        time.sleep(0.1)
                        break
                    time.sleep(1)

            DisconnectNamedPipe(handle)
            CloseHandle(handle)
            root_logger.removeHandler(handler)
            logger.debug("Log pipe server client disconnected")


class CliPipeHandler:
    """
    Handles named pipe communication for CLI commands.
    Creates a server that listens for commands and executes them via the provided callback.
    """

    def __init__(self, cli_command: Callable[[str], None]):
        """
        Initialize the pipe handler.

        Args:
            cli_command: Callback function to execute received commands
        """
        self.cli_command = cli_command
        self.server_thread = None
        self.stop_event = threading.Event()
        self.log_server = LogPipeServer()

    def start_cli_pipe_server(self):
        """
        Start the Named Pipe server to listen for incoming commands.
        """
        self.stop_event.clear()
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.name = "CLIPipeServer"
        self.server_thread.start()
        self.log_server.start()

    def stop_cli_pipe_server(self):
        """
        Stop the Named Pipe server cleanly without blocking.
        """
        try:
            self.stop_event.set()
            self.log_server.stop()

            logger.debug("CLI server stopped")
        except Exception as e:
            logger.error(f"Error stopping CLI server: {e}")

    def _run_server(self):
        """Internal method to run the server loop"""
        logger.info(f"CLI server started v{CLI_VERSION}")

        while not self.stop_event.is_set():
            handle = CreateNamedPipe(
                CLI_SERVER_PIPE_NAME,
                PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
                PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
                10,
                BUFSIZE,
                BUFSIZE,
                0,
                None,
            )
            if handle == INVALID_HANDLE_VALUE:
                logger.error(f"CLI pipe server failed to create handle. Err: {GetLastError()}")
                time.sleep(1)
                continue

            # Wait for a client to connect
            if not ConnectNamedPipe(handle):
                logger.error("Cli handler server failed to connect")
                DisconnectNamedPipe(handle)
                CloseHandle(handle)
                time.sleep(0.1)
                continue

            self._handle_client_connection(handle)
            DisconnectNamedPipe(handle)
            CloseHandle(handle)

    def _handle_client_connection(self, pipe: int):
        """Handle a client connection and process commands"""
        success, data = ReadFile(pipe, 64 * 1024)
        if not success or len(data) == 0:
            logger.info(f"CLI client disconnected or read error. Err: {GetLastError()}")
            return None

        full_command = data.decode("utf-8").strip()
        # Get just the base command for comparison
        command = full_command.split()[0].lower() if full_command else ""

        logger.info(f"CLI server received command: {full_command}")

        if command in ["stop", "reload", "show-bar", "hide-bar", "toggle-bar", "toggle-widget"]:
            success = WriteFile(pipe, b"ACK")
            if not success:
                logger.error(f"Write ACK failed. Err: {GetLastError()}")
                return None

            # Ensure we restart the pipe server if it's a reload command
            if command == "reload":
                restart_thread = threading.Thread(target=self._restart_pipe_server)
                restart_thread.daemon = True
                restart_thread.start()

            # Execute command
            self.cli_command(full_command)
        else:
            WriteFile(pipe, b"CLI Unknown Command")

    def _restart_pipe_server(self):
        """Restart the pipe server after a brief delay to ensure continuity"""
        try:
            # Wait a moment for the reload to begin
            time.sleep(0.5)

            # Stop existing server if running
            if self.server_thread and self.server_thread.is_alive():
                old_thread = self.server_thread
                self.stop_event.set()
                old_thread.join(timeout=1.0)

            # Stop the log server as well
            self.log_server.stop()

            # Start a new server
            self.stop_event.clear()
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()

            # Start a new log server
            self.log_server.start()

        except Exception as e:
            logger.error(f"Failed to restart cli server: {e}")
