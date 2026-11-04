from typing import Any

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine, QQmlError
from PyQt6.QtQuick import QQuickItem

from core.qml_types import register_qml_types
from core.services.language import keyboard as keyboard_module
from core.services.language.keyboard import KeyboardLanguage, layout_klid
from core.utils.win32.constants import WM_INPUTLANGCHANGEREQUEST
from core.widget_files import BUILTIN_WIDGETS_DIR
from settings import QML_IMPORT_PATH
from tests.support.qt import find_item

ENGLISH = 0x04090409
# Ukrainian (Enhanced), a variant layout whose handle Windows sign extends
UKRAINIAN = 0xFFFFFFFFF0A80422


class Windows:
    """Stands in for the keyboard state, so the tests never switch the real layout."""

    def __init__(self) -> None:
        self.layouts = [UKRAINIAN, ENGLISH]
        self.foreground: tuple[int, int] = (100, ENGLISH)
        self.caps_lock = False
        self.window_class = "Notepad"
        self.posted: list[tuple[int, int, int]] = []
        self.activated: list[int] = []
        self.focused: list[int] = []

    # user32
    def IsWindow(self, hwnd: int) -> bool:
        return hwnd == 100

    def GetClassNameW(self, hwnd: int, buffer: Any, size: int) -> int:
        buffer.value = self.window_class
        return len(self.window_class)

    def SetForegroundWindow(self, hwnd: int) -> bool:
        self.focused.append(hwnd)
        return True

    def PostMessageW(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        self.posted.append((hwnd, msg, lparam))
        return 1

    def ActivateKeyboardLayout(self, hkl: Any, flags: int) -> int:
        self.activated.append(hkl.value)
        return ENGLISH


@pytest.fixture
def windows(qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch) -> Windows:
    windows = Windows()
    monkeypatch.setattr(keyboard_module, "installed_layouts", lambda: list(windows.layouts))
    monkeypatch.setattr(keyboard_module, "foreground_layout", lambda: windows.foreground)
    monkeypatch.setattr(keyboard_module, "caps_lock_on", lambda: windows.caps_lock)
    monkeypatch.setattr(keyboard_module, "layout_text", {"00000409": "US"}.get)
    monkeypatch.setattr(keyboard_module, "user32", windows)
    return windows


def test_the_language_follows_the_window_in_front(windows: Windows):
    keyboard = KeyboardLanguage()
    language = keyboard.property("language")
    assert (language["language_code"], language["country_code"], language["full_name"]) == (
        "en",
        "US",
        "English (United States)",
    )
    windows.foreground = (100, UKRAINIAN)
    keyboard.refresh()
    assert keyboard.property("language")["iso_language_code"] == "ukr"


def test_yasb_windows_keep_the_language_of_the_window_before_them(windows: Windows):
    keyboard = KeyboardLanguage()
    windows.foreground = (200, 0)
    keyboard.refresh()
    assert keyboard.property("language")["language_code"] == "en"


def test_layouts_are_sorted_by_language_and_mark_the_current_one(windows: Windows):
    keyboard = KeyboardLanguage()
    layouts = keyboard.property("layouts")
    assert [(layout["name"], layout["code"], layout["layout"], layout["current"]) for layout in layouts] == [
        ("English (United States)", "ENG", "US", True),
        ("Ukrainian (Ukraine)", "UKR", "Ukrainian (Ukraine)", False),
    ]
    windows.foreground = (100, UKRAINIAN)
    keyboard.refresh()
    assert [layout["current"] for layout in keyboard.property("layouts")] == [False, True]


def test_new_layouts_are_read_when_windows_adds_them(windows: Windows):
    keyboard = KeyboardLanguage()
    windows.layouts = [ENGLISH]
    keyboard.refresh()
    assert [layout["name"] for layout in keyboard.property("layouts")] == ["English (United States)"]


def test_caps_lock_is_read_on_refresh(windows: Windows):
    keyboard = KeyboardLanguage()
    assert keyboard.property("capsLock") is False
    windows.caps_lock = True
    keyboard.refresh()
    assert keyboard.property("capsLock") is True


def test_a_chosen_layout_goes_to_the_window_that_was_in_front(windows: Windows):
    keyboard = KeyboardLanguage()
    keyboard.rememberWindow()
    windows.foreground = (200, 0)
    keyboard.activate(f"{UKRAINIAN:x}")
    assert windows.focused == [100]
    assert windows.posted == [(100, WM_INPUTLANGCHANGEREQUEST, UKRAINIAN)]
    assert keyboard.property("language")["iso_language_code"] == "ukr"


def test_on_the_desktop_the_layout_is_activated_directly(windows: Windows):
    windows.window_class = "Progman"
    keyboard = KeyboardLanguage()
    keyboard.rememberWindow()
    keyboard.activate(f"{UKRAINIAN:x}")
    assert (windows.posted, windows.activated) == ([], [UKRAINIAN])


def test_unknown_layouts_are_ignored(windows: Windows):
    keyboard = KeyboardLanguage()
    keyboard.rememberWindow()
    keyboard.activate("12345678")
    keyboard.activate("not hex")
    assert (windows.posted, windows.activated) == ([], [])


def test_klids_come_from_the_handle_without_activating_it():
    assert layout_klid(ENGLISH) == "00000409"
    assert layout_klid(0xE0010804) == "E0010804"


def test_the_label_formats_placeholders_and_toggles(windows: Windows):
    register_qml_types()
    engine = QQmlEngine()
    engine.addImportPath(QML_IMPORT_PATH)
    warnings: list[str] = []

    def collect_warnings(errors: list[QQmlError]) -> None:
        warnings.extend(error.toString() for error in errors)

    engine.warnings.connect(collect_warnings)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(BUILTIN_WIDGETS_DIR / "Language" / "Language.qml")))
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    label = find_item(widget, "label")
    assert label is not None
    assert label.property("text") == "en-US"
    widget.setProperty("showAlternate", True)
    assert label.property("text") == "English (United States)"
    widget.setProperty("alternateLabel", "{lang[iso_language_code]} {lang[missing]}")
    assert label.property("text") == "eng {lang[missing]}"
    assert not warnings
    sip.delete(widget)
