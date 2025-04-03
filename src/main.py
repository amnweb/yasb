import asyncio
import logging
import sys
import qasync
import ctypes
from dotenv import load_dotenv
from sys import argv, exit
import settings
from PyQt6.QtWidgets import QApplication
from core.bar_manager import BarManager
from core.config import get_config_and_stylesheet, get_resolved_env_file_path
from core.log import init_logger
from core.tray import TrayIcon
from core.watcher import create_observer
from core.event_service import EventService
from core.utils.cli_client import CliPipeHandler
from core.app_controller import process_cli_command

logging.getLogger('asyncio').setLevel(logging.WARNING)

def main():

    config, stylesheet = get_config_and_stylesheet()

    if config['debug']:
        settings.DEBUG = True
        logging.info("Debug mode enabled.")

    if getattr(sys, 'frozen', False):
        """
        Start the Named Pipe server to listen for incoming commands.
        This is only needed when running as a standalone executable.
        """
        pipe_handler = CliPipeHandler(cli_command=process_cli_command)
        pipe_handler.start_cli_pipe_server()

    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)

    env_file = config.get('env_file')
    if env_file:
        env_file = get_resolved_env_file_path(env_file)
        if load_dotenv(env_file):
            logging.info(f"Loaded environment variables from {env_file}")
        else:
            logging.warning(f"Failed to load environment variables from {env_file}")

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