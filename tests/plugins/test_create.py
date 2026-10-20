import json
import re
import sys
from pathlib import Path

import pytest
import yaml
from PyQt6.QtWidgets import QApplication, QLabel

from core.plugins import cli
from core.plugins.discovery import read_manifest
from core.plugins.manifest import PLUGIN_API_VERSION, PluginError, plugin_widget_type, version_tuple
from core.plugins.template import create_plugin
from core.utils.widget_builder import WidgetBuilder
from settings import BUILD_VERSION


def test_created_plugin_builds_from_its_readme_config(plugins_root: Path, qapp: QApplication):
    folder = create_plugin(plugins_root, "now-playing", 'Now "Playing"', "jdoe", "Shows what's playing")
    readme = (folder / "README.md").read_text(encoding="utf-8")
    example = re.search(r"```yaml\n(.*?)```", readme, re.DOTALL)
    assert example is not None
    widgets = yaml.safe_load(example[1])["widgets"]

    widget = WidgetBuilder(widgets).build_widget("plugin-now-playing")

    assert widgets["plugin-now-playing"]["type"] == plugin_widget_type("now-playing", "NowPlayingWidget")
    assert widget is not None
    label = widget.findChild(QLabel)
    assert label is not None and label.text() == 'Now "Playing"'
    widget.close()


def test_created_manifest_targets_this_yasb(tmp_path: Path):
    folder = create_plugin(tmp_path, "now-playing", "Now Playing", "jdoe", "Shows what's playing")

    _, found = read_manifest(folder)

    assert found.manifest is not None
    assert found.manifest.api == str(PLUGIN_API_VERSION)
    assert version_tuple(found.manifest.min_yasb) == version_tuple(BUILD_VERSION)
    assert found.manifest.widgets == {"NowPlayingWidget": "widget:NowPlayingWidget"}
    assert found.manifest.description == "Shows what's playing"


def test_create_keeps_an_existing_folder(tmp_path: Path):
    create_plugin(tmp_path, "now-playing", "Now Playing", "jdoe", "Shows what's playing")

    with pytest.raises(PluginError, match="already exists"):
        create_plugin(tmp_path, "now-playing", "Other", "someone", "Something else")


def test_cli_asks_step_by_step(config_home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    answers = iter(["Now Playing", "now-playing", "", "Now Playing", "", "jdoe", "x" * 71, "Shows what's playing"])

    def answer(prompt: str) -> str:
        return next(answers)

    monkeypatch.setattr("builtins.input", answer)

    assert cli.run(["create"]) == 0

    out = capsys.readouterr().out
    assert out.count("Use lowercase letters") == 1
    assert out.count("Keep it to 70 characters, this one has 71.") == 1
    manifest = json.loads((config_home / "plugins" / "now-playing" / "manifest.json").read_text(encoding="utf-8"))
    assert (manifest["name"], manifest["author"], manifest["description"]) == (
        "Now Playing",
        "jdoe",
        "Shows what's playing",
    )


def test_cli_empty_answer_stays_on_the_same_line_in_a_terminal(
    config_home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    answers = iter(["", "", "now-playing", "Now Playing", "jdoe", "Shows what's playing"])

    def answer(prompt: str) -> str:
        return next(answers)

    def terminal() -> bool:
        return True

    monkeypatch.setattr("builtins.input", answer)
    monkeypatch.setattr(sys.stdout, "isatty", terminal)

    assert cli.run(["create"]) == 0

    assert capsys.readouterr().out.count("\033[F\033[K") == 2


def test_cli_create_can_be_cancelled(
    config_home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    def closed_input(prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", closed_input)

    assert cli.run(["create"]) == 1

    assert "Cancelled." in capsys.readouterr().err
    assert not (config_home / "plugins").exists()
