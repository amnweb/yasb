import asyncio
import ctypes
import logging
from ctypes import POINTER, byref, c_void_p

import winrt.windows.ui.notifications.management as management
from PyQt6.QtCore import QThread, pyqtSignal
from winrt.windows.ui.notifications import NotificationKinds

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


class WindowsNotificationEventListener(QThread):
    clear_notifications = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.total_notifications = 0
        self.event_service = EventService()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._async_stop_event: asyncio.Event | None = None
        self._stopped = False
        self._listener = None
        self._wnf_sub = None
        self._wnf_active = False
        self._wnf_cb = WnfCallbackType(self._wnf_toast_callback)

        self.clear_notifications.connect(self._clear_notifications)
        self.event_service.register_event("WindowsNotificationClear", self.clear_notifications)

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
        self.event_service.unregister_event("WindowsNotificationClear", self.clear_notifications)
        try:
            self.clear_notifications.disconnect(self._clear_notifications)
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
        except Exception:
            logging.exception("Error in WNF callback")
        return 0

    def _clear_notifications(self, _msg: str = ""):
        if self._loop and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._do_clear_all_notifications(), self._loop)
            except RuntimeError as e:
                logging.debug("Failed to schedule clear notifications: %s", e)

    async def _do_clear_all_notifications(self):
        try:
            notifications = await self._listener.get_notifications_async(NotificationKinds.TOAST)
            for n in notifications:
                try:
                    self._listener.remove_notification(n.id)
                except Exception as e:
                    logging.debug("Failed to remove notification %s: %s", n.id, e)
            self.total_notifications = 0
            self.event_service.emit_event("WindowsNotificationUpdate", 0)
        except Exception as e:
            logging.error("Error clearing notifications: %s", e)
