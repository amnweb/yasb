from typing import Literal

from pydantic import Field

from core.utils.widgets.prayer_times.schedule import ALL_PRAYER_NAMES
from core.validation.widgets.base_model import (
    CallbacksConfig,
    CustomBaseModel,
    KeybindingConfig,
)

PrayerName = Literal[
    "Imsak",
    "Fajr",
    "Sunrise",
    "Dhuhr",
    "Asr",
    "Sunset",
    "Maghrib",
    "Isha",
    "Firstthird",
    "Midnight",
    "Lastthird",
]

if set(PrayerName.__args__) != set(ALL_PRAYER_NAMES):  # pragma: no cover - guards against drift
    raise RuntimeError("PrayerName Literal is out of sync with ALL_PRAYER_NAMES")

# Nine comma-separated minute offsets, matching the Aladhan `tune` parameter.
TUNE_PATTERN = r"^$|^-?\d+(,-?\d+){8}$"


class PrayerTimesCallbacksConfig(CallbacksConfig):
    on_left: str = "toggle_card"
    on_middle: str = "do_nothing"
    on_right: str = "toggle_label"


class PrayerTimesIconsConfig(CustomBaseModel):
    # Nerd Fonts v3 codepoints. Every prayer uses Weather Icons (U+E300-U+E3E3) so the
    # glyphs share one drawing style and follow the sun across the day; the mosque and
    # the fallback clock are Font Awesome. No default may use the pre-v3 Material Design
    # range (U+F500-U+FD46): Nerd Fonts v3 removed it and it renders as tofu.
    mosque: str = "\ueed3"  # fa-mosque
    imsak: str = "\ue3c2"  # weather-moonset
    fajr: str = "\ue342"  # weather-horizon_alt
    sunrise: str = "\ue34c"  # weather-sunrise
    dhuhr: str = "\ue30d"  # weather-day_sunny
    asr: str = "\ue30d"  # weather-day_sunny
    sunset: str = "\ue34d"  # weather-sunset
    maghrib: str = "\ue343"  # weather-horizon
    isha: str = "\ue390"  # weather-moon_waxing_crescent_3
    firstthird: str = "\ue32b"  # weather-night_clear
    midnight: str = "\ue32b"  # weather-night_clear
    lastthird: str = "\ue32b"  # weather-night_clear
    # oct-dot_fill. A dot, not a check: the widget knows the time has gone by, not that
    # you prayed it, and the same dot is what a passed prayer becomes on the day ribbon.
    done: str = "\uf444"
    default: str = "\uf017"  # fa-clock_o


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
    debug: bool = False
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
    tune: str = Field(default="", pattern=TUNE_PATTERN)
    timezone: str = ""
    shafaq: Literal["", "general", "ahmer", "abyad"] = ""
    prayers_to_show: list[PrayerName] = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    grace_period: int = Field(default=15, ge=0, le=120)
    update_interval: int = Field(default=3600, ge=60, le=86400)
    tooltip: bool = True
    icons: PrayerTimesIconsConfig = PrayerTimesIconsConfig()
    menu: PrayerTimesMenuConfig = PrayerTimesMenuConfig()
    flash: PrayerTimesFlashConfig = PrayerTimesFlashConfig()
    callbacks: PrayerTimesCallbacksConfig = PrayerTimesCallbacksConfig()
    keybindings: list[KeybindingConfig] = []
