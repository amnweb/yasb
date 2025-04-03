import logging
import threading
import win32pipe, win32file, pywintypes
import settings

class CliPipeHandler:
    def __init__(self, cli_command):
        self.cli_command = cli_command
        self.pipe_name = r'\\.\pipe\yasb_pipe_cli'
        self.server_thread = None
        self.stop_event = threading.Event()

    def handle_client_connection(self, pipe):
        try:
            while True:
                data = win32file.ReadFile(pipe, 64*1024)
                command = data[1].decode('utf-8').strip().lower()
                if settings.DEBUG:
                    logging.debug(f"YASB received command {command}")
                if command in ('stop', 'reload'):
                    win32file.WriteFile(pipe, b'ACK')
                    self.cli_command(command)
                    self.stop_cli_pipe_server()
                else:
                    win32file.WriteFile(pipe, b'YASB Unknown Command')
        except pywintypes.error as e:
            if e.args[0] == 109:  # ERROR_BROKEN_PIPE
                if settings.DEBUG:
                    logging.debug("YASB CLI Pipe client disconnected")
            else:
                logging.error(f"YASB CLI error handling client: {e}")

    def start_cli_pipe_server(self):
        """
        Start the Named Pipe server to listen for incoming commands.
        """
        def run_server():
            if settings.DEBUG:
                logging.debug(f"YASB CLI Pipe server started")
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
                    client_thread.start()
                except Exception as e:
                    logging.error(f"Pipe server encountered an error: {e}")
                    win32pipe.DisconnectNamedPipe(pipe)

        self.stop_event.clear()
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.start()

    def stop_cli_pipe_server(self):
        """
        Stop the Named Pipe server.
        """
        self.stop_event.set()
        if self.server_thread:
            self.server_thread.join()
            if settings.DEBUG:
                logging.debug("YASB CLI Pipe server stopped")