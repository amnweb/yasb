# pyright: reportPrivateUsage=false

import ctypes
import threading
from collections.abc import Callable

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QMetaObject, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlComponent, QQmlEngine
from PyQt6.QtQuick import QQuickItem

from core.qml_types import register_qml_types
from core.services.power_mode import power_mode_api as api
from core.utils.win32.structs import GUID
from tests.support.qt import wait


def _until(ready: Callable[[], bool]) -> None:
    for _ in range(100):
        if ready():
            return
        wait(20)
    assert ready()


def test_power_modes_are_unavailable_without_the_optional_windows_exports(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api, "has_power_mode_api", False)
    assert api._read_modes() == api._Modes()


def test_custom_qml_can_select_and_confirm_a_mode_for_one_power_source(
    qapp: QGuiApplication, monkeypatch: pytest.MonkeyPatch
):
    ac = api.POWER_MODE_BALANCED
    dc = api.POWER_MODE_BEST_PERFORMANCE
    writes: list[str] = []
    accept = False
    gui_thread = threading.get_ident()

    def read(target: GUID, configured: GUID) -> int:
        assert threading.get_ident() != gui_thread
        ctypes.memmove(ctypes.byref(target), ctypes.byref(configured), ctypes.sizeof(GUID))
        return 0

    def read_ac(target: GUID) -> int:
        return read(target, ac)

    def read_dc(target: GUID) -> int:
        return read(target, dc)

    def set_ac(guid: GUID) -> int:
        nonlocal ac
        assert threading.get_ident() != gui_thread
        writes.append("ac")
        ac = guid
        return 0

    def set_dc(guid: GUID) -> int:
        nonlocal dc
        assert threading.get_ident() != gui_thread
        writes.append("dc")
        if accept:
            dc = guid
        return 0

    monkeypatch.setattr(api, "_supports_active_plan", lambda: True)
    monkeypatch.setattr(api, "PowerGetUserConfiguredACPowerMode", read_ac)
    monkeypatch.setattr(api, "PowerGetUserConfiguredDCPowerMode", read_dc)
    monkeypatch.setattr(api, "PowerSetUserConfiguredACPowerMode", set_ac)
    monkeypatch.setattr(api, "PowerSetUserConfiguredDCPowerMode", set_dc)
    register_qml_types()
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(
        b"""
        import QtQuick
        import Yasb
        Item {
            property string options: PowerModes.modes.map(mode => mode.id).join(",")
            property bool ready: PowerModes.supported && !PowerModes.loading
            property string acMode: PowerModes.acModeId
            property string dcMode: PowerModes.dcModeId
            property string error: PowerModes.error
            function selectBattery() { PowerModes.setMode("efficiency", "dc") }
            function selectPluggedIn() { PowerModes.setMode("performance", "ac") }
        }
        """,
        QUrl(),
    )
    widget = component.create()
    assert isinstance(widget, QQuickItem), [error.toString() for error in component.errors()]
    try:
        _until(lambda: widget.property("ready"))
        assert widget.property("options") == "efficiency,balanced,performance"
        assert (widget.property("acMode"), widget.property("dcMode")) == ("balanced", "performance")

        QMetaObject.invokeMethod(widget, "selectBattery")
        _until(lambda: widget.property("ready"))
        assert widget.property("error") == "Windows did not apply the requested power mode."
        assert (widget.property("acMode"), widget.property("dcMode")) == ("balanced", "performance")

        accept = True
        QMetaObject.invokeMethod(widget, "selectBattery")
        _until(lambda: widget.property("ready"))
        assert widget.property("error") == ""
        assert (widget.property("acMode"), widget.property("dcMode")) == ("balanced", "efficiency")

        QMetaObject.invokeMethod(widget, "selectPluggedIn")
        _until(lambda: widget.property("ready"))
        assert (widget.property("acMode"), widget.property("dcMode")) == ("performance", "efficiency")
        assert writes == ["dc", "dc", "ac"]
    finally:
        sip.delete(widget)
        sip.delete(engine)
