import ctypes
import logging
import os
import re
import subprocess
import sys
import webbrowser
import winreg

import win32com.client
from PyQt6.QtCore import QTimer

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult

# Segoe Fluent icon chars
_ICON_FILE = "\ue8a5"
_ICON_FOLDER = "\ue8b7"
_ICON_SEARCH = "\ue721"
_ICON_WARNING = "\ue7ba"

# Everything SDK constants
EVERYTHING_REQUEST_FILE_NAME = 0x00000001
EVERYTHING_REQUEST_PATH = 0x00000002
EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME = 0x00000004
EVERYTHING_REQUEST_SIZE = 0x00000010
EVERYTHING_SORT_NAME_ASCENDING = 1
EVERYTHING_OK = 0
EVERYTHING_ERROR_IPC = 2


if getattr(sys, "frozen", False):
    _BUNDLED_DLL = os.path.join(os.path.dirname(sys.executable), "lib", "Everything64.dll")
else:
    _BUNDLED_DLL = os.path.join(os.path.dirname(__file__), "sdk", "Everything64.dll")


class _EverythingBackend:
    """Backend using voidtools Everything SDK DLL."""

    _EXE_NAMES = ("Everything64.exe", "Everything32.exe", "Everything.exe")

    def __init__(self):
        self._dll = None
        self._available: bool | None = None
        self._buf = ctypes.create_unicode_buffer(520)
        self._size_val = ctypes.c_ulonglong(0)
        self._exe_path: str | None = None
        self._ipc_error = False

    def _load(self) -> bool:
        if self._available is not None:
            return self._available
        if not os.path.isfile(_BUNDLED_DLL):
            logging.debug(f"Everything DLL not found: {_BUNDLED_DLL}")
            self._available = False
            return False
        dll_path = _BUNDLED_DLL
        try:
            dll = ctypes.WinDLL(dll_path)
            dll.Everything_SetSearchW.argtypes = [ctypes.c_wchar_p]
            dll.Everything_SetMax.argtypes = [ctypes.c_ulong]
            dll.Everything_SetOffset.argtypes = [ctypes.c_ulong]
            dll.Everything_SetRequestFlags.argtypes = [ctypes.c_ulong]
            dll.Everything_SetSort.argtypes = [ctypes.c_ulong]
            dll.Everything_QueryW.argtypes = [ctypes.c_int]
            dll.Everything_QueryW.restype = ctypes.c_int
            dll.Everything_GetNumResults.restype = ctypes.c_ulong
            dll.Everything_GetLastError.restype = ctypes.c_ulong
            dll.Everything_GetResultFullPathNameW.argtypes = [
                ctypes.c_ulong,
                ctypes.c_wchar_p,
                ctypes.c_ulong,
            ]
            dll.Everything_IsFolderResult.argtypes = [ctypes.c_ulong]
            dll.Everything_IsFolderResult.restype = ctypes.c_int
            dll.Everything_GetResultSize.argtypes = [
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulonglong),
            ]
            dll.Everything_GetResultSize.restype = ctypes.c_int
            dll.Everything_Reset.argtypes = []
            dll.Everything_Reset.restype = None
            self._dll = dll
            self._available = True
            logging.info(f"Everything SDK loaded: {dll_path}")
        except Exception as e:
            logging.debug(f"Failed to load Everything DLL: {e}")
            self._available = False
        return self._available

    @property
    def available(self) -> bool:
        return self._load()

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        if not self._load():
            return []
        dll = self._dll
        try:
            dll.Everything_SetSearchW(query)
            dll.Everything_SetMax(max_results)
            dll.Everything_SetOffset(0)
            dll.Everything_SetRequestFlags(
                EVERYTHING_REQUEST_FILE_NAME
                | EVERYTHING_REQUEST_PATH
                | EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME
                | EVERYTHING_REQUEST_SIZE
            )
            dll.Everything_SetSort(EVERYTHING_SORT_NAME_ASCENDING)

            if not dll.Everything_QueryW(1):
                err = dll.Everything_GetLastError()
                if err == EVERYTHING_ERROR_IPC:
                    self._ipc_error = True
                    logging.debug("Everything IPC error - is Everything running?")
                return []

            num = min(dll.Everything_GetNumResults(), max_results)
            results = []
            buf = self._buf
            size_val = self._size_val
            for i in range(num):
                dll.Everything_GetResultFullPathNameW(i, buf, 520)
                full_path = buf.value
                is_folder = bool(dll.Everything_IsFolderResult(i))
                file_size = 0
                if not is_folder and dll.Everything_GetResultSize(i, ctypes.byref(size_val)):
                    file_size = size_val.value
                results.append(
                    {
                        "path": full_path,
                        "name": os.path.basename(full_path),
                        "is_folder": is_folder,
                        "size": file_size,
                    }
                )
            dll.Everything_Reset()
            self._ipc_error = False
            return results
        except Exception as e:
            logging.debug(f"Everything search error: {e}")
            return []

    def _find_exe(self) -> str | None:
        """Locate the Everything executable from registry or common paths."""
        if self._exe_path is not None:
            return self._exe_path or None
        # Check registry
        for key_path in (
            r"SOFTWARE\voidtools\Everything",
            r"SOFTWARE\WOW6432Node\voidtools\Everything",
        ):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    install_dir = winreg.QueryValueEx(key, "InstallFolder")[0]
                    if install_dir:
                        for name in self._EXE_NAMES:
                            candidate = os.path.join(install_dir, name)
                            if os.path.isfile(candidate):
                                self._exe_path = candidate
                                return candidate
            except OSError:
                continue
        # Check common install locations
        for base in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", "")):
            if not base:
                continue
            d = os.path.join(base, "Everything")
            if os.path.isdir(d):
                for name in self._EXE_NAMES:
                    candidate = os.path.join(d, name)
                    if os.path.isfile(candidate):
                        self._exe_path = candidate
                        return candidate
        self._exe_path = ""
        return None

    @property
    def has_ipc_error(self) -> bool:
        return self._ipc_error

    def launch_everything(self) -> bool:
        """Attempt to start the Everything process."""
        exe = self._find_exe()
        if not exe:
            return False
        try:
            subprocess.Popen(
                [exe, "-startup"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._ipc_error = False
            self._available = None  # Reset so next query retries
            return True
        except Exception as e:
            logging.debug(f"Failed to launch Everything: {e}")
            return False


class _WindowsSearchBackend:
    """Backend using Windows Search indexer via COM (ADODB)."""

    def __init__(self):
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import win32com.client

            conn = win32com.client.Dispatch("ADODB.Connection")
            conn.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
            conn.Close()
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        try:
            conn = win32com.client.Dispatch("ADODB.Connection")
            conn.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
            # Strip to safe filename characters only, ADODB doesn't support parameterized queries
            safe_query = re.sub(r"[^\w\s.\-()]", "", query)
            if not safe_query:
                conn.Close()
                return []
            sql = (
                f"SELECT TOP {max_results} System.ItemPathDisplay, System.ItemType, System.Size "
                f"FROM SystemIndex "
                f"WHERE System.FileName LIKE '%{safe_query}%' "
                f"ORDER BY System.ItemPathDisplay ASC"
            )
            rs, _ = conn.Execute(sql)
            results = []
            while not rs.EOF:
                path = rs.Fields("System.ItemPathDisplay").Value
                item_type = rs.Fields("System.ItemType").Value or ""
                size_val = rs.Fields("System.Size").Value
                is_folder = item_type == "Directory" or (path and os.path.isdir(path))
                results.append(
                    {
                        "path": path or "",
                        "name": os.path.basename(path) if path else "",
                        "is_folder": is_folder,
                        "size": int(size_val) if size_val else 0,
                    }
                )
                rs.MoveNext()
            rs.Close()
            conn.Close()
            return results
        except Exception as e:
            logging.debug(f"Windows Search error: {e}")
            return []


def _format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return ""
    val = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024:
            return f"{val:.0f} {unit}" if unit == "B" else f"{val:.1f} {unit}"
        val /= 1024
    return f"{val:.1f} PB"


class FileSearchProvider(BaseProvider):
    """Search files and folders using Everything or Windows Search."""

    name = "file_search"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._backend_name = (config or {}).get("backend", "auto")
        self._max_results = (config or {}).get("_max_results", 50)
        self._everything = _EverythingBackend()
        self._windows_search = _WindowsSearchBackend()
        self._active_backend = None

    def _get_backend(self):
        if self._active_backend is not None:
            return self._active_backend
        if self._backend_name == "everything":
            if self._everything.available:
                self._active_backend = self._everything
            else:
                logging.warning("Everything backend requested but not available")
        elif self._backend_name == "windows":
            if self._windows_search.available:
                self._active_backend = self._windows_search
            else:
                logging.warning("Windows Search backend requested but not available")
        else:  # auto
            if self._everything.available:
                self._active_backend = self._everything
                logging.info("File search: using Everything backend")
            elif self._windows_search.available:
                self._active_backend = self._windows_search
                logging.info("File search: using Windows Search backend")
            else:
                logging.warning("No file search backend available")
        return self._active_backend

    def match(self, text: str) -> bool:
        if self.prefix:
            return text.strip().startswith(self.prefix)
        return True

    def get_results(self, text: str) -> list[ProviderResult]:
        query = self.get_query_text(text) if self.prefix and text.strip().startswith(self.prefix) else text.strip()

        if not query:
            backend = self._get_backend()
            # Check if Everything is configured but not running
            if self._everything.has_ipc_error or (
                self._backend_name in ("auto", "everything") and self._everything._available and not backend
            ):
                return self._everything_not_running_results()
            backend_label = (
                "Everything"
                if isinstance(backend, _EverythingBackend)
                else "Windows Search"
                if backend
                else "unavailable"
            )
            return [
                ProviderResult(
                    title="Search files and folders",
                    description=f"Backend: {backend_label}",
                    icon_char=_ICON_SEARCH,
                    provider=self.name,
                )
            ]

        backend = self._get_backend()
        if not backend:
            # Check if Everything DLL loaded but service not running
            if self._everything.has_ipc_error:
                return self._everything_not_running_results()
            return [
                ProviderResult(
                    title="No search backend available",
                    description="Install Everything or enable Windows Search indexer",
                    icon_char=_ICON_SEARCH,
                    provider=self.name,
                )
            ]

        raw = backend.search(query, self._max_results)
        # Check if Everything returned empty due to IPC error
        if not raw and isinstance(backend, _EverythingBackend) and backend.has_ipc_error:
            return self._everything_not_running_results()

        results = []
        home = os.path.expanduser("~")
        for item in raw:
            path = item["path"]
            name = item["name"]
            is_folder = item["is_folder"]
            size = item["size"]
            parent = os.path.dirname(path)
            # Shorten home directory prefix to ~
            if parent.startswith(home):
                parent = "~" + parent[len(home) :]
            size_str = f"  \u2022  {_format_size(size)}" if size and not is_folder else ""
            results.append(
                ProviderResult(
                    title=name,
                    description=f"{parent}{size_str}",
                    icon_char=_ICON_FOLDER if is_folder else _ICON_FILE,
                    provider=self.name,
                    action_data={"path": path, "is_folder": is_folder},
                )
            )
        return results

    def execute(self, result: ProviderResult) -> bool:
        action = result.action_data.get("action", "")
        if action == "launch_everything":
            self._everything.launch_everything()
            self._active_backend = None  # Reset backend selection
            self._wait_for_everything_ipc()
            return False  # Keep popup open
        if action == "install_everything":
            webbrowser.open("https://www.voidtools.com/")
            return True
        path = result.action_data.get("path", "")
        if not path or not os.path.exists(path):
            return False
        try:
            os.startfile(path)
            return True
        except Exception as e:
            logging.error(f"Failed to open: {e}")
            return False

    def _wait_for_everything_ipc(self, retries: int = 10, interval: int = 500):
        """Poll for Everything IPC availability after launch, then trigger a refresh."""
        self._ipc_retries_left = retries
        self._ipc_poll_timer = QTimer()
        self._ipc_poll_timer.setSingleShot(True)
        self._ipc_poll_timer.setInterval(interval)
        self._ipc_poll_timer.timeout.connect(self._check_everything_ipc)
        self._ipc_poll_timer.start()

    def _check_everything_ipc(self):
        """Check if Everything IPC is ready, retry or trigger refresh."""
        self._everything._available = None
        if self._everything.available:
            self._active_backend = self._everything
            if self.request_refresh:
                self.request_refresh()
            return
        self._ipc_retries_left -= 1
        if self._ipc_retries_left > 0:
            self._ipc_poll_timer.start()
        else:
            logging.debug("Everything IPC not available after 10 retries")

    def _everything_not_running_results(self) -> list[ProviderResult]:
        exe = self._everything._find_exe()
        results = []
        if exe:
            results.append(
                ProviderResult(
                    title="Everything service is not running",
                    description="Click to launch Everything",
                    icon_char=_ICON_WARNING,
                    provider=self.name,
                    action_data={"action": "launch_everything"},
                )
            )
        else:
            results.append(
                ProviderResult(
                    title="Everything is not installed",
                    description="Click to download from voidtools.com",
                    icon_char=_ICON_WARNING,
                    provider=self.name,
                    action_data={"action": "install_everything"},
                )
            )
        return results
