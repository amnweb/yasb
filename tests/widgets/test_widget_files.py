from pathlib import Path

import pytest

from core import widget_files
from core.validation.config import YasbConfig
from core.widget_files import WidgetFile, bar_widget_files, find_widget_file, undefined_widgets


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
