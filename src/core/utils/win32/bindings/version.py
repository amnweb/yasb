"""Wrappers for version.dll (file version information) win32 API functions"""

from collections.abc import Iterable
from ctypes import POINTER, Array, WinDLL, byref, c_char, c_void_p, cast, create_string_buffer, wstring_at
from ctypes.wintypes import BOOL, DWORD, LPCVOID, LPCWSTR, LPDWORD, LPVOID, UINT, WORD

version = WinDLL("version", use_last_error=True)

version.GetFileVersionInfoSizeW.argtypes = [LPCWSTR, LPDWORD]
version.GetFileVersionInfoSizeW.restype = DWORD

version.GetFileVersionInfoW.argtypes = [LPCWSTR, DWORD, DWORD, LPVOID]
version.GetFileVersionInfoW.restype = BOOL

version.VerQueryValueW.argtypes = [LPCVOID, LPCWSTR, POINTER(LPVOID), POINTER(UINT)]
version.VerQueryValueW.restype = BOOL


def GetFileVersionInfo(filename: str) -> Array[c_char] | None:
    size = version.GetFileVersionInfoSizeW(filename, None)
    if not size:
        return None
    block = create_string_buffer(size)
    if not version.GetFileVersionInfoW(filename, 0, size, block):
        return None
    return block


def VerQueryValue(block: Array[c_char], sub_block: str) -> tuple[int, int] | None:
    """(address, length) of the value; the address points into block, so keep block alive while using it."""
    address = c_void_p()
    length = UINT()
    if not version.VerQueryValueW(block, sub_block, byref(address), byref(length)):
        return None
    if not address.value or not length.value:
        return None
    return address.value, length.value


def get_version_strings(filename: str, names: Iterable[str]) -> dict[str, str]:
    """Non-empty string values for the first language in the file's version info, keyed by name."""
    block = GetFileVersionInfo(filename)
    if block is None:
        return {}
    translation = VerQueryValue(block, r"\VarFileInfo\Translation")
    if translation is None:
        return {}
    language, codepage = cast(translation[0], POINTER(WORD * 2)).contents
    prefix = rf"\StringFileInfo\{language:04X}{codepage:04X}"
    values: dict[str, str] = {}
    for name in names:
        value = VerQueryValue(block, f"{prefix}\\{name}")
        if value is not None and (text := wstring_at(value[0]).strip()):
            values[name] = text
    return values
