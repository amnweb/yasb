import logging
import threading
import time
from typing import Callable

import pywintypes
from win32con import (
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
from settings import CLI_VERSION

CLI_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_cli"
LOG_SERVER_PIPE_NAME = r"\\.\pipe\yasb_pipe_log"

logger = logging.getLogger("cli_server")


class PipeLogHandler(logging.Handler):
    """Custom logging handler to write log messages to a pipe"""

    def __init__(self, pipe_handle: int):
        super().__init__()
        self.pipe_handle = pipe_handle

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record) + "\n"
            WriteFile(self.pipe_handle, msg.encode("utf-8"))
        except OSError as e:
            logger.debug(f"PipeLogHandler emit failed: {e}")


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
            try:
                # Create a dedicated pipe for logging
                pipe = CreateNamedPipe(
                    LOG_SERVER_PIPE_NAME,
                    PIPE_ACCESS_DUPLEX,
                    PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
                    1,
                    65536,
                    65536,
                    0,
                    None,
                )

                # Wait for a client to connect
                ConnectNamedPipe(pipe)

                logger.debug("Log pipe server client connected")

                # Set up logging handler
                root_logger = logging.getLogger()
                handler = PipeLogHandler(pipe)
                formatter = ColoredFormatter(CLI_LOG_FORMAT, datefmt=CLI_LOG_DATETIME)
                handler.setFormatter(formatter)
                root_logger.addHandler(handler)
                while True:
                    # Ping the client to keep the connection alive
                    WriteFile(pipe, b"PING")
                    response = ReadFile(pipe, 64 * 1024)
                    if bool(response) and response.decode("utf-8").strip() != "PONG":
                        handler.close()
                        root_logger.removeHandler(handler)
                        logger.debug("Log pipe server client disconnected")
                        break
                    time.sleep(1)
                DisconnectNamedPipe(pipe)
                CloseHandle(pipe)
            except Exception as e:
                logger.error(f"Log pipe server error: {e}")
                time.sleep(0.1)


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
            pipe = CreateNamedPipe(
                CLI_SERVER_PIPE_NAME,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
                1,
                65536,
                65536,
                0,
                None,
            )

            try:
                ConnectNamedPipe(pipe)
                self._handle_client_connection(pipe)
            except Exception as e:
                if not self.stop_event.is_set():  # Only log errors if not intentionally stopping
                    logger.error(f"CLI server encountered an error: {e}")
            finally:
                try:
                    DisconnectNamedPipe(pipe)
                    CloseHandle(pipe)
                except Exception:
                    pass

            # Small delay to avoid tight loop if there are recurring errors
            if not self.stop_event.is_set():
                time.sleep(0.1)

    def _handle_client_connection(self, pipe: int):
        """Handle a client connection and process commands"""
        try:
            data = ReadFile(pipe, 64 * 1024)
            command = data.decode("utf-8").strip().lower()

            logger.info(f"CLI server received command: {command}")

            if command == "stop" or command == "reload":
                WriteFile(pipe, b"ACK")

                # Ensure we restart the pipe server if it's a reload command
                if command == "reload":
                    restart_thread = threading.Thread(target=self._restart_pipe_server)
                    restart_thread.daemon = True
                    restart_thread.start()

                # Execute command
                self.cli_command(command)
            else:
                WriteFile(pipe, b"CLI Unknown Command")

        except pywintypes.error as e:
            if e.args[0] == 109:  # ERROR_BROKEN_PIPE
                logger.info("CLI client disconnected")
            else:
                logger.error(f"CLI error handling client: {e}")

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