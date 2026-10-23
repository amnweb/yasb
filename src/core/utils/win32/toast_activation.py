"""Handing a notification back to the app that sent it, the way the shell does.

Clicking a notification in the Notification Center does not just raise the sending app: it
gives the app the launch string of that particular toast, which is how a screenshot
notification opens the screenshot and a browser notification opens the page behind it.
The listener API has nothing for this, so what the shell does is done here instead.

There are two ways in, and which one a toast wants is written in its payload. A toast that
asks for protocol activation names a URI, which is opened like any other link. Everything
else goes to the sender's toast activator, a COM class the app registers for exactly this
call, either in the registry for a plain desktop app or in the manifest for a packaged one.
A sender that has neither cannot be handed anything, and the caller is told so.
"""

import logging
import re
import uuid
import winreg
import xml.etree.ElementTree as ET

from comtypes import GUID, COMError  # pyright: ignore[reportMissingTypeStubs]

from core.utils.win32.bindings.ole32 import CoInitialize, create_com_object
from core.utils.win32.bindings.shell32 import INotificationActivationCallback, shell_execute
from core.utils.win32.bindings.user32 import AllowSetForegroundWindow
from core.utils.win32.constants import ASFW_ANY, CLSCTX_LOCAL_SERVER
from core.utils.win32.packages import installed_path, package_family_name

# ShellExecute reports failure as a value that would be a meaningless instance handle
SHELL_EXECUTE_MIN_SUCCESS = 32
# A URI scheme as RFC 3986 spells it, two letters at the least so that a drive letter,
# which reads as a one letter scheme, is not taken for one
URI_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]+:")

# Where a plain desktop app registers the class the shell calls back into. A packaged app
# declares it in its manifest instead, under this element
CUSTOM_ACTIVATOR = "CustomActivator"
ACTIVATION_ELEMENT = "ToastNotificationActivation"
ACTIVATION_ATTRIBUTE = "ToastActivatorCLSID"
# Toasts whose activation the shell handles itself, with nothing to hand the sender
SHELL_ACTIVATION_TYPES = ("system",)


def activate_toast(aumid: str, launch: str, activation_type: str) -> bool:
    """Act on a notification the way clicking it in the Notification Center does.

    Returns whether the sender was actually handed the notification, so a caller can fall
    back to merely raising it for a sender that registered no way of taking one.
    """
    activation_type = activation_type.casefold()
    if activation_type in SHELL_ACTIVATION_TYPES:
        return False
    if activation_type == "protocol":
        return _open_protocol(launch)
    return _invoke_activator(aumid, launch)


def _open_protocol(launch: str) -> bool:
    """Open the URI a toast names, which is what protocol activation amounts to.

    Only a URI, the way the shell only launches one: ShellExecute would just as readily
    run a program or open a file, and the launch string is written by the sender. A file:
    URI is a path by another name, so it is turned away with the rest.
    """
    if not URI_SCHEME.match(launch) or launch[:5].casefold() == "file:":
        if launch:
            logging.debug("Not opening a notification protocol that is not a URI: %s", launch)
        return False
    # Let whichever process the notification goes to take the foreground, which it is only
    # allowed to do because the click that got us here happened in a window of ours
    AllowSetForegroundWindow(ASFW_ANY)
    result = shell_execute(launch)
    if result and result > SHELL_EXECUTE_MIN_SUCCESS:
        return True
    logging.debug("Failed to open the notification protocol %s (%s)", launch, result)
    return False


def _invoke_activator(aumid: str, launch: str) -> bool:
    """Call the sender's toast activator with the launch string of the notification."""
    clsid = toast_activator_clsid(aumid)
    if not clsid:
        return False

    try:
        # The registry spells it with braces and a manifest without, comtypes only reads the first
        class_id = GUID(f"{{{uuid.UUID(clsid)}}}")
    except ValueError:
        logging.debug("The toast activator of %s is not a CLSID: %s", aumid, clsid)
        return False

    # An apartment of some kind is needed before the class can be created, and the caller
    # is not always one that has been in COM before
    CoInitialize()
    activator = create_com_object(class_id, INotificationActivationCallback, CLSCTX_LOCAL_SERVER)
    if activator is None:
        logging.debug("The toast activator of %s could not be created", aumid)
        return False

    AllowSetForegroundWindow(ASFW_ANY)
    try:
        # No user input: the menu shows a notification, it does not offer its input fields
        activator.Activate(aumid, launch, None, 0)
    except COMError as e:
        logging.debug("%s refused the notification (0x%08X)", aumid, e.hresult & 0xFFFFFFFF)
        return False
    return True


# aumid -> clsid, for senders that have one
_activators: dict[str, str] = {}


def toast_activator_clsid(aumid: str) -> str:
    """The class the sender registered to be called back on, or an empty string if none.

    Only a class that was found is remembered. A sender without one is looked up again on
    the next click, since it may have registered one since, and a click is rare enough for
    a registry read and a manifest to cost nothing that anybody notices.
    """
    if not aumid:
        return ""
    clsid = _activators.get(aumid)
    if clsid is None:
        clsid = _registered_activator(aumid) or _declared_activator(aumid)
        if clsid:
            _activators[aumid] = clsid
    return clsid


def _registered_activator(aumid: str) -> str:
    """What a plain desktop app writes under its AUMID when it registers for toasts."""
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"AppUserModelId\{aumid}") as key:
            return str(winreg.QueryValueEx(key, CUSTOM_ACTIVATOR)[0]).strip()
    except OSError:
        return ""


def _declared_activator(aumid: str) -> str:
    """What a packaged app declares in its manifest instead of registering one."""
    root = installed_path(package_family_name(aumid))
    if root is None:
        return ""
    manifest = root / "AppxManifest.xml"
    try:
        tree = ET.parse(manifest)
    except (ET.ParseError, OSError) as e:
        logging.debug("Unreadable manifest for %s: %s", aumid, e)
        return ""

    # The element is namespaced by the manifest schema it came from, which has changed
    # more than once, so it is matched on its local name
    for element in tree.iter():
        _, _, name = element.tag.rpartition("}")
        if name == ACTIVATION_ELEMENT:
            clsid = (element.get(ACTIVATION_ATTRIBUTE) or "").strip()
            if clsid:
                return clsid
    return ""
