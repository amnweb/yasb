"""Type checking helpers for ctypes"""

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    # NOTE: this is an internal ctypes type that does not exist during runtime
    from ctypes import _CArgObject as CArgObject  # type: ignore[reportPrivateUsage]
    from ctypes import _Pointer as CPointer  # type: ignore[reportPrivateUsage]
else:
    CArgObject = Any

    class CPointer[T]:
        pass
