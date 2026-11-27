"""The first-run setup: whether YASB needs it, and the config, layout and theme it writes."""

import logging
import os
from pathlib import Path
from typing import Any, Literal, cast, override

import yaml
from pydantic import ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel
from PyQt6.QtGui import QFontDatabase
from yaml import YAMLError

from core.bar.window import USER_LAYOUTS_DIR
from core.config import ConfigError, get_config_path
from core.theme_files import USER_THEMES_DIR
from core.utils.validation_errors import format_pydantic_errors_to_yaml
from core.validation.bar import AutoHide, WidgetName
from core.validation.base_model import CustomBaseModel
from core.validation.config import YasbConfig
from settings import QML_IMPORT_PATH, WEBSITE_DOCS_URL

type SetupReason = Literal["new", "upgrade"]
type Style = Literal["bar", "floating", "islands"]
type Position = Literal["left", "center", "right"]

# Top-level keys every 2.x config had and 3.0 never accepts
V2_KEYS = frozenset({"watch_config", "watch_stylesheet", "widgets"})
BAR_NAME = "yasb-bar"
POSITIONS: tuple[Position, ...] = ("left", "center", "right")
FLOATING_GAP = 6
TEMPLATES = Path(QML_IMPORT_PATH) / "Yasb" / "Setup"
LAYOUT_TEMPLATES = TEMPLATES / "layouts"
THEME_NAME = "yasb"
THEME_TEMPLATE = TEMPLATES / "themes" / f"{THEME_NAME}.qml"
# The bar's and popups' background in the theme, without the alpha when there is no blur
TRANSLUCENT_BACKGROUND = "Qt.alpha(colors.background, 0.85)"
OPAQUE_BACKGROUND = "colors.background"
ICON_FONT = "Segoe Fluent Icons"
ICON_FONT_URL = "https://aka.ms/SegoeFluentIcons"
CONFIG_HEADER = f"# YASB's configuration. Every option is explained at {WEBSITE_DOCS_URL}\n\n"


class SetupChoices(CustomBaseModel):
    """What the user picked in the setup window, sent with camelCase names."""

    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)

    edge: Literal["top", "bottom"]
    style: Style
    thickness: int = Field(ge=1)
    screens: Literal["*", "primary"]
    backdrop: bool
    always_on_top: bool
    hide_on_fullscreen: bool
    auto_hide: AutoHide
    reserve_space: bool
    widgets: dict[Position, list[WidgetName]]
    update_check: bool
    autostart: bool


class ConfigDumper(yaml.SafeDumper):
    """Writes every list as a block, each item indented under its key."""

    @override
    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        super().increase_indent(flow, False)


def config_folder() -> Path:
    return Path(get_config_path()).parent


def setup_reason() -> SetupReason | None:
    """Why the config needs the setup: it is missing, or from 2.x. None for any other config."""
    path = Path(get_config_path())
    if not path.exists():
        return "new"
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError, UnicodeDecodeError, YAMLError:
        return None
    if isinstance(config, dict) and not V2_KEYS.isdisjoint(cast(dict[str, Any], config)):
        return "upgrade"
    return None


def build_config(choices: SetupChoices) -> dict[str, Any]:
    """The config.yaml the choices make, validated."""
    bar: dict[str, Any] = {
        "layout": choices.style,
        "screens": [choices.screens],
        "edge": choices.edge,
        "thickness": choices.thickness,
    }
    if choices.style == "floating":
        bar["margin"] = {side: FLOATING_GAP for side in (choices.edge, "left", "right")}
    bar["always_on_top"] = choices.always_on_top
    bar["hide_on_fullscreen"] = choices.hide_on_fullscreen
    bar["auto_hide"] = choices.auto_hide
    bar["reserve_space"] = choices.reserve_space
    bar["backdrop"] = choices.backdrop
    bar["widgets"] = {position: list(names) for position in POSITIONS if (names := choices.widgets.get(position))}
    fields = YasbConfig.model_fields
    config: dict[str, Any] = {
        "debug": fields["debug"].default,
        "update_check": choices.update_check,
        "theme": THEME_NAME,
        "bars": {BAR_NAME: bar},
    }
    try:
        YasbConfig(**config)
    except ValidationError as e:
        raise ConfigError(
            "The setup's choices do not make a valid config.", format_pydantic_errors_to_yaml(e)
        ) from None
    return config


def _write_template(text: str, target: Path) -> None:
    """Writes a layout or theme, unless the user already has one of that name."""
    if target.exists():
        logging.info("Keeping %s, which is already there", target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="")
    logging.info("Created %s", target)


def theme_text(backdrop: bool) -> str:
    """The theme to write, with opaque backgrounds when there is no backdrop."""
    text = THEME_TEMPLATE.read_text(encoding="utf-8", newline="")
    return text if backdrop else text.replace(TRANSLUCENT_BACKGROUND, OPAQUE_BACKGROUND)


def write_setup(config: dict[str, Any], choices: SetupChoices) -> None:
    """Writes the layout and theme, then config.yaml, so it never names a missing file."""
    path = Path(get_config_path())
    layout = LAYOUT_TEMPLATES / f"{choices.style}.qml"
    _write_template(layout.read_text(encoding="utf-8", newline=""), path.parent / USER_LAYOUTS_DIR.name / layout.name)
    _write_template(theme_text(choices.backdrop), path.parent / USER_THEMES_DIR.name / THEME_TEMPLATE.name)
    # Moved over config.yaml, so a failed write never leaves half a file
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        text = yaml.dump(config, Dumper=ConfigDumper, sort_keys=False, allow_unicode=True)
        temporary.write_text(CONFIG_HEADER + text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    logging.info("Created the config %s", path)


def icon_font_installed() -> bool:
    """Whether Segoe Fluent Icons is installed."""
    return ICON_FONT in QFontDatabase.families()
