from typing import Literal

from pydantic import field_validator

from core.validation.widgets.base_model import CallbacksConfig, CustomBaseModel, KeybindingConfig


class ControlCenterPopupConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0


class ControlCenterActionConfig(CustomBaseModel):
    id: str
    label: str
    icon: str
    command: str | None = None


class QuickActionsSectionConfig(CustomBaseModel):
    show: bool = True
    columns: int = 3
    label_position: Literal["default", "inline"] = "default"
    actions: list[ControlCenterActionConfig] = [
        ControlCenterActionConfig(id="toggle_dnd", label="Do Not Disturb", icon="\uf285"),
        ControlCenterActionConfig(id="toggle_theme", label="Dark Mode", icon="\ue708"),
        ControlCenterActionConfig(id="touch_keyboard", label="Keyboard", icon="\ue765"),
        ControlCenterActionConfig(id="toggle_mute", label="Mute", icon="\ue74f"),
        ControlCenterActionConfig(id="toggle_mic_mute", label="Mic Mute", icon="\uf12e"),
        ControlCenterActionConfig(id="screenshot", label="Screenshot", icon="\ue91b"),
    ]

    @field_validator("actions")
    @classmethod
    def _no_duplicate_ids(cls, v: list[ControlCenterActionConfig]) -> list[ControlCenterActionConfig]:
        seen: set[str] = set()
        for action in v:
            if action.id in seen:
                raise ValueError(f"Duplicate action id: {action.id}")
            seen.add(action.id)
        return v


class ControlCenterSliderConfig(CustomBaseModel):
    show_slider: bool = True
    icon: str
    show_source_selector: bool = False
    source_selector_icon: str = "\ue972"


class SlidersSectionConfig(CustomBaseModel):
    show: bool = True
    brightness: ControlCenterSliderConfig = ControlCenterSliderConfig(icon="\ue706")
    volume: ControlCenterSliderConfig = ControlCenterSliderConfig(icon="\ue767")
    microphone: ControlCenterSliderConfig = ControlCenterSliderConfig(icon="\ue720")


class PowerSectionConfig(CustomBaseModel):
    show: bool = True
    power_plan_title: str = "Power Plan"
    power_mode_title: str = "Power Mode"
    button_menu_icon: str = "\ue76c"


class MediaSectionIconsConfig(CustomBaseModel):
    prev_track: str = "\ue892"
    next_track: str = "\ue893"
    play: str = "\ue768"
    pause: str = "\ue769"


class MediaSectionConfig(CustomBaseModel):
    show: bool = True
    thumbnail_size: int = 64
    thumbnail_radius: int = 8
    icons: MediaSectionIconsConfig = MediaSectionIconsConfig()


class SystemControlsConfig(CustomBaseModel):
    show: bool = True
    profile_image_size: int = 28
    power_icon: str = "\ue7e8"
    lock_icon: str = "\ue72e"
    settings_icon: str = "\ue713"


class ControlCenterSectionsConfig(CustomBaseModel):
    system_controls: SystemControlsConfig = SystemControlsConfig()
    quick_actions: QuickActionsSectionConfig = QuickActionsSectionConfig()
    sliders: SlidersSectionConfig = SlidersSectionConfig()
    power: PowerSectionConfig = PowerSectionConfig()
    media: MediaSectionConfig = MediaSectionConfig()


class ControlCenterCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_menu"


class ControlCenterConfig(CustomBaseModel):
    label: str = "<span>\ue90a</span>"
    label_alt: str = "<span>\ue90a</span>"
    class_name: str = ""
    tooltip: bool = False
    popup: ControlCenterPopupConfig = ControlCenterPopupConfig()
    sections: ControlCenterSectionsConfig = ControlCenterSectionsConfig()
    sections_order: list[Literal["system_controls", "quick_actions", "sliders", "power", "media"]] = [
        "system_controls",
        "quick_actions",
        "sliders",
        "power",
        "media",
    ]
    keybindings: list[KeybindingConfig] = []
    callbacks: ControlCenterCallbacksConfig = ControlCenterCallbacksConfig()
