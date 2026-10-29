import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PyQt6.QtCore import (
    Q_ARG,
    Q_RETURN_ARG,
    QByteArray,
    QDate,
    QDateTime,
    QEventLoop,
    QLocale,
    QMetaObject,
    QObject,
    QTimer,
    QTimeZone,
    QUrl,
)
from PyQt6.QtGui import QColor
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from PyQt6.QtWidgets import QApplication

from core import widget_files
from core.qml_types import register_qml_types
from core.widget_files import BUILTIN_WIDGETS_DIR, find_widget_file
from core.widgets.services.clock.time_zones import TimeZones
from settings import QML_IMPORT_PATH
from tests.support.widgets import write_widget

CLOCK = BUILTIN_WIDGETS_DIR / "Clock" / "Clock.qml"

type MakeClock = Callable[..., QQuickItem]


@pytest.fixture
def engine(qapp: QApplication) -> QQmlEngine:
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    return engine


@pytest.fixture
def make_clock(engine: QQmlEngine) -> Iterator[MakeClock]:
    windows: list[QQuickWindow] = []
    clocks: list[QQuickItem] = []

    def make(path: Path = CLOCK, window_y: int = 0, **properties: Any) -> QQuickItem:
        window = QQuickWindow()
        window.setGeometry(0, window_y, 400, 32)
        windows.append(window)
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(path)))
        initial: dict[str | None, Any] = {name: value for name, value in properties.items()}
        clock = component.createWithInitialProperties(initial)
        assert isinstance(clock, QQuickItem), [error.toString() for error in component.errors()]
        clock.setParentItem(window.contentItem())
        clock.setHeight(32)
        window.show()
        _wait(50)
        clocks.append(clock)
        return clock

    yield make
    for window in windows:
        window.close()


def _wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _zone_time(zone: str, pattern: str) -> str:
    return QLocale().toString(QDateTime.currentDateTime().toTimeZone(QTimeZone(QByteArray(zone.encode()))), pattern)


def _calendar(clock: QQuickItem) -> QObject:
    calendar = clock.findChild(QObject, "calendar")
    assert calendar is not None
    return calendar


def _call(target: QObject, name: str, *args: Any) -> None:
    QMetaObject.invokeMethod(target, name, *args)


def test_clock_is_the_builtin_widget_for_its_name():
    assert find_widget_file("clock") == CLOCK


def test_default_format_shows_hours_and_minutes(make_clock: MakeClock):
    before = QDateTime.currentDateTime().toString("HH:mm")
    text = make_clock().property("text")
    assert text in (before, QDateTime.currentDateTime().toString("HH:mm"))


def test_format_uses_the_given_locale(make_clock: MakeClock):
    clock = make_clock(format="yyyy MMMM", locale="de_DE")
    assert clock.property("text") == QLocale("de_DE").toString(QDateTime.currentDateTime(), "yyyy MMMM")


def test_right_click_format_replaces_the_format(make_clock: MakeClock):
    clock = make_clock(format="'main'", alternateFormat="'alt'")
    assert clock.property("text") == "main"
    _call(clock, "toggleFormat")
    assert clock.property("text") == "alt"


@pytest.mark.parametrize(("format", "longest"), [("HH:mm:ss", 1000), ("HH:mm", 60000)])
def test_the_next_tick_lines_up_with_what_is_shown(make_clock: MakeClock, format: str, longest: int):
    clock = make_clock(format=format)
    wait = QMetaObject.invokeMethod(clock, "nextTick", Q_RETURN_ARG(int))
    assert 0 < wait <= longest


def test_a_user_file_overrides_the_clock_settings(
    make_clock: MakeClock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    user_file = write_widget(tmp_path, "clock", "import Yasb.Widgets\n\nClock {\n    format: \"'custom'\"\n}\n")
    monkeypatch.setattr(widget_files, "USER_WIDGETS_DIR", tmp_path)

    path = find_widget_file("clock")
    assert path is not None
    assert path == user_file
    assert make_clock(path).property("text") == "custom"


@pytest.mark.parametrize("zone", ["UTC", "Asia/Kolkata", "America/New_York"])
def test_time_zones_format_in_the_given_zone(zone: str):
    assert TimeZones().format(zone, "t", "") == _zone_time(zone, "t")


@pytest.mark.parametrize("zone", ["", "local"])
def test_time_zones_use_local_time_without_a_zone(zone: str):
    assert TimeZones().format(zone, "t", "") == QLocale().toString(QDateTime.currentDateTime(), "t")


def test_an_unknown_time_zone_falls_back_to_local_and_warns_once(caplog: pytest.LogCaptureFixture):
    zones = TimeZones()
    with caplog.at_level(logging.WARNING):
        for _ in range(2):
            assert zones.format("Mars/Olympus", "t", "") == QLocale().toString(QDateTime.currentDateTime(), "t")
    assert [record.getMessage() for record in caplog.records].count(
        "Unknown time zone 'Mars/Olympus', showing local time instead"
    ) == 1


def test_middle_click_cycles_through_the_time_zones(make_clock: MakeClock):
    clock = make_clock(format="t", timeZones=["UTC", "Asia/Kolkata"])
    assert clock.property("text") == _zone_time("UTC", "t")
    _call(clock, "nextTimeZone")
    assert clock.property("text") == _zone_time("Asia/Kolkata", "t")
    _call(clock, "nextTimeZone")
    assert clock.property("text") == _zone_time("UTC", "t")


@pytest.mark.parametrize("zone", ["Pacific/Kiritimati", "Pacific/Pago_Pago"])
def test_the_calendar_opens_on_today_in_the_clock_zone(make_clock: MakeClock, zone: str):
    clock = make_clock(timeZones=[zone])
    _call(clock, "toggleCalendar")
    calendar = _calendar(clock)
    assert calendar.property("visible")

    today = QDateTime.currentDateTime().toTimeZone(QTimeZone(QByteArray(zone.encode()))).date()
    shown = calendar.property("today").date()
    assert QDate(shown.year(), shown.month(), shown.day()) == today
    assert (calendar.property("month"), calendar.property("year")) == (today.month() - 1, today.year())

    _call(clock, "toggleCalendar")
    assert not calendar.property("visible")


def test_the_calendar_steps_across_the_new_year(make_clock: MakeClock):
    calendar = _calendar(make_clock(locale="de_DE"))
    calendar.setProperty("year", 2026)
    calendar.setProperty("month", 11)
    title = calendar.findChild(QObject, "title")
    assert title is not None
    assert title.property("text") == f"{QLocale('de_DE').standaloneMonthName(12)} 2026"

    _call(calendar, "showMonth", Q_ARG(int, 1))
    assert (calendar.property("month"), calendar.property("year")) == (0, 2027)


@pytest.fixture
def fake_bar(engine: QQmlEngine) -> QObject:
    component = QQmlComponent(engine)
    component.setData(
        b'import QtQuick\n\nItem {\n    property color textColor: "#123456"\n'
        b'    property font font: Qt.font({ family: "Arial", pixelSize: 20 })\n    property string edge: "top"\n}\n',
        QUrl("fake_bar.qml"),
    )
    bar = component.create()
    assert bar is not None
    return bar


@pytest.mark.parametrize("edge", ["top", "bottom", "left", "right"])
def test_the_calendar_opens_away_from_the_bar_edge(make_clock: MakeClock, fake_bar: QObject, edge: str):
    fake_bar.setProperty("edge", edge)
    clock = make_clock()
    clock.setProperty("bar", fake_bar)
    window = clock.window()
    assert window is not None
    window.setPosition(400, 400)
    _call(clock, "toggleCalendar")
    _wait(50)
    calendar = _calendar(clock)
    x, y = calendar.property("x"), calendar.property("y")
    away = {"top": y >= clock.height(), "bottom": y < 0, "left": x >= clock.width(), "right": x < 0}
    assert away[edge]


def test_the_clock_takes_its_colour_and_font_from_its_bar(make_clock: MakeClock, fake_bar: QObject):
    clock = make_clock()
    clock.setProperty("bar", fake_bar)
    assert clock.property("color") == QColor("#123456")
    assert (clock.property("font").family(), clock.property("font").pixelSize()) == ("Arial", 20)


def test_a_colour_in_the_clock_file_beats_the_bar(make_clock: MakeClock, fake_bar: QObject, tmp_path: Path):
    (tmp_path / "clock.qml").write_text('import Yasb.Widgets\n\nClock {\n    color: "#ff0000"\n}\n')
    clock = make_clock(tmp_path / "clock.qml")
    clock.setProperty("bar", fake_bar)
    assert clock.property("color") == QColor("#ff0000")
