import logging
from os.path import join
from settings import DEFAULT_LOG_FILENAME, APP_NAME, APP_NAME_FULL
from core.config import get_config_dir

LOG_PATH = join(get_config_dir(), DEFAULT_LOG_FILENAME)
LOG_FORMAT = "%(asctime)s %(levelname)s %(filename)s: %(message)s"
LOG_DATETIME = "%Y-%m-%d %H:%M:%S"


def init_logger():
    logging.basicConfig(
        level=logging.DEBUG,
        filename=join(get_config_dir(), DEFAULT_LOG_FILENAME),
        format=LOG_FORMAT,
        datefmt=LOG_DATETIME,
        filemode="w",
    )

    logging.getLogger().addHandler(logging.StreamHandler())
    logging.info(f"{APP_NAME} - {APP_NAME_FULL}")
