import asyncio
import logging
import sys
from sys import argv, exit
import qasync
from PyQt6.QtWidgets import QApplication
from core.bar_manager import BarManager
from core.config import get_config_and_stylesheet
from core.log import init_logger
from core.tray import TrayIcon
from core.watcher import create_observer
from core.event_service import EventService
import settings
import ctypes
import ctypes.wintypes
from core.utils.win32.windows import WindowsTaskbar

logging.getLogger('asyncio').setLevel(logging.WARNING)

def main():
    config, stylesheet = get_config_and_stylesheet()
    global hide_taskbar
    hide_taskbar = config['hide_taskbar']
    
    if config['debug']:
        settings.DEBUG = True
        logging.info("Debug mode enabled.")
    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)

    # Need qasync event loop to make async calls work properly with PyQt6
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Initialise bars and background event listeners
    manager = BarManager(config, stylesheet)
    manager.initialize_bars(init=True)

    # Build system tray icon
    tray_icon = TrayIcon(manager)
    tray_icon.show()

    # Initialise file watcher
    if config['watch_config'] or config['watch_stylesheet']:
        observer = create_observer(manager)
        observer.start()
    else:
        observer = None

    # Stop observer upon quit
    def stop_observer():
        if observer:
            observer.stop()
            observer.join()
            if hide_taskbar:
                WindowsTaskbar.hide(False, settings.DEBUG)
    app.aboutToQuit.connect(stop_observer)

    with loop:
        if hide_taskbar:
            WindowsTaskbar.hide(True, settings.DEBUG)
        loop.run_forever()
        

if __name__ == "__main__":
    init_logger()
    base_excepthook = sys.excepthook 
    def exception_hook(exctype, value, traceback):
        if hide_taskbar:
            WindowsTaskbar.hide(False, settings.DEBUG)
        EventService().clear()
        logging.error("Unhandled exception", exc_info=value)
        sys.exit(1) 
    sys.excepthook = exception_hook 

    # Create a named mutex to prevent multiple instances
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "yasb_reborn")
    if mutex == 0:
        logging.error("Failed to create mutex.")
        sys.exit(1)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        logging.error("Another instance of the YASB is already running.")
        ctypes.windll.kernel32.CloseHandle(mutex)
        sys.exit(1)
    try:
        main()
    except BaseException as e:
        if isinstance(e, SystemExit) and e.code == 0:
            exit(e.code)
        # remove StreamHandler
        logging.getLogger().handlers = [h for h in logging.getLogger().handlers if not isinstance(h, logging.StreamHandler)]
        logging.exception("Exception in main()")
        raise
    finally:
        ctypes.windll.kernel32.ReleaseMutex(mutex)
        ctypes.windll.kernel32.CloseHandle(mutex)