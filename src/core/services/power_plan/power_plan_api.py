import ctypes
import logging
import winreg
from ctypes import byref, wintypes
from dataclasses import dataclass
from itertools import count
from typing import TypedDict

from PyQt6 import sip
from PyQt6.QtCore import QObject, QWinEventNotifier, pyqtSignal, pyqtSlot

from core.utils.qml import qml_property
from core.utils.win32.bindings.advapi32 import RegNotifyChangeKeyValue
from core.utils.win32.bindings.kernel32 import CloseHandle, CreateEvent, LocalFree
from core.utils.win32.bindings.powrprof import (
    PowerEnumerate,
    PowerGetActiveScheme,
    PowerReadFriendlyName,
    PowerSetActiveScheme,
)
from core.utils.win32.constants import (
    ACCESS_SCHEME,
    ERROR_MORE_DATA,
    ERROR_NO_MORE_ITEMS,
    ERROR_SUCCESS,
    REG_NOTIFY_CHANGE_LAST_SET,
    REG_NOTIFY_CHANGE_NAME,
)
from core.utils.win32.registry_keys import POWER_SCHEMES_KEY
from core.utils.win32.structs import GUID
from core.utils.worker import run_in_worker

logger = logging.getLogger(__name__)


class Plan(TypedDict):
    id: str
    name: str


@dataclass
class Snapshot:
    plans: list[Plan]
    active_id: str


def _read_name(guid: GUID) -> str:
    size = wintypes.DWORD()
    result = PowerReadFriendlyName(None, byref(guid), None, None, None, byref(size))
    if result not in (ERROR_SUCCESS, ERROR_MORE_DATA):
        raise ctypes.WinError(result)
    buffer = (ctypes.c_ubyte * size.value)()
    result = PowerReadFriendlyName(None, byref(guid), None, None, buffer, byref(size))
    if result != ERROR_SUCCESS:
        raise ctypes.WinError(result)
    return bytes(buffer[: size.value]).decode("utf-16-le").rstrip("\0") or str(guid)


def _read_plans() -> Snapshot:
    plans: list[Plan] = []
    buffer = (ctypes.c_ubyte * ctypes.sizeof(GUID))()
    for index in count():
        size = wintypes.DWORD(len(buffer))
        result = PowerEnumerate(None, None, None, ACCESS_SCHEME, index, buffer, byref(size))
        if result == ERROR_NO_MORE_ITEMS:
            break
        if result != ERROR_SUCCESS:
            raise ctypes.WinError(result)
        guid = GUID.from_buffer_copy(buffer)
        plans.append({"id": str(guid), "name": _read_name(guid)})

    active = ctypes.POINTER(GUID)()
    result = PowerGetActiveScheme(None, byref(active))
    if result != ERROR_SUCCESS:
        raise ctypes.WinError(result)
    if not active:
        raise RuntimeError("Windows did not return an active power plan.")
    try:
        return Snapshot(plans, str(active.contents))
    finally:
        LocalFree(active)


def _select_plan(plan_id: str) -> Snapshot:
    guid = GUID.from_string(plan_id)
    result = PowerSetActiveScheme(None, byref(guid))
    if result != ERROR_SUCCESS:
        raise RuntimeError(f"Could not change the power plan. {ctypes.FormatError(result).strip()}")
    return _read_plans()


class PowerPlans(QObject):
    """The installed power plans and the selection confirmed by Windows, shared by the QML engine."""

    changed = pyqtSignal()
    plansChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._snapshot = Snapshot([], "")
        self._loading = False
        self._error = ""
        self._refresh_pending = False
        self._chosen_id = ""
        self._watch()
        self.refresh()

    @qml_property("QVariantList", notify=plansChanged)
    def plans(self) -> list[Plan]:
        return self._snapshot.plans

    @qml_property(str, notify=changed)
    def activeId(self) -> str:
        return self._snapshot.active_id

    @qml_property(bool, notify=changed)
    def loading(self) -> bool:
        return self._loading

    @qml_property(str, notify=changed)
    def error(self) -> str:
        return self._error

    @pyqtSlot()
    def refresh(self) -> None:
        if self._loading:
            self._refresh_pending = True
            return
        self._start()
        run_in_worker(_read_plans, self._receive, "Could not read Windows power plans.")

    @pyqtSlot(str)
    def selectPlan(self, plan_id: str) -> None:
        if self._loading:
            # Chosen while the plans are read, such as just after the popup opened: applied once they are in
            self._chosen_id = plan_id
            return
        if plan_id == self._snapshot.active_id:
            return
        if not any(plan["id"] == plan_id for plan in self._snapshot.plans):
            return
        self._start()
        run_in_worker(
            lambda: _select_plan(plan_id),
            lambda result, error: self._receive(result, error, plan_id),
            "Could not change the power plan.",
        )

    def _start(self) -> None:
        self._loading = True
        self._error = ""
        self.changed.emit()

    def _receive(self, result: object, error: str, requested_id: str = "") -> None:
        if sip.isdeleted(self):
            return
        previous_plans = self._snapshot.plans
        if isinstance(result, Snapshot):
            self._snapshot = result
            if requested_id and result.active_id != requested_id:
                error = "Windows did not activate the selected power plan."
        self._loading = False
        self._error = error
        pending, self._refresh_pending = self._refresh_pending, False
        chosen, self._chosen_id = self._chosen_id, ""
        if self._snapshot.plans != previous_plans:
            self.plansChanged.emit()
        self.changed.emit()
        if chosen and chosen != self._snapshot.active_id:
            # Selecting reads the plans again after, so it also covers a pending refresh
            self.selectPlan(chosen)
            if self._loading:
                return
        if pending:
            self.refresh()

    def _watch(self) -> None:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, POWER_SCHEMES_KEY, access=winreg.KEY_NOTIFY)
        except OSError:
            logger.debug("Could not watch Windows power plans", exc_info=True)
            return

        handle = CreateEvent(None, False, False, None)
        if not handle:
            key.Close()
            logger.warning("Could not create the power plan change event")
            return

        notifier = QWinEventNotifier(sip.voidptr(handle), self)

        def arm() -> None:
            flags = REG_NOTIFY_CHANGE_LAST_SET | REG_NOTIFY_CHANGE_NAME
            result = RegNotifyChangeKeyValue(key.handle, False, flags, handle, True)
            if result != ERROR_SUCCESS:
                notifier.setEnabled(False)
                logger.warning("Could not watch Windows power plans (%d)", result)

        def changed() -> None:
            arm()
            self.refresh()

        def close() -> None:
            notifier.setEnabled(False)
            key.Close()
            CloseHandle(handle)

        self.destroyed.connect(close)
        notifier.activated.connect(changed)
        arm()
