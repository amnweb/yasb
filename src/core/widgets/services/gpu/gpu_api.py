import ctypes
import logging
from ctypes import byref, wintypes
from typing import NamedTuple

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.utils.win32.bindings.pdh import pdh
from core.utils.win32.constants import PDH_FMT_DOUBLE

logger = logging.getLogger("gpu_widget")

_VENDOR_NVIDIA = 0x10DE
_VENDOR_AMD = 0x1002
_VENDOR_WARP = 0x1414


class GpuData(NamedTuple):
    index: int
    name: str
    utilization: float
    mem_total: int
    mem_used: int
    mem_free: int
    mem_shared_total: int
    mem_shared_used: int
    temp: int
    fan_speed: int
    power_draw: float


class _PdhItemW(ctypes.Structure):
    _fields_ = [
        ("szName", ctypes.c_wchar_p),
        ("CStatus", wintypes.DWORD),
        ("_pad", wintypes.DWORD),
        ("doubleValue", ctypes.c_double),
    ]


class _DxgiLuid(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", ctypes.c_long)]


class _DxgiAdapterDesc(ctypes.Structure):
    _fields_ = [
        ("Description", ctypes.c_wchar * 128),
        ("VendorId", ctypes.c_uint),
        ("DeviceId", ctypes.c_uint),
        ("SubSysId", ctypes.c_uint),
        ("Revision", ctypes.c_uint),
        ("DedicatedVideoMemory", ctypes.c_size_t),
        ("DedicatedSystemMemory", ctypes.c_size_t),
        ("SharedSystemMemory", ctypes.c_size_t),
        ("AdapterLuid", _DxgiLuid),
    ]


class _NvmlMemory(ctypes.Structure):
    _fields_ = [
        ("total", ctypes.c_ulonglong),
        ("free", ctypes.c_ulonglong),
        ("used", ctypes.c_ulonglong),
    ]


class _AdlTemperature(ctypes.Structure):
    _fields_ = [("iSize", ctypes.c_int), ("iTemperature", ctypes.c_int), ("iType", ctypes.c_int)]


class _AdlFanSpeedValue(ctypes.Structure):
    _fields_ = [
        ("iSize", ctypes.c_int),
        ("iSpeedType", ctypes.c_int),
        ("iFanSpeed", ctypes.c_int),
        ("iFlags", ctypes.c_int),
    ]


class _AdlODNFanControl(ctypes.Structure):
    _fields_ = [
        ("iMode", ctypes.c_int),
        ("iFanControlMode", ctypes.c_int),
        ("iCurrentFanSpeedMode", ctypes.c_int),
        ("iCurrentFanSpeed", ctypes.c_int),
        ("iTargetFanSpeed", ctypes.c_int),
        ("iTargetTemperature", ctypes.c_int),
        ("iMinPerformanceClock", ctypes.c_int),
        ("iMinFanLimit", ctypes.c_int),
    ]


_ADL_MALLOC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_int)


def _pdh_read_array(counter: wintypes.HANDLE) -> list[tuple[str, float]]:
    buf_size = wintypes.DWORD(0)
    count = wintypes.DWORD(0)
    pdh.PdhGetFormattedCounterArrayW(counter, PDH_FMT_DOUBLE, byref(buf_size), byref(count), None)
    if not count.value:
        return []
    raw = (ctypes.c_byte * buf_size.value)()
    if pdh.PdhGetFormattedCounterArrayW(counter, PDH_FMT_DOUBLE, byref(buf_size), byref(count), raw) != 0:
        return []
    items = ctypes.cast(raw, ctypes.POINTER(_PdhItemW))
    return [(items[i].szName or "", items[i].doubleValue) for i in range(count.value)]


def _luid_str(name: str) -> str:
    idx = name.lower().find("luid_0x")
    if idx == -1:
        return name
    parts = name[idx:].split("_")
    return ("_".join(parts[:3]) if len(parts) >= 3 else name).lower()


def _read_dxgi_gpus() -> list[dict]:
    """Enumerate physical GPU adapters via DXGI COM vtable dispatch.

    Skips Microsoft WARP software adapter.
    """
    result = []
    try:
        dxgi = ctypes.WinDLL("dxgi.dll")
        dxgi.CreateDXGIFactory1.restype = ctypes.c_long
        # IDXGIFactory1 IID {770AAE78-F26F-4DBA-A829-253C83D1B387}
        iid = (ctypes.c_byte * 16)(
            0x78,
            0xAE,
            0x0A,
            0x77,
            0x6F,
            0xF2,
            0xBA,
            0x4D,
            0xA8,
            0x29,
            0x25,
            0x3C,
            0x83,
            0xD1,
            0xB3,
            0x87,
        )
        factory = ctypes.c_void_p()
        if dxgi.CreateDXGIFactory1(byref(iid), byref(factory)) != 0 or not factory.value:
            return result
        fvt = ctypes.cast(ctypes.cast(factory, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        EnumAdapters = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)
        )(fvt[7])
        FactoryRelease = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(fvt[2])

        i = 0
        while True:
            adapter = ctypes.c_void_p()
            if EnumAdapters(factory, i, byref(adapter)) != 0 or not adapter.value:
                break
            i += 1
            avt = ctypes.cast(ctypes.cast(adapter, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
            GetDesc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_DxgiAdapterDesc))(avt[8])
            AdapterRelease = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(avt[2])
            desc = _DxgiAdapterDesc()
            if GetDesc(adapter, byref(desc)) == 0 and desc.VendorId != _VENDOR_WARP:
                high = desc.AdapterLuid.HighPart & 0xFFFFFFFF
                result.append(
                    {
                        "name": desc.Description.strip(),
                        "vram_total": desc.DedicatedVideoMemory,
                        "shared_total": desc.SharedSystemMemory,
                        "luid_str": f"luid_0x{high:08x}_0x{desc.AdapterLuid.LowPart:08x}",
                        "vendor_id": desc.VendorId,
                    }
                )
            AdapterRelease(adapter)
        FactoryRelease(factory)
    except OSError as e:
        logger.debug("DXGI enumeration failed %s", e)
    return result


class _NvmlState:
    def __init__(self) -> None:
        self.dll = None
        self.name_map: dict[str, ctypes.c_void_p] = {}

    def load(self) -> None:
        try:
            dll = ctypes.WinDLL("nvml.dll")
            for fn in (
                "nvmlInit_v2",
                "nvmlDeviceGetCount_v2",
                "nvmlDeviceGetHandleByIndex_v2",
                "nvmlDeviceGetName",
                "nvmlDeviceGetTemperature",
                "nvmlDeviceGetFanSpeed",
                "nvmlDeviceGetMemoryInfo",
                "nvmlDeviceGetPowerUsage",
                "nvmlShutdown",
            ):
                getattr(dll, fn).restype = ctypes.c_int

            if dll.nvmlInit_v2() != 0:
                return

            count = ctypes.c_uint()
            dll.nvmlDeviceGetCount_v2(byref(count))
            for i in range(count.value):
                handle = ctypes.c_void_p()
                if dll.nvmlDeviceGetHandleByIndex_v2(i, byref(handle)) != 0:
                    continue
                buf = ctypes.create_string_buffer(96)
                if dll.nvmlDeviceGetName(handle, buf, 96) == 0:
                    self.name_map[buf.value.decode("utf-8", "replace")] = handle

            self.dll = dll
        except OSError:
            pass

    def get_mem_total(self, handle: ctypes.c_void_p) -> int:
        if self.dll is None:
            return 0
        mem = _NvmlMemory()
        return mem.total if self.dll.nvmlDeviceGetMemoryInfo(handle, byref(mem)) == 0 else 0

    def query(self, handle: ctypes.c_void_p) -> tuple[int, int, float]:
        """Returns (temp_c, fan_pct, power_w)."""
        if self.dll is None:
            return 0, 0, 0.0
        temp, fan, power = ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint()
        t = self.dll.nvmlDeviceGetTemperature(handle, 0, byref(temp))
        f = self.dll.nvmlDeviceGetFanSpeed(handle, byref(fan))
        p = self.dll.nvmlDeviceGetPowerUsage(handle, byref(power))
        return (
            temp.value if t == 0 else 0,
            fan.value if f == 0 else 0,
            power.value / 1000.0 if p == 0 else 0.0,
        )

    def shutdown(self) -> None:
        if self.dll is not None:
            try:
                self.dll.nvmlShutdown()
            except Exception:
                pass
            self.dll = None


class _AdlState:
    """OverdriveN first (modern GPUs), Overdrive5 fallback (older GPUs)."""

    def __init__(self) -> None:
        self.dll = None
        self.ctx = ctypes.c_void_p()
        self.active_indices: list[int] = []
        self._odn_temp = False
        self._odn_fan = False
        self._od5_temp = False
        self._od5_fan = False
        self._malloc_cb = _ADL_MALLOC(lambda s: ctypes.cast(ctypes.create_string_buffer(s), ctypes.c_void_p).value)

    def load(self) -> None:
        try:
            dll = ctypes.WinDLL("atiadlxx.dll")
            for fn in (
                "ADL2_Main_Control_Create",
                "ADL2_Main_Control_Destroy",
                "ADL2_Adapter_NumberOfAdapters_Get",
                "ADL2_Adapter_Active_Get",
            ):
                getattr(dll, fn).restype = ctypes.c_int

            for attr, flag in (
                ("ADL2_OverdriveN_Temperature_Get", "_odn_temp"),
                ("ADL2_OverdriveN_FanControl_Get", "_odn_fan"),
                ("ADL2_Overdrive5_Temperature_Get", "_od5_temp"),
                ("ADL2_Overdrive5_FanSpeed_Get", "_od5_fan"),
            ):
                try:
                    getattr(dll, attr).restype = ctypes.c_int
                    setattr(self, flag, True)
                except AttributeError:
                    pass

            ctx = ctypes.c_void_p()
            if dll.ADL2_Main_Control_Create(self._malloc_cb, 1, byref(ctx)) != 0:
                return

            count = ctypes.c_int()
            dll.ADL2_Adapter_NumberOfAdapters_Get(ctx, byref(count))
            for i in range(count.value):
                active = ctypes.c_int()
                if dll.ADL2_Adapter_Active_Get(ctx, i, byref(active)) == 0 and active.value:
                    self.active_indices.append(i)

            self.dll = dll
            self.ctx = ctx
        except OSError:
            pass

    def query(self, adapter_index: int) -> tuple[int, int]:
        """Returns (temp_c, fan_pct)."""
        if self.dll is None:
            return 0, 0

        temp = 0
        if self._odn_temp:
            t_val = ctypes.c_int()
            if self.dll.ADL2_OverdriveN_Temperature_Get(self.ctx, adapter_index, 1, byref(t_val)) == 0 and t_val.value:
                temp = t_val.value // 1000
        if not temp and self._od5_temp:
            temp_s = _AdlTemperature(iSize=ctypes.sizeof(_AdlTemperature))
            if self.dll.ADL2_Overdrive5_Temperature_Get(self.ctx, adapter_index, 0, byref(temp_s)) == 0:
                temp = temp_s.iTemperature // 1000

        fan = 0
        if self._odn_fan:
            fan_ctl = _AdlODNFanControl()
            if self.dll.ADL2_OverdriveN_FanControl_Get(self.ctx, adapter_index, byref(fan_ctl)) == 0:
                fan = fan_ctl.iCurrentFanSpeed
        if not fan and self._od5_fan:
            fan_s = _AdlFanSpeedValue(iSize=ctypes.sizeof(_AdlFanSpeedValue), iSpeedType=1)
            if self.dll.ADL2_Overdrive5_FanSpeed_Get(self.ctx, adapter_index, 0, byref(fan_s)) == 0:
                fan = fan_s.iFanSpeed

        return temp, fan

    def shutdown(self) -> None:
        if self.dll is not None and self.ctx:
            try:
                self.dll.ADL2_Main_Control_Destroy(self.ctx)
            except Exception:
                pass
            self.dll = None


class GpuApi:
    def __init__(self, gpu_indices: set[int]) -> None:
        self._gpu_indices = gpu_indices
        self._luid_info: dict[str, dict] = {}
        self._dxgi_gpus: list[dict] = []
        self._ready = False

        self._nvml = _NvmlState()
        self._adl = _AdlState()

        self._query = wintypes.HANDLE()
        self._h_util = wintypes.HANDLE()
        self._h_mem_ded = wintypes.HANDLE()
        self._h_mem_shr = wintypes.HANDLE()
        if pdh.PdhOpenQueryW(None, None, byref(self._query)) != 0:
            logger.error("GpuApi: PdhOpenQueryW failed")
            return
        pdh.PdhAddEnglishCounterW(self._query, r"\GPU Engine(*)\Utilization Percentage", None, byref(self._h_util))
        pdh.PdhAddEnglishCounterW(self._query, r"\GPU Adapter Memory(*)\Dedicated Usage", None, byref(self._h_mem_ded))
        pdh.PdhAddEnglishCounterW(self._query, r"\GPU Adapter Memory(*)\Shared Usage", None, byref(self._h_mem_shr))

    def prime(self) -> None:
        """Seed PDH baseline, enumerate DXGI adapters, load vendor sensor libs."""
        pdh.PdhCollectQueryData(self._query)
        util_rows = _pdh_read_array(self._h_util)
        mem_rows = _pdh_read_array(self._h_mem_ded)
        all_luids = sorted({_luid_str(n) for n, _ in util_rows + mem_rows})

        self._dxgi_gpus = _read_dxgi_gpus()
        self._luid_info = self._build_luid_info(all_luids)

        needed_vendors: set[int] = set()
        for g in self._dxgi_gpus:
            info = self._luid_info.get(g["luid_str"])
            if info and info["index"] in self._gpu_indices:
                needed_vendors.add(g["vendor_id"])

        if _VENDOR_NVIDIA in needed_vendors:
            self._nvml.load()
            self._bind_nvml()
        if _VENDOR_AMD in needed_vendors:
            self._adl.load()
            self._bind_adl()

        self._ready = True

    def collect(self) -> list[GpuData]:
        """Collect current GPU data."""
        if not self._ready:
            return []

        pdh.PdhCollectQueryData(self._query)

        eng_max: dict[tuple[str, str], float] = {}
        for name, val in _pdh_read_array(self._h_util):
            luid = _luid_str(name)
            etype = name.split("engtype_")[-1] if "engtype_" in name else "other"
            key = (luid, etype)
            eng_max[key] = max(eng_max.get(key, 0.0), val)

        util: dict[str, float] = {}
        for (luid, _), val in eng_max.items():
            util[luid] = min(100.0, util.get(luid, 0.0) + val)

        mem_ded: dict[str, int] = {_luid_str(n): int(v) for n, v in _pdh_read_array(self._h_mem_ded)}
        mem_shr: dict[str, int] = {_luid_str(n): int(v) for n, v in _pdh_read_array(self._h_mem_shr)}

        result: list[GpuData] = []
        for luid, info in sorted(self._luid_info.items(), key=lambda x: x[1]["index"]):
            if info["index"] not in self._gpu_indices:
                continue

            total = info["vram_total"]
            used = mem_ded.get(luid, 0)
            temp, fan_speed, power_draw = 0, 0, 0.0

            nvml_handle = info.get("nvml_handle")
            adl_index = info.get("adl_index", -1)
            if nvml_handle is not None:
                temp, fan_speed, power_draw = self._nvml.query(nvml_handle)
            elif adl_index >= 0:
                temp, fan_speed = self._adl.query(adl_index)

            result.append(
                GpuData(
                    index=info["index"],
                    name=info["name"],
                    utilization=round(util.get(luid, 0.0), 1),
                    mem_total=total,
                    mem_used=used,
                    mem_free=max(0, total - used),
                    mem_shared_total=info["shared_total"],
                    mem_shared_used=mem_shr.get(luid, 0),
                    temp=temp,
                    fan_speed=fan_speed,
                    power_draw=power_draw,
                )
            )
        return result

    def close(self) -> None:
        pdh.PdhCloseQuery(self._query)
        self._nvml.shutdown()
        self._adl.shutdown()
        self._ready = False

    def _build_luid_info(self, all_luids: list[str]) -> dict[str, dict]:
        """Map PDH LUIDs to DXGI adapter info. Index follows DXGI order.
        Only includes LUIDs that have a matching DXGI adapter."""
        luid_to_dxgi = {g["luid_str"]: g for g in self._dxgi_gpus}
        all_luid_set = set(all_luids)
        dxgi_ordered = [g["luid_str"] for g in self._dxgi_gpus if g["luid_str"] in all_luid_set]

        result: dict[str, dict] = {}
        for i, luid in enumerate(dxgi_ordered):
            dg = luid_to_dxgi[luid]
            result[luid] = {
                "index": i,
                "name": dg["name"],
                "vram_total": dg["vram_total"],
                "shared_total": dg["shared_total"],
            }
        return result

    def _bind_nvml(self) -> None:
        """Bind NVML handles to luid_info entries for NVIDIA GPUs."""
        for luid, info in self._luid_info.items():
            dg = next((g for g in self._dxgi_gpus if g["luid_str"] == luid), None)
            if dg and dg["vendor_id"] == _VENDOR_NVIDIA:
                handle = self._nvml.name_map.get(dg["name"])
                if handle:
                    info["nvml_handle"] = handle
                    vram = self._nvml.get_mem_total(handle)
                    if vram:
                        info["vram_total"] = vram

    def _bind_adl(self) -> None:
        """Bind ADL adapter indices to luid_info entries for AMD GPUs."""
        amd_luids = [
            luid
            for luid in self._luid_info
            if any(g["luid_str"] == luid and g["vendor_id"] == _VENDOR_AMD for g in self._dxgi_gpus)
        ]
        for luid, adl_idx in zip(amd_luids, self._adl.active_indices):
            self._luid_info[luid]["adl_index"] = adl_idx


class GpuWorker(QThread):
    _instance: GpuWorker | None = None
    data_ready = pyqtSignal(list)

    @classmethod
    def get_instance(cls, update_interval: int) -> GpuWorker:
        if cls._instance is None:
            cls._instance = cls(update_interval)
        return cls._instance

    def add_index(self, index: int) -> None:
        self._gpu_indices.add(index)

    def __init__(self, update_interval: int, parent=None):
        super().__init__(parent)
        self._running = True
        self._update_interval = update_interval
        self._gpu_indices: set[int] = set()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop)

    def stop(self) -> None:
        self._running = False
        GpuWorker._instance = None

    def run(self) -> None:
        api = GpuApi(self._gpu_indices)
        try:
            api.prime()
            available = {info["index"] for info in api._luid_info.values()}
            missing = self._gpu_indices - available
            if missing:
                logger.warning("GpuWorker gpu_index %s not found. Available indices: %s", missing, sorted(available))
            if not (self._gpu_indices & available):
                return
            while self._running:
                try:
                    data = api.collect()
                    if self._running:
                        self.data_ready.emit(data)
                except Exception as e:
                    logger.error("GpuWorker %s", e)
                    if self._running:
                        self.data_ready.emit([])
                self.msleep(self._update_interval)
        finally:
            api.close()
