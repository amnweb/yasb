import asyncio
import ctypes
import logging
import os
import winreg
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable, Coroutine, Iterable
from concurrent.futures import Future
from ctypes import byref, c_void_p
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import winrt.windows.ui.notifications.management as management
from PyQt6.QtCore import QThread, pyqtSignal
from winrt.windows.ui.notifications import (
    KnownNotificationBindings,
    NotificationKinds,
    ToastNotificationManager,
    UserNotification,
)

from core.events.service import EventService
from core.utils.win32.bindings.ntdll import (
    WNF_SUPPORTED,
    RtlSubscribeWnfStateChangeNotification,
    RtlUnsubscribeWnfStateChangeNotification,
    WnfCallbackType,
)
from core.utils.win32.undocumented import WNF_SHEL_NOTIFICATION_TOTAL, WNF_SHEL_NOTIFICATIONS
from core.widgets.services.notifications.toast_activation import activate_toast, get_install_folder, show_app

# seconds to wait after a change, so a burst of changes is read once
REFRESH_DELAY = 0.1
# where Windows records the web images it downloaded for toasts
WPNIDM_KEY = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications\wpnidm"


@dataclass(frozen=True, slots=True)
class NotificationItem:
    id: int
    aumid: str
    app_name: str
    title: str
    body: str
    created_at: datetime
    launch: str = ""
    activation_type: str = "foreground"
    attribution: str = ""
    # local files, "" when the toast has none or it isn't on this PC
    logo: str = ""
    logo_circle: bool = False
    hero: str = ""
    image: str = ""


class WindowsNotificationEventListener(QThread):
    clear_notifications = pyqtSignal(str)
    clear_app_notifications = pyqtSignal(str)
    refresh_notifications = pyqtSignal(str)
    remove_notification = pyqtSignal(int)
    activate_notification = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.total_notifications = 0
        self.event_service = EventService()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._async_stop_event: asyncio.Event | None = None
        self._stopped = False
        self._listener: management.UserNotificationListener | None = None
        self._wnf_sub = None
        self._wnf_active = False
        self._wnf_cb = WnfCallbackType(self._wnf_toast_callback)
        self._refresh_pending = False
        # the last list read, kept on the loop thread
        self._items: list[NotificationItem] = []

        self._events = (
            ("WindowsNotificationClear", self.clear_notifications, self._clear_notifications),
            ("WindowsNotificationClearApp", self.clear_app_notifications, self._clear_app_notifications),
            ("WindowsNotificationRefresh", self.refresh_notifications, self._refresh_notifications),
            ("WindowsNotificationRemove", self.remove_notification, self._remove_notification),
            ("WindowsNotificationActivate", self.activate_notification, self._activate_notification),
        )
        for event, signal, slot in self._events:
            signal.connect(slot)
            self.event_service.register_event(event, signal)

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._async_stop_event = asyncio.Event()

        # If stop was requested before the loop started running, set it immediately
        if self._stopped:
            self._async_stop_event.set()

        self._listener = management.UserNotificationListener.current

        try:
            status = self._loop.run_until_complete(self._listener.request_access_async())
            if status != management.UserNotificationListenerAccessStatus.ALLOWED:
                logging.warning("Notification access is turned off, the notification list will be empty")
            self._loop.run_until_complete(self._watch_notifications())
        except Exception as e:
            logging.error("Notification listener error: %s", e)
        finally:
            self._cleanup()

    def stop(self):
        self._stopped = True
        if self._loop and self._loop.is_running() and self._async_stop_event:
            self._loop.call_soon_threadsafe(self._async_stop_event.set)

    def _cleanup(self):
        """Clean up thread resources and unregister events."""
        logging.info("Notification service stopped")
        for event, signal, slot in self._events:
            self.event_service.unregister_event(event, signal)
            try:
                signal.disconnect(slot)
            except Exception:
                pass

        self._unsubscribe_wnf()
        self._wnf_cb = None  # Free ctypes callback pointer

        if self._loop:
            self._loop.run_until_complete(self._cancel_pending_tasks())
            self._loop.close()
            self._loop = None

    async def _watch_notifications(self):
        """WNF event-driven watch."""
        self._subscribe_wnf()
        await self._wait_for_stop()

    async def _wait_for_stop(self) -> None:
        if self._async_stop_event:
            await self._async_stop_event.wait()

    async def _cancel_pending_tasks(self):
        if not self._loop:
            return
        pending = asyncio.all_tasks(self._loop)
        pending.discard(asyncio.current_task())
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def _try_subscribe(self, state: int, name: str) -> bool:
        """Subscribe to a WNF state. Returns True on success."""
        callback = self._wnf_cb
        if not WNF_SUPPORTED or callback is None:
            return False
        try:
            sub = c_void_p()
            status = RtlSubscribeWnfStateChangeNotification(
                byref(sub),
                state,
                0,
                callback,
                None,
                None,
                0,
                0,
            )
            if status == 0:
                self._wnf_sub = sub
                self._wnf_active = True
                return True
            logging.debug("%s unavailable (0x%08X)", name, status & 0xFFFFFFFF)
        except Exception:
            logging.exception("Failed to subscribe to %s", name)
        return False

    def _subscribe_wnf(self):
        """Prefer Win11 state, fall back to Win10 NOTIFICATIONS (badge/unread)."""
        if self._wnf_active or not WNF_SUPPORTED:
            return
        if self._try_subscribe(WNF_SHEL_NOTIFICATION_TOTAL, "WNF_SHEL_NOTIFICATION_TOTAL"):
            logging.info("Notification service started (WNF_SHEL_NOTIFICATION_TOTAL)")
            return
        if self._try_subscribe(WNF_SHEL_NOTIFICATIONS, "WNF_SHEL_NOTIFICATIONS"):
            logging.info("Notification service started (WNF_SHEL_NOTIFICATIONS)")
            return
        logging.error("Notification service failed to subscribe to WNF")

    def _unsubscribe_wnf(self):
        """Unsubscribe from WNF."""
        if not self._wnf_active or not WNF_SUPPORTED or not self._wnf_sub:
            return
        try:
            RtlUnsubscribeWnfStateChangeNotification(self._wnf_sub)
        except Exception:
            pass
        self._wnf_sub = None
        self._wnf_active = False
        logging.debug("Unsubscribed from WNF notifications")

    def _wnf_toast_callback(
        self,
        _state_name: int,
        _change_stamp: int,
        _type_id: int | None,
        _context: int | None,
        buffer: int | None,
        buffer_size: int,
    ) -> int:
        """Buffer u32 is the count (Win11 total / Win10 unread badge). Skip unchanged values."""
        try:
            self._schedule_refresh()
            if not buffer or buffer_size < 4:
                return 0
            wnf_count = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint32))[0]
            if wnf_count == self.total_notifications:
                return 0
            self.total_notifications = wnf_count
            self.event_service.emit_event("WindowsNotificationUpdate", wnf_count)
        except Exception:
            logging.exception("Error in WNF callback")
        return 0

    def _clear_notifications(self, _msg: str = ""):
        self._submit(self._clear, None)

    def _clear_app_notifications(self, aumid: str):
        self._submit(self._clear, aumid)

    def _refresh_notifications(self, _msg: str = ""):
        self._schedule_refresh()

    def _remove_notification(self, notification_id: int):
        self._submit(self._remove, notification_id)

    def _activate_notification(self, item: NotificationItem):
        self._submit(self._activate, item)

    def _submit(self, function: Callable[..., Coroutine[None, None, None]], *args: object) -> bool:
        """Run function(*args) on the listener's loop, from any thread."""
        loop = self._loop
        if loop is None or not loop.is_running():
            return False
        try:
            future = asyncio.run_coroutine_threadsafe(function(*args), loop)
        except RuntimeError as e:
            logging.debug("Failed to schedule %s: %s", function.__name__, e)
            return False
        future.add_done_callback(_log_task_error)
        return True

    def _schedule_refresh(self):
        if not self._refresh_pending:
            self._refresh_pending = self._submit(self._refresh)

    async def _refresh(self):
        await asyncio.sleep(REFRESH_DELAY)
        self._refresh_pending = False
        items = await self._read_notifications()
        self._items = items or []
        self.event_service.emit_event("WindowsNotificationsChanged", items)

    async def _read_notifications(self) -> list[NotificationItem] | None:
        """Newest first, or None while notification access is turned off."""
        listener = self._listener
        if listener is None:
            return None
        try:
            if listener.get_access_status() != management.UserNotificationListenerAccessStatus.ALLOWED:
                return None
            notifications = await listener.get_notifications_async(NotificationKinds.TOAST)
        except Exception as e:
            logging.error("Error reading notifications: %s", e)
            return []
        return _read_items(sorted(notifications, key=lambda n: n.creation_time, reverse=True))

    async def _activate(self, item: NotificationItem):
        handled = activate_toast(item.aumid, item.launch, item.activation_type)
        if not handled:
            handled = show_app(item.aumid)
        if handled:
            await self._remove(item.id)

    async def _remove(self, notification_id: int):
        if self._listener is None:
            return
        try:
            self._listener.remove_notification(notification_id)
        except Exception as e:
            logging.debug("Failed to remove notification %s: %s", notification_id, e)
        self._schedule_refresh()

    async def _clear(self, aumid: str | None):
        """Remove every notification, or only those of aumid."""
        listener = self._listener
        if listener is None:
            return
        # ClearNotifications() fails with ERROR_NOT_FOUND without package identity
        for app in {item.aumid for item in self._items if aumid in (None, item.aumid)} - {""}:
            try:
                ToastNotificationManager.history.clear_with_id(app)
            except Exception as e:
                logging.debug("Failed to clear the notifications of %s: %s", app, e)
        if aumid is None:
            try:
                leftovers = [n.id for n in await listener.get_notifications_async(NotificationKinds.TOAST)]
            except Exception as e:
                logging.error("Error clearing notifications: %s", e)
                leftovers = []
        else:
            leftovers = [item.id for item in self._items if not aumid and not item.aumid]
        for notification_id in leftovers:
            try:
                listener.remove_notification(notification_id)
            except Exception as e:
                logging.debug("Failed to remove notification %s: %s", notification_id, e)
        self._schedule_refresh()


def _log_task_error(future: Future[None]):
    if not future.cancelled() and (error := future.exception()) is not None:
        logging.error("Notification service task failed", exc_info=error)


def _read_items(notifications: Iterable[UserNotification]) -> list[NotificationItem]:
    """Expects newest first, the order the toast history comes in."""
    entries = [(n, *_get_app_info(n)) for n in notifications]
    counts = Counter(aumid for _, aumid, _, _ in entries)
    history: dict[str, list[ET.Element]] = {}
    items: list[NotificationItem] = []
    for n, aumid, name, family in entries:
        texts = _get_texts(n)
        if aumid not in history:
            history[aumid] = _read_toast_xml(aumid, counts[aumid])
        toast = _pop_toast(history[aumid], texts)
        if toast is None:
            toast = ET.Element("toast")
        logo = _find_image(toast, "appLogoOverride")
        items.append(
            NotificationItem(
                id=n.id,
                aumid=aumid,
                app_name=name,
                title=texts[0] if texts else "",
                body="\n".join(texts[1:]),
                created_at=_get_display_timestamp(toast) or n.creation_time,
                launch=toast.get("launch", ""),
                activation_type=toast.get("activationType", "foreground"),
                attribution=_get_attribution(toast),
                logo=_get_image_path(logo, aumid, family),
                logo_circle=logo is not None and logo.get("hint-crop") == "circle",
                hero=_get_image_path(_find_image(toast, "hero"), aumid, family),
                image=_get_image_path(_find_image(toast, None), aumid, family),
            )
        )
    return items


def _get_app_info(notification: UserNotification) -> tuple[str, str, str]:
    """AUMID, display name and package family name, empty for a sender Windows can't name."""
    try:
        app = notification.app_info
        return app.app_user_model_id or "", app.display_info.display_name or "", app.package_family_name or ""
    except Exception:
        # senders without a registered AUMID raise E_NOTIMPL
        return "", "", ""


def _get_texts(notification: UserNotification) -> list[str]:
    try:
        binding = notification.notification.visual.get_binding(KnownNotificationBindings.toast_generic)
        # an empty text element comes back as whitespace
        return [text for element in binding.get_text_elements() if (text := (element.text or "").strip())]
    except Exception as e:
        logging.debug("Notification %s has no readable text: %s", notification.id, e)
        return []


def _read_toast_xml(aumid: str, count: int) -> list[ET.Element]:
    """The newest `count` toasts of aumid, newest first."""
    if not aumid:
        return []
    try:
        history = ToastNotificationManager.history.get_history_with_id(aumid)
    except Exception as e:
        logging.debug("Failed to read the toast history of %s: %s", aumid, e)
        return []
    toasts: list[ET.Element] = []
    for toast in history:
        if len(toasts) >= count:
            break
        try:
            toasts.append(ET.fromstring(toast.content.get_xml()))
        except OSError, ET.ParseError:
            # Windows keeps up to 100 entries per app but empties all but the newest 20
            continue
    return toasts


def _pop_toast(toasts: list[ET.Element], texts: list[str]) -> ET.Element | None:
    # the history has no notification ids, so a toast is matched by its text
    for index, toast in enumerate(toasts):
        if _get_xml_texts(toast) == texts:
            return toasts.pop(index)
    return None


def _get_display_timestamp(toast: ET.Element) -> datetime | None:
    try:
        timestamp = datetime.fromisoformat(toast.get("displayTimestamp", ""))
    except ValueError:
        return None
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)


def _get_attribution(toast: ET.Element) -> str:
    for element in toast.findall("visual/binding/text"):
        if element.get("placement") == "attribution":
            return (element.text or "").strip()
    return ""


def _get_xml_texts(toast: ET.Element) -> list[str]:
    """The text the listener returns: the binding's own text elements, without the attribution."""
    return [
        text
        for element in toast.findall("visual/binding/text")
        if element.get("placement") != "attribution" and (text := (element.text or "").strip())
    ]


def _find_image(toast: ET.Element, placement: str | None) -> ET.Element | None:
    """The binding's first image with this placement, None for an inline image."""
    binding = toast.find("visual/binding")
    if binding is None:
        return None
    # the Windows 8 templates (ToastImageAndText01-04) have one image, shown where appLogoOverride goes
    if binding.get("template", "").startswith("ToastImageAndText"):
        return binding.find("image") if placement == "appLogoOverride" else None
    for image in binding.findall("image"):
        if image.get("placement") == placement:
            return image
    return None


def _get_image_path(image: ET.Element | None, aumid: str, family: str) -> str:
    """The local file an image src points to, "" for a web image Windows didn't download or a missing file.

    https://learn.microsoft.com/uwp/schemas/tiles/toastschema/element-image lists the sources.
    """
    if image is None:
        return ""
    src = image.get("src", "").strip()
    url = urlparse(src)
    relative = unquote(url.path).lstrip("/")
    root: Path | None = None
    match url.scheme.lower():
        # a file on a share would hand the sender's server our credentials
        case "file" if not url.netloc:
            path = Path(relative)
        # urlparse takes the drive letter of a plain path for a scheme
        case scheme if len(scheme) == 1:
            path = Path(src)
        case "ms-appx" if family:
            root = get_install_folder(aumid)
            if root is None:
                return ""
            path = root / relative
        case "ms-appdata" if family and relative.lower().startswith("local/"):
            root = Path(os.environ.get("LOCALAPPDATA", ""), "Packages", family, "LocalState")
            path = root / relative[len("local/") :]
        # Windows downloaded it to draw the toast, we only read that copy
        case "http" | "https":
            root = Path(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Notifications", "wpnidm")
            path = Path(_get_downloaded_image(src))
        case _:
            return ""
    if not path.is_absolute() or path.drive.startswith(("\\\\", "//")):
        return ""
    try:
        path = path.resolve()
        if root is not None and not path.is_relative_to(root.resolve()):
            return ""
        return str(path) if path.is_file() else ""
    except OSError, ValueError:
        return ""


def _get_downloaded_image(url: str) -> str:
    """The file Windows saved for a web image, "" when it has none."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WPNIDM_KEY) as key:
            for index in range(winreg.QueryInfoKey(key)[0]):
                with winreg.OpenKey(key, winreg.EnumKey(key, index)) as entry:
                    if str(winreg.QueryValueEx(entry, "Url")[0]).removeprefix("wpnidm:") == url:
                        return str(winreg.QueryValueEx(entry, "LocalPath")[0])
    except OSError:
        pass
    return ""
