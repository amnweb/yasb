"""Windows toast notifications, shown under YASB's app identity."""

import logging
from collections.abc import Callable
from functools import lru_cache
from typing import Any
from xml.sax.saxutils import escape

from comtypes import GUID, COMObject
from comtypes.server.localserver import ClassFactory
from winrt.windows.data.xml.dom import XmlDocument
from winrt.windows.ui.notifications import ToastNotification, ToastNotificationManager

from core.utils.win32.bindings.shell32 import INotificationActivationCallback
from core.utils.win32.constants import CLSCTX_LOCAL_SERVER
from core.utils.win32.registry_keys import APP_USER_MODEL_ID_KEY
from settings import TOAST_ACTIVATOR_CLSID

# What a click on a toast shown with an action does
_actions: dict[str, Callable[[], object]] = {}
_factory: ClassFactory | None = None


def on_toast(action: str, handler: Callable[[], object]) -> None:
    """Calls handler, on the main thread, when a toast shown with action or its button is clicked."""
    _actions[action] = handler


class _Activator(COMObject):
    """Takes YASB's toast clicks, from the notification center and from the notification widget alike. The installer
    registers it for YASB's toasts, and Windows starts YASB for a click while it isn't running."""

    _com_interfaces_ = [INotificationActivationCallback]
    _reg_clsid_ = GUID(TOAST_ACTIVATOR_CLSID)
    _reg_clsctx_ = CLSCTX_LOCAL_SERVER

    def Activate(self, this: Any, _app_id: str | None, action: str | None, _data: Any, _count: int) -> int:
        handler = _actions.get(action or "")
        if handler is not None:
            try:
                handler()
            except Exception:
                logging.exception("The toast action %s failed", action)
        return 0


def register_activator() -> None:
    """Takes toast clicks until revoke_activator; called on the main thread, whose message loop brings them in."""
    global _factory
    if _factory is None:
        try:
            _factory = ClassFactory(_Activator)
        except OSError:
            logging.warning("Clicks on YASB's notifications can't reach it", exc_info=True)


def revoke_activator() -> None:
    global _factory
    if _factory is not None:
        # comtypes has no public way to revoke
        _factory._revoke_class()  # pyright: ignore[reportPrivateUsage]
        _factory = None


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
        action: str | None = None,
    ) -> None:
        """A click on the toast or its button runs what on_toast gave for action, in place of opening launch_url."""
        # refer to https://learn.microsoft.com/en-us/uwp/schemas/tiles/toastschema/schema-root
        scenario = ' scenario="reminder"' if scenario else ""
        activation = f'activationType="foreground" launch="{action}"' if action else 'activationType="protocol"'
        button = (
            f'activationType="foreground" arguments="{action}"'
            if action
            else f'activationType="protocol" arguments="{launch_url}"'
        )
        actions = (
            f"""
            <actions>
                <action content="{launch_label}" {button}/>
            </actions>
            """
            if action or launch_url
            else ""
        )
        xml = XmlDocument()
        xml.load_xml(f"""
        <toast {activation} duration="{duration}"{scenario}>
            <visual>
                <binding template="ToastGeneric">
                    <image placement="appLogoOverride" hint-crop="circle" src="{icon_path}"/>
                    <text>{escape(title)}</text>
                    <text>{escape(message)}</text>
                </binding>
            </visual>
            {actions}
        </toast>
        """)
        self.toaster.show(ToastNotification(xml))
