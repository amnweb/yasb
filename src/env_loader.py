import logging
import os
import sys

from dotenv import load_dotenv


def get_env_path():
    config_home = os.environ.get("YASB_CONFIG_HOME")
    if config_home:
        return os.path.join(config_home, ".env")
    return os.path.join(os.path.expanduser("~"), ".config", "yasb", ".env")


def load_env():
    """
    Load environment variables from a env_file file specified in the YASB configuration.
    """
    env_path = get_env_path()
    if os.path.isfile(env_path):
        if not load_dotenv(env_path):
            logging.warning(f"Failed to load environment variables from {env_path}")
        else:
            logging.info(f"Loaded environment variables from {env_path}")


def set_font_engine():
    """
    Set the font engine for the application based on the YASB_FONT_ENGINE environment variable.
    When launched with --service, proactively register user-installed fonts  before configuring the Qt font engine.
    """
    if "--service" in sys.argv:
        font_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")
        if os.path.isdir(font_dir):
            from core.utils.win32.bindings.gdi32 import AddFontResource
            from core.utils.win32.bindings.user32 import SendNotifyMessage

            fonts = [f for f in os.listdir(font_dir) if f.lower().endswith((".ttf", ".otf", ".ttc"))]
            for f in fonts:
                AddFontResource(os.path.join(font_dir, f))
            if fonts:
                SendNotifyMessage(0xFFFF, 0x001D, 0, 0)

    font_engine = os.getenv("YASB_FONT_ENGINE")
    if font_engine == "native":
        os.environ["QT_QPA_PLATFORM"] = "windows:fontengine=native"
    elif font_engine == "freetype":
        os.environ["QT_QPA_PLATFORM"] = "windows:fontengine=freetype"
    else:
        os.environ["QT_QPA_PLATFORM"] = "windows:fontengine=gdi"
