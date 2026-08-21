"""AES-256-GCM through the Windows CNG provider (bcrypt.dll)."""

import ctypes
import threading
from ctypes import POINTER, byref, c_void_p, create_unicode_buffer, sizeof
from ctypes.wintypes import LPCWSTR, ULONG
from typing import Any

from core.cloud.errors import CryptoError, IntegrityError

# Algorithm identifiers and property names from bcrypt.h.
BCRYPT_AES_ALGORITHM = "AES"
BCRYPT_CHAINING_MODE = "ChainingMode"
BCRYPT_CHAIN_MODE_GCM = "ChainingModeGCM"
BCRYPT_OBJECT_LENGTH = "ObjectLength"

BCRYPT_INIT_AUTH_MODE_INFO_VERSION = 1

STATUS_SUCCESS = 0x00000000
STATUS_AUTH_TAG_MISMATCH = 0xC000A002

KEY_LEN = 32
"""AES-256."""

NONCE_LEN = 12
"""96-bit: the size GCM is defined for and the only one that avoids re-hashing."""

TAG_LEN = 16
"""Full 128-bit authentication tag. Never truncate it."""

PUCHAR = POINTER(ctypes.c_ubyte)


class BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO(ctypes.Structure):
    """`BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO` from bcrypt.h."""

    _fields_ = (
        ("cbSize", ULONG),
        ("dwInfoVersion", ULONG),
        ("pbNonce", PUCHAR),
        ("cbNonce", ULONG),
        ("pbAuthData", PUCHAR),
        ("cbAuthData", ULONG),
        ("pbTag", PUCHAR),
        ("cbTag", ULONG),
        ("pbMacContext", PUCHAR),
        ("cbMacContext", ULONG),
        ("cbAAD", ULONG),
        ("cbData", ctypes.c_ulonglong),
        ("dwFlags", ULONG),
    )


_bcrypt = ctypes.WinDLL("bcrypt.dll")

_bcrypt.BCryptOpenAlgorithmProvider.argtypes = [POINTER(c_void_p), LPCWSTR, LPCWSTR, ULONG]
_bcrypt.BCryptOpenAlgorithmProvider.restype = ctypes.c_long

_bcrypt.BCryptCloseAlgorithmProvider.argtypes = [c_void_p, ULONG]
_bcrypt.BCryptCloseAlgorithmProvider.restype = ctypes.c_long

_bcrypt.BCryptGetProperty.argtypes = [c_void_p, LPCWSTR, PUCHAR, ULONG, POINTER(ULONG), ULONG]
_bcrypt.BCryptGetProperty.restype = ctypes.c_long

_bcrypt.BCryptSetProperty.argtypes = [c_void_p, LPCWSTR, PUCHAR, ULONG, ULONG]
_bcrypt.BCryptSetProperty.restype = ctypes.c_long

_bcrypt.BCryptGenerateSymmetricKey.argtypes = [
    c_void_p,
    POINTER(c_void_p),
    PUCHAR,
    ULONG,
    PUCHAR,
    ULONG,
    ULONG,
]
_bcrypt.BCryptGenerateSymmetricKey.restype = ctypes.c_long

_bcrypt.BCryptDestroyKey.argtypes = [c_void_p]
_bcrypt.BCryptDestroyKey.restype = ctypes.c_long

_bcrypt.BCryptEncrypt.argtypes = [
    c_void_p,
    PUCHAR,
    ULONG,
    c_void_p,
    PUCHAR,
    ULONG,
    PUCHAR,
    ULONG,
    POINTER(ULONG),
    ULONG,
]
_bcrypt.BCryptEncrypt.restype = ctypes.c_long

_bcrypt.BCryptDecrypt.argtypes = _bcrypt.BCryptEncrypt.argtypes
_bcrypt.BCryptDecrypt.restype = ctypes.c_long


def _check(status: int, operation: str) -> None:
    """Raise on a failed NTSTATUS, mapping tag mismatch to `IntegrityError`."""
    code = status & 0xFFFFFFFF
    if code == STATUS_SUCCESS:
        return
    if code == STATUS_AUTH_TAG_MISMATCH:
        raise IntegrityError("Authentication failed: data was modified, truncated, or the key is wrong")
    raise CryptoError(f"{operation} failed (NTSTATUS 0x{code:08X})")


def _buf(data: bytes) -> ctypes.Array[ctypes.c_ubyte]:
    return (ctypes.c_ubyte * len(data)).from_buffer_copy(data)


def _as_puchar(buffer: ctypes.Array[ctypes.c_ubyte] | None) -> Any:
    """Cast a ctypes byte array to `PUCHAR`, or NULL for an empty/absent buffer."""
    if buffer is None or len(buffer) == 0:
        return ctypes.cast(None, PUCHAR)
    return ctypes.cast(buffer, PUCHAR)


class _Provider:
    """Process-wide AES-GCM provider, opened on first use and never closed."""

    def __init__(self) -> None:
        self._handle: c_void_p | None = None
        self._object_length = 0
        self._lock = threading.Lock()

    def acquire(self) -> tuple[c_void_p, int]:
        """Return `(algorithm_handle, key_object_length)`.

        Workers call this from their own threads. `_handle` is assigned last, so the
        unlocked read either sees a finished provider or falls through to the lock.
        """
        if self._handle is not None:
            return self._handle, self._object_length
        with self._lock:
            if self._handle is not None:
                return self._handle, self._object_length

            handle = c_void_p()
            _check(
                _bcrypt.BCryptOpenAlgorithmProvider(byref(handle), BCRYPT_AES_ALGORITHM, None, 0),
                "BCryptOpenAlgorithmProvider",
            )

            mode = create_unicode_buffer(BCRYPT_CHAIN_MODE_GCM)
            _check(
                _bcrypt.BCryptSetProperty(
                    handle,
                    BCRYPT_CHAINING_MODE,
                    ctypes.cast(mode, PUCHAR),
                    sizeof(mode),
                    0,
                ),
                "BCryptSetProperty(ChainingModeGCM)",
            )

            length = ULONG(0)
            written = ULONG(0)
            _check(
                _bcrypt.BCryptGetProperty(
                    handle,
                    BCRYPT_OBJECT_LENGTH,
                    ctypes.cast(byref(length), PUCHAR),
                    sizeof(length),
                    byref(written),
                    0,
                ),
                "BCryptGetProperty(ObjectLength)",
            )

            self._object_length = length.value
            self._handle = handle
            return self._handle, self._object_length


_provider = _Provider()


class GcmKey:
    """An AES-256-GCM key handle. Holds unmanaged memory, so use it as a context manager."""

    __slots__ = ("_closed", "_handle", "_key_object")

    def __init__(self, key: bytes) -> None:
        if len(key) != KEY_LEN:
            raise CryptoError(f"AES-256 requires a {KEY_LEN}-byte key, got {len(key)}")

        algorithm, object_length = _provider.acquire()
        self._key_object = (ctypes.c_ubyte * object_length)()
        self._handle = c_void_p()
        self._closed = False

        secret = _buf(key)
        _check(
            _bcrypt.BCryptGenerateSymmetricKey(
                algorithm,
                byref(self._handle),
                _as_puchar(self._key_object),
                object_length,
                _as_puchar(secret),
                len(secret),
                0,
            ),
            "BCryptGenerateSymmetricKey",
        )

    def __enter__(self) -> GcmKey:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._handle:
            _bcrypt.BCryptDestroyKey(self._handle)
            self._handle = c_void_p()

    def __del__(self) -> None:
        # Backstop for a key nobody closed. Too late in teardown to report anything useful.
        try:
            self.close()
        except Exception:
            pass

    def _mode_info(
        self,
        nonce: bytes,
        aad: bytes,
        tag_buffer: ctypes.Array[ctypes.c_ubyte],
    ) -> tuple[BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO, tuple[object, ...]]:
        """Build the auth-mode struct for one complete message.

        `pbMacContext` is empty because no frame is split across calls. The returned buffers
        must stay alive while the struct is in use, or ctypes collects them.
        """
        nonce_buffer = _buf(nonce)
        aad_buffer = _buf(aad) if aad else None

        info = BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO()
        info.cbSize = sizeof(BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO)
        info.dwInfoVersion = BCRYPT_INIT_AUTH_MODE_INFO_VERSION
        info.pbNonce = _as_puchar(nonce_buffer)
        info.cbNonce = len(nonce_buffer)
        info.pbAuthData = _as_puchar(aad_buffer)
        info.cbAuthData = len(aad_buffer) if aad_buffer is not None else 0
        info.pbTag = _as_puchar(tag_buffer)
        info.cbTag = len(tag_buffer)
        return info, (nonce_buffer, aad_buffer, tag_buffer)

    def encrypt(self, nonce: bytes, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
        """Encrypt one message, returning `(ciphertext, tag)`.

        Nonces are the caller's problem. Reusing a (key, nonce) pair breaks GCM outright.
        """
        if len(nonce) != NONCE_LEN:
            raise CryptoError(f"GCM requires a {NONCE_LEN}-byte nonce, got {len(nonce)}")

        tag_buffer = (ctypes.c_ubyte * TAG_LEN)()
        info, _keepalive = self._mode_info(nonce, aad, tag_buffer)

        source = _buf(plaintext)
        output = (ctypes.c_ubyte * len(plaintext))()
        written = ULONG(0)

        _check(
            _bcrypt.BCryptEncrypt(
                self._handle,
                _as_puchar(source),
                len(source),
                byref(info),
                None,
                0,
                _as_puchar(output),
                len(output),
                byref(written),
                0,
            ),
            "BCryptEncrypt",
        )
        # string_at is one memcpy, slicing a ctypes array builds a list of ints per byte.
        return ctypes.string_at(output, written.value), bytes(tag_buffer)

    def decrypt(self, nonce: bytes, ciphertext: bytes, tag: bytes, aad: bytes = b"") -> bytes:
        """Decrypt and verify the tag."""
        if len(nonce) != NONCE_LEN:
            raise CryptoError(f"GCM requires a {NONCE_LEN}-byte nonce, got {len(nonce)}")
        if len(tag) != TAG_LEN:
            raise IntegrityError(f"Expected a {TAG_LEN}-byte tag, got {len(tag)}")

        tag_buffer = _buf(tag)
        info, _keepalive = self._mode_info(nonce, aad, tag_buffer)

        source = _buf(ciphertext)
        output = (ctypes.c_ubyte * len(ciphertext))()
        written = ULONG(0)

        _check(
            _bcrypt.BCryptDecrypt(
                self._handle,
                _as_puchar(source),
                len(source),
                byref(info),
                None,
                0,
                _as_puchar(output),
                len(output),
                byref(written),
                0,
            ),
            "BCryptDecrypt",
        )
        return ctypes.string_at(output, written.value)
