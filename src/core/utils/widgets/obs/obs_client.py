"""
OBS WebSocket Client for OBS WebSocket v5.x Protocol.
"""

import base64
import hashlib
import json
import os
import socket
import struct
import threading
import uuid

from PyQt6.QtCore import QThread, pyqtSignal


class ObsWebSocketClient:
    """WebSocket client for OBS."""

    EVENT_OUTPUTS = 1 << 6
    EVENT_UI = 1 << 10
    EVENT_SCENES = 1 << 2

    def __init__(self, host: str = "localhost", port: int = 4455, auth_key: str = "", event_subscriptions: int = 0):
        self.host = host
        self.port = port
        self.auth_key = auth_key
        self.event_subscriptions = event_subscriptions or self.EVENT_OUTPUTS

        self._socket: socket.socket | None = None
        self._connected = False
        self._identified = False
        self._running = False
        self._lock = threading.Lock()
        self._pending: dict[str, threading.Event] = {}
        self._responses: dict[str, dict] = {}
        self._recv_thread: threading.Thread | None = None
        self._event_callbacks: list = []
        self._connection_callbacks: list = []

    @property
    def connected(self) -> bool:
        return self._connected and self._identified

    def connect(self) -> bool:
        if self._connected:
            return True
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(2.0)
            self._socket.connect((self.host, self.port))

            if not self._ws_handshake():
                self._cleanup()
                return False

            self._connected = True
            self._running = True
            self._recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._recv_thread.start()

            # Wait for identification
            for _ in range(40):  # 2 seconds
                if self._identified or not self._running:
                    break
                threading.Event().wait(0.05)

            return self._identified
        except Exception:
            self._cleanup()
            return False

    def disconnect(self):
        self._running = False
        self._cleanup()

    def _cleanup(self):
        was_connected = self._connected
        self._connected = False
        self._identified = False

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        with self._lock:
            for event in self._pending.values():
                event.set()
            self._pending.clear()

        if was_connected:
            for cb in self._connection_callbacks:
                try:
                    cb(False)
                except Exception:
                    pass

    def register_event_callback(self, callback):
        if callback not in self._event_callbacks:
            self._event_callbacks.append(callback)

    def register_connection_callback(self, callback):
        if callback not in self._connection_callbacks:
            self._connection_callbacks.append(callback)

    def call(self, request_type: str, request_data: dict | None = None, timeout: float = 5.0) -> dict:
        """Send request and wait for response."""
        if not self.connected:
            raise RuntimeError("Not connected")

        request_id = str(uuid.uuid4())
        event = threading.Event()

        with self._lock:
            self._pending[request_id] = event

        msg = {"op": 6, "d": {"requestType": request_type, "requestId": request_id}}
        if request_data:
            msg["d"]["requestData"] = request_data

        try:
            self._ws_send(json.dumps(msg))
        except Exception as e:
            with self._lock:
                self._pending.pop(request_id, None)
            raise RuntimeError(f"Send failed: {e}") from e

        if not event.wait(timeout):
            with self._lock:
                self._pending.pop(request_id, None)
            raise RuntimeError(f"Timeout: {request_type}")

        with self._lock:
            self._pending.pop(request_id, None)
            response = self._responses.pop(request_id, {})

        status = response.get("requestStatus", {})
        if not status.get("result", False):
            raise RuntimeError(f"Request failed: {status.get('comment', 'Unknown')}")

        return response.get("responseData", {})

    def send(self, request_type: str, request_data: dict | None = None):
        """Fire-and-forget request."""
        if not self.connected:
            return
        msg = {"op": 6, "d": {"requestType": request_type, "requestId": str(uuid.uuid4())}}
        if request_data:
            msg["d"]["requestData"] = request_data
        try:
            self._ws_send(json.dumps(msg))
        except Exception:
            pass

    # WebSocket implementation
    def _ws_handshake(self) -> bool:
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        self._socket.sendall(request.encode())

        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self._socket.recv(1024)
            if not chunk:
                return False
            response += chunk

        return b"101" in response and b"Upgrade" in response

    def _ws_send(self, data: str):
        payload = data.encode()
        length = len(payload)
        header = bytearray([0x81])

        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack(">H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack(">Q", length))

        mask = os.urandom(4)
        header.extend(mask)

        masked = bytearray(payload)
        for i in range(length):
            masked[i] ^= mask[i % 4]

        self._socket.sendall(bytes(header) + bytes(masked))

    def _ws_recv(self) -> tuple[int, bytes] | None:
        try:
            header = self._recv_exact(2)
            if not header:
                return None

            opcode = header[0] & 0x0F
            masked = (header[1] & 0x80) != 0
            length = header[1] & 0x7F

            if length == 126:
                ext = self._recv_exact(2)
                if not ext:
                    return None
                length = struct.unpack(">H", ext)[0]
            elif length == 127:
                ext = self._recv_exact(8)
                if not ext:
                    return None
                length = struct.unpack(">Q", ext)[0]

            mask = self._recv_exact(4) if masked else None
            payload = self._recv_exact(length)
            if payload is None:
                return None

            if mask:
                payload = bytearray(payload)
                for i in range(len(payload)):
                    payload[i] ^= mask[i % 4]
                payload = bytes(payload)

            return (opcode, payload)
        except Exception:
            return None

    def _recv_exact(self, n: int) -> bytes | None:
        data = b""
        while len(data) < n:
            try:
                chunk = self._socket.recv(n - len(data))
                if not chunk:
                    return None
                data += chunk
            except Exception:
                return None
        return data

    def _receive_loop(self):
        while self._running and self._socket:
            try:
                self._socket.settimeout(0.5)
                result = self._ws_recv()
                if result is None:
                    continue

                opcode, payload = result
                if opcode == 0x1:  # Text
                    self._handle_message(payload.decode())
                elif opcode == 0x9:  # Ping
                    self._ws_send_pong(payload)
                elif opcode == 0x8:  # Close
                    break
            except socket.timeout:
                continue
            except Exception:
                break

        self._cleanup()

    def _ws_send_pong(self, payload: bytes):
        length = len(payload)
        header = bytearray([0x8A, 0x80 | length])
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytearray(payload)
        for i in range(length):
            masked[i] ^= mask[i % 4]
        try:
            self._socket.sendall(bytes(header) + bytes(masked))
        except Exception:
            pass

    def _handle_message(self, message: str):
        try:
            data = json.loads(message)
            op = data.get("op")
            d = data.get("d", {})

            if op == 0:  # Hello
                self._handle_hello(d)
            elif op == 2:  # Identified
                self._identified = True
                for cb in self._connection_callbacks:
                    try:
                        cb(True)
                    except Exception:
                        pass
            elif op == 5:  # Event
                event_type = d.get("eventType", "")
                event_data = d.get("eventData", {})
                for cb in self._event_callbacks:
                    try:
                        cb(event_type, event_data)
                    except Exception:
                        pass
            elif op == 7:  # Response
                req_id = d.get("requestId", "")
                with self._lock:
                    if req_id in self._pending:
                        self._responses[req_id] = d
                        self._pending[req_id].set()
        except Exception:
            pass

    def _obs_ws_auth(self, secret_key: str, salt: str, challenge: str) -> str:
        """
        Generate OBS WebSocket authentication string per protocol specification.
        """
        secret = base64.b64encode(hashlib.sha256((secret_key + salt).encode()).digest()).decode()
        return base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()

    def _handle_hello(self, payload: dict):
        auth = payload.get("authentication")
        msg = {"op": 1, "d": {"rpcVersion": 1, "eventSubscriptions": self.event_subscriptions}}

        if auth and self.auth_key:
            msg["d"]["authentication"] = self._obs_ws_auth(
                self.auth_key, auth.get("salt", ""), auth.get("challenge", "")
            )

        try:
            self._ws_send(json.dumps(msg))
        except Exception:
            pass


class ObsWorker(QThread):
    """Shared worker thread for OBS WebSocket connection."""

    connection_signal = pyqtSignal(bool)
    state_signal = pyqtSignal(dict)
    stream_signal = pyqtSignal(dict)
    virtual_cam_signal = pyqtSignal(bool)
    studio_mode_signal = pyqtSignal(bool)
    scene_signal = pyqtSignal(str)

    _instance: "ObsWorker | None" = None
    _users = 0
    _lock = threading.Lock()

    def __init__(self, connection: dict = None):
        super().__init__()
        self._connection = connection or {}
        self.running = True
        self.client: ObsWebSocketClient | None = None
        self._connected = False

    @classmethod
    def get_instance(cls, connection: dict = None) -> "ObsWorker":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(connection)
            cls._users += 1
            return cls._instance

    @classmethod
    def release_instance(cls):
        with cls._lock:
            cls._users = max(cls._users - 1, 0)
            if cls._users == 0 and cls._instance:
                cls._instance.stop()
                cls._instance = None

    def run(self):
        while self.running:
            try:
                if not self.client:
                    self.client = ObsWebSocketClient(
                        host=self._connection.get("host", "localhost"),
                        port=self._connection.get("port", 4455),
                        auth_key=self._connection.get("password", ""),
                        event_subscriptions=ObsWebSocketClient.EVENT_OUTPUTS
                        | ObsWebSocketClient.EVENT_UI
                        | ObsWebSocketClient.EVENT_SCENES,
                    )
                    self.client.register_event_callback(self._on_event)
                    self.client.register_connection_callback(self._on_connection)

                if self.client.connect():
                    self._set_connected(True)
                    while self.running and self.client.connected:
                        self.msleep(250)
                else:
                    self._set_connected(False)
                    self._cleanup_client()
                    self.msleep(5000)
            except Exception:
                self._set_connected(False)
                self._cleanup_client()
                self.msleep(5000)

    def stop(self):
        self.running = False
        self._cleanup_client()
        self._set_connected(False)
        self.wait()

    def _cleanup_client(self):
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self.client = None

    def _set_connected(self, connected: bool):
        if self._connected != connected:
            self._connected = connected
            self.connection_signal.emit(connected)

    def _on_connection(self, connected: bool):
        self._set_connected(connected)
        if not connected:
            self._cleanup_client()

    def _on_event(self, event_type: str, event_data: dict):
        if event_type == "RecordStateChanged":
            self.state_signal.emit(event_data)
        elif event_type == "StreamStateChanged":
            self.stream_signal.emit(event_data)
        elif event_type == "VirtualcamStateChanged":
            self.virtual_cam_signal.emit(event_data.get("outputActive", False))
        elif event_type == "StudioModeStateChanged":
            self.studio_mode_signal.emit(event_data.get("studioModeEnabled", False))
        elif event_type == "CurrentProgramSceneChanged":
            self.scene_signal.emit(event_data.get("sceneName", ""))
