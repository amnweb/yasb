import json
import logging
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from PyQt6.QtWidgets import QApplication, QLabel

import main
from core.plugins import loader
from core.plugins.discovery import discover_plugins
from core.plugins.manifest import PLUGIN_API_VERSION, PluginError, PluginManifest
from core.plugins.resolver import resolve_widget_class
from core.utils import widget_builder
from core.utils.widget_builder import WidgetBuilder
from core.widgets import registry
from core.widgets.yasb.clock import ClockWidget
from tests.plugins.helpers import (
    PACKAGE,
    PLUGIN_ID,
    WIDGET_TYPE,
    boom_module,
    manifest_data,
    plugin_modules,
    write_manifest,
)

# --- manifest.json ---------------------------------------------------------------------


def test_example_manifest_is_valid():
    manifest = PluginManifest.model_validate(manifest_data())

    assert manifest.id == PLUGIN_ID
    assert manifest.api == str(PLUGIN_API_VERSION)
    assert manifest.widgets == {"HelloWidget": "widget:HelloWidget"}
    assert manifest.styles == "styles.css"
    assert manifest.example_config == "example.yaml"
    assert manifest.slug == "hello"
    assert manifest.author == "YASB"


def test_unknown_manifest_fields_are_ignored():
    assert PluginManifest.model_validate(manifest_data(homepage="https://example.com")).id == PLUGIN_ID


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "Hello"},
        {"id": "owner/hello"},
        {"id": "hello_world"},
        {"id": "hello.world"},
        {"id": "-hello"},
        {"id": "hello-"},
        {"author": ""},
        {"name": ""},
        {"version": "1.0"},
        {"api": "one"},
        {"api": 1},
        {"min_yasb": "latest"},
        {"widgets": {}},
        {"widgets": {"HelloWidget": "widget.HelloWidget"}},
        {"widgets": {"HelloWidget": ".widget:HelloWidget"}},
        {"widgets": {"Hello-Widget": "widget:HelloWidget"}},
        {"styles": "../outside.css"},
        {"styles": "C:/Windows/styles.css"},
        {"example_config": "/example.yaml"},
    ],
    ids=lambda changes: json.dumps(changes),
)
def test_invalid_manifest_is_rejected(changes: dict[str, Any]):
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(manifest_data(**changes))


@pytest.mark.parametrize("field", ["id", "name", "version", "author", "api", "min_yasb", "widgets"])
def test_required_manifest_field(field: str):
    data = manifest_data()
    del data[field]

    with pytest.raises(ValidationError):
        PluginManifest.model_validate(data)


# --- discovery -------------------------------------------------------------------------


def test_discovery_finds_installed_plugin(plugins_root: Path, plugin_dir: Path):
    found = discover_plugins(plugins_root)

    assert list(found) == [PLUGIN_ID]
    assert found[PLUGIN_ID].directory == plugin_dir
    assert found[PLUGIN_ID].manifest is not None


def test_discovery_without_plugins_folder(tmp_path: Path):
    assert discover_plugins(tmp_path / "missing") == {}


def test_unreadable_manifest_is_reported_by_folder(plugins_root: Path, plugin_dir: Path):
    (plugin_dir / "manifest.json").write_text("{not json", encoding="utf-8")

    found = discover_plugins(plugins_root)

    assert found["hello"].manifest is None
    assert "unreadable manifest.json" in (found["hello"].error or "")


def test_plugin_installed_twice_is_skipped(plugins_root: Path, plugin_dir: Path):
    shutil.copytree(plugin_dir, plugins_root / "hello-copy")

    found = discover_plugins(plugins_root)

    assert found[PLUGIN_ID].manifest is None
    assert "installed twice" in (found[PLUGIN_ID].error or "")


def test_api_mismatch_is_skipped(plugin_dir: Path, caplog: pytest.LogCaptureFixture):
    write_manifest(plugin_dir, api=str(PLUGIN_API_VERSION + 1))

    with caplog.at_level(logging.ERROR), pytest.raises(PluginError, match=f"plugin API {PLUGIN_API_VERSION + 1}"):
        resolve_widget_class(WIDGET_TYPE)

    assert f'Skipping plugin "{PLUGIN_ID}"' in caplog.text
    assert f"supports plugin API {PLUGIN_API_VERSION}" in caplog.text
    assert plugin_modules() == []


def test_api_mismatch_wins_over_schema_errors(plugin_dir: Path):
    write_manifest(plugin_dir, api="2", widgets="not a mapping")

    with pytest.raises(PluginError, match="plugin API 2"):
        resolve_widget_class(WIDGET_TYPE)


def test_newer_min_yasb_is_skipped(plugin_dir: Path):
    write_manifest(plugin_dir, min_yasb="99.0.0")

    with pytest.raises(PluginError, match="requires YASB 99.0.0"):
        resolve_widget_class(WIDGET_TYPE)


# --- resolving widget types ------------------------------------------------------------


def test_builtin_type_resolves():
    assert resolve_widget_class("yasb.clock.ClockWidget") is ClockWidget


@pytest.mark.parametrize(
    ("type_str", "error"),
    [
        ("ClockWidget", ValueError),
        ("yasb.clock.MissingWidget", AttributeError),
        ("yasb.missing.ClockWidget", ModuleNotFoundError),
        ("yasb.clock.datetime", ValueError),
    ],
)
def test_bad_builtin_type(type_str: str, error: type[Exception]):
    with pytest.raises(error):
        resolve_widget_class(type_str)


def test_plugin_type_resolves(plugin_dir: Path):
    widget_cls = resolve_widget_class(WIDGET_TYPE)

    assert widget_cls.__name__ == "HelloWidget"
    assert widget_cls.__module__ == f"{PACKAGE}.widget"
    assert resolve_widget_class(WIDGET_TYPE) is widget_cls
    assert all(Path(entry) != plugin_dir for entry in sys.path)


def test_plugin_widget_is_registered_under_plugin_id(plugins_root: Path):
    widget_cls = resolve_widget_class(WIDGET_TYPE)

    assert registry.WIDGET_REGISTRY[WIDGET_TYPE] is widget_cls
    assert registry.widget_type_key(widget_cls) == WIDGET_TYPE
    assert registry.widget_type_key(ClockWidget) == "yasb.clock.ClockWidget"


def test_plugin_that_is_not_installed(plugins_root: Path):
    with pytest.raises(PluginError, match='"someone-else" is not installed'):
        resolve_widget_class("plugins.someone-else.SomeWidget")


def test_plugin_without_that_widget(plugins_root: Path):
    with pytest.raises(PluginError, match='has no widget "MissingWidget"'):
        resolve_widget_class(f"plugins.{PLUGIN_ID}.MissingWidget")


def test_plugin_entry_that_is_not_a_widget(plugin_dir: Path):
    write_manifest(plugin_dir, widgets={"HelloWidget": "text:greeting"})

    with pytest.raises(PluginError, match="not a BaseWidget subclass"):
        resolve_widget_class(WIDGET_TYPE)


def test_plugin_import_error_is_reported(plugin_dir: Path):
    (plugin_dir / "text.py").write_text("raise RuntimeError('broken plugin')\n", encoding="utf-8")

    with pytest.raises(PluginError, match="RuntimeError: broken plugin"):
        resolve_widget_class(WIDGET_TYPE)
    with pytest.raises(PluginError, match="RuntimeError: broken plugin"):
        resolve_widget_class(WIDGET_TYPE)


# --- building plugin widgets -----------------------------------------------------------


@pytest.mark.parametrize("with_init", [True, False], ids=["package", "no-init"])
def test_relative_imports_inside_plugin(plugin_dir: Path, qapp: QApplication, with_init: bool):
    if not with_init:
        (plugin_dir / "__init__.py").unlink()
    builder = WidgetBuilder({"hello": {"type": WIDGET_TYPE, "options": {"name": "YASB"}}})

    widget = builder.build_widget("hello")

    assert widget is not None
    assert widget.widget_name == "hello"
    label = widget.findChild(QLabel)
    assert label is not None and label.text() == "Hello, YASB!"
    assert f"{PACKAGE}.text" in sys.modules
    widget.close()


def test_incompatible_plugin_uses_builder_alerts(plugin_dir: Path, qapp: QApplication, monkeypatch: pytest.MonkeyPatch):
    write_manifest(plugin_dir, api=str(PLUGIN_API_VERSION + 1))
    alerts: list[dict[str, Any]] = []

    def record_alert(**alert: Any) -> None:
        alerts.append(alert)

    monkeypatch.setattr(widget_builder, "raise_info_alert", record_alert)
    builder = WidgetBuilder({"hello": {"type": WIDGET_TYPE}})

    assert builder.build_widget("hello") is None
    builder.raise_alerts_if_errors_present()

    assert len(alerts) == 1
    assert alerts[0]["title"].startswith("Failed to load plugin widget(s)")
    assert f'hello: Plugin "{PLUGIN_ID}" was skipped: it targets plugin API' in alerts[0]["additional_details"]


# --- unhandled exceptions --------------------------------------------------------------


def _raise_in_plugin(plugin_dir: Path) -> RuntimeError:
    boom = boom_module(plugin_dir)
    with pytest.raises(RuntimeError) as raised:
        boom.explode()
    return raised.value


@pytest.fixture
def cleared_events(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    cleared: list[bool] = []
    monkeypatch.setattr(main, "EventService", lambda: SimpleNamespace(clear=lambda: cleared.append(True)))
    return cleared


def test_traceback_is_attributed_to_plugin(plugin_dir: Path):
    error = _raise_in_plugin(plugin_dir)

    assert loader.plugin_for_traceback(error.__traceback__) == PLUGIN_ID


def test_plugin_exception_does_not_exit(plugin_dir: Path, cleared_events: list[bool], caplog: pytest.LogCaptureFixture):
    error = _raise_in_plugin(plugin_dir)

    with caplog.at_level(logging.ERROR):
        main.exception_hook(type(error), error, error.__traceback__)

    assert f'Unhandled exception in plugin "{PLUGIN_ID}"' in caplog.text
    assert cleared_events == []


def test_core_exception_still_exits(plugin_dir: Path, cleared_events: list[bool]):
    resolve_widget_class(WIDGET_TYPE)
    error = RuntimeError("core")
    try:
        raise error
    except RuntimeError:
        pass

    assert loader.plugin_for_traceback(error.__traceback__) is None
    with pytest.raises(SystemExit):
        main.exception_hook(type(error), error, error.__traceback__)
    assert cleared_events == [True]
