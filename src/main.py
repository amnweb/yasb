import logging
import sys
from sys import argv
from types import TracebackType

from core.application import YASBApplication
from core.log import init_logger
from core.utils.controller import start_cli_server
from core.utils.single_instance import single_instance_lock
from env import load_env, set_defaults

if __name__ == "__main__":
    init_logger()
    load_env()
    set_defaults()

    # PyQt drops the callback that raised and YASB keeps running, exiting here would skip the shutdown
    def exception_hook(_exctype: type, value: BaseException, _traceback: TracebackType | None):
        logging.error("Unhandled exception", exc_info=value)

    sys.excepthook = exception_hook

    try:
        # Acquire the single instance lock before doing any heavy initialization
        with single_instance_lock():
            start_cli_server()
            exit_code = YASBApplication(argv).run()
    except Exception:
        logging.exception("Exception during application startup")
        sys.exit(1)
    sys.exit(exit_code)
