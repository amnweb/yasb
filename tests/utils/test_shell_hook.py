# pyright: reportPrivateUsage=false

import ctypes

from PyQt6 import sip
from PyQt6.QtGui import QGuiApplication

from core.utils.win32 import shell_hook
from core.utils.win32.constants import HSHELL_MONITORCHANGED, HSHELL_WINDOWCREATED
from core.utils.win32.shell_hook import _ShellHook, _ShellSignal, shell_event
from core.utils.win32.structs import MSG

SHELLHOOK = 0xC100


def send(hook: _ShellHook, hwnd: int, message: int, code: int, window: int) -> bool:
    msg = MSG(hwnd, message, code, window, 0, 0, 0)
    taken, _ = hook.nativeEventFilter("windows_generic_MSG", sip.voidptr(ctypes.addressof(msg)))
    return taken


def test_each_message_for_its_window_reaches_its_signal(qapp: QGuiApplication):
    hook = _ShellHook()
    # Offscreen there is no real window, so the test gives it one
    hook.hwnd, hook.message = 77, SHELLHOOK
    hook.signals = {HSHELL_WINDOWCREATED: _ShellSignal(), HSHELL_MONITORCHANGED: _ShellSignal()}
    created: list[int] = []
    moved: list[int] = []
    hook.signals[HSHELL_WINDOWCREATED].triggered.connect(created.append)
    hook.signals[HSHELL_MONITORCHANGED].triggered.connect(moved.append)

    assert send(hook, 77, SHELLHOOK, HSHELL_MONITORCHANGED, 5)
    assert (created, moved) == ([], [5])
    # Messages for other windows, such as one of Qt's own, are left to Qt
    assert not send(hook, 88, SHELLHOOK, HSHELL_WINDOWCREATED, 6)
    assert not send(hook, 77, 0x0010, HSHELL_WINDOWCREATED, 6)
    assert created == []


def test_nothing_is_registered_without_a_real_window(qapp: QGuiApplication):
    hook = _ShellHook()
    assert hook.hwnd == 0
    assert not send(hook, 0, 0, HSHELL_WINDOWCREATED, 5)
    hook.stop()


def test_every_widget_shares_one_hook_window(qapp: QGuiApplication):
    shell_event(HSHELL_WINDOWCREATED)
    hook = shell_hook._hook
    assert hook is not None
    created = hook.signals[HSHELL_WINDOWCREATED]
    # Widgets on two bars asking for the same messages
    for _ in range(3):
        shell_event(HSHELL_WINDOWCREATED)
        shell_event(HSHELL_MONITORCHANGED)
    assert shell_hook._hook is hook
    assert hook.signals[HSHELL_WINDOWCREATED] is created
    assert {HSHELL_WINDOWCREATED, HSHELL_MONITORCHANGED} <= set(hook.signals)
