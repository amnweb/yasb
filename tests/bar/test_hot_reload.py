import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PyQt6 import sip
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtQml import QQmlEngine
from watchdog.events import FileModifiedEvent, FileMovedEvent

from core import widget_files
from core.app import watcher
from core.app.watcher import FileModifiedEventHandler
from core.bar import manager as bar_manager
from core.bar import window
from core.bar.manager import QML_RELOAD_DELAY_MS, BarManager
from core.bar.window import BAR_QML, BarWindow
from core.qml_types import register_qml_types
from core.validation.config import YasbConfig
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait
from tests.support.widgets import write_widget

type MakeManager = Callable[..., BarManager]


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "widgets").mkdir()
    (tmp_path / "bars").mkdir()
    monkeypatch.setattr(widget_files, "USER_WIDGETS_DIR", tmp_path / "widgets")
    monkeypatch.setattr(widget_files, "BUILTIN_WIDGETS_DIR", tmp_path / "builtin")
    return tmp_path


@pytest.fixture(autouse=True)
def alerts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    titles: list[str] = []

    def alert(title: str, message: str, details: str = "") -> None:
        titles.append(title)

    for module in (widget_files, window, bar_manager):
        monkeypatch.setattr(module, "show_alert", alert)
    return titles


@pytest.fixture
def make_manager(qapp: QGuiApplication, fake_app_bar: None) -> Iterator[MakeManager]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    managers: list[BarManager] = []

    def make(**bars: dict[str, Any]) -> BarManager:
        manager = BarManager(YasbConfig.model_validate({"bars": bars}), engine)
        manager.initialize_bars()
        managers.append(manager)
        return manager

    yield make
    for manager in managers:
        manager.close_bars()
    # Deleted here, after the bars' items it created; left to Python, the garbage collector can delete it on any thread
    sip.delete(engine)


def _widget(folder: Path, name: str, text: str) -> Path:
    source = (
        f'import QtQuick\n\nText {{\n    objectName: "{name}"\n    property Item bar: null\n    text: "{text}"\n}}\n'
    )
    return write_widget(folder / "widgets", name, source)


def _bar_file(folder: Path, color: str) -> Path:
    path = folder / "bars" / "top.qml"
    path.write_text(f'import Yasb.Bar\n\nBar {{\n    color: "{color}"\n}}\n')
    return path


def _changed(manager: BarManager, path: Path) -> None:
    manager.qml_changed.emit(str(path))
    wait(QML_RELOAD_DELAY_MS + 200)


def _text(bar: BarWindow, name: str) -> str | None:
    assert bar.item is not None
    item = find_item(bar.item, name)
    return None if item is None else item.property("text")


def _color(bar: BarWindow) -> QColor:
    assert bar.item is not None
    return bar.item.property("color")


def _text_color(bar: BarWindow) -> QColor:
    assert bar.item is not None
    return bar.item.property("theme").property("colors").property("text")


def test_editing_the_bar_file_reloads_it_in_the_same_window(make_manager: MakeManager, folder: Path):
    path = _bar_file(folder, "#ff0000")
    manager = make_manager(top={"layout": str(path)})
    bar = manager.bars[0]
    window, before = bar.hwnd, bar.item

    _bar_file(folder, "#0000ff")
    _changed(manager, path)
    assert bar.item is not before
    assert _color(bar) == QColor("#0000ff")
    assert bar.hwnd == window


def test_a_broken_bar_file_keeps_the_current_bar(
    make_manager: MakeManager, folder: Path, alerts: list[str], caplog: pytest.LogCaptureFixture
):
    path = _bar_file(folder, "#ff0000")
    manager = make_manager(top={"layout": str(path)})
    bar = manager.bars[0]
    before = bar.item

    path.write_text("import Yasb.Bar\n\nBar {\n")
    with caplog.at_level(logging.ERROR):
        _changed(manager, path)
    assert bar.item is before
    assert _color(bar) == QColor("#ff0000")
    assert f"{path} has errors, bars keep the current version" in caplog.text
    assert alerts == ["A QML file has errors"]

    _bar_file(folder, "#00ff00")
    _changed(manager, path)
    assert _color(bar) == QColor("#00ff00")


def test_a_bar_file_that_is_not_a_bar_keeps_the_current_bar(
    make_manager: MakeManager, folder: Path, alerts: list[str], caplog: pytest.LogCaptureFixture
):
    path = _bar_file(folder, "#ff0000")
    manager = make_manager(top={"layout": str(path)})
    bar = manager.bars[0]
    before = bar.item

    path.write_text("import QtQuick\n\nItem {}\n")
    with caplog.at_level(logging.ERROR):
        _changed(manager, path)
    assert bar.item is before
    assert "Bar top kept its current content" in caplog.text
    assert alerts == ["Failed to reload the layout of bar 'top'"]


def test_widget_edits_apply_while_the_bar_file_is_broken(make_manager: MakeManager, folder: Path):
    bar_path = _bar_file(folder, "#ff0000")
    widget_path = _widget(folder, "a", "one")
    manager = make_manager(top={"layout": str(bar_path), "widgets": {"left": ["a"]}})
    bar = manager.bars[0]

    bar_path.write_text("import Yasb.Bar\n\nBar {\n")
    _changed(manager, bar_path)
    _widget(folder, "a", "two")
    _changed(manager, widget_path)
    assert _text(bar, "a") == "two"
    assert _color(bar) == QColor("#ff0000")


def test_widget_edits_apply_to_the_built_in_fallback(make_manager: MakeManager, folder: Path):
    bar_path = folder / "bars" / "broken.qml"
    bar_path.write_text("import Yasb.Bar\n\nBar {\n")
    widget_path = _widget(folder, "a", "one")
    manager = make_manager(top={"layout": str(bar_path), "widgets": {"left": ["a"]}})
    bar = manager.bars[0]
    assert bar.shown_file == BAR_QML

    _widget(folder, "a", "two")
    _changed(manager, widget_path)
    assert _text(bar, "a") == "two"
    assert bar.shown_file == BAR_QML


def test_a_layout_is_found_by_name_in_the_layouts_folder(
    make_manager: MakeManager, folder: Path, monkeypatch: pytest.MonkeyPatch
):
    layouts = folder / "layouts"
    layouts.mkdir()
    monkeypatch.setattr(window, "USER_LAYOUTS_DIR", layouts)
    (layouts / "Islands.qml").write_text('import Yasb.Bar\n\nBar {\n    color: "#00ff00"\n}\n')
    manager = make_manager(named={"layout": "islands"}, builtin={"layout": "DEFAULT"})
    named, builtin = manager.bars
    # In the case it has on disk, which QML needs
    assert str(named.bar_file) == str(layouts / "Islands.qml")
    assert _color(named) == QColor("#00ff00")
    assert builtin.bar_file == BAR_QML


def test_qml_files_no_bar_loads_are_left_alone(
    make_manager: MakeManager, folder: Path, alerts: list[str], caplog: pytest.LogCaptureFixture
):
    path = _bar_file(folder, "#ff0000")
    manager = make_manager(top={"layout": str(path)})
    bar = manager.bars[0]
    before = bar.item

    # Not a layout, theme or widget of any bar: not even compiled
    other = folder / "bars" / "other.qml"
    other.write_text("import Yasb.Bar\n\nBar {\n")
    with caplog.at_level(logging.ERROR):
        _changed(manager, other)
    assert bar.item is before
    assert alerts == [] and "has errors" not in caplog.text
    assert not manager.uses_file(str(other))
    assert manager.uses_file(str(path)) and manager.uses_file(str(folder / "widgets" / "a" / "a.qml"))


def test_editing_a_widget_reloads_only_the_bars_using_it(make_manager: MakeManager, folder: Path):
    path = _widget(folder, "a", "one")
    _widget(folder, "b", "other")
    manager = make_manager(first={"widgets": {"left": ["a"]}}, second={"widgets": {"left": ["b"]}})
    first, second = manager.bars
    untouched = second.item

    _widget(folder, "a", "two")
    _changed(manager, path)
    assert _text(first, "a") == "two"
    assert second.item is untouched


def _theme_source(text: str) -> str:
    return f'import Yasb.Themes\n\nTheme {{\n    colors.text: "{text}"\n}}\n'


def test_editing_a_theme_swaps_it_into_the_bars_using_it(
    make_manager: MakeManager, folder: Path, alerts: list[str], monkeypatch: pytest.MonkeyPatch
):
    theme = folder / "wal.qml"
    theme.write_text(_theme_source("#ff0000"))
    manager = make_manager(top={"theme": str(theme)}, other={})
    bar, other = manager.bars
    before, untouched = bar.item, other.item
    restarts: list[list[BarWindow]] = []
    monkeypatch.setattr(manager.hotkeys, "restart", restarts.append)
    assert _text_color(bar) == QColor("#ff0000")

    theme.write_text(_theme_source("#00ff00"))
    _changed(manager, theme)
    assert _text_color(bar) == QColor("#00ff00")
    # Not built again, so its widgets keep any window they opened, and their hotkeys
    assert bar.item is before
    assert other.item is untouched
    assert restarts == []

    theme.write_text("import Yasb.Themes\n\nTheme {\n")
    _changed(manager, theme)
    assert _text_color(bar) == QColor("#00ff00")
    assert alerts == ["A QML file has errors"]


def test_a_broken_widget_keeps_the_current_version(
    make_manager: MakeManager, folder: Path, alerts: list[str], caplog: pytest.LogCaptureFixture
):
    path = _widget(folder, "a", "one")
    manager = make_manager(top={"widgets": {"left": ["a"]}})
    bar = manager.bars[0]
    before = bar.item

    path.write_text("import QtQuick\n\nText {\n")
    with caplog.at_level(logging.ERROR):
        _changed(manager, path)
    assert bar.item is before
    assert _text(bar, "a") == "one"
    assert f"{path} has errors, bars keep the current version" in caplog.text
    assert alerts == ["A QML file has errors"]

    _widget(folder, "a", "fixed")
    _changed(manager, path)
    assert _text(bar, "a") == "fixed"


def test_a_broken_widget_at_startup_is_reported(make_manager: MakeManager, folder: Path, alerts: list[str]):
    write_widget(folder / "widgets", "a", "import QtQuick\n\nText {\n")
    _widget(folder, "b", "fine")
    bar = make_manager(top={"widgets": {"left": ["a", "b"]}}).bars[0]
    assert alerts == ["Some widgets could not load"]
    assert _text(bar, "b") == "fine"


def test_a_widget_file_added_later_shows_up(make_manager: MakeManager, folder: Path):
    manager = make_manager(top={"widgets": {"left": ["late"]}})
    bar = manager.bars[0]
    assert _text(bar, "late") is None

    _changed(manager, _widget(folder, "late", "here"))
    assert _text(bar, "late") == "here"


class _Signal:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def emit(self, *args: Any) -> None:
        self.calls.append(args)


def _handler(watch: bool = True) -> tuple[FileModifiedEventHandler, _Signal, _Signal]:
    qml_changed, config_modified = _Signal(), _Signal()
    manager = SimpleNamespace(
        config=SimpleNamespace(watch=watch), qml_changed=qml_changed, config_modified=config_modified
    )
    return FileModifiedEventHandler(cast(Any, manager)), qml_changed, config_modified


def test_the_watcher_passes_qml_changes_on(tmp_path: Path):
    handler, qml_changed, config_modified = _handler()
    handler.dispatch(FileModifiedEvent(str(tmp_path / "bar.qml")))
    handler.dispatch(FileMovedEvent(str(tmp_path / "bar.qml.tmp"), str(tmp_path / "widgets" / "clock.qml")))
    handler.dispatch(FileModifiedEvent(str(tmp_path / "yasb.log")))
    assert qml_changed.calls == [(str(tmp_path / "bar.qml"),), (str(tmp_path / "widgets" / "clock.qml"),)]
    assert config_modified.calls == []


def test_the_watcher_skips_a_qml_event_without_new_content(tmp_path: Path):
    handler, qml_changed, _ = _handler()
    path = tmp_path / "clock.qml"
    path.write_text("Text {}\n")
    handler.dispatch(FileModifiedEvent(str(path)))
    handler.dispatch(FileModifiedEvent(str(path)))
    assert len(qml_changed.calls) == 1

    path.write_text('Text { text: "x" }\n')
    handler.dispatch(FileModifiedEvent(str(path)))
    assert len(qml_changed.calls) == 2


def test_the_watcher_reloads_only_the_real_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config = tmp_path / "config.yaml"
    other = tmp_path / "widgets" / "config.yaml"
    monkeypatch.setattr(watcher, "get_config_path", lambda: str(config))
    handler, _, config_modified = _handler()
    other.parent.mkdir()
    other.write_text("bars: {}\n")
    config.write_text("bars: {}\n")

    handler.dispatch(FileModifiedEvent(str(other)))
    assert config_modified.calls == []
    handler.dispatch(FileModifiedEvent(str(config)))
    assert config_modified.calls == [()]


def test_the_watcher_does_nothing_when_watching_is_off(tmp_path: Path):
    handler, qml_changed, _ = _handler(watch=False)
    handler.dispatch(FileModifiedEvent(str(tmp_path / "bar.qml")))
    assert qml_changed.calls == []
