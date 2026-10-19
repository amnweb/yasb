import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from core.plugins import config_edit, discovery, loader
from core.plugins.loader import PluginLoader
from core.widgets import registry
from tests.plugins.helpers import FIXTURE, plugin_modules


@pytest.fixture
def plugins_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    root = tmp_path / "plugins"
    shutil.copytree(FIXTURE, root / "hello", ignore=shutil.ignore_patterns("__pycache__"))
    monkeypatch.setattr(loader, "_active", PluginLoader(root))
    monkeypatch.setattr(registry, "_plugin_packages", {})
    saved_registry = dict(registry.WIDGET_REGISTRY)
    yield root
    registry.WIDGET_REGISTRY.clear()
    registry.WIDGET_REGISTRY.update(saved_registry)
    for name in plugin_modules():
        del sys.modules[name]


@pytest.fixture
def plugin_dir(plugins_root: Path) -> Path:
    return plugins_root / "hello"


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "config"
    home.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(discovery, "DEFAULT_CONFIG_DIRECTORY", str(home))
    monkeypatch.setattr(config_edit, "DEFAULT_CONFIG_DIRECTORY", str(home))
    return home
