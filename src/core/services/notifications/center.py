from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QCoreApplication, QObject, QTimer, QUrl, pyqtSignal, pyqtSlot

from core.events.service import EventService
from core.services.dnd.dnd_api import DndService
from core.utils.icons.image_provider import icon_url
from core.utils.icons.service import IconService
from core.utils.icons.sources import AppIcon
from core.utils.qml import qml_property
from core.utils.system import is_windows_10
from core.utils.win32.system_function import notification_center, quick_settings

if TYPE_CHECKING:
    from core.services.notifications.windows_notification import (
        NotificationItem,
        WindowsNotificationEventListener,
    )

_listener: WindowsNotificationEventListener | None = None


def _start_listener() -> WindowsNotificationEventListener:
    """The one listener every widget shares, stopped when YASB quits."""
    global _listener
    if _listener is None:
        # WinRT's notification modules load only once a widget uses them
        from core.services.notifications.windows_notification import WindowsNotificationEventListener

        listener = WindowsNotificationEventListener()
        listener.start()

        def stop() -> None:
            listener.stop()
            listener.wait(2000)

        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(stop)
        _listener = listener
    return _listener


def _file_url(path: str) -> str:
    return QUrl.fromLocalFile(path).toString() if path else ""


class NotificationCenter(QObject):
    """The notifications Windows keeps in its notification center, and its do not disturb."""

    countChanged = pyqtSignal()
    notificationsChanged = pyqtSignal()
    doNotDisturbChanged = pyqtSignal()
    # From EventService, which the listener and Windows' callbacks emit on their own threads
    _count_event = pyqtSignal(int)
    _list_event = pyqtSignal(object)
    _dnd_event = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._listener = _start_listener()
        self._count = self._listener.total_notifications
        self._items: list[NotificationItem] = []
        self._entries: list[dict[str, Any]] = []
        self._allowed = True
        self._dnd_status = "unknown"
        self._events = EventService()
        subscriptions = (
            ("WindowsNotificationUpdate", self._count_event, self._on_count),
            ("WindowsNotificationsChanged", self._list_event, self._on_list),
            ("dnd_status_changed", self._dnd_event, self._on_dnd),
        )
        for event, signal, slot in subscriptions:
            signal.connect(slot)
            self._events.register_event(event, signal)
        events = self._events

        def unsubscribe(*_: object) -> None:
            for event, signal, _slot in subscriptions:
                events.unregister_event(event, signal)

        self.destroyed.connect(unsubscribe)
        IconService.instance().icons_changed.connect(self._on_icons_changed)
        DndService.initialize_wnf_listener()
        # Reading do not disturb asks another process, so it waits until the bar is up
        self._dnd_timer = QTimer(self)
        self._dnd_timer.setSingleShot(True)
        self._dnd_timer.setInterval(0)
        self._dnd_timer.timeout.connect(lambda: self._on_dnd(DndService.get_status()))
        self._dnd_timer.start()
        self.refresh()

    # What Windows counts in its notification center, which can include toasts the list can't read
    @qml_property(int, notify=countChanged)
    def count(self) -> int:
        return self._count

    # Newest first: [{id, appId, appName, title, body, attribution, time, icon, logo, logoCircle, hero, image}],
    # time in ms since 1970 and images as file URLs, "" when there's none
    @qml_property("QVariantList", notify=notificationsChanged)
    def notifications(self) -> list[dict[str, Any]]:
        return self._entries

    # False when notification access is turned off in Windows' privacy settings
    @qml_property(bool, notify=notificationsChanged)
    def allowed(self) -> bool:
        return self._allowed

    @qml_property(bool, notify=doNotDisturbChanged)
    def doNotDisturbAvailable(self) -> bool:
        return self._dnd_status != "unknown"

    @qml_property(bool, notify=doNotDisturbChanged)
    def doNotDisturb(self) -> bool:
        return self._dnd_status not in ("disabled", "unknown")

    @pyqtSlot(int)
    def _on_count(self, count: int) -> None:
        self._count = count
        self.countChanged.emit()

    @pyqtSlot(object)
    def _on_list(self, items: list[NotificationItem] | None) -> None:
        self._allowed = items is not None
        self._items = items or []
        self._entries = [self._entry(item) for item in self._items]
        self.notificationsChanged.emit()

    @pyqtSlot(str)
    def _on_dnd(self, status: str) -> None:
        if status != self._dnd_status:
            self._dnd_status = status
            self.doNotDisturbChanged.emit()

    def _on_icons_changed(self) -> None:
        # The provider answered with a blank icon while it loaded, so the new revision makes QML ask again
        if any(item.aumid for item in self._items):
            self._entries = [self._entry(item) for item in self._items]
            self.notificationsChanged.emit()

    def _entry(self, item: NotificationItem) -> dict[str, Any]:
        return {
            "id": item.id,
            "appId": item.aumid,
            "appName": item.app_name,
            "title": item.title,
            "body": item.body,
            "attribution": item.attribution,
            "time": item.created_at.timestamp() * 1000,
            "icon": icon_url(AppIcon(item.aumid), IconService.instance().revision) if item.aumid else "",
            "logo": _file_url(item.logo),
            "logoCircle": item.logo_circle,
            "hero": _file_url(item.hero),
            "image": _file_url(item.image),
        }

    @pyqtSlot()
    def refresh(self) -> None:
        self._events.emit_event("WindowsNotificationRefresh", "")

    @pyqtSlot()
    def clearAll(self) -> None:
        self._events.emit_event("WindowsNotificationClear", "")

    @pyqtSlot(str)
    def clearApp(self, app_id: str) -> None:
        self._events.emit_event("WindowsNotificationClearApp", app_id)

    # Notification ids are unsigned 32-bit, past what QML's int holds
    @pyqtSlot("qint64")
    def dismiss(self, notification_id: int) -> None:
        self._events.emit_event("WindowsNotificationRemove", notification_id)

    @pyqtSlot("qint64")
    def activate(self, notification_id: int) -> None:
        item = next((item for item in self._items if item.id == notification_id), None)
        if item is not None:
            self._events.emit_event("WindowsNotificationActivate", item)

    @pyqtSlot(bool)
    def setDoNotDisturb(self, enabled: bool) -> None:
        status = "priority" if enabled else "disabled"
        DndService.set_status(status)
        self._on_dnd(status)

    @pyqtSlot()
    def openNotificationCenter(self) -> None:
        if is_windows_10():
            quick_settings()
        else:
            notification_center()
