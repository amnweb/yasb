from typing import Any

from core.plugins.manifest import plugin_widget_type

WIDGET_REGISTRY: dict[str, Any] = {}
_plugin_packages: dict[str, str] = {}


def register_plugin_package(package: str, plugin_id: str) -> None:
    _plugin_packages[package] = plugin_id


def plugin_id_for_module(module: str) -> str | None:
    return _plugin_packages.get(".".join(module.split(".", 2)[:2]))


def widget_type_key(cls: type[Any]) -> str:
    if plugin_id := plugin_id_for_module(cls.__module__):
        return plugin_widget_type(plugin_id, cls.__name__)
    return f"{cls.__module__.removeprefix('core.widgets.')}.{cls.__name__}"


def register_widget_class(cls: type[Any], key: str | None = None):
    """
    Register a widget class in the global registry.
    The key is generated based on the class module and name,
    or "plugins.<plugin>.ClassName" for classes inside a plugin package.
    """
    WIDGET_REGISTRY[key or widget_type_key(cls)] = cls
