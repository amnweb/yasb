import asyncio
import logging
import signal
import sys
from sys import argv
from types import FrameType, TracebackType

import qasync  # pyright: ignore[reportMissingTypeStubs]

from core.application import YASBApplication
from core.bar_manager import BarManager
from core.config import get_config_and_stylesheet, is_first_run
from core.events.service import EventService
from core.log import enable_debug_logging, init_logger
from core.tray import SystemTrayManager
from core.ui.views.welcome import run_setup_wizard
from core.utils.controller import start_cli_server
from core.utils.single_instance import single_instance_lock
from core.utils.system_colors import SystemColorsService
from core.utils.update_service import get_update_service, start_update_checker
from core.watcher import create_observer
from env import load_env, set_font_engine


def main():
    """Main entry point"""
    app = YASBApplication(argv)

    if is_first_run() and not run_setup_wizard():
        return

    loop = qasync.QEventLoop(app)
    try:
        loop.run_until_complete(main_async(app))  # pyright: ignore[reportUnknownMemberType]
    finally:
        loop.close()


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

    def handle_sigint(_signum: int, _frame: FrameType | None) -> None:
        logging.info("KeyboardInterrupt (Ctrl+C) detected. Initiating graceful shutdown...")
        app_close_event.set()

    try:
        signal.signal(signal.SIGINT, handle_sigint)
    except ValueError:
        pass

    # Initialize configuration early after the single instance check
    config, stylesheet = get_config_and_stylesheet()

    if config.debug:
        enable_debug_logging()
        logging.info("Debug mode enabled.")

    # Initialise bars and background event listeners
    manager = BarManager(config, stylesheet)

    try:
        manager.initialize_bars(init=True)
        # Initialise file watcher if needed
        observer = create_observer(manager) if config.watch_config or config.watch_stylesheet else None
        if observer:
            observer.start()

        def stop_observer():
            if observer:
                observer.stop()
                observer.join()

        app.aboutToQuit.connect(stop_observer)

        # Initialize system colors service
        if config.system_colors:
            SystemColorsService.start_service()

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
    set_font_engine()

    def exception_hook(_exctype: type, value: BaseException, _traceback: TracebackType | None):
        EventService().clear()
        logging.error("Unhandled exception", exc_info=value)
        sys.exit(1)

    sys.excepthook = exception_hook

    try:
        # Acquire the single instance lock before doing any heavy initialization
        with single_instance_lock():
            start_cli_server()
            main()
    except Exception:
        logging.exception("Exception during application startup")
        sys.exit(1)
