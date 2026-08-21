"""Logging for the cloud app and the automatic backup worker."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.cloud.constants import LOG_BACKUP_COUNT, LOG_MAX_BYTES
from core.cloud.session import cloud_dir
from core.cloud.settings import load as load_settings

NAME = "core.cloud"
FORMAT = "%(asctime)s,%(msecs)03d [%(levelname)s] [%(threadName)s] [%(name)s/%(filename)s:%(lineno)d]: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.getLogger(NAME).addHandler(logging.NullHandler())


def set_level(debug: bool) -> None:
    """Apply the Detailed logging setting."""
    logging.getLogger(NAME).setLevel(logging.DEBUG if debug else logging.WARNING)


def setup(filename: str) -> None:
    """Attach this process's log file. Called once, from the entry point.

    An unwritable log leaves the app logging nowhere rather than stopping a backup.
    """
    logger = logging.getLogger(NAME)
    if any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        return

    logger.propagate = False
    set_level(load_settings().debug_logging)
    try:
        handler = RotatingFileHandler(
            Path(cloud_dir()) / filename,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        return

    handler.setFormatter(logging.Formatter(FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)
