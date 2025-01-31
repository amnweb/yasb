import logging
import threading
import win32pipe, win32file, pywintypes
from settings import DEBUG

class CliPipeHandler:
    def __init__(self, stop_or_reload_callback):
        self.stop_or_reload_callback = stop_or_reload_callback
        self.pipe_name = r'\\.\pipe\yasb_pipe_cli'
        self.server_thread = None
        self.stop_event = threading.Event()

    def handle_client_connection(self, pipe):
        try:
            while True:
                data = win32file.ReadFile(pipe, 64*1024)
                command = data[1].decode('utf-8').strip()
                if DEBUG:
                    logging.info(f"YASB received command {command}")
                if command.lower() == 'stop':
                    win32file.WriteFile(pipe, b'ACK')
                    self.stop_or_reload_callback()
                    self.stop_cli_pipe_server()
                elif command.lower() == 'reload':
                    win32file.WriteFile(pipe, b'ACK')
                    self.stop_or_reload_callback(reload=True)
                    self.stop_cli_pipe_server()
                else:
                    win32file.WriteFile(pipe, b'YASB Unknown Command')
        except pywintypes.error as e:
            if e.args[0] == 109:  # ERROR_BROKEN_PIPE
                if DEBUG:
                    logging.info("Pipe closed by client")
            else:
                logging.error(f"YASB CLI error handling client: {e}")

    def start_cli_pipe_server(self):
        """
        Start the Named Pipe server to listen for incoming commands.
        """
        def run_server():
            if DEBUG:
                logging.info(f"YASB CLI Pipe server started")
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
        if DEBUG:
            logging.info("YASB Named Pipe server stopped")