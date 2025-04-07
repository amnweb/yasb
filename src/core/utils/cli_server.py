import logging
import threading
import time
import win32pipe, win32file, pywintypes
import settings

class CliPipeHandler:
    """
    Handles named pipe communication for CLI commands.
    Creates a server that listens for commands and executes them via the provided callback.
    """
    
    def __init__(self, cli_command):
        """
        Initialize the pipe handler.
        
        Args:
            cli_command: Callback function to execute received commands
        """
        self.cli_command = cli_command
        self.pipe_name = r'\\.\pipe\yasb_pipe_cli'
        self.server_thread = None
        self.stop_event = threading.Event()

    def start_cli_pipe_server(self):
        """
        Start the Named Pipe server to listen for incoming commands.
        """
        self.stop_event.clear()
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        
    def stop_cli_pipe_server(self):
        """
        Stop the Named Pipe server cleanly without blocking.
        """
        try:
            self.stop_event.set()
            if settings.DEBUG:
                logging.debug("CLI server stopped")
        except Exception as e:
            logging.error(f"Error stopping CLI server: {e}")

    def _run_server(self):
        """Internal method to run the server loop"""
        if settings.DEBUG:
            logging.info(f"CLI server started v{settings.CLI_VERSION}")
        while not self.stop_event.is_set():
            pipe = win32pipe.CreateNamedPipe(
                self.pipe_name,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                1, 65536, 65536,
                0,
                None
            )
            try:
                win32pipe.ConnectNamedPipe(pipe, None)
                client_thread = threading.Thread(target=self.handle_client_connection, args=(pipe,))
                client_thread.daemon = True  # Make client threads daemon
                client_thread.start()
            except Exception as e:
                if not self.stop_event.is_set():  # Only log errors if not intentionally stopping
                    logging.error(f"CLI server encountered an error: {e}")
                try:
                    win32pipe.DisconnectNamedPipe(pipe)
                    win32file.CloseHandle(pipe)
                except:
                    pass

    def handle_client_connection(self, pipe):
        """Handle a client connection and process commands"""
        try:
            while True:
                data = win32file.ReadFile(pipe, 64*1024)
                command = data[1].decode('utf-8').strip().lower()
                if settings.DEBUG:
                    logging.info(f"CLI server received command {command}")

                if command == 'stop' or command == 'reload':
                    win32file.WriteFile(pipe, b'ACK')
                    win32file.CloseHandle(pipe)
                    
                    # Ensure we restart the pipe server if it's a reload command before executing command
                    if command == 'reload':
                        restart_thread = threading.Thread(target=self._restart_pipe_server)
                        restart_thread.daemon = True
                        restart_thread.start()
                        
                    # Execute command after ensuring pipe server will restart
                    self.cli_command(command)
                    break
                else:
                    win32file.WriteFile(pipe, b'CLI Unknown Command')
                    
        except pywintypes.error as e:
            if e.args[0] == 109:  # ERROR_BROKEN_PIPE
                if settings.DEBUG:
                    logging.info("CLI client disconnected")
            else:
                logging.error(f"CLI error handling client: {e}")

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
            
            # Start a new server
            self.stop_event.clear()
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
        except Exception as e:
            logging.error(f"Failed to restart cli server: {e}")