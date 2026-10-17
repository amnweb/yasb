"""voidtools Everything SDK (Everything64.dll or EverythingARM64.dll), bundled with YASB"""

from ctypes import POINTER, Array, WinDLL, c_longlong, c_wchar
from ctypes.wintypes import BOOL, DWORD, LPCWSTR, LPWSTR

from core.utils.win32.typecheck import CArgObject

EVERYTHING_REQUEST_FILE_NAME = 0x00000001
EVERYTHING_REQUEST_PATH = 0x00000002
EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME = 0x00000004
EVERYTHING_REQUEST_SIZE = 0x00000010
EVERYTHING_SORT_NAME_ASCENDING = 1
EVERYTHING_ERROR_IPC = 2


class EverythingLibrary:
    """Raises OSError when the SDK DLL at path cannot be loaded."""

    def __init__(self, path: str) -> None:
        self._dll = WinDLL(path, use_last_error=True)
        self._dll.Everything_SetSearchW.argtypes = [LPCWSTR]
        self._dll.Everything_SetSearchW.restype = None
        self._dll.Everything_SetMax.argtypes = [DWORD]
        self._dll.Everything_SetMax.restype = None
        self._dll.Everything_SetOffset.argtypes = [DWORD]
        self._dll.Everything_SetOffset.restype = None
        self._dll.Everything_SetRequestFlags.argtypes = [DWORD]
        self._dll.Everything_SetRequestFlags.restype = None
        self._dll.Everything_SetSort.argtypes = [DWORD]
        self._dll.Everything_SetSort.restype = None
        self._dll.Everything_QueryW.argtypes = [BOOL]
        self._dll.Everything_QueryW.restype = BOOL
        self._dll.Everything_GetNumResults.argtypes = []
        self._dll.Everything_GetNumResults.restype = DWORD
        self._dll.Everything_GetMajorVersion.argtypes = []
        self._dll.Everything_GetMajorVersion.restype = DWORD
        self._dll.Everything_GetLastError.argtypes = []
        self._dll.Everything_GetLastError.restype = DWORD
        self._dll.Everything_GetResultFullPathNameW.argtypes = [DWORD, LPWSTR, DWORD]
        self._dll.Everything_GetResultFullPathNameW.restype = DWORD
        self._dll.Everything_IsFolderResult.argtypes = [DWORD]
        self._dll.Everything_IsFolderResult.restype = BOOL
        self._dll.Everything_GetResultSize.argtypes = [DWORD, POINTER(c_longlong)]
        self._dll.Everything_GetResultSize.restype = BOOL
        self._dll.Everything_Reset.argtypes = []
        self._dll.Everything_Reset.restype = None

    def Everything_SetSearchW(self, lpString: str) -> None:
        self._dll.Everything_SetSearchW(lpString)

    def Everything_SetMax(self, dwMax: int) -> None:
        self._dll.Everything_SetMax(dwMax)

    def Everything_SetOffset(self, dwOffset: int) -> None:
        self._dll.Everything_SetOffset(dwOffset)

    def Everything_SetRequestFlags(self, dwRequestFlags: int) -> None:
        self._dll.Everything_SetRequestFlags(dwRequestFlags)

    def Everything_SetSort(self, dwSortType: int) -> None:
        self._dll.Everything_SetSort(dwSortType)

    def Everything_QueryW(self, bWait: bool) -> bool:
        return bool(self._dll.Everything_QueryW(bWait))

    def Everything_GetNumResults(self) -> int:
        return self._dll.Everything_GetNumResults()

    def Everything_GetMajorVersion(self) -> int:
        return self._dll.Everything_GetMajorVersion()

    def Everything_GetLastError(self) -> int:
        return self._dll.Everything_GetLastError()

    def Everything_GetResultFullPathNameW(self, dwIndex: int, wbuf: Array[c_wchar], wbuf_size_in_wchars: int) -> int:
        return self._dll.Everything_GetResultFullPathNameW(dwIndex, wbuf, wbuf_size_in_wchars)

    def Everything_IsFolderResult(self, dwIndex: int) -> bool:
        return bool(self._dll.Everything_IsFolderResult(dwIndex))

    def Everything_GetResultSize(self, dwIndex: int, lpSize: CArgObject) -> bool:
        return bool(self._dll.Everything_GetResultSize(dwIndex, lpSize))

    def Everything_Reset(self) -> None:
        self._dll.Everything_Reset()
