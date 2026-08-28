"""One-off restore: set LG TV (DISPLAY2) back to native 1920x1200@60."""
import ctypes
import time
from ctypes import wintypes

user32 = ctypes.windll.user32


class POINTL(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class DEVMODE_UNION(ctypes.Union):
    _fields_ = [
        ("dmPosition", POINTL),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmNup", wintypes.DWORD),
    ]


class DEVMODEW(ctypes.Structure):
    _anonymous_ = ("u1",)
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("u1", DEVMODE_UNION),
        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


DM_PELSHEIGHT = 0x100000
DM_PELSWIDTH = 0x80000
DM_POSITION = 0x20
DM_DISPLAYFREQUENCY = 0x400000

ENUM_CURRENT_SETTINGS = -1

dev = "\\\\.\\DISPLAY2"
dm = DEVMODEW()
dm.dmSize = ctypes.sizeof(DEVMODEW)
ok = user32.EnumDisplaySettingsExW(dev, ENUM_CURRENT_SETTINGS, ctypes.byref(dm), 0)
print("enum ok:", ok, "cur:", dm.dmPelsWidth, "x", dm.dmPelsHeight, "@", dm.dmDisplayFrequency)

dm.dmPelsWidth = 1920
dm.dmPelsHeight = 1200
dm.dmDisplayFrequency = 60
dm.dmPosition.x = 1608
dm.dmPosition.y = 1440
dm.dmFields = DM_PELSHEIGHT | DM_PELSWIDTH | DM_POSITION | DM_DISPLAYFREQUENCY

r = user32.ChangeDisplaySettingsExW(dev, ctypes.byref(dm), None, 0, None)
print("ChangeDisplaySettingsExW ret:", r)
time.sleep(1)

dm2 = DEVMODEW()
dm2.dmSize = ctypes.sizeof(DEVMODEW)
user32.EnumDisplaySettingsExW(dev, ENUM_CURRENT_SETTINGS, ctypes.byref(dm2), 0)
print("now:", dm2.dmPelsWidth, "x", dm2.dmPelsHeight, "@", dm2.dmDisplayFrequency, "pos:", dm2.dmPosition.x, dm2.dmPosition.y)