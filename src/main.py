import asyncio
import contextlib
import ctypes
import logging
import subprocess
import sys
import time
import winreg
from sys import argv
from types import TracebackType


def get_windows_version():
    # Read core OS information from the registry
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")

    product_name = winreg.QueryValueEx(key, "ProductName")[0]
    current_build = winreg.QueryValueEx(key, "CurrentBuild")[0]
    ubr = winreg.QueryValueEx(key, "UBR")[0]

    # Construct full build string
    full_build = f"{current_build}.{ubr}"

    # Correct Windows version label if necessary
    major_build = int(current_build)
    if major_build >= 22000 and not product_name.startswith("Windows 11"):
        product_name = product_name.replace("Windows 10", "Windows 11")

    return f"{product_name}, Build {full_build}"


import qasync

import pretty_log as _log
import settings
from core.application import YASBApplication
from core.bar_manager import BarManager
from core.config import get_config_and_stylesheet
from core.event_service import EventService
from core.log import init_logger
from core.tray import SystemTrayManager
from core.utils.controller import start_cli_server
from core.utils.update_service import get_update_service, start_update_checker
from core.watcher import create_observer
from env_loader import load_env, set_font_engine


@contextlib.contextmanager
def single_instance_lock(name: str = "yasb_reborn"):
    """Create a Windows mutex to ensure a single instance, with optional restart wait.

    If the process is launched with --restart-wait, the new instance will
    wait for the previous instance to exit and release the mutex (bounded
    wait) instead of exiting immediately.
    """
    ERROR_ALREADY_EXISTS = 183
    wait_for_restart = "--restart-wait" in sys.argv

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
            timeout_s = 10
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
    logging.debug("main() entrypoint reached.")

    try:
        data = get_windows_version()
        logging.info("Retrieved OS information.")
        logging.info(f" |  {data}")
    except BaseException as e:
        logging.info("Failed to retrieve OS information.")
        logging.info(f" |  {e}")
        try:
            platform = __import__("platform")
            simple_windows_version = lambda: f"Windows {platform.release()}, Build {platform.version()}"
            logging.info("Retrieved minimal OS information (may be innacurate).")
            logging.info(f" |  {simple_windows_version}")
        except BaseException:
            logging.warning("Failed to retrieve OS information.")

    logging.info("YASB info:")
    version = subprocess.check_output(["yasbc", "--version"]).decode().split("\n")
    logging.info(" |  version (Main): %r", version[0].replace("\r", ""))
    logging.info(" |  version (CLI):  %r", version[1].replace("\r", ""))

    # Application instance should be created first
    app = QApplication(argv)
    """Main entry point"""
    app = YASBApplication(argv)
    asyncio.run(main_async(app), loop_factory=qasync.QEventLoop)


async def main_async(app: YASBApplication):
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

    # Initialize configuration early after the single instance check
    config, stylesheet = get_config_and_stylesheet()

    if config["debug"]:
        settings.DEBUG = True
        logging.info("Debug mode enabled.")

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
    if config["show_systray"]:
        tray_manager = SystemTrayManager(manager)
        tray_manager.show()

    # Initialize auto update service
    if config["update_check"]:
        try:
            update_service = get_update_service()
            if update_service.is_update_supported():
                start_update_checker()
        except Exception as e:
            _log.log_error("Failed to start auto update service", e)

    # Wait for application shutdown
    try:
        await app_close_event.wait()
    except asyncio.CancelledError:
        logging.info("Application closes...")
    except Exception as e:
        logging.error(f"Error during application shutdown: {e}")
    finally:
        app.quit()
        sys.exit()


if __name__ == "__main__":
    init_logger()
    start_cli_server()
    load_env()
    set_font_engine()

    def exception_hook(_exctype: type, value: BaseException, _traceback: TracebackType | None):
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
