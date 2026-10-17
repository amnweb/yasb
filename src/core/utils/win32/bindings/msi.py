"""Wrappers for msi win32 API functions"""

from ctypes import Array, WinDLL, c_wchar
from ctypes.wintypes import DWORD, LPCWSTR, LPWSTR, UINT

msi = WinDLL("msi", use_last_error=True)

msi.MsiEnumRelatedProductsW.argtypes = [LPCWSTR, DWORD, DWORD, LPWSTR]
msi.MsiEnumRelatedProductsW.restype = UINT


def MsiEnumRelatedProducts(upgrade_code: str, index: int, product_buf: Array[c_wchar]) -> int:
    return msi.MsiEnumRelatedProductsW(upgrade_code, 0, index, product_buf)
