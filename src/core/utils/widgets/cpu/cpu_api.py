"""
Windows CPU API using PDH

Note: If PDH counters are broken/corrupted, this module will return
safe default values instead of crashing. Users can repair PDH counters
by running: lodctr /r (as Administrator) or rebuilding performance counters.
"""

import ctypes
import logging
from ctypes import POINTER, byref, wintypes
from typing import NamedTuple

from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.pdh import pdh
from core.utils.win32.constants import PDH_FMT_DOUBLE, PDH_FMT_LARGE
from core.utils.win32.structs import PDH_FMT_COUNTERVALUE_DOUBLE, PDH_FMT_COUNTERVALUE_LARGE, SYSTEM_INFO


class CpuFreq(NamedTuple):
    """CPU frequency data (MHz)."""

    current: float
    min: float
    max: float


class CpuData(NamedTuple):
    """Complete CPU data returned by get_cpu_data()."""

    freq: CpuFreq
    percent: float
    percent_per_core: list[float]
    cores_physical: int
    cores_logical: int


# Cached core counts
_cores_logical: int | None = None
_cores_physical: int | None = None

# Single unified PDH query
_query: wintypes.HANDLE | None = None
_counter_percent_total: wintypes.HANDLE | None = None
_counter_perf: wintypes.HANDLE | None = None
_counters_per_core: list[wintypes.HANDLE] = []
_base_freq: float = 0.0

# Track if PDH initialization failed
_pdh_init_failed: bool = False
_pdh_error_logged: bool = False


def _get_core_counts() -> tuple[int, int]:
    """Get and cache logical and physical core counts."""
    global _cores_logical, _cores_physical

    if _cores_logical is None:
        _cores_logical = _get_logical_cores()

    if _cores_physical is None:
        _cores_physical = _get_physical_cores()

    return _cores_logical, _cores_physical


def _get_logical_cores() -> int:
    """Get logical core count using GetSystemInfo."""
    try:
        sysinfo = SYSTEM_INFO()
        kernel32.GetSystemInfo(byref(sysinfo))
        return max(1, sysinfo.dwNumberOfProcessors)
    except Exception:
        return 1


def _get_physical_cores() -> int:
    """Calculate physical core count using GetLogicalProcessorInformationEx."""
    logical = _cores_logical or 1
    try:
        RelationProcessorCore = 0
        length = wintypes.DWORD(0)

        kernel32.GetLogicalProcessorInformationEx(RelationProcessorCore, None, byref(length))
        if length.value == 0:
            return max(1, logical // 2)

        buffer = (ctypes.c_byte * length.value)()
        if not kernel32.GetLogicalProcessorInformationEx(RelationProcessorCore, buffer, byref(length)):
            return max(1, logical // 2)

        physical = 0
        offset = 0
        while offset < length.value:
            relationship = ctypes.cast(ctypes.addressof(buffer) + offset, POINTER(wintypes.DWORD)).contents.value
            size = ctypes.cast(ctypes.addressof(buffer) + offset + 4, POINTER(wintypes.DWORD)).contents.value
            if relationship == RelationProcessorCore:
                physical += 1
            offset += size

        return physical if physical > 0 else max(1, logical // 2)
    except Exception:
        return max(1, logical // 2)


def _init_query() -> bool:
    """Initialize the unified PDH query with all counters."""
    global _query, _counter_percent_total, _counter_perf, _counters_per_core, _base_freq
    global _pdh_init_failed, _pdh_error_logged

    if _query is not None:
        return True

    if _pdh_init_failed:
        return False

    logical, _ = _get_core_counts()

    try:
        _query = wintypes.HANDLE()
        status = pdh.PdhOpenQueryW(None, None, byref(_query))
        if status != 0:
            _query = None
            _pdh_init_failed = True
            if not _pdh_error_logged:
                logging.warning(f"Failed to open PDH query (status={status}). CPU widget will show default values.")
                _pdh_error_logged = True
            return False

        # Total CPU percent
        _counter_percent_total = wintypes.HANDLE()
        status = pdh.PdhAddEnglishCounterW(
            _query, r"\Processor Information(_Total)\% Processor Utility", None, byref(_counter_percent_total)
        )
        if status != 0:
            # Fallback to % Processor Time
            status = pdh.PdhAddEnglishCounterW(
                _query, r"\Processor Information(_Total)\% Processor Time", None, byref(_counter_percent_total)
            )
            if status != 0:
                _cleanup_query()
                _pdh_init_failed = True
                if not _pdh_error_logged:
                    logging.warning(
                        f"Failed to add CPU percent counter (status={status}). "
                        "PDH counters may be corrupted. Try running 'lodctr /r' as Administrator to repair."
                    )
                    _pdh_error_logged = True
                return False

        # Processor Performance
        _counter_perf = wintypes.HANDLE()
        pdh.PdhAddEnglishCounterW(
            _query, r"\Processor Information(_Total)\% Processor Performance", None, byref(_counter_perf)
        )

        # Per-core CPU percent
        _counters_per_core = []
        for i in range(logical):
            counter = wintypes.HANDLE()
            status = pdh.PdhAddEnglishCounterW(
                _query, f"\\Processor Information(0,{i})\\% Processor Utility", None, byref(counter)
            )
            if status != 0:
                pdh.PdhAddEnglishCounterW(
                    _query, f"\\Processor Information(0,{i})\\% Processor Time", None, byref(counter)
                )
            _counters_per_core.append(counter)

        # Initial collection
        pdh.PdhCollectQueryData(_query)

        # Get and cache base frequency
        freq_counter = wintypes.HANDLE()
        if (
            pdh.PdhAddEnglishCounterW(
                _query, r"\Processor Information(_Total)\Processor Frequency", None, byref(freq_counter)
            )
            == 0
        ):
            pdh.PdhCollectQueryData(_query)
            val = PDH_FMT_COUNTERVALUE_LARGE()
            if pdh.PdhGetFormattedCounterValue(freq_counter, PDH_FMT_LARGE, None, byref(val)) == 0:
                _base_freq = float(val.largeValue)

        return True

    except Exception as e:
        _cleanup_query()
        _pdh_init_failed = True
        if not _pdh_error_logged:
            logging.error(f"Exception during PDH initialization: {e}")
            _pdh_error_logged = True
        return False


def _cleanup_query():
    """Clean up PDH query resources."""
    global _query, _counter_percent_total, _counter_perf, _counters_per_core
    if _query is not None:
        try:
            pdh.PdhCloseQuery(_query)
        except Exception:
            pass
    _query = None
    _counter_percent_total = None
    _counter_perf = None
    _counters_per_core = []


def _get_counter_double(counter: wintypes.HANDLE) -> float:
    """Get a double value from a PDH counter. Returns 0.0 on any error."""
    if counter is None:
        return 0.0
    try:
        val = PDH_FMT_COUNTERVALUE_DOUBLE()
        status = pdh.PdhGetFormattedCounterValue(counter, PDH_FMT_DOUBLE, None, byref(val))
        if status == 0 and val.CStatus == 0:
            return val.doubleValue
    except Exception:
        pass
    return 0.0


class CpuAPI:
    """Windows CPU API wrapper."""

    # Re-export types for convenience
    CpuData = CpuData
    CpuFreq = CpuFreq

    @classmethod
    def get_data(cls) -> CpuData:
        """
        Get all CPU data in a single optimized call.

        Returns:
            CpuData with freq, percent, percent_per_core, cores_physical, cores_logical
        """
        logical, physical = _get_core_counts()

        # Return defaults if PDH not available or broken
        if not _init_query():
            return CpuData(
                freq=CpuFreq(0.0, 0.0, _base_freq),
                percent=0.0,
                percent_per_core=[0.0] * logical,
                cores_physical=physical,
                cores_logical=logical,
            )

        try:
            # Single data collection for all counters
            status = pdh.PdhCollectQueryData(_query)
            if status != 0:
                # Collection failed - return safe defaults
                return CpuData(
                    freq=CpuFreq(_base_freq, 0.0, _base_freq),
                    percent=0.0,
                    percent_per_core=[0.0] * logical,
                    cores_physical=physical,
                    cores_logical=logical,
                )

            # Get total CPU percent
            percent = min(100.0, max(0.0, round(_get_counter_double(_counter_percent_total), 1)))

            # Get frequency (% Processor Performance can exceed 100% during turbo)
            perf_pct = _get_counter_double(_counter_perf)
            current_freq = round(_base_freq * perf_pct / 100.0, 1) if perf_pct > 0 else _base_freq
            freq = CpuFreq(current=current_freq, min=0.0, max=_base_freq)

            # Get per-core percentages
            per_core = [min(100.0, max(0.0, round(_get_counter_double(c), 1))) for c in _counters_per_core]

            return CpuData(
                freq=freq,
                percent=percent,
                percent_per_core=per_core,
                cores_physical=physical,
                cores_logical=logical,
            )

        except Exception as e:
            # Any exception - return safe defaults
            logging.debug(f"Error collecting CPU data: {e}")
            return CpuData(
                freq=CpuFreq(_base_freq, 0.0, _base_freq),
                percent=0.0,
                percent_per_core=[0.0] * logical,
                cores_physical=physical,
                cores_logical=logical,
            )
