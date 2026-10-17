"""AMD Display Library (atiadlxx.dll), installed with the AMD driver"""

from ctypes import POINTER, WINFUNCTYPE, Structure, WinDLL, c_int, c_void_p

from core.utils.win32.typecheck import CArgObject, CFunctionType


# adl_structures.h. ADLTemperature has exactly two members: the driver may reject a call whose iSize
# is larger than sizeof(ADLTemperature).
class ADLTemperature(Structure):
    _fields_ = [("iSize", c_int), ("iTemperature", c_int)]


class ADLFanSpeedValue(Structure):
    _fields_ = [
        ("iSize", c_int),
        ("iSpeedType", c_int),
        ("iFanSpeed", c_int),
        ("iFlags", c_int),
    ]


class ADLODNFanControl(Structure):
    _fields_ = [
        ("iMode", c_int),
        ("iFanControlMode", c_int),
        ("iCurrentFanSpeedMode", c_int),
        ("iCurrentFanSpeed", c_int),
        ("iTargetFanSpeed", c_int),
        ("iTargetTemperature", c_int),
        ("iMinPerformanceClock", c_int),
        ("iMinFanLimit", c_int),
    ]


# adl_sdk.h: typedef void* (__stdcall *ADL_MAIN_MALLOC_CALLBACK)(int)
ADL_MAIN_MALLOC_CALLBACK = WINFUNCTYPE(c_void_p, c_int)


class AdlLibrary:
    """Raises OSError when atiadlxx.dll is not installed. The Overdrive exports vary by driver."""

    def __init__(self) -> None:
        self._dll = WinDLL("atiadlxx.dll", use_last_error=True)
        self._dll.ADL2_Main_Control_Create.argtypes = [ADL_MAIN_MALLOC_CALLBACK, c_int, POINTER(c_void_p)]
        self._dll.ADL2_Main_Control_Create.restype = c_int
        self._dll.ADL2_Main_Control_Destroy.argtypes = [c_void_p]
        self._dll.ADL2_Main_Control_Destroy.restype = c_int
        self._dll.ADL2_Adapter_NumberOfAdapters_Get.argtypes = [c_void_p, POINTER(c_int)]
        self._dll.ADL2_Adapter_NumberOfAdapters_Get.restype = c_int
        self._dll.ADL2_Adapter_Active_Get.argtypes = [c_void_p, c_int, POINTER(c_int)]
        self._dll.ADL2_Adapter_Active_Get.restype = c_int

        try:
            self._dll.ADL2_OverdriveN_Temperature_Get.argtypes = [c_void_p, c_int, c_int, POINTER(c_int)]
            self._dll.ADL2_OverdriveN_Temperature_Get.restype = c_int
            self.has_overdrive_n_temperature = True
        except AttributeError:
            self.has_overdrive_n_temperature = False

        try:
            self._dll.ADL2_OverdriveN_FanControl_Get.argtypes = [c_void_p, c_int, POINTER(ADLODNFanControl)]
            self._dll.ADL2_OverdriveN_FanControl_Get.restype = c_int
            self.has_overdrive_n_fan_control = True
        except AttributeError:
            self.has_overdrive_n_fan_control = False

        try:
            self._dll.ADL2_Overdrive5_Temperature_Get.argtypes = [c_void_p, c_int, c_int, POINTER(ADLTemperature)]
            self._dll.ADL2_Overdrive5_Temperature_Get.restype = c_int
            self.has_overdrive5_temperature = True
        except AttributeError:
            self.has_overdrive5_temperature = False

        try:
            self._dll.ADL2_Overdrive5_FanSpeed_Get.argtypes = [c_void_p, c_int, c_int, POINTER(ADLFanSpeedValue)]
            self._dll.ADL2_Overdrive5_FanSpeed_Get.restype = c_int
            self.has_overdrive5_fan_speed = True
        except AttributeError:
            self.has_overdrive5_fan_speed = False

    def ADL2_Main_Control_Create(
        self, callback: CFunctionType, iEnumConnectedAdapters: int, context: CArgObject
    ) -> int:
        return self._dll.ADL2_Main_Control_Create(callback, iEnumConnectedAdapters, context)

    def ADL2_Main_Control_Destroy(self, context: c_void_p) -> int:
        return self._dll.ADL2_Main_Control_Destroy(context)

    def ADL2_Adapter_NumberOfAdapters_Get(self, context: c_void_p, lpNumAdapters: CArgObject) -> int:
        return self._dll.ADL2_Adapter_NumberOfAdapters_Get(context, lpNumAdapters)

    def ADL2_Adapter_Active_Get(self, context: c_void_p, iAdapterIndex: int, lpStatus: CArgObject) -> int:
        return self._dll.ADL2_Adapter_Active_Get(context, iAdapterIndex, lpStatus)

    def ADL2_OverdriveN_Temperature_Get(
        self, context: c_void_p, iAdapterIndex: int, iTemperatureType: int, iTemperature: CArgObject
    ) -> int:
        return self._dll.ADL2_OverdriveN_Temperature_Get(context, iAdapterIndex, iTemperatureType, iTemperature)

    def ADL2_OverdriveN_FanControl_Get(self, context: c_void_p, iAdapterIndex: int, lpOdFanSpeed: CArgObject) -> int:
        return self._dll.ADL2_OverdriveN_FanControl_Get(context, iAdapterIndex, lpOdFanSpeed)

    def ADL2_Overdrive5_Temperature_Get(
        self, context: c_void_p, iAdapterIndex: int, iThermalControllerIndex: int, lpTemperature: CArgObject
    ) -> int:
        return self._dll.ADL2_Overdrive5_Temperature_Get(context, iAdapterIndex, iThermalControllerIndex, lpTemperature)

    def ADL2_Overdrive5_FanSpeed_Get(
        self, context: c_void_p, iAdapterIndex: int, iThermalControllerIndex: int, lpFanSpeedValue: CArgObject
    ) -> int:
        return self._dll.ADL2_Overdrive5_FanSpeed_Get(context, iAdapterIndex, iThermalControllerIndex, lpFanSpeedValue)
