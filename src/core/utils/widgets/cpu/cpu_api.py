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

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.pdh import pdh
from core.utils.win32.constants import PDH_FMT_DOUBLE, PDH_FMT_LARGE
from core.utils.win32.structs import PDH_FMT_COUNTERVALUE_DOUBLE, PDH_FMT_COUNTERVALUE_LARGE, SYSTEM_INFO


class CpuFreq(NamedTuple):
    """CPU frequency in MHz."""

    current: float
    min: float
    max: float


class CpuData(NamedTuple):
    """CPU data snapshot."""

    freq: CpuFreq
    percent: float
    percent_per_core: list[float]
    cores_physical: int
    cores_logical: int


class CpuAPI:
    """Windows CPU API using PDH performance counters.

    All PDH state is held as class attributes and accessed via classmethods.
    If PDH counters are corrupted, safe defaults are returned instead of
    crashing. Repair with: lodctr /r (as Administrator).
    """

    CpuData = CpuData
    CpuFreq = CpuFreq

    _cores_logical: int | None = None
    _cores_physical: int | None = None

    _query: wintypes.HANDLE | None = None
    _counter_total: wintypes.HANDLE | None = None
    _counter_perf: wintypes.HANDLE | None = None
    _counters_per_core: list[wintypes.HANDLE] = []
    _base_freq: float = 0.0

    _init_failed: bool = False
    _error_logged: bool = False

    @classmethod
    def _get_core_counts(cls) -> tuple[int, int]:
        """Get and cache logical and physical core counts."""
        if cls._cores_logical is None:
            cls._cores_logical = cls._get_logical_cores()
        if cls._cores_physical is None:
            cls._cores_physical = cls._get_physical_cores()
        return cls._cores_logical, cls._cores_physical

    @classmethod
    def _get_logical_cores(cls) -> int:
        """Get logical core count via GetSystemInfo."""
        try:
            sysinfo = SYSTEM_INFO()
            kernel32.GetSystemInfo(byref(sysinfo))
            return max(1, sysinfo.dwNumberOfProcessors)
        except Exception:
            return 1

    @classmethod
    def _get_physical_cores(cls) -> int:
        """Get physical core count via GetLogicalProcessorInformationEx."""
        logical = cls._cores_logical or 1
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

    @classmethod
    def _init_query(cls) -> bool:
        """Initialize the PDH query with all counters."""
        if cls._query is not None:
            return True
        if cls._init_failed:
            return False

        logical, _ = cls._get_core_counts()

        try:
            cls._query = wintypes.HANDLE()
            status = pdh.PdhOpenQueryW(None, None, byref(cls._query))
            if status != 0:
                cls._query = None
                cls._init_failed = True
                if not cls._error_logged:
                    logging.warning(f"Failed to open PDH query (status={status}). CPU widget will show default values.")
                    cls._error_logged = True
                return False

            # Total CPU percent
            cls._counter_total = wintypes.HANDLE()
            status = pdh.PdhAddEnglishCounterW(
                cls._query, r"\Processor Information(_Total)\% Processor Utility", None, byref(cls._counter_total)
            )
            if status != 0:
                # Fallback to % Processor Time
                status = pdh.PdhAddEnglishCounterW(
                    cls._query, r"\Processor Information(_Total)\% Processor Time", None, byref(cls._counter_total)
                )
                if status != 0:
                    cls._cleanup_query()
                    cls._init_failed = True
                    if not cls._error_logged:
                        logging.warning(
                            f"Failed to add CPU percent counter (status={status}). "
                            "PDH counters may be corrupted. Try running 'lodctr /r' as Administrator."
                        )
                        cls._error_logged = True
                    return False

            # Processor performance (for frequency calculation)
            cls._counter_perf = wintypes.HANDLE()
            pdh.PdhAddEnglishCounterW(
                cls._query, r"\Processor Information(_Total)\% Processor Performance", None, byref(cls._counter_perf)
            )

            # Per-core CPU percent
            cls._counters_per_core = []
            for i in range(logical):
                counter = wintypes.HANDLE()
                status = pdh.PdhAddEnglishCounterW(
                    cls._query, f"\\Processor Information(0,{i})\\% Processor Utility", None, byref(counter)
                )
                if status != 0:
                    pdh.PdhAddEnglishCounterW(
                        cls._query, f"\\Processor Information(0,{i})\\% Processor Time", None, byref(counter)
                    )
                cls._counters_per_core.append(counter)

            # Initial data collection
            pdh.PdhCollectQueryData(cls._query)

            # Cache base frequency
            freq_counter = wintypes.HANDLE()
            if (
                pdh.PdhAddEnglishCounterW(
                    cls._query, r"\Processor Information(_Total)\Processor Frequency", None, byref(freq_counter)
                )
                == 0
            ):
                pdh.PdhCollectQueryData(cls._query)
                val = PDH_FMT_COUNTERVALUE_LARGE()
                if pdh.PdhGetFormattedCounterValue(freq_counter, PDH_FMT_LARGE, None, byref(val)) == 0:
                    cls._base_freq = float(val.largeValue)

            return True

        except Exception as e:
            cls._cleanup_query()
            cls._init_failed = True
            if not cls._error_logged:
                logging.error(f"PDH initialization error: {e}")
                cls._error_logged = True
            return False

    @classmethod
    def _cleanup_query(cls):
        """Release PDH query resources."""
        if cls._query is not None:
            try:
                pdh.PdhCloseQuery(cls._query)
            except Exception:
                pass
        cls._query = None
        cls._counter_total = None
        cls._counter_perf = None
        cls._counters_per_core = []

    @classmethod
    def _get_counter_double(cls, counter: wintypes.HANDLE) -> float:
        """Read a double value from a PDH counter."""
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

    @classmethod
    def get_data(cls) -> CpuData:
        """Collect all CPU data in a single call.

        Returns safe defaults if PDH is unavailable or corrupted.
        """
        logical, physical = cls._get_core_counts()

        if not cls._init_query():
            return CpuData(
                freq=CpuFreq(0.0, 0.0, cls._base_freq),
                percent=0.0,
                percent_per_core=[0.0] * logical,
                cores_physical=physical,
                cores_logical=logical,
            )

        try:
            status = pdh.PdhCollectQueryData(cls._query)
            if status != 0:
                return CpuData(
                    freq=CpuFreq(cls._base_freq, 0.0, cls._base_freq),
                    percent=0.0,
                    percent_per_core=[0.0] * logical,
                    cores_physical=physical,
                    cores_logical=logical,
                )

            # Total CPU percent
            percent = min(100.0, max(0.0, round(cls._get_counter_double(cls._counter_total), 1)))

            # Current frequency from performance percentage
            perf_pct = cls._get_counter_double(cls._counter_perf)
            current_freq = round(cls._base_freq * perf_pct / 100.0, 1) if perf_pct > 0 else cls._base_freq
            freq = CpuFreq(current=current_freq, min=0.0, max=cls._base_freq)

            # Per-core percentages
            per_core = [min(100.0, max(0.0, round(cls._get_counter_double(c), 1))) for c in cls._counters_per_core]

            return CpuData(
                freq=freq,
                percent=percent,
                percent_per_core=per_core,
                cores_physical=physical,
                cores_logical=logical,
            )

        except Exception as e:
            logging.debug(f"CPU data collection error: {e}")
            return CpuData(
                freq=CpuFreq(cls._base_freq, 0.0, cls._base_freq),
                percent=0.0,
                percent_per_core=[0.0] * logical,
                cores_physical=physical,
                cores_logical=logical,
            )


class CpuWorker(QThread):
    """Background thread for non-blocking CPU data collection."""

    _instance: "CpuWorker | None" = None
    data_ready = pyqtSignal(object)

    @classmethod
    def get_instance(cls, update_interval: int) -> "CpuWorker":
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
        CpuWorker._instance = None

    def run(self):
        """Collect CPU data in a loop until stopped."""
        while self._running:
            try:
                data = CpuAPI.get_data()
                if self._running:
                    self.data_ready.emit(data)
            except Exception as e:
                logging.error(f"CPU worker error: {e}")
            self.msleep(self._update_interval)
