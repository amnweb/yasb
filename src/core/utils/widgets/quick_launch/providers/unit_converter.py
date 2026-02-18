import re

from PyQt6.QtWidgets import QApplication

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_UNIT

# Each category maps unit aliases to (canonical_name, factor_to_base).

_LENGTH = {
    "mm": ("Millimeters", 0.001),
    "millimeter": ("Millimeters", 0.001),
    "millimeters": ("Millimeters", 0.001),
    "cm": ("Centimeters", 0.01),
    "centimeter": ("Centimeters", 0.01),
    "centimeters": ("Centimeters", 0.01),
    "m": ("Meters", 1.0),
    "meter": ("Meters", 1.0),
    "meters": ("Meters", 1.0),
    "km": ("Kilometers", 1000.0),
    "kilometer": ("Kilometers", 1000.0),
    "kilometers": ("Kilometers", 1000.0),
    "in": ("Inches", 0.0254),
    "inch": ("Inches", 0.0254),
    "inches": ("Inches", 0.0254),
    "ft": ("Feet", 0.3048),
    "foot": ("Feet", 0.3048),
    "feet": ("Feet", 0.3048),
    "yd": ("Yards", 0.9144),
    "yard": ("Yards", 0.9144),
    "yards": ("Yards", 0.9144),
    "mi": ("Miles", 1609.344),
    "mile": ("Miles", 1609.344),
    "miles": ("Miles", 1609.344),
    "nmi": ("Nautical miles", 1852.0),
}

_WEIGHT = {
    "mg": ("Milligrams", 0.001),
    "milligram": ("Milligrams", 0.001),
    "milligrams": ("Milligrams", 0.001),
    "g": ("Grams", 1.0),
    "gram": ("Grams", 1.0),
    "grams": ("Grams", 1.0),
    "kg": ("Kilograms", 1000.0),
    "kilogram": ("Kilograms", 1000.0),
    "kilograms": ("Kilograms", 1000.0),
    "t": ("Metric tons", 1_000_000.0),
    "ton": ("Metric tons", 1_000_000.0),
    "tons": ("Metric tons", 1_000_000.0),
    "oz": ("Ounces", 28.3495),
    "ounce": ("Ounces", 28.3495),
    "ounces": ("Ounces", 28.3495),
    "lb": ("Pounds", 453.592),
    "lbs": ("Pounds", 453.592),
    "pound": ("Pounds", 453.592),
    "pounds": ("Pounds", 453.592),
    "st": ("Stones", 6350.29),
    "stone": ("Stones", 6350.29),
    "stones": ("Stones", 6350.29),
}

_VOLUME = {
    "ml": ("Milliliters", 0.001),
    "milliliter": ("Milliliters", 0.001),
    "milliliters": ("Milliliters", 0.001),
    "l": ("Liters", 1.0),
    "liter": ("Liters", 1.0),
    "liters": ("Liters", 1.0),
    "gal": ("Gallons (US)", 3.78541),
    "gallon": ("Gallons (US)", 3.78541),
    "gallons": ("Gallons (US)", 3.78541),
    "qt": ("Quarts (US)", 0.946353),
    "quart": ("Quarts (US)", 0.946353),
    "quarts": ("Quarts (US)", 0.946353),
    "pt": ("Pints (US)", 0.473176),
    "pint": ("Pints (US)", 0.473176),
    "pints": ("Pints (US)", 0.473176),
    "cup": ("Cups (US)", 0.236588),
    "cups": ("Cups (US)", 0.236588),
    "floz": ("Fluid ounces (US)", 0.0295735),
    "fl oz": ("Fluid ounces (US)", 0.0295735),
    "tbsp": ("Tablespoons", 0.0147868),
    "tablespoon": ("Tablespoons", 0.0147868),
    "tablespoons": ("Tablespoons", 0.0147868),
    "tsp": ("Teaspoons", 0.00492892),
    "teaspoon": ("Teaspoons", 0.00492892),
    "teaspoons": ("Teaspoons", 0.00492892),
}

_SPEED = {
    "m/s": ("m/s", 1.0),
    "km/h": ("km/h", 1 / 3.6),
    "kmh": ("km/h", 1 / 3.6),
    "kph": ("km/h", 1 / 3.6),
    "mph": ("mph", 0.44704),
    "knot": ("Knots", 0.514444),
    "knots": ("Knots", 0.514444),
    "kn": ("Knots", 0.514444),
    "ft/s": ("ft/s", 0.3048),
}

_DATA = {
    "b": ("Bytes", 1),
    "byte": ("Bytes", 1),
    "bytes": ("Bytes", 1),
    "kb": ("Kilobytes", 1024),
    "kilobyte": ("Kilobytes", 1024),
    "kilobytes": ("Kilobytes", 1024),
    "mb": ("Megabytes", 1024**2),
    "megabyte": ("Megabytes", 1024**2),
    "megabytes": ("Megabytes", 1024**2),
    "gb": ("Gigabytes", 1024**3),
    "gigabyte": ("Gigabytes", 1024**3),
    "gigabytes": ("Gigabytes", 1024**3),
    "tb": ("Terabytes", 1024**4),
    "terabyte": ("Terabytes", 1024**4),
    "terabytes": ("Terabytes", 1024**4),
    "pb": ("Petabytes", 1024**5),
    "petabyte": ("Petabytes", 1024**5),
    "petabytes": ("Petabytes", 1024**5),
}

_TIME = {
    "ms": ("Milliseconds", 0.001),
    "millisecond": ("Milliseconds", 0.001),
    "milliseconds": ("Milliseconds", 0.001),
    "s": ("Seconds", 1.0),
    "sec": ("Seconds", 1.0),
    "second": ("Seconds", 1.0),
    "seconds": ("Seconds", 1.0),
    "min": ("Minutes", 60.0),
    "minute": ("Minutes", 60.0),
    "minutes": ("Minutes", 60.0),
    "h": ("Hours", 3600.0),
    "hr": ("Hours", 3600.0),
    "hour": ("Hours", 3600.0),
    "hours": ("Hours", 3600.0),
    "d": ("Days", 86400.0),
    "day": ("Days", 86400.0),
    "days": ("Days", 86400.0),
    "wk": ("Weeks", 604800.0),
    "week": ("Weeks", 604800.0),
    "weeks": ("Weeks", 604800.0),
    "yr": ("Years", 31_557_600.0),
    "year": ("Years", 31_557_600.0),
    "years": ("Years", 31_557_600.0),
}

_CATEGORIES: list[tuple[str, dict]] = [
    ("Length", _LENGTH),
    ("Weight", _WEIGHT),
    ("Volume", _VOLUME),
    ("Speed", _SPEED),
    ("Data", _DATA),
    ("Time", _TIME),
]

# Temperature needs special handling since it's not a simple factor conversion
_TEMP_UNITS = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}


def _to_celsius(value: float, unit: str) -> float:
    u = unit.lower()
    if u in ("f", "fahrenheit"):
        return (value - 32) * 5 / 9
    if u in ("k", "kelvin"):
        return value - 273.15
    return value


def _from_celsius(c: float, unit: str) -> float:
    u = unit.lower()
    if u in ("f", "fahrenheit"):
        return c * 9 / 5 + 32
    if u in ("k", "kelvin"):
        return c + 273.15
    return c


_TEMP_LABELS = {
    "c": "Celsius",
    "celsius": "Celsius",
    "f": "Fahrenheit",
    "fahrenheit": "Fahrenheit",
    "k": "Kelvin",
    "kelvin": "Kelvin",
}

# Canonical unit for each temp label (used for "auto" conversions)
_TEMP_OTHERS = {
    "Celsius": [("Fahrenheit", "f"), ("Kelvin", "k")],
    "Fahrenheit": [("Celsius", "c"), ("Kelvin", "k")],
    "Kelvin": [("Celsius", "c"), ("Fahrenheit", "f")],
}

# Pattern: "10 kg to lb" or "10kg lb" or "10 km"
_QUERY_RE = re.compile(
    r"^([\d.,]+)\s*([a-z/\s]+?)(?:\s+(?:to|in|as|->)\s+([a-z/\s]+?))?$",
    re.IGNORECASE,
)


def _find_category(unit: str) -> tuple[str, dict, str, float] | None:
    """Return (category_name, table, canonical_name, factor) or None."""
    u = unit.lower().strip()
    for cat_name, table in _CATEGORIES:
        if u in table:
            name, factor = table[u]
            return cat_name, table, name, factor
    return None


def _format_number(value: float) -> str:
    if value == 0:
        return "0"
    if abs(value) >= 1e12 or (abs(value) < 1e-6 and value != 0):
        return f"{value:.6g}"
    if value == int(value) and abs(value) < 1e15:
        return f"{int(value):,}"
    # Reasonable decimal places
    if abs(value) < 0.01:
        return f"{value:.6f}".rstrip("0").rstrip(".")
    if abs(value) < 1:
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return f"{value:,.4f}".rstrip("0").rstrip(".")


def _get_common_targets(category: str, table: dict, from_canonical: str) -> list[tuple[str, float]]:
    """Return a list of (canonical_name, factor) for common units other than from_canonical."""
    seen = set()
    targets = []
    for name, factor in table.values():
        if name != from_canonical and name not in seen:
            seen.add(name)
            targets.append((name, factor))
    return targets[:6]


class UnitConverterProvider(BaseProvider):
    """Convert between units of measurement."""

    name = "unit_converter"
    display_name = "Unit Converter"
    input_placeholder = "Convert units, e.g. 10 kg to lb..."
    icon = ICON_UNIT

    def match(self, text: str) -> bool:
        text = text.strip()
        if self.prefix and text.startswith(self.prefix):
            return True
        return False

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).strip()
        if not query:
            return [
                ProviderResult(
                    title="Unit Converter",
                    description="e.g. 10 kg to lb, 100 mi to km, 72 f to c, 1 gb to mb",
                    icon_char=ICON_UNIT,
                    provider=self.name,
                )
            ]

        m = _QUERY_RE.match(query)
        if not m:
            return [
                ProviderResult(
                    title="Invalid format",
                    description="Try: 10 kg to lb, 100 f to c, 500 mb to gb",
                    icon_char=ICON_UNIT,
                    provider=self.name,
                )
            ]

        value_str, from_unit, to_unit = m.group(1), m.group(2).strip(), (m.group(3) or "").strip()
        try:
            value = float(value_str.replace(",", ""))
        except ValueError:
            return []

        from_lower = from_unit.lower()
        to_lower = to_unit.lower() if to_unit else ""

        # Temperature
        if from_lower in _TEMP_UNITS:
            return self._convert_temperature(value, from_lower, to_lower)

        # Factor-based categories
        info = _find_category(from_lower)
        if not info:
            return [
                ProviderResult(
                    title=f"Unknown unit: {from_unit}",
                    description="Supported: length, weight, volume, speed, data, time, temperature",
                    icon_char=ICON_UNIT,
                    provider=self.name,
                )
            ]
        cat_name, table, from_name, from_factor = info

        if to_lower:
            to_info = _find_category(to_lower)
            if not to_info or to_info[0] != cat_name:
                return [
                    ProviderResult(
                        title=f"Cannot convert {from_name} to {to_unit}",
                        description=f"Both units must be in the same category ({cat_name})",
                        icon_char=ICON_UNIT,
                        provider=self.name,
                    )
                ]
            _, _, to_name, to_factor = to_info
            converted = value * from_factor / to_factor
            display = _format_number(converted)
            return [
                ProviderResult(
                    title=f"{display} {to_name}",
                    description=f"{_format_number(value)} {from_name} - press Enter to copy",
                    icon_char=ICON_UNIT,
                    provider=self.name,
                    action_data={"value": display},
                )
            ]

        # No target unit - show conversions to common units in the same category
        targets = _get_common_targets(cat_name, table, from_name)
        results = []
        for to_name, to_factor in targets:
            converted = value * from_factor / to_factor
            display = _format_number(converted)
            results.append(
                ProviderResult(
                    title=f"{display} {to_name}",
                    description=f"{_format_number(value)} {from_name} - press Enter to copy",
                    icon_char=ICON_UNIT,
                    provider=self.name,
                    action_data={"value": display},
                )
            )
        return results

    def _convert_temperature(self, value: float, from_lower: str, to_lower: str) -> list[ProviderResult]:
        from_label = _TEMP_LABELS[from_lower]
        celsius = _to_celsius(value, from_lower)

        if to_lower and to_lower in _TEMP_UNITS:
            to_label = _TEMP_LABELS[to_lower]
            converted = _from_celsius(celsius, to_lower)
            display = _format_number(converted)
            return [
                ProviderResult(
                    title=f"{display} {to_label}",
                    description=f"{_format_number(value)} {from_label} - press Enter to copy",
                    icon_char=ICON_UNIT,
                    provider=self.name,
                    action_data={"value": display},
                )
            ]

        # No target - show all other temperature units
        results = []
        for to_label, to_key in _TEMP_OTHERS[from_label]:
            converted = _from_celsius(celsius, to_key)
            display = _format_number(converted)
            results.append(
                ProviderResult(
                    title=f"{display} {to_label}",
                    description=f"{_format_number(value)} {from_label} - press Enter to copy",
                    icon_char=ICON_UNIT,
                    provider=self.name,
                    action_data={"value": display},
                )
            )
        return results

    def execute(self, result: ProviderResult) -> bool:
        value = result.action_data.get("value", "")
        if value:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(value)
        return True
