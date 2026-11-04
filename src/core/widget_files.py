import logging
from pathlib import Path
from typing import NamedTuple

from core.app.windows.alert_dialog import show_alert
from core.validation.bar import BarConfig
from core.validation.config import YasbConfig
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME, SCRIPT_PATH

USER_WIDGETS_DIR = Path(DEFAULT_CONFIG_DIRECTORY) / "widgets"
BUILTIN_WIDGETS_DIR = Path(SCRIPT_PATH) / "core" / "qml" / "Yasb" / "Widgets"


class WidgetFile(NamedTuple):
    name: str
    path: Path


def find_widget_file(widget_name: str) -> Path | None:
    """The widget's folder and file are named as config.yaml names it, in any case; the user's comes first."""
    candidates = (
        USER_WIDGETS_DIR / widget_name / f"{widget_name}.qml",
        BUILTIN_WIDGETS_DIR / widget_name / f"{widget_name}.qml",
    )
    path = next((path for path in candidates if path.is_file()), None)
    # QML refuses a path whose case differs from the file's; resolving gives the name as it is on disk
    return path.resolve() if path else None


def bar_widget_files(bar: BarConfig) -> dict[str, list[WidgetFile]]:
    return {
        slot: [WidgetFile(name, path) for name in names if (path := find_widget_file(name)) is not None]
        for slot, names in bar.widgets.items()
    }


def undefined_widgets(config: YasbConfig) -> list[str]:
    names = {name for bar in config.bars.values() if bar.enabled for names in bar.widgets.values() for name in names}
    return sorted(name for name in names if find_widget_file(name) is None)


def report_undefined_widgets(config: YasbConfig) -> None:
    missing = undefined_widgets(config)
    if not missing:
        return
    details = "\n".join(
        f' - "{name}": no {name}/{name}.qml in {USER_WIDGETS_DIR} and no built-in {name} widget' for name in missing
    )
    logging.error("Undefined widget(s) in %s:\n%s", DEFAULT_CONFIG_FILENAME, details)
    show_alert(
        title=f"Undefined widget(s) in {DEFAULT_CONFIG_FILENAME}",
        message="Some widgets in your bars could not be found and were skipped.",
        details=details,
    )
