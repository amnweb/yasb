# pyright: reportPrivateUsage=false

import os
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QMetaObject, Qt, QUrl
from PyQt6.QtGui import QColor
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError
from PyQt6.QtQuick import QQuickItem, QQuickWindow
from PyQt6.QtWidgets import QApplication

import core.widgets.services.quick_launch.providers.resources.icons as icons
from core.qml_types import register_qml_types
from core.utils.icons.image_provider import _source, icon_url
from core.utils.icons.sources import AppIcon, FileIcon, ProcessIcon, WindowIcon
from core.widget_files import BUILTIN_WIDGETS_DIR
from core.widgets.services.quick_launch.base_provider import ProviderResult
from core.widgets.services.quick_launch.search import ROLES, QuickLaunchSearch, image_url
from core.widgets.services.quick_launch.service import QuickLaunchService
from settings import QML_IMPORT_PATH
from tests.support.qt import wait

PROVIDERS = {"calculator": {"enabled": True, "prefix": "="}, "web_search": {"enabled": True, "prefix": "?"}}


def until(condition: Callable[[], Any]) -> None:
    for _ in range(200):
        if condition():
            return
        wait(10)
    assert condition()


@pytest.fixture(scope="module", autouse=True)
def service(qapp: QApplication) -> Iterator[QuickLaunchService]:
    service = QuickLaunchService.instance()
    yield service
    service._stop_workers()
    QuickLaunchService._instance = None


@pytest.fixture
def search(qapp: QApplication) -> Iterator[QuickLaunchSearch]:
    search = QuickLaunchSearch()
    search.setProperty("providers", PROVIDERS)
    until(lambda: search.property("prefixes"))
    yield search
    search.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


def rows(search: QuickLaunchSearch) -> list[dict[str, Any]]:
    model = search.property("results")
    return [
        {role: model.data(model.index(row), Qt.ItemDataRole.UserRole + i) for i, role in enumerate(ROLES)}
        for row in range(model.rowCount())
    ]


def test_every_icon_constant_points_at_a_file():
    paths = [value for name, value in vars(icons).items() if name.isupper() and str(value).endswith(".svg")]
    assert len(paths) > 100 and all(os.path.isfile(path) for path in paths)


@pytest.mark.parametrize(
    "source",
    [
        WindowIcon(42),
        ProcessIcon(7),
        AppIcon("Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"),
        FileIcon(r"C:\A b\c#d.lnk"),
    ],
)
def test_icon_urls_name_their_source(source: Any):
    kind, value, revision = icon_url(source, 3).removeprefix("image://icon/").split("/")
    assert _source(kind, value) == source and revision == "3"


def test_image_url_tells_files_svg_and_text_apart():
    assert image_url(icons.ICON_APPS) == QUrl.fromLocalFile(icons.ICON_APPS).toString()
    assert image_url("<svg xmlns='http://www.w3.org/2000/svg'/>").startswith("data:image/svg+xml;base64,")
    assert image_url("😀") == ""


def test_a_row_that_is_gone_gives_empty_values_not_undefined(search: QuickLaunchSearch):
    model = search.property("results")
    values = [model.data(model.index(-1), Qt.ItemDataRole.UserRole + i) for i in range(len(ROLES))]
    assert values == ["", "", "", "", False, False, "", ""]


def test_a_prefixed_query_returns_its_provider_results(search: QuickLaunchSearch):
    assert {"=", "?"} <= {p["prefix"] for p in search.property("prefixes")}
    search.search("= 6*7")
    until(lambda: rows(search) and not search.property("loading"))
    [row] = rows(search)
    assert row["title"] == "42" and row["icon"].endswith("icons/calculator.svg") and row["provider"] == "calculator"


def test_the_home_page_lists_prefixes_and_picking_one_requests_it(search: QuickLaunchSearch):
    requested: list[str] = []
    search.prefixRequested.connect(requested.append)
    search.setProperty("homePage", True)
    search.search("")
    titles = [row["title"] for row in rows(search)]
    assert "=" in titles
    search.execute(titles.index("="))
    assert requested == ["="]


def test_colour_rows_ask_the_launcher_for_text_or_the_picker(search: QuickLaunchSearch):
    queries: list[str] = []
    picks: list[str] = []
    search.queryRequested.connect(queries.append)
    search.colorPickRequested.connect(picks.append)
    search.property("results").set_results(
        [
            ProviderResult(title="Random", provider="calculator", action_data={"_replace_input": "random"}),
            ProviderResult(title="Pick", provider="calculator", action_data={"_pick_color": True}),
        ]
    )
    search.execute(0)
    search.execute(1)
    assert queries == ["= random"] and picks == ["= "]


def test_colours_around_a_point_are_read_live_from_the_screen(qapp: QApplication):
    red = QQuickWindow()
    red.setColor(QColor("#FF0000"))
    red.setFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
    red.setGeometry(300, 300, 100, 100)
    red.show()
    try:
        wait(300)
        search = QuickLaunchSearch()
        colours = search.colorsAround(350, 350, 11)
        assert len(colours) == 121 and set(colours) == {"#FF0000"}
        search.deleteLater()
    finally:
        red.close()


def test_a_preview_is_ready_for_qml(search: QuickLaunchSearch):
    image = b"\x89PNG\r\n\x1a\n"
    result = ProviderResult(
        title="file",
        provider="calculator",
        preview={"kind": "image", "image_data": image, "icon": icons.ICON_FILE, "metadata": [("Size", "1 KB")]},
    )
    search.property("results").set_results([result])
    preview = search.preview(0)
    assert preview["image_data"].startswith("data:image/png;base64,")
    assert preview["icon"].endswith("icons/file.svg")
    assert preview["metadata"] == ["Size", "1 KB"] and preview["shown"]


def test_the_widget_searches_without_qml_warnings(qapp: QApplication):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect)
    component = QQmlComponent(engine)
    # The way a user turns providers on: a widget file of their own that overrides the built-in defaults
    component.setData(
        b"import Yasb.Widgets\nQuickLaunch { homePage: true; calculator.enabled: true; webSearch.enabled: true; webSearch.prefix: '??' }",
        QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "QuickLaunch" / "User.qml")),
    )
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    host = QQuickWindow()
    try:
        widget.setParentItem(host.contentItem())
        host.show()
        search = widget.findChild(QuickLaunchSearch)
        assert search is not None
        until(lambda: {p["prefix"] for p in search.property("prefixes")} == {"=", "??"})
        QMetaObject.invokeMethod(widget, "open")
        until(lambda: rows(search))
        search.search("= 2+2")
        until(lambda: [row["title"] for row in rows(search)] == ["4"])
        wait(50)
        assert not warnings
    finally:
        widget.setParentItem(None)
        widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        host.close()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
