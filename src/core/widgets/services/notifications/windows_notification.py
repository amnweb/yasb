import asyncio
import ctypes
import logging
from ctypes import POINTER, byref, c_void_p
from dataclasses import dataclass

import winrt.windows.ui.notifications.management as management
from PyQt6.QtCore import QThread, pyqtSignal
from winrt.windows.ui.notifications import (
    KnownNotificationBindings,
    NotificationKinds,
    ToastNotificationManager,
    UserNotification,
)

from core.events.service import EventService

_ntdll = ctypes.WinDLL("ntdll")

WnfCallbackType = ctypes.WINFUNCTYPE(
    ctypes.c_long,  # NTSTATUS
    ctypes.c_uint64,  # StateName
    ctypes.c_ulong,  # ChangeStamp
    c_void_p,  # TypeId
    c_void_p,  # CallbackContext
    c_void_p,  # Buffer
    ctypes.c_ulong,  # BufferSize
)

try:
    _RtlSubscribeWnfStateChangeNotification = _ntdll.RtlSubscribeWnfStateChangeNotification
    _RtlSubscribeWnfStateChangeNotification.restype = ctypes.c_long
    _RtlSubscribeWnfStateChangeNotification.argtypes = [
        POINTER(c_void_p),
        ctypes.c_uint64,
        ctypes.c_ulong,
        WnfCallbackType,
        c_void_p,
        c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]

    _RtlUnsubscribeWnfStateChangeNotification = _ntdll.RtlUnsubscribeWnfStateChangeNotification
    _RtlUnsubscribeWnfStateChangeNotification.restype = ctypes.c_long
    _RtlUnsubscribeWnfStateChangeNotification.argtypes = [c_void_p]
    WNF_SUPPORTED = True
except AttributeError:
    _RtlSubscribeWnfStateChangeNotification = None
    _RtlUnsubscribeWnfStateChangeNotification = None
    WNF_SUPPORTED = False

# Win11: Action Center toast total
WNF_SHEL_NOTIFICATION_TOTAL = 0x0D83063EA3B8D035
# Win10: unread/badge count
WNF_SHEL_NOTIFICATIONS = 0x0D83063EA3BC1035


@dataclass(frozen=True, slots=True)
class NotificationItem:
    """A single toast notification, flattened to plain Python types.

    WinRT objects are bound to the listener thread, so they are converted here before
    being handed over to the GUI thread through the event service.
    """

    id: int
    aumid: str
    app_name: str
    title: str
    body: str
    created_at: str  # ISO 8601, consumed by core.utils.time_utils.get_relative_time


class WindowsNotificationEventListener(QThread):
    clear_notifications = pyqtSignal(str)
    refresh_notifications = pyqtSignal(str)
    remove_notification = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.total_notifications = 0
        self.event_service = EventService()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._async_stop_event: asyncio.Event | None = None
        self._stopped = False
        self._listener = None
        self._access_allowed = True
        self._wnf_sub = None
        self._wnf_active = False
        self._wnf_cb = WnfCallbackType(self._wnf_toast_callback)

        for signal, slot, event in (
            (self.clear_notifications, self._clear_notifications, "WindowsNotificationClear"),
            (self.refresh_notifications, self._refresh_notifications, "WindowsNotificationRefresh"),
            (self.remove_notification, self._remove_notification, "WindowsNotificationRemove"),
        ):
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
            self._loop.run_until_complete(self._listener.request_access_async())
            self._refresh_access()
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
        for signal, slot, event in (
            (self.clear_notifications, self._clear_notifications, "WindowsNotificationClear"),
            (self.refresh_notifications, self._refresh_notifications, "WindowsNotificationRefresh"),
            (self.remove_notification, self._remove_notification, "WindowsNotificationRemove"),
        ):
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
        await self._emit_notifications()
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
        if not WNF_SUPPORTED:
            return False
        try:
            sub = c_void_p()
            status = _RtlSubscribeWnfStateChangeNotification(
                byref(sub),
                ctypes.c_uint64(state),
                0,
                self._wnf_cb,
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
            _RtlUnsubscribeWnfStateChangeNotification(self._wnf_sub)
        except Exception:
            pass
        self._wnf_sub = None
        self._wnf_active = False
        logging.debug("Unsubscribed from WNF notifications")

    def _wnf_toast_callback(self, _state_name, _change_stamp, _type_id, _context, buffer, buffer_size):
        """Buffer u32 is the count (Win11 total / Win10 unread badge). Skip unchanged values."""
        try:
            if not buffer or buffer_size < 4:
                return 0
            wnf_count = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint32))[0]
            if wnf_count == self.total_notifications:
                return 0
            self.total_notifications = wnf_count
            self.event_service.emit_event("WindowsNotificationUpdate", wnf_count)
            # This runs on an ntdll thread, so the fetch is queued onto the listener loop
            self._schedule(self._emit_notifications())
        except Exception:
            logging.exception("Error in WNF callback")
        return 0

    def _schedule(self, coro):
        """Run a coroutine on the listener loop from any thread."""
        if not (self._loop and self._loop.is_running()):
            coro.close()
            return
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except RuntimeError as e:
            coro.close()
            logging.debug("Failed to schedule notification task: %s", e)

    def _clear_notifications(self, _msg: str = ""):
        self._schedule(self._do_clear_all_notifications())

    def _refresh_notifications(self, _msg: str = ""):
        self._schedule(self._emit_notifications())

    def _remove_notification(self, notification_id: int):
        self._schedule(self._do_remove_notification(notification_id))

    def _set_access(self, allowed: bool):
        """Remember whether Windows granted access and let the widgets know when it changes.

        Access is a single global switch for apps installed outside the Store, so a denied
        listener silently returns an empty list forever. The menu says so instead of
        pretending there is nothing to show.
        """
        if allowed == self._access_allowed:
            return
        self._access_allowed = allowed
        if not allowed:
            logging.warning("Notification access is denied, the notification list will stay empty")
        else:
            logging.info("Notification access granted")
        self.event_service.emit_event("WindowsNotificationAccess", allowed)

    def _refresh_access(self) -> bool:
        """Re-read the access status, which the user can revoke at any time."""
        try:
            status = self._listener.get_access_status()
        except Exception as e:
            logging.debug("Failed to read notification access status: %s", e)
            return self._access_allowed
        self._set_access(status == management.UserNotificationListenerAccessStatus.ALLOWED)
        return self._access_allowed

    async def _emit_notifications(self):
        """Read the current toasts and broadcast them to the widgets."""
        self.event_service.emit_event("WindowsNotificationsChanged", await self._read_notifications())

    async def _read_notifications(self) -> list[NotificationItem]:
        if not self._listener or not self._refresh_access():
            return []
        try:
            notifications = await self._listener.get_notifications_async(NotificationKinds.TOAST)
        except Exception as e:
            logging.error("Error reading notifications: %s", e)
            return []
        # Windows returns the oldest first, but the newest belongs at the top of the menu
        return [self._to_item(n) for n in reversed(list(notifications))]

    @classmethod
    def _to_item(cls, notification: UserNotification) -> NotificationItem:
        aumid = ""
        app_name = ""
        try:
            app_info = notification.app_info
            aumid = app_info.app_user_model_id or ""
            app_name = app_info.display_info.display_name or ""
        except Exception as e:
            # Senders whose AUMID is not registered (plain Win32 apps) raise E_NOTIMPL here
            logging.debug("Notification %s has no app info: %s", notification.id, e)

        created_at = ""
        try:
            created_at = notification.creation_time.isoformat()
        except Exception as e:
            logging.debug("Notification %s has no creation time: %s", notification.id, e)

        texts = cls._read_text_elements(notification)
        return NotificationItem(
            id=notification.id,
            aumid=aumid,
            app_name=app_name,
            title=texts[0] if texts else "",
            body="\n".join(texts[1:]),
            created_at=created_at,
        )

    @staticmethod
    def _read_text_elements(notification: UserNotification) -> list[str]:
        """Return the toast text lines, preferring the generic binding over any other one."""
        try:
            visual = notification.notification.visual
            binding = visual.get_binding(KnownNotificationBindings.toast_generic)
            bindings = [binding] if binding is not None else list(visual.bindings)
        except Exception as e:
            logging.debug("Notification %s has no readable visual: %s", notification.id, e)
            return []

        for binding in bindings:
            texts = [element.text for element in binding.get_text_elements() if element.text]
            if texts:
                return texts
        return []

    async def _do_remove_notification(self, notification_id: int):
        try:
            self._listener.remove_notification(notification_id)
        except Exception as e:
            logging.debug("Failed to remove notification %s: %s", notification_id, e)
        await self._emit_notifications()

    async def _do_clear_all_notifications(self):
        """Empty the Action Center, then report whatever is actually left.

        Two passes, because neither one alone empties it. The listener hands out at most
        twenty notifications per app while the Action Center keeps one more, so removing
        the ones we were given leaves that last one behind, still counted on the bar and
        still there when the user opens the Notification Center. Clearing the history of
        each sender takes it too.

        The history is cleared per app rather than in one call: ClearNotifications() fails
        with ERROR_NOT_FOUND for apps installed outside the Store. A removal can still fail
        and a new toast can arrive while this runs, so the result is read back instead of
        assuming the Action Center is empty. The count on the bar is left to the WNF
        callback, which reports what Windows itself counts.
        """
        try:
            notifications = await self._listener.get_notifications_async(NotificationKinds.TOAST)
        except Exception as e:
            logging.error("Error clearing notifications: %s", e)
            return

        senders: list[str] = []
        for n in notifications:
            aumid = self._aumid_of(n)
            if aumid and aumid not in senders:
                senders.append(aumid)
            try:
                self._listener.remove_notification(n.id)
            except Exception as e:
                logging.debug("Failed to remove notification %s: %s", n.id, e)

        for aumid in senders:
            try:
                ToastNotificationManager.history.clear_with_id(aumid)
            except Exception as e:
                logging.debug("Failed to clear the notification history of %s: %s", aumid, e)

        await self._emit_notifications()

    @staticmethod
    def _aumid_of(notification: UserNotification) -> str:
        try:
            return notification.app_info.app_user_model_id or ""
        except Exception as e:
            # Senders whose AUMID is not registered (plain Win32 apps) raise E_NOTIMPL here
            logging.debug("Notification %s has no app info: %s", notification.id, e)
            return ""
