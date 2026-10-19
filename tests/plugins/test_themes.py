# pyright: reportPrivateUsage=false

from pathlib import Path
from typing import Any

import yaml

from core.ui.views.themes import _theme_config_errors
from tests.plugins.helpers import WIDGET_TYPE


def _theme(widget: dict[str, Any]) -> bytes:
    config = {"bars": {"main": {"widgets": {"left": ["hello"]}}}, "widgets": {"hello": widget}}
    return yaml.safe_dump(config).encode("utf-8")


def test_theme_with_an_installed_plugin_widget_is_valid(plugins_root: Path):
    assert _theme_config_errors(_theme({"type": WIDGET_TYPE, "options": {"name": "YASB"}})) == ""


def test_theme_with_bad_plugin_widget_options(plugins_root: Path):
    errors = _theme_config_errors(_theme({"type": WIDGET_TYPE, "options": {"colour": "red"}}))

    assert errors.startswith(" - hello")
    assert "colour" in errors


def test_theme_with_a_plugin_that_is_not_installed(plugins_root: Path):
    errors = _theme_config_errors(_theme({"type": "plugins.someone-else.SomeWidget"}))

    assert errors == f' - hello: Plugin "someone-else" is not installed in {plugins_root}'
