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

SVG_SUNNY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="a" x1="213.99" x2="298.01" y1="183.24" y2="328.76" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#fbbf24"/><stop offset=".45" stop-color="#fbbf24"/><stop offset="1" stop-color="#f59e0b"/></linearGradient></defs><circle cx="256" cy="256" r="84" fill="url(#a)" stroke="#f8af18" stroke-miterlimit="10" stroke-width="6"/><path fill="none" stroke="#fbbf24" stroke-linecap="round" stroke-miterlimit="10" stroke-width="24" d="M256 125.66V76m0 360v-49.66m92.17-222.51 35.11-35.11M128.72 383.28l35.11-35.11m0-184.34L128.72 128.72m254.56 254.56-35.11-35.11M125.66 256H76m360 0h-49.66"/></svg>
"""

SVG_CLEAR_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="a" x1="175.33" x2="308.18" y1="150.03" y2="380.13" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#86c3db"/><stop offset=".45" stop-color="#86c3db"/><stop offset="1" stop-color="#5eafcf"/></linearGradient></defs><path fill="url(#a)" stroke="#72b9d5" stroke-linecap="round" stroke-linejoin="round" stroke-width="6" d="M373.25 289.63C299.13 289.63 239 230.35 239 157.21A130.48 130.48 0 0 1 243.47 124C176.29 131.25 124 187.37 124 255.58 124 328.71 184.09 388 258.21 388 320.69 388 373 345.82 388 288.79a135.56 135.56 0 0 1-14.75.84Z"/></svg>"""

SVG_CLOUDY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="a" x1="146" x2="186" y1="172.35" y2="241.65" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#fbbf24"/><stop offset=".45" stop-color="#fbbf24"/><stop offset="1" stop-color="#f59e0b"/></linearGradient><linearGradient id="b" x1="180.45" x2="313.64" y1="175.68" y2="406.37" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#f3f7fe"/><stop offset=".45" stop-color="#f3f7fe"/><stop offset="1" stop-color="#deeafb"/></linearGradient></defs><circle cx="166" cy="207" r="40" fill="url(#a)" stroke="#f8af18" stroke-miterlimit="10" stroke-width="4"/><path fill="none" stroke="#fbbf24" stroke-linecap="round" stroke-miterlimit="10" stroke-width="12" d="M166 140.38V115m0 184v-25.38m47.11-113.73L231.05 142M101 272.05l17.94-17.94m0-94.22L101 142m130.1 130.1-17.94-17.94M74 207h25.38M258 207h-25.38"/><path fill="url(#b)" stroke="#e6effc" stroke-miterlimit="10" stroke-width="6" d="M372 252c-.85 0-1.68.09-2.53.13A83.9 83.9 0 0 0 216.6 187.92 55.91 55.91 0 0 0 132 236a56.56 56.56 0 0 0 .8 9.08A60 60 0 0 0 144 364c1.35 0 2.67-.11 4-.2v.2h224a56 56 0 0 0 0-112Z"/></svg>"""

SVG_CLOUDY_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="a" x1="114.67" x2="199.21" y1="139.56" y2="285.99" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#86c3db"/><stop offset=".45" stop-color="#86c3db"/><stop offset="1" stop-color="#5eafcf"/></linearGradient><linearGradient id="b" x1="180.45" x2="313.64" y1="175.68" y2="406.37" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#f3f7fe"/><stop offset=".45" stop-color="#f3f7fe"/><stop offset="1" stop-color="#deeafb"/></linearGradient></defs><path fill="url(#a)" stroke="#72b9d5" stroke-linecap="round" stroke-linejoin="round" stroke-width="4" d="M240.62 228.4c-47.17 0-85.41-37.73-85.41-84.26A83.31 83.31 0 0 1 158 123C115.27 127.61 82 163.33 82 206.73 82 253.27 120.24 291 167.41 291A85.16 85.16 0 0 0 250 227.87a88 88 0 0 1-9.38.53Z"/><path fill="url(#b)" stroke="#e6effc" stroke-miterlimit="10" stroke-width="6" d="M372 252c-.85 0-1.68.09-2.53.13A83.9 83.9 0 0 0 216.6 187.92 55.91 55.91 0 0 0 132 236a56.56 56.56 0 0 0 .8 9.08A60 60 0 0 0 144 364c1.35 0 2.67-.11 4-.2v.2h224a56 56 0 0 0 0-112Z"/></svg>"""

SVG_FOGGY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="a" x1="213.99" x2="298.01" y1="183.24" y2="328.76" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#fbbf24"/><stop offset=".45" stop-color="#fbbf24"/><stop offset="1" stop-color="#f59e0b"/></linearGradient></defs><circle cx="256" cy="256" r="84" fill="url(#a)" stroke="#f8af18" stroke-miterlimit="10" stroke-width="6"/><path fill="none" stroke="#fbbf24" stroke-linecap="round" stroke-miterlimit="10" stroke-width="24" d="M256 125.66V76m0 360v-49.66m92.17-222.51 35.11-35.11M128.72 383.28l35.11-35.11m0-184.34L128.72 128.72m254.56 254.56-35.11-35.11M125.66 256H76m360 0h-49.66"/><path fill="none" stroke="#d4d7dd" stroke-linecap="round" stroke-miterlimit="10" stroke-width="24" d="M136 348h240"/><path fill="none" stroke="#bec1c6" stroke-linecap="round" stroke-miterlimit="10" stroke-width="24" d="M136 396h240"/></svg>"""

SVG_FOGGY_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="a" x1="175.33" x2="308.18" y1="150.03" y2="380.13" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#86c3db"/><stop offset=".45" stop-color="#86c3db"/><stop offset="1" stop-color="#5eafcf"/></linearGradient></defs><path fill="url(#a)" stroke="#72b9d5" stroke-linecap="round" stroke-linejoin="round" stroke-width="6" d="M373.25 289.63C299.13 289.63 239 230.35 239 157.21A130.48 130.48 0 0 1 243.47 124C176.29 131.25 124 187.37 124 255.58 124 328.71 184.09 388 258.21 388 320.69 388 373 345.82 388 288.79a135.56 135.56 0 0 1-14.75.84Z"/><path fill="none" stroke="#d4d7dd" stroke-linecap="round" stroke-miterlimit="10" stroke-width="24" d="M136 420h240"/><path fill="none" stroke="#bec1c6" stroke-linecap="round" stroke-miterlimit="10" stroke-width="24" d="M136 458h240"/></svg>"""

SVG_DRIZZLE_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="b" x1="180.45" x2="313.64" y1="175.68" y2="406.37" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#f3f7fe"/><stop offset=".45" stop-color="#f3f7fe"/><stop offset="1" stop-color="#deeafb"/></linearGradient></defs><path fill="url(#b)" stroke="#e6effc" stroke-miterlimit="10" stroke-width="6" d="M372 252c-.85 0-1.68.09-2.53.13A83.9 83.9 0 0 0 216.6 187.92 55.91 55.91 0 0 0 132 236a56.56 56.56 0 0 0 .8 9.08A60 60 0 0 0 144 364c1.35 0 2.67-.11 4-.2v.2h224a56 56 0 0 0 0-112Z"/><path fill="#0a5ad4" stroke="#0a5ad4" stroke-miterlimit="10" d="M200 376a8 8 0 0 1-8-8v-12a8 8 0 0 1 16 0v12a8 8 0 0 1-8 8Z"/><path fill="#0a5ad4" stroke="#0a5ad4" stroke-miterlimit="10" d="M256 456a8 8 0 0 1-8-8v-12a8 8 0 0 1 16 0v12a8 8 0 0 1-8 8Z"/><path fill="#0a5ad4" stroke="#0a5ad4" stroke-miterlimit="10" d="M312 406a8 8 0 0 1-8-8v-12a8 8 0 0 1 16 0v12a8 8 0 0 1-8 8Z"/></svg>"""

SVG_DRIZZLE_NIGHT = SVG_DRIZZLE_DAY

SVG_RAINY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="b" x1="180.45" x2="313.64" y1="175.68" y2="406.37" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#f3f7fe"/><stop offset=".45" stop-color="#f3f7fe"/><stop offset="1" stop-color="#deeafb"/></linearGradient></defs><path fill="url(#b)" stroke="#e6effc" stroke-miterlimit="10" stroke-width="6" d="M372 252c-.85 0-1.68.09-2.53.13A83.9 83.9 0 0 0 216.6 187.92 55.91 55.91 0 0 0 132 236a56.56 56.56 0 0 0 .8 9.08A60 60 0 0 0 144 364c1.35 0 2.67-.11 4-.2v.2h224a56 56 0 0 0 0-112Z"/><path fill="#0a5ad4" stroke="#0a5ad4" stroke-miterlimit="10" d="M200 400a8 8 0 0 1-8-8v-40a8 8 0 0 1 16 0v40a8 8 0 0 1-8 8Z"/><path fill="#0a5ad4" stroke="#0a5ad4" stroke-miterlimit="10" d="M256 453a8 8 0 0 1-8-8v-40a8 8 0 0 1 16 0v40a8 8 0 0 1-8 8Z"/><path fill="#0a5ad4" stroke="#0a5ad4" stroke-miterlimit="10" d="M312 418a8 8 0 0 1-8-8v-40a8 8 0 0 1 16 0v40a8 8 0 0 1-8 8Z"/></svg>"""

SVG_RAINY_NIGHT = SVG_RAINY_DAY

SVG_SNOWY_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="b" x1="180.45" x2="313.64" y1="175.68" y2="406.37" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#f3f7fe"/><stop offset=".45" stop-color="#f3f7fe"/><stop offset="1" stop-color="#deeafb"/></linearGradient></defs><path fill="url(#b)" stroke="#e6effc" stroke-miterlimit="10" stroke-width="6" d="M372 252c-.85 0-1.68.09-2.53.13A83.9 83.9 0 0 0 216.6 187.92 55.91 55.91 0 0 0 132 236a56.56 56.56 0 0 0 .8 9.08A60 60 0 0 0 144 364c1.35 0 2.67-.11 4-.2v.2h224a56 56 0 0 0 0-112Z"/><g stroke="#86c3db" stroke-width="5" stroke-linecap="round"><line x1="200" y1="383" x2="200" y2="407"/><line x1="188" y1="389" x2="212" y2="401"/><line x1="188" y1="401" x2="212" y2="389"/></g><g stroke="#86c3db" stroke-width="5" stroke-linecap="round"><line x1="256" y1="425" x2="256" y2="461"/><line x1="243" y1="432" x2="269" y2="454"/><line x1="243" y1="454" x2="269" y2="432"/></g><g stroke="#86c3db" stroke-width="5" stroke-linecap="round"><line x1="312" y1="390" x2="312" y2="414"/><line x1="300" y1="396" x2="324" y2="408"/><line x1="300" y1="408" x2="324" y2="396"/></g></svg>"""

SVG_SNOWY_NIGHT = SVG_SNOWY_DAY

SVG_THUNDERSTORM_DAY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="a" x1="146" x2="186" y1="172.35" y2="241.65" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#fbbf24"/><stop offset=".45" stop-color="#fbbf24"/><stop offset="1" stop-color="#f59e0b"/></linearGradient><linearGradient id="b" x1="180.45" x2="313.64" y1="175.68" y2="406.37" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#f3f7fe"/><stop offset=".45" stop-color="#f3f7fe"/><stop offset="1" stop-color="#deeafb"/></linearGradient><linearGradient id="e" x1="213.9" x2="286.11" y1="308.07" y2="433.14" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#f7b23b"/><stop offset=".45" stop-color="#f7b23b"/><stop offset="1" stop-color="#f59e0b"/></linearGradient></defs><circle cx="166" cy="207" r="40" fill="url(#a)" stroke="#f8af18" stroke-miterlimit="10" stroke-width="4"/><path fill="none" stroke="#fbbf24" stroke-linecap="round" stroke-miterlimit="10" stroke-width="12" d="M166 140.38V115m0 184v-25.38m47.11-113.73L231.05 142M101 272.05l17.94-17.94m0-94.22L101 142m130.1 130.1-17.94-17.94M74 207h25.38M258 207h-25.38"/><path fill="url(#b)" stroke="#e6effc" stroke-miterlimit="10" stroke-width="6" d="M372 252c-.85 0-1.68.09-2.53.13A83.9 83.9 0 0 0 216.6 187.92 55.91 55.91 0 0 0 132 236a56.56 56.56 0 0 0 .8 9.08A60 60 0 0 0 144 364c1.35 0 2.67-.11 4-.2v.2h224a56 56 0 0 0 0-112Z"/><path fill="url(#e)" stroke="#f6a823" stroke-miterlimit="10" stroke-width="4" d="M240 293 L208 389 H240 L224 469 L304 357 H256 L288 293 Z"/></svg>"""

SVG_THUNDERSTORM_NIGHT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="a" x1="114.67" x2="199.21" y1="139.56" y2="285.99" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#86c3db"/><stop offset=".45" stop-color="#86c3db"/><stop offset="1" stop-color="#5eafcf"/></linearGradient><linearGradient id="b" x1="180.45" x2="313.64" y1="175.68" y2="406.37" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#f3f7fe"/><stop offset=".45" stop-color="#f3f7fe"/><stop offset="1" stop-color="#deeafb"/></linearGradient><linearGradient id="e" x1="213.9" x2="286.11" y1="308.07" y2="433.14" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#f7b23b"/><stop offset=".45" stop-color="#f7b23b"/><stop offset="1" stop-color="#f59e0b"/></linearGradient></defs><path fill="url(#a)" stroke="#72b9d5" stroke-linecap="round" stroke-linejoin="round" stroke-width="4" d="M240.62 228.4c-47.17 0-85.41-37.73-85.41-84.26A83.31 83.31 0 0 1 158 123C115.27 127.61 82 163.33 82 206.73 82 253.27 120.24 291 167.41 291A85.16 85.16 0 0 0 250 227.87a88 88 0 0 1-9.38.53Z"/><path fill="url(#b)" stroke="#e6effc" stroke-miterlimit="10" stroke-width="6" d="M372 252c-.85 0-1.68.09-2.53.13A83.9 83.9 0 0 0 216.6 187.92 55.91 55.91 0 0 0 132 236a56.56 56.56 0 0 0 .8 9.08A60 60 0 0 0 144 364c1.35 0 2.67-.11 4-.2v.2h224a56 56 0 0 0 0-112Z"/><path fill="url(#e)" stroke="#f6a823" stroke-miterlimit="10" stroke-width="4" d="M240 293 L208 389 H240 L224 469 L304 357 H256 L288 293 Z"/></svg>"""

SVG_DEFAULT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="b" x1="180.45" x2="313.64" y1="175.68" y2="406.37" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#f3f7fe"/><stop offset=".45" stop-color="#f3f7fe"/><stop offset="1" stop-color="#deeafb"/></linearGradient></defs><path fill="url(#b)" stroke="#e6effc" stroke-miterlimit="10" stroke-width="6" d="M372 252c-.85 0-1.68.09-2.53.13A83.9 83.9 0 0 0 216.6 187.92 55.91 55.91 0 0 0 132 236a56.56 56.56 0 0 0 .8 9.08A60 60 0 0 0 144 364c1.35 0 2.67-.11 4-.2v.2h224a56 56 0 0 0 0-112Z"/></svg>"""


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
