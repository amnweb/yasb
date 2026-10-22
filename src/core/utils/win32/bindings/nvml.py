"""NVIDIA Management Library (nvml.dll), installed with the NVIDIA driver"""

from ctypes import POINTER, Array, Structure, WinDLL, c_char, c_int, c_uint, c_ulonglong, c_void_p

from core.utils.win32.typecheck import CArgObject

NVML_TEMPERATURE_GPU = 0


# nvml.h
class nvmlMemory_t(Structure):
    _fields_ = [("total", c_ulonglong), ("free", c_ulonglong), ("used", c_ulonglong)]


class NvmlLibrary:
    """Raises OSError when nvml.dll is not installed."""

    def __init__(self) -> None:
        self._dll = WinDLL("nvml.dll", use_last_error=True)
        self._dll.nvmlInit_v2.argtypes = []
        self._dll.nvmlInit_v2.restype = c_int
        self._dll.nvmlShutdown.argtypes = []
        self._dll.nvmlShutdown.restype = c_int
        self._dll.nvmlDeviceGetCount_v2.argtypes = [POINTER(c_uint)]
        self._dll.nvmlDeviceGetCount_v2.restype = c_int
        self._dll.nvmlDeviceGetHandleByIndex_v2.argtypes = [c_uint, POINTER(c_void_p)]
        self._dll.nvmlDeviceGetHandleByIndex_v2.restype = c_int
        self._dll.nvmlDeviceGetName.argtypes = [c_void_p, POINTER(c_char), c_uint]
        self._dll.nvmlDeviceGetName.restype = c_int
        self._dll.nvmlDeviceGetTemperature.argtypes = [c_void_p, c_int, POINTER(c_uint)]
        self._dll.nvmlDeviceGetTemperature.restype = c_int
        self._dll.nvmlDeviceGetFanSpeed.argtypes = [c_void_p, POINTER(c_uint)]
        self._dll.nvmlDeviceGetFanSpeed.restype = c_int
        self._dll.nvmlDeviceGetMemoryInfo.argtypes = [c_void_p, POINTER(nvmlMemory_t)]
        self._dll.nvmlDeviceGetMemoryInfo.restype = c_int
        self._dll.nvmlDeviceGetPowerUsage.argtypes = [c_void_p, POINTER(c_uint)]
        self._dll.nvmlDeviceGetPowerUsage.restype = c_int

    def nvmlInit_v2(self) -> int:
        return self._dll.nvmlInit_v2()

    def nvmlShutdown(self) -> int:
        return self._dll.nvmlShutdown()

    def nvmlDeviceGetCount_v2(self, deviceCount: CArgObject) -> int:
        return self._dll.nvmlDeviceGetCount_v2(deviceCount)

    def nvmlDeviceGetHandleByIndex_v2(self, index: int, device: CArgObject) -> int:
        return self._dll.nvmlDeviceGetHandleByIndex_v2(index, device)

    def nvmlDeviceGetName(self, device: c_void_p, name: Array[c_char], length: int) -> int:
        return self._dll.nvmlDeviceGetName(device, name, length)

    def nvmlDeviceGetTemperature(self, device: c_void_p, sensorType: int, temp: CArgObject) -> int:
        return self._dll.nvmlDeviceGetTemperature(device, sensorType, temp)

    def nvmlDeviceGetFanSpeed(self, device: c_void_p, speed: CArgObject) -> int:
        return self._dll.nvmlDeviceGetFanSpeed(device, speed)

    def nvmlDeviceGetMemoryInfo(self, device: c_void_p, memory: CArgObject) -> int:
        return self._dll.nvmlDeviceGetMemoryInfo(device, memory)

    def nvmlDeviceGetPowerUsage(self, device: c_void_p, power: CArgObject) -> int:
        return self._dll.nvmlDeviceGetPowerUsage(device, power)
