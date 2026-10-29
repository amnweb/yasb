import ctypes
import datetime
import fnmatch
import logging
import os
import re
import string
import struct
import sys
import sysconfig
import winreg
from collections import deque
from collections.abc import Callable
from threading import Event
from typing import Any

from PyQt6.QtCore import QStandardPaths, QTimer
from PyQt6.QtGui import QGuiApplication

from core.utils.shell_utils import shell_open
from core.utils.win32.bindings.everything import (
    EVERYTHING_ERROR_IPC,
    EVERYTHING_REQUEST_FILE_NAME,
    EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME,
    EVERYTHING_REQUEST_PATH,
    EVERYTHING_REQUEST_SIZE,
    EVERYTHING_SORT_NAME_ASCENDING,
    EverythingLibrary,
)
from core.utils.win32.bindings.kernel32 import (
    FindClose,
    FindFirstFileEx,
    FindNextFile,
    GetDriveType,
    GetLastError,
    GetLogicalDrives,
    GlobalAlloc,
    GlobalFree,
    GlobalLock,
    GlobalUnlock,
)
from core.utils.win32.bindings.user32 import CloseClipboard, EmptyClipboard, OpenClipboard, SetClipboardData
from core.utils.win32.constants import (
    CF_HDROP,
    DRIVE_CDROM,
    DRIVE_REMOTE,
    DRIVE_REMOVABLE,
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_HIDDEN,
    FILE_ATTRIBUTE_SYSTEM,
    FIND_EX_INFO_BASIC,
    FIND_FIRST_EX_LARGE_FETCH,
    GHND,
    SW_HIDE,
)
from core.utils.win32.registry_keys import EVERYTHING_KEY, EVERYTHING_WOW64_KEY
from core.utils.win32.structs import WIN32_FIND_DATAW
from core.widgets.services.quick_launch.base_provider import (
    BaseProvider,
    ProviderMenuAction,
    ProviderMenuActionResult,
    ProviderResult,
)
from core.widgets.services.quick_launch.providers.resources.icons import (
    ICON_ARCHIVE,
    ICON_AUDIO,
    ICON_CODE,
    ICON_DATABASE,
    ICON_DISC,
    ICON_EXE,
    ICON_FILE,
    ICON_FOLDER,
    ICON_FONT,
    ICON_IMAGE,
    ICON_PDF,
    ICON_PRESENTATION,
    ICON_SEARCH,
    ICON_SPREADSHEET,
    ICON_TEXT,
    ICON_VIDEO,
    ICON_WARNING,
)

_EXT_ICON_MAP: dict[str, str] = {}
for _icon, _exts in (
    (ICON_TEXT, (".txt", ".log", ".md", ".rtf", ".doc", ".docx", ".odt", ".tex", ".epub")),
    (ICON_PDF, (".pdf",)),
    (
        ICON_IMAGE,
        (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".tif", ".heic", ".avif", ".raw"),
    ),
    (ICON_VIDEO, (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".3gp")),
    (ICON_AUDIO, (".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".mid", ".midi")),
    (
        ICON_CODE,
        (
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".c",
            ".cpp",
            ".h",
            ".cs",
            ".java",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".html",
            ".css",
            ".scss",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".cfg",
            ".sh",
            ".bat",
            ".ps1",
            ".sql",
        ),
    ),
    (ICON_ARCHIVE, (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst", ".cab")),
    (ICON_SPREADSHEET, (".xls", ".xlsx", ".csv", ".ods")),
    (ICON_PRESENTATION, (".ppt", ".pptx", ".odp")),
    (ICON_DATABASE, (".db", ".sqlite", ".mdb", ".accdb", ".sql")),
    (ICON_FONT, (".ttf", ".otf", ".woff", ".woff2")),
    (ICON_EXE, (".exe", ".msi", ".dll", ".sys")),
    (ICON_DISC, (".iso", ".img", ".vhd", ".vhdx")),
):
    for _ext in _exts:
        _EXT_ICON_MAP[_ext] = _icon


def _get_file_icon(name: str, is_folder: bool) -> str:
    if is_folder:
        return ICON_FOLDER
    ext = os.path.splitext(name)[1].lower()
    return _EXT_ICON_MAP.get(ext, ICON_FILE)


from core.utils.win32.bindings.ole32 import create_dispatch
from settings import IS_FROZEN

# Loaded into YASB's own process, so it follows the Python build's architecture, not the host's.
_EVERYTHING_DLL = "EverythingARM64.dll" if sysconfig.get_platform() == "win-arm64" else "Everything64.dll"
_BUNDLED_DLL = (
    os.path.join(os.path.dirname(sys.executable), "lib", _EVERYTHING_DLL)
    if IS_FROZEN
    else os.path.join(os.path.dirname(__file__), "resources", _EVERYTHING_DLL)
)


class _EverythingBackend:
    """Backend using voidtools Everything SDK DLL."""

    _EXE_NAMES = ("Everything64.exe", "Everything32.exe", "Everything.exe")

    def __init__(self):
        self._dll: EverythingLibrary | None = None
        self._available: bool | None = None
        self._buf = ctypes.create_unicode_buffer(520)
        self._size_val = ctypes.c_longlong(0)
        self._exe_path: str | None = None
        self._ipc_error = False

    def _load(self) -> bool:
        if self._available is not None:
            return self._available
        if not os.path.isfile(_BUNDLED_DLL):
            logging.debug("Everything DLL not found: %s", _BUNDLED_DLL)
            self._available = False
            return False
        dll_path = _BUNDLED_DLL
        try:
            self._dll = EverythingLibrary(dll_path)
            self._available = True
            logging.info("Everything SDK loaded: %s", dll_path)
        except Exception as e:
            logging.debug("Failed to load Everything DLL: %s", e)
            self._available = False
        return self._available

    @property
    def available(self) -> bool:
        return self._load()

    def is_running(self) -> bool:
        """True when the Everything app answers; the bundled SDK DLL loads either way."""
        if not self._load() or self._dll is None:
            return False
        running = self._dll.Everything_GetMajorVersion() != 0
        self._ipc_error = not running
        return running

    def search(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        if not self._load():
            return []
        dll = self._dll
        if dll is None:
            return []
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

            if not dll.Everything_QueryW(True):
                err = dll.Everything_GetLastError()
                if err == EVERYTHING_ERROR_IPC:
                    self._ipc_error = True
                    logging.debug("Everything IPC error - is Everything running?")
                return []

            num = min(dll.Everything_GetNumResults(), max_results)
            results: list[dict[str, Any]] = []
            buf = self._buf
            size_val = self._size_val
            for i in range(num):
                dll.Everything_GetResultFullPathNameW(i, buf, 520)
                full_path = buf.value
                is_folder = dll.Everything_IsFolderResult(i)
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
            logging.debug("Everything search error: %s", e)
            return []

    def find_exe(self) -> str | None:
        """Locate the Everything executable from registry or common paths."""
        if self._exe_path is not None:
            return self._exe_path or None
        # Check registry
        for key_path in (EVERYTHING_KEY, EVERYTHING_WOW64_KEY):
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
        # Check Scoop installations
        scoop_dirs = [
            os.environ.get("SCOOP") or os.path.join(os.path.expanduser("~"), "scoop"),
            os.environ.get("SCOOP_GLOBAL") or os.path.join(os.environ.get("PROGRAMDATA", ""), "scoop"),
        ]
        for scoop_root in scoop_dirs:
            if not scoop_root or not os.path.isabs(scoop_root):
                continue
            app_dir = os.path.join(scoop_root, "apps", "everything", "current")
            for name in self._EXE_NAMES:
                candidate = os.path.join(app_dir, name)
                if os.path.isfile(candidate):
                    self._exe_path = candidate
                    return candidate
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
        exe = self.find_exe()
        if not exe:
            return False
        try:
            shell_open(exe, parameters="-startup", show_cmd=SW_HIDE)
            self._ipc_error = False
            return True
        except Exception as e:
            logging.debug("Failed to launch Everything: %s", e)
            return False


class _DiskSearchBackend:
    """Backend using Win32 FindFirstFileExW for full-disk search without index."""

    _SKIP_FOLDERS = frozenset(
        {
            # Windows system
            "windows",
            "boot",
            "recovery",
            "perflogs",
            "config.msi",
            "msocache",
            "documents and settings",
            "$recycle.bin",
            "system volume information",
            "$windows.~bt",
            "$windows.~ws",
            "$sysreset",
            "$winreagent",
            # System data
            "programdata",
            "windows.old",
            # Package/dependency caches
            "node_modules",
            "__pycache__",
            ".git",
            ".svn",
            ".hg",
            ".tox",
            ".nox",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "site-packages",
            "dist-packages",
            ".venv",
            "venv",
            "env",
            ".gradle",
            ".maven",
            ".cargo",
            ".rustup",
            # App caches
            ".cache",
            ".tmp",
            ".temp",
            # IDE/editor
            ".vs",
            ".idea",
            ".vscode",
        }
    )

    _SKIP_FILES = frozenset(
        {
            "pagefile.sys",
            "swapfile.sys",
            "hiberfil.sys",
            "bootmgr",
            "bootmgr.efi",
            "bootnxt",
            "ntldr",
            "ntuser.dat",
            "ntuser.dat.log",
            "ntuser.ini",
            "usrclass.dat",
            "usrclass.dat.log",
            "desktop.ini",
            "thumbs.db",
        }
    )

    def __init__(self):
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    _SKIP_DRIVE_TYPES = frozenset({DRIVE_REMOVABLE, DRIVE_REMOTE, DRIVE_CDROM})

    def _get_drives(self) -> list[str]:
        bitmask = GetLogicalDrives()
        drives: list[str] = []
        for i, letter in enumerate(string.ascii_uppercase):
            if bitmask & (1 << i):
                d = f"{letter}:\\"
                if GetDriveType(d) not in self._SKIP_DRIVE_TYPES and os.path.isdir(d):
                    drives.append(d)
        return drives

    _PROFILE_LOCATIONS = (
        QStandardPaths.StandardLocation.DesktopLocation,
        QStandardPaths.StandardLocation.DownloadLocation,
        QStandardPaths.StandardLocation.DocumentsLocation,
        QStandardPaths.StandardLocation.PicturesLocation,
        QStandardPaths.StandardLocation.MoviesLocation,
        QStandardPaths.StandardLocation.MusicLocation,
    )

    def _profile_folders(self) -> list[str]:
        folders: list[str] = []
        for location in self._PROFILE_LOCATIONS:
            path = QStandardPaths.writableLocation(location)
            if path and os.path.isdir(path):
                folders.append(os.path.normpath(path))
        return folders

    def _search_from(
        self,
        starts: list[str],
        match_fn: Callable[[str], bool],
        results: list[dict[str, Any]],
        max_results: int,
        cancel_event: Event | None = None,
    ) -> None:
        # Breadth-first from every start at once, so a shallow match on any drive comes before a deep one.
        queue = deque(starts)
        visited: set[str] = set()
        data = WIN32_FIND_DATAW()
        while queue:
            path = queue.popleft()
            key = os.path.normcase(path.rstrip("\\"))
            if key in visited:
                continue
            visited.add(key)
            handle = FindFirstFileEx(
                os.path.join(path, "*"),
                FIND_EX_INFO_BASIC,
                ctypes.byref(data),
                0,
                FIND_FIRST_EX_LARGE_FETCH,
            )
            if handle is None:
                continue
            try:
                while True:
                    if cancel_event and cancel_event.is_set():
                        return
                    name = data.cFileName
                    if name not in (".", ".."):
                        attrs = data.dwFileAttributes
                        low = name.lower()
                        if attrs & FILE_ATTRIBUTE_DIRECTORY:
                            if (
                                not (attrs & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM))
                                and low not in self._SKIP_FOLDERS
                                and not low.startswith("$")
                            ):
                                full_path = os.path.join(path, name)
                                queue.append(full_path)
                                if match_fn(low):
                                    results.append({"path": full_path, "name": name, "is_folder": True, "size": 0})
                                    if len(results) >= max_results:
                                        return
                        elif not (attrs & FILE_ATTRIBUTE_SYSTEM) and low not in self._SKIP_FILES and match_fn(low):
                            size = (data.nFileSizeHigh << 32) | data.nFileSizeLow
                            results.append(
                                {"path": os.path.join(path, name), "name": name, "is_folder": False, "size": size}
                            )
                            if len(results) >= max_results:
                                return
                    if not FindNextFile(handle, ctypes.byref(data)):
                        break
            finally:
                FindClose(handle)

    def search(self, query: str, max_results: int = 20, cancel_event: Event | None = None) -> list[dict[str, Any]]:
        if not self._available:
            return []
        # Parse drive/path prefix: "d: foo", "d:\ foo", "c:\users\ bar"
        search_dir = None
        drive_only = re.match(r"^([a-zA-Z]):[\\/]?\s+(.+)$", query)
        path_prefix = re.match(r"^([a-zA-Z]:\\(?:[^\\/]+\\)*)\s+(.+)$", query)
        if path_prefix:
            search_dir = path_prefix.group(1)
            query = path_prefix.group(2)
        elif drive_only:
            search_dir = drive_only.group(1) + ":\\"
            query = drive_only.group(2)

        query_lower = query.lower()
        # Detect glob patterns
        has_wildcard = any(c in query for c in "*?[]")
        match_fn: Callable[[str], bool]
        if has_wildcard:
            match_fn = lambda name: fnmatch.fnmatch(name, query_lower)
        else:
            match_fn = lambda name: query_lower in name
        if search_dir and os.path.isdir(search_dir):
            starts = [search_dir]
        else:
            starts = [*self._profile_folders(), *self._get_drives(), os.path.expanduser("~")]
        results: list[dict[str, Any]] = []
        try:
            self._search_from(starts, match_fn, results, max_results, cancel_event)
        except Exception as e:
            logging.debug("Disk search error: %s", e)
        return results


class _WindowsSearchBackend:
    """Backend using Windows Search indexer via COM (ADODB)."""

    def __init__(self):
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            conn = create_dispatch("ADODB.Connection")
            conn.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
            conn.Close()
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def search(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        try:
            conn = create_dispatch("ADODB.Connection")
            conn.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
            # Strip to safe filename characters only, ADODB doesn't support parameterized queries
            # Convert glob wildcards (* ?) to SQL LIKE equivalents (% _)
            safe_query = re.sub(r"[^\w\s.\-()*?]", "", query)
            if not safe_query:
                conn.Close()
                return []
            has_wildcard = "*" in safe_query or "?" in safe_query
            if has_wildcard:
                like_pattern = safe_query.replace("*", "%").replace("?", "_")
            else:
                like_pattern = f"%{safe_query}%"
            sql = (
                f"SELECT TOP {max_results} System.ItemPathDisplay, System.ItemType, System.Size "
                f"FROM SystemIndex "
                f"WHERE System.FileName LIKE '{like_pattern}' "
                f"AND SCOPE='file:' "
                f"ORDER BY System.Search.Rank DESC"
            )
            rs = conn.Execute(sql)
            results: list[dict[str, Any]] = []
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
            logging.debug("Windows Search error: %s", e)
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
    """Search files and folders using Everything, Windows Search, or full disk search."""

    name = "file_search"
    display_name = "File Search"
    input_placeholder = "Search files and folders..."
    icon = ICON_SEARCH

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._backend_name = (config or {}).get("backend", "auto")
        self._everything = _EverythingBackend()
        self._windows_search = _WindowsSearchBackend()
        self._disk_search = _DiskSearchBackend()
        self._active_backend = None

    def _fallback_backend(self):
        if self._windows_search.available:
            return self._windows_search
        if self._disk_search.available:
            return self._disk_search
        return None

    @staticmethod
    def _backend_label(backend: object) -> str:
        if isinstance(backend, _EverythingBackend):
            return "Everything"
        if isinstance(backend, _WindowsSearchBackend):
            return "Windows Search"
        if isinstance(backend, _DiskSearchBackend):
            return "Disk Search"
        return "unavailable"

    def _get_backend(self):
        if self._backend_name == "auto":
            backend = self._everything if self._everything.is_running() else self._fallback_backend()
            if backend is not self._active_backend:
                self._active_backend = backend
                reason = "" if backend is self._everything else " (Everything is not running)"
                logging.info("File search: using %s backend%s", self._backend_label(backend), reason)
            return backend
        if self._active_backend is not None:
            return self._active_backend
        if self._backend_name == "everything":
            if self._everything.available:
                self._active_backend = self._everything
            else:
                logging.warning("Everything backend requested but not available")
        elif self._backend_name == "index":
            if self._windows_search.available:
                self._active_backend = self._windows_search
            else:
                logging.warning("Index backend requested but not available")
        elif self._backend_name == "disk":
            if self._disk_search.available:
                self._active_backend = self._disk_search
                logging.info("File search: using disk search backend")
            else:
                logging.warning("Disk search backend not available")
        return self._active_backend

    def _search(self, backend: Any, query: str, cancel_event: Event | None) -> list[dict[str, Any]]:
        if isinstance(backend, _DiskSearchBackend):
            return backend.search(query, self.max_results, cancel_event=cancel_event)
        return backend.search(query, self.max_results)

    def get_results(self, text: str, **kwargs: Any) -> list[ProviderResult]:
        cancel_event = kwargs.get("cancel_event")
        query = self.get_query_text(text) if self.prefix and text.strip().startswith(self.prefix) else text.strip()

        if not query:
            backend = self._get_backend()
            if self._backend_name == "everything" and not self._everything.is_running():
                return self._everything_not_running_results()
            backend_label = self._backend_label(backend)
            return [
                ProviderResult(
                    title="Search files and folders",
                    description=f"Backend: {backend_label}",
                    icon_path=ICON_SEARCH,
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
                    icon_path=ICON_SEARCH,
                    provider=self.name,
                )
            ]

        raw = self._search(backend, query, cancel_event)
        if not raw and isinstance(backend, _EverythingBackend) and backend.has_ipc_error:
            if self._backend_name != "auto":
                return self._everything_not_running_results()
            # Everything quit after the check above; auto searches with the fallback instead.
            backend = self._get_backend()
            raw = self._search(backend, query, cancel_event) if backend else []

        results: list[ProviderResult] = []
        show_path = self.config.get("show_path", True)
        home = os.path.expanduser("~")
        for item in raw:
            path = item["path"]
            name = item["name"]
            is_folder = item["is_folder"]
            size = item["size"]
            if show_path:
                parent = os.path.dirname(path)
                # Shorten home directory prefix to ~
                if parent.startswith(home):
                    parent = "~" + parent[len(home) :]
                size_str = _format_size(size) if size and not is_folder else ""
                description = f"{size_str} - {parent}" if size_str else parent
            else:
                description = ""
            preview = self._build_file_preview(path, name, is_folder, size)
            results.append(
                ProviderResult(
                    title=name,
                    description=description,
                    icon_path=_get_file_icon(name, is_folder),
                    provider=self.name,
                    action_data={"path": path, "is_folder": is_folder},
                    preview=preview,
                )
            )
        return results

    def _build_file_preview(self, path: str, name: str, is_folder: bool, size: int) -> dict[str, Any]:
        """Build a toggleable preview dict with file/folder metadata."""
        metadata: list[list[str]] = []
        try:
            st = os.stat(path)
            if not is_folder:
                metadata.append(["File Size", _format_size(st.st_size) or _format_size(size)])
            metadata.append(["Created", datetime.datetime.fromtimestamp(st.st_birthtime).strftime("%Y-%m-%d %H:%M")])
            metadata.append(["Last Modified", datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")])
        except OSError:
            if size and not is_folder:
                metadata.append(["File Size", _format_size(size)])
        return {
            "kind": "text",
            "icon": _get_file_icon(name, is_folder),
            "title": name,
            "subtitle": path,
            "metadata": metadata,
        }

    def execute(self, result: ProviderResult) -> bool:
        action = result.action_data.get("action", "")
        if action == "launch_everything":
            self._everything.launch_everything()
            self._active_backend = None  # Reset backend selection
            self._wait_for_everything_ipc()
            return False  # Keep popup open
        if action == "install_everything":
            shell_open("https://www.voidtools.com/")
            return True
        path = result.action_data.get("path", "")
        if not path or not os.path.exists(path):
            return False
        try:
            shell_open(path)
            return True
        except Exception as e:
            logging.error("Failed to open: %s", e)
            return False

    def get_context_menu_actions(self, result: ProviderResult) -> list[ProviderMenuAction]:
        path = result.action_data.get("path", "")
        if not path:
            return []

        actions = [
            ProviderMenuAction(id="reveal_in_explorer", label="Reveal in Explorer"),
            ProviderMenuAction(id="copy_path", label="Copy path"),
        ]

        if not bool(result.action_data.get("is_folder", False)):
            actions.append(ProviderMenuAction(id="copy_file", label="Copy file"))

        return actions

    def execute_context_menu_action(self, action_id: str, result: ProviderResult) -> ProviderMenuActionResult:
        path = result.action_data.get("path", "")
        is_folder = bool(result.action_data.get("is_folder", False))
        if not path or not os.path.exists(path):
            return ProviderMenuActionResult()

        if action_id == "reveal_in_explorer":
            try:
                shell_open("explorer.exe", parameters=f'/select, "{path}"')
            except Exception as e:
                logging.debug("Failed to reveal in Explorer: %s", e)
            return ProviderMenuActionResult(close_popup=True)

        if action_id == "copy_path":
            clipboard = QGuiApplication.clipboard()
            if clipboard:
                clipboard.setText(path)
            return ProviderMenuActionResult()

        if action_id == "copy_file" and not is_folder:
            try:
                self._copy_file_to_clipboard(path)
            except Exception as e:
                logging.debug("Failed to copy file to clipboard: %s", e)
            return ProviderMenuActionResult()

        return ProviderMenuActionResult()

    @staticmethod
    def _copy_file_to_clipboard(path: str):
        """Place a file on the clipboard via CF_HDROP, like Explorer's Copy."""
        # DROPFILES header (20 bytes): pFiles, pt.x, pt.y, fNC, fWide
        dropfiles_fmt = "IiiII"
        dropfiles_size = struct.calcsize(dropfiles_fmt)
        header = struct.pack(dropfiles_fmt, dropfiles_size, 0, 0, 0, 1)

        # File path encoded as UTF-16LE, null-terminated, then extra null to end list
        file_bytes = path.encode("utf-16-le") + b"\x00\x00\x00\x00"
        data = header + file_bytes

        hMem = GlobalAlloc(GHND, len(data))
        if not hMem:
            raise ctypes.WinError(GetLastError())

        pMem = GlobalLock(hMem)
        if not pMem:
            GlobalFree(hMem)
            raise ctypes.WinError(GetLastError())

        ctypes.memmove(pMem, data, len(data))
        GlobalUnlock(hMem)

        if not OpenClipboard(None):
            GlobalFree(hMem)
            raise ctypes.WinError(GetLastError())

        try:
            EmptyClipboard()
            if not SetClipboardData(CF_HDROP, hMem):
                GlobalFree(hMem)
                raise ctypes.WinError(GetLastError())
        finally:
            CloseClipboard()

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
        if self._everything.is_running():
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
        exe = self._everything.find_exe()
        if exe:
            return [
                ProviderResult(
                    title="Everything is not running",
                    description="Click to launch Everything",
                    icon_path=ICON_WARNING,
                    provider=self.name,
                    action_data={"action": "launch_everything"},
                )
            ]
        return [
            ProviderResult(
                title="Everything is not installed",
                description="Click to download from voidtools.com",
                icon_path=ICON_WARNING,
                provider=self.name,
                action_data={"action": "install_everything"},
            )
        ]
