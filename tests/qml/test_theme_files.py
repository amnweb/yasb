from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtQml import QQmlEngine

from core import theme_files
from core.bar.revisions import Revisions
from core.theme_files import find_theme_file, load_theme
from settings import QML_IMPORT_PATH


@pytest.fixture
def themes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "themes"
    folder.mkdir()
    monkeypatch.setattr(theme_files, "DEFAULT_CONFIG_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(theme_files, "USER_THEMES_DIR", folder)
    return folder


@pytest.fixture
def engine(qapp: QGuiApplication) -> Iterator[QQmlEngine]:
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    yield engine
    sip.delete(engine)


def _load(engine: QQmlEngine, theme: str) -> tuple[QObject | None, list[str]]:
    created, _, errors = load_theme(engine, Revisions(), theme, engine)
    return created, errors


def _value(theme: QObject, name: str) -> Any:
    group, prop = name.split(".")
    return theme.property(group).property(prop)


def _is_default(theme: QObject | None) -> bool:
    return theme is not None and _value(theme, "colors.background") in (QColor("#202020"), QColor("#f3f3f3"))


def test_a_name_finds_its_qml_file_in_any_case(themes: Path):
    (themes / "Dracula.qml").write_text("")
    assert str(find_theme_file("DRACULA")) == str(themes / "Dracula.qml")
    assert find_theme_file("nord") is None


def test_a_path_is_relative_to_the_config_folder(themes: Path, tmp_path: Path):
    path = tmp_path / "elsewhere" / "wal.qml"
    path.parent.mkdir()
    path.write_text("")
    assert find_theme_file("elsewhere/wal.qml") == path.resolve()
    assert find_theme_file(str(path)) == path.resolve()


@pytest.mark.parametrize("theme", [None, "default", "Default"])
def test_a_bar_naming_no_theme_gets_the_default(engine: QQmlEngine, theme: str | None):
    created, keys, errors = load_theme(engine, Revisions(), theme, engine)
    assert _is_default(created)
    assert (keys, errors) == (set(), [])


def test_a_qml_theme_keeps_what_it_does_not_set(engine: QQmlEngine, themes: Path):
    (themes / "dracula.qml").write_text('import Yasb.Themes\n\nTheme {\n    colors.accent: "#bd93f9"\n}\n')
    created, errors = _load(engine, "dracula")
    assert errors == []
    assert created is not None
    assert _value(created, "colors.accent") == QColor("#bd93f9")
    assert _value(created, "popup.radius") == 8


def test_a_qml_file_that_is_not_a_theme_is_refused(engine: QQmlEngine, themes: Path):
    (themes / "wrong.qml").write_text("import QtQuick\n\nItem {}\n")
    created, errors = _load(engine, "wrong")
    assert _is_default(created)
    assert "is not a theme" in errors[0]


def test_a_missing_theme_is_reported_and_the_default_used(engine: QQmlEngine, themes: Path):
    created, errors = _load(engine, "nord")
    assert _is_default(created)
    assert "Theme 'nord' not found" in errors[0]
