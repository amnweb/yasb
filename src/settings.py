import os
import sys

# Application Metadata
BUILD_VERSION = "3.0.0"
CLI_VERSION = "1.3.0"
RELEASE_CHANNEL = "stable"

# Application Settings
APP_NAME = "YASB"
APP_NAME_FULL = "Yet Another Status Bar"
APP_BAR_TITLE = "YasbBar"
APP_ID = "YASB.YetAnotherStatusBar"

# The installer's upgrade code
MSI_UPGRADE_CODE = "{3f620cf5-07b5-47fd-8e37-9ca8ad14b608}"
# The COM class that takes clicks on YASB's notifications
TOAST_ACTIVATOR_CLSID = "{24B95123-2CD6-414B-9C51-3ED187712BFC}"

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
