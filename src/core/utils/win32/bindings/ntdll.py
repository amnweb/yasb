"""Wrappers for ntdll win32 API functions"""

from ctypes import POINTER, c_void_p, windll
from ctypes.wintypes import HANDLE, LONG, ULONG

ntdll = windll.ntdll

# NtQueryInformationProcess - used to get process command line, etc.
ntdll.NtQueryInformationProcess.argtypes = [
    HANDLE,  # ProcessHandle
    ULONG,  # ProcessInformationClass
    c_void_p,  # ProcessInformation
    ULONG,  # ProcessInformationLength
    POINTER(ULONG),  # ReturnLength
]
ntdll.NtQueryInformationProcess.restype = LONG

# Process information class constants
ProcessCommandLineInformation = 60
