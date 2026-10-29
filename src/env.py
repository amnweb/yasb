import logging
import os

from dotenv import load_dotenv
from PyQt6.QtQuick import QQuickWindow, QSGRendererInterface

from settings import DEFAULT_CONFIG_DIRECTORY


def get_env_path():
    return os.path.join(DEFAULT_CONFIG_DIRECTORY, ".env")


def load_env():
    """
    Load environment variables from a env_file file specified in the YASB configuration.
    """
    env_path = get_env_path()
    if os.path.isfile(env_path):
        if not load_dotenv(env_path):
            logging.warning("Failed to load environment variables from %s", env_path)
        else:
            logging.info("Loaded environment variables from %s", env_path)


def set_qt_quick_defaults():
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.Direct3D11)
    # Direct3D windows need no GDI redirection surface, which some systems paint opaque over a backdrop
    os.environ["QT_QPA_DISABLE_REDIRECTION_SURFACE"] = "1"
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "FluentWinUI3"
