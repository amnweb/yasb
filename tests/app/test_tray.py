# pyright: reportPrivateUsage=false

import ctypes
import logging
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from PyQt6.QtGui import QGuiApplication

from core.app import tray as tray_module
from core.app.tray import TRAY_MESSAGE, SystemTrayManager
from core.utils.win32.bindings.user32 import RegisterWindowMessage, user32
from core.utils.win32.constants import NIM_ADD, NIM_DELETE, NIM_MODIFY, WM_LBUTTONUP, WM_RBUTTONUP
from core.utils.win32.structs import NOTIFYICONDATAW
from core.validation.config import GlazeWMConfig, KomorebiConfig, YasbConfig


class Shell:
    """Stands in for Shell_NotifyIconW, so the tests never touch the real notification area. It refuses everything
    while the taskbar isn't up, adding the icon while it is there, and changing or removing it while it is not."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str, int]] = []
        self.ready = True
        self.has_icon = False

    def notify(self, action: int, data: Any) -> bool:
        icon = cast(NOTIFYICONDATAW, data._obj)
        self.calls.append((action, icon.szTip, icon.hIcon or 0))
        if not self.ready or (action == NIM_ADD) == self.has_icon:
            return False
        if action != NIM_MODIFY:
            self.has_icon = action == NIM_ADD
        return True


@pytest.fixture
def shell(monkeypatch: pytest.MonkeyPatch) -> Shell:
    shell = Shell()
    monkeypatch.setattr(tray_module, "shell32", SimpleNamespace(Shell_NotifyIconW=shell.notify))
    return shell


@pytest.fixture
def tray(
    qapp: QGuiApplication, shell: Shell, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
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
    tray.show()
    user32.SendMessageW(tray._hwnd, TRAY_MESSAGE, 0, WM_LBUTTONUP)
    assert opened == []
    user32.SendMessageW(tray._hwnd, TRAY_MESSAGE, 0, WM_RBUTTONUP)
    assert opened == [True]


def test_the_menu_offers_an_installed_window_managers_commands_and_runs_the_chosen_one(
    tray: SystemTrayManager, monkeypatch: pytest.MonkeyPatch
):
    config = YasbConfig(
        komorebi=KomorebiConfig(start_command="komorebic start", stop_command="komorebic stop"),
        glazewm=GlazeWMConfig(start_command="glazewm start"),
    )
    monkeypatch.setattr(tray._bar_manager, "config", config)
    items: dict[str, int] = {}

    def installed(program: str) -> str | None:
        # Komorebi is installed, GlazeWM is not
        return "komorebi.exe" if program == "komorebi" else None

    def append(menu: int, flags: int, item: int, label: str) -> bool:
        items[label] = item
        return True

    def choose(menu: int, flags: int, x: int, y: int, hwnd: int) -> int:
        return items["Stop Komorebi"]

    monkeypatch.setattr(tray_module.shutil, "which", installed)
    monkeypatch.setattr(tray_module, "AppendMenu", append)
    monkeypatch.setattr(tray_module, "TrackPopupMenu", choose)
    ran: list[str] = []
    monkeypatch.setattr(tray_module, "_run_hidden", ran.append)
    tray._show_context_menu()
    assert {"Start Komorebi", "Stop Komorebi", "Komorebi"} <= items.keys() and "Reload Komorebi" not in items
    assert "GlazeWM" not in items and "Start GlazeWM" not in items
    assert ran == ["komorebic stop"]


def test_the_icon_comes_back_after_explorer_restarts(tray: SystemTrayManager, shell: Shell):
    tray.show()
    # Explorer starts again without it
    shell.has_icon = False
    user32.SendMessageW(tray._hwnd, RegisterWindowMessage("TaskbarCreated"), 0, 0)
    assert [action for action, _, _ in shell.calls] == [NIM_ADD, NIM_ADD] and shell.has_icon


def test_the_systray_widgets_broadcast_updates_the_icon_and_leaves_it_to_be_removed(
    tray: SystemTrayManager, shell: Shell, caplog: pytest.LogCaptureFixture
):
    tray.show()
    # Sent to have every app add its icons, while this one is still there
    user32.SendMessageW(tray._hwnd, RegisterWindowMessage("TaskbarCreated"), 0, 0)
    tray.close()
    assert [action for action, _, _ in shell.calls] == [NIM_ADD, NIM_ADD, NIM_MODIFY, NIM_DELETE]
    assert not shell.has_icon and not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_an_icon_the_taskbar_was_not_up_for_is_added_once_it_is(tray: SystemTrayManager, shell: Shell):
    shell.ready = False
    tray.show()
    shell.ready = True
    user32.SendMessageW(tray._hwnd, RegisterWindowMessage("TaskbarCreated"), 0, 0)
    assert [action for action, _, _ in shell.calls] == [NIM_ADD, NIM_ADD] and shell.has_icon


def test_an_update_shows_a_badged_icon(tray: SystemTrayManager, shell: Shell):
    tray.show()
    plain = shell.calls[0][2]
    tray._set_update_badge(None)
    action, tip, icon = shell.calls[-1]
    assert action == NIM_MODIFY and tip == "Update available" and icon not in (0, plain)
    assert tray._update_available


def test_the_struct_has_the_size_windows_expects():
    assert ctypes.sizeof(NOTIFYICONDATAW) == 976
