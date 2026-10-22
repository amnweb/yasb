import logging
import re
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, override

from PIL import Image, ImageDraw, ImageOps
from PIL.ImageQt import ImageQt
from PyQt6.QtCore import QObject, QPointF, QRunnable, QSizeF, Qt, QThreadPool, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QMouseEvent, QPainter, QPaintEvent, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.events.service import EventService
from core.utils.icons.service import IconService
from core.utils.icons.sources import AppIcon
from core.utils.qobject import is_valid_qobject
from core.utils.system import is_windows_10
from core.utils.time_utils import get_relative_time
from core.utils.tooltip import set_tooltip
from core.utils.utilities import ElidedLabel, PopupWidget, refresh_widget_style
from core.utils.win32.aumid import activate_app_by_aumid
from core.utils.win32.aumid_process import get_process_name_for_aumid
from core.utils.win32.system_function import notification_center, quick_settings
from core.utils.win32.toast_activation import activate_toast
from core.validation.widgets.yasb.notifications import NotificationsConfig
from core.widgets.base import BaseWidget
from core.widgets.services.dnd.dnd_api import DndService

if TYPE_CHECKING:
    from core.widgets.services.notifications.windows_notification import NotificationItem

try:
    from core.widgets.services.notifications.windows_notification import WindowsNotificationEventListener
except ImportError:
    WindowsNotificationEventListener = None
    logging.warning("Failed to load Windows Notification Event Listener")

# Room for the margin, border and padding the stylesheet puts around an item, so a full
# width image does not push the list wider than the menu
IMAGE_MARGIN = 32
# Toast images are keyed by a path that changes with every notification, unlike the app
# icons keyed by AUMID, so this cache needs a lid on it. Large enough to hold a full menu
IMAGE_CACHE_SIZE = 128
# Holds the global "Let apps access my notifications" switch
NOTIFICATION_PRIVACY_URI = "ms-settings:privacy-notifications"
# Between a section's icon and the name beside it
SECTION_ICON_GAP = 6
# Decodes one toast image, on whichever thread it is handed to
type ImageDecoder = Callable[[], Image.Image | None]
# (path, width, height, circle, dpr) of a decoded toast image
type ImageKey = tuple[str, int, int, bool, float]
# A key and what decodes the image it names
type ImageJob = tuple[ImageKey, ImageDecoder]


class SectionHeaderLabel(QLabel):
    """A section header with the icon of the sender drawn in front of its name.

    One label rather than an icon and a label side by side, because a stylesheet reaches a
    widget and not its children: split in two, the font and the colour written for the
    header would stop reaching the name. So the text is indented to leave room and the icon
    is drawn into the gap. Qt's own inline images are no use for this: where one lands
    depends on how tall it is, so an icon that sits right at one size sits low at the next.
    """

    def __init__(self, text: str, icon: QPixmap, parent: QWidget | None = None):
        super().__init__(text, parent)
        self._icon = icon
        self.setIndent(round(self._icon_size().width()) + SECTION_ICON_GAP)

    def _icon_size(self) -> QSizeF:
        """The icon in the pixels the label is laid out in, not the ones it was drawn at."""
        ratio = self._icon.devicePixelRatio() or 1.0
        return QSizeF(self._icon.width() / ratio, self._icon.height() / ratio)

    @override
    def paintEvent(self, a0: QPaintEvent | None) -> None:
        super().paintEvent(a0)
        size = self._icon_size()
        contents = self.contentsRect()
        # Centred in the box the label centres its line in, so the two share an axis. Not
        # worked out from the baseline and the x-height instead: that is where an inline
        # image belongs by the book, but it reads as sitting low, and it puts the icon at
        # the mercy of metrics a font is free to be wrong about
        top = contents.top() + (contents.height() - size.height()) / 2
        painter = QPainter(self)
        try:
            painter.drawPixmap(QPointF(float(contents.left()), top), self._icon)
        finally:
            painter.end()


class ImageSignals(QObject):
    # image cache key, PIL image or None
    loaded = pyqtSignal(object, object)


class ImageLoader(QRunnable):
    """Decodes and scales one toast image away from the GUI thread.

    A photo takes around ten milliseconds, so a menu holding a few dozen of them would
    spend a noticeable while on the click. This only produces the pixels and leaves
    turning them into a pixmap to the thread that owns them.
    """

    def __init__(self, cache_key: ImageKey, decode: ImageDecoder):
        super().__init__()
        self._cache_key = cache_key
        self._decode = decode
        self.signals = ImageSignals()

    def run(self):
        self.signals.loaded.emit(self._cache_key, self._decode())


class NotificationsWidget(BaseWidget):
    validation_schema = NotificationsConfig
    windows_notification_update_signal = pyqtSignal(int)
    windows_notifications_changed_signal = pyqtSignal(list)
    windows_notification_access_signal = pyqtSignal(bool)
    dnd_status_changed_signal = pyqtSignal(str)
    # Raising a window is the GUI thread's job, and the click that asks for it is not
    # always still on it by then
    raise_app_signal = pyqtSignal(str)
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
        self._image_cache: dict[ImageKey, QPixmap | None] = {}
        self._image_pending: set[ImageKey] = set()
        # The app icon slots of the menu as it stands, by sender, asked again when icons load
        self._icon_labels: dict[str, list[QLabel]] = {}
        self._icons = IconService.instance()
        self._icons.icons_changed.connect(self._refresh_app_icons)
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
        self.raise_app_signal.connect(self._raise_app)

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
        self._warm_images(notifications)
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

            if part and widget_index < len(active_widgets):
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

        A cap is a matter of width rather than of truth: the number counts the same
        notifications the menu lists, so a long one is only ever a long one.
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
        viewport = self._scroll_area.viewport()
        if viewport is not None:
            viewport.setAutoFillBackground(False)
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
            self._dnd_button.mousePressEvent = lambda ev: self._toggle_dnd()
            self._update_dnd_button(dnd_status)
            header_layout.addWidget(self._dnd_button)

        clear_all_label = QLabel("Clear all")
        clear_all_label.setProperty("class", "label clear-all")
        clear_all_label.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_all_label.mousePressEvent = lambda ev: self._clear_notifications()
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
        open_center_label.mousePressEvent = lambda ev: self._open_notification_center()
        footer_layout.addWidget(open_center_label)
        footer_layout.addStretch()

        return footer

    def _open_notification_center(self):
        if is_valid_qobject(self._menu):
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
        menu = self._menu
        if not is_valid_qobject(menu):
            return
        menu.setUpdatesEnabled(False)
        try:
            self._rebuild_contents(menu)
        finally:
            menu.setUpdatesEnabled(True)

    def _rebuild_contents(self, menu: PopupWidget):
        if self._scroll_area is None or self._header_label is None:
            return
        notifications = self._notifications[: self.config.menu.max_notifications]
        # The slots of the menu being replaced go with it, so an icon that loads late has
        # nothing left to fill in
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
            for items in self._group_by_sender(notifications):
                content_layout.addWidget(self._build_section_header(items[0]))
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

        menu.adjustSize()
        menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )

    @staticmethod
    def _group_by_sender(notifications: list[NotificationItem]) -> list[list[NotificationItem]]:
        """The notifications in the order they are shown, split into the sections they head.

        Grouped the way the Notification Center groups them, by the sender Windows filed
        them under rather than by the app the listener names: a browser files one sender
        per website, so a page's notifications sit under the page instead of all of them
        landing together under the browser.
        """
        sections: dict[str, list[NotificationItem]] = {}
        # Senders that expose no name at all have nothing to head them with, so they are
        # collected under a generic header and moved last instead of trailing a real app
        unnamed: list[NotificationItem] = []
        for notification in notifications:
            if notification.app_name:
                sections.setdefault(notification.sender_id, []).append(notification)
            else:
                unnamed.append(notification)
        return [*sections.values(), unnamed] if unnamed else list(sections.values())

    def _build_section_header(self, notification: NotificationItem) -> QLabel:
        """The name a section is headed with, next to the icon Windows heads it with."""
        icon = self._section_icon(notification.sender_icon)
        text = notification.app_name or "Other"
        section_header = QLabel(text) if icon is None else SectionHeaderLabel(text, icon)
        section_header.setProperty("class", "section-header" if notification.app_name else "section-header other")
        section_header.setTextFormat(Qt.TextFormat.PlainText)
        return section_header

    def _section_icon(self, path: str) -> QPixmap | None:
        """The icon Windows registered for the sender, if it registered one.

        Only senders it keeps an icon for have one, which in practice means websites: an
        app is headed by its name alone, the way it already was.
        """
        if not self.config.menu.show_app_icons or not path:
            return None
        return self._get_app_logo(path, circle=False, size=self.config.menu.section_icon_size)

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
            action.mousePressEvent = lambda ev: self._open_privacy_settings()
            center_layout.addWidget(action, alignment=Qt.AlignmentFlag.AlignCenter)

        center_layout.addStretch()
        return center_layout

    def _open_privacy_settings(self):
        if is_valid_qobject(self._menu):
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
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # The Notification Center draws the hero above everything and the inline images
        # below the text, with the rest of the toast on a single row in between
        hero_label = self._build_image_label(notification.hero, "hero")
        if hero_label is not None:
            container_layout.addWidget(hero_label)

        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        container_layout.addLayout(row_layout)

        if self.config.menu.show_app_icons:
            icon_label = self._build_icon_label(notification, grouped=not show_app_name)
            if icon_label is not None:
                row_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignVCenter)

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

        row_layout.addWidget(text_content, 1)

        dismiss_label = QLabel(self.config.icons.dismiss)
        dismiss_label.setProperty("class", "dismiss")
        dismiss_label.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dismiss_label.mousePressEvent = self._create_dismiss_event(notification.id)
        row_layout.addWidget(dismiss_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        for path in notification.inline_images:
            image_label = self._build_image_label(path, "inline-image")
            if image_label is not None:
                container_layout.addWidget(image_label)

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
        def mouse_press_event(ev: QMouseEvent | None) -> None:
            if ev is not None:
                # Keep the click from bubbling up to the item and activating the app
                ev.accept()
            self._remove_notification(notification_id)

        return mouse_press_event

    def _create_activate_event(self, notification: NotificationItem):
        """Do with a click what the Notification Center does with one."""

        def mouse_press_event(a0: QMouseEvent | None) -> None:
            if is_valid_qobject(self._menu):
                self._menu.hide_animated()
            self._activate_notification(notification)

        return mouse_press_event

    def _activate_notification(self, notification: NotificationItem):
        """Hand a notification back to the app that sent it, away from the GUI thread.

        Handing it over means giving the app the launch string of that particular toast,
        which is what makes a screenshot notification open the screenshot rather than the
        tool that took it. Windows takes an activated notification off the list, so this
        does too. A sender that registered no way of being handed one is only brought to
        the front, and keeps its notification.

        Not on the GUI thread, because handing a notification to an app that is not running
        takes as long as the app takes to start, which is not something the bar should be
        waiting on. Only the handover happens out here: raising a window is left to the
        thread that owns them.
        """
        notification_id = notification.id
        aumid = notification.aumid
        launch = notification.launch
        activation_type = notification.activation_type

        def activate():
            if activate_toast(aumid, launch, activation_type):
                self._remove_notification(notification_id)
            elif aumid and is_valid_qobject(self):
                self.raise_app_signal.emit(aumid)

        # Ahead of any pictures still being prepared, which nobody is waiting on
        self._icon_pool.start(activate, 1)

    def _raise_app(self, aumid: str):
        activate_app_by_aumid(aumid, fallback_process_name=get_process_name_for_aumid(aumid))

    def _build_icon_label(self, notification: NotificationItem, grouped: bool) -> QLabel | None:
        """The icon slot of an item, or None when there is no icon to draw in it.

        A toast can override the app icon with one of its own, a contact photo for example,
        and that one is a local file which is read straight away. Anything else, including
        an override that will not load, falls back to the icon of the app that sent it.
        That one comes from the icon service and may not be ready yet, so its slot holds the
        space with the transparent stand-in the service hands out and the picture drops into
        it when the icon has loaded, rather than pushing the text along.

        A website is the exception. The app its notifications come through is the browser,
        which is not what sent them, and the shell has no icon for the name the browser
        gives it here, only a blank document. So a website that brought no picture of its
        own gets no icon at all, the way the Notification Center shows it, or the site's
        own icon when show_site_icons asks for it.
        """
        menu = self.config.menu
        website = self._is_from_website(notification)
        logos: list[tuple[str, bool]] = []
        if menu.show_images:
            logos.append((notification.app_logo, notification.app_logo_circle))
        if website:
            if menu.show_site_icons:
                logos.append((notification.sender_icon, False))
        elif menu.show_images and not grouped:
            # Ungrouped there is no section header carrying the sender's own icon, so
            # the item falls back to it before falling back to the app it came through
            logos.append((notification.sender_icon, False))
        for path, circle in logos:
            logo = self._get_app_logo(path, circle) if path else None
            if logo is not None:
                # An app logo override belongs in the app icon's place, the way Windows shows it
                return self._icon_label(logo, "icon app-logo")
        if website:
            return None

        aumid = notification.aumid
        pixmap = self._app_icon(aumid)
        if pixmap is None:
            return None
        icon_label = self._icon_label(pixmap, "icon")
        self._icon_labels.setdefault(aumid, []).append(icon_label)
        return icon_label

    @staticmethod
    def _is_from_website(notification: NotificationItem) -> bool:
        """Whether the notification came from a website rather than from the app it names.

        The listener names the browser, while the notification database files each website
        as a sender of its own, so the two disagree only for a website's notifications.
        """
        return bool(notification.sender_id) and notification.sender_id.casefold() != notification.aumid.casefold()

    @staticmethod
    def _icon_label(pixmap: QPixmap, class_name: str) -> QLabel:
        icon_label = QLabel()
        icon_label.setProperty("class", class_name)
        # No fixed size: it would fight the stylesheet box model and clip the pixmap
        icon_label.setPixmap(pixmap)
        return icon_label

    def _warm_app_icons(self, notifications: list[NotificationItem]):
        """Start on the icons of senders we have not seen, before anybody opens the menu.

        The list is normally known well before it is looked at, and extracting an icon is
        slow enough that doing it on the click is what makes opening the menu feel slow.
        """
        # A website never falls back to the icon of the browser it came through
        aumids = {n.aumid for n in notifications if n.aumid and not self._is_from_website(n)}
        self._icons.preload(
            (AppIcon(aumid) for aumid in aumids), self.config.menu.app_icon_size, self._device_pixel_ratio()
        )

    def _app_icon(self, aumid: str) -> QPixmap | None:
        return self._icons.get_icon(AppIcon(aumid), self.config.menu.app_icon_size, self._device_pixel_ratio())

    def _refresh_app_icons(self):
        """Put the icons that have loaded since the menu was built into its slots."""
        for aumid, icon_labels in self._icon_labels.items():
            pixmap = self._app_icon(aumid)
            if pixmap is None:
                continue
            for icon_label in icon_labels:
                if is_valid_qobject(icon_label):
                    icon_label.setPixmap(pixmap)

    @staticmethod
    def _to_pixmap(image: Image.Image, dpr: float) -> QPixmap | None:
        try:
            # Copy to avoid a dangling view into the PIL buffer
            pixmap = QPixmap.fromImage(ImageQt(image).copy())
            pixmap.setDevicePixelRatio(dpr)
            return pixmap
        except Exception:
            logging.exception("Failed to turn an icon or a toast image into a pixmap")
            return None

    def _icon_pixels(self, dpr: float, size: int | None = None) -> int:
        """The edge of an icon in device pixels, an app icon's own size unless told otherwise.

        A stylesheet cannot resize this: Qt draws a label's pixmap at the size it was made
        at, so the size has to be known before the pixmap is built.
        """
        return max(1, int(round((size or self.config.menu.app_icon_size) * dpr)))

    def _device_pixel_ratio(self) -> float:
        screen = self._menu.screen() if is_valid_qobject(self._menu) else self.screen()
        return float(screen.devicePixelRatio()) if screen is not None else 1.0

    def _build_image_label(self, path: str, class_name: str) -> QLabel | None:
        """A full width image row, or None when there is nothing to draw."""
        if not self.config.menu.show_images or not path:
            return None
        pixmap = self._get_notification_image(path)
        if pixmap is None:
            return None
        image_label = QLabel()
        image_label.setProperty("class", class_name)
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return image_label

    def _get_app_logo(self, path: str, circle: bool, size: int | None = None) -> QPixmap | None:
        """The app logo a toast brought with it, cropped square and optionally round."""
        return self._cached_image(*self._app_logo_job(path, circle, size))

    def _get_notification_image(self, path: str) -> QPixmap | None:
        """A hero or inline image, scaled to fit the menu."""
        return self._cached_image(*self._notification_image_job(path))

    def _app_logo_job(self, path: str, circle: bool, size: int | None = None) -> ImageJob:
        """The cache key of an app logo and what decodes it, for the menu and the loader alike."""
        dpr = self._device_pixel_ratio()
        pixels = self._icon_pixels(dpr, size)
        return (path, pixels, pixels, circle, dpr), partial(self._decode_app_logo, path, pixels, circle)

    def _notification_image_job(self, path: str) -> ImageJob:
        """The cache key of a hero or inline image and what decodes it."""
        dpr = self._device_pixel_ratio()
        width = max(1, self.config.menu.width - IMAGE_MARGIN)
        height = self.config.menu.image_max_height
        box = (max(1, int(width * dpr)), max(1, int(height * dpr)))
        return (path, width, height, False, dpr), partial(self._decode_notification_image, path, box)

    def _cached_image(self, cache_key: ImageKey, decode: ImageDecoder) -> QPixmap | None:
        """An image from the cache, decoded on the spot if the loader has not got to it yet.

        The spot is the GUI thread, which is only ever the case for a picture that arrived
        a moment before the menu was built: everything else was warmed as the list came in.
        """
        if cache_key not in self._image_cache:
            self._store_image(cache_key, decode())
        return self._image_cache[cache_key]

    def _warm_images(self, notifications: list[NotificationItem]):
        """Start on the pictures of the list as soon as it arrives, the way app icons are.

        Only the ones the menu is going to draw, asked for with the same keys it will look
        them up by, so the menu finds them ready and draws exactly what it drew before.
        """
        menu = self.config.menu
        for notification in notifications[: menu.max_notifications]:
            jobs: list[ImageJob] = []
            if menu.show_images:
                paths = (notification.hero, *notification.inline_images)
                jobs.extend(self._notification_image_job(path) for path in paths if path)
                if menu.show_app_icons and notification.app_logo:
                    jobs.append(self._app_logo_job(notification.app_logo, notification.app_logo_circle))
            # The sender's icon in the item itself, on the same terms _build_icon_label draws it
            if menu.show_app_icons and notification.sender_icon:
                if self._is_from_website(notification):
                    in_item = menu.show_site_icons
                else:
                    in_item = menu.show_images and not menu.group_by_app
                if in_item:
                    jobs.append(self._app_logo_job(notification.sender_icon, False))
            if menu.show_app_icons and menu.group_by_app and notification.sender_icon:
                jobs.append(self._app_logo_job(notification.sender_icon, False, menu.section_icon_size))
            for cache_key, decode in jobs:
                self._request_image(cache_key, decode)

    def _request_image(self, cache_key: ImageKey, decode: ImageDecoder):
        if cache_key in self._image_cache or cache_key in self._image_pending:
            return
        self._image_pending.add(cache_key)
        loader = ImageLoader(cache_key, decode)
        loader.signals.loaded.connect(self._on_image_loaded)
        self._icon_pool.start(loader)

    def _on_image_loaded(self, cache_key: ImageKey, image: Image.Image | None):
        self._image_pending.discard(cache_key)
        # The menu may have needed it first and decoded it itself
        if cache_key not in self._image_cache:
            self._store_image(cache_key, image)

    def _store_image(self, cache_key: ImageKey, image: Image.Image | None):
        pixmap = self._to_pixmap(image, cache_key[-1]) if image is not None else None
        self._cache_image(cache_key, pixmap)

    @classmethod
    def _decode_app_logo(cls, path: str, size: int, circle: bool) -> Image.Image | None:
        """Safe to run off the GUI thread: PIL only, no Qt."""
        try:
            with Image.open(path) as source:
                # These are photos as often as icons, so they are cropped to fill the square
                image = ImageOps.fit(cls._resizable(source), (size, size), Image.LANCZOS).convert("RGBA")
            if circle:
                round_image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                round_image.paste(image, mask=cls._circle_mask(size))
                image = round_image
            return image
        except Exception:
            logging.debug("Failed to load the app logo of a notification", exc_info=True)
            return None

    @classmethod
    def _decode_notification_image(cls, path: str, box: tuple[int, int]) -> Image.Image | None:
        """Safe to run off the GUI thread: PIL only, no Qt."""
        try:
            with Image.open(path) as source:
                image = cls._resizable(source)
                # Fits the box without cropping, and leaves an image smaller than it alone.
                # The conversion stays inside the block: an image that already fits is not
                # resized at all, and its pixels are still to be read from the open file
                image.thumbnail(box, Image.LANCZOS)
                return image.convert("RGBA")
        except Exception:
            logging.debug("Failed to load a notification image", exc_info=True)
            return None

    def _cache_image(self, cache_key: ImageKey, pixmap: QPixmap | None):
        # Dropping the lot is enough: the menu rebuilds from the entries it just filled in
        if len(self._image_cache) >= IMAGE_CACHE_SIZE:
            self._image_cache.clear()
        self._image_cache[cache_key] = pixmap

    @staticmethod
    def _resizable(source: Image.Image) -> Image.Image:
        """An image in a mode that can be resampled, ready to be scaled down.

        Scaling is done before the conversion to RGBA rather than after it, because it
        costs several times more once every pixel carries an alpha channel: a photo a
        messaging app sends takes 49ms the other way round and 11ms this way. Palette and
        bilevel images cannot be resampled at all, so those are converted first.
        """
        return source if source.mode in ("L", "RGB", "RGBA") else source.convert("RGBA")

    @staticmethod
    def _circle_mask(size: int) -> Image.Image:
        """A round mask, drawn oversized and scaled back down so the edge is not jagged."""
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
        return mask.resize((size, size), Image.LANCZOS)
