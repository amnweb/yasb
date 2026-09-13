"""
TaskbarNotificationMonitor
--------------------------
Polls the Windows Notification Center via WinRT UserNotificationListener and
emits a per-app unread count dictionary every time the counts change.

This is used by TaskbarWidget to drive the per-button notification badge when
`badge.enabled = true` in config.yaml.

Why WinRT instead of ITaskbarList3?
  ITaskbarList3::SetOverlayIcon is write-only — no public Windows API lets a
  third-party process read back another app's overlay icon or badge count.
  The Windows Notification Center (Action Center) DOES expose per-app counts
  via UserNotificationListener and is the practical source of truth for
  unread notifications (used by WhatsApp, Discord, Slack, Outlook, Teams, …).

Access requirement:
  Windows → Settings → System → Notifications
  → "Allow apps to access notifications" must be ON.
  On first run the user may be prompted to grant access.
"""

import asyncio
import logging

import winrt.windows.ui.notifications.management as management
from PyQt6.QtCore import QThread, pyqtSignal


class TaskbarNotificationMonitor(QThread):
    """Background thread that polls Windows notification counts per app.

    Emits `counts_updated` with a ``dict[str, int]`` of
    ``{app_display_name_lower: unread_count}`` whenever the snapshot changes.
    """

    counts_updated = pyqtSignal(dict)

    # Toast = 1, Tile = 2, Badge = 4, Raw = 8
    _KINDS = 1 | 4  # Toast + Badge

    def __init__(self, poll_interval: float = 2.0):
        super().__init__()
        self._running = True
        self._poll_interval = poll_interval
        self._loop = asyncio.new_event_loop()

    # ------------------------------------------------------------------
    # Private async helpers
    # ------------------------------------------------------------------

    async def _poll(self) -> None:
        try:
            listener = management.UserNotificationListener.current
            access_result = await listener.request_access_async()

            if access_result != management.UserNotificationListenerAccessStatus.ALLOWED:
                logging.warning(
                    "TaskbarNotificationMonitor: Windows notification access denied. "
                    "Enable 'Allow apps to access notifications' in Windows Settings → System → Notifications."
                )
                return

            last_counts: dict[str, int] = {}

            while self._running:
                try:
                    counts = await self._snapshot(listener)
                    if counts != last_counts:
                        last_counts = counts
                        self.counts_updated.emit(dict(counts))
                except Exception as exc:
                    logging.debug("TaskbarNotificationMonitor poll error: %s", exc)

                await asyncio.sleep(self._poll_interval)

        except Exception as exc:
            logging.warning("TaskbarNotificationMonitor stopped: %s", exc)

    async def _snapshot(self, listener) -> dict[str, int]:
        """Return ``{app_name_lower: count}`` for all current notifications."""
        counts: dict[str, int] = {}
        try:
            notifications = await listener.get_notifications_async(self._KINDS)
            for notif in notifications:
                try:
                    name = notif.app_info.display_info.display_name.strip().lower()
                    if name:
                        counts[name] = counts.get(name, 0) + 1
                except Exception:
                    pass
        except Exception as exc:
            logging.debug("TaskbarNotificationMonitor snapshot error: %s", exc)
        return counts

    # ------------------------------------------------------------------
    # QThread interface
    # ------------------------------------------------------------------

    def run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._poll())
        except Exception as exc:
            logging.error("TaskbarNotificationMonitor thread error: %s", exc)
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            self._loop.close()

    def stop(self) -> None:
        self._running = False
        try:
            if self._loop and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception as exc:
            logging.debug("TaskbarNotificationMonitor stop error: %s", exc)
