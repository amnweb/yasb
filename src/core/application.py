import contextlib
import logging
import signal
import socket
import traceback
from collections.abc import Generator
from types import FrameType

from PyQt6 import sip
from PyQt6.QtCore import QEventLoop, QSocketNotifier
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlEngine
from watchdog.observers.api import BaseObserver

from core.bar.manager import BarManager
from core.config import ConfigError, load_config
from core.log import enable_debug_logging
from core.qml_types import register_qml_types
from core.tray import SystemTrayManager
from core.utils.alert_dialog import close_alerts, show_alert
from core.utils.controller import exit_application
from core.utils.icons.image_provider import ICON_PROVIDER, IconImageProvider
from core.utils.update_service import get_update_service, start_update_checker
from core.utils.win32.composition import shutdown_composition
from core.watcher import create_observer
from core.widgets.services.media.art import MEDIA_ART_PROVIDER, MediaArtProvider
from core.widgets.services.systray.systray import SYSTRAY_ICON_PROVIDER, SystrayIconProvider
from settings import QML_IMPORT_PATH


class YASBApplication(QGuiApplication):
    """Owns the QML engine, the bars, the tray and the file watcher, and runs them until YASB exits."""

    def __init__(self, args: list[str]):
        super().__init__(args)
        # Alerts and popups are windows too, and closing the last one must not end YASB
        self.setQuitOnLastWindowClosed(False)
        register_qml_types()
        self._engine = QQmlEngine()
        self._engine.addImportPath(QML_IMPORT_PATH)
        self._engine.addImageProvider(ICON_PROVIDER, IconImageProvider())
        self._engine.addImageProvider(MEDIA_ART_PROVIDER, MediaArtProvider())
        self._engine.addImageProvider(SYSTRAY_ICON_PROVIDER, SystrayIconProvider())
        self._bars: BarManager | None = None
        self._tray: SystemTrayManager | None = None
        self._observer: BaseObserver | None = None
        self.aboutToQuit.connect(self._stop_watching)

    def run(self) -> int:
        with _exit_on_ctrl_c():
            try:
                return self.exec() if self._start() else 1
            finally:
                self._tray = None
                self._bars = None
                # Qt's threads still call or delete Python objects while the engine goes, which hangs for good once
                # Python itself is shutting down. The bars are closed by now, when the app quit.
                sip.delete(self._engine)
                shutdown_composition()

    def _start(self) -> bool:
        try:
            config = load_config()
            if config.debug:
                enable_debug_logging()
                logging.info("Debug mode enabled.")
            self._bars = BarManager(config, self._engine)
            self._bars.initialize_bars()
            if config.watch:
                self._observer = create_observer(self._bars)
                self._observer.start()
            if config.show_systray:
                self._tray = SystemTrayManager(self._bars)
                self._tray.show()
            if config.update_check:
                _start_update_checker()
        except ConfigError as e:
            _report_startup_error("YASB could not start", str(e), e.details)
            return False
        except Exception as e:
            _report_startup_error("YASB stopped while starting", str(e) or type(e).__name__, traceback.format_exc())
            return False
        return True

    def _stop_watching(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()


@contextlib.contextmanager
def _exit_on_ctrl_c() -> Generator[None]:
    def handle_ctrl_c(_signum: int, _frame: FrameType | None) -> None:
        exit_application("Exiting Application from Ctrl+C...")

    previous = signal.signal(signal.SIGINT, handle_ctrl_c)
    # Python runs a signal handler only once Python code runs again, and an idle exec() runs none, so the
    # signal also writes to a socket that wakes Qt
    receiver, sender = socket.socketpair()
    sender.setblocking(False)
    notifier = QSocketNotifier(sip.voidptr(receiver.fileno()), QSocketNotifier.Type.Read)
    notifier.activated.connect(lambda *_: receiver.recv(64))
    signal.set_wakeup_fd(sender.fileno())
    try:
        yield
    finally:
        signal.set_wakeup_fd(-1)
        signal.signal(signal.SIGINT, previous)
        notifier.setEnabled(False)
        receiver.close()
        sender.close()


def _report_startup_error(title: str, message: str, details: str) -> None:
    logging.error("%s: %s\n%s", title, message, details)
    closed = QEventLoop()
    show_alert(title, message, details, closed.quit)
    closed.exec()
    close_alerts()


def _start_update_checker() -> None:
    try:
        if get_update_service().is_update_supported():
            start_update_checker()
    except Exception as e:
        logging.error("Failed to start auto update service: %s", e)
