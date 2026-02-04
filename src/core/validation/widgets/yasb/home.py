from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    PaddingConfig,
    ShadowConfig,
)


class MenuItemConfig(CustomBaseModel):
    title: str | None = None
    path: str | None = None
    uri: str | None = None
    command: str | None = None
    separator: bool | None = None
    args: list[str] | None = None
    shell: bool | None = None
    show_window: bool | None = None


class MenuLabelsConfig(CustomBaseModel):
    shutdown: str = "Shutdown"
    restart: str = "Restart"
    hibernate: str = "Hibernate"
    logout: str = "Logout"
    lock: str = "Lock"
    sleep: str = "Sleep"
    system: str = "System Settings"
    about: str = "About This PC"
    task_manager: str = "Task Manager"


class CallbacksHomeConfig(CallbacksConfig):
    on_left: str = "toggle_menu"


class HomeConfig(CustomBaseModel):
    label: str = "\ue71a"
    menu_list: list[MenuItemConfig] | None = None
    container_padding: PaddingConfig = PaddingConfig()
    power_menu: bool = True
    system_menu: bool = True
    blur: bool = False
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "left"
    direction: str = "down"
    distance: int = 6
    offset_top: int = 6
    offset_left: int = 0
    menu_labels: MenuLabelsConfig = MenuLabelsConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    keybindings: list[KeybindingConfig] = []
    callbacks: CallbacksHomeConfig = CallbacksHomeConfig()
