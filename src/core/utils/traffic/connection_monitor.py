import logging
import socket

import psutil
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal


class ConnectionTestWorker(QThread):
    """Worker thread for testing internet connectivity"""

    result_ready = pyqtSignal(bool)

    def __init__(self, interface=None):
        super().__init__()
        self.interface = interface
        self._running = True

    def run(self):
        """Test connectivity in background thread"""
        if not self._running:
            return

        is_connected = self._test_connection()
        if self._running:
            self.result_ready.emit(is_connected)

    def stop(self):
        """Stop the worker thread"""
        self._running = False
        self.quit()
        self.wait(1000)

    def _test_connection(self):
        """Test connectivity using multiple fallback servers"""
        test_servers = [
            ("8.8.8.8", 53),  # Google DNS
            ("1.1.1.1", 53),  # Cloudflare DNS (standard)
            # ("208.67.222.222", 53), # OpenDNS
        ]

        for server, port in test_servers:
            if not self._running:
                break

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)

                if self.interface and self.interface.lower() != "auto":
                    interface_ip = self._get_interface_ip()
                    if not interface_ip:
                        continue
                    sock.bind((interface_ip, 0))

                sock.connect((server, port))
                sock.close()
                return True

            except:
                continue

        return False

    def _get_interface_ip(self):
        """Get the IP address of the specified network interface"""
        try:
            net_if_addrs = psutil.net_if_addrs()
            if self.interface in net_if_addrs:
                for addr in net_if_addrs[self.interface]:
                    if addr.family == socket.AF_INET:
                        return addr.address
            return None

        except Exception as e:
            logging.debug(f"Error getting interface IP: {e}")
            return None


class InternetChecker(QObject):
    """Monitor internet connectivity and emit signals on changes"""

    connection_changed = pyqtSignal(bool)

    def __init__(self, parent=None, check_interval=10000, interface=None):
        super().__init__(parent)
        self.interface = interface
        self.last_status = None
        self.worker = None
        self._is_checking = False

        # Set up timer for regular checks
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_connection)
        self.timer.start(check_interval)

        # Do initial check after short delay
        QTimer.singleShot(1000, self.check_connection)

    def stop(self):
        """Stop the connection monitoring"""
        if hasattr(self, "timer") and self.timer:
            self.timer.stop()
            self.timer = None

        if self.worker:
            self.worker.stop()
            self.worker = None

    def __del__(self):
        """Ensure timer is stopped on deletion"""
        self.stop()

    def check_connection(self):
        """Check internet connectivity using background thread"""
        # Skip if already checking
        if self._is_checking:
            return

        self._is_checking = True

        # Clean up previous worker if it exists
        if self.worker:
            self.worker.stop()

        # Create new worker thread
        self.worker = ConnectionTestWorker(self.interface)
        self.worker.result_ready.connect(self._on_connection_result)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_connection_result(self, is_connected):
        """Handle connection test result"""
        # Emit signal on first check or when status changes
        if self.last_status is None or is_connected != self.last_status:
            self.last_status = is_connected
            self.connection_changed.emit(is_connected)

    def _on_worker_finished(self):
        """Clean up when worker thread finishes"""
        self._is_checking = False
        if self.worker:
            self.worker.deleteLater()
            self.worker = None


class NetworkUtils:
    """Utility class for network operations"""

    @staticmethod
    def get_available_interfaces():
        try:
            return list(psutil.net_if_addrs().keys())
        except:
            return []

    @staticmethod
    def is_interface_active(interface_name):
        try:
            stats = psutil.net_if_stats()
            return interface_name in stats and stats[interface_name].isup
        except:
            return False
