import logging
from typing import ClassVar

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.utils.widgets.server_monitor.worker import ServerCheckWorker


class ServerCheckService(QObject):
    """Server-check runner."""

    status_updated = pyqtSignal(int, list)
    refresh_started = pyqtSignal()

    _instances: ClassVar[dict[tuple, "ServerCheckService"]] = {}

    @classmethod
    def get_instance(
        cls,
        servers: list[str],
        ssl_verify: bool,
        ssl_check: bool,
        timeout: int,
        update_interval_s: int,
    ) -> "ServerCheckService":
        key = (tuple(servers), ssl_verify, ssl_check, timeout, int(update_interval_s))
        inst = cls._instances.get(key)
        if inst is None:
            inst = cls(
                servers=list(servers),
                ssl_verify=ssl_verify,
                ssl_check=ssl_check,
                timeout=timeout,
                update_interval_s=int(update_interval_s),
                _key=key,
            )
            cls._instances[key] = inst
        inst._refcount += 1
        return inst

    def __init__(
        self,
        servers: list[str],
        ssl_verify: bool,
        ssl_check: bool,
        timeout: int,
        update_interval_s: int,
        _key: tuple,
    ):
        super().__init__()
        self._key = _key
        self._refcount = 0
        self._run_id = 0

        self._worker = ServerCheckWorker()
        self._worker.set_servers(servers, ssl_verify, ssl_check, timeout)
        self._worker.status_updated.connect(self._on_worker_status_updated)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._start_if_idle)
        self._timer.start(max(int(update_interval_s), 1) * 1000)

        self._start_if_idle()

    def release(self) -> None:
        self._refcount -= 1
        if self._refcount > 0:
            return
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            self._worker.stop()
        except Exception:
            pass
        ServerCheckService._instances.pop(self._key, None)
        try:
            self.deleteLater()
        except Exception:
            pass

    def is_running(self) -> bool:
        try:
            return self._worker.isRunning()
        except RuntimeError:
            return False

    def start_now(self) -> None:
        self._start_if_idle()

    def _start_if_idle(self) -> None:
        try:
            if not self._worker.isRunning():
                self._run_id += 1
                self.refresh_started.emit()
                self._worker.start()
                logging.info("ServerCheckWorker started...")
        except RuntimeError:
            return

    def _on_worker_status_updated(self, status_list: list) -> None:
        self.status_updated.emit(self._run_id, status_list)
