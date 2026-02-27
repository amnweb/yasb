"""Location persistence for OpenMeteoWidget.

Stores location data (lat, lon, name, etc.) per widget instance in
``weather.json`` inside the YASB app data directory.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from core.utils.utilities import app_data_path

_LOCATION_FILE = "weather.json"


def _get_file_path() -> Path:
    return app_data_path(_LOCATION_FILE)


def get_widget_id(widget: Any) -> str:
    """Build a unique identifier for a widget based on its name."""
    name = getattr(widget, "widget_name", None) or "open_meteo"
    return re.sub(r"\W+", "_", name).strip("_")


def _read_file() -> dict[str, Any]:
    path = _get_file_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logging.warning(f"Failed to read {path}: {e}")
        return {}


def _write_file(data: dict[str, Any]) -> None:
    path = _get_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logging.error(f"Failed to write {path}: {e}")


def load_location(widget_id: str) -> dict[str, Any] | None:
    """Load saved location data for the given widget ID.

    Returns:
        Dict with ``latitude``, ``longitude``, ``name``, ``country``,
        ``admin1``,``timezone`` keys, or ``None`` if not found.
    """
    data = _read_file()
    return data.get(widget_id)


def save_location(widget_id: str, location: dict[str, Any] | None) -> None:
    """Save location data for the given widget ID.

    Args:
        widget_id: Unique identifier for the widget instance.
        location: Dict containing at minimum ``latitude`` and ``longitude``.
                  If None, the location is deleted.
    """
    if location is None:
        delete_location(widget_id)
        return

    data = _read_file()
    existing_cache = data.get(widget_id, {})

    data[widget_id] = {
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "name": location.get("name", "Unknown"),
        "country": location.get("country", ""),
        "admin1": location.get("admin1", ""),
        "admin2": location.get("admin2", ""),
        "admin3": location.get("admin3", ""),
        "timezone": location.get("timezone", "auto"),
        # Preserve weather cache when changing names, not coordinates
        "cached_data": existing_cache.get("cached_data", None)
        if location.get("latitude") == existing_cache.get("latitude")
        else None,
        "last_updated_ms": existing_cache.get("last_updated_ms", 0)
        if location.get("latitude") == existing_cache.get("latitude")
        else 0,
    }
    _write_file(data)
    logging.info(f"Saved location for {widget_id}: {data[widget_id]['name']}")


def save_weather_cache(widget_id: str, weather_data: dict[str, Any]) -> None:
    """Save raw Open-Meteo API response to local disk cache."""
    data = _read_file()
    if widget_id not in data:
        return

    data[widget_id]["cached_data"] = weather_data
    data[widget_id]["last_updated_ms"] = int(time.time() * 1000)
    _write_file(data)


def load_weather_cache(widget_id: str) -> tuple[dict[str, Any] | None, int]:
    """Retrieve the cached Open-Meteo metadata and its last updated timestamp."""
    data = _read_file()
    widget_data = data.get(widget_id, {})
    return widget_data.get("cached_data", None), widget_data.get("last_updated_ms", 0)


def delete_location(widget_id: str) -> None:
    """Remove saved location data for the given widget ID."""
    data = _read_file()
    if widget_id in data:
        del data[widget_id]
        _write_file(data)
        logging.info(f"Deleted location for {widget_id}")


def cleanup_stale_entries(active_widget_ids: set[str]) -> None:
    """Remove entries from weather.json that are not in the active widget set."""
    data = _read_file()
    stale_keys = [key for key in data if key not in active_widget_ids]
    if not stale_keys:
        return
    for key in stale_keys:
        del data[key]
        logging.info(f"Removed stale weather entry: {key}")
    _write_file(data)
