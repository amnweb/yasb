import socket
import logging
import threading

class TCPHandler:
    def __init__(self, stop_or_reload_callback):
        self.stop_or_reload_callback = stop_or_reload_callback

    def handle_client_connection(self, conn, addr):
        with conn:
            try:
                command = conn.recv(1024).decode('utf-8').strip()
                logging.info(f"YASB received command: {command}")
                if command.lower() == 'stop':
                    conn.sendall(b'ACK')
                    self.stop_or_reload_callback()
                elif command.lower() == 'reload':
                    conn.sendall(b'ACK')
                    self.stop_or_reload_callback(reload=True)
                else:
                    conn.sendall(b'YASB Unknown Command')
            except Exception as e:
                logging.error(f"Error handling client {addr}: {e}")

    def start_socket_server(self, host='localhost', port=65432):
        """
        Start the TCP server to listen for incoming commands.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            try:
                server.bind((host, port))
                server.listen()
                logging.info(f"YASB socket server started on {host}:{port}")
                while True:
                    conn, addr = server.accept()
                    client_thread = threading.Thread(target=self.handle_client_connection, args=(conn, addr))
                    client_thread.start()
            except Exception as e:
                logging.error(f"Socket server encountered an error: {e}")