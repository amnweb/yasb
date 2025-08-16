import asyncio
import contextlib
import ctypes
import logging
import os
import sys
import time
from sys import argv

import qasync
from PyQt6.QtWidgets import QApplication

import settings
from core.bar_manager import BarManager
from core.config import get_config_and_stylesheet
from core.event_service import EventService
from core.log import init_logger
from core.tray import SystemTrayManager
from core.utils.controller import start_cli_server
from core.utils.update_check import UpdateCheckService
from core.watcher import create_observer
from env_loader import load_env, set_font_engine

logging.getLogger("asyncio").setLevel(logging.WARNING)


@contextlib.contextmanager
def single_instance_lock(name="yasb_reborn"):
    """Create a Windows mutex to ensure a single instance, with optional restart wait.

    If the process is launched with --restart-wait (or env YASB_RESTART=1),
    the new instance will wait for the previous instance to exit and release
    the mutex (bounded wait) instead of exiting immediately.
    """
    ERROR_ALREADY_EXISTS = 183
    wait_for_restart = ("--restart-wait" in sys.argv) or (os.environ.get("YASB_RESTART") == "1")

    # CreateMutexW(bInitialOwner=True) to own the mutex while we run
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, name)
    if not mutex:
        logging.error("Failed to create mutex.")
        sys.exit(1)

    last_err = ctypes.windll.kernel32.GetLastError()
    if last_err == ERROR_ALREADY_EXISTS:
        # Another instance owns or created the mutex. If we're in restart mode, wait for it.
        if wait_for_restart:
            logging.info("Waiting for previous YASB instance to exit...")
            # Release our initial ownership before waiting to avoid interfering
            ctypes.windll.kernel32.ReleaseMutex(mutex)

            # Loop trying to acquire (CreateMutexW again) until timeout
            timeout_s = 20
            start = time.time()
            acquired = False
            while time.time() - start < timeout_s:
                ctypes.windll.kernel32.CloseHandle(mutex)
                mutex = ctypes.windll.kernel32.CreateMutexW(None, True, name)
                if not mutex:
                    logging.error("CreateMutexW failed while waiting")
                    break
                if ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS:
                    acquired = True
                    break
                # Still held by previous instance
                ctypes.windll.kernel32.ReleaseMutex(mutex)
                ctypes.windll.kernel32.CloseHandle(mutex)
                time.sleep(0.25)

            if not acquired:
                logging.error("Timeout waiting for previous instance. Aborting start.")
                sys.exit(1)

            logging.info("Previous instance exited, continuing startup.")
        else:
            ctypes.windll.kernel32.CloseHandle(mutex)
            logging.error("Another instance of the YASB is already running.")
            sys.exit(1)

    try:
        yield mutex
    finally:
        # Ensure we release and close the mutex on exit
        try:
            ctypes.windll.kernel32.ReleaseMutex(mutex)
        except Exception:
            pass
        ctypes.windll.kernel32.CloseHandle(mutex)


def main():
    # Application instance should be created first
    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)

    # Initialize configuration early after the single instance check
    config, stylesheet = get_config_and_stylesheet()

    if config["debug"]:
        settings.DEBUG = True
        logging.info("Debug mode enabled.")

    # Need qasync event loop to work with PyQt6
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Initialise bars and background event listeners
    manager = BarManager(config, stylesheet)
    manager.initialize_bars(init=True)

    # Initialise file watcher if needed
    observer = create_observer(manager) if config["watch_config"] or config["watch_stylesheet"] else None
    if observer:
        observer.start()

    def stop_observer():
        if observer:
            observer.stop()
            observer.join()

    app.aboutToQuit.connect(stop_observer)

    # Build system tray icon
    tray_manager = SystemTrayManager(manager)
    tray_manager.show()

    # Initialize auto update service
    if config["update_check"] and getattr(sys, "frozen", False):
        try:
            auto_update_service = UpdateCheckService()
            app.auto_update_service = auto_update_service
        except Exception as e:
            logging.error(f"Failed to start auto update service: {e}")

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    init_logger()
    start_cli_server()
    load_env()
    set_font_engine()

    def exception_hook(exctype, value, traceback):
        EventService().clear()
        logging.error("Unhandled exception", exc_info=value)
        sys.exit(1)

    sys.excepthook = exception_hook

    try:
        # Acquire the single instance lock before doing any heavy initialization
        with single_instance_lock():
            main()
    except Exception:
        logging.exception("Exception during application startup")
        sys.exit(1)
