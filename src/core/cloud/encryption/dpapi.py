"""Local at-rest protection via DPAPI (`crypt32.dll`)."""

import ctypes
from ctypes import POINTER, byref, c_void_p
from ctypes.wintypes import BOOL, DWORD, LPCWSTR

from core.cloud.errors import CryptoError

CRYPTPROTECT_UI_FORBIDDEN = 0x1
"""Never prompt. This runs unattended, a blocking dialog would hang the app."""


class DATA_BLOB(ctypes.Structure):
    """`DATA_BLOB` from wincrypt.h."""

    _fields_ = (("cbData", DWORD), ("pbData", POINTER(ctypes.c_char)))


_crypt32 = ctypes.WinDLL("crypt32.dll", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32.dll")

_crypt32.CryptProtectData.argtypes = [
    POINTER(DATA_BLOB),
    LPCWSTR,
    POINTER(DATA_BLOB),
    c_void_p,
    c_void_p,
    DWORD,
    POINTER(DATA_BLOB),
]
_crypt32.CryptProtectData.restype = BOOL

_crypt32.CryptUnprotectData.argtypes = [
    POINTER(DATA_BLOB),
    POINTER(LPCWSTR),
    POINTER(DATA_BLOB),
    c_void_p,
    c_void_p,
    DWORD,
    POINTER(DATA_BLOB),
]
_crypt32.CryptUnprotectData.restype = BOOL

_kernel32.LocalFree.argtypes = [c_void_p]
_kernel32.LocalFree.restype = c_void_p


def _blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array[ctypes.c_char]]:
    """Build a DATA_BLOB plus the buffer it points at, which the caller must keep alive."""
    buffer = ctypes.create_string_buffer(data, len(data))
    blob = DATA_BLOB(len(data), ctypes.cast(buffer, POINTER(ctypes.c_char)))
    return blob, buffer


def _take(blob: DATA_BLOB) -> bytes:
    """Copy an output blob and release the memory CryptoAPI allocated for it."""
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        if blob.pbData:
            _kernel32.LocalFree(blob.pbData)


def protect(data: bytes, entropy: bytes) -> bytes:
    """Encrypt `data` for the current Windows user.

    `entropy` is a fixed label, not a password. session.bin and vault.bin use different ones
    so neither can be renamed over the other.
    """
    source, _keep_source = _blob(data)
    extra, _keep_extra = _blob(entropy)
    output = DATA_BLOB()

    ok = _crypt32.CryptProtectData(
        byref(source),
        None,
        byref(extra),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        byref(output),
    )
    if not ok:
        raise CryptoError(f"CryptProtectData failed (error {ctypes.get_last_error()})")
    return _take(output)


def unprotect(data: bytes, entropy: bytes) -> bytes:
    """Decrypt a blob produced by `protect` with the same `entropy`.

    Fails for another Windows user, on another machine, or with the wrong label.
    """
    source, _keep_source = _blob(data)
    extra, _keep_extra = _blob(entropy)
    output = DATA_BLOB()

    ok = _crypt32.CryptUnprotectData(
        byref(source),
        None,
        byref(extra),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        byref(output),
    )
    if not ok:
        raise CryptoError(f"CryptUnprotectData failed (error {ctypes.get_last_error()})")
    return _take(output)
