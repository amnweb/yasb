from core.utils.shell_utils import shell_open
from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import (
    ICON_SETTINGS,
    ICON_SETTINGS_PAGE_ABOUT,
    ICON_SETTINGS_PAGE_ACCESSIBILITY,
    ICON_SETTINGS_PAGE_ACCOUNTS,
    ICON_SETTINGS_PAGE_BLUETOOTH,
    ICON_SETTINGS_PAGE_CAMERA,
    ICON_SETTINGS_PAGE_COLORS,
    ICON_SETTINGS_PAGE_DATE_TIME,
    ICON_SETTINGS_PAGE_DEFAULT_APPS,
    ICON_SETTINGS_PAGE_DISPLAY,
    ICON_SETTINGS_PAGE_ETHERNET,
    ICON_SETTINGS_PAGE_FOCUS,
    ICON_SETTINGS_PAGE_INSTALLED_APPS,
    ICON_SETTINGS_PAGE_LANGUAGE_REGION,
    ICON_SETTINGS_PAGE_LOCK_SCREEN,
    ICON_SETTINGS_PAGE_MOBILE_HOTSPOT,
    ICON_SETTINGS_PAGE_MOUSE,
    ICON_SETTINGS_PAGE_MULTITASKING,
    ICON_SETTINGS_PAGE_NIGHT_LIGHT,
    ICON_SETTINGS_PAGE_NOTIFICATIONS,
    ICON_SETTINGS_PAGE_PERSONALIZATION,
    ICON_SETTINGS_PAGE_POWER_BATTERY,
    ICON_SETTINGS_PAGE_PRINTERS_SCANNERS,
    ICON_SETTINGS_PAGE_PRIVACY_SECURITY,
    ICON_SETTINGS_PAGE_PROXY,
    ICON_SETTINGS_PAGE_SIGN_IN_OPTIONS,
    ICON_SETTINGS_PAGE_SOUND,
    ICON_SETTINGS_PAGE_START,
    ICON_SETTINGS_PAGE_STARTUP_APPS,
    ICON_SETTINGS_PAGE_STORAGE,
    ICON_SETTINGS_PAGE_TASKBAR,
    ICON_SETTINGS_PAGE_TOUCHPAD,
    ICON_SETTINGS_PAGE_TYPING,
    ICON_SETTINGS_PAGE_VPN,
    ICON_SETTINGS_PAGE_WI_FI,
    ICON_SETTINGS_PAGE_WINDOWS_SECURITY,
    ICON_SETTINGS_PAGE_WINDOWS_UPDATE,
)

_SETTINGS_PAGES = [
    {
        "keywords": ["wifi", "wi-fi", "wireless", "network"],
        "title": "Wi-Fi",
        "description": "Network & internet > Wi-Fi",
        "icon": ICON_SETTINGS_PAGE_WI_FI,
        "uri": "ms-settings:network-wifi",
    },
    {
        "keywords": ["bluetooth"],
        "title": "Bluetooth",
        "description": "Bluetooth & devices",
        "icon": ICON_SETTINGS_PAGE_BLUETOOTH,
        "uri": "ms-settings:bluetooth",
    },
    {
        "keywords": ["display", "screen", "monitor", "resolution", "scale", "scaling"],
        "title": "Display",
        "description": "System > Display",
        "icon": ICON_SETTINGS_PAGE_DISPLAY,
        "uri": "ms-settings:display",
    },
    {
        "keywords": ["sound", "audio", "speaker", "volume", "microphone"],
        "title": "Sound",
        "description": "System > Sound",
        "icon": ICON_SETTINGS_PAGE_SOUND,
        "uri": "ms-settings:sound",
    },
    {
        "keywords": ["notifications", "notification"],
        "title": "Notifications",
        "description": "System > Notifications",
        "icon": ICON_SETTINGS_PAGE_NOTIFICATIONS,
        "uri": "ms-settings:notifications",
    },
    {
        "keywords": ["power", "battery", "energy", "power plan"],
        "title": "Power & battery",
        "description": "System > Power & battery",
        "icon": ICON_SETTINGS_PAGE_POWER_BATTERY,
        "uri": "ms-settings:powersleep",
    },
    {
        "keywords": ["storage", "disk", "space", "cleanup"],
        "title": "Storage",
        "description": "System > Storage",
        "icon": ICON_SETTINGS_PAGE_STORAGE,
        "uri": "ms-settings:storagesense",
    },
    {
        "keywords": ["multitasking", "snap", "virtual desktop"],
        "title": "Multitasking",
        "description": "System > Multitasking",
        "icon": ICON_SETTINGS_PAGE_MULTITASKING,
        "uri": "ms-settings:multitasking",
    },
    {
        "keywords": ["vpn"],
        "title": "VPN",
        "description": "Network & internet > VPN",
        "icon": ICON_SETTINGS_PAGE_VPN,
        "uri": "ms-settings:network-vpn",
    },
    {
        "keywords": ["proxy"],
        "title": "Proxy",
        "description": "Network & internet > Proxy",
        "icon": ICON_SETTINGS_PAGE_PROXY,
        "uri": "ms-settings:network-proxy",
    },
    {
        "keywords": ["personalization", "theme", "themes", "wallpaper", "background", "desktop background"],
        "title": "Personalization",
        "description": "Personalization",
        "icon": ICON_SETTINGS_PAGE_PERSONALIZATION,
        "uri": "ms-settings:personalization",
    },
    {
        "keywords": ["colors", "colour", "accent", "dark mode", "light mode"],
        "title": "Colors",
        "description": "Personalization > Colors",
        "icon": ICON_SETTINGS_PAGE_COLORS,
        "uri": "ms-settings:colors",
    },
    {
        "keywords": ["lock screen", "lockscreen"],
        "title": "Lock screen",
        "description": "Personalization > Lock screen",
        "icon": ICON_SETTINGS_PAGE_LOCK_SCREEN,
        "uri": "ms-settings:lockscreen",
    },
    {
        "keywords": ["taskbar"],
        "title": "Taskbar",
        "description": "Personalization > Taskbar",
        "icon": ICON_SETTINGS_PAGE_TASKBAR,
        "uri": "ms-settings:taskbar",
    },
    {
        "keywords": ["start menu", "start"],
        "title": "Start",
        "description": "Personalization > Start",
        "icon": ICON_SETTINGS_PAGE_START,
        "uri": "ms-settings:personalization-start",
    },
    {
        "keywords": ["apps", "installed apps", "programs", "uninstall", "add remove"],
        "title": "Installed apps",
        "description": "Apps > Installed apps",
        "icon": ICON_SETTINGS_PAGE_INSTALLED_APPS,
        "uri": "ms-settings:appsfeatures",
    },
    {
        "keywords": ["default apps", "defaults", "file association"],
        "title": "Default apps",
        "description": "Apps > Default apps",
        "icon": ICON_SETTINGS_PAGE_DEFAULT_APPS,
        "uri": "ms-settings:defaultapps",
    },
    {
        "keywords": ["startup apps", "startup"],
        "title": "Startup apps",
        "description": "Apps > Startup",
        "icon": ICON_SETTINGS_PAGE_STARTUP_APPS,
        "uri": "ms-settings:startupapps",
    },
    {
        "keywords": ["accounts", "account", "user", "profile"],
        "title": "Accounts",
        "description": "Accounts > Your info",
        "icon": ICON_SETTINGS_PAGE_ACCOUNTS,
        "uri": "ms-settings:yourinfo",
    },
    {
        "keywords": ["signin", "sign in", "password", "pin", "hello"],
        "title": "Sign-in options",
        "description": "Accounts > Sign-in options",
        "icon": ICON_SETTINGS_PAGE_SIGN_IN_OPTIONS,
        "uri": "ms-settings:signinoptions",
    },
    {
        "keywords": ["date", "time", "timezone", "clock", "time zone"],
        "title": "Date & time",
        "description": "Time & language > Date & time",
        "icon": ICON_SETTINGS_PAGE_DATE_TIME,
        "uri": "ms-settings:dateandtime",
    },
    {
        "keywords": ["language", "region", "locale", "input"],
        "title": "Language & region",
        "description": "Time & language > Language & region",
        "icon": ICON_SETTINGS_PAGE_LANGUAGE_REGION,
        "uri": "ms-settings:regionlanguage",
    },
    {
        "keywords": ["keyboard", "typing"],
        "title": "Typing",
        "description": "Time & language > Typing",
        "icon": ICON_SETTINGS_PAGE_TYPING,
        "uri": "ms-settings:typing",
    },
    {
        "keywords": ["update", "windows update", "check for updates"],
        "title": "Windows Update",
        "description": "Windows Update",
        "icon": ICON_SETTINGS_PAGE_WINDOWS_UPDATE,
        "uri": "ms-settings:windowsupdate",
    },
    {
        "keywords": ["privacy", "permissions"],
        "title": "Privacy & security",
        "description": "Privacy & security",
        "icon": ICON_SETTINGS_PAGE_PRIVACY_SECURITY,
        "uri": "ms-settings:privacy",
    },
    {
        "keywords": ["windows security", "virus", "antivirus", "defender", "firewall", "protection"],
        "title": "Windows Security",
        "description": "Privacy & security > Windows Security",
        "icon": ICON_SETTINGS_PAGE_WINDOWS_SECURITY,
        "uri": "ms-settings:windowsdefender",
    },
    {
        "keywords": ["mouse", "cursor", "pointer"],
        "title": "Mouse",
        "description": "Bluetooth & devices > Mouse",
        "icon": ICON_SETTINGS_PAGE_MOUSE,
        "uri": "ms-settings:mousetouchpad",
    },
    {
        "keywords": ["touchpad"],
        "title": "Touchpad",
        "description": "Bluetooth & devices > Touchpad",
        "icon": ICON_SETTINGS_PAGE_TOUCHPAD,
        "uri": "ms-settings:devices-touchpad",
    },
    {
        "keywords": ["printers", "printer", "scanners"],
        "title": "Printers & scanners",
        "description": "Bluetooth & devices > Printers & scanners",
        "icon": ICON_SETTINGS_PAGE_PRINTERS_SCANNERS,
        "uri": "ms-settings:printers",
    },
    {
        "keywords": ["camera", "webcam"],
        "title": "Camera",
        "description": "Bluetooth & devices > Camera",
        "icon": ICON_SETTINGS_PAGE_CAMERA,
        "uri": "ms-settings:camera",
    },
    {
        "keywords": ["accessibility", "ease of access", "narrator"],
        "title": "Accessibility",
        "description": "Accessibility",
        "icon": ICON_SETTINGS_PAGE_ACCESSIBILITY,
        "uri": "ms-settings:easeofaccess",
    },
    {
        "keywords": ["about", "system info", "device name", "rename pc", "specs", "specifications"],
        "title": "About",
        "description": "System > About",
        "icon": ICON_SETTINGS_PAGE_ABOUT,
        "uri": "ms-settings:about",
    },
    {
        "keywords": ["night light", "nightlight", "blue light"],
        "title": "Night light",
        "description": "System > Display > Night light",
        "icon": ICON_SETTINGS_PAGE_NIGHT_LIGHT,
        "uri": "ms-settings:nightlight",
    },
    {
        "keywords": ["focus", "do not disturb", "focus assist"],
        "title": "Focus",
        "description": "System > Focus",
        "icon": ICON_SETTINGS_PAGE_FOCUS,
        "uri": "ms-settings:quiethours",
    },
    {
        "keywords": ["ethernet", "wired", "lan"],
        "title": "Ethernet",
        "description": "Network & internet > Ethernet",
        "icon": ICON_SETTINGS_PAGE_ETHERNET,
        "uri": "ms-settings:network-ethernet",
    },
    {
        "keywords": ["mobile hotspot", "hotspot", "tethering"],
        "title": "Mobile hotspot",
        "description": "Network & internet > Mobile hotspot",
        "icon": ICON_SETTINGS_PAGE_MOBILE_HOTSPOT,
        "uri": "ms-settings:network-mobilehotspot",
    },
]


class SettingsProvider(BaseProvider):
    """Quick access to Windows Settings pages."""

    name = "settings"
    display_name = "Windows Settings"
    input_placeholder = "Search Windows settings..."
    icon = ICON_SETTINGS

    def match(self, text: str) -> bool:
        if self.prefix and text.strip().startswith(self.prefix):
            return True
        text_lower = text.strip().lower()
        if len(text_lower) < 2:
            return False
        for page in _SETTINGS_PAGES:
            for kw in page["keywords"]:
                if text_lower in kw or kw.startswith(text_lower):
                    return True
        return False

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = (
            self.get_query_text(text).lower()
            if self.prefix and text.strip().startswith(self.prefix)
            else text.strip().lower()
        )

        if not query:
            return [
                ProviderResult(
                    title=page["title"],
                    description=page["description"],
                    icon_char=page["icon"],
                    provider=self.name,
                    action_data={"uri": page["uri"]},
                )
                for page in _SETTINGS_PAGES
            ]

        results = []
        for page in _SETTINGS_PAGES:
            matched = any(query in kw or kw.startswith(query) for kw in page["keywords"])
            if not matched:
                matched = query in page["title"].lower()
            if matched:
                results.append(
                    ProviderResult(
                        title=page["title"],
                        description=page["description"],
                        icon_char=page["icon"],
                        provider=self.name,
                        action_data={"uri": page["uri"]},
                    )
                )
        return results

    def execute(self, result: ProviderResult) -> bool:
        uri = result.action_data.get("uri", "")
        if not uri:
            return False
        shell_open(uri)
        return True
