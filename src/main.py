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
logging.getLogger('asyncio').setLevel(logging.WARNING)

def main():
    if sys.version_info < (3, 12):
        logging.error("This application requires Python 3.12 or higher.")
        sys.exit(1)
    config, stylesheet = get_config_and_stylesheet()
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
    app.aboutToQuit.connect(stop_observer)

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    init_logger()
    base_excepthook = sys.excepthook 
    def exception_hook(exctype, value, traceback):
        EventService().clear()
        logging.error("Unhandled exception", exc_info=value)
        # base_excepthook(exctype, value, traceback) 
        sys.exit(1) 
    sys.excepthook = exception_hook 
    try:
        main()
    except BaseException as e:
        if isinstance(e, SystemExit) and e.code == 0:
            exit(e.code)
        # remove StreamHandler
        logging.getLogger().handlers = [h for h in logging.getLogger().handlers if not isinstance(h, logging.StreamHandler)]
        logging.exception("Exception in main()")
        raise