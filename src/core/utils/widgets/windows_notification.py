import asyncio
import logging
from enum import IntFlag
from winsdk.windows.ui.notifications import management
from PyQt6.QtCore import QThread
from core.event_service import EventService
from settings import DEBUG

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
    def __init__(self):
        super().__init__()
        self.running = True
        self.previous_count = 0
        self.total_notifications = 0
        self.event_service = EventService()
        self.loop = asyncio.new_event_loop()

    async def update_count(self, sender):
        try:
            notifications = await sender.get_notifications_async(get_all_kinds())
            return len(notifications)
        except Exception as e:
            if DEBUG:
                logging.error(f"Error updating notification count: {e}")
            return None
            
    async def watch_notifications(self):
        try:
            listener = management.UserNotificationListener.current
            access_result = await listener.request_access_async()
            
            if access_result == management.UserNotificationListenerAccessStatus.ALLOWED:
                while self.running:
                    current_count = await self.update_count(listener)
                    if current_count is not None and current_count != self.previous_count:
                        if current_count > self.previous_count:
                            added = current_count - self.previous_count
                            self.total_notifications += added
                        elif current_count == 0:
                            self.total_notifications = 0
                        
                        self.previous_count = current_count
                        self.event_service.emit_event("WindowsNotificationUpdate", self.total_notifications)
                    
                    await asyncio.sleep(2)
            else:
                if DEBUG:
                    logging.warning(f"Access denied to notifications, access status: {access_result}")
        except Exception as e:
            logging.error(f"Error: {e}")
            await asyncio.sleep(10) # Wait for 5 seconds before retrying if an error occurs

    def run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.watch_notifications())
        except Exception as e:
            logging.error(f"Error in notification listener: {e}")
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.close()

    def stop(self):
        self.running = False
        if self.loop and self.loop.is_running():
            self.loop.stop()
            self.loop.close()
        self.wait()