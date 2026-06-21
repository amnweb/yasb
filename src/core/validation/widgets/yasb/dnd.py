from core.validation.widgets.base_model import CallbacksConfig, CustomBaseModel


class DndIconsConfig(CustomBaseModel):
    disabled: str = "\uf0f3"
    priority: str = "\uf186"
    alarms: str = "\uf1f6"


class DndCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_status"
    on_right: str = "cycle_status"


class DndConfig(CustomBaseModel):
    label: str = "{icon}"
    label_alt: str = "{icon} {status}"
    class_name: str = ""
    tooltip: bool = True
    default_active_mode: str = "priority"
    icons: DndIconsConfig = DndIconsConfig()
    callbacks: DndCallbacksConfig = DndCallbacksConfig()
