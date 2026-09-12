from pydantic import Field

from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)


class NotificationsMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0
    width: int = Field(default=380, ge=200)
    max_height: int = Field(default=400, ge=100)
    max_notifications: int = Field(default=30, ge=1)
    show_app_icons: bool = True
    group_by_app: bool = True
    show_dnd_toggle: bool = True
    show_notification_center: bool = True


class NotificationsIconsConfig(CustomBaseModel):
    new: str = "\udb80\udc9e"
    default: str = "\udb80\udc9a"
    dnd_on: str = "\udb80\udc9b"
    dnd_off: str = "\udb80\udc9a"
    dismiss: str = "\uf00d"


class NotificationsCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"


class NotificationsConfig(CustomBaseModel):
    label: str = "{count} new notifications"
    label_alt: str = "{count} new notifications"
    class_name: str = ""
    hide_empty: bool = False
    max_count: int = Field(default=0, ge=0)
    tooltip: bool = True
    icons: NotificationsIconsConfig = NotificationsIconsConfig()
    menu: NotificationsMenuConfig = NotificationsMenuConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: NotificationsCallbacksConfig = NotificationsCallbacksConfig()
