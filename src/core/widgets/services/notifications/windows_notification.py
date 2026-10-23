import asyncio
import ctypes
import logging
from collections.abc import Coroutine
from ctypes import byref, c_void_p
from dataclasses import dataclass, replace
from typing import Any

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
from core.widgets.services.notifications.toast_images import read_toast_details


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
    # Local file paths, resolved by core.widgets.services.notifications.toast_images
    app_logo: str = ""
    app_logo_circle: bool = False
    hero: str = ""
    inline_images: tuple[str, ...] = ()
    # How the notification database files the sender, which for a browser is one entry per
    # website rather than one for the browser: the sender the Notification Center groups
    # by and heads with a name and an icon of its own
    sender_id: str = ""
    sender_icon: str = ""
    # What the shell hands the sender when the notification is clicked, and how
    launch: str = ""
    activation_type: str = ""


class WindowsNotificationEventListener(QThread):
    clear_notifications = pyqtSignal(str)
    refresh_notifications = pyqtSignal(str)
    remove_notification = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        # What Windows publishes for the shell, kept only for the case where the list
        # itself cannot be read. It is not the number the menu shows: see _count_on_bar
        self._wnf_count = 0
        self._wnf_stamp: int | None = None
        self.event_service = EventService()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._async_stop_event: asyncio.Event | None = None
        self._stopped = False
        self._listener: management.UserNotificationListener | None = None
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
        change_stamp: int,
        _type_id: int | None,
        _context: int | None,
        buffer: int | None,
        buffer_size: int,
    ) -> int:
        """Windows wrote the toast counter, which is the signal that the list has changed.

        Every write is taken as a reason to read the list again, including one that leaves
        the number where it was. The number is not to be trusted on its own: it counts what
        the shell was told rather than what the Action Center holds, and a notification
        activated from the Notification Center leaves its share of the count behind. So the
        buffer (u32: Win11 total / Win10 unread badge) is only kept as a last resort, and
        the change stamp is what tells one write from the next.
        """
        try:
            if change_stamp == self._wnf_stamp:
                return 0
            self._wnf_stamp = change_stamp
            if buffer and buffer_size >= 4:
                self._wnf_count = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint32))[0]
            # This runs on an ntdll thread, so the fetch is queued onto the listener loop
            self._schedule(self._emit_notifications())
        except Exception:
            logging.exception("Error in WNF callback")
        return 0

    def _schedule(self, coro: Coroutine[Any, Any, Any]) -> None:
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
        if self._listener is None:
            return self._access_allowed
        try:
            status = self._listener.get_access_status()
        except Exception as e:
            logging.debug("Failed to read notification access status: %s", e)
            return self._access_allowed
        self._set_access(status == management.UserNotificationListenerAccessStatus.ALLOWED)
        return self._access_allowed

    async def _emit_notifications(self):
        """Read the current toasts and broadcast them, along with the count, to the widgets."""
        notifications = await self._read_notifications()
        self.event_service.emit_event("WindowsNotificationsChanged", notifications)
        self.event_service.emit_event("WindowsNotificationUpdate", self._count_on_bar(notifications))

    def _count_on_bar(self, notifications: list[NotificationItem]) -> int:
        """How many notifications there are, counted the way the menu counts them.

        The list is the only honest answer: what Windows publishes for the shell drifts
        away from it, because a notification activated from the Notification Center is
        taken off the list without being taken off that count. Which leaves the published
        number good for one thing, namely the case where there is no list to count, when
        the user has turned notification access off.
        """
        return len(notifications) if self._access_allowed else self._wnf_count

    async def _read_notifications(self) -> list[NotificationItem]:
        if not self._listener or not self._refresh_access():
            return []
        try:
            notifications = await self._listener.get_notifications_async(NotificationKinds.TOAST)
        except Exception as e:
            logging.error("Error reading notifications: %s", e)
            return []
        # Windows returns the oldest first, but the newest belongs at the top of the menu
        items = [self._to_item(n) for n in reversed(list(notifications))]
        return self._with_details(items)

    @staticmethod
    def _with_details(items: list[NotificationItem]) -> list[NotificationItem]:
        """Fill in what the listener API does not hand out but Windows stored anyway.

        The images a toast carries are only in the payload Windows kept for itself, and so
        is the launch string that says what clicking it should do. So is the sender, which
        the listener reports as the app while the database files it the way the Notification
        Center groups it, one entry per website for a browser. The batch is read in one go.
        """
        try:
            details = read_toast_details({item.id: item.aumid for item in items})
        except Exception:
            logging.exception("Failed to read toast details")
            return items

        enriched: list[NotificationItem] = []
        for item in items:
            found = details.get(item.id)
            if found is None:
                enriched.append(item)
                continue
            enriched.append(
                replace(
                    item,
                    # Only ever a fallback. What the listener reports is the sender the
                    # shell will activate, while this is how the database files it, which
                    # for a browser is one entry per website and activates nothing
                    aumid=item.aumid or found.sender,
                    # The other way round for the name: the database knows the website a
                    # notification came from, the listener only knows the browser
                    app_name=found.sender_name or item.app_name,
                    app_logo=found.images.app_logo,
                    app_logo_circle=found.images.app_logo_circle,
                    hero=found.images.hero,
                    inline_images=found.images.inline,
                    sender_id=found.sender or item.aumid,
                    sender_icon=found.sender_icon,
                    launch=found.launch,
                    activation_type=found.activation_type,
                )
            )
        return enriched

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
            # Replaced by what the database files the sender under, where it has one
            sender_id=aumid,
        )

    @staticmethod
    def _read_text_elements(notification: UserNotification) -> list[str]:
        """Return the toast text lines, preferring the generic binding over any other one."""
        try:
            visual = notification.notification.visual
            binding = visual.get_binding(KnownNotificationBindings.toast_generic)
            # None when the toast has no generic binding, which the stubs do not say
            bindings = [binding] if binding is not None else list(visual.bindings)  # pyright: ignore[reportUnnecessaryComparison]
        except Exception as e:
            logging.debug("Notification %s has no readable visual: %s", notification.id, e)
            return []

        for binding in bindings:
            texts = [element.text for element in binding.get_text_elements() if element.text]
            if texts:
                return texts
        return []

    async def _do_remove_notification(self, notification_id: int):
        if self._listener is None:
            return
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
        assuming the Action Center is empty, and it is that result the bar is given.
        """
        listener = self._listener
        if listener is None:
            return
        try:
            notifications = await listener.get_notifications_async(NotificationKinds.TOAST)
        except Exception as e:
            logging.error("Error clearing notifications: %s", e)
            return

        senders: list[str] = []
        for n in notifications:
            aumid = self._aumid_of(n)
            if aumid and aumid not in senders:
                senders.append(aumid)
            try:
                listener.remove_notification(n.id)
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
