import ctypes
import ctypes.wintypes as wintypes

from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.constants import TH32CS_SNAPPROCESS
from core.utils.win32.structs import PROCESSENTRY32


def is_process_running(process_name: str) -> bool:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return False

    try:
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)

        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return False

        target = process_name.lower()
        while True:
            if entry.szExeFile.lower() == target:
                return True
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
        return False
    finally:
        kernel32.CloseHandle(snapshot)
