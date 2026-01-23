"""Windows native API for memory statistics."""

import ctypes
from ctypes import wintypes
from typing import NamedTuple

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


class MemoryAPI:
    """Windows native memory API using GlobalMemoryStatusEx and GetPerformanceInfo."""

    @classmethod
    def _get_swap_percent(cls) -> float:
        """Get swap usage percentage using PDH performance counter."""
        try:
            counter_path = "\\Paging File(_Total)\\% Usage"
            h_query = wintypes.HANDLE()
            h_counter = wintypes.HANDLE()

            # Open PDH query
            if pdh.PdhOpenQueryW(None, 0, ctypes.byref(h_query)) != 0:
                return 0.0

            # Add counter
            status = pdh.PdhAddEnglishCounterW(h_query, counter_path, 0, ctypes.byref(h_counter))
            if status != 0:
                pdh.PdhCloseQuery(h_query)
                return 0.0

            # Collect data
            if pdh.PdhCollectQueryData(h_query) != 0:
                pdh.PdhCloseQuery(h_query)
                return 0.0

            # Get counter value
            counter_value = PDH_FMT_COUNTERVALUE_DOUBLE()
            status = pdh.PdhGetFormattedCounterValue(h_counter, PDH_FMT_DOUBLE, None, ctypes.byref(counter_value))

            pdh.PdhCloseQuery(h_query)

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
