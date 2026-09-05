"""Wrappers for user32 CCD (Display Configuration) APIs used to capture and apply monitor layout profiles."""

from ctypes import (
    POINTER,
    Structure,
    Union,
    c_long,
    c_uint16,
    c_uint32,
    c_uint64,
    windll,
)
from ctypes.wintypes import (
    BOOL,
    LONG,
    WCHAR,
)

# ---------------------------------------------------------------- Structures


class LUID(Structure):
    _fields_ = [
        ("LowPart", c_uint32),
        ("HighPart", c_uint32),
    ]


class POINTL(Structure):
    _fields_ = [
        ("x", c_long),
        ("y", c_long),
    ]


class DISPLAYCONFIG_RATIONAL(Structure):
    _fields_ = [
        ("Numerator", c_uint32),
        ("Denominator", c_uint32),
    ]


class DISPLAYCONFIG_2DREGION(Structure):
    _fields_ = [
        ("cx", c_uint32),
        ("cy", c_uint32),
    ]


class _DISPLAYCONFIG_ADDITIONAL_SIGNAL_INFO(Structure):
    _fields_ = [
        ("videoStandard", c_uint32, 16),
        ("vSyncFreqDivider", c_uint32, 6),
        ("reserved", c_uint32, 10),
    ]


class _DISPLAYCONFIG_VIDEO_SIGNAL_INFO_UNION(Union):
    _fields_ = [
        ("AdditionalSignalInfo", _DISPLAYCONFIG_ADDITIONAL_SIGNAL_INFO),
        ("videoStandard", c_uint32),
    ]


class DISPLAYCONFIG_VIDEO_SIGNAL_INFO(Structure):
    _anonymous_ = ("DUMMYUNIONNAME",)
    _fields_ = [
        ("pixelRate", c_uint64),
        ("hSyncFreq", DISPLAYCONFIG_RATIONAL),
        ("vSyncFreq", DISPLAYCONFIG_RATIONAL),
        ("activeSize", DISPLAYCONFIG_2DREGION),
        ("totalSize", DISPLAYCONFIG_2DREGION),
        ("DUMMYUNIONNAME", _DISPLAYCONFIG_VIDEO_SIGNAL_INFO_UNION),
        ("scanLineOrdering", c_uint32),
    ]


class DISPLAYCONFIG_TARGET_MODE(Structure):
    _fields_ = [
        ("targetVideoSignalInfo", DISPLAYCONFIG_VIDEO_SIGNAL_INFO),
    ]


class DISPLAYCONFIG_PIXELFORMAT:
    DISPLAYCONFIG_PIXELFORMAT_8BPP = 1
    DISPLAYCONFIG_PIXELFORMAT_16BPP = 2
    DISPLAYCONFIG_PIXELFORMAT_24BPP = 3
    DISPLAYCONFIG_PIXELFORMAT_32BPP = 4
    DISPLAYCONFIG_PIXELFORMAT_NONGDI = 5
    DISPLAYCONFIG_PIXELFORMAT_FORCE_UINT32 = 0xFFFFFFFF


class DISPLAYCONFIG_SOURCE_MODE(Structure):
    _fields_ = [
        ("width", c_uint32),
        ("height", c_uint32),
        ("pixelFormat", c_uint32),
        ("position", POINTL),
    ]


class _DISPLAYCONFIG_MODE_INFO_UNION(Union):
    _fields_ = [
        ("targetMode", DISPLAYCONFIG_TARGET_MODE),
        ("sourceMode", DISPLAYCONFIG_SOURCE_MODE),
    ]


class DISPLAYCONFIG_MODE_INFO(Structure):
    _anonymous_ = ("DUMMYUNIONNAME",)
    _fields_ = [
        ("infoType", c_uint32),
        ("id", c_uint32),
        ("adapterId", LUID),
        ("DUMMYUNIONNAME", _DISPLAYCONFIG_MODE_INFO_UNION),
    ]


class _DISPLAYCONFIG_PATH_SOURCE_INFO_UNION(Union):
    class _Bits(Structure):
        _fields_ = [
            ("cloneGroupId", c_uint32, 16),
            ("sourceModeInfoIdx", c_uint32, 16),
        ]

    _anonymous_ = ("DUMMYSTRUCTNAME",)
    _fields_ = [
        ("modeInfoIdx", c_uint32),
        ("DUMMYSTRUCTNAME", _Bits),
    ]


class DISPLAYCONFIG_PATH_SOURCE_INFO(Structure):
    _anonymous_ = ("DUMMYUNIONNAME",)
    _fields_ = [
        ("adapterId", LUID),
        ("id", c_uint32),
        ("DUMMYUNIONNAME", _DISPLAYCONFIG_PATH_SOURCE_INFO_UNION),
        ("statusFlags", c_uint32),
    ]


class _DISPLAYCONFIG_PATH_TARGET_INFO_UNION(Union):
    class _Bits(Structure):
        _fields_ = [
            ("desktopModeInfoIdx", c_uint32, 16),
            ("targetModeInfoIdx", c_uint32, 16),
        ]

    _anonymous_ = ("DUMMYSTRUCTNAME",)
    _fields_ = [
        ("modeInfoIdx", c_uint32),
        ("DUMMYSTRUCTNAME", _Bits),
    ]


class DISPLAYCONFIG_PATH_TARGET_INFO(Structure):
    _anonymous_ = ("DUMMYUNIONNAME",)
    _fields_ = [
        ("adapterId", LUID),
        ("id", c_uint32),
        ("DUMMYUNIONNAME", _DISPLAYCONFIG_PATH_TARGET_INFO_UNION),
        ("outputTechnology", c_uint32),
        ("rotation", c_uint32),
        ("scaling", c_uint32),
        ("refreshRate", DISPLAYCONFIG_RATIONAL),
        ("scanLineOrdering", c_uint32),
        ("targetAvailable", BOOL),
        ("statusFlags", c_uint32),
    ]


class DISPLAYCONFIG_PATH_INFO(Structure):
    _fields_ = [
        ("sourceInfo", DISPLAYCONFIG_PATH_SOURCE_INFO),
        ("targetInfo", DISPLAYCONFIG_PATH_TARGET_INFO),
        ("flags", c_uint32),
    ]


class DISPLAYCONFIG_DEVICE_INFO_HEADER(Structure):
    _fields_ = [
        ("type", c_uint32),
        ("size", c_uint32),
        ("adapterId", LUID),
        ("id", c_uint32),
    ]


class DISPLAYCONFIG_SOURCE_DEVICE_NAME(Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("viewGdiDeviceName", WCHAR * 32),  # CCHDEVICENAME
    ]


class DISPLAYCONFIG_TARGET_DEVICE_NAME(Structure):
    _fields_ = [
        ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
        ("flags", c_uint32),
        ("outputTechnology", c_uint32),
        ("edidManufactureId", c_uint16),
        ("edidProductCodeId", c_uint16),
        ("connectorInstance", c_uint32),
        ("monitorFriendlyDeviceName", WCHAR * 64),
        ("monitorDevicePath", WCHAR * 128),
    ]


# ---------------------------------------------------------------- Functions

user32 = windll.user32

# GetDisplayConfigBufferSizes
user32.GetDisplayConfigBufferSizes.argtypes = [c_uint32, POINTER(c_uint32), POINTER(c_uint32)]
user32.GetDisplayConfigBufferSizes.restype = LONG

# QueryDisplayConfig
user32.QueryDisplayConfig.argtypes = [
    c_uint32,  # flags
    POINTER(c_uint32),  # numPathArrayElements
    POINTER(DISPLAYCONFIG_PATH_INFO),  # pathArray
    POINTER(c_uint32),  # numModeInfoArrayElements
    POINTER(DISPLAYCONFIG_MODE_INFO),  # modeInfoArray
    POINTER(c_uint32),  # currentTopologyId (optional, pass None)
]
user32.QueryDisplayConfig.restype = LONG

# SetDisplayConfig
user32.SetDisplayConfig.argtypes = [
    c_uint32,  # numPathArrayElements
    POINTER(DISPLAYCONFIG_PATH_INFO),  # pathArray
    c_uint32,  # numModeInfoArrayElements
    POINTER(DISPLAYCONFIG_MODE_INFO),  # modeInfoArray
    c_uint32,  # flags
]
user32.SetDisplayConfig.restype = LONG

# DisplayConfigGetDeviceInfo
user32.DisplayConfigGetDeviceInfo.argtypes = [POINTER(DISPLAYCONFIG_DEVICE_INFO_HEADER)]
user32.DisplayConfigGetDeviceInfo.restype = LONG

# ---------------------------------------------------------------- Constants

# QueryDisplayConfig flags
QDC_ALL_PATHS = 0x00000001
QDC_ONLY_ACTIVE_PATHS = 0x00000002
QDC_DATABASE_CURRENT = 0x00000004
QDC_VIRTUAL_MODE_AWARE = 0x00000010
QDC_INCLUDE_HMD = 0x00000020
QDC_VIRTUAL_REFRESH_RATE_AWARE = 0x00000040

# SetDisplayConfig flags
SDC_TOPOLOGY_INTERNAL = 0x00000001
SDC_TOPOLOGY_CLONE = 0x00000002
SDC_TOPOLOGY_EXTEND = 0x00000004
SDC_TOPOLOGY_EXTERNAL = 0x00000008
SDC_TOPOLOGY_SUPPLIED = 0x00000010
SDC_USE_SUPPLIED_DISPLAY_CONFIG = 0x00000020
SDC_VALIDATE = 0x00000040
SDC_APPLY = 0x00000080
SDC_NO_OPTIMIZATION = 0x00000100
SDC_SAVE_TO_DATABASE = 0x00000200
SDC_ALLOW_CHANGES = 0x00000400
SDC_PATH_PERSIST_IF_REQUIRED = 0x00000800
SDC_FORCE_MODE_ENUMERATION = 0x00001000
SDC_ALLOW_PATH_ORDER_CHANGES = 0x00002000
SDC_VIRTUAL_MODE_AWARE = 0x00008000
SDC_VIRTUAL_REFRESH_RATE_AWARE = 0x00020000
SDC_USE_DATABASE_CURRENT = SDC_TOPOLOGY_INTERNAL | SDC_TOPOLOGY_CLONE | SDC_TOPOLOGY_EXTEND | SDC_TOPOLOGY_EXTERNAL

# DISPLAYCONFIG_MODE_INFO_TYPE
DISPLAYCONFIG_MODE_INFO_TYPE_SOURCE = 1
DISPLAYCONFIG_MODE_INFO_TYPE_TARGET = 2
DISPLAYCONFIG_MODE_INFO_TYPE_DESKTOP_IMAGE = 3

# DISPLAYCONFIG_DEVICE_INFO_TYPE
DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME = 1
DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME = 2

# DISPLAYCONFIG_PATH_INFO flags
DISPLAYCONFIG_PATH_ACTIVE = 0x00000001

# DISPLAYCONFIG_ROTATION
DISPLAYCONFIG_ROTATION_IDENTITY = 1
DISPLAYCONFIG_ROTATION_ROTATE90 = 2
DISPLAYCONFIG_ROTATION_ROTATE180 = 3
DISPLAYCONFIG_ROTATION_ROTATE270 = 4

# DISPLAYCONFIG_TARGET_DEVICE_NAME_FLAGS
DISPLAYCONFIG_TARGET_DEVICE_NAME_FLAG_FROM_EDID = 0x00000001

# MONITORINFOF_FROM_CCD shortcut for topology detection (from winuser.h)
MONITORINFOF_FROM_CCD = 0x00000001
