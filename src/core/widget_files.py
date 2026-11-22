import json
import logging
from functools import cache
from pathlib import Path
from typing import Any, NamedTuple, cast

from settings import BUILD_VERSION, DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME, SCRIPT_PATH, SERVICE_API_VERSION

# Lazy: yasbc reads the widget folders without loading Qt or the config's models
lazy from core.app.windows.alert_dialog import show_alert
lazy from core.validation.bar import BarConfig
lazy from core.validation.config import YasbConfig

USER_WIDGETS_DIR = Path(DEFAULT_CONFIG_DIRECTORY) / "widgets"
BUILTIN_WIDGETS_DIR = Path(SCRIPT_PATH) / "core" / "qml" / "Yasb" / "Widgets"
MANIFEST = "manifest.json"
WIDGET_LIST = "widgets.json"


class WidgetFile(NamedTuple):
    name: str
    path: Path


def file_name(widget_name: str) -> str:
    """The QML file a widget's folder holds: its name, or for a namespaced amnweb.clock, Clock.qml."""
    return f"{widget_name.rpartition('.')[2]}.qml"


def user_widget_file(widget_name: str) -> Path:
    return USER_WIDGETS_DIR / widget_name / file_name(widget_name)


def builtin_widget_file(widget_name: str) -> Path | None:
    """Where YASB's own widget of that name is; namespaced names are never YASB's."""
    return None if "." in widget_name else BUILTIN_WIDGETS_DIR / widget_name / file_name(widget_name)


@cache
def _widget_list(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {widget["id"]: widget for widget in data["widgets"]}


def builtin_manifests() -> dict[str, dict[str, Any]]:
    """YASB's own widgets by id, from widgets.json; empty without that file."""
    path = BUILTIN_WIDGETS_DIR / WIDGET_LIST
    return _widget_list(path) if path.is_file() else {}


def builtin_manifest(widget_name: str) -> dict[str, Any] | None:
    """YASB's own widget of that name, in any case; namespaced names are never YASB's."""
    if "." in widget_name:
        return None
    folded = widget_name.casefold()
    return next((data for name, data in builtin_manifests().items() if name.casefold() == folded), None)


def manifest(widget_name: str) -> dict[str, Any] | None:
    """The manifest in the user's folder of the widget, None without one; raises ValueError for one that can't be read."""
    path = USER_WIDGETS_DIR / widget_name / MANIFEST
    if not path.is_file():
        return None
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"{MANIFEST} can't be read: {e}") from None
    if not isinstance(data, dict):
        raise ValueError(f"{MANIFEST} is not a JSON object")
    return cast(dict[str, Any], data)


def manifest_problem(widget_name: str) -> str | None:
    """Why the user's widget no longer fits this YASB, from its manifest; None when it fits or has no manifest."""
    try:
        data = manifest(widget_name)
    except ValueError as e:
        return str(e)
    if data is None:
        return None
    if "id" not in data:
        return f"{MANIFEST} has no id"
    if str(data["id"]).casefold() != widget_name.casefold():
        return f"{MANIFEST} has the id {data['id']}, but its folder is {widget_name}"
    api = data.get("yasbApi")
    if api != SERVICE_API_VERSION[0]:
        return f"needs YASB API {api}, YASB {BUILD_VERSION} has {SERVICE_API_VERSION[0]}"
    builtin = builtin_manifest(widget_name)
    if builtin is not None and data.get("version") != builtin["version"]:
        return f"copy of v{data.get('version')}, YASB's {builtin['id']} is v{builtin['version']}"
    return None


def find_widget_file(widget_name: str) -> Path | None:
    """The widget's folder and file are named as config.yaml names it, in any case; the user's comes first, unless
    its manifest says it no longer fits, and then YASB's own widget of that name is used."""
    user = user_widget_file(widget_name)
    candidates = [user] if user.is_file() and manifest_problem(widget_name) is None else []
    if (builtin := builtin_widget_file(widget_name)) is not None:
        candidates.append(builtin)
    path = next((path for path in candidates if path.is_file()), None)
    # QML refuses a path whose case differs from the file's; resolving gives the name as it is on disk
    return path.resolve() if path else None


def bar_widget_files(bar: BarConfig) -> dict[str, list[WidgetFile]]:
    return {
        slot: [WidgetFile(name, path) for name in names if (path := find_widget_file(name)) is not None]
        for slot, names in bar.widgets.items()
    }


def _bar_widgets(config: YasbConfig) -> set[str]:
    return {name for bar in config.bars.values() if bar.enabled for names in bar.widgets.values() for name in names}


def undefined_widgets(config: YasbConfig) -> list[str]:
    # A user's widget turned away by its manifest is reported as outdated instead
    return sorted(
        name for name in _bar_widgets(config) if find_widget_file(name) is None and not user_widget_file(name).is_file()
    )


def outdated_widgets(config: YasbConfig) -> dict[str, str]:
    """The user's widgets in the bars that their manifests say no longer fit, each with why."""
    found = {name: manifest_problem(name) for name in _bar_widgets(config) if user_widget_file(name).is_file()}
    return {name: problem for name, problem in sorted(found.items()) if problem is not None}


def report_undefined_widgets(config: YasbConfig) -> None:
    missing = undefined_widgets(config)
    if not missing:
        return
    details = "\n".join(
        f' - "{name}": no {name}/{file_name(name)} in {USER_WIDGETS_DIR} and no built-in {name} widget'
        for name in missing
    )
    logging.error("Undefined widget(s) in %s:\n%s", DEFAULT_CONFIG_FILENAME, details)
    show_alert(
        title=f"Undefined widget(s) in {DEFAULT_CONFIG_FILENAME}",
        message="Some widgets in your bars could not be found and were skipped.",
        details=details,
    )


def report_outdated_widgets(config: YasbConfig) -> None:
    outdated = outdated_widgets(config)
    if not outdated:
        return
    details = "\n".join(f' - "{name}" in {USER_WIDGETS_DIR / name}: {problem}' for name, problem in outdated.items())
    logging.error("Widget(s) that no longer fit this YASB:\n%s", details)
    show_alert(
        title="Some of your widgets no longer fit this YASB",
        message="YASB uses its own widget of that name where it has one, and skips the rest.",
        details=details,
    )
