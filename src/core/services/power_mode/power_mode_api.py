import ctypes
from collections.abc import Callable
from ctypes import byref, wintypes
from dataclasses import dataclass

from PyQt6 import sip
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from core.utils.qml import qml_property
from core.utils.win32.bindings.kernel32 import LocalFree
from core.utils.win32.bindings.powrprof import (
    PowerGetActiveScheme,
    PowerGetUserConfiguredACPowerMode,
    PowerGetUserConfiguredDCPowerMode,
    PowerReadACValueIndex,
    PowerSetUserConfiguredACPowerMode,
    PowerSetUserConfiguredDCPowerMode,
    has_power_mode_api,
)
from core.utils.win32.constants import ERROR_SUCCESS, GUID_POWERSCHEME_PERSONALITY
from core.utils.win32.structs import GUID
from core.utils.win32.undocumented import POWER_MODE_BALANCED, POWER_MODE_BEST_EFFICIENCY, POWER_MODE_BEST_PERFORMANCE
from core.utils.worker import run_in_worker

_NO_SUBGROUP = GUID.from_string("fea3413e-7e05-4911-9a71-700331f1c294")
_BALANCED_PERSONALITY = 2
_MODES = {
    "efficiency": ("Best power efficiency", POWER_MODE_BEST_EFFICIENCY),
    "balanced": ("Balanced", POWER_MODE_BALANCED),
    "performance": ("Best performance", POWER_MODE_BEST_PERFORMANCE),
}


@dataclass(frozen=True)
class _Modes:
    supported: bool = False
    ac_id: str = ""
    dc_id: str = ""


def _supports_active_plan() -> bool:
    if not has_power_mode_api:
        return False

    active = ctypes.POINTER(GUID)()
    result = PowerGetActiveScheme(None, byref(active))
    if result != ERROR_SUCCESS:
        raise ctypes.WinError(result)
    if not active:
        raise RuntimeError("Windows did not return an active power plan.")
    try:
        personality = wintypes.DWORD()
        result = PowerReadACValueIndex(
            None, byref(active.contents), byref(_NO_SUBGROUP), byref(GUID_POWERSCHEME_PERSONALITY), byref(personality)
        )
        if result != ERROR_SUCCESS:
            raise ctypes.WinError(result)
        return personality.value == _BALANCED_PERSONALITY
    finally:
        LocalFree(active)


def _read_mode(read: Callable[[GUID], int]) -> str:
    guid = GUID()
    result = read(guid)
    if result != ERROR_SUCCESS:
        raise ctypes.WinError(result)
    return next((mode_id for mode_id, (_, mode_guid) in _MODES.items() if bytes(mode_guid) == bytes(guid)), "")


def _read_modes() -> _Modes:
    if not _supports_active_plan():
        return _Modes()
    return _Modes(
        supported=True,
        ac_id=_read_mode(PowerGetUserConfiguredACPowerMode),
        dc_id=_read_mode(PowerGetUserConfiguredDCPowerMode),
    )


def _set_mode(mode_id: str, source: str) -> _Modes:
    if not _supports_active_plan():
        return _Modes()
    setter = PowerSetUserConfiguredACPowerMode if source == "ac" else PowerSetUserConfiguredDCPowerMode
    result = setter(_MODES[mode_id][1])
    if result != ERROR_SUCCESS:
        raise RuntimeError(f"Could not change the power mode. {ctypes.FormatError(result).strip()}")
    return _read_modes()


class PowerModes(QObject):
    """Windows' configured power modes for plugged-in and battery power, shared by the QML engine."""

    changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = _Modes()
        self._loading = False
        self._error = ""
        self.refresh()

    @qml_property("QVariantList", constant=True)
    def modes(self) -> list[dict[str, str]]:
        return [{"id": mode_id, "name": name} for mode_id, (name, _) in _MODES.items()]

    @qml_property(str, notify=changed)
    def acModeId(self) -> str:
        return self._state.ac_id

    @qml_property(str, notify=changed)
    def dcModeId(self) -> str:
        return self._state.dc_id

    @qml_property(bool, notify=changed)
    def supported(self) -> bool:
        return self._state.supported

    @qml_property(bool, notify=changed)
    def loading(self) -> bool:
        return self._loading

    @qml_property(str, notify=changed)
    def error(self) -> str:
        return self._error

    @pyqtSlot()
    def refresh(self) -> None:
        if self._loading:
            return
        self._start()
        run_in_worker(_read_modes, self._receive, "Could not read Windows power modes.")

    @pyqtSlot(str, str)
    def setMode(self, mode_id: str, source: str) -> None:
        if self._loading or not self._state.supported:
            return
        if mode_id not in _MODES or source not in ("ac", "dc"):
            self._error = "Invalid power mode or power source."
            self.changed.emit()
            return
        self._start()
        run_in_worker(
            lambda: _set_mode(mode_id, source),
            lambda result, error: self._receive(result, error, mode_id, source),
            "Could not change the power mode.",
        )

    def _start(self) -> None:
        self._loading = True
        self._error = ""
        self.changed.emit()

    def _receive(self, result: object, error: str, requested_id: str = "", source: str = "") -> None:
        if sip.isdeleted(self):
            return
        if isinstance(result, _Modes):
            self._state = result
            configured_id = result.ac_id if source == "ac" else result.dc_id
            if requested_id and configured_id != requested_id:
                error = "Windows did not apply the requested power mode."
        self._error = error
        self._loading = False
        self.changed.emit()
