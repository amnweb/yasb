from pydantic import Field

from core.validation.widgets.base_model import (
    AnimationConfig,
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
    ShadowConfig,
)


class PrayerTimesCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_card"
    on_middle: str = "do_nothing"
    on_right: str = "toggle_label"


class PrayerTimesIconsConfig(CustomBaseModel):
    mosque: str = "\uf67f"
    fajr: str = "\uf185"
    sunrise: str = "\uf185"
    dhuhr: str = "\uf185"
    asr: str = "\uf185"
    maghrib: str = "\uf186"
    isha: str = "\uf186"
    imsak: str = "\uf185"
    sunset: str = "\uf185"
    midnight: str = "\uf186"
    default: str = "\uf017"


class PrayerTimesMenuConfig(CustomBaseModel):
    blur: bool = True
    round_corners: bool = True
    round_corners_type: str = "normal"
    border_color: str = "System"
    alignment: str = "right"
    direction: str = "down"
    offset_top: int = 6
    offset_left: int = 0


class PrayerTimesFlashConfig(CustomBaseModel):
    enabled: bool = True
    duration: int = Field(default=30, ge=1, le=3600)
    interval: int = Field(default=500, ge=100, le=5000)
    color_a: str = "#ff8c00"
    color_b: str = "#1e1e2e"


class PrayerTimesConfig(CustomBaseModel):
    label: str = "{icon} {next_prayer} {next_prayer_time}"
    label_alt: str = "Fajr {fajr} · Dhuhr {dhuhr} · Asr {asr} · Maghrib {maghrib} · Isha {isha}"
    class_name: str = ""
    latitude: float = Field(default=51.5074, ge=-90.0, le=90.0)
    longitude: float = Field(default=-0.1278, ge=-180.0, le=180.0)
    method: int = Field(default=2, ge=0, le=99)
    school: int = Field(default=0, ge=0, le=1)
    midnight_mode: int = Field(default=0, ge=0, le=1)
    tune: str = ""
    timezone: str = ""
    shafaq: str = ""
    prayers_to_show: list[str] = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    grace_period: int = Field(default=15, ge=0, le=120)
    update_interval: int = Field(default=3600, ge=60, le=86400)
    tooltip: bool = True
    icons: PrayerTimesIconsConfig = PrayerTimesIconsConfig()
    menu: PrayerTimesMenuConfig = PrayerTimesMenuConfig()
    flash: PrayerTimesFlashConfig = PrayerTimesFlashConfig()
    animation: AnimationConfig = AnimationConfig()
    label_shadow: ShadowConfig = ShadowConfig()
    container_shadow: ShadowConfig = ShadowConfig()
    callbacks: PrayerTimesCallbacksConfig = PrayerTimesCallbacksConfig()
    keybindings: list[KeybindingConfig] = []
