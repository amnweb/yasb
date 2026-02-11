import os

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult

_SETTINGS_PAGES = [
    {
        "keywords": ["wifi", "wi-fi", "wireless", "network"],
        "title": "Wi-Fi",
        "description": "Network & internet > Wi-Fi",
        "icon": "\ue701",
        "uri": "ms-settings:network-wifi",
    },
    {
        "keywords": ["bluetooth"],
        "title": "Bluetooth",
        "description": "Bluetooth & devices",
        "icon": "\ue702",
        "uri": "ms-settings:bluetooth",
    },
    {
        "keywords": ["display", "screen", "monitor", "resolution", "scale", "scaling"],
        "title": "Display",
        "description": "System > Display",
        "icon": "\ue7f4",
        "uri": "ms-settings:display",
    },
    {
        "keywords": ["sound", "audio", "speaker", "volume", "microphone"],
        "title": "Sound",
        "description": "System > Sound",
        "icon": "\ue767",
        "uri": "ms-settings:sound",
    },
    {
        "keywords": ["notifications", "notification"],
        "title": "Notifications",
        "description": "System > Notifications",
        "icon": "\ue7e7",
        "uri": "ms-settings:notifications",
    },
    {
        "keywords": ["power", "battery", "energy", "power plan"],
        "title": "Power & battery",
        "description": "System > Power & battery",
        "icon": "\uee63",
        "uri": "ms-settings:powersleep",
    },
    {
        "keywords": ["storage", "disk", "space", "cleanup"],
        "title": "Storage",
        "description": "System > Storage",
        "icon": "\ueda2",
        "uri": "ms-settings:storagesense",
    },
    {
        "keywords": ["multitasking", "snap", "virtual desktop"],
        "title": "Multitasking",
        "description": "System > Multitasking",
        "icon": "\ue7c4",
        "uri": "ms-settings:multitasking",
    },
    {
        "keywords": ["vpn"],
        "title": "VPN",
        "description": "Network & internet > VPN",
        "icon": "\ue705",
        "uri": "ms-settings:network-vpn",
    },
    {
        "keywords": ["proxy"],
        "title": "Proxy",
        "description": "Network & internet > Proxy",
        "icon": "\ue968",
        "uri": "ms-settings:network-proxy",
    },
    {
        "keywords": ["personalization", "theme", "themes", "wallpaper", "background", "desktop background"],
        "title": "Personalization",
        "description": "Personalization",
        "icon": "\ue771",
        "uri": "ms-settings:personalization",
    },
    {
        "keywords": ["colors", "colour", "accent", "dark mode", "light mode"],
        "title": "Colors",
        "description": "Personalization > Colors",
        "icon": "\ue790",
        "uri": "ms-settings:colors",
    },
    {
        "keywords": ["lock screen", "lockscreen"],
        "title": "Lock screen",
        "description": "Personalization > Lock screen",
        "icon": "\ue72e",
        "uri": "ms-settings:lockscreen",
    },
    {
        "keywords": ["taskbar"],
        "title": "Taskbar",
        "description": "Personalization > Taskbar",
        "icon": "\ue7c4",
        "uri": "ms-settings:taskbar",
    },
    {
        "keywords": ["start menu", "start"],
        "title": "Start",
        "description": "Personalization > Start",
        "icon": "\ue8fc",
        "uri": "ms-settings:personalization-start",
    },
    {
        "keywords": ["apps", "installed apps", "programs", "uninstall", "add remove"],
        "title": "Installed apps",
        "description": "Apps > Installed apps",
        "icon": "\ued35",
        "uri": "ms-settings:appsfeatures",
    },
    {
        "keywords": ["default apps", "defaults", "file association"],
        "title": "Default apps",
        "description": "Apps > Default apps",
        "icon": "\ued35",
        "uri": "ms-settings:defaultapps",
    },
    {
        "keywords": ["startup apps", "startup"],
        "title": "Startup apps",
        "description": "Apps > Startup",
        "icon": "\ue945",
        "uri": "ms-settings:startupapps",
    },
    {
        "keywords": ["accounts", "account", "user", "profile"],
        "title": "Accounts",
        "description": "Accounts > Your info",
        "icon": "\ue910",
        "uri": "ms-settings:yourinfo",
    },
    {
        "keywords": ["signin", "sign in", "password", "pin", "hello"],
        "title": "Sign-in options",
        "description": "Accounts > Sign-in options",
        "icon": "\ue928",
        "uri": "ms-settings:signinoptions",
    },
    {
        "keywords": ["date", "time", "timezone", "clock", "time zone"],
        "title": "Date & time",
        "description": "Time & language > Date & time",
        "icon": "\uec92",
        "uri": "ms-settings:dateandtime",
    },
    {
        "keywords": ["language", "region", "locale", "input"],
        "title": "Language & region",
        "description": "Time & language > Language & region",
        "icon": "\ue774",
        "uri": "ms-settings:regionlanguage",
    },
    {
        "keywords": ["keyboard", "typing"],
        "title": "Typing",
        "description": "Time & language > Typing",
        "icon": "\ue765",
        "uri": "ms-settings:typing",
    },
    {
        "keywords": ["update", "windows update", "check for updates"],
        "title": "Windows Update",
        "description": "Windows Update",
        "icon": "\ue777",
        "uri": "ms-settings:windowsupdate",
    },
    {
        "keywords": ["privacy", "permissions"],
        "title": "Privacy & security",
        "description": "Privacy & security",
        "icon": "\ue8d7",
        "uri": "ms-settings:privacy",
    },
    {
        "keywords": ["windows security", "virus", "antivirus", "defender", "firewall", "protection"],
        "title": "Windows Security",
        "description": "Privacy & security > Windows Security",
        "icon": "\ue83d",
        "uri": "ms-settings:windowsdefender",
    },
    {
        "keywords": ["mouse", "cursor", "pointer"],
        "title": "Mouse",
        "description": "Bluetooth & devices > Mouse",
        "icon": "\ue962",
        "uri": "ms-settings:mousetouchpad",
    },
    {
        "keywords": ["touchpad"],
        "title": "Touchpad",
        "description": "Bluetooth & devices > Touchpad",
        "icon": "\uefa5",
        "uri": "ms-settings:devices-touchpad",
    },
    {
        "keywords": ["printers", "printer", "scanners"],
        "title": "Printers & scanners",
        "description": "Bluetooth & devices > Printers & scanners",
        "icon": "\ue749",
        "uri": "ms-settings:printers",
    },
    {
        "keywords": ["camera", "webcam"],
        "title": "Camera",
        "description": "Bluetooth & devices > Camera",
        "icon": "\ue722",
        "uri": "ms-settings:camera",
    },
    {
        "keywords": ["accessibility", "ease of access", "narrator"],
        "title": "Accessibility",
        "description": "Accessibility",
        "icon": "\ue776",
        "uri": "ms-settings:easeofaccess",
    },
    {
        "keywords": ["about", "system info", "device name", "rename pc", "specs", "specifications"],
        "title": "About",
        "description": "System > About",
        "icon": "\ue946",
        "uri": "ms-settings:about",
    },
    {
        "keywords": ["night light", "nightlight", "blue light"],
        "title": "Night light",
        "description": "System > Display > Night light",
        "icon": "\uf08c",
        "uri": "ms-settings:nightlight",
    },
    {
        "keywords": ["focus", "do not disturb", "focus assist"],
        "title": "Focus",
        "description": "System > Focus",
        "icon": "\ue708",
        "uri": "ms-settings:quiethours",
    },
    {
        "keywords": ["ethernet", "wired", "lan"],
        "title": "Ethernet",
        "description": "Network & internet > Ethernet",
        "icon": "\ue839",
        "uri": "ms-settings:network-ethernet",
    },
    {
        "keywords": ["mobile hotspot", "hotspot", "tethering"],
        "title": "Mobile hotspot",
        "description": "Network & internet > Mobile hotspot",
        "icon": "\ue88a",
        "uri": "ms-settings:network-mobilehotspot",
    },
]


class SettingsProvider(BaseProvider):
    """Quick access to Windows Settings pages."""

    name = "settings"

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

    def get_results(self, text: str) -> list[ProviderResult]:
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
        if uri:
            os.startfile(uri)
            return True
        return False
