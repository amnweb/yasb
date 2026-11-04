# pyright: reportPrivateUsage=false

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtWidgets import QApplication

from core.qml_types import register_qml_types
from core.services.systray import model as model_module
from core.services.systray import systray as systray_module
from core.services.systray.model import IconList, SystrayModel
from core.services.systray.systray import TrayIcon, merge_icon_data
from core.services.systray.systray_monitor import IconData
from core.utils.win32.constants import NIF_STATE, NIF_TIP, NIM_MODIFY, NIM_SETVERSION, NIS_HIDDEN, NIS_SHAREDICON
from core.utils.win32.undocumented import TRAY_VOLUME_ICON_GUID
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import wait


class FakeTray(QObject):
    iconChanged = pyqtSignal(object)
    iconRemoved = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.icons: list[TrayIcon] = []

    def add(self, icon_id: int, exe: str, guid: UUID | None = None) -> TrayIcon:
        image = QImage(16, 16, QImage.Format.Format_ARGB32)
        data = IconData(hWnd=icon_id, uID=1, guid=guid, exe=exe, exe_path=rf"C:\{exe}.exe", icon_image=image)
        icon = TrayIcon(icon_id, data)
        self.icons.append(icon)
        self.iconChanged.emit(icon)
        return icon

    def remove(self, icon: TrayIcon) -> None:
        self.icons.remove(icon)
        self.iconRemoved.emit(icon)


@pytest.fixture
def tray(qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[FakeTray]:
    fake = FakeTray()

    def instance(use_hook: bool = True) -> FakeTray:
        return fake

    def app_data_path(filename: str) -> Path:
        return tmp_path / filename

    def screen_id(screen_name: str) -> str:
        return "SCREEN"

    monkeypatch.setattr(model_module.SystrayIcons, "instance", instance)
    monkeypatch.setattr(model_module, "app_data_path", app_data_path)
    monkeypatch.setattr(model_module, "screen_id", screen_id)
    yield fake


def started(**settings: Any) -> SystrayModel:
    model = SystrayModel()
    for name, value in settings.items():
        model.setProperty(name, value)
    model._start()
    return model


def items(parent: QQuickItem) -> Iterator[QQuickItem]:
    for child in parent.childItems():
        yield child
        yield from items(child)


def exes(icons: IconList) -> list[str]:
    return [icon["tip"] for icon in icons.icons]


def test_icon_list_changes_rows_in_place():
    icons = IconList()
    icons.update([{"iconId": i, "tip": str(i), "source": ""} for i in (1, 2, 3)])
    moves: list[bool] = []
    resets: list[bool] = []
    icons.rowsMoved.connect(lambda *_: moves.append(True))
    icons.modelReset.connect(lambda: resets.append(True))
    icons.update([{"iconId": i, "tip": "new" if i == 1 else str(i), "source": ""} for i in (3, 1, 4)])
    assert [(icon["iconId"], icon["tip"]) for icon in icons.icons] == [(3, "3"), (1, "new"), (4, "4")]
    assert icons.property("count") == 3 and moves and not resets


def test_new_icons_go_where_the_saved_state_has_them(tray: FakeTray, tmp_path: Path):
    (tmp_path / "systray_state_SCREEN.json").write_text(
        json.dumps({r"C:\b.exe": {"is_pinned": True, "index": 0}, r"C:\a.exe": {"is_pinned": False, "index": 1}})
    )
    model = started()
    tray.add(1, "new")
    tray.add(2, "a")
    tray.add(3, "b")
    model._publish()
    assert exes(model._pinned_icons) == ["b"]
    assert exes(model._unpinned_icons) == ["a", "new"]


def test_a_widget_made_after_the_icons_arrived_still_shows_them(tray: FakeTray):
    tray.add(1, "a")
    model = started()
    assert exes(model._unpinned_icons) == ["a"]


def test_hidden_and_filtered_icons_are_not_shown(tray: FakeTray):
    model = started(hideIcons=["Discord"])
    tray.add(1, "discord")
    tray.add(2, "volume", guid=TRAY_VOLUME_ICON_GUID)
    hidden = tray.add(3, "hidden")
    merge_icon_data(hidden.data, IconData(uFlags=NIF_STATE, dwState=NIS_HIDDEN, dwStateMask=NIS_HIDDEN))
    tray.add(4, "shown")
    model._publish()
    assert exes(model._unpinned_icons) == ["shown"]
    model.setProperty("showVolume", True)
    assert exes(model._unpinned_icons) == ["volume", "shown"]


def test_messages_without_an_icon_keep_the_icon(tray: FakeTray):
    model = started()
    icon = tray.add(1, "a")
    # Most apps set the version right after adding the icon, then change the tooltip now and then
    merge_icon_data(icon.data, IconData(message_type=NIM_SETVERSION, hWnd=1, uID=1, uVersion=4))
    merge_icon_data(icon.data, IconData(message_type=NIM_MODIFY, hWnd=1, uID=1, uFlags=NIF_TIP, szTip="Tip"))
    model._publish()
    assert [i["tip"] for i in model._unpinned_icons.icons] == ["Tip"]
    assert icon.data.exe_path == r"C:\a.exe" and icon.data.uVersion == 4


def test_a_state_change_only_touches_the_bits_in_its_mask():
    data = IconData(dwState=NIS_HIDDEN)
    merge_icon_data(data, IconData(uFlags=NIF_STATE, dwState=0, dwStateMask=NIS_SHAREDICON))
    assert data.dwState == NIS_HIDDEN
    merge_icon_data(data, IconData(uFlags=NIF_STATE, dwState=0, dwStateMask=NIS_HIDDEN))
    assert data.dwState == 0


def test_moving_and_pinning_icons_saves_their_order(tray: FakeTray, tmp_path: Path):
    model = started()
    for icon_id, exe in enumerate("abc", 1):
        tray.add(icon_id, exe)
    model._publish()
    # The index counts the dragged icon, so dropping "a" before "c" puts it after "b"
    model.moveIcon(1, False, 2)
    assert exes(model._unpinned_icons) == ["b", "a", "c"]
    model.togglePinned(3)
    model.moveIcon(2, True, 0)
    assert exes(model._pinned_icons) == ["b", "c"]
    assert exes(model._unpinned_icons) == ["a"]

    state = json.loads((tmp_path / "systray_state_SCREEN.json").read_text())
    assert state[r"C:\b.exe"] == {"is_pinned": True, "index": 0}
    assert state[r"C:\c.exe"] == {"is_pinned": True, "index": 1}
    assert state[r"C:\a.exe"] == {"is_pinned": False, "index": 0}


def test_a_removed_icon_leaves(tray: FakeTray):
    model = started()
    icon = tray.add(1, "a")
    model._publish()
    tray.remove(icon)
    model._publish()
    assert exes(model._unpinned_icons) == []


class FakeDesktop:
    """Fake foreground window and menu state for the menu watcher."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.foreground: int | None = os.getpid()
        self.menu = False
        self.other_window = False
        monkeypatch.setattr(model_module, "foreground_pid", lambda: self.foreground)
        monkeypatch.setattr(model_module, "menu_shown", self.menu_shown)
        monkeypatch.setattr(model_module, "other_window_in_front", lambda: self.other_window)

    def menu_shown(self, pid: int) -> bool:
        return self.menu


def test_the_popup_stays_open_while_an_icons_menu_is_up(tray: FakeTray, monkeypatch: pytest.MonkeyPatch):
    desktop = FakeDesktop(monkeypatch)
    model = started()
    tray.add(1, "a")
    model.click(1, 2)
    assert model.property("menuOpen")
    # The app takes focus before showing its menu.
    desktop.foreground = 4321
    model._watch_menu()
    model._watch_menu()
    assert model.property("menuOpen")
    desktop.menu = True
    model._watch_menu()
    assert model.property("menuOpen")
    # Focus returns after the menu closes.
    desktop.menu = False
    model._watch_menu()
    assert model.property("menuOpen")
    assert model._menu_missing_since is not None
    model._menu_missing_since -= 0.3
    model._watch_menu()
    assert not model.property("menuOpen")


def test_a_menu_item_that_opens_a_window_lets_the_popup_close(tray: FakeTray, monkeypatch: pytest.MonkeyPatch):
    desktop = FakeDesktop(monkeypatch)
    model = started()
    tray.add(1, "a")
    model.click(1, 2)
    desktop.foreground, desktop.other_window = 4321, True
    model._watch_menu()
    assert not model.property("menuOpen")


class FakeWindows:
    """Fake foreground window and menu windows for the systray checks."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, class_name: str, style: int, pid: int) -> None:
        self.class_name, self.style, self.pid = class_name, style, pid
        monkeypatch.setattr(systray_module, "FindWindowEx", self.find_window_ex)
        monkeypatch.setattr(systray_module, "GetForegroundWindow", lambda: 100)
        monkeypatch.setattr(systray_module, "IsWindowVisible", self.is_window_visible)
        monkeypatch.setattr(systray_module, "GetClassName", self.get_class_name)
        monkeypatch.setattr(systray_module, "GetWindowLong", self.get_window_long)
        monkeypatch.setattr(systray_module, "get_window_thread_process_id", self.get_window_thread_process_id)

    def find_window_ex(self, parent: int, after: int, class_name: str, window_name: str | None) -> int:
        return 0

    def is_window_visible(self, hwnd: int) -> bool:
        return True

    def get_class_name(self, hwnd: int) -> str:
        return self.class_name

    def get_window_long(self, hwnd: int, index: int) -> int:
        return self.style

    def get_window_thread_process_id(self, hwnd: int) -> tuple[int, int]:
        return 1, self.pid


@pytest.mark.parametrize(
    ("class_name", "style", "pid", "menu", "moved_on"),
    [
        # App-drawn popup menu.
        ("Qt5QWindowPopupDropShadowSaveBits", 0x86000000, 42, True, False),
        # Popup owned by another process.
        ("Qt5QWindowPopupDropShadowSaveBits", 0x86000000, 7, False, False),
        # Explorer desktop and taskbar.
        ("Progman", 0x96000000, 42, False, True),
        ("Shell_TrayWnd", 0x96000000, 42, False, True),
        # Captioned app window.
        ("Notepad", 0x14CF0000, 42, False, True),
    ],
)
def test_what_counts_as_a_menu(
    monkeypatch: pytest.MonkeyPatch, class_name: str, style: int, pid: int, menu: bool, moved_on: bool
):
    FakeWindows(monkeypatch, class_name, style, pid)
    assert systray_module.menu_shown(42) == menu
    assert systray_module.other_window_in_front() == moved_on


def test_a_click_that_shows_nothing_lets_the_popup_close_again(tray: FakeTray, monkeypatch: pytest.MonkeyPatch):
    FakeDesktop(monkeypatch)
    model = started()
    tray.add(1, "a")
    model.click(1, 1)
    model._watch_menu()
    assert model.property("menuOpen")
    model._menu_since -= 3
    model._watch_menu()
    assert not model.property("menuOpen")


def test_pinned_icons_do_not_hold_the_popup(tray: FakeTray, monkeypatch: pytest.MonkeyPatch):
    FakeDesktop(monkeypatch)
    model = started()
    tray.add(1, "a")
    model.togglePinned(1)
    model.click(1, 2)
    assert not model.property("menuOpen")


def test_the_widget_shows_pinned_icons_on_the_bar(tray: FakeTray, tmp_path: Path):
    (tmp_path / "systray_state_SCREEN.json").write_text(json.dumps({r"C:\a.exe": {"is_pinned": True, "index": 0}}))
    tray.add(1, "a")
    tray.add(2, "b")
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Systray" / "Systray.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    wait(50)
    sources = [str(item.property("source")) for item in items(widget) if item.objectName() == "trayIcon"]
    # The unpinned icon waits in the closed popup
    assert sources == ["image://systray/1/0"]
    sip.delete(widget)
