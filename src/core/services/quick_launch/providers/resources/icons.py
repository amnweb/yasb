"""Icons used in the Quick Launch widget."""

from pathlib import Path

from settings import SCRIPT_PATH

ICONS_DIR = Path(SCRIPT_PATH) / "core" / "qml" / "Yasb" / "Widgets" / "QuickLaunch" / "icons"


def _icon(name: str) -> str:
    return str(ICONS_DIR / f"{name}.svg")


# Widget UI icons header section
ICON_SEARCH_INPUT = "\ue721"  # Search input icon
ICON_SUBMIT = "\ue751"  # Search input enter/return icon
ICON_SEARCH_MAIN = _icon("search-main")


# Providers icons
ICON_APPS = _icon("apps")
ICON_BINANCE = _icon("binance")
ICON_BOOKMARK = _icon("bookmark")
ICON_CALCULATOR = _icon("calculator")
ICON_CLIPBOARD = _icon("clipboard")
ICON_COLOR = _icon("color")
ICON_COLOR_PICKER = _icon("color-picker")
ICON_CURRENCY = _icon("currency")
ICON_EMOJI = _icon("emoji")
ICON_KILL_PROCESS = _icon("kill-process")
ICON_PORT = _icon("port")
ICON_SEARCH = _icon("search")
ICON_SETTINGS = _icon("settings")
ICON_SNIPPET = _icon("snippet")
ICON_SYSTEM = _icon("system")
ICON_UNIT = _icon("unit")
ICON_WEB_SEARCH = _icon("web-search")
ICON_CLOCK = _icon("clock")
ICON_HACKER_NEWS = _icon("hacker-news")
ICON_DEV_TOOLS = _icon("dev-tools")
ICON_IP_INFO = _icon("ip-info")
ICON_VSCODE = _icon("vscode")
ICON_WINDOWS_SWITCHER = _icon("windows-switcher")
ICON_WINDOWS_TERMINAL = _icon("windows-terminal")
ICON_WINDOWS_TERMINAL_PREVIEW = _icon("windows-terminal-preview")
ICON_WINDOWS_TERMINAL_CANARY = _icon("windows-terminal-canary")
ICON_GITHUB = _icon("github")
ICON_SSH = _icon("ssh")
ICON_WSL = _icon("wsl")
ICON_EXAMPLE = "\ue8a7"


# General purpose
ICON_WARNING = _icon("warning")
ICON_CLEAR = _icon("clear")


# File type icons (used by file_search ext -> icon mapping)
ICON_FILE = _icon("file")
ICON_FOLDER = _icon("folder")
ICON_TEXT = _icon("text")
ICON_IMAGE = _icon("image")
ICON_VIDEO = _icon("video")
ICON_AUDIO = _icon("audio")
ICON_CODE = _icon("code")
ICON_ARCHIVE = _icon("archive")
ICON_PDF = _icon("pdf")
ICON_SPREADSHEET = _icon("spreadsheet")
ICON_PRESENTATION = _icon("presentation")
ICON_DATABASE = _icon("database")
ICON_FONT = _icon("font")
ICON_EXE = _icon("exe")
ICON_DISC = _icon("disc")


# Clipboard-specific
ICON_CLIPBOARD_TEXT = ICON_TEXT
ICON_CLIPBOARD_IMAGE = ICON_IMAGE


# System command-specific
ICON_SHUTDOWN = _icon("shutdown")
ICON_RESTART = _icon("restart")
ICON_SLEEP = _icon("sleep")
ICON_HIBERNATE = _icon("hibernate")
ICON_LOCK = _icon("lock")
ICON_SIGN_OUT = _icon("sign-out")


# Settings page icons
ICON_SETTINGS_PAGE_WI_FI = _icon("settings-page-wi-fi")
ICON_SETTINGS_PAGE_BLUETOOTH = _icon("settings-page-bluetooth")
ICON_SETTINGS_PAGE_DISPLAY = _icon("settings-page-display")
ICON_SETTINGS_PAGE_SOUND = _icon("settings-page-sound")
ICON_SETTINGS_PAGE_NOTIFICATIONS = _icon("settings-page-notifications")
ICON_SETTINGS_PAGE_POWER_BATTERY = _icon("settings-page-power-battery")
ICON_SETTINGS_PAGE_STORAGE = _icon("settings-page-storage")
ICON_SETTINGS_PAGE_MULTITASKING = _icon("settings-page-multitasking")
ICON_SETTINGS_PAGE_VPN = _icon("settings-page-vpn")
ICON_SETTINGS_PAGE_PROXY = _icon("settings-page-proxy")
ICON_SETTINGS_PAGE_PERSONALIZATION = _icon("settings-page-personalization")
ICON_SETTINGS_PAGE_COLORS = _icon("settings-page-colors")
ICON_SETTINGS_PAGE_LOCK_SCREEN = _icon("settings-page-lock-screen")
ICON_SETTINGS_PAGE_TASKBAR = _icon("settings-page-taskbar")
ICON_SETTINGS_PAGE_START = _icon("settings-page-start")
ICON_SETTINGS_PAGE_INSTALLED_APPS = _icon("settings-page-installed-apps")
ICON_SETTINGS_PAGE_DEFAULT_APPS = _icon("settings-page-default-apps")
ICON_SETTINGS_PAGE_STARTUP_APPS = _icon("settings-page-startup-apps")
ICON_SETTINGS_PAGE_ACCOUNTS = _icon("settings-page-accounts")
ICON_SETTINGS_PAGE_SIGN_IN_OPTIONS = _icon("settings-page-sign-in-options")
ICON_SETTINGS_PAGE_DATE_TIME = _icon("settings-page-date-time")
ICON_SETTINGS_PAGE_LANGUAGE_REGION = _icon("settings-page-language-region")
ICON_SETTINGS_PAGE_TYPING = _icon("settings-page-typing")
ICON_SETTINGS_PAGE_WINDOWS_UPDATE = _icon("settings-page-windows-update")
ICON_SETTINGS_PAGE_PRIVACY_SECURITY = _icon("settings-page-privacy-security")
ICON_SETTINGS_PAGE_WINDOWS_SECURITY = _icon("settings-page-windows-security")
ICON_SETTINGS_PAGE_MOUSE = _icon("settings-page-mouse")
ICON_SETTINGS_PAGE_TOUCHPAD = _icon("settings-page-touchpad")
ICON_SETTINGS_PAGE_PRINTERS_SCANNERS = _icon("settings-page-printers-scanners")
ICON_SETTINGS_PAGE_CAMERA = _icon("settings-page-camera")
ICON_SETTINGS_PAGE_ACCESSIBILITY = _icon("settings-page-accessibility")
ICON_SETTINGS_PAGE_ABOUT = _icon("settings-page-about")
ICON_SETTINGS_PAGE_NIGHT_LIGHT = _icon("settings-page-night-light")
ICON_SETTINGS_PAGE_FOCUS = _icon("settings-page-focus")
ICON_SETTINGS_PAGE_ETHERNET = _icon("settings-page-ethernet")
ICON_SETTINGS_PAGE_MOBILE_HOTSPOT = _icon("settings-page-mobile-hotspot")
# End settings page icons

# Web search-specific
ICON_WEB_GOOGLE = _icon("web-google")
ICON_WEB_BING = _icon("web-bing")
ICON_WEB_BRAVE = _icon("web-brave")
ICON_WEB_DUCKDUCKGO = _icon("web-duckduckgo")
ICON_WEB_WIKIPEDIA = _icon("web-wikipedia")
ICON_WEB_GITHUB = _icon("web-github")
ICON_WEB_YOUTUBE = _icon("web-youtube")
ICON_WEB_REDDIT = _icon("web-reddit")
ICON_WEB_X_TWITTER = _icon("web-x-twitter")
ICON_WEB_STACKOVERFLOW = _icon("web-stackoverflow")

# Github icons
GITHUB_ISSUE_OPEN = _icon("github-issue-open")
GITHUB_ISSUE_CLOSED = _icon("github-issue-closed")
GITHUB_PR_OPEN = _icon("github-pr-open")
GITHUB_PR_CLOSED = _icon("github-pr-closed")
GITHUB_PR_MERGED = _icon("github-pr-merged")

GITHUB_PR_DRAFT = _icon("github-pr-draft")

GITHUB_RELEASE = _icon("github-release")
GITHUB_DISCUSSION = _icon("github-discussion")
GITHUB_CHECKSUITE = _icon("github-checksuite")
GITHUB_DEFAULT = ICON_GITHUB


# WSL icons
ICON_WSL_RUNNING = _icon("wsl-running")
ICON_WSL_STOPPED = _icon("wsl-stopped")
ICON_WSL_ONLINE = _icon("wsl-online")
