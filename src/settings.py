import os
import sys

# Application Metadata
BUILD_VERSION = "3.0.0"
CLI_VERSION = "1.3.0"
RELEASE_CHANNEL = "stable"
# Raised in its major number when a change to the services breaks widgets that use them
SERVICE_API_VERSION = (1, 0)
# Application Settings
APP_NAME = "YASB"
APP_NAME_FULL = "Yet Another Status Bar"
APP_BAR_TITLE = "YasbBar"
APP_ID = "YASB.YetAnotherStatusBar"
IS_FROZEN = getattr(sys, "frozen", False)
SCRIPT_PATH = os.path.dirname(sys.executable) if IS_FROZEN else os.path.dirname(os.path.abspath(__file__))
QML_IMPORT_PATH = os.path.join(SCRIPT_PATH, "core", "qml")
# The app's logo, and the copy on a transparent background that Windows notifications show
APP_ICON = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
APP_ICON_TRANSPARENT = os.path.join(SCRIPT_PATH, "assets", "images", "app_transparent.png")
# URLs
GITHUB_URL = "https://github.com/amnweb/yasb"
GITHUB_WIKI_URL = "https://github.com/amnweb/yasb/wiki"
WEBSITE_URL = "https://yasb.dev"
WEBSITE_DOCS_URL = "https://docs.yasb.dev/latest"
YASB_ADDONS = "https://github.com/amnweb/yasb-addons"
# Configuration Settings
DEFAULT_CONFIG_DIRECTORY = os.getenv("YASB_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config", "yasb")
DEFAULT_CONFIG_FILENAME = "config.yaml"
DEFAULT_LOG_FILENAME = "yasb.log"
