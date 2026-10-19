import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from core.plugins import cli, config_edit
from core.plugins.config_edit import AddedWidget, add_widget, remove_plugin_widgets
from core.plugins.discovery import read_manifest
from core.plugins.manifest import PluginError, PluginManifest
from core.validation.config import YasbConfig
from tests.plugins.helpers import FIXTURE, PLUGIN_ID, WIDGET_TYPE, write_manifest

FLOW = """\
# my config
bars:
  main:
    widgets:
      left: ["clock"]  # keep this
      center: []
      right: ["volume"]
widgets:
  clock:
    type: "yasb.clock.ClockWidget"
  volume:
    type: "yasb.volume.VolumeWidget"
"""

BLOCK = """\
bars:
  main:
    widgets:
      left:
        - clock
      right:
        - volume
widgets:
    clock:
        type: yasb.clock.ClockWidget
    volume:
        type: yasb.volume.VolumeWidget
"""

HELLO = {"type": WIDGET_TYPE, "options": {"name": "YASB"}}


def _manifest(folder: Path = FIXTURE) -> PluginManifest:
    _, found = read_manifest(folder)
    assert found.manifest is not None
    return found.manifest


def _add(text: str, folder: Path = FIXTURE) -> tuple[str, AddedWidget | None]:
    return add_widget(text, _manifest(folder), folder)


def _load(text: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(text)
    YasbConfig.model_validate(data)
    return data


def _left(text: str, bar: str = "main") -> list[str]:
    return _load(text)["bars"][bar]["widgets"]["left"]


def _plugin_copy(tmp_path: Path, **manifest_changes: Any) -> Path:
    folder = tmp_path / "plugin"
    shutil.copytree(FIXTURE, folder, ignore=shutil.ignore_patterns("__pycache__"))
    write_manifest(folder, **manifest_changes)
    return folder


# --- adding the widget -----------------------------------------------------------------


def test_widget_goes_first_on_the_left():
    text, added = _add(FLOW)

    assert added == AddedWidget("hello", WIDGET_TYPE, "main")
    assert 'left: ["hello", "clock"]  # keep this' in text
    assert _load(text)["widgets"]["hello"] == HELLO
    assert text.startswith("# my config\n")


def test_empty_left_list():
    text, _ = _add(FLOW.replace('left: ["clock"]', "left: []"))

    assert _left(text) == ["hello"]


def test_block_list_keeps_its_style():
    text, _ = _add(BLOCK)

    assert "      left:\n        - hello\n        - clock\n" in text
    assert "    hello:\n      type:" in text
    assert _load(text)["widgets"]["hello"] == HELLO


def test_bar_without_a_left_list():
    text, _ = _add(BLOCK.replace("      left:\n        - clock\n", ""))

    assert '    widgets:\n      left: ["hello"]\n      right:' in text
    assert _left(text) == ["hello"]


def test_bar_without_widgets():
    text, _ = _add("bars:\n  main:\n    enabled: true\nwidgets:\n  clock:\n    type: yasb.clock.ClockWidget\n")

    assert _left(text) == ["hello"]


def test_first_enabled_bar_is_used():
    config = FLOW.replace(
        "bars:\n  main:\n", "bars:\n  spare:\n    enabled: no\n    widgets:\n      left: []\n  main:\n"
    )

    text, added = _add(config)

    assert added is not None and added.bar == "main"
    assert _left(text) == ["hello", "clock"]
    assert _left(text, "spare") == []


def test_without_bars_only_the_widget_is_added():
    text, added = _add("widgets:\n  clock:\n    type: yasb.clock.ClockWidget\n")

    assert added == AddedWidget("hello", WIDGET_TYPE, None)
    assert yaml.safe_load(text)["widgets"]["hello"] == HELLO


def test_adds_a_widgets_section_when_there_is_none():
    text, _ = _add("bars:\n  main:\n    widgets:\n      left: []\n")

    assert _load(text)["widgets"] == {"hello": HELLO}


def test_keeps_windows_line_endings():
    text, _ = _add(FLOW.replace("\n", "\r\n"))

    assert "\n" not in text.replace("\r\n", "")
    assert _left(text) == ["hello", "clock"]


def test_file_without_a_final_newline():
    text, _ = _add(FLOW.rstrip("\n"))

    assert _load(text)["widgets"]["hello"] == HELLO


def test_config_that_already_uses_the_plugin_is_left_alone():
    moved = (
        FLOW.replace('right: ["volume"]', 'right: ["volume", "greeting"]') + f'  greeting:\n    type: "{WIDGET_TYPE}"\n'
    )

    assert _add(moved) == (moved, None)


def test_default_name_taken_by_another_widget_gets_a_number():
    config = FLOW.replace("  volume:\n", "  hello:\n    type: yasb.clock.ClockWidget\n  volume:\n")

    text, added = _add(config)

    assert added is not None and added.name == "hello_2"
    assert _left(text) == ["hello_2", "clock"]


def test_without_an_example_config_only_the_type_is_written(tmp_path: Path):
    text, added = _add(FLOW, _plugin_copy(tmp_path, example_config=None))

    assert added is not None and added.name == "hello"
    assert _load(text)["widgets"]["hello"] == {"type": WIDGET_TYPE}


def test_plugin_with_several_widgets_adds_its_first_one(tmp_path: Path):
    folder = _plugin_copy(
        tmp_path, example_config=None, widgets={"ByeWidget": "widget:HelloWidget", "HelloWidget": "widget:HelloWidget"}
    )

    text, added = _add(FLOW, folder)

    assert added == AddedWidget("bye", f"plugins.{PLUGIN_ID}.ByeWidget", "main")
    assert _left(text) == ["bye", "clock"]


def test_flow_style_widgets_section_is_refused():
    with pytest.raises(PluginError, match="not a block mapping"):
        _add("bars:\n  main:\n    widgets:\n      left: []\nwidgets: {clock: {type: yasb.clock.ClockWidget}}\n")


# --- removing a plugin's widgets -------------------------------------------------------

WITHOUT = """\
bars:
  main:
    widgets:
      left: ["clock"]  # keep this
      right: ["volume"]
  second:
    widgets:
      left:
        - clock
widgets:
  clock:
    type: "yasb.clock.ClockWidget"
  volume:
    type: "yasb.volume.VolumeWidget"
"""

WITH = f"""\
bars:
  main:
    widgets:
      left: ["hello", "clock"]  # keep this
      right: ["volume", "hello_alt"]
  second:
    widgets:
      left:
        - clock
        - hello
widgets:
  clock:
    type: "yasb.clock.ClockWidget"
  hello:
    type: "{WIDGET_TYPE}"
    options:
      name: "YASB"
  volume:
    type: "yasb.volume.VolumeWidget"
  hello_alt:
    type: "{WIDGET_TYPE}"
"""


def test_remove_takes_the_widgets_out_everywhere():
    cleaned, removed = remove_plugin_widgets(WITH, PLUGIN_ID)

    assert removed == ["hello", "hello_alt"]
    assert cleaned == WITHOUT


def test_remove_undoes_an_add():
    text, _ = _add(FLOW)

    assert remove_plugin_widgets(text, PLUGIN_ID) == (FLOW, ["hello"])


def test_remove_without_plugin_widgets_changes_nothing():
    assert remove_plugin_widgets(FLOW, PLUGIN_ID) == (FLOW, [])


# --- writing config.yaml ---------------------------------------------------------------


def test_edit_config_keeps_a_backup(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(FLOW, encoding="utf-8")

    added = config_edit.edit_config(path, lambda text: _add(text))

    assert added is not None and added.name == "hello"
    assert (tmp_path / "config.yaml.bak").read_text(encoding="utf-8") == FLOW
    assert _left(path.read_text(encoding="utf-8")) == ["hello", "clock"]


def test_edit_config_refuses_to_write_invalid_yaml(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text(FLOW, encoding="utf-8")

    with pytest.raises(PluginError, match="left unchanged"):
        config_edit.edit_config(path, lambda text: (text + "bars: [\n", None))

    assert path.read_text(encoding="utf-8") == FLOW
    assert not (tmp_path / "config.yaml.bak").exists()


# --- yasbc plugin install / remove -----------------------------------------------------


@pytest.fixture
def config(config_home: Path) -> Path:
    path = config_home / "config.yaml"
    path.write_text(FLOW, encoding="utf-8")
    return path


def test_install_adds_the_widget_first_on_the_left(config: Path, capsys: pytest.CaptureFixture[str]):
    assert cli.run(["install", str(FIXTURE)]) == 0

    out = capsys.readouterr().out
    assert f'Added the widget "hello" to {config}, first on the left of bar "main".' in out
    assert _left(config.read_text(encoding="utf-8")) == ["hello", "clock"]
    assert (config.parent / "config.yaml.bak").read_text(encoding="utf-8") == FLOW
    assert (config.parent / "plugins" / "hello" / "manifest.json").is_file()


def test_reinstalling_keeps_where_you_moved_it(config: Path, capsys: pytest.CaptureFixture[str]):
    cli.run(["install", str(FIXTURE)])
    moved = (
        config.read_text(encoding="utf-8")
        .replace('["hello", "clock"]', '["clock"]')
        .replace('["volume"]', '["volume", "hello"]')
    )
    config.write_text(moved, encoding="utf-8")
    capsys.readouterr()

    assert cli.run(["install", str(FIXTURE), "--force"]) == 0

    assert "config.yaml already uses this plugin (hello)" in capsys.readouterr().out
    assert config.read_text(encoding="utf-8") == moved


def test_install_can_keep_the_config(config: Path, capsys: pytest.CaptureFixture[str]):
    assert cli.run(["install", str(FIXTURE), "--keep-config"]) == 0

    assert f'type: "{WIDGET_TYPE}"' in capsys.readouterr().out
    assert config.read_text(encoding="utf-8") == FLOW


def test_install_without_a_config_file(config_home: Path, capsys: pytest.CaptureFixture[str]):
    assert cli.run(["install", str(FIXTURE)]) == 0

    out = capsys.readouterr().out
    assert f"There is no {config_home / 'config.yaml'} yet." in out
    assert f'type: "{WIDGET_TYPE}"' in out


def test_install_with_a_config_it_cannot_edit(config: Path, capsys: pytest.CaptureFixture[str]):
    config.write_text("bars:\n  main: {widgets: {left: []}}\nwidgets: {}\n", encoding="utf-8")

    assert cli.run(["install", str(FIXTURE)]) == 1

    assert "The plugin is installed, but config.yaml was not changed" in capsys.readouterr().err
    assert (config.parent / "plugins" / "hello").is_dir()


def test_remove_takes_the_widget_out_of_the_config(config: Path, capsys: pytest.CaptureFixture[str]):
    cli.run(["install", str(FIXTURE)])

    assert cli.run(["remove", PLUGIN_ID, "-y"]) == 0

    assert f"Removed hello from {config}" in capsys.readouterr().out
    assert config.read_text(encoding="utf-8") == FLOW


def test_remove_can_keep_the_config(config: Path):
    cli.run(["install", str(FIXTURE)])
    configured = config.read_text(encoding="utf-8")

    assert cli.run(["remove", PLUGIN_ID, "-y", "--keep-config"]) == 0

    assert config.read_text(encoding="utf-8") == configured
