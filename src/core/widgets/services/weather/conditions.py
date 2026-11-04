"""Open-Meteo's WMO weather codes as a picture and a description."""

# Codes whose precipitation chance is a chance of rain, or of snow
RAIN_CODES = frozenset({51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82})
SNOW_CODES = frozenset({71, 73, 75, 77, 85, 86})

# The kind of sky, which takes Day or Night for its picture, and the description of each code
CONDITIONS: dict[int, tuple[str, str]] = {
    0: ("sunny", "Clear sky"),
    1: ("cloudy", "Mainly clear"),
    2: ("cloudy", "Partly cloudy"),
    3: ("cloudy", "Overcast"),
    45: ("foggy", "Fog"),
    48: ("foggy", "Depositing rime fog"),
    51: ("drizzle", "Light drizzle"),
    53: ("drizzle", "Moderate drizzle"),
    55: ("drizzle", "Dense drizzle"),
    56: ("drizzle", "Light freezing drizzle"),
    57: ("drizzle", "Dense freezing drizzle"),
    61: ("rainy", "Slight rain"),
    63: ("rainy", "Moderate rain"),
    65: ("rainy", "Heavy rain"),
    66: ("rainy", "Light freezing rain"),
    67: ("rainy", "Heavy freezing rain"),
    71: ("snowy", "Slight snow fall"),
    73: ("snowy", "Moderate snow fall"),
    75: ("snowy", "Heavy snow fall"),
    77: ("snowy", "Snow grains"),
    80: ("rainy", "Slight rain showers"),
    81: ("rainy", "Moderate rain showers"),
    82: ("rainy", "Violent rain showers"),
    85: ("snowy", "Slight snow showers"),
    86: ("snowy", "Heavy snow showers"),
    95: ("thunderstorm", "Thunderstorm"),
    96: ("thunderstorm", "Thunderstorm with slight hail"),
    99: ("thunderstorm", "Thunderstorm with heavy hail"),
}


def condition(code: int | None, is_day: bool) -> tuple[str, str]:
    """The picture, such as sunnyDay, clearNight or rainyNight, and the description of a weather code."""
    kind, text = CONDITIONS.get(code if code is not None else -1, ("", "Unknown"))
    if not kind:
        return "default", text
    if kind == "sunny" and not is_day:
        return "clearNight", text
    return f"{kind}{'Day' if is_day else 'Night'}", text
