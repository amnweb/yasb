"""Windows native API for memory statistics."""

import ctypes
import logging
from ctypes import wintypes
from typing import NamedTuple

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.pdh import pdh
from core.utils.win32.bindings.psapi import psapi
from core.utils.win32.constants import PDH_FMT_DOUBLE
from core.utils.win32.structs import MEMORYSTATUSEX, PDH_FMT_COUNTERVALUE_DOUBLE, PERFORMANCE_INFORMATION


class VirtualMemory(NamedTuple):
    """Virtual memory statistics."""

    total: int
    available: int
    percent: float
    used: int
    free: int


class SwapMemory(NamedTuple):
    """Swap memory statistics."""

    total: int
    used: int
    free: int
    percent: float


class MemoryData(NamedTuple):
    """Combined memory data snapshot."""

    virtual: VirtualMemory
    swap: SwapMemory


class MemoryAPI:
    """Windows native memory API using GlobalMemoryStatusEx and GetPerformanceInfo."""

    # Cached PDH query for swap percent (avoids open/close every call)
    _swap_query: wintypes.HANDLE | None = None
    _swap_counter: wintypes.HANDLE | None = None
    _swap_init_failed: bool = False

    @classmethod
    def _init_swap_query(cls) -> bool:
        """Initialize and cache the PDH query for swap usage."""
        if cls._swap_query is not None:
            return True
        if cls._swap_init_failed:
            return False

        try:
            cls._swap_query = wintypes.HANDLE()
            if pdh.PdhOpenQueryW(None, 0, ctypes.byref(cls._swap_query)) != 0:
                cls._swap_query = None
                cls._swap_init_failed = True
                return False

            cls._swap_counter = wintypes.HANDLE()
            status = pdh.PdhAddEnglishCounterW(
                cls._swap_query, "\\Paging File(_Total)\\% Usage", 0, ctypes.byref(cls._swap_counter)
            )
            if status != 0:
                pdh.PdhCloseQuery(cls._swap_query)
                cls._swap_query = None
                cls._swap_counter = None
                cls._swap_init_failed = True
                return False

            return True
        except Exception:
            cls._swap_init_failed = True
            return False

    @classmethod
    def _get_swap_percent(cls) -> float:
        """Get swap usage percentage using cached PDH counter."""
        if not cls._init_swap_query():
            return 0.0
        try:
            if pdh.PdhCollectQueryData(cls._swap_query) != 0:
                return 0.0

            counter_value = PDH_FMT_COUNTERVALUE_DOUBLE()
            status = pdh.PdhGetFormattedCounterValue(
                cls._swap_counter, PDH_FMT_DOUBLE, None, ctypes.byref(counter_value)
            )
            if status == 0 and counter_value.CStatus == 0:
                return counter_value.doubleValue
            return 0.0
        except Exception:
            return 0.0

    @classmethod
    def virtual_memory(cls) -> VirtualMemory:
        """Get virtual (physical) memory statistics."""
        try:
            mem_status = MEMORYSTATUSEX()
            mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if not kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status)):
                return VirtualMemory(total=0, available=0, percent=0.0, used=0, free=0)

            total = mem_status.ullTotalPhys
            available = mem_status.ullAvailPhys
            used = total - available
            percent = round((used / total) * 100, 1) if total > 0 else 0.0

            return VirtualMemory(
                total=total,
                available=available,
                percent=percent,
                used=used,
                free=available,
            )
        except Exception:
            return VirtualMemory(total=0, available=0, percent=0.0, used=0, free=0)

    @classmethod
    def swap_memory(cls) -> SwapMemory:
        """Get swap (page file) memory statistics."""
        try:
            perf = PERFORMANCE_INFORMATION()
            perf.cb = ctypes.sizeof(PERFORMANCE_INFORMATION)
            if not psapi.GetPerformanceInfo(ctypes.byref(perf), perf.cb):
                return SwapMemory(total=0, used=0, free=0, percent=0.0)

            page_size = perf.PageSize
            if page_size == 0:
                return SwapMemory(total=0, used=0, free=0, percent=0.0)

            total = (perf.CommitLimit - perf.PhysicalTotal) * page_size

            if total > 0:
                percent_swap = cls._get_swap_percent()
                used = int(0.01 * percent_swap * total)
            else:
                percent_swap = 0.0
                used = 0

            free = max(0, total - used)
            percent = round(percent_swap, 1)

            return SwapMemory(
                total=total,
                used=used,
                free=free,
                percent=percent,
            )
        except Exception:
            return SwapMemory(total=0, used=0, free=0, percent=0.0)

    @classmethod
    def get_data(cls) -> MemoryData:
        """Collect all memory data in a single call."""
        return MemoryData(
            virtual=cls.virtual_memory(),
            swap=cls.swap_memory(),
        )


class MemoryWorker(QThread):
    """Background thread for non-blocking memory data collection."""

    _instance: "MemoryWorker | None" = None
    data_ready = pyqtSignal(object)

    @classmethod
    def get_instance(cls, update_interval: int) -> "MemoryWorker":
        """Get or create the singleton worker instance."""
        if cls._instance is None:
            cls._instance = cls(update_interval)
        return cls._instance

    def __init__(self, update_interval: int, parent=None):
        super().__init__(parent)
        self._running = True
        self._update_interval = update_interval
        app_inst = QApplication.instance()
        if app_inst is not None:
            app_inst.aboutToQuit.connect(self.stop)

    def stop(self):
        """Signal the worker to stop."""
        self._running = False
        MemoryWorker._instance = None

    def run(self):
        """Collect memory data in a loop until stopped."""
        while self._running:
            try:
                data = MemoryAPI.get_data()
                if self._running:
                    self.data_ready.emit(data)
            except Exception as e:
                logging.error(f"Memory worker error: {e}")
            self.msleep(self._update_interval)
