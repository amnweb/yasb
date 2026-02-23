"""
Inline SVG weather icons and WMO weather code mapping for OpenMeteoWidget.

WMO Weather interpretation codes (WW):
  0: Clear sky
  1, 2, 3: Mainly clear, Partly cloudy, Overcast
  45, 48: Fog, Depositing rime fog
  51, 53, 55: Drizzle (light, moderate, dense)
  56, 57: Freezing drizzle (light, dense)
  61, 63, 65: Rain (slight, moderate, heavy)
  66, 67: Freezing rain (light, heavy)
  71, 73, 75: Snow fall (slight, moderate, heavy)
  77: Snow grains
  80, 81, 82: Rain showers (slight, moderate, violent)
  85, 86: Snow showers (slight, heavy)
  95: Thunderstorm (slight or moderate)
  96, 99: Thunderstorm with hail (slight, heavy)
"""

#  SVG Icon Constants

SVG_SUNNY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <circle cx="32" cy="32" r="14" fill="#FFD93D" stroke="#F4A900" stroke-width="2"/>
  <g stroke="#FFD93D" stroke-width="2.5" stroke-linecap="round">
    <line x1="32" y1="4" x2="32" y2="12"/>
    <line x1="32" y1="52" x2="32" y2="60"/>
    <line x1="4" y1="32" x2="12" y2="32"/>
    <line x1="52" y1="32" x2="60" y2="32"/>
    <line x1="12.2" y1="12.2" x2="17.9" y2="17.9"/>
    <line x1="46.1" y1="46.1" x2="51.8" y2="51.8"/>
    <line x1="12.2" y1="51.8" x2="17.9" y2="46.1"/>
    <line x1="46.1" y1="17.9" x2="51.8" y2="12.2"/>
  </g>
</svg>"""

SVG_CLEAR_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M38 10 A22 22 0 1 0 54 38 A17 17 0 1 1 38 10Z" fill="#C4C9D4" stroke="#A0A8B8" stroke-width="1.5"/>
  <circle cx="48" cy="12" r="1.5" fill="#E8E8E8"/>
  <circle cx="54" cy="22" r="1" fill="#E8E8E8"/>
  <circle cx="44" cy="6" r="1" fill="#E8E8E8"/>
</svg>"""

SVG_CLOUDY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <circle cx="22" cy="22" r="10" fill="#FFD93D" stroke="#F4A900" stroke-width="1.5"/>
  <g stroke="#FFD93D" stroke-width="2" stroke-linecap="round">
    <line x1="22" y1="6" x2="22" y2="10"/>
    <line x1="22" y1="34" x2="22" y2="38"/>
    <line x1="6" y1="22" x2="10" y2="22"/>
    <line x1="34" y1="22" x2="38" y2="22"/>
    <line x1="10.7" y1="10.7" x2="13.5" y2="13.5"/>
    <line x1="30.5" y1="30.5" x2="33.3" y2="33.3"/>
    <line x1="10.7" y1="33.3" x2="13.5" y2="30.5"/>
    <line x1="30.5" y1="13.5" x2="33.3" y2="10.7"/>
  </g>
  <path d="M20 52 Q20 42 28 40 Q30 32 38 30 Q48 30 50 38 Q58 38 58 46 Q58 52 52 52Z" fill="#B0BEC5" stroke="#90A4AE" stroke-width="1.5"/>
</svg>"""

SVG_CLOUDY_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M16 18 A10 10 0 1 0 28 26 A7 7 0 1 1 16 18Z" fill="#C4C9D4" stroke="#A0A8B8" stroke-width="1"/>
  <path d="M20 52 Q20 42 28 40 Q30 32 38 30 Q48 30 50 38 Q58 38 58 46 Q58 52 52 52Z" fill="#90A4AE" stroke="#78909C" stroke-width="1.5"/>
</svg>"""

SVG_FOGGY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <circle cx="24" cy="16" r="8" fill="#FFD93D" opacity="0.5"/>
  <g stroke="#B0BEC5" stroke-width="3" stroke-linecap="round" opacity="0.8">
    <line x1="10" y1="30" x2="54" y2="30"/>
    <line x1="14" y1="38" x2="50" y2="38"/>
    <line x1="10" y1="46" x2="54" y2="46"/>
    <line x1="18" y1="54" x2="46" y2="54"/>
  </g>
</svg>"""

SVG_FOGGY_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M20 12 A7 7 0 1 0 30 18 A5 5 0 1 1 20 12Z" fill="#C4C9D4" opacity="0.5"/>
  <g stroke="#90A4AE" stroke-width="3" stroke-linecap="round" opacity="0.8">
    <line x1="10" y1="30" x2="54" y2="30"/>
    <line x1="14" y1="38" x2="50" y2="38"/>
    <line x1="10" y1="46" x2="54" y2="46"/>
    <line x1="18" y1="54" x2="46" y2="54"/>
  </g>
</svg>"""

SVG_DRIZZLE_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <circle cx="20" cy="14" r="7" fill="#FFD93D" stroke="#F4A900" stroke-width="1"/>
  <path d="M16 42 Q16 34 22 32 Q24 26 30 24 Q38 24 40 30 Q46 30 46 36 Q46 42 40 42Z" fill="#B0BEC5" stroke="#90A4AE" stroke-width="1.5"/>
  <g stroke="#64B5F6" stroke-width="1.5" stroke-linecap="round">
    <line x1="24" y1="46" x2="23" y2="50"/>
    <line x1="32" y1="46" x2="31" y2="50"/>
    <line x1="28" y1="52" x2="27" y2="56"/>
  </g>
</svg>"""

SVG_DRIZZLE_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M14 10 A6 6 0 1 0 24 16 A4 4 0 1 1 14 10Z" fill="#C4C9D4" stroke="#A0A8B8" stroke-width="0.8"/>
  <path d="M16 42 Q16 34 22 32 Q24 26 30 24 Q38 24 40 30 Q46 30 46 36 Q46 42 40 42Z" fill="#90A4AE" stroke="#78909C" stroke-width="1.5"/>
  <g stroke="#5C9FD4" stroke-width="1.5" stroke-linecap="round">
    <line x1="24" y1="46" x2="23" y2="50"/>
    <line x1="32" y1="46" x2="31" y2="50"/>
    <line x1="28" y1="52" x2="27" y2="56"/>
  </g>
</svg>"""

SVG_RAINY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <circle cx="20" cy="14" r="7" fill="#FFD93D" stroke="#F4A900" stroke-width="1"/>
  <path d="M14 40 Q14 32 20 30 Q22 24 28 22 Q36 22 38 28 Q44 28 44 34 Q44 40 38 40Z" fill="#B0BEC5" stroke="#90A4AE" stroke-width="1.5"/>
  <g stroke="#42A5F5" stroke-width="2" stroke-linecap="round">
    <line x1="20" y1="44" x2="18" y2="52"/>
    <line x1="28" y1="44" x2="26" y2="52"/>
    <line x1="36" y1="44" x2="34" y2="52"/>
    <line x1="24" y1="54" x2="22" y2="60"/>
    <line x1="32" y1="54" x2="30" y2="60"/>
  </g>
</svg>"""

SVG_RAINY_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M14 10 A6 6 0 1 0 24 16 A4 4 0 1 1 14 10Z" fill="#C4C9D4" stroke="#A0A8B8" stroke-width="0.8"/>
  <path d="M14 40 Q14 32 20 30 Q22 24 28 22 Q36 22 38 28 Q44 28 44 34 Q44 40 38 40Z" fill="#90A4AE" stroke="#78909C" stroke-width="1.5"/>
  <g stroke="#3D8FCC" stroke-width="2" stroke-linecap="round">
    <line x1="20" y1="44" x2="18" y2="52"/>
    <line x1="28" y1="44" x2="26" y2="52"/>
    <line x1="36" y1="44" x2="34" y2="52"/>
    <line x1="24" y1="54" x2="22" y2="60"/>
    <line x1="32" y1="54" x2="30" y2="60"/>
  </g>
</svg>"""

SVG_SNOWY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <circle cx="20" cy="14" r="7" fill="#FFD93D" stroke="#F4A900" stroke-width="1"/>
  <path d="M14 38 Q14 30 20 28 Q22 22 28 20 Q36 20 38 26 Q44 26 44 32 Q44 38 38 38Z" fill="#B0BEC5" stroke="#90A4AE" stroke-width="1.5"/>
  <g fill="#E0E0E0">
    <circle cx="20" cy="46" r="2.5"/>
    <circle cx="30" cy="44" r="2"/>
    <circle cx="38" cy="48" r="2.5"/>
    <circle cx="24" cy="54" r="2"/>
    <circle cx="34" cy="56" r="2.5"/>
  </g>
</svg>"""

SVG_SNOWY_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M14 10 A6 6 0 1 0 24 16 A4 4 0 1 1 14 10Z" fill="#C4C9D4" stroke="#A0A8B8" stroke-width="0.8"/>
  <path d="M14 38 Q14 30 20 28 Q22 22 28 20 Q36 20 38 26 Q44 26 44 32 Q44 38 38 38Z" fill="#90A4AE" stroke="#78909C" stroke-width="1.5"/>
  <g fill="#D0D0D0">
    <circle cx="20" cy="46" r="2.5"/>
    <circle cx="30" cy="44" r="2"/>
    <circle cx="38" cy="48" r="2.5"/>
    <circle cx="24" cy="54" r="2"/>
    <circle cx="34" cy="56" r="2.5"/>
  </g>
</svg>"""

SVG_THUNDERSTORM_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M12 38 Q12 28 20 26 Q22 18 30 16 Q40 16 42 24 Q50 24 50 32 Q50 38 44 38Z" fill="#78909C" stroke="#607D8B" stroke-width="1.5"/>
  <polygon points="30,38 24,50 30,50 26,62 38,46 32,46 36,38" fill="#FFD93D" stroke="#F4A900" stroke-width="0.8"/>
  <g stroke="#42A5F5" stroke-width="1.5" stroke-linecap="round">
    <line x1="16" y1="42" x2="14" y2="50"/>
    <line x1="44" y1="42" x2="42" y2="50"/>
  </g>
</svg>"""

SVG_THUNDERSTORM_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M12 38 Q12 28 20 26 Q22 18 30 16 Q40 16 42 24 Q50 24 50 32 Q50 38 44 38Z" fill="#607D8B" stroke="#546E7A" stroke-width="1.5"/>
  <polygon points="30,38 24,50 30,50 26,62 38,46 32,46 36,38" fill="#FFD93D" stroke="#F4A900" stroke-width="0.8"/>
  <g stroke="#3D8FCC" stroke-width="1.5" stroke-linecap="round">
    <line x1="16" y1="42" x2="14" y2="50"/>
    <line x1="44" y1="42" x2="42" y2="50"/>
  </g>
</svg>"""

SVG_DEFAULT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M16 46 Q16 36 24 34 Q26 26 34 24 Q44 24 46 32 Q54 32 54 40 Q54 46 48 46Z" fill="#B0BEC5" stroke="#90A4AE" stroke-width="1.5"/>
</svg>"""


# Maps icon key names to SVG strings
ICON_MAP: dict[str, str] = {
    "sunnyDay": SVG_SUNNY_DAY,
    "clearNight": SVG_CLEAR_NIGHT,
    "cloudyDay": SVG_CLOUDY_DAY,
    "cloudyNight": SVG_CLOUDY_NIGHT,
    "foggyDay": SVG_FOGGY_DAY,
    "foggyNight": SVG_FOGGY_NIGHT,
    "drizzleDay": SVG_DRIZZLE_DAY,
    "drizzleNight": SVG_DRIZZLE_NIGHT,
    "rainyDay": SVG_RAINY_DAY,
    "rainyNight": SVG_RAINY_NIGHT,
    "snowyDay": SVG_SNOWY_DAY,
    "snowyNight": SVG_SNOWY_NIGHT,
    "thunderstormDay": SVG_THUNDERSTORM_DAY,
    "thunderstormNight": SVG_THUNDERSTORM_NIGHT,
    "default": SVG_DEFAULT,
}


def get_weather_icon(code: int, is_day: bool) -> tuple[str, str, str]:
    """Map a WMO weather code to an SVG icon, CSS class name, and description.

    Args:
        code: WMO weather interpretation code (0-99).
        is_day: True for daytime, False for nighttime.

    Returns:
        Tuple of (svg_string, icon_class_name, description_text).
    """
    time = "Day" if is_day else "Night"

    # Clear sky
    if code == 0:
        if is_day:
            return ICON_MAP["sunnyDay"], "sunnyDay", "Clear sky"
        return ICON_MAP["clearNight"], "clearNight", "Clear sky"

    # Mainly clear, Partly cloudy, Overcast
    if code in {1, 2, 3}:
        key = f"cloudy{time}"
        descriptions = {1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast"}
        return ICON_MAP[key], key, descriptions.get(code, "Cloudy")

    # Fog
    if code in {45, 48}:
        key = f"foggy{time}"
        desc = "Fog" if code == 45 else "Depositing rime fog"
        return ICON_MAP[key], key, desc

    # Drizzle
    if code in {51, 53, 55, 56, 57}:
        key = f"drizzle{time}"
        descriptions = {
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
        }
        return ICON_MAP[key], key, descriptions.get(code, "Drizzle")

    # Rain
    if code in {61, 63, 65, 66, 67}:
        key = f"rainy{time}"
        descriptions = {
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
        }
        return ICON_MAP[key], key, descriptions.get(code, "Rain")

    # Snow
    if code in {71, 73, 75, 77}:
        key = f"snowy{time}"
        descriptions = {
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
        }
        return ICON_MAP[key], key, descriptions.get(code, "Snow")

    # Rain showers
    if code in {80, 81, 82}:
        key = f"rainy{time}"
        descriptions = {
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
        }
        return ICON_MAP[key], key, descriptions.get(code, "Rain showers")

    # Snow showers
    if code in {85, 86}:
        key = f"snowy{time}"
        desc = "Slight snow showers" if code == 85 else "Heavy snow showers"
        return ICON_MAP[key], key, desc

    # Thunderstorm
    if code in {95, 96, 99}:
        key = f"thunderstorm{time}"
        descriptions = {
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return ICON_MAP[key], key, descriptions.get(code, "Thunderstorm")

    # Default fallback
    return ICON_MAP["default"], "default", "Unknown"
