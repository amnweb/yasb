import logging
import re
from pathlib import Path
from typing import NamedTuple

from core.utils.alert_dialog import raise_info_alert
from core.validation.bar import BarConfig
from core.validation.config import YasbConfig
from settings import DEFAULT_CONFIG_DIRECTORY, DEFAULT_CONFIG_FILENAME, SCRIPT_PATH

USER_WIDGETS_DIR = Path(DEFAULT_CONFIG_DIRECTORY) / "widgets"
BUILTIN_WIDGETS_DIR = Path(SCRIPT_PATH) / "core" / "qml" / "Yasb" / "Widgets"


class WidgetFile(NamedTuple):
    name: str
    path: Path


def component_name(widget_name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[_-]", widget_name) if part)


def find_widget_file(widget_name: str) -> Path | None:
    builtin = component_name(widget_name)
    candidates = (
        USER_WIDGETS_DIR / widget_name / f"{widget_name}.qml",
        BUILTIN_WIDGETS_DIR / builtin / f"{builtin}.qml",
    )
    return next((path for path in candidates if path.is_file()), None)


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
        f' - "{name}": no {name}/{name}.qml in {USER_WIDGETS_DIR} and no built-in {component_name(name)} widget'
        for name in missing
    )
    logging.error("Undefined widget(s) in %s:\n%s", DEFAULT_CONFIG_FILENAME, details)
    raise_info_alert(
        title=f"Undefined widget(s) in {DEFAULT_CONFIG_FILENAME}",
        msg="Some widgets in your bars could not be found and were skipped.",
        informative_msg="Please click 'Show Details' to find out more.",
        additional_details=details,
    )
