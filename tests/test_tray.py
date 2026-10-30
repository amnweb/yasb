# pyright: reportPrivateUsage=false

import ctypes
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PyQt6.QtWidgets import QApplication

from core import tray as tray_module
from core.tray import TRAY_MESSAGE, SystemTrayManager
from core.utils.win32.bindings.user32 import RegisterWindowMessage, user32
from core.utils.win32.constants import NIM_ADD, NIM_DELETE, NIM_MODIFY, WM_LBUTTONUP, WM_RBUTTONUP
from core.utils.win32.structs import NOTIFYICONDATAW
from core.validation.config import YasbConfig
from tests.support.qt import wait


class Shell:
    """Stands in for Shell_NotifyIconW, so the tests never touch the real notification area."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str, int]] = []

    def notify(self, action: int, data: Any) -> bool:
        icon = cast(NOTIFYICONDATAW, data._obj)
        self.calls.append((action, icon.szTip, icon.hIcon or 0))
        return True


@pytest.fixture
def shell(monkeypatch: pytest.MonkeyPatch) -> Shell:
    shell = Shell()
    monkeypatch.setattr(tray_module, "shell32", SimpleNamespace(Shell_NotifyIconW=shell.notify))
    return shell


@pytest.fixture
def tray(
    qapp: QApplication, shell: Shell, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[SystemTrayManager]:
    def no_updates(callback: Callable[[Any], object]) -> None:
        pass

    # Laid out like the build, which ships app_icon.png and no .ico
    shutil.copy(Path(tray_module.ICON_DIR) / "app_icon.png", tmp_path / "app_icon.png")
    monkeypatch.setattr(tray_module, "ICON_DIR", str(tmp_path))
    monkeypatch.setattr(tray_module, "register_update_callback", no_updates)
    tray = SystemTrayManager(cast(Any, SimpleNamespace(config=YasbConfig())))
    yield tray
    tray.close()


def test_the_icon_is_added_with_the_app_name_and_removed_on_close(tray: SystemTrayManager, shell: Shell):
    tray.show()
    hwnd = tray._hwnd
    tray.close()
    assert [(action, tip) for action, tip, _ in shell.calls] == [(NIM_ADD, "YASB"), (NIM_DELETE, "YASB")]
    assert shell.calls[0][2] != 0
    assert not user32.IsWindow(hwnd) and tray._hwnd == 0


def test_a_right_click_opens_the_menu_and_a_left_click_does_not(
    tray: SystemTrayManager, monkeypatch: pytest.MonkeyPatch
):
    opened: list[bool] = []
    monkeypatch.setattr(tray, "_show_context_menu", lambda: opened.append(True))
    tray._menu_timer.timeout.disconnect()
    tray._menu_timer.timeout.connect(tray._show_context_menu)
    tray.show()
    user32.SendMessageW(tray._hwnd, TRAY_MESSAGE, 0, WM_LBUTTONUP)
    wait(50)
    assert opened == []
    user32.SendMessageW(tray._hwnd, TRAY_MESSAGE, 0, WM_RBUTTONUP)
    wait(50)
    assert opened == [True]


def test_the_icon_comes_back_after_explorer_restarts(tray: SystemTrayManager, shell: Shell):
    tray.show()
    user32.SendMessageW(tray._hwnd, RegisterWindowMessage("TaskbarCreated"), 0, 0)
    assert [action for action, _, _ in shell.calls] == [NIM_ADD, NIM_ADD]


def test_an_update_shows_a_badged_icon(tray: SystemTrayManager, shell: Shell):
    tray.show()
    plain = shell.calls[0][2]
    tray._set_update_badge(None)
    action, tip, icon = shell.calls[-1]
    assert action == NIM_MODIFY and tip == "Update available" and icon not in (0, plain)
    assert tray._update_available


def test_the_struct_has_the_size_windows_expects():
    assert ctypes.sizeof(NOTIFYICONDATAW) == 976
