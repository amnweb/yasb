import importlib
import importlib.machinery
import importlib.util
import logging
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, TracebackType

from core.plugins.discovery import DiscoveredPlugin, discover_plugins, plugins_dir
from core.plugins.manifest import PluginError, PluginManifest, plugin_widget_type
from core.widgets.base import BaseWidget
from core.widgets.registry import register_plugin_package, register_widget_class

PLUGIN_NAMESPACE = "yasb_plugins"


@dataclass(frozen=True)
class LoadedPlugin:
    manifest: PluginManifest
    directory: Path
    package: str
    widgets: dict[str, type[BaseWidget]]


def _namespace_package() -> ModuleType:
    if namespace := sys.modules.get(PLUGIN_NAMESPACE):
        return namespace
    namespace = importlib.util.module_from_spec(importlib.machinery.ModuleSpec(PLUGIN_NAMESPACE, None, is_package=True))
    sys.modules[PLUGIN_NAMESPACE] = namespace
    return namespace


def _import_package(package: str, directory: Path) -> None:
    init = directory / "__init__.py"
    if init.is_file():
        spec = importlib.util.spec_from_file_location(package, init, submodule_search_locations=[str(directory)])
    else:
        spec = importlib.machinery.ModuleSpec(package, None, is_package=True)
        spec.submodule_search_locations = [str(directory)]
    if spec is None:
        raise ImportError(f"cannot create a module spec for {init}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[package] = module
    setattr(_namespace_package(), package.rpartition(".")[2], module)
    if spec.loader is not None:
        spec.loader.exec_module(module)


class PluginLoader:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._discovered: dict[str, DiscoveredPlugin] | None = None
        self._loaded: dict[str, LoadedPlugin] = {}
        self._failed: dict[str, str] = {}
        self._directories: dict[str, str] = {}

    def discover(self) -> dict[str, DiscoveredPlugin]:
        if self._discovered is None:
            self._discovered = discover_plugins(self.root)
        return self._discovered

    def load(self, plugin_id: str) -> LoadedPlugin:
        if plugin := self._loaded.get(plugin_id):
            return plugin
        if error := self._failed.get(plugin_id):
            raise PluginError(error)
        try:
            plugin = self._load(plugin_id)
        except PluginError as e:
            self._failed[plugin_id] = str(e)
            raise
        self._loaded[plugin_id] = plugin
        return plugin

    def widget_class(self, plugin_id: str, class_name: str) -> type[BaseWidget]:
        plugin = self.load(plugin_id)
        if widget_cls := plugin.widgets.get(class_name):
            return widget_cls
        available = ", ".join(sorted(plugin.widgets))
        raise PluginError(f'Plugin "{plugin_id}" has no widget "{class_name}" (it provides: {available})')

    def stylesheets(self, plugin_ids: Iterable[str]) -> list[Path]:
        discovered = self.discover()
        paths: list[Path] = []
        for plugin_id in dict.fromkeys(plugin_ids):
            source = discovered.get(plugin_id)
            if source is None or source.manifest is None or source.manifest.styles is None:
                continue
            path = source.directory / source.manifest.styles
            if path.is_file():
                paths.append(path)
            else:
                logging.warning(
                    'Plugin "%s" lists styles "%s" but %s does not exist', plugin_id, source.manifest.styles, path
                )
        return paths

    def plugin_for_file(self, filename: str) -> str | None:
        path = os.path.normcase(filename)
        for plugin_id, directory in self._directories.items():
            if path.startswith(directory):
                return plugin_id
        return None

    def plugin_for_traceback(self, tb: TracebackType | None) -> str | None:
        owner: str | None = None
        while tb is not None:
            owner = self.plugin_for_file(tb.tb_frame.f_code.co_filename) or owner
            tb = tb.tb_next
        return owner

    def _load(self, plugin_id: str) -> LoadedPlugin:
        source = self.discover().get(plugin_id)
        if source is None:
            raise PluginError(f'Plugin "{plugin_id}" is not installed in {self.root}')
        if source.manifest is None:
            raise PluginError(f'Plugin "{plugin_id}" was skipped: it {source.error}')
        manifest = source.manifest
        package = f"{PLUGIN_NAMESPACE}.{manifest.slug}"
        self._directories[plugin_id] = os.path.normcase(str(source.directory)) + os.sep
        register_plugin_package(package, plugin_id)
        widgets: dict[str, type[BaseWidget]] = {}
        try:
            _import_package(package, source.directory)
            for name, entry in manifest.widgets.items():
                module_name, _, attr = entry.partition(":")
                widget_cls = getattr(importlib.import_module(f"{package}.{module_name}"), attr, None)
                if not (isinstance(widget_cls, type) and issubclass(widget_cls, BaseWidget)):
                    raise PluginError(f'Plugin "{plugin_id}": widgets.{name} "{entry}" is not a BaseWidget subclass')
                register_widget_class(widget_cls, plugin_widget_type(plugin_id, name))
                widgets[name] = widget_cls
        except PluginError:
            raise
        except Exception as e:
            logging.exception('Plugin "%s" failed to import from %s', plugin_id, source.directory)
            raise PluginError(f'Plugin "{plugin_id}" failed to import: {type(e).__name__}: {e}') from e
        logging.info('Loaded plugin "%s" %s from %s', plugin_id, manifest.version, source.directory)
        return LoadedPlugin(manifest, source.directory, package, widgets)


_active: PluginLoader | None = None


def plugin_loader() -> PluginLoader:
    global _active
    if _active is None:
        _active = PluginLoader(plugins_dir())
    return _active


def plugin_for_traceback(tb: TracebackType | None) -> str | None:
    return _active.plugin_for_traceback(tb) if _active else None
