import json
import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from PyQt6.QtWidgets import QApplication

from core.utils.utilities import app_data_path
from core.utils.widgets.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_CLOCK

_PINNED_FILE = str(app_data_path("quick_launch_world_clock_pins.json"))

# City name IANA timezone
_CITIES: dict[str, str] = {
    # Americas - North
    "New York": "America/New_York",
    "Los Angeles": "America/Los_Angeles",
    "Chicago": "America/Chicago",
    "Denver": "America/Denver",
    "Phoenix": "America/Phoenix",
    "Houston": "America/Chicago",
    "Miami": "America/New_York",
    "Seattle": "America/Los_Angeles",
    "San Francisco": "America/Los_Angeles",
    "Boston": "America/New_York",
    "Atlanta": "America/New_York",
    "Dallas": "America/Chicago",
    "Detroit": "America/Detroit",
    "Minneapolis": "America/Chicago",
    "Washington DC": "America/New_York",
    "Philadelphia": "America/New_York",
    "Toronto": "America/Toronto",
    "Montreal": "America/Toronto",
    "Vancouver": "America/Vancouver",
    "Calgary": "America/Edmonton",
    "Edmonton": "America/Edmonton",
    "Ottawa": "America/Toronto",
    "Winnipeg": "America/Winnipeg",
    "Honolulu": "Pacific/Honolulu",
    "Anchorage": "America/Anchorage",
    # Americas - Central & South
    "Mexico City": "America/Mexico_City",
    "Cancun": "America/Cancun",
    "Havana": "America/Havana",
    "Panama City": "America/Panama",
    "San Juan": "America/Puerto_Rico",
    "Kingston": "America/Jamaica",
    "São Paulo": "America/Sao_Paulo",
    "Rio de Janeiro": "America/Sao_Paulo",
    "Buenos Aires": "America/Argentina/Buenos_Aires",
    "Lima": "America/Lima",
    "Bogota": "America/Bogota",
    "Santiago": "America/Santiago",
    "Caracas": "America/Caracas",
    "Quito": "America/Guayaquil",
    "Montevideo": "America/Montevideo",
    "Asuncion": "America/Asuncion",
    "La Paz": "America/La_Paz",
    # Europe - Western
    "London": "Europe/London",
    "Paris": "Europe/Paris",
    "Berlin": "Europe/Berlin",
    "Madrid": "Europe/Madrid",
    "Barcelona": "Europe/Madrid",
    "Rome": "Europe/Rome",
    "Milan": "Europe/Rome",
    "Amsterdam": "Europe/Amsterdam",
    "Brussels": "Europe/Brussels",
    "Zurich": "Europe/Zurich",
    "Geneva": "Europe/Zurich",
    "Vienna": "Europe/Vienna",
    "Lisbon": "Europe/Lisbon",
    "Dublin": "Europe/Dublin",
    "Edinburgh": "Europe/London",
    "Manchester": "Europe/London",
    "Munich": "Europe/Berlin",
    "Frankfurt": "Europe/Berlin",
    "Hamburg": "Europe/Berlin",
    "Luxembourg": "Europe/Luxembourg",
    # Europe - Nordic
    "Stockholm": "Europe/Stockholm",
    "Oslo": "Europe/Oslo",
    "Copenhagen": "Europe/Copenhagen",
    "Helsinki": "Europe/Helsinki",
    "Reykjavik": "Atlantic/Reykjavik",
    # Europe - Eastern
    "Warsaw": "Europe/Warsaw",
    "Prague": "Europe/Prague",
    "Budapest": "Europe/Budapest",
    "Bucharest": "Europe/Bucharest",
    "Sofia": "Europe/Sofia",
    "Belgrade": "Europe/Belgrade",
    "Zagreb": "Europe/Zagreb",
    "Athens": "Europe/Athens",
    "Istanbul": "Europe/Istanbul",
    "Moscow": "Europe/Moscow",
    "Saint Petersburg": "Europe/Moscow",
    "Kyiv": "Europe/Kyiv",
    "Minsk": "Europe/Minsk",
    "Tallinn": "Europe/Tallinn",
    "Riga": "Europe/Riga",
    "Vilnius": "Europe/Vilnius",
    # Asia - East
    "Tokyo": "Asia/Tokyo",
    "Osaka": "Asia/Tokyo",
    "Shanghai": "Asia/Shanghai",
    "Beijing": "Asia/Shanghai",
    "Shenzhen": "Asia/Shanghai",
    "Guangzhou": "Asia/Shanghai",
    "Hong Kong": "Asia/Hong_Kong",
    "Macau": "Asia/Macau",
    "Taipei": "Asia/Taipei",
    "Seoul": "Asia/Seoul",
    "Busan": "Asia/Seoul",
    "Ulaanbaatar": "Asia/Ulaanbaatar",
    # Asia - Southeast
    "Singapore": "Asia/Singapore",
    "Bangkok": "Asia/Bangkok",
    "Jakarta": "Asia/Jakarta",
    "Kuala Lumpur": "Asia/Kuala_Lumpur",
    "Manila": "Asia/Manila",
    "Hanoi": "Asia/Ho_Chi_Minh",
    "Ho Chi Minh": "Asia/Ho_Chi_Minh",
    "Phnom Penh": "Asia/Phnom_Penh",
    "Yangon": "Asia/Yangon",
    # Asia - South
    "Mumbai": "Asia/Kolkata",
    "Delhi": "Asia/Kolkata",
    "Bangalore": "Asia/Kolkata",
    "Kolkata": "Asia/Kolkata",
    "Chennai": "Asia/Kolkata",
    "Hyderabad": "Asia/Kolkata",
    "Karachi": "Asia/Karachi",
    "Lahore": "Asia/Karachi",
    "Islamabad": "Asia/Karachi",
    "Dhaka": "Asia/Dhaka",
    "Colombo": "Asia/Colombo",
    "Kathmandu": "Asia/Kathmandu",
    # Asia - West / Middle East
    "Dubai": "Asia/Dubai",
    "Abu Dhabi": "Asia/Dubai",
    "Riyadh": "Asia/Riyadh",
    "Jeddah": "Asia/Riyadh",
    "Tehran": "Asia/Tehran",
    "Doha": "Asia/Qatar",
    "Kuwait City": "Asia/Kuwait",
    "Muscat": "Asia/Muscat",
    "Bahrain": "Asia/Bahrain",
    "Amman": "Asia/Amman",
    "Beirut": "Asia/Beirut",
    "Baghdad": "Asia/Baghdad",
    "Jerusalem": "Asia/Jerusalem",
    "Tel Aviv": "Asia/Jerusalem",
    "Baku": "Asia/Baku",
    "Tbilisi": "Asia/Tbilisi",
    "Yerevan": "Asia/Yerevan",
    # Asia - Central
    "Tashkent": "Asia/Tashkent",
    "Almaty": "Asia/Almaty",
    "Nur-Sultan": "Asia/Almaty",
    # Oceania
    "Sydney": "Australia/Sydney",
    "Melbourne": "Australia/Melbourne",
    "Brisbane": "Australia/Brisbane",
    "Perth": "Australia/Perth",
    "Adelaide": "Australia/Adelaide",
    "Darwin": "Australia/Darwin",
    "Hobart": "Australia/Hobart",
    "Auckland": "Pacific/Auckland",
    "Wellington": "Pacific/Auckland",
    "Fiji": "Pacific/Fiji",
    "Guam": "Pacific/Guam",
    "Samoa": "Pacific/Apia",
    # Africa
    "Cairo": "Africa/Cairo",
    "Lagos": "Africa/Lagos",
    "Nairobi": "Africa/Nairobi",
    "Johannesburg": "Africa/Johannesburg",
    "Cape Town": "Africa/Johannesburg",
    "Casablanca": "Africa/Casablanca",
    "Accra": "Africa/Accra",
    "Addis Ababa": "Africa/Addis_Ababa",
    "Dar es Salaam": "Africa/Dar_es_Salaam",
    "Kinshasa": "Africa/Kinshasa",
    "Algiers": "Africa/Algiers",
    "Tunis": "Africa/Tunis",
    "Khartoum": "Africa/Khartoum",
    "Dakar": "Africa/Dakar",
    "Kampala": "Africa/Kampala",
    # Special
    "UTC": "UTC",
}

_DEFAULT_CITIES = [
    "New York",
    "London",
    "Paris",
    "Berlin",
    "Tokyo",
    "Shanghai",
    "Sydney",
    "Dubai",
    "Mumbai",
    "São Paulo",
    "Los Angeles",
    "Singapore",
]


def _format_utc_offset(dt: datetime) -> str:
    """Format UTC offset like UTC+5:30 or UTC-8."""
    offset = dt.utcoffset()
    if offset is None:
        return "UTC"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if minutes:
        return f"UTC{sign}{hours}:{minutes:02d}"
    return f"UTC{sign}{hours}"


def _format_diff(local_dt: datetime, city_dt: datetime) -> str:
    """Format difference from local time like '5h ahead' or '3h behind'."""
    local_off = local_dt.utcoffset() or timedelta()
    city_off = city_dt.utcoffset() or timedelta()
    diff = city_off - local_off
    total_hours = diff.total_seconds() / 3600
    if total_hours == 0:
        return "same as local"
    sign = "ahead" if total_hours > 0 else "behind"
    total_hours = abs(total_hours)
    if total_hours == int(total_hours):
        return f"{int(total_hours)}h {sign}"
    h = int(total_hours)
    m = int((total_hours - h) * 60)
    return f"{h}h {m}m {sign}"


def _build_result(city: str, tz_id: str, now_utc: datetime, local_dt: datetime, pinned: bool = False) -> ProviderResult:
    """Build a ProviderResult for a city."""
    tz = ZoneInfo(tz_id)
    city_dt = now_utc.astimezone(tz)
    time_str = city_dt.strftime("%I:%M %p").lstrip("0")
    date_str = city_dt.strftime("%a, %b %d")
    utc_str = _format_utc_offset(city_dt)
    diff_str = _format_diff(local_dt, city_dt)
    desc = f"{date_str} - {utc_str} ({diff_str})"
    if pinned:
        desc += " - pinned"
    return ProviderResult(
        title=f"{city} - {time_str}",
        description=desc,
        icon_char=ICON_CLOCK,
        provider="world_clock",
        action_data={"time": time_str, "city": city, "date": date_str, "utc": utc_str},
    )


class WorldClockProvider(BaseProvider):
    """Show current time in cities around the world."""

    name = "world_clock"
    display_name = "World Clock"
    input_placeholder = "Search cities or timezones..."
    icon = ICON_CLOCK

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._pinned: list[str] = self._load_pinned()

    def _load_pinned(self) -> list[str]:
        try:
            if os.path.isfile(_PINNED_FILE):
                with open(_PINNED_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return [c for c in data if isinstance(c, str) and c in _CITIES]
        except Exception as e:
            logging.debug(f"Failed to load pinned cities: {e}")
        return []

    def _save_pinned(self):
        try:
            os.makedirs(os.path.dirname(_PINNED_FILE), exist_ok=True)
            with open(_PINNED_FILE, "w", encoding="utf-8") as f:
                json.dump(self._pinned, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.debug(f"Failed to save pinned cities: {e}")

    def is_pinned(self, city: str) -> bool:
        return city in self._pinned

    def match(self, text: str) -> bool:
        if self.prefix and text.strip().startswith(self.prefix):
            return True
        return False

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).strip().lower()
        now_utc = datetime.now(timezone.utc)
        try:
            local_dt = now_utc.astimezone(ZoneInfo("localtime"))
        except Exception:
            local_dt = now_utc.astimezone()

        if not query:
            show_cities = self._pinned if self._pinned else _DEFAULT_CITIES
            results = []
            for city in show_cities:
                tz_id = _CITIES.get(city)
                if tz_id:
                    results.append(_build_result(city, tz_id, now_utc, local_dt, pinned=city in self._pinned))
            return results

        pinned_results = []
        regular_results = []
        for city, tz_id in _CITIES.items():
            if query in city.lower() or query in tz_id.lower():
                pinned = self.is_pinned(city)
                r = _build_result(city, tz_id, now_utc, local_dt, pinned=pinned)
                if pinned:
                    pinned_results.append(r)
                else:
                    regular_results.append(r)
                if len(pinned_results) + len(regular_results) >= self.max_results:
                    break
        return pinned_results + regular_results

    def execute(self, result: ProviderResult) -> bool:
        city = result.action_data.get("city", "")
        time_str = result.action_data.get("time", "")
        date_str = result.action_data.get("date", "")
        utc_str = result.action_data.get("utc", "")
        text = f"{city}: {time_str}, {date_str} ({utc_str})"
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
        return True

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        city = result.action_data.get("city", "")
        if not city:
            return []
        pinned = self.is_pinned(city)
        return [
            ProviderMenuAction(id="copy", label="Copy time"),
            ProviderMenuAction(id="toggle_pin", label="Unpin city" if pinned else "Pin city"),
        ]

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        city = result.action_data.get("city", "")
        if not city:
            return ProviderMenuActionResult()

        if action_id == "copy":
            time_str = result.action_data.get("time", "")
            date_str = result.action_data.get("date", "")
            utc_str = result.action_data.get("utc", "")
            text = f"{city}: {time_str}, {date_str} ({utc_str})"
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
            return ProviderMenuActionResult()

        if action_id == "toggle_pin":
            if self.is_pinned(city):
                self._pinned.remove(city)
            else:
                self._pinned.append(city)
            self._save_pinned()
            return ProviderMenuActionResult(refresh_results=True)

        return ProviderMenuActionResult()
