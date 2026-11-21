import json
import re
from pathlib import Path

import pytest

from core import widget_files
from core.validation.config import YasbConfig
from core.widget_files import (
    WIDGET_LIST,
    WidgetFile,
    bar_widget_files,
    builtin_manifests,
    find_widget_file,
    outdated_widgets,
    undefined_widgets,
)
from settings import SERVICE_API_VERSION


@pytest.fixture
def widget_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    user, builtin = tmp_path / "user", tmp_path / "builtin"
    user.mkdir()
    builtin.mkdir()
    monkeypatch.setattr(widget_files, "USER_WIDGETS_DIR", user)
    monkeypatch.setattr(widget_files, "BUILTIN_WIDGETS_DIR", builtin)
    return user, builtin


def _widget(folder: Path, name: str) -> Path:
    path = folder / name / f"{name}.qml"
    path.parent.mkdir()
    path.touch()
    return path


# Windows paths compare equal whatever their case, so these compare the text QML is given


def test_a_user_file_overrides_the_builtin(widget_dirs: tuple[Path, Path]):
    user, builtin = widget_dirs
    _widget(builtin, "Clock")
    path = _widget(user, "Clock")
    assert str(find_widget_file("Clock")) == str(path)


@pytest.mark.parametrize("name", ["wallpapers", "Wallpapers", "WALLPAPERS"])
def test_any_case_finds_the_widget_spelled_as_on_disk(widget_dirs: tuple[Path, Path], name: str):
    user, builtin = widget_dirs
    path = _widget(user, "Wallpapers")
    assert str(find_widget_file(name)) == str(path)
    path.unlink()
    path.parent.rmdir()
    builtin_path = _widget(builtin, "Wallpapers")
    assert str(find_widget_file(name)) == str(builtin_path)


def test_a_user_file_can_add_its_own_widget(widget_dirs: tuple[Path, Path]):
    user, _ = widget_dirs
    path = _widget(user, "clock_utc")
    assert str(find_widget_file("clock_utc")) == str(path)


@pytest.mark.parametrize("name", ["windows_desktops", "windows-desktops", "Windows_Desktops"])
def test_underscores_and_dashes_name_another_widget(widget_dirs: tuple[Path, Path], name: str):
    user, builtin = widget_dirs
    _widget(builtin, "WindowsDesktops")
    _widget(user, "WindowsDesktops")
    assert find_widget_file(name) is None


def test_a_widget_file_lives_in_its_own_folder(widget_dirs: tuple[Path, Path]):
    user, _ = widget_dirs
    (user / "clock.qml").touch()
    (user / "clock").mkdir()
    (user / "clock" / "main.qml").touch()
    assert find_widget_file("clock") is None


def test_bar_widget_files_keep_their_order_and_skip_unknown_names(widget_dirs: tuple[Path, Path]):
    user, builtin = widget_dirs
    clock = _widget(builtin, "Clock")
    cpu = _widget(user, "cpu")
    config = YasbConfig.model_validate(
        {"bars": {"main": {"widgets": {"left": ["cpu", "missing", "clock"], "right": ["clock"]}}}}
    )
    assert bar_widget_files(config.bars["main"]) == {
        "left": [WidgetFile("cpu", cpu), WidgetFile("clock", clock)],
        "right": [WidgetFile("clock", clock)],
    }


def test_undefined_widgets_ignores_disabled_bars(widget_dirs: tuple[Path, Path]):
    config = YasbConfig.model_validate(
        {
            "bars": {
                "main": {"widgets": {"left": ["b", "a"], "right": ["a"]}},
                "off": {"enabled": False, "widgets": {"left": ["c"]}},
            }
        }
    )
    assert undefined_widgets(config) == ["a", "b"]


def test_a_namespaced_widget_is_found_by_its_own_file_name(widget_dirs: tuple[Path, Path]):
    user, builtin = widget_dirs
    _widget(builtin, "Clock")
    folder = user / "amnweb.clock"
    folder.mkdir()
    (folder / "Clock.qml").touch()
    assert str(find_widget_file("amnweb.clock")) == str(folder / "Clock.qml")
    assert YasbConfig.model_validate({"bars": {"main": {"widgets": {"left": ["amnweb.clock"]}}}})


def _manifest(user: Path, name: str, **fields: object) -> None:
    (user / name / "manifest.json").write_text(json.dumps({"id": name, **fields}), encoding="utf-8")


def test_a_copy_its_manifest_says_no_longer_fits_gives_way_to_the_builtin(widget_dirs: tuple[Path, Path]):
    user, builtin = widget_dirs
    builtin_clock = _widget(builtin, "Clock")
    (builtin / WIDGET_LIST).write_text(json.dumps({"widgets": [{"id": "Clock", "version": 2}]}), encoding="utf-8")
    copy = _widget(user, "Clock")
    _manifest(user, "Clock", version=2, yasbApi=SERVICE_API_VERSION[0])
    assert str(find_widget_file("clock")) == str(copy)

    _manifest(user, "Clock", version=1, yasbApi=SERVICE_API_VERSION[0])
    assert str(find_widget_file("Clock")) == str(builtin_clock)
    config = YasbConfig.model_validate({"bars": {"main": {"widgets": {"left": ["Clock"]}}}})
    assert list(outdated_widgets(config)) == ["Clock"]


def test_a_widget_made_for_another_api_or_under_another_id_is_skipped(widget_dirs: tuple[Path, Path]):
    user, _ = widget_dirs
    _widget(user, "Mine")
    _manifest(user, "Mine", yasbApi=SERVICE_API_VERSION[0] + 1)
    config = YasbConfig.model_validate({"bars": {"main": {"widgets": {"left": ["Mine"]}}}})
    assert find_widget_file("Mine") is None
    assert "YASB API" in outdated_widgets(config)["Mine"]
    assert undefined_widgets(config) == []

    (user / "Mine" / "manifest.json").write_text(json.dumps({"id": "amnweb.mine", "yasbApi": SERVICE_API_VERSION[0]}))
    assert find_widget_file("Mine") is None
    assert "amnweb.mine" in outdated_widgets(config)["Mine"]


def test_the_widget_list_names_every_widget_in_qmldir():
    qmldir = (widget_files.BUILTIN_WIDGETS_DIR / "qmldir").read_text(encoding="utf-8")
    declared = re.findall(r"^(\w+) \d+\.\d+ \1/\1\.qml$", qmldir, flags=re.MULTILINE)
    assert len(declared) > 20
    assert list(builtin_manifests()) == declared
