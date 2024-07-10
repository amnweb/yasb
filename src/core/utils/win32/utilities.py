import psutil
import ctypes
import ctypes.wintypes
from win32process import GetWindowThreadProcessId
from win32gui import GetWindowText, GetClassName, GetWindowRect, GetWindowPlacement
from win32api import MonitorFromWindow, GetMonitorInfo
from contextlib import suppress


SW_MAXIMIZE = 3
DWMWA_EXTENDED_FRAME_BOUNDS = 9
dwmapi = ctypes.WinDLL("dwmapi")


def get_monitor_hwnd(window_hwnd: int) -> int:
    return int(MonitorFromWindow(window_hwnd))


def get_monitor_info(monitor_hwnd: int) -> dict:
    monitor_info = GetMonitorInfo(monitor_hwnd)
    return {
        'rect': {
            'x': monitor_info['Monitor'][0],
            'y': monitor_info['Monitor'][1],
            'width': monitor_info['Monitor'][2],
            'height': monitor_info['Monitor'][3]
        },
        'rect_work_area': {
            'x': monitor_info['Work'][0],
            'y': monitor_info['Work'][1],
            'width': monitor_info['Work'][2],
            'height': monitor_info['Work'][3]
        },
        'flags': monitor_info['Flags'],
        'device': monitor_info['Device']
    }


def get_process_info(hwnd: int) -> dict:
    process_id = GetWindowThreadProcessId(hwnd)
    process = psutil.Process(process_id[-1])
    return {
        'name': process.name(),
        'pid': process.pid,
        'ppid': process.ppid(),
        'cpu_percent': process.cpu_percent(),
        'mem_percent': process.memory_percent(),
        'num_threads': process.num_threads(),
        'username': process.username(),
        'status': process.status()
    }


def get_window_extended_frame_bounds(hwnd: int) -> dict:
    rect = ctypes.wintypes.RECT()

    dwmapi.DwmGetWindowAttribute(
        ctypes.wintypes.HWND(hwnd),
        ctypes.wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
        ctypes.byref(rect),
        ctypes.sizeof(rect)
    )

    return {
        'x': rect.left,
        'y': rect.top,
        'width': rect.right - rect.left,
        'height': rect.bottom - rect.top
    }


def get_window_rect(hwnd: int) -> dict:
    window_rect = GetWindowRect(hwnd)
    return {
        'x': window_rect[0],
        'y': window_rect[1],
        'width': window_rect[2] - window_rect[0],
        'height': window_rect[3] - window_rect[1],
    }


def is_window_maximised(hwnd: int) -> bool:
    window_placement = GetWindowPlacement(hwnd)
    return window_placement[1] == SW_MAXIMIZE


def get_hwnd_info(hwnd: int) -> dict:
    with suppress(Exception):
        monitor_hwnd = get_monitor_hwnd(hwnd)
        monitor_info = get_monitor_info(monitor_hwnd)

        return {
            'hwnd': hwnd,
            'title': GetWindowText(hwnd),
            'class_name': GetClassName(hwnd),
            'process': get_process_info(hwnd),
            'monitor_hwnd': monitor_hwnd,
            'monitor_info': monitor_info,
            'rect': get_window_rect(hwnd)
        }
