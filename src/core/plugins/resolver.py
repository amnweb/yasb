from importlib import import_module

from core.plugins.loader import plugin_loader
from core.plugins.manifest import plugin_id_of
from core.widgets.base import BaseWidget


def resolve_widget_class(type_str: str) -> type[BaseWidget]:
    module_path, _, class_name = type_str.rpartition(".")
    if not module_path or not class_name:
        raise ValueError(f'Invalid widget type "{type_str}"')
    if plugin_id := plugin_id_of(type_str):
        return plugin_loader().widget_class(plugin_id, class_name)
    widget_cls = getattr(import_module(f"core.widgets.{module_path}"), class_name)
    if not (isinstance(widget_cls, type) and issubclass(widget_cls, BaseWidget)):
        raise ValueError(f'"{type_str}" is not a widget class')
    return widget_cls
