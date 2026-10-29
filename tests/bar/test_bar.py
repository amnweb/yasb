# pyright: reportPrivateUsage=false

import math
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QMetaObject, QPoint, QPointF, QRectF, QUrl
from PyQt6.QtGui import QColor, QContextMenuEvent, QGuiApplication, QWindow
from PyQt6.QtQml import QQmlEngine
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core import widget_files
from core.bar import window
from core.bar.backdrop import Backdrop
from core.bar.hotkeys import WidgetHotkeys, widget_items
from core.bar.window import BarWindow
from core.qml_types import register_qml_types
from core.utils.win32 import app_bar
from core.utils.win32.structs import APPBARDATA
from core.validation.bar import BarConfig
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait
from tests.support.widgets import write_widget

type MakeBar = Callable[..., BarWindow]


@pytest.fixture
def make_bar(qapp: QApplication, fake_app_bar: None) -> Iterator[MakeBar]:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    bars: list[BarWindow] = []

    def make(**config: Any) -> BarWindow:
        screen = QGuiApplication.primaryScreen()
        assert screen is not None
        bar = BarWindow(engine, "test-bar", screen, BarConfig.model_validate(config))
        bars.append(bar)
        return bar

    yield make
    for bar in bars:
        bar.close()
        # A closed bar left alive crashes Qt once a later bar opens a popup window
        bar.deleteLater()
    # Like close_bars: a closed backdrop left alive until Python exits crashes the process there
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


# One entry per option that switches on its own code path
BAR_CONFIGS: dict[str, dict[str, Any]] = {
    "defaults": {},
    "bottom": {"edge": "bottom"},
    "align-left": {"align": "left", "length": 600},
    "align-right": {"align": "right", "length": 600},
    "margin": {"margin": {"top": 4, "left": 8, "bottom": 4, "right": 8}},
    "width-auto": {"length": "auto"},
    "width-percent": {"length": "50%"},
    "no-animation": {"animation": {"type": "none"}},
    "fade-animation": {"animation": {"type": "fade"}},
    "backdrop": {"backdrop": True},
    "always-on-top": {"always_on_top": True},
    "reserve-space": {"reserve_space": True},
    "hide-on-fullscreen": {"always_on_top": True, "hide_on_fullscreen": True},
    "auto-hide": {"auto_hide": "always"},
    "auto-hide-maximized": {"auto_hide": "maximized"},
    "auto-hide-bottom": {"edge": "bottom", "auto_hide": "always", "always_on_top": True},
    "left": {"edge": "left", "align": "top"},
    "right-reserve-space": {"edge": "right", "reserve_space": True},
    "auto-hide-right": {"edge": "right", "auto_hide": "always", "always_on_top": True},
}


@pytest.mark.parametrize("config", BAR_CONFIGS.values(), ids=BAR_CONFIGS.keys())
def test_bar_lifecycle(make_bar: MakeBar, config: dict[str, Any]):
    bar = make_bar(**config)
    wait(50)
    assert bar.load_errors == []
    assert bar.item is not None


@pytest.mark.parametrize("edge", ["top", "bottom"])
def test_bar_sits_at_its_screen_edge(make_bar: MakeBar, edge: str):
    bar = make_bar(edge=edge, thickness=32)
    screen = bar.target_screen.geometry()
    geometry = bar.geometry()
    if edge == "top":
        assert geometry.top() == screen.top()
    else:
        assert geometry.bottom() == screen.bottom()
    assert geometry.height() == 32


def test_auto_width_follows_the_qml_content(make_bar: MakeBar):
    bar = make_bar(length="auto")
    root = bar.item
    assert root is not None
    assert bar.width() == math.ceil(root.implicitWidth())
    root.setImplicitWidth(321)
    assert bar.width() == 321


def test_auto_hide_sets_up_its_manager(make_bar: MakeBar):
    assert make_bar(auto_hide="always").autohide_enabled


def test_maximized_auto_hide_starts_the_watcher(make_bar: MakeBar):
    assert make_bar(auto_hide="maximized")._maximized_watcher is not None
    assert make_bar(auto_hide="maximized", reserve_space=True)._maximized_watcher is None


@pytest.mark.parametrize(
    ("config", "registered"),
    [
        ({"hide_on_fullscreen": True}, False),
        ({"reserve_space": True}, True),
        ({"hide_on_fullscreen": True, "always_on_top": True}, True),
    ],
)
def test_app_bar_registration(make_bar: MakeBar, registered_bars: list[int], config: dict[str, Any], registered: bool):
    bar = make_bar(**config)
    assert (bar.hwnd in registered_bars) is registered


@pytest.mark.parametrize(("animation_type", "edge"), [("slide", "top"), ("slide", "left"), ("fade", "top")])
def test_animations_run_to_completion(make_bar: MakeBar, animation_type: str, edge: str):
    bar = make_bar(edge=edge, animation={"type": animation_type, "duration": 50})
    wait(150)
    resting = bar.geometry()

    bar.hide_bar()
    wait(150)
    assert not bar.isVisible()

    bar.show_bar()
    wait(150)
    assert bar.isVisible()
    assert bar.opacity() == 1.0
    assert bar.geometry() == resting


def test_cli_toggles_the_bar_on_its_own_screen(make_bar: MakeBar):
    bar = make_bar(animation={"type": "none"})
    bar.handle_cli("toggle", "some-other-screen")
    assert bar.isVisible()
    bar.handle_cli("toggle", "")
    assert not bar.isVisible()
    bar.handle_cli("show", bar.target_screen.name())
    assert bar.isVisible()


def test_qml_gets_the_resolved_widget_files(make_bar: MakeBar, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = write_widget(tmp_path, "clock", "import QtQuick\nItem {}\n")
    monkeypatch.setattr(widget_files, "USER_WIDGETS_DIR", tmp_path)
    monkeypatch.setattr(widget_files, "BUILTIN_WIDGETS_DIR", tmp_path / "builtin")

    bar = make_bar(widgets={"left": ["clock", "missing"], "right": ["clock"]})
    clock = {"name": "clock", "url": QUrl.fromLocalFile(str(path)).toString()}
    assert bar.context is not None
    assert bar.context.property("widgets") == {"left": [clock], "right": [clock]}


WIDGET_WIDTHS = {"a": 40, "b": 60, "c": 100, "d": 40}


@pytest.fixture
def widget_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(widget_files, "USER_WIDGETS_DIR", tmp_path)
    monkeypatch.setattr(widget_files, "BUILTIN_WIDGETS_DIR", tmp_path / "builtin")
    for name, width in WIDGET_WIDTHS.items():
        write_widget(tmp_path, name, f'import QtQuick\nRectangle {{ objectName: "{name}"; implicitWidth: {width} }}\n')
    write_widget(tmp_path, "broken", "import QtQuick\nRectangle {\n")
    return tmp_path


def _position(bar: BarWindow, name: str) -> QPointF:
    root = bar.item
    assert root is not None
    item = find_item(root, name)
    assert item is not None, f"{name} was not loaded"
    return item.mapToItem(root, QPointF(0, 0))


def _left(bar: BarWindow, name: str) -> float:
    return _position(bar, name).x()


WIDGETS = {"left": ["a", "b"], "center": ["c"], "right": ["d"]}


def test_sections_split_the_bar_and_keep_the_yaml_order(make_bar: MakeBar, widget_dir: Path):
    bar = make_bar(length=600, widgets=WIDGETS)
    wait(50)
    assert _left(bar, "a") == 8
    assert _left(bar, "b") == 8 + 40 + 8
    assert abs(_left(bar, "c") + 50 - 300) < 1
    assert _left(bar, "d") + 40 == 600 - 8


def test_auto_width_fits_the_widgets(make_bar: MakeBar, widget_dir: Path):
    bar = make_bar(length="auto", widgets=WIDGETS)
    wait(50)
    assert bar.width() == 8 + (40 + 8 + 60) + 100 + 40 + 8
    assert _left(bar, "c") == 8 + 108
    assert _left(bar, "d") + 40 == bar.width() - 8


def _bar_file(folder: Path, body: str) -> str:
    path = folder / "bars" / "top.qml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(body)
    return str(path)


def test_a_bar_file_can_stop_a_slot_from_stretching(make_bar: MakeBar, widget_dir: Path):
    file = _bar_file(widget_dir, "import Yasb.Bar\n\nBar {\n    leftSlot.stretch: false\n}\n")
    bar = make_bar(length=600, widgets=WIDGETS, file=file)
    wait(50)
    center_width = (600 - 16 - 108) / 2
    assert abs(_left(bar, "c") - (8 + 108 + (center_width - 100) / 2)) < 1


def test_a_bar_file_can_align_a_slot(make_bar: MakeBar, widget_dir: Path):
    file = _bar_file(widget_dir, 'import Yasb.Bar\n\nBar {\n    centerSlot.alignment: "left"\n}\n')
    bar = make_bar(length=600, widgets=WIDGETS, file=file)
    wait(50)
    assert abs(_left(bar, "c") - (8 + (600 - 16) / 3)) < 1


def test_a_broken_widget_leaves_no_gap(make_bar: MakeBar, widget_dir: Path):
    bar = make_bar(length=600, widgets={"left": ["a", "broken", "b"]})
    wait(50)
    assert _left(bar, "b") == 8 + 40 + 8


def _root(bar: BarWindow) -> QQuickItem:
    root = bar.item
    assert root is not None
    return root


def test_a_bar_file_sets_the_look(make_bar: MakeBar, widget_dir: Path):
    file = _bar_file(widget_dir, 'import Yasb.Bar\n\nBar {\n    color: "#ff0000"\n    padding: 20\n}\n')
    bar = make_bar(length=600, widgets=WIDGETS, file=file)
    wait(50)
    assert _root(bar).property("color") == QColor("#ff0000")
    assert _left(bar, "a") == 20


def test_invalid_backdrop_shapes_leave_the_bar_without_blur(make_bar: MakeBar, widget_dir: Path):
    file = _bar_file(widget_dir, "import Yasb.Bar\n\nBar {\n    backdropShapes: [{ x: 0, y: 0 }]\n}\n")
    backdrop = make_bar(backdrop=True, file=file)._backdrop_window
    assert backdrop is not None and backdrop._shapes == []


def _opened_backdrop_popup(make_bar: MakeBar, widget_dir: Path, backdrop: bool) -> Backdrop:
    file = _bar_file(
        widget_dir,
        "import QtQuick\nimport Yasb.Bar\nimport Yasb.Common\n\nBar {\n    id: root\n    property alias popup: popup\n"
        "    BackdropPopup {\n        id: popup\n        width: 200\n        height: 120\n        anchor: root\n"
        "        backdropItem: panel\n        Rectangle { id: panel; anchors.fill: parent; radius: 8 }\n    }\n}\n",
    )
    popup = _root(make_bar(backdrop=backdrop, file=file)).property("popup")
    QMetaObject.invokeMethod(popup, "open")
    wait(50)
    helper = popup.findChild(Backdrop)
    assert helper is not None
    return helper


def test_a_backdrop_popup_blurs_behind_its_backdrop_item(make_bar: MakeBar, widget_dir: Path):
    backdrop = _opened_backdrop_popup(make_bar, widget_dir, backdrop=True)._backdrop_window
    assert backdrop is not None and backdrop._shapes == [(QRectF(100, 50, 200, 120), 8.0)]


def test_a_backdrop_popup_has_no_blur_when_its_bar_has_none(make_bar: MakeBar, widget_dir: Path):
    assert _opened_backdrop_popup(make_bar, widget_dir, backdrop=False)._backdrop_window is None


def test_a_custom_layout_places_its_own_slots(make_bar: MakeBar, widget_dir: Path):
    file = _bar_file(
        widget_dir,
        "import QtQuick\nimport Yasb.Bar\n\nBarBase {\n    Row {\n        height: parent.height\n"
        '        WidgetSlot { name: "first" }\n        WidgetSlot { name: "second" }\n    }\n}\n',
    )
    bar = make_bar(length=600, widgets={"first": ["a"], "second": ["c"]}, file=file)
    wait(50)
    assert set(_root(bar).property("slotNames")) == {"first", "second"}
    assert _left(bar, "a") == 8
    assert _left(bar, "c") == 8 + 40


def test_slots_the_bar_file_lacks_are_reported(make_bar: MakeBar, widget_dir: Path, caplog: pytest.LogCaptureFixture):
    make_bar(widgets={"left": ["a"], "tray": ["b", "c"]})
    assert "Bar test-bar has no slot 'tray'" in caplog.text
    assert "'left'" not in caplog.text


@pytest.mark.parametrize(
    "body",
    [None, "import QtQuick\nRectangle {\n", "import QtQuick\n\nItem {}\n"],
    ids=["missing", "syntax-error", "not-a-bar"],
)
def test_a_bad_bar_file_falls_back_to_the_built_in_bar(
    make_bar: MakeBar, widget_dir: Path, monkeypatch: pytest.MonkeyPatch, body: str | None
):
    alerts: list[str] = []

    def alert(**kwargs: str) -> None:
        alerts.append(kwargs["title"])

    monkeypatch.setattr(window, "show_alert", alert)
    file = str(widget_dir / "bars" / "missing.qml") if body is None else _bar_file(widget_dir, body)

    bar = make_bar(widgets=WIDGETS, file=file)
    assert alerts == ["Failed to load the bar file of bar 'test-bar'"]
    assert set(_root(bar).property("slotNames")) == {"left", "center", "right"}


def test_a_widgets_hotkey_runs_its_handler(make_bar: MakeBar, widget_dir: Path):
    write_widget(
        widget_dir,
        "keyed",
        "import QtQuick\nimport Yasb\n\nItem {\n    id: keyed\n\n    property int pressed: 0\n    implicitWidth: 10\n\n"
        '    Hotkey {\n        keys: "win+alt+k"\n        screen: "cursor"\n        onActivated: keyed.pressed += 1\n    }\n}\n',
    )
    bar = make_bar(widgets={"left": ["keyed"]})
    hotkeys = WidgetHotkeys()
    assert [(binding.hotkey, binding.screen) for binding in hotkeys.bindings([bar])] == [("win+alt+k", "cursor")]

    hotkeys.restart([])
    hotkeys._bars = [bar]
    hotkeys._run("alt+win+k", bar.target_screen.name())
    widget = next(item for name, item in widget_items(_root(bar)) if name == "keyed")
    assert widget.property("pressed") == 1


def test_widgets_are_handed_their_bar(make_bar: MakeBar, widget_dir: Path):
    write_widget(
        widget_dir,
        "named",
        'import QtQuick\n\nText {\n    objectName: "named"\n    property Item bar: null\n'
        '    text: bar ? bar.name : ""\n}\n',
    )
    bar = make_bar(widgets={"left": ["named"]})
    named = find_item(_root(bar), "named")
    assert named is not None
    assert named.property("text") == "test-bar"


def test_the_bar_exposes_its_info(make_bar: MakeBar):
    bar = make_bar(edge="bottom")
    root = _root(bar)
    assert (root.property("name"), root.property("edge")) == ("test-bar", "bottom")
    assert root.property("screenName") == bar.target_screen.name()


ISLAND_BAR = 'import Yasb.Bar\n\nIslandBar {\n    color: "#ff0000"\n    padding: 10\n}\n'


def _islands(bar: BarWindow) -> list[list[float]]:
    return _root(bar).property("islands").toVariant()


def test_islands_hug_the_widgets_of_each_slot(make_bar: MakeBar, widget_dir: Path):
    bar = make_bar(length=600, widgets={"left": ["a"], "center": ["c"]}, file=_bar_file(widget_dir, ISLAND_BAR))
    wait(50)
    assert _islands(bar) == [[0, 60], [240, 360]]


def test_an_island_follows_its_widgets(make_bar: MakeBar, widget_dir: Path):
    bar = make_bar(length=600, widgets={"left": ["a"]}, file=_bar_file(widget_dir, ISLAND_BAR))
    wait(50)
    widget = find_item(_root(bar), "a")
    assert widget is not None
    widget.setImplicitWidth(80)
    wait(50)
    assert _islands(bar) == [[0, 100]]


def test_touching_islands_merge(make_bar: MakeBar, widget_dir: Path):
    bar = make_bar(length="auto", widgets=WIDGETS, file=_bar_file(widget_dir, ISLAND_BAR))
    wait(50)
    assert _islands(bar) == [[0, bar.width()]]


def test_a_widget_can_sit_outside_the_islands(make_bar: MakeBar, widget_dir: Path):
    write_widget(widget_dir, "x", "import QtQuick\nItem { property bool island: false; implicitWidth: 30 }\n")
    bar = make_bar(length=600, widgets={"left": ["a", "x", "b"]}, file=_bar_file(widget_dir, ISLAND_BAR))
    wait(50)
    assert _islands(bar) == [[0, 60], [86, 166]]


@pytest.mark.parametrize(("edge", "rail", "gap"), [("top", 2, 20), ("bottom", 27, 10)])
def test_islands_are_drawn_and_the_gaps_left_empty(make_bar: MakeBar, widget_dir: Path, edge: str, rail: int, gap: int):
    file = _bar_file(widget_dir, ISLAND_BAR)
    bar = make_bar(length=600, edge=edge, widgets={"left": ["a"], "center": ["c"]}, file=file)
    bar.show()
    wait(100)
    image = bar.grabWindow()
    assert image.pixelColor(150, rail) == QColor("#ff0000")
    assert image.pixelColor(150, gap).alpha() == 0
    assert image.pixelColor(5, gap) == QColor("#ff0000")


EDGE_CURVES_BAR = ISLAND_BAR.replace("padding: 10", "padding: 10\n    edgeRadius: 14")


@pytest.mark.parametrize(
    ("edge", "item_y", "curve", "hollow", "strip"),
    [("top", 0, (1, 31), (12, 42), (300, 35)), ("bottom", 14, (1, 12), (12, 1), (300, 8))],
)
def test_edge_curves_grow_a_full_width_window(
    make_bar: MakeBar,
    widget_dir: Path,
    edge: str,
    item_y: int,
    curve: tuple[int, int],
    hollow: tuple[int, int],
    strip: tuple[int, int],
):
    bar = make_bar(edge=edge, widgets={"left": ["a"]}, file=_bar_file(widget_dir, EDGE_CURVES_BAR))
    bar.show()
    wait(100)
    screen = bar.target_screen.geometry()
    assert (bar.height(), _root(bar).height(), _root(bar).y()) == (44, 30, item_y)
    assert bar.y() == screen.top() if edge == "top" else bar.geometry().bottom() == screen.bottom()
    image = bar.grabWindow()
    assert image.pixelColor(*curve) == QColor("#ff0000")
    assert image.pixelColor(*hollow).alpha() == 0
    assert bar.mask().contains(QPoint(*curve))
    assert not bar.mask().contains(QPoint(*strip))


def test_edge_curves_need_a_full_width_bar(make_bar: MakeBar, widget_dir: Path):
    bar = make_bar(length=600, widgets={"left": ["a"]}, file=_bar_file(widget_dir, EDGE_CURVES_BAR))
    assert bar.height() == 30
    assert bar.mask().isEmpty()


RED_TO_BLUE = (
    '        GradientStop { position: 0; color: "#ff0000" }\n        GradientStop { position: 1; color: "#0000ff" }\n'
)


def _filled_island_bar(end_point: str) -> str:
    return (
        "import QtQuick\nimport QtQuick.Shapes\nimport Yasb.Bar\n\nIslandBar {\n    id: bar\n    padding: 10\n"
        f"    fillGradient: LinearGradient {{\n        {end_point}\n{RED_TO_BLUE}    }}\n}}\n"
    )


def _gradient_bar(orientation: str) -> str:
    return (
        "import QtQuick\nimport Yasb.Bar\n\nBar {\n    gradient: Gradient {\n"
        f"        orientation: Gradient.{orientation}\n{RED_TO_BLUE}    }}\n}}\n"
    )


def _red(color: QColor) -> bool:
    return color.red() > 200 and color.blue() < 60


def _blue(color: QColor) -> bool:
    return color.blue() > 200 and color.red() < 60


@pytest.mark.parametrize("edge", ["top", "bottom"])
def test_a_vertical_fill_gradient_runs_top_to_bottom_on_either_edge(make_bar: MakeBar, widget_dir: Path, edge: str):
    file = _bar_file(widget_dir, _filled_island_bar("y2: bar.height"))
    bar = make_bar(length=600, edge=edge, widgets={"left": ["a"]}, file=file)
    bar.show()
    wait(100)
    image = bar.grabWindow()
    assert _red(image.pixelColor(5, 1))
    assert _blue(image.pixelColor(5, 28))


def test_a_horizontal_fill_gradient_spans_the_bar(make_bar: MakeBar, widget_dir: Path):
    file = _bar_file(widget_dir, _filled_island_bar("x2: bar.width"))
    bar = make_bar(length=600, widgets={"left": ["a"]}, file=file)
    bar.show()
    wait(100)
    image = bar.grabWindow()
    assert _red(image.pixelColor(5, 2))
    assert _blue(image.pixelColor(595, 2))
    assert image.pixelColor(300, 20).alpha() == 0


def test_a_bar_gradient_replaces_its_color(make_bar: MakeBar, widget_dir: Path):
    bar = make_bar(length=600, widgets={"left": ["a"]}, file=_bar_file(widget_dir, _gradient_bar("Horizontal")))
    bar.show()
    wait(100)
    image = bar.grabWindow()
    assert _red(image.pixelColor(2, 20))
    assert _blue(image.pixelColor(597, 20))


def test_a_changed_gradient_stop_repaints_the_islands(make_bar: MakeBar, widget_dir: Path):
    body = (
        "import QtQuick\nimport QtQuick.Shapes\nimport Yasb.Bar\n\nIslandBar {\n    id: bar\n"
        '    property color first: "#ff0000"\n    padding: 10\n    fillGradient: LinearGradient {\n'
        "        y2: bar.height\n        GradientStop { position: 0; color: bar.first }\n"
        '        GradientStop { position: 1; color: "#0000ff" }\n    }\n}\n'
    )
    bar = make_bar(length=600, widgets={"left": ["a"]}, file=_bar_file(widget_dir, body))
    bar.show()
    wait(100)
    _root(bar).setProperty("first", QColor("#0000ff"))
    wait(100)
    assert _blue(bar.grabWindow().pixelColor(5, 1))


def test_switching_fill_gradients_repaints_the_islands(make_bar: MakeBar, widget_dir: Path):
    body = (
        "import QtQuick\nimport QtQuick.Shapes\nimport Yasb.Bar\n\nIslandBar {\n    id: bar\n"
        "    property bool warm: true\n"
        '    property LinearGradient red: LinearGradient { GradientStop { position: 0; color: "#ff0000" } }\n'
        '    property LinearGradient blue: LinearGradient { GradientStop { position: 0; color: "#0000ff" } }\n'
        "    fillGradient: bar.warm ? bar.red : bar.blue\n}\n"
    )
    bar = make_bar(length=600, widgets={"left": ["a"]}, file=_bar_file(widget_dir, body))
    bar.show()
    wait(100)
    assert _red(bar.grabWindow().pixelColor(5, 1))
    _root(bar).setProperty("warm", False)
    wait(100)
    assert _blue(bar.grabWindow().pixelColor(5, 1))


def _tall_widgets(folder: Path, heights: dict[str, int]) -> None:
    for name, height in heights.items():
        write_widget(folder, name, f'import QtQuick\nRectangle {{ objectName: "{name}"; implicitHeight: {height} }}\n')


def test_a_vertical_bar_stacks_its_slots_top_to_bottom(make_bar: MakeBar, widget_dir: Path):
    _tall_widgets(widget_dir, {"t": 20, "m": 40, "b": 30})
    bar = make_bar(edge="left", length=600, widgets={"top": ["t"], "center": ["m"], "bottom": ["b"]})
    wait(50)
    assert set(_root(bar).property("slotNames")) == {"top", "center", "bottom"}
    assert _position(bar, "t").y() == 8
    assert abs(_position(bar, "m").y() + 20 - 300) < 1
    assert _position(bar, "b").y() + 30 == 600 - 8
    widget = find_item(_root(bar), "t")
    assert widget is not None and widget.width() == bar.width()


@pytest.mark.parametrize(
    ("edge", "item_x", "curve", "hollow", "rail", "gap", "strip"),
    [
        ("left", 0, (31, 1), (42, 12), (2, 300), (20, 300), (37, 300)),
        ("right", 14, (13, 1), (2, 12), (42, 300), (24, 300), (7, 300)),
    ],
)
def test_a_vertical_island_bar_curves_into_the_screen_edges(
    make_bar: MakeBar,
    widget_dir: Path,
    edge: str,
    item_x: int,
    curve: tuple[int, int],
    hollow: tuple[int, int],
    rail: tuple[int, int],
    gap: tuple[int, int],
    strip: tuple[int, int],
):
    _tall_widgets(widget_dir, {"t": 40})
    bar = make_bar(edge=edge, align="top", widgets={"top": ["t"]}, file=_bar_file(widget_dir, EDGE_CURVES_BAR))
    bar.show()
    wait(100)
    assert (bar.width(), _root(bar).width(), _root(bar).x()) == (44, 30, item_x)
    assert _islands(bar) == [[0, 60]]
    image = bar.grabWindow()
    assert image.pixelColor(*curve) == QColor("#ff0000")
    assert image.pixelColor(*hollow).alpha() == 0
    assert image.pixelColor(*rail) == QColor("#ff0000")
    assert image.pixelColor(*gap).alpha() == 0
    assert bar.mask().contains(QPoint(*curve))
    assert not bar.mask().contains(QPoint(*strip))


@pytest.mark.parametrize("edge", ["top", "bottom", "left", "right"])
def test_the_app_bar_reserves_its_screen_edge(qapp: QApplication, edge: str):
    screen = QGuiApplication.primaryScreen()
    assert screen is not None
    area = screen.geometry()
    left, top, right, bottom = area.x(), area.y(), area.x() + area.width(), area.y() + area.height()
    expected = {
        "top": (left, top, right, top + 40),
        "bottom": (left, bottom - 40, right, bottom),
        "left": (left, top, left + 40, bottom),
        "right": (right - 40, top, right, bottom),
    }
    reservation = app_bar.Win32AppBar()
    reservation.app_bar_data = APPBARDATA()
    reservation.app_bar_data.uEdge = window.APP_BAR_EDGES[edge]
    reservation.position_bar(40, screen)
    rc = reservation.app_bar_data.rc
    assert (rc.left, rc.top, rc.right, rc.bottom) == expected[edge]


def _open_windows() -> set[QWindow]:
    return {window for window in QGuiApplication.topLevelWindows() if window.isVisible()}


def _right_click(bar: BarWindow, x: float) -> None:
    point = QPoint(round(x), bar.height() // 2)
    QApplication.sendEvent(bar, QContextMenuEvent(QContextMenuEvent.Reason.Mouse, point, bar.mapToGlobal(point)))
    wait(100)


def test_the_bar_menu_opens_off_widgets_only(make_bar: MakeBar, widget_dir: Path):
    bar = make_bar(length=600, widgets={"left": ["a"]})
    wait(50)
    before = _open_windows()
    _right_click(bar, _left(bar, "a") + 5)
    assert _open_windows() == before

    _right_click(bar, 400)
    menus = _open_windows() - before
    assert len(menus) == 1
    for menu in menus:
        menu.close()


def test_the_bar_context_switches_auto_hide(make_bar: MakeBar):
    bar = make_bar()
    context = bar.context
    assert context is not None
    context.setProperty("autoHide", True)
    assert bar.autohide_enabled and context.property("autoHide")
    context.setProperty("autoHide", False)
    assert not bar.autohide_enabled


def test_a_screenshot_of_the_bar_is_saved(make_bar: MakeBar, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(window, "SCREENSHOT_DIR", tmp_path)
    path = make_bar().save_screenshot()
    assert path is not None and path.parent == tmp_path and path.is_file()
