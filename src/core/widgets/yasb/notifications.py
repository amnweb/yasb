import logging
import re

from PIL import Image
from PIL.ImageQt import ImageQt
from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QMouseEvent, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.events.service import EventService
from core.utils.qobject import is_valid_qobject
from core.utils.system import is_windows_10
from core.utils.time_utils import get_relative_time
from core.utils.tooltip import set_tooltip
from core.utils.utilities import ElidedLabel, PopupWidget, refresh_widget_style
from core.utils.win32.app_icons import get_icon_for_aumid
from core.utils.win32.aumid import activate_app_by_aumid
from core.utils.win32.system_function import notification_center, quick_settings
from core.validation.widgets.yasb.notifications import NotificationsConfig
from core.widgets.base import BaseWidget
from core.widgets.services.dnd.dnd_api import DndService
from core.widgets.services.media.aumid_process import get_process_name_for_aumid

try:
    from core.widgets.services.notifications.windows_notification import (
        NotificationItem,
        WindowsNotificationEventListener,
    )
except ImportError:
    NotificationItem = None
    WindowsNotificationEventListener = None
    logging.warning("Failed to load Windows Notification Event Listener")

APP_ICON_SIZE = 20
# Holds the global "Let apps access my notifications" switch
NOTIFICATION_PRIVACY_URI = "ms-settings:privacy-notifications"


class AppIconSignals(QObject):
    # aumid, device pixel ratio, PIL image or None
    loaded = pyqtSignal(str, float, object)


class AppIconLoader(QRunnable):
    """Extracts the icon of one sender away from the GUI thread.

    The shell hands these out over COM and takes between ten and a hundred milliseconds per
    app, which is long enough to be felt when a menu holding half a dozen senders is opened.
    Nothing here touches a widget: the finished image is handed back and turned into a
    pixmap by the thread that owns them.
    """

    def __init__(self, aumid: str, size: int, dpr: float):
        super().__init__()
        self._aumid = aumid
        self._size = size
        self._dpr = dpr
        self.signals = AppIconSignals()

    def run(self):
        image = None
        try:
            image = get_icon_for_aumid(self._aumid, size=self._size)
            if image is not None:
                # Squared off here rather than on the GUI thread, which then has nothing
                # left to do but wrap the pixels
                if image.mode != "RGBA":
                    image = image.convert("RGBA")
                if image.size != (self._size, self._size):
                    image = image.resize((self._size, self._size), Image.LANCZOS)
        except Exception:
            logging.exception("Failed to load app icon for %s", self._aumid)
            image = None
        self.signals.loaded.emit(self._aumid, self._dpr, image)


class NotificationsWidget(BaseWidget):
    validation_schema = NotificationsConfig
    windows_notification_update_signal = pyqtSignal(int)
    windows_notifications_changed_signal = pyqtSignal(list)
    windows_notification_access_signal = pyqtSignal(bool)
    dnd_status_changed_signal = pyqtSignal(str)
    event_listener = WindowsNotificationEventListener

    def __init__(self, config: NotificationsConfig):
        super().__init__(class_name=f"notification-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self._notification_count = 0
        self._notifications: list[NotificationItem] = []
        # Assume access until the listener reports otherwise, so the menu never flashes
        # a permission warning while the listener is still starting up
        self._access_allowed = True
        self._menu: PopupWidget | None = None
        self._scroll_area: QScrollArea | None = None
        self._header_label: QLabel | None = None
        self._dnd_button: QLabel | None = None
        self._icon_cache: dict[tuple[str, float], QPixmap | None] = {}
        self._icon_pending: set[tuple[str, float]] = set()
        # The icon slots of the menu as it stands, waiting for a loader to fill them in
        self._icon_labels: dict[tuple[str, float], list[QLabel]] = {}
        self._placeholders: dict[float, QPixmap] = {}
        self._icon_pool = QThreadPool()
        self._icon_pool.setMaxThreadCount(4)

        self._init_container()
        self.build_widget_label(self.config.label, self.config.label_alt)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("toggle_notification", self._toggle_notification)
        self.register_callback("clear_notifications", self._clear_notifications)

        # Register the WindowsNotificationUpdate event
        self.event_service = EventService()
        self.event_service.register_event("WindowsNotificationUpdate", self.windows_notification_update_signal)  # type: ignore
        self.event_service.register_event("WindowsNotificationsChanged", self.windows_notifications_changed_signal)  # type: ignore
        self.event_service.register_event("WindowsNotificationAccess", self.windows_notification_access_signal)  # type: ignore
        self.windows_notification_update_signal.connect(self._on_windows_notification_update)
        self.windows_notifications_changed_signal.connect(self._on_notifications_changed)
        self.windows_notification_access_signal.connect(self._on_access_changed)

        if self.config.menu.show_dnd_toggle:
            DndService.initialize_wnf_listener()
            self.event_service.register_event("dnd_status_changed", self.dnd_status_changed_signal)  # type: ignore
            self.dnd_status_changed_signal.connect(self._on_dnd_status_changed)

        self._update_label()

    def _on_windows_notification_update(self, total_notifications: int):
        self._notification_count = total_notifications
        if total_notifications > 0:
            self.setVisible(True)
        elif self.config.hide_empty:
            self.setVisible(False)
        self._update_label()

    def _on_notifications_changed(self, notifications: list[NotificationItem]):
        if self.config.menu.show_app_icons:
            self._warm_app_icons(notifications)
        # Opening the menu draws the list we already hold and asks the listener for a fresh
        # one at the same time. That reply is usually the same list, and rebuilding every
        # item to arrive at the same menu is the one thing that makes opening it feel slow
        changed = notifications != self._notifications
        self._notifications = notifications
        if changed and is_valid_qobject(self._menu) and self._menu.isVisible():
            self._populate_menu()

    def _on_access_changed(self, allowed: bool):
        self._access_allowed = allowed
        if is_valid_qobject(self._menu) and self._menu.isVisible():
            self._populate_menu()

    def _on_dnd_status_changed(self, status: str):
        if is_valid_qobject(self._menu) and self._menu.isVisible():
            self._update_dnd_button(status)

    def _toggle_notification(self):
        if is_windows_10():
            quick_settings()
        else:
            notification_center()

    def _toggle_label(self):
        self._show_alt_label = not self._show_alt_label
        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)
        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)
        self._update_label()

    def _clear_notifications(self):
        if WindowsNotificationEventListener:
            self.event_service.emit_event("WindowsNotificationClear", "clear_all_notifications")

    def _update_label(self):
        if self._notification_count == 0 and self.config.hide_empty:
            self.setVisible(False)
            return

        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self.config.label_alt if self._show_alt_label else self.config.label

        if self._notification_count > 0:
            icon = self.config.icons.new
        else:
            icon = self.config.icons.default

        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]
        widget_index = 0

        # Provide replacements for {count} and {icon}
        label_options = [("{count}", self._count_text()), ("{icon}", icon)]

        for part in label_parts:
            part = part.strip()
            for option, value in label_options:
                part = part.replace(option, str(value))

            if part and widget_index < len(active_widgets) and isinstance(active_widgets[widget_index], QLabel):
                if "<span" in part and "</span>" in part:
                    icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                    active_widgets[widget_index].setText(icon)
                else:
                    active_widgets[widget_index].setText(part)

                if self.config.tooltip:
                    set_tooltip(active_widgets[widget_index], f"Notifications {self._notification_count}")

                # Update class based on notification count
                current_class = active_widgets[widget_index].property("class")
                if self._notification_count > 0:
                    if "new-notification" not in current_class:
                        current_class += " new-notification"
                else:
                    current_class = current_class.replace(" new-notification", "")

                active_widgets[widget_index].setProperty("class", current_class.strip())

                widget_index += 1
        for widget in active_widgets:
            refresh_widget_style(widget)

    def _count_text(self) -> str:
        """The count as it goes on the bar, capped when a cap was asked for.

        The number on the bar and the list in the menu come from two different places and
        stop agreeing once an app has sent more notifications than Windows keeps for it. A
        cap keeps the bar from advertising a number the menu cannot account for.
        """
        max_count = self.config.max_count
        if max_count and self._notification_count > max_count:
            return f"{max_count}+"
        return str(self._notification_count)

    def _toggle_menu(self):
        if is_valid_qobject(self._menu) and self._menu.isVisible():
            self._menu.hide_animated()
            return
        self._show_menu()

    def _show_menu(self):
        menu = self.config.menu
        self._menu = PopupWidget(
            self,
            menu.blur,
            menu.round_corners,
            menu.round_corners_type,
            menu.border_color,
        )
        self._menu.setProperty("class", "notification-menu")
        self._menu.setFixedWidth(menu.width)

        main_layout = QVBoxLayout(self._menu)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_header())

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # A scroll area paints its own viewport with the palette background, which no
        # stylesheet rule on the QScrollArea itself reaches. Left alone it puts an opaque
        # slab between the popup and the list, so a menu styled to be see-through is not
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.viewport().setAutoFillBackground(False)
        self._scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; border-radius:0; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
        """)
        main_layout.addWidget(self._scroll_area)

        if menu.show_notification_center:
            main_layout.addWidget(self._build_footer())

        self._populate_menu()
        self._menu.show()

        # Ask the listener for a fresh list; the reply repopulates the menu in place
        if WindowsNotificationEventListener:
            self.event_service.emit_event("WindowsNotificationRefresh", "refresh_notifications")

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setProperty("class", "header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        self._header_label = QLabel("Notifications")
        self._header_label.setProperty("class", "label")
        header_layout.addWidget(self._header_label)
        header_layout.addStretch()

        self._dnd_button = None
        dnd_status = DndService.get_status() if self.config.menu.show_dnd_toggle else "unknown"
        if dnd_status != "unknown":
            self._dnd_button = QLabel()
            self._dnd_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._dnd_button.mousePressEvent = lambda _event: self._toggle_dnd()
            self._update_dnd_button(dnd_status)
            header_layout.addWidget(self._dnd_button)

        clear_all_label = QLabel("Clear all")
        clear_all_label.setProperty("class", "label clear-all")
        clear_all_label.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_all_label.mousePressEvent = lambda _event: self._clear_notifications()
        header_layout.addWidget(clear_all_label)

        return header

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setProperty("class", "footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(0)

        open_center_label = QLabel("Open Notification Center")
        open_center_label.setProperty("class", "label")
        open_center_label.setCursor(Qt.CursorShape.PointingHandCursor)
        open_center_label.mousePressEvent = lambda _event: self._open_notification_center()
        footer_layout.addWidget(open_center_label)
        footer_layout.addStretch()

        return footer

    def _open_notification_center(self):
        self._menu.hide_animated()
        self._toggle_notification()

    def _toggle_dnd(self):
        next_status = "priority" if DndService.get_status() == "disabled" else "disabled"
        DndService.set_status(next_status)
        self._update_dnd_button(next_status)

    def _update_dnd_button(self, status: str):
        if not is_valid_qobject(self._dnd_button):
            return
        enabled = status not in ("disabled", "unknown")
        icons = self.config.icons
        self._dnd_button.setText(icons.dnd_on if enabled else icons.dnd_off)
        self._dnd_button.setProperty("class", "dnd-button active" if enabled else "dnd-button")
        if self.config.tooltip:
            set_tooltip(self._dnd_button, "Turn off Do Not Disturb" if enabled else "Turn on Do Not Disturb")
        refresh_widget_style(self._dnd_button)

    def _populate_menu(self):
        """Rebuild the scroll area contents from the cached notification list."""
        # The list is thrown away and built again from scratch, so none of the intermediate
        # states are worth painting
        self._menu.setUpdatesEnabled(False)
        try:
            self._rebuild_contents()
        finally:
            self._menu.setUpdatesEnabled(True)

    def _rebuild_contents(self):
        notifications = self._notifications[: self.config.menu.max_notifications]
        # The slots of the menu being replaced go with it, so a loader that finishes late
        # has nothing left to fill in
        self._icon_labels.clear()

        content = QWidget()
        content.setProperty("class", "contents")
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        if not notifications:
            content_layout.addLayout(self._build_empty_state())
        elif self.config.menu.group_by_app:
            grouped: dict[str, list[NotificationItem]] = {}
            for notification in notifications:
                grouped.setdefault(notification.app_name, []).append(notification)
            # Senders that expose no app info have no name to head them with, so they are
            # collected under a generic header and moved last instead of trailing a real app
            unnamed = grouped.pop("", None)
            if unnamed:
                grouped[""] = unnamed
            for app_name, items in grouped.items():
                section_header = QLabel(app_name or "Other")
                section_header.setProperty("class", "section-header" if app_name else "section-header other")
                section_header.setTextFormat(Qt.TextFormat.PlainText)
                content_layout.addWidget(section_header)
                content_layout.addWidget(self._build_section(items, show_app_name=False))
        else:
            content_layout.addWidget(self._build_section(notifications, show_app_name=True))

        self._header_label.setText(
            f"Notifications ({len(self._notifications)})" if self._notifications else "Notifications"
        )
        # Replacing the widget deletes the previous one along with all of its items
        self._scroll_area.setWidget(content)
        # setWidget turns this back on, so it has to be cleared afterwards or the list is
        # drawn on an opaque background whatever the stylesheet says
        content.setAutoFillBackground(False)
        # Size the list explicitly: QScrollArea does not shrink back on its own once shown
        content.ensurePolished()
        self._scroll_area.setFixedHeight(min(content.sizeHint().height(), self.config.menu.max_height))

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )

    def _build_empty_state(self) -> QVBoxLayout:
        icon_label = QLabel(self.config.icons.default)
        icon_label.setProperty("class", "empty-icon")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        center_layout = QVBoxLayout()
        center_layout.addStretch()
        center_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        if not WindowsNotificationEventListener:
            text = "Notification listener unavailable"
        elif not self._access_allowed:
            text = "Notification access is turned off"
        else:
            text = "No new notifications"

        no_data = QLabel(text)
        no_data.setProperty("class", "empty-text")
        no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(no_data, alignment=Qt.AlignmentFlag.AlignCenter)

        # Windows grants this permission globally, so point at the page that holds the switch
        if WindowsNotificationEventListener and not self._access_allowed:
            action = QLabel("Open notification settings")
            action.setProperty("class", "empty-action")
            action.setAlignment(Qt.AlignmentFlag.AlignCenter)
            action.setCursor(Qt.CursorShape.PointingHandCursor)
            action.mousePressEvent = lambda _event: self._open_privacy_settings()
            center_layout.addWidget(action, alignment=Qt.AlignmentFlag.AlignCenter)

        center_layout.addStretch()
        return center_layout

    def _open_privacy_settings(self):
        self._menu.hide_animated()
        QDesktopServices.openUrl(QUrl(NOTIFICATION_PRIVACY_URI))

    def _build_section(self, notifications: list[NotificationItem], show_app_name: bool) -> QFrame:
        section = QFrame()
        section.setProperty("class", "section")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(0)

        last_index = len(notifications) - 1
        for index, notification in enumerate(notifications):
            position_classes: list[str] = []
            if index == 0:
                position_classes.append("first")
            if index == last_index:
                position_classes.append("last")
            section_layout.addWidget(
                self._build_notification_item(notification, position_classes, show_app_name, parent=section)
            )

        return section

    def _build_notification_item(
        self,
        notification: NotificationItem,
        position_classes: list[str],
        show_app_name: bool,
        parent: QWidget | None = None,
    ) -> QFrame:
        container = QFrame(parent)
        container.setProperty("class", " ".join(["item", *position_classes]))
        container.setContentsMargins(0, 0, 0, 0)
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        if self.config.menu.show_app_icons:
            icon_label = self._build_icon_label(notification.aumid)
            if icon_label is not None:
                container_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        title_label = ElidedLabel(notification.title or "(no content)")
        title_label.setTextFormat(Qt.TextFormat.PlainText)
        title_label.setProperty("class", "title")
        title_label.setContentsMargins(0, 0, 0, 0)

        text_content = QWidget()
        text_content_layout = QVBoxLayout(text_content)
        # No layout alignment here: it would size the elided labels to their (ignored) size hint
        text_content_layout.setContentsMargins(0, 0, 0, 0)
        text_content_layout.setSpacing(0)
        text_content_layout.addWidget(title_label)

        if notification.body:
            body_label = ElidedLabel(notification.body.replace("\n", " "))
            body_label.setTextFormat(Qt.TextFormat.PlainText)
            body_label.setProperty("class", "body")
            body_label.setContentsMargins(0, 0, 0, 0)
            text_content_layout.addWidget(body_label)

        description = self._build_description(notification, show_app_name)
        if description:
            description_label = ElidedLabel(description)
            description_label.setTextFormat(Qt.TextFormat.PlainText)
            description_label.setProperty("class", "description")
            description_label.setContentsMargins(0, 0, 0, 0)
            text_content_layout.addWidget(description_label)

        container_layout.addWidget(text_content, 1)

        dismiss_label = QLabel(self.config.icons.dismiss)
        dismiss_label.setProperty("class", "dismiss")
        dismiss_label.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dismiss_label.mousePressEvent = self._create_dismiss_event(notification.id)
        container_layout.addWidget(dismiss_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        container.mousePressEvent = self._create_activate_event(notification)
        return container

    @staticmethod
    def _build_description(notification: NotificationItem, show_app_name: bool) -> str:
        parts: list[str] = []
        if show_app_name and notification.app_name:
            parts.append(notification.app_name)
        relative_time = get_relative_time(notification.created_at)
        if relative_time:
            parts.append(relative_time)
        return " • ".join(parts)

    def _remove_notification(self, notification_id: int):
        self.event_service.emit_event("WindowsNotificationRemove", notification_id)

    def _create_dismiss_event(self, notification_id: int):
        def mouse_press_event(a0: QMouseEvent | None) -> None:
            if a0 is not None:
                # Keep the click from bubbling up to the item and activating the app
                a0.accept()
            self._remove_notification(notification_id)

        return mouse_press_event

    def _create_activate_event(self, notification: NotificationItem):
        """Bring the sending app to the front. Removing the notification is the dismiss button's job."""

        def mouse_press_event(_a0: QMouseEvent | None) -> None:
            if notification.aumid:
                activate_app_by_aumid(
                    notification.aumid,
                    fallback_process_name=get_process_name_for_aumid(notification.aumid),
                )

        return mouse_press_event

    def _build_icon_label(self, aumid: str) -> QLabel | None:
        """The icon slot of an item, or None when the sender has no icon to draw.

        An icon that has not been extracted yet gets a transparent stand-in the same size,
        so the row is laid out once and the picture drops into it when the loader is done
        rather than pushing the text along.
        """
        if not aumid:
            return None
        dpr = self._device_pixel_ratio()
        cache_key = (aumid, dpr)
        known = cache_key in self._icon_cache
        pixmap = self._icon_cache.get(cache_key)
        if known and pixmap is None:
            return None

        icon_label = QLabel()
        icon_label.setProperty("class", "icon")
        # No fixed size: it would fight the stylesheet box model and clip the pixmap
        icon_label.setPixmap(pixmap if known else self._placeholder_pixmap(dpr))
        if not known:
            self._icon_labels.setdefault(cache_key, []).append(icon_label)
            self._request_app_icon(aumid, dpr)
        return icon_label

    def _warm_app_icons(self, notifications: list[NotificationItem]):
        """Start on the icons of senders we have not seen, before anybody opens the menu.

        The list is normally known well before it is looked at, and extracting an icon is
        slow enough that doing it on the click is what makes opening the menu feel slow.
        """
        dpr = self._device_pixel_ratio()
        for aumid in {notification.aumid for notification in notifications if notification.aumid}:
            self._request_app_icon(aumid, dpr)

    def _request_app_icon(self, aumid: str, dpr: float):
        cache_key = (aumid, dpr)
        if cache_key in self._icon_cache or cache_key in self._icon_pending:
            return
        self._icon_pending.add(cache_key)
        loader = AppIconLoader(aumid, self._icon_pixels(dpr), dpr)
        loader.signals.loaded.connect(self._on_app_icon_loaded)
        self._icon_pool.start(loader)

    def _on_app_icon_loaded(self, aumid: str, dpr: float, image: object):
        cache_key = (aumid, dpr)
        self._icon_pending.discard(cache_key)
        pixmap = self._to_pixmap(image, dpr) if image is not None else None
        self._icon_cache[cache_key] = pixmap

        for icon_label in self._icon_labels.pop(cache_key, []):
            if not is_valid_qobject(icon_label):
                continue
            if pixmap is None:
                # There is nothing to draw for this sender, so the slot goes away and the
                # item reads the way every later rebuild will draw it, without one
                icon_label.hide()
            else:
                icon_label.setPixmap(pixmap)

    @staticmethod
    def _to_pixmap(image: Image.Image, dpr: float) -> QPixmap | None:
        try:
            # Copy to avoid a dangling view into the PIL buffer
            pixmap = QPixmap.fromImage(ImageQt(image).copy())
            pixmap.setDevicePixelRatio(dpr)
            return pixmap
        except Exception:
            logging.exception("Failed to read an app icon")
            return None

    def _placeholder_pixmap(self, dpr: float) -> QPixmap:
        """A transparent pixmap the size of an app icon, holding the space until one lands."""
        pixmap = self._placeholders.get(dpr)
        if pixmap is None:
            size = self._icon_pixels(dpr)
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            pixmap.setDevicePixelRatio(dpr)
            self._placeholders[dpr] = pixmap
        return pixmap

    @staticmethod
    def _icon_pixels(dpr: float) -> int:
        """The icon edge in device pixels.

        A stylesheet cannot resize this: Qt draws a label's pixmap at the size it was made
        at, so the size has to be known before the pixmap is built.
        """
        return max(1, int(round(APP_ICON_SIZE * dpr)))

    def _device_pixel_ratio(self) -> float:
        screen = self._menu.screen() if is_valid_qobject(self._menu) else self.screen()
        return float(screen.devicePixelRatio()) if screen is not None else 1.0
