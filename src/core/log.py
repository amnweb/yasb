import logging
from logging.handlers import RotatingFileHandler
from os.path import join
from settings import DEFAULT_LOG_FILENAME, APP_NAME, BUILD_VERSION
from core.config import get_config_dir

LOG_PATH = join(get_config_dir(), DEFAULT_LOG_FILENAME)
LOG_FORMAT = "%(asctime)s,%(msecs)03d [%(threadName)s] [%(levelname)s] [%(name)s/%(filename)s:%(lineno)d]: %(message)s"
LOG_DATETIME = "%Y-%m-%d %H:%M:%S"
CONSOLE_FORMAT = "%(asctime)s,%(msecs)03d: %(message)s"
CONSOLE_DATETIME = "%H:%M:%S"

# ANSI escape codes for colors
LOG_COLORS = {
    "INFO": "\033[92m",  # Green
    "WARNING": "\033[93m",  # Yellow
    "ERROR": "\033[91m",  # Red
    "CRITICAL": "\033[41m",  # Red background
    "RESET": "\033[0m",  # Reset color
}


def init_logger():
    # File handler should be without colors
    file_handler = RotatingFileHandler(
        join(get_config_dir(), DEFAULT_LOG_FILENAME), maxBytes=1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATETIME))

    class ColoredFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_color = LOG_COLORS.get(record.levelname, LOG_COLORS["RESET"])
            record.msg = f"{log_color}{record.msg}{LOG_COLORS['RESET']}"
            return super().format(record)

    # Configure logging with colors
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter(CONSOLE_FORMAT, datefmt=CONSOLE_DATETIME))
    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, handler])
    logging.info(f"{APP_NAME} v{BUILD_VERSION}")
