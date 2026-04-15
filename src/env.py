import logging
import os

from dotenv import load_dotenv

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


def set_font_engine():
    """
    Set the font engine for the application based on the YASB_FONT_ENGINE environment variable.
    """
    valid_engines = {"native", "freetype", "gdi"}
    font_engine = os.getenv("YASB_FONT_ENGINE", "gdi").lower()
    if font_engine not in valid_engines:
        logging.warning("Unknown font engine '%s', falling back to 'gdi'", font_engine)
        font_engine = "gdi"
    os.environ["QT_QPA_PLATFORM"] = f"windows:fontengine={font_engine}"
