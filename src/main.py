import logging
import sys
from sys import argv, exit
from PyQt6.QtWidgets import QApplication
from core.bar_manager import BarManager
from core.config import get_config_and_stylesheet
from core.log import init_logger
from core.tray import TrayIcon
from core.watcher import create_observer
from core.event_service import EventService

def main():
    config, stylesheet = get_config_and_stylesheet()

    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)

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

    # Start Application
    exit_status = app.exec()

    # Before Application Exit
    if observer:
        observer.stop()
        observer.join()
    exit(exit_status)

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