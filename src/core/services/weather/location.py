"""The place each location id shows and its last forecast, kept in weather.json in YASB's app data folder."""

import json
import logging
import time
from typing import Any, cast

from core.utils.system import app_data_path

LOCATION_FILE = "weather.json"
# What a place keeps of the geocoding result it was picked from
PLACE_FIELDS = ("name", "latitude", "longitude", "country", "admin1", "admin2", "admin3", "timezone")
COORDINATES = ("latitude", "longitude")


def _object(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _read() -> dict[str, Any]:
    path = app_data_path(LOCATION_FILE)
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        logging.warning("Could not read %s: %s", path, e)
        return {}
    return _object(data)


def _write(data: dict[str, Any]) -> None:
    path = app_data_path(LOCATION_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logging.error("Could not write %s: %s", path, e)


def _entry(location_id: str) -> dict[str, Any]:
    return _object(_read().get(location_id))


def has_coordinates(place: dict[str, Any]) -> bool:
    return all(isinstance(place.get(field), int | float) for field in COORDINATES)


def place_fields(source: dict[str, Any]) -> dict[str, Any]:
    place = {field: source.get(field) or "" for field in PLACE_FIELDS}
    place.update({field: source[field] for field in COORDINATES})
    return place


def region(place: dict[str, Any]) -> str:
    """Where a place lies, such as "Île-de-France, France"."""
    parts: list[str] = []
    for field in ("admin3", "admin2", "admin1", "country"):
        part = str(place.get(field) or "")
        if part and part != place.get("name") and part not in parts:
            parts.append(part)
    return ", ".join(parts)


def place_row(place: dict[str, Any]) -> dict[str, Any]:
    """A place as QML gets it: its saved fields and where it lies."""
    return {**place_fields(place), "region": region(place)}


def load_location(location_id: str) -> dict[str, Any] | None:
    """The saved place, or None when there is none or it has no coordinates."""
    entry = _entry(location_id)
    return place_fields(entry) if has_coordinates(entry) else None


def save_location(location_id: str, place: dict[str, Any]) -> None:
    data = _read()
    previous = _object(data.get(location_id))
    entry = place_fields(place)
    entry["name"] = entry["name"] or "Unknown"
    # The forecast stays when only the name changes
    if all(previous.get(field) == entry[field] for field in COORDINATES):
        entry.update({key: previous[key] for key in ("cached_data", "last_updated_ms", "units") if key in previous})
    data[location_id] = entry
    _write(data)


def delete_location(location_id: str) -> None:
    data = _read()
    if data.pop(location_id, None) is not None:
        _write(data)


def load_weather_cache(location_id: str) -> tuple[dict[str, Any] | None, int, str]:
    """The last forecast, when it was fetched in ms since the epoch, and its units."""
    entry = _entry(location_id)
    forecast = _object(entry.get("cached_data"))
    if not forecast:
        return None, 0, ""
    return forecast, int(entry.get("last_updated_ms") or 0), str(entry.get("units") or "")


def save_weather_cache(location_id: str, forecast: dict[str, Any], units: str) -> None:
    data = _read()
    entry = _object(data.get(location_id))
    if not entry:
        return
    entry.update({"cached_data": forecast, "last_updated_ms": int(time.time() * 1000), "units": units})
    _write(data)
