# pyright: reportPrivateUsage=false

import itertools
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PyQt6.QtCore import QEventLoop, QPoint, QTimer
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication, QLabel

from core.bar import Bar
from core.bar_style import AdaptiveBarFrame
from core.utils.win32 import app_bar
from core.validation.bar import BarConfig
from core.widgets.base import BaseWidget

BAR_HEIGHT = 30
RAIL = 4
EDGE_RADIUS = 10
EXCLUDED = "excluded"
BACKGROUND = QColor(200, 0, 0)
BORDER = QColor(0, 0, 255)

type Groups = dict[str, list[BaseWidget]]
type MakeBar = Callable[..., Bar]


class _FakeAppBar:
    def create_appbar(self, *args: Any, **kwargs: Any) -> None:
        pass

    def remove_appbar(self) -> None:
        pass


def _wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _widget(width: int, name: str | None = None) -> BaseWidget:
    widget = BaseWidget()
    widget.setFixedWidth(width)
    widget.widget_name = name
    return widget


def _frame(bar: Bar) -> AdaptiveBarFrame:
    frame = bar.bar_frame
    assert isinstance(frame, AdaptiveBarFrame)
    return frame


@pytest.fixture
def make_bar(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[MakeBar]:
    monkeypatch.setattr(app_bar, "Win32AppBar", _FakeAppBar)
    bars: list[Bar] = []

    def make(css: str = "", groups: Groups | None = None, rules: str = "", **config: Any) -> Bar:
        screen = QApplication.primaryScreen()
        assert screen is not None
        bar = Bar(
            bar_id="adaptive",
            bar_name="adaptive",
            bar_screen=screen,
            stylesheet=f".bar {{ background: rgb(200, 0, 0); qproperty-railheight: {RAIL}; {css} }} {rules}",
            widgets={"left": [], "center": [], "right": [], **(groups or {})},
            config=BarConfig.model_validate(
                {
                    "style": "adaptive",
                    "style_adaptive_exclude": [EXCLUDED],
                    "animation": {"enabled": False},
                    "dimensions": {"height": BAR_HEIGHT},
                    **config,
                }
            ),
            init=True,
        )
        bars.append(bar)
        _wait(20)
        return bar

    yield make
    for bar in bars:
        bar.skip_animation = True
        bar.close()


LAYOUTS: dict[str, Callable[[], Groups]] = {
    "edges_and_centre": lambda: {"left": [_widget(100)], "center": [_widget(120)], "right": [_widget(80)]},
    "centre_only": lambda: {"center": [_widget(120)]},
    "empty": lambda: {},
    "excluded_at_edge": lambda: {"left": [_widget(60, EXCLUDED), _widget(100)], "center": [_widget(120)]},
}

COMBINATIONS = list(itertools.product(("top", "bottom"), (True, False), (0, EDGE_RADIUS), (False, True), LAYOUTS))


def _combination_id(combination: tuple[str, bool, int, bool, str]) -> str:
    position, islands, edge_radius, border, layout = combination
    return "-".join(
        (
            position,
            "islands" if islands else "no_islands",
            f"edgeradius{edge_radius}",
            "border" if border else "no_border",
            layout,
        )
    )


def _painted(color: QColor, expected: QColor) -> bool:
    channels = (
        (color.red(), expected.red()),
        (color.green(), expected.green()),
        (color.blue(), expected.blue()),
    )
    return color.alpha() > 200 and all(abs(a - b) < 40 for a, b in channels)


def _broken_rules(bar: Bar, position: str, islands: bool, edge_radius: int, border: bool) -> list[str]:
    frame = _frame(bar)
    problems: list[str] = []
    width, height = frame.width(), frame.height()
    overhang = frame.edge_overhang
    spans = frame._islands

    if spans != frame._island_spans():
        problems.append(f"the painted islands {spans} are stale, the widgets say {frame._island_spans()}")
    if overhang != edge_radius:
        problems.append(f"a full-width bar with edgeradius {edge_radius} reserved {overhang} for the edge curves")
    if (height, bar.height()) != (BAR_HEIGHT + overhang, BAR_HEIGHT + overhang):
        problems.append(f"frame {height} / window {bar.height()} high, expected {BAR_HEIGHT + overhang}")

    band_top = overhang if position == "bottom" else 0
    band_bottom = band_top + BAR_HEIGHT
    click = frame.click_rect()
    if (click.top(), click.height()) != (band_top, BAR_HEIGHT):
        problems.append(f"clicks are taken in {click.getRect()}, the bar is rows {band_top}-{band_bottom - 1}")

    rail_y = band_bottom - 2 if position == "bottom" else band_top + 1
    deep_y = band_top + 3 if position == "bottom" else band_bottom - 4
    inner_edge_y = band_top if position == "bottom" else band_bottom - 1
    rail_edge_y = band_bottom - RAIL if position == "bottom" else band_top + RAIL - 1

    image: QImage = frame.grab().toImage()

    layout = frame.layout()
    assert layout is not None
    for index in range(layout.count()):
        item = layout.itemAt(index)
        container = item.widget() if item else None
        if container is None:
            continue
        for child in container.findChildren(BaseWidget):
            top = child.mapTo(frame, QPoint(0, 0)).y()
            if top < band_top or top + child.height() > band_bottom:
                problems.append(f"widget at rows {top}-{top + child.height() - 1} reaches into the edge curve strip")
            x = child.mapTo(frame, QPoint(0, 0)).x() + child.width() // 2
            covered = any(start <= x < end for start, end in spans)
            if child.widget_name == EXCLUDED:
                if islands and covered:
                    problems.append(f"excluded widget at x={x} sits on an island {spans}")
            elif not covered:
                problems.append(f"widget at x={x} has no island under it {spans}")

    for start, end in spans:
        x = (start + end) // 2
        if not _painted(image.pixelColor(x, deep_y), BACKGROUND):
            problems.append(f"island {start}-{end} is not painted at x={x}: {image.pixelColor(x, deep_y).getRgb()}")
        if border and not _painted(image.pixelColor(x, inner_edge_y), BORDER):
            problems.append(f"island {start}-{end} has no border: {image.pixelColor(x, inner_edge_y).getRgb()}")

    edges = [0, *(x for span in spans for x in span), width]
    for start, end in zip(edges[::2], edges[1::2], strict=True):
        if end - start < 40:
            continue
        x = (start + end) // 2
        if image.pixelColor(x, deep_y).alpha() > 1:
            problems.append(f"the gap {start}-{end} is not cut out at x={x}: {image.pixelColor(x, deep_y).getRgb()}")
        if not _painted(image.pixelColor(x, rail_y), BACKGROUND):
            problems.append(f"no rail over the gap {start}-{end}: {image.pixelColor(x, rail_y).getRgb()}")
        if border and not _painted(image.pixelColor(x, rail_edge_y), BORDER):
            problems.append(f"no border along the rail over {start}-{end}: {image.pixelColor(x, rail_edge_y).getRgb()}")

    if overhang:
        strip_y = overhang // 2 if position == "bottom" else band_bottom + overhang // 2
        if image.pixelColor(width // 2, strip_y).alpha() > 1:
            problems.append(
                f"the edge curve strip is painted mid-bar: {image.pixelColor(width // 2, strip_y).getRgb()}"
            )

    return problems


@pytest.mark.parametrize(
    ("position", "islands", "edge_radius", "border", "layout"),
    COMBINATIONS,
    ids=[_combination_id(combination) for combination in COMBINATIONS],
)
def test_every_combination_keeps_the_rules(
    make_bar: MakeBar, position: str, islands: bool, edge_radius: int, border: bool, layout: str
):
    css = f"qproperty-edgeradius: {edge_radius}; qproperty-islands: {'true' if islands else 'false'};"
    if border:
        css += " qproperty-borderwidth: 2; qproperty-bordercolor: rgb(0, 0, 255);"
    bar = make_bar(css, LAYOUTS[layout](), alignment={"position": position})

    problems = _broken_rules(bar, position, islands, edge_radius, border)

    assert not problems, "\n".join(problems)


def test_an_island_grows_with_its_widget(make_bar: MakeBar):
    clock = BaseWidget()
    label = QLabel("12:00")
    clock.widget_layout.addWidget(label)
    frame = _frame(make_bar(groups={"center": [clock]}))
    (before,) = frame._islands

    label.setText("12:00 Wednesday 7 October 2026")
    _wait(20)

    (after,) = frame._islands
    assert after[0] < before[0] and after[1] > before[1], f"the island stayed {before} -> {after}"
    gained = (after[0] + before[0]) // 2
    image = frame.grab().toImage()
    assert _painted(image.pixelColor(gained, BAR_HEIGHT - 4), BACKGROUND), "the grown part is not painted"


def test_an_excluded_widget_splits_its_group(make_bar: MakeBar):
    excluded = _widget(80, EXCLUDED)
    frame = _frame(make_bar(groups={"center": [_widget(100), excluded, _widget(100)]}))

    middle = excluded.mapTo(frame, QPoint(0, 0)).x() + excluded.width() // 2
    assert len(frame._islands) == 2, f"expected an island either side of the excluded widget: {frame._islands}"
    assert frame.grab().toImage().pixelColor(middle, BAR_HEIGHT - 4).alpha() <= 1, "the excluded widget is covered"


@pytest.mark.parametrize("dimensions", [{"width": "auto"}, {"width": 600}], ids=["auto_width", "fixed_width"])
def test_the_edge_curves_need_a_full_width_bar(make_bar: MakeBar, dimensions: dict[str, Any]):
    bar = make_bar(
        f"qproperty-edgeradius: {EDGE_RADIUS};",
        {"center": [_widget(120)]},
        dimensions={**dimensions, "height": BAR_HEIGHT},
    )

    assert _frame(bar).edge_overhang == 0
    assert bar.height() == BAR_HEIGHT


@pytest.mark.parametrize("position", ["top", "bottom"])
def test_changing_edgeradius_keeps_the_bar_on_its_edge(make_bar: MakeBar, position: str):
    groups = {"center": [_widget(120)]}
    bar = make_bar("qproperty-edgeradius: 0;", groups, alignment={"position": position})
    screen = bar.target_screen.geometry()
    before = bar.geometry()

    bar.setStyleSheet(
        f".bar {{ background: rgb(200, 0, 0); qproperty-railheight: {RAIL}; qproperty-edgeradius: {EDGE_RADIUS}; }}"
    )
    assert bar.geometry() == before, (
        "the bar moved during the stylesheet reload, while Windows still shows its old picture"
    )
    _wait(20)

    assert bar.height() == BAR_HEIGHT + EDGE_RADIUS
    if position == "top":
        assert bar.geometry().top() == screen.top() + bar.padding["top"], "a top bar must grow downwards"
    else:
        assert bar.geometry().bottom() == screen.bottom() - bar.padding["bottom"], "a bottom bar must grow upwards"


def test_an_island_near_the_screen_edge_snaps_to_it(make_bar: MakeBar):
    frame = _frame(make_bar(groups={"left": [_widget(100)]}, rules=".container-left { padding-left: 12px; }"))

    (island,) = frame._islands
    assert island[0] == 0, f"the island stops {island[0]}px short of the screen edge"
    assert _painted(frame.grab().toImage().pixelColor(1, BAR_HEIGHT - 2), BACKGROUND), "the corner at the edge is cut"
