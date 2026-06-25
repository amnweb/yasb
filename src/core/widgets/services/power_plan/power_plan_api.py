import ctypes
import logging
import threading
import winreg
from ctypes import byref, c_void_p, windll, wintypes
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.events.service import EventService
from core.utils.win32.bindings.powrprof import (
    PowerEnumerate,
    PowerGetActiveScheme,
    PowerReadFriendlyName,
    PowerSetActiveScheme,
)
from core.utils.win32.structs import GUID

logger = logging.getLogger("power_plan_service")

_POWER_SCHEMES_KEY = r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes"
_REG_NOTIFY_CHANGE_LAST_SET = 0x00000004
_WAIT_OBJECT_0 = 0x00000000
_INFINITE = 0xFFFFFFFF


@dataclass
class PowerPlanInfo:
    guid: GUID
    name: str


class PowerPlanService:
    _instance: PowerPlanService | None = None
    _initialized: bool = False
    _reg_thread: threading.Thread | None = None
    _reg_stop_handle: int = 0

    def __new__(cls) -> PowerPlanService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if PowerPlanService._initialized:
            return
        PowerPlanService._initialized = True

    @classmethod
    def instance(cls) -> PowerPlanService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_power_plans(self) -> tuple[list[PowerPlanInfo], GUID | None]:
        """Enumerate all installed power schemes and the currently active one."""
        index = 0
        plans: list[PowerPlanInfo] = []
        while True:
            guid_buf = (ctypes.c_ubyte * 16)()
            size = wintypes.DWORD(16)
            if PowerEnumerate(None, None, None, 16, index, guid_buf, byref(size)) != 0:
                break
            scheme_guid = GUID.from_buffer_copy(guid_buf)
            name_buf = (ctypes.c_ubyte * 1024)()
            name_size = wintypes.DWORD(1024)
            PowerReadFriendlyName(None, byref(scheme_guid), None, None, name_buf, byref(name_size))
            name = bytes(name_buf[: name_size.value]).decode("utf-16", errors="ignore").strip("\x00")
            plans.append(PowerPlanInfo(guid=scheme_guid, name=name))
            index += 1
        return plans, self._get_active_guid()

    def set_power_plan(self, guid: GUID) -> int:
        """Activate guid. Returns 0 (ERROR_SUCCESS) on success."""
        return PowerSetActiveScheme(None, byref(guid))

    @staticmethod
    def guids_equal(guid1: GUID, guid2: GUID) -> bool:
        """Return True if both GUIDs represent the same scheme."""
        try:
            return ctypes.string_at(byref(guid1), ctypes.sizeof(GUID)) == ctypes.string_at(
                byref(guid2), ctypes.sizeof(GUID)
            )
        except Exception:
            return False

    @staticmethod
    def _get_active_guid() -> GUID | None:
        active_ptr = ctypes.POINTER(GUID)()
        if PowerGetActiveScheme(None, byref(active_ptr)) != 0 or not active_ptr:
            return None
        result = GUID.from_buffer_copy(active_ptr.contents)
        windll.kernel32.LocalFree(active_ptr)
        return result

    @classmethod
    def _watch_loop(cls) -> None:
        """Block on RegNotifyChangeKeyValue emit event on every scheme change."""
        kernel32 = windll.kernel32
        kernel32.CreateEventW.restype = c_void_p
        kernel32.WaitForMultipleObjects.restype = wintypes.DWORD

        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, _POWER_SCHEMES_KEY, access=winreg.KEY_NOTIFY | winreg.KEY_READ
            )
        except OSError:
            logger.exception("PowerPlanService failed to open registry key.")
            return

        try:
            while True:
                reg_event = kernel32.CreateEventW(None, True, False, None)
                ret = windll.advapi32.RegNotifyChangeKeyValue(
                    ctypes.c_void_p(key.handle),
                    False,
                    _REG_NOTIFY_CHANGE_LAST_SET,
                    ctypes.c_void_p(reg_event),
                    True,
                )
                if ret != 0:
                    kernel32.CloseHandle(ctypes.c_void_p(reg_event))
                    logger.warning("PowerPlanService RegNotifyChangeKeyValue failed (%d).", ret)
                    break

                handles = (c_void_p * 2)(reg_event, cls._reg_stop_handle)
                result = kernel32.WaitForMultipleObjects(2, handles, False, _INFINITE)
                kernel32.CloseHandle(ctypes.c_void_p(reg_event))

                if result == _WAIT_OBJECT_0:
                    try:
                        EventService().emit_event("power_plan_changed")
                    except Exception:
                        logger.exception("PowerPlanService emit error.")
                else:
                    break
        finally:
            winreg.CloseKey(key)

    @classmethod
    def initialize_listener(cls) -> None:
        """Start the registry watcher."""
        if cls._reg_thread and cls._reg_thread.is_alive():
            return

        kernel32 = windll.kernel32
        kernel32.CreateEventW.restype = c_void_p
        cls._reg_stop_handle = kernel32.CreateEventW(None, True, False, None)
        if not cls._reg_stop_handle:
            logger.warning("PowerPlanService could not create stop event.")
            return

        cls._reg_thread = threading.Thread(target=cls._watch_loop, name="PowerPlanWatcher", daemon=True)
        cls._reg_thread.start()
        logger.info("PowerPlanService started....")

        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(cls.shutdown_listener, Qt.ConnectionType.UniqueConnection)

    @classmethod
    def shutdown_listener(cls) -> None:
        """Stop the registry watcher."""
        if cls._reg_stop_handle:
            windll.kernel32.SetEvent(ctypes.c_void_p(cls._reg_stop_handle))
        if cls._reg_thread and cls._reg_thread.is_alive():
            cls._reg_thread.join(timeout=2.0)
        if cls._reg_stop_handle:
            windll.kernel32.CloseHandle(ctypes.c_void_p(cls._reg_stop_handle))
            cls._reg_stop_handle = 0
        cls._reg_thread = None
        logger.info("PowerPlanService stopped...")
