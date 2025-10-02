import asyncio
import logging
from enum import IntFlag

import winrt.windows.ui.notifications.management as management
from PyQt6.QtCore import QThread, pyqtSignal

from core.event_service import EventService


class NotificationKinds(IntFlag):
    """
    Enum for notification kinds (toast, tile, badge, proto)
    """

    toast = 1
    tile = 2
    badge = 4
    proto = 8


def get_all_kinds():
    """
    Get all notification kinds, including toast, tile, badge, and proto.
    In the future, this function can be modified to return a different set of notification kinds.
    """
    return NotificationKinds.toast | NotificationKinds.tile | NotificationKinds.badge | NotificationKinds.proto


class WindowsNotificationEventListener(QThread):
    clear_notifications = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.total_notifications = 0
        self.event_service = EventService()
        self.loop = asyncio.new_event_loop()

        self.clear_notifications.connect(self._clear_notifications)
        self.event_service.register_event("WindowsNotificationClear", self.clear_notifications)

    def _clear_notifications(self):
        asyncio.run_coroutine_threadsafe(self.clear_all_notifications(), self.loop)

    async def update_count(self, listener):
        try:
            notifications = await listener.get_notifications_async(get_all_kinds())
            return len(notifications)
        except Exception as e:
            logging.error(f"Error updating notification count: {e}")
            return None

    async def watch_notifications(self):
        try:
            listener = management.UserNotificationListener.current
            access_result = await listener.request_access_async()

            if access_result == management.UserNotificationListenerAccessStatus.ALLOWED:
                while self.running:
                    current_count = await self.update_count(listener)
                    if current_count is not None and current_count != self.total_notifications:
                        self.total_notifications = current_count
                        self.event_service.emit_event("WindowsNotificationUpdate", self.total_notifications)

                    await asyncio.sleep(2)
            else:
                logging.warning(f"Access denied to notifications, access status: {access_result}")
        except Exception as e:
            logging.error(f"Error in notification listener: {e}")
            await asyncio.sleep(10)

    async def clear_all_notifications(self):
        """
        Clear all notifications from the notification center.
        """
        try:
            listener = management.UserNotificationListener.current
            notifications = await listener.get_notifications_async(get_all_kinds())
            for n in notifications:
                # Call without await since it might not be an async method
                listener.remove_notification(n.id)
            self.total_notifications = 0
            self.event_service.emit_event("WindowsNotificationUpdate", self.total_notifications)
        except Exception as e:
            logging.error(f"Error clearing notifications: {e}")

    def run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.watch_notifications())
        except Exception as e:
            logging.error(f"Error in notification listener thread: {e}")
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.close()

    def stop(self):
        self.running = False
        try:
            if self.loop and self.loop.is_running():
                self.loop.call_soon_threadsafe(lambda: None)
        except Exception:
            pass
