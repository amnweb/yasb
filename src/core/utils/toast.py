"""Windows toast notifications, shown under YASB's app identity."""

from functools import lru_cache

from winrt.windows.data.xml.dom import XmlDocument
from winrt.windows.ui.notifications import ToastNotification, ToastNotificationManager

from core.utils.win32.registry_keys import APP_USER_MODEL_ID_KEY


@lru_cache(maxsize=1)
def get_app_identifier():
    """Returns AppUserModelID regardless of installation location"""
    import os
    import sys
    import winreg
    from pathlib import Path

    from settings import APP_ID, IS_FROZEN

    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{APP_USER_MODEL_ID_KEY}\\{APP_ID}")
        winreg.CloseKey(key)
        return APP_ID
    except:
        if IS_FROZEN:
            # Check if YASB is installed via Scoop and if so, return the path to the executable
            # This is a workaround for the issue where the registry key doesn't exist to return the correct App name and icon
            scoop_shortcut = os.path.join(
                os.environ.get("APPDATA", ""),
                "Microsoft",
                "Windows",
                "Start Menu",
                "Programs",
                "Scoop Apps",
                "YASB.lnk",
            )
            if Path(scoop_shortcut).exists():
                return sys.executable
        # Fallback to the default AppUserModelID
        return "YASB"


class ToastNotifier:
    """
    A class to show toast notifications using the Windows Toast Notification API.
    Methods:
        show(icon_path, title, message, duration):
    """

    def __init__(self):
        self.manager = ToastNotificationManager.get_default()
        self.toaster = self.manager.create_toast_notifier(get_app_identifier())

    def show(
        self,
        icon_path: str,
        title: str,
        message: str,
        duration: str = "short",
        launch_url: str | None = None,
        launch_label: str = "Download &amp; Install",
        scenario: str | None = None,
    ) -> None:
        # refer to https://learn.microsoft.com/en-us/uwp/schemas/tiles/toastschema/schema-root
        scenario = ' scenario="reminder"' if scenario else ""
        actions = (
            f"""
            <actions>
                <action
                    content="{launch_label}"
                    activationType="protocol"
                    arguments="{launch_url}"/>
            </actions>
            """
            if launch_url
            else ""
        )
        xml = XmlDocument()
        xml.load_xml(f"""
        <toast activationType="protocol" duration="{duration}"{scenario}>
            <visual>
                <binding template="ToastGeneric">
                    <image placement="appLogoOverride" hint-crop="circle" src="{icon_path}"/>
                    <text>{title}</text>
                    <text>{message}</text>
                </binding>
            </visual>
            {actions}
        </toast>
        """)
        notification = ToastNotification(xml)
        self.toaster.show(notification)
