import logging
import re
import winreg
import xml.etree.ElementTree as ET
from pathlib import Path

from comtypes import GUID, COMError  # pyright: ignore[reportMissingTypeStubs]
from winrt.windows.applicationmodel import AppInfo

from core.utils.shell_utils import shell_open
from core.utils.win32.aumid import activate_app_by_aumid
from core.utils.win32.aumid_process import get_process_name_for_aumid, resolve_shell_app
from core.utils.win32.bindings.ole32 import create_com_object
from core.utils.win32.bindings.shell32 import (
    INotificationActivationCallback,
    SHGetPropertyStoreFromParsingName,
    get_clsid_property,
)
from core.utils.win32.bindings.user32 import AllowSetForegroundWindow
from core.utils.win32.constants import ASFW_ANY, CLSCTX_LOCAL_SERVER, PKEY_AppUserModel_ToastActivatorCLSID
from core.widgets.services.taskbar.shortcut_resolver import find_shortcut_by_aumid

# at least two letters, so a drive letter isn't taken for a scheme
URI_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]+:")


def activate_toast(aumid: str, launch: str, activation_type: str) -> bool:
    """Hand a toast to its app, False when the app registered nothing that takes it."""
    if activation_type == "protocol":
        return _open_uri(launch)
    if activation_type in ("foreground", "background"):
        return _call_activator(aumid, launch)
    return False


def show_app(aumid: str) -> bool:
    """Bring the app's window forward, or start it. False when the app can't be found."""
    if not aumid:
        return False
    if activate_app_by_aumid(aumid, get_process_name_for_aumid(aumid)):
        return True
    if resolve_shell_app(aumid)[0] is None:
        return False
    shell_open(f"shell:AppsFolder\\{aumid}")
    return True


def _open_uri(launch: str) -> bool:
    # a file: URI is a path the sender chose, not a link
    if not URI_SCHEME.match(launch) or launch.lower().startswith("file:"):
        return False
    AllowSetForegroundWindow(ASFW_ANY)
    shell_open(launch)
    return True


def _call_activator(aumid: str, launch: str) -> bool:
    clsid = _find_activator(aumid)
    if clsid is None:
        return False
    # out of process, an app's activator never loads into YASB
    activator = create_com_object(clsid, INotificationActivationCallback, CLSCTX_LOCAL_SERVER)
    if activator is None:
        logging.warning("The toast activator %s of %s could not be created", clsid, aumid)
        return False
    AllowSetForegroundWindow(ASFW_ANY)
    try:
        activator.Activate(aumid, launch, None, 0)
    except COMError as e:
        logging.warning("The toast activator %s of %s failed: %s", clsid, aumid, e)
        return False
    return True


def _find_activator(aumid: str) -> GUID | None:
    """The COM class an app registered for its toasts, in the registry, on its Start menu shortcut or in its manifest."""
    if not aumid:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"AppUserModelId\\{aumid}") as key:
            return GUID(winreg.QueryValueEx(key, "CustomActivator")[0])
    except OSError, TypeError, ValueError:
        pass
    shortcut = find_shortcut_by_aumid(aumid)
    store = SHGetPropertyStoreFromParsingName(shortcut[0]) if shortcut is not None else None
    clsid = get_clsid_property(store, PKEY_AppUserModel_ToastActivatorCLSID) if store is not None else None
    return clsid if clsid is not None else _manifest_activator(get_install_folder(aumid), aumid.partition("!")[2])


def _manifest_activator(folder: Path | None, app_id: str) -> GUID | None:
    """The toast activator a packaged app declares for app_id in its AppxManifest.xml."""
    if folder is None or not app_id:
        return None
    try:
        for app in ET.parse(folder / "AppxManifest.xml").getroot().iterfind("{*}Applications/{*}Application"):
            if app.get("Id") == app_id:
                activation = app.find("{*}Extensions/{*}Extension/{*}ToastNotificationActivation")
                return GUID("{" + activation.get("ToastActivatorCLSID", "") + "}") if activation is not None else None
    except OSError, ET.ParseError, ValueError:
        pass
    return None


def get_install_folder(aumid: str) -> Path | None:
    # the listener's AppInfo doesn't implement Package (E_NOINTERFACE), a fresh lookup does
    try:
        folder = AppInfo.get_from_app_user_model_id(aumid).package.installed_path
    except Exception as e:
        logging.debug("No install folder for %s: %s", aumid, e)
        return None
    return Path(folder) if folder else None
