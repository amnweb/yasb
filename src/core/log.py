import logging
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from os.path import join

from core.config import get_config_dir
from settings import APP_NAME, BUILD_VERSION, DEFAULT_LOG_FILENAME

LOG_PATH = join(get_config_dir(), DEFAULT_LOG_FILENAME)

LOG_FORMAT = "%(asctime)s,%(msecs)03d [%(levelname)s] [%(threadName)s] [%(name)s/%(filename)s:%(lineno)d]: %(message)s"
LOG_DATETIME = "%Y-%m-%d %H:%M:%S"
CONSOLE_FORMAT = "%(asctime)s,%(msecs)03d %(levelname)s: %(message)s"
CONSOLE_DATETIME = "%H:%M:%S"
CLI_LOG_FORMAT = "%(asctime)s,%(msecs)03d %(levelname)s: %(message)s"
CLI_LOG_DATETIME = "%H:%M:%S"


@dataclass
class Format:
    reset = "\033[0m"
    green = "\033[92m"
    yellow = "\033[93m"
    red = "\033[91m"
    red_bg = "\033[41m"
    underline = "\033[4m"
    gray = "\033[90m"
    blue = "\033[94m"


# ANSI escape codes for colors
LOG_COLORS = {
    "DEBUG": Format.blue,
    "INFO": Format.green,
    "WARNING": Format.yellow,
    "ERROR": Format.red,
    "CRITICAL": Format.red_bg,
    "RESET": Format.reset,
}


class ColoredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_color = LOG_COLORS.get(record.levelname, LOG_COLORS["RESET"])
        record.levelname = f"{log_color}{record.levelname:>8}{LOG_COLORS['RESET']}"
        return super().format(record)


def init_logger():
    # File handler should be without colors
    file_handler = RotatingFileHandler(
        join(get_config_dir(), DEFAULT_LOG_FILENAME), maxBytes=1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATETIME))
    # Configure logging with colors
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(CONSOLE_FORMAT, datefmt=CONSOLE_DATETIME))
    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])
    logging.info(f"{APP_NAME} v{BUILD_VERSION}")
