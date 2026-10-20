from pathlib import Path

from core.plugins.discovery import plugin_data_dir
from core.plugins.manifest import PLUGIN_API_VERSION
from core.utils.qobject import is_valid_qobject
from core.utils.shell_utils import shell_open
from core.utils.tooltip import set_tooltip
from core.utils.utilities import ElidedLabel, PopupWidget, refresh_widget_style
from core.validation.widgets.base_model import CallbacksConfig, KeybindingConfig
from core.validation.widgets.base_model import CustomBaseModel as WidgetConfig
from core.widgets.base import BaseWidget
from core.widgets.registry import plugin_id_for_module
from settings import BUILD_VERSION, DEFAULT_CONFIG_DIRECTORY

API_VERSION = PLUGIN_API_VERSION
YASB_VERSION = BUILD_VERSION

__all__ = [
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
]


def data_dir(module: str) -> Path:
    plugin_id = plugin_id_for_module(module)
    if plugin_id is None:
        raise ValueError(f"{module} is not part of a loaded YASB plugin, pass the plugin module's __name__")
    return plugin_data_dir(plugin_id)


def config_dir() -> Path:
    return Path(DEFAULT_CONFIG_DIRECTORY)
