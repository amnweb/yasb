import asyncio
import logging
import threading

import winrt.windows.ui.notifications.management as management
from PyQt6.QtCore import QThread, pyqtSignal
from winrt.windows.ui.notifications import NotificationKinds

from core.event_service import EventService


class WindowsNotificationEventListener(QThread):
    clear_notifications = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.total_notifications = 0
        self.event_service = EventService()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event = threading.Event()

        self.clear_notifications.connect(self._clear_notifications)
        self.event_service.register_event("WindowsNotificationClear", self.clear_notifications)

    def _clear_notifications(self, _msg: str = ""):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._do_clear_all_notifications(), self._loop)

    async def _get_notification_count(self, listener) -> int | None:
        try:
            notifications = await listener.get_notifications_async(NotificationKinds.TOAST)
            return len(notifications)
        except Exception as e:
            logging.error(f"Error getting notification count: {e}")
            return None

    async def _do_clear_all_notifications(self):
        try:
            listener = management.UserNotificationListener.current
            notifications = await listener.get_notifications_async(NotificationKinds.TOAST)
            for n in notifications:
                try:
                    listener.remove_notification(n.id)
                except Exception as e:
                    logging.debug(f"Failed to remove notification {n.id}: {e}")
            self.total_notifications = 0
            self.event_service.emit_event("WindowsNotificationUpdate", self.total_notifications)
        except Exception as e:
            logging.error(f"Error clearing notifications: {e}")

    async def _wait_for_stop(self, timeout: float) -> bool:
        """Non-blocking wait that keeps the event loop responsive.
        Returns True if stop was requested, False on timeout."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._stop_event.wait, timeout)

    async def _watch_notifications(self, listener):
        retry_delay = 2

        while not self._stop_event.is_set():
            try:
                # Use sync check — cheaper than request_access_async on every iteration
                access_status = listener.get_access_status()

                if access_status != management.UserNotificationListenerAccessStatus.ALLOWED:
                    logging.warning(f"Access denied to notifications, access status: {access_status}")
                    if await self._wait_for_stop(30):
                        break
                    continue

                # Polling loop
                while not self._stop_event.is_set():
                    current_count = await self._get_notification_count(listener)
                    if current_count is not None and current_count != self.total_notifications:
                        self.total_notifications = current_count
                        self.event_service.emit_event("WindowsNotificationUpdate", self.total_notifications)

                    if await self._wait_for_stop(2):
                        break

            except Exception as e:
                logging.error(f"Error in notification listener: {e}")
                if await self._wait_for_stop(retry_delay):
                    break
                retry_delay = min(retry_delay * 2, 60)

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        listener = management.UserNotificationListener.current
        try:
            self._loop.run_until_complete(listener.request_access_async())
        except Exception as e:
            logging.error(f"Failed to request notification access: {e}")
            self._loop.close()
            self._loop = None
            return

        try:
            self._loop.run_until_complete(self._watch_notifications(listener))
        except Exception as e:
            logging.error(f"Error in notification listener thread: {e}")
        finally:
            self._loop.run_until_complete(self._cancel_pending_tasks())
            self._loop.close()
            self._loop = None

    async def _cancel_pending_tasks(self):
        pending = asyncio.all_tasks()
        pending.discard(asyncio.current_task())
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def stop(self):
        self._stop_event.set()
