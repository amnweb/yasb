from pathlib import Path

import pytest

from core import widget_files
from core.validation.config import YasbConfig
from core.widget_files import WidgetFile, bar_widget_files, component_name, find_widget_file, undefined_widgets


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


@pytest.mark.parametrize(
    ("name", "component"),
    [("clock", "Clock"), ("active_window", "ActiveWindow"), ("media-lite", "MediaLite"), ("cpu2", "Cpu2")],
)
def test_component_name(name: str, component: str):
    assert component_name(name) == component


def test_a_user_file_overrides_the_builtin(widget_dirs: tuple[Path, Path]):
    user, builtin = widget_dirs
    _widget(builtin, "Clock")
    path = _widget(user, "clock")
    assert find_widget_file("clock") == path


def test_a_builtin_is_used_without_a_user_file(widget_dirs: tuple[Path, Path]):
    _, builtin = widget_dirs
    path = _widget(builtin, "ActiveWindow")
    assert find_widget_file("active_window") == path


def test_a_user_file_can_add_its_own_widget(widget_dirs: tuple[Path, Path]):
    user, _ = widget_dirs
    path = _widget(user, "clock_utc")
    assert find_widget_file("clock_utc") == path


def test_a_widget_file_lives_in_its_own_folder(widget_dirs: tuple[Path, Path]):
    user, _ = widget_dirs
    (user / "clock.qml").touch()
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
