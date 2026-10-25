import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, QSizeF, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.events.service import EventService
from core.utils.icons.service import AppIcon, IconService
from core.utils.qobject import is_valid_qobject
from core.utils.shell_utils import shell_open
from core.utils.system import is_windows_10
from core.utils.time_utils import get_relative_time
from core.utils.tooltip import set_tooltip
from core.utils.utilities import ElidedLabel, PopupWidget, refresh_widget_style
from core.utils.win32.system_function import notification_center, quick_settings
from core.validation.widgets.yasb.notifications import NotificationsConfig
from core.widgets.base import BaseWidget
from core.widgets.services.dnd.dnd_api import DndService
from core.widgets.services.notifications.notification_widgets import (
    HoverFrame,
    ImageLoader,
    ImageSignals,
    ImageView,
    NotificationCard,
)

if TYPE_CHECKING:
    from core.widgets.services.notifications.windows_notification import NotificationItem

try:
    from core.widgets.services.notifications.windows_notification import WindowsNotificationEventListener
except ImportError:
    WindowsNotificationEventListener = None
    logging.warning("Failed to load Windows Notification Event Listener")

NOTIFICATION_SETTINGS_URI = "ms-settings:privacy-notifications"
MAX_COUNT = 9
# notifications shown per app before "N more"
COLLAPSED_COUNT = 2
# logical px; the logo and hero sizes the toast docs give at 100% scaling
AVATAR_SIZE = 48
HERO_ASPECT = QSizeF(364, 180)
PICTURE_MAX_HEIGHT = 240
PICTURE_LOAD_SIZE = QSize(480, 400)
# ms
PICTURE_REFRESH_DELAY = 50


class NotificationsWidget(BaseWidget):
    validation_schema = NotificationsConfig
    windows_notification_update_signal = pyqtSignal(int)
    windows_notifications_changed_signal = pyqtSignal(object)
    dnd_status_changed_signal = pyqtSignal(str)
    event_listener = WindowsNotificationEventListener

    def __init__(self, config: NotificationsConfig):
        super().__init__(class_name=f"notification-widget {config.class_name}")
        self.config = config
        self._show_alt_label = False
        self._notification_count = 0
        # None while notification access is turned off
        self._notifications: list[NotificationItem] | None = []
        self._menu: PopupWidget | None = None
        self._scroll_area: QScrollArea | None = None
        self._dnd_button: QLabel | None = None
        self._expanded: set[str] = set()
        self._icon_labels: list[tuple[str, QLabel]] = []
        self._icons = IconService.instance()
        self._icons.icons_changed.connect(self._refresh_app_icons)
        self._pictures: dict[str, QPixmap] = {}
        self._pictures_loading: set[str] = set()
        self._picture_signals = ImageSignals()
        self._picture_signals.loaded.connect(self._on_picture_loaded)
        self._picture_pool = QThreadPool(self)
        self._picture_pool.setMaxThreadCount(2)
        self._menu_refresh_timer = QTimer(self)
        self._menu_refresh_timer.setSingleShot(True)
        self._menu_refresh_timer.setInterval(PICTURE_REFRESH_DELAY)
        self._menu_refresh_timer.timeout.connect(self._refresh_menu_items)

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
        self.windows_notification_update_signal.connect(self._on_windows_notification_update)
        self.event_service.register_event("WindowsNotificationsChanged", self.windows_notifications_changed_signal)  # type: ignore
        self.windows_notifications_changed_signal.connect(self._on_notifications_changed)

        DndService.initialize_wnf_listener()
        self.event_service.register_event("dnd_status_changed", self.dnd_status_changed_signal)  # type: ignore
        self.dnd_status_changed_signal.connect(self._update_dnd_button)

        self._update_label()

    def _on_windows_notification_update(self, total_notifications: int):
        self._notification_count = total_notifications
        if total_notifications > 0:
            self.setVisible(True)
        elif self.config.hide_empty:
            self.setVisible(False)
        self._update_label()

    def _on_notifications_changed(self, notifications: list[NotificationItem] | None):
        if notifications == self._notifications:
            return
        self._notifications = notifications
        self._load_pictures(notifications or [])
        if notifications:
            sources = {AppIcon(n.aumid) for n in notifications if n.aumid}
            self._icons.preload(sources, self.config.menu.app_icon_size, self._dpr())
        if self._menu_is_open():
            self._refresh_menu_items()

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

        count = self._notification_count
        # Provide replacements for {count} and {icon}
        label_options = [("{count}", f"{MAX_COUNT}+" if count > MAX_COUNT else count), ("{icon}", icon)]

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

    def _menu_is_open(self) -> bool:
        return is_valid_qobject(self._menu) and self._menu.isVisible()

    def _toggle_menu(self):
        if self._menu_is_open():
            self._close_menu()
            return
        self._show_menu()

    def _close_menu(self):
        if is_valid_qobject(self._menu):
            self._menu.hide_animated()

    def _show_menu(self):
        menu_config = self.config.menu
        self._menu = PopupWidget(
            self,
            menu_config.blur,
            menu_config.round_corners,
            menu_config.round_corners_type,
            menu_config.border_color,
        )
        self._menu.setProperty("class", "notification-menu")
        self._expanded.clear()

        layout = QVBoxLayout(self._menu)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._create_header())
        self._scroll_area = self._create_scroll_area()
        layout.addWidget(self._scroll_area)
        layout.addWidget(self._create_footer())

        self._refresh_menu_items()
        self._menu.show()
        self.event_service.emit_event("WindowsNotificationRefresh", "refresh_notifications")

    def _create_header(self) -> QFrame:
        header = QFrame()
        header.setProperty("class", "header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("Notifications")
        title.setProperty("class", "title")
        layout.addWidget(title, 1)

        self._dnd_button = None
        status = DndService.get_status()
        if status != "unknown":
            self._dnd_button = self._create_button("", "dnd", self._toggle_dnd)
            self._update_dnd_button(status)
            layout.addWidget(self._dnd_button)

        layout.addWidget(self._create_button("Clear all", "clear-all", self._clear_notifications))
        return header

    def _create_scroll_area(self) -> QScrollArea:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; border-radius:0; }
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
        """)
        # the viewport paints the palette background, which the stylesheet above doesn't reach
        viewport = scroll_area.viewport()
        if viewport is not None:
            viewport.setAutoFillBackground(False)
        return scroll_area

    def _create_footer(self) -> QFrame:
        footer = QFrame()
        footer.setProperty("class", "footer")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._create_button("Open Notification Center", "label", self._open_notification_center))
        layout.addStretch()
        return footer

    def _refresh_menu_items(self):
        menu, scroll_area = self._menu, self._scroll_area
        if not is_valid_qobject(menu) or scroll_area is None:
            return
        self._icon_labels.clear()
        scroll_bar = scroll_area.verticalScrollBar()
        scroll_position = scroll_bar.value() if scroll_bar is not None else 0

        contents = QWidget()
        contents.setProperty("class", "contents")
        layout = QVBoxLayout(contents)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if self._notifications:
            for items in self._group_by_app(self._notifications):
                layout.addWidget(self._create_app_section(items))
        else:
            layout.addStretch()
            layout.addWidget(self._create_empty_message())
        layout.addStretch()

        # setWidget deletes the old list at once, while a click on one of its buttons may still be running
        old = scroll_area.takeWidget()
        if old is not None:
            old.deleteLater()
        scroll_area.setWidget(contents)
        # setWidget turns it back on
        contents.setAutoFillBackground(False)
        menu.adjustSize()
        menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )
        if scroll_bar is not None:
            scroll_bar.setValue(scroll_position)

    @staticmethod
    def _group_by_app(notifications: list[NotificationItem]) -> list[list[NotificationItem]]:
        groups: dict[str, list[NotificationItem]] = {}
        for notification in notifications:
            groups.setdefault(notification.aumid, []).append(notification)
        return list(groups.values())

    def _create_app_section(self, items: list[NotificationItem]) -> QFrame:
        aumid = items[0].aumid
        section = QFrame()
        section.setProperty("class", "section")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._create_app_header(items[0]))

        expanded = aumid in self._expanded
        shown = items if expanded else items[:COLLAPSED_COUNT]
        for item in shown:
            layout.addWidget(self._create_notification_item(item))

        hidden = len(items) - len(shown)
        if hidden or (expanded and len(items) > COLLAPSED_COUNT):
            text = f"{hidden} more" if hidden else "Show less"
            layout.addWidget(self._create_button(text, "more", lambda: self._toggle_expanded(aumid)))
        return section

    def _create_app_header(self, item: NotificationItem) -> QFrame:
        clear = self._create_button(self.config.icons.dismiss, "clear-app", lambda: self._clear_app(item.aumid))
        header = HoverFrame(clear)
        header.setProperty("class", "section-header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        pixmap = self._get_app_icon(item.aumid)
        if pixmap is not None:
            icon = QLabel()
            icon.setProperty("class", "icon")
            icon.setPixmap(pixmap)
            self._icon_labels.append((item.aumid, icon))
            layout.addWidget(icon)
        name = QLabel(item.app_name or "Other")
        name.setProperty("class", "name")
        name.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(name, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(clear)
        return header

    def _create_notification_item(self, item: NotificationItem) -> QFrame:
        time = QLabel(get_relative_time(item.created_at.isoformat(), short=True))
        time.setProperty("class", "time")
        dismiss = self._create_button(self.config.icons.dismiss, "dismiss", lambda: self._dismiss(item.id))
        card = NotificationCard(lambda: self._activate(item), time, dismiss)
        card.setProperty("class", "item")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hero = self._create_picture(item.hero, "hero", HERO_ASPECT)
        if hero is not None:
            layout.addWidget(hero)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        layout.addLayout(row)
        avatar = self._create_avatar(item)
        if avatar is not None:
            row.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        row.addLayout(text, 1)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(0)
        title = ElidedLabel(item.title or item.app_name)
        title.setProperty("class", "title")
        title.setTextFormat(Qt.TextFormat.PlainText)
        # a stylesheet margin gives a label a frame, and a framed label indents its text
        title.setIndent(0)
        title_row.addWidget(title, 1)
        corner = QGridLayout()
        corner.setContentsMargins(0, 0, 0, 0)
        for label in (time, dismiss):
            corner.addWidget(label, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        title_row.addLayout(corner)
        text.addLayout(title_row)

        if item.body:
            body = QLabel(item.body)
            body.setProperty("class", "body")
            body.setTextFormat(Qt.TextFormat.PlainText)
            body.setWordWrap(True)
            body.setIndent(0)
            # a stylesheet max-height cuts the end of the text, not both ends
            body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            text.addWidget(body)

        if item.attribution:
            attribution = ElidedLabel(item.attribution)
            attribution.setProperty("class", "attribution")
            attribution.setTextFormat(Qt.TextFormat.PlainText)
            attribution.setIndent(0)
            text.addWidget(attribution)

        picture = self._create_picture(item.image, "image")
        if picture is not None:
            text.addWidget(picture)
        return card

    def _create_empty_message(self) -> QFrame:
        empty = QFrame()
        empty.setProperty("class", "empty")
        layout = QVBoxLayout(empty)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        icon = QLabel(self.config.icons.default)
        icon.setProperty("class", "icon")
        layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        no_access = self._notifications is None
        text = QLabel("Notification access is turned off" if no_access else "No new notifications")
        text.setProperty("class", "text")
        layout.addWidget(text, alignment=Qt.AlignmentFlag.AlignCenter)
        if no_access:
            link = self._create_button("Open settings", "link", self._open_notification_settings)
            layout.addWidget(link, alignment=Qt.AlignmentFlag.AlignCenter)
        return empty

    @staticmethod
    def _create_button(text: str, class_name: str, action: Callable[[], None]) -> QLabel:
        button = QLabel(text)
        button.setProperty("class", class_name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.mousePressEvent = lambda ev: action()
        return button

    def _toggle_expanded(self, aumid: str):
        self._expanded ^= {aumid}
        self._refresh_menu_items()

    def _dismiss(self, notification_id: int):
        self.event_service.emit_event("WindowsNotificationRemove", notification_id)

    def _clear_app(self, aumid: str):
        self.event_service.emit_event("WindowsNotificationClearApp", aumid)

    def _activate(self, item: NotificationItem):
        self._close_menu()
        self.event_service.emit_event("WindowsNotificationActivate", item)

    def _open_notification_center(self):
        self._close_menu()
        self._toggle_notification()

    def _open_notification_settings(self):
        self._close_menu()
        shell_open(NOTIFICATION_SETTINGS_URI)

    def _toggle_dnd(self):
        status = "priority" if DndService.get_status() == "disabled" else "disabled"
        DndService.set_status(status)
        self._update_dnd_button(status)

    def _update_dnd_button(self, status: str):
        button = self._dnd_button
        if not is_valid_qobject(button):
            return
        enabled = status not in ("disabled", "unknown")
        button.setText(self.config.icons.dnd_on if enabled else self.config.icons.dnd_off)
        button.setProperty("class", "dnd active" if enabled else "dnd")
        if self.config.tooltip:
            set_tooltip(button, "Turn off do not disturb" if enabled else "Turn on do not disturb")
        refresh_widget_style(button)

    def _get_app_icon(self, aumid: str) -> QPixmap | None:
        if not aumid:
            return None
        return self._icons.get_icon(AppIcon(aumid), self.config.menu.app_icon_size, self._dpr())

    def _refresh_app_icons(self):
        for aumid, label in self._icon_labels:
            pixmap = self._get_app_icon(aumid)
            if pixmap is not None and is_valid_qobject(label):
                label.setPixmap(pixmap)

    def _create_avatar(self, item: NotificationItem) -> QLabel | None:
        pixmap = self._pictures.get(self._picture_key(item.logo, "round" if item.logo_circle else "square"))
        if pixmap is None:
            return None
        avatar = QLabel()
        avatar.setProperty("class", "avatar")
        avatar.setPixmap(pixmap)
        return avatar

    def _create_picture(self, path: str, class_name: str, aspect: QSizeF | None = None) -> ImageView | None:
        pixmap = self._pictures.get(self._picture_key(path, "full"))
        if pixmap is None:
            return None
        picture = ImageView(pixmap, aspect or pixmap.deviceIndependentSize(), PICTURE_MAX_HEIGHT)
        picture.setProperty("class", class_name)
        return picture

    @staticmethod
    def _picture_key(path: str, shape: str) -> str:
        return f"{shape}:{path}"

    def _load_pictures(self, notifications: list[NotificationItem]):
        wanted: dict[str, tuple[str, str]] = {}
        for n in notifications:
            if n.logo:
                shape = "round" if n.logo_circle else "square"
                wanted[self._picture_key(n.logo, shape)] = (n.logo, shape)
            for path in (n.hero, n.image):
                if path:
                    wanted[self._picture_key(path, "full")] = (path, "full")
        self._pictures = {key: pixmap for key, pixmap in self._pictures.items() if key in wanted}
        dpr = self._dpr()
        for key, (path, shape) in wanted.items():
            if key in self._pictures or key in self._pictures_loading:
                continue
            self._pictures_loading.add(key)
            square = shape != "full"
            size = QSize(AVATAR_SIZE, AVATAR_SIZE) if square else PICTURE_LOAD_SIZE
            self._picture_pool.start(
                ImageLoader(self._picture_signals, key, path, size * dpr, square, shape == "round")
            )

    def _on_picture_loaded(self, key: str, image: QImage):
        self._pictures_loading.discard(key)
        if image.isNull():
            return
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(self._dpr())
        self._pictures[key] = pixmap
        if self._menu_is_open():
            self._menu_refresh_timer.start()

    def _dpr(self) -> float:
        screen = self.screen()
        return screen.devicePixelRatio() if screen is not None else 1.0
