from collections.abc import Callable
from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QEvent, QMetaObject, QObject, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QKeyEvent, QWindow
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError, QQmlProperty
from PyQt6.QtQuick import QQuickItem, QQuickWindow

from core.qml_types import register_qml_types
from core.services.taskbar.apps import OpenWindows
from core.services.window_switcher import windows as windows_module
from core.services.window_switcher.windows import WindowList
from core.utils.icons.image_provider import ICON_PROVIDER, IconImageProvider
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.bar import create_with_bar
from tests.support.qt import wait


class Tracked(QObject):
    """Stands in for the windows the taskbar widgets share, so the tests never hook the shell."""

    changed = pyqtSignal()

    def __init__(self, titles: dict[int, str]) -> None:
        super().__init__()
        self.windows: dict[int, dict[str, Any]] = {
            hwnd: {"hwnd": hwnd, "title": title, "monitor": 1, "active": False} for hwnd, title in titles.items()
        }


def stand_in(tracked: Tracked) -> Callable[[type[OpenWindows]], Tracked]:
    """OpenWindows.instance, giving the stand-in."""

    def instance(_cls: type[OpenWindows]) -> Tracked:
        return tracked

    return instance


def test_the_windows_are_listed_front_to_back(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch):
    tracked = Tracked({1: "Mail", 2: "Editor", 3: "Terminal"})
    # Front to back, with windows that are not on a taskbar among them
    z_order = [9, 2, 3, 1]
    monkeypatch.setattr(OpenWindows, "instance", classmethod(stand_in(tracked)))
    monkeypatch.setattr(windows_module, "enum_windows", lambda: z_order)
    listed = WindowList()

    def hwnds() -> list[int]:
        return [window["hwnd"] for window in listed.property("windows")]

    assert hwnds() == [2, 3, 1]
    first = listed.property("windows")[0]
    assert first["title"] == "Editor" and first["icon"].startswith("image://") and "monitor" not in first

    # A window brought to the front, then one closed
    z_order[:] = [1, 2, 3]
    tracked.changed.emit()
    assert hwnds() == [1, 2, 3]
    del tracked.windows[2]
    tracked.changed.emit()
    assert hwnds() == [1, 3]


def test_the_switcher_starts_behind_the_window_in_front_and_works_with_the_keys(
    qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch
):
    tracked = Tracked({1: "Mail", 2: "Editor", 3: "Terminal"})
    monkeypatch.setattr(OpenWindows, "instance", classmethod(stand_in(tracked)))
    monkeypatch.setattr(windows_module, "enum_windows", lambda: [2, 3, 1])

    def in_front(hwnd: int) -> bool:
        return hwnd == 2

    def exists(_hwnd: int) -> bool:
        return True

    monkeypatch.setattr(windows_module, "IsWindow", exists)
    monkeypatch.setattr(windows_module, "is_owner_root_active", in_front)
    monkeypatch.setattr(windows_module, "force_foreground_focus", exists)
    switched: list[int] = []
    closed: list[int] = []
    monkeypatch.setattr(windows_module, "_switch", switched.append)
    monkeypatch.setattr(windows_module, "close_application", closed.append)
    held = [Qt.KeyboardModifier.NoModifier]

    class Keyboard:
        @staticmethod
        def queryKeyboardModifiers() -> Qt.KeyboardModifier:
            return held[0]

    monkeypatch.setattr(windows_module, "QGuiApplication", Keyboard)

    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    engine.addImageProvider(ICON_PROVIDER, IconImageProvider())
    warnings: list[str] = []

    def collect(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect)
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "WindowSwitcher" / "WindowSwitcher.qml"))
    )
    widget = create_with_bar(component)
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    host = QQuickWindow()
    widget.setParentItem(host.contentItem())

    def popup() -> QWindow | None:
        return next(
            (w for w in QGuiApplication.topLevelWindows() if w.title() == "Window Switcher" and w.isVisible()), None
        )

    def press(key: Qt.Key, kind: QEvent.Type = QEvent.Type.KeyPress) -> None:
        window = popup()
        assert window is not None
        QGuiApplication.sendEvent(window, QKeyEvent(kind, key, Qt.KeyboardModifier.NoModifier))

    def state() -> tuple[list[int], int]:
        return list(QQmlProperty.read(widget, "order").toVariant()), QQmlProperty.read(widget, "current")

    def hidden() -> bool:
        # The popup fades out before it hides
        for _ in range(100):
            if popup() is None:
                return True
            wait(10)
        return False

    QMetaObject.invokeMethod(widget, "toggle")
    # Front to back, on the window behind the one in front
    assert popup() is not None and state() == ([2, 3, 1], 1)
    press(Qt.Key.Key_Right)
    press(Qt.Key.Key_Right)
    assert state() == ([2, 3, 1], 2)
    # Delete closes the selected window and keeps the place
    press(Qt.Key.Key_Delete)
    assert closed == [1] and state() == ([2, 3], 1)
    press(Qt.Key.Key_Left)
    press(Qt.Key.Key_Return)
    assert hidden() and switched == [2] and state() == ([], -1)

    # A window closing meanwhile leaves the row
    QMetaObject.invokeMethod(widget, "toggle")
    del tracked.windows[3]
    tracked.changed.emit()
    assert state() == ([2, 1], 1)
    press(Qt.Key.Key_Escape)
    assert hidden() and switched == [2]

    # Opened with alt held, as by "alt+w": opening again moves on, letting go of alt switches
    held[0] = Qt.KeyboardModifier.AltModifier
    QMetaObject.invokeMethod(widget, "toggle")
    wait(10)
    assert state() == ([2, 1], 1)
    QMetaObject.invokeMethod(widget, "toggle")
    assert state() == ([2, 1], 0)
    held[0] = Qt.KeyboardModifier.NoModifier
    press(Qt.Key.Key_Alt, QEvent.Type.KeyRelease)
    assert hidden() and switched == [2, 2]
    assert not warnings
    sip.delete(widget)
    sip.delete(host)
