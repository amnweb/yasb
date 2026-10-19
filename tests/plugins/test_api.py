from pathlib import Path

import pytest

import yasb_api
from core.plugins.manifest import PLUGIN_API_VERSION
from core.plugins.resolver import resolve_widget_class
from core.utils.system import app_data_path
from tests.plugins.helpers import PACKAGE, WIDGET_TYPE

API_1_NAMES = {
    "API_VERSION",
    "YASB_VERSION",
    "BaseWidget",
    "CallbacksConfig",
    "ElidedLabel",
    "KeybindingConfig",
    "PopupWidget",
    "WidgetConfig",
    "config_dir",
    "data_dir",
    "is_valid_qobject",
    "refresh_widget_style",
    "set_tooltip",
    "shell_open",
}


def test_api_1_names_are_still_there():
    missing = API_1_NAMES - set(yasb_api.__all__)

    assert not missing, f"Plugins written for API 1 use {sorted(missing)}. Keep them or bump PLUGIN_API_VERSION."


def test_every_exported_name_exists():
    for name in yasb_api.__all__:
        assert hasattr(yasb_api, name), name


def test_api_version_is_the_plugin_api_version():
    assert yasb_api.API_VERSION == PLUGIN_API_VERSION


def test_data_dir_belongs_to_the_plugin(plugins_root: Path):
    resolve_widget_class(WIDGET_TYPE)

    folder = yasb_api.data_dir(f"{PACKAGE}.widget")

    assert folder == app_data_path("plugin-data") / "hello"
    assert folder.is_dir()


def test_data_dir_outside_a_plugin():
    with pytest.raises(ValueError, match="not part of a loaded YASB plugin"):
        yasb_api.data_dir(__name__)
