import logging
from logging.handlers import RotatingFileHandler
from os.path import join
from settings import DEFAULT_LOG_FILENAME, APP_NAME, BUILD_VERSION
from core.config import get_config_dir

LOG_PATH = join(get_config_dir(), DEFAULT_LOG_FILENAME)
LOG_FORMAT = "%(asctime)s %(levelname)s %(filename)s:%(lineno)d: %(message)s"
LOG_DATETIME = "%Y-%m-%d %H:%M:%S"


def init_logger():
    logging.basicConfig(
        handlers=[RotatingFileHandler(join(get_config_dir(), DEFAULT_LOG_FILENAME), maxBytes=1024*1024, backupCount=5)],
        level=logging.DEBUG,
        format=LOG_FORMAT,
        datefmt=LOG_DATETIME,
    )

    logging.getLogger().addHandler(logging.StreamHandler())
    logging.info(f"{APP_NAME} v{BUILD_VERSION}")