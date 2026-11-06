# pyright: reportPrivateUsage=false

from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import Q_ARG, QMetaObject, QObject, QPointF, QUrl, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.qml_types import register_qml_types
from core.services.windows_desktops import desktops as desktops_module
from core.services.windows_desktops.com import DesktopInfo, VirtualDesktopError
from core.services.windows_desktops.desktops import VirtualDesktops
from core.services.windows_desktops.service import ForegroundView
from core.utils.hotkey import Hotkey
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item, wait


class FakeDesktopService(QObject):
    desktop_changed = pyqtSignal(dict)
    desktops_updated = pyqtSignal(dict, dict)
    populated_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.desktops = [DesktopInfo(1, "a", ""), DesktopInfo(2, "b", " Work "), DesktopInfo(3, "c", "")]
        self.current = 1
        self.populated = {2}
        self.foreground: ForegroundView | None = ForegroundView(hwnd=11, pinned=False, app_pinned=True)
        self.calls: list[tuple[Any, ...]] = []
        self.widgets: list[QObject] = []

    def changed(self) -> None:
        self.desktops_updated.emit({"index": self.current}, {"update_buttons": True})

    def get_desktops(self) -> list[DesktopInfo]:
        return self.desktops

    def get_populated_desktops(self) -> set[int]:
        return self.populated

    def get_current_desktop(self) -> DesktopInfo:
        return next(desktop for desktop in self.desktops if desktop.number == self.current)

    def get_foreground_app_view(self) -> ForegroundView | None:
        return self.foreground

    def register_widget(self, widget: QObject) -> None:
        self.widgets.append(widget)

    def unregister_widget(self, widget: QObject) -> None:
        self.widgets.remove(widget)

    def notify_desktops_updated(self, update_buttons: bool = False) -> None:
        self.calls.append(("refresh", update_buttons))

    def __getattr__(self, name: str) -> Any:
        if name in (
            "switch_desktop",
            "create_desktop",
            "remove_desktop",
            "rename_desktop",
            "move_window",
            "toggle_pin_window",
            "toggle_pin_app",
            "set_wallpaper",
            "set_wallpaper_all",
        ):

            def record(*args: Any) -> None:
                self.calls.append((name, *args))

            return record
        raise AttributeError(name)


@pytest.fixture
def service(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> FakeDesktopService:
    service = FakeDesktopService()
    monkeypatch.setattr(desktops_module, "WindowsDesktopService", lambda: service)
    return service


def actions(service: FakeDesktopService) -> list[tuple[Any, ...]]:
    return [call for call in service.calls if call[0] != "refresh"]


def test_desktops_current_and_populated_come_from_the_service(service: FakeDesktopService):
    desktops = VirtualDesktops()
    assert desktops.property("current") == 1
    assert [(d["number"], d["name"], d["populated"]) for d in desktops.property("desktops")] == [
        (1, "", False),
        (2, "Work", True),
        (3, "", False),
    ]


def test_a_change_is_announced_only_when_something_changed(service: FakeDesktopService):
    desktops = VirtualDesktops()
    announced: list[bool] = []
    desktops.desktopsChanged.connect(lambda: announced.append(True))
    service.changed()
    assert announced == []
    service.current = 3
    service.desktop_changed.emit({"index": 3})
    service.populated = {1, 2}
    service.populated_changed.emit()
    assert len(announced) == 2 and desktops.property("current") == 3


def test_switching_steps_and_wraps_and_skips_missing_desktops(service: FakeDesktopService):
    desktops = VirtualDesktops()
    desktops.step(-1)
    desktops.step(1)
    desktops.switchTo(9)
    assert actions(service) == [("switch_desktop", 3), ("switch_desktop", 2)]


def test_edits_reach_the_service_and_refresh_it(service: FakeDesktopService):
    desktops = VirtualDesktops()
    desktops.rename(2, "  Games ")
    desktops.remove(0)
    desktops.create()
    assert service.calls == [
        ("rename_desktop", 2, "Games"),
        ("refresh", True),
        ("remove_desktop", 1),
        ("refresh", False),
        ("create_desktop",),
        ("refresh", False),
    ]


def test_a_failing_shell_call_is_logged_not_raised(service: FakeDesktopService, monkeypatch: pytest.MonkeyPatch):
    def fail(*_: object) -> None:
        raise VirtualDesktopError("no desktop")

    monkeypatch.setattr(service, "switch_desktop", fail, raising=False)
    VirtualDesktops().switchTo(2)


def test_menus_act_on_the_window_in_front_when_they_opened(service: FakeDesktopService):
    desktops = VirtualDesktops()
    desktops.moveWindowTo(2)
    assert actions(service) == []
    desktops.readForeground()
    assert (desktops.property("hasWindow"), desktops.property("windowPinned"), desktops.property("appPinned")) == (
        True,
        False,
        True,
    )
    # The menu has taken focus by now, the window it was opened over still counts
    service.foreground = ForegroundView(hwnd=22, pinned=True, app_pinned=False)
    desktops.moveWindowTo(3)
    desktops.toggleWindowPin()
    desktops.moveFrontWindowTo(1)
    assert actions(service) == [("move_window", 11, 3), ("toggle_pin_window", 11), ("move_window", 22, 1)]


def test_a_window_is_not_moved_to_a_missing_desktop(service: FakeDesktopService):
    VirtualDesktops().moveFrontWindowTo(9)
    assert actions(service) == []


def test_renaming_by_number_opens_the_dialog_for_that_desktop(service: FakeDesktopService):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "WindowsDesktops" / "WindowsDesktops.qml"))
    )
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    rename = widget.findChild(QObject, "rename")
    assert rename is not None
    QMetaObject.invokeMethod(widget, "run", Q_ARG("QString", "rename_desktop 3"), Q_ARG("int", 0))
    # The dialog opens for desktop 3, not the one in view
    assert rename.property("number") == 3
    QMetaObject.invokeMethod(rename, "close")
    assert actions(service) == []
    sip.delete(widget)


def test_wallpapers_take_a_file_url(service: FakeDesktopService):
    desktops = VirtualDesktops()
    desktops.setWallpaper(2, QUrl.fromLocalFile("C:/images/sky.png"))
    desktops.setWallpaperAll(QUrl.fromLocalFile("C:/images/sea.png"))
    assert actions(service) == [("set_wallpaper", 2, "C:/images/sky.png"), ("set_wallpaper_all", "C:/images/sea.png")]


def test_the_service_forgets_a_type_once_qml_deleted_it(service: FakeDesktopService):
    desktops = VirtualDesktops()
    assert service.widgets == [desktops]
    sip.delete(desktops)
    assert service.widgets == []


def test_the_widget_labels_desktops_and_runs_actions_and_hotkeys(service: FakeDesktopService):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect)
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "WindowsDesktops" / "WindowsDesktops.qml"))
    )
    widget = component.createWithInitialProperties(
        {
            "label": "{index}",
            "activeLabel": "[{name}]",
            "populatedLabel": "{name}*",
            "keybindings": [{"keys": "alt+2", "action": "switch_desktop 2"}],
        }
    )
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    window = QQuickWindow()
    widget.setParentItem(window.contentItem())
    wait(10)

    captions = [find_item(widget, f"desktop-{number}") for number in (1, 2, 3)]
    assert [item.property("caption") for item in captions if item is not None] == ["[1]", "Work*", "3"]
    assert widget.property("implicitWidth") > 0

    for action, number in (("next_desktop", 0), ("move_window_to 3", 0), ("delete_desktop 2", 0), ("do_nothing", 1)):
        QMetaObject.invokeMethod(widget, "run", Q_ARG("QString", action), Q_ARG("int", number))
    assert actions(service) == [("switch_desktop", 2), ("move_window", 11, 3), ("remove_desktop", 2)]

    # How the bar finds the hotkeys of each widget it loaded
    [hotkey] = widget.findChildren(Hotkey)
    assert hotkey.property("keys") == "alt+2"
    service.calls.clear()
    hotkey.activated.emit()
    assert actions(service) == [("switch_desktop", 2)]
    assert not warnings
    sip.delete(widget)
    sip.delete(window)


@pytest.mark.parametrize("window_in_front", [True, False], ids=["window", "no-window"])
def test_the_menu_opens_and_closes_without_errors(service: FakeDesktopService, window_in_front: bool):
    if not window_in_front:
        service.foreground = None
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect)
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "WindowsDesktops" / "WindowsDesktops.qml"))
    )
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    host = QQuickWindow()
    host.setPosition(100, 40)
    widget.setParentItem(host.contentItem())
    widget.setHeight(32)
    button = find_item(widget, "desktop-2")
    assert button is not None
    bottom = button.mapToGlobal(QPointF(0, button.height())).y()
    before = set(QGuiApplication.topLevelWindows())
    QMetaObject.invokeMethod(widget, "openMenu", Q_ARG("int", 2))
    [menu] = [window for window in QGuiApplication.topLevelWindows() if window not in before and window.isVisible()]
    assert menu.y() == round(bottom + 6)
    # Shown at its final size, a window resized while it opens stutters
    resized: list[int] = []
    menu.widthChanged.connect(resized.append)
    menu.heightChanged.connect(resized.append)
    wait(50)
    assert resized == []
    assert menu.isActive()
    # Clicking outside the menu takes its focus, which closes it
    host.show()
    host.requestActivate()
    wait(50)
    assert sip.isdeleted(menu) or not menu.isVisible()
    assert not warnings
    sip.delete(widget)
    sip.delete(host)


def test_the_garbage_collector_leaves_the_open_menu_alone(service: FakeDesktopService):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "WindowsDesktops" / "WindowsDesktops.qml"))
    )
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    host = QQuickWindow()
    widget.setParentItem(host.contentItem())
    before = set(QGuiApplication.topLevelWindows())
    QMetaObject.invokeMethod(widget, "openMenu", Q_ARG("int", 2))
    [menu] = [window for window in QGuiApplication.topLevelWindows() if window not in before and window.isVisible()]
    engine.collectGarbage()
    wait(50)
    assert not sip.isdeleted(menu) and menu.isVisible()
    menu.close()
    sip.delete(widget)
    sip.delete(host)
