import os
import sys

# Application Settings
APP_NAME = "YASB"
APP_NAME_FULL = "Yet Another Status Bar"
APP_BAR_TITLE = "YasbBar"
APP_ID = "YASB.YetAnotherStatusBar"
SCRIPT_PATH = (
    os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
)
GITHUB_URL = "https://github.com/amnweb/yasb"
GITHUB_THEME_URL = "https://github.com/amnweb/yasb-themes"
BUILD_VERSION = "1.7.8"
CLI_VERSION = "1.1.2"
RELEASE_CHANNEL = "stable"
# Development Settings
DEBUG = False
# Configuration Settings
DEFAULT_CONFIG_DIRECTORY = os.getenv("YASB_CONFIG_HOME", ".config\\yasb")
DEFAULT_STYLES_FILENAME = "styles.css"
DEFAULT_CONFIG_FILENAME = "config.yaml"
DEFAULT_LOG_FILENAME = "yasb.log"
