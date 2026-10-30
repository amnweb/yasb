import asyncio
import logging
import signal
import sys
import traceback
from sys import argv
from types import FrameType, TracebackType

import qasync  # pyright: ignore[reportMissingTypeStubs]
from PyQt6 import sip
from PyQt6.QtCore import QEventLoop
from PyQt6.QtQml import QQmlEngine

from core.application import YASBApplication
from core.bar.manager import BarManager
from core.config import ConfigError, load_config
from core.log import enable_debug_logging, init_logger
from core.qml_types import register_qml_types
from core.tray import SystemTrayManager
from core.utils.alert_dialog import close_alerts, show_alert
from core.utils.controller import start_cli_server
from core.utils.icons.image_provider import ICON_PROVIDER, IconImageProvider
from core.utils.single_instance import single_instance_lock
from core.utils.update_service import get_update_service, start_update_checker
from core.utils.win32.composition import shutdown_composition
from core.watcher import create_observer
from env import load_env, set_qt_quick_defaults
from settings import QML_IMPORT_PATH


def main():
    """Main entry point"""
    app = YASBApplication(argv)
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    engine.addImageProvider(ICON_PROVIDER, IconImageProvider())

    loop = qasync.QEventLoop(app)
    try:
        loop.run_until_complete(main_async(app, engine))  # pyright: ignore[reportUnknownMemberType]
    except Exception as e:
        logging.exception("YASB stopped while starting")
        closed = QEventLoop()
        show_alert("YASB stopped while starting", str(e) or type(e).__name__, traceback.format_exc(), closed.quit)
        closed.exec()
        close_alerts()
        sys.exit(1)
    finally:
        loop.close()
        # Qt's threads still call or delete Python objects while the engine goes, which hangs for good once
        # Python itself is shutting down. The bars are closed by now, when the app quit.
        sip.delete(engine)
        shutdown_composition()


async def main_async(app: YASBApplication, engine: QQmlEngine):
    """
    Async entry point
    Required for qasync to work properly
    """
    # Event to signal application shutdown
    app_close_event = asyncio.Event()

    # Assign the loop and close event to the app instance
    # This allows the controller to close the app gracefully from another thread
    app.loop = asyncio.get_running_loop()
    app.close_event = app_close_event

    # Prevent the app from exiting when closing the dialogs
    app.setQuitOnLastWindowClosed(False)

    # Connect the app's aboutToQuit signal to the close event
    app.aboutToQuit.connect(app_close_event.set)

    def handle_sigint(_signum: int, _frame: FrameType | None) -> None:
        logging.info("KeyboardInterrupt (Ctrl+C) detected. Initiating graceful shutdown...")
        app_close_event.set()

    try:
        signal.signal(signal.SIGINT, handle_sigint)
    except ValueError:
        pass

    # Initialize configuration early after the single instance check
    try:
        config = load_config()
    except ConfigError as e:
        logging.error("YASB could not start: %s\n%s", e, e.details)
        closed = asyncio.Event()
        show_alert("YASB could not start", str(e), e.details, closed.set)
        await closed.wait()
        app.quit()
        return

    if config.debug:
        enable_debug_logging()
        logging.info("Debug mode enabled.")

    # Initialise bars and background event listeners
    manager = BarManager(config, engine)

    try:
        manager.initialize_bars()
        # Initialise file watcher if needed
        observer = create_observer(manager) if config.watch else None
        if observer:
            observer.start()

        def stop_observer():
            if observer:
                observer.stop()
                observer.join()

        app.aboutToQuit.connect(stop_observer)

        # Build system tray icon
        if config.show_systray:
            tray_manager = SystemTrayManager(manager)
            tray_manager.show()

        # Initialize auto update service
        if config.update_check:
            try:
                update_service = get_update_service()
                if update_service.is_update_supported():
                    start_update_checker()
            except Exception as e:
                logging.error("Failed to start auto update service: %s", e)

        await app_close_event.wait()
    finally:
        # Cancel async tasks while loop is still running
        current = asyncio.current_task()
        tasks = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        app.quit()


if __name__ == "__main__":
    init_logger()
    load_env()
    set_qt_quick_defaults()

    # PyQt drops the callback that raised and YASB keeps running; exiting here would skip the shutdown
    def exception_hook(_exctype: type, value: BaseException, _traceback: TracebackType | None):
        logging.error("Unhandled exception", exc_info=value)

    sys.excepthook = exception_hook

    try:
        # Acquire the single instance lock before doing any heavy initialization
        with single_instance_lock():
            start_cli_server()
            main()
    except Exception:
        logging.exception("Exception during application startup")
        sys.exit(1)
