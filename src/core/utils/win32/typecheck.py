"""
Type checking helpers for ctypes
Required for private types (_CArgObject, _CFunctionType, _Pointer) not exposed to the public API
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # NOTE: this is an internal ctypes type that does not exist during runtime
    from ctypes import _CArgObject, _CData, _CFunctionType, _Pointer  # pyright: ignore[reportPrivateUsage]

    type CArgObject = _CArgObject
    type CFunctionType = _CFunctionType
    type CPointer[T: _CData] = _Pointer[T]
else:
    # NOTE: During runtime just use Any placeholders
    CArgObject = Any
    CFunctionType = Any

    class CPointer[T]:
        pass
