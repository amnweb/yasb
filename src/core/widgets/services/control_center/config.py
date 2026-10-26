from typing import Literal

from pydantic import field_validator

from core.validation.base_model import CustomBaseModel


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
        ControlCenterActionConfig(id="toggle_dnd", label="Do Not Disturb", icon=""),
        ControlCenterActionConfig(id="toggle_theme", label="Dark Mode", icon=""),
        ControlCenterActionConfig(id="touch_keyboard", label="Keyboard", icon=""),
        ControlCenterActionConfig(id="toggle_mute", label="Mute", icon=""),
        ControlCenterActionConfig(id="toggle_mic_mute", label="Mic Mute", icon=""),
        ControlCenterActionConfig(id="screenshot", label="Screenshot", icon=""),
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
    source_selector_icon: str = ""


class SlidersSectionConfig(CustomBaseModel):
    show: bool = True
    brightness: ControlCenterSliderConfig = ControlCenterSliderConfig(icon="")
    volume: ControlCenterSliderConfig = ControlCenterSliderConfig(icon="")
    microphone: ControlCenterSliderConfig = ControlCenterSliderConfig(icon="")


class PowerSectionConfig(CustomBaseModel):
    show: bool = True
    power_plan_title: str = "Power Plan"
    power_mode_title: str = "Power Mode"
    button_menu_icon: str = ""


class MediaSectionIconsConfig(CustomBaseModel):
    prev_track: str = ""
    next_track: str = ""
    play: str = ""
    pause: str = ""


class MediaSectionConfig(CustomBaseModel):
    show: bool = True
    thumbnail_size: int = 64
    thumbnail_radius: int = 8
    icons: MediaSectionIconsConfig = MediaSectionIconsConfig()


class SystemControlsConfig(CustomBaseModel):
    show: bool = True
    profile_image_size: int = 28
    power_icon: str = ""
    lock_icon: str = ""
    settings_icon: str = ""
