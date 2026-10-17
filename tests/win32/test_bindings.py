# pyright: reportPrivateUsage=false

import ctypes
import os
import sys
import uuid
from collections.abc import Callable, Iterator
from ctypes import POINTER, byref
from ctypes.wintypes import UINT
from pathlib import Path
from typing import Any

import comtypes  # pyright: ignore[reportMissingTypeStubs]
import pytest
from comtypes.client import CreateObject  # pyright: ignore[reportMissingTypeStubs]
from comtypes.persist import IPersistFile  # pyright: ignore[reportMissingTypeStubs]
from comtypes.shelllink import IShellLinkW, ShellLink  # pyright: ignore[reportMissingTypeStubs]

from core.utils.win32.aumid import get_aumid_for_process, get_aumid_from_shortcut
from core.utils.win32.bindings.advapi32 import (
    OpenProcessToken,
    enable_token_privilege,
    get_current_user_sid,
    get_token_group_sids,
    get_token_user_sid,
)
from core.utils.win32.bindings.kernel32 import (
    CloseHandle,
    CreateFile,
    GetApplicationUserModelId,
    GetCurrentProcess,
    GetCurrentThreadId,
    GetLastError,
    GetModuleHandle,
    GetPackageFullName,
    OpenProcess,
    _query_process_string,
    snapshot_processes,
)
from core.utils.win32.bindings.ole32 import CoInitialize
from core.utils.win32.bindings.shell32 import (
    SHGetPropertyStoreFromParsingName,
    get_shell_item_icon_location,
    get_string_property,
    read_shortcut,
)
from core.utils.win32.bindings.user32 import (
    CreateWindowEx,
    DefWindowProc,
    DestroyWindow,
    GetMonitorInfo,
    GetParent,
    GetWindowText,
    IsWindow,
    MonitorFromRect,
    enum_child_windows,
    enum_display_monitors,
    enum_windows,
    get_window_thread_process_id,
    user32,
)
from core.utils.win32.bindings.version import get_version_strings
from core.utils.win32.constants import (
    ERROR_INSUFFICIENT_BUFFER,
    GPS_READWRITE,
    INVALID_HANDLE_VALUE,
    OPEN_EXISTING,
    PROCESS_QUERY_LIMITED_INFORMATION,
    SE_SHUTDOWN_NAME,
    TOKEN_ADJUST_PRIVILEGES,
    TOKEN_QUERY,
    VT_LPWSTR,
    WS_CHILD,
    WS_POPUP,
    PKEY_AppUserModel_ID,
)
from core.utils.win32.structs import GUID, PROPERTYKEY, PROPVARIANT, WNDCLASS, WNDPROC
from core.utils.win32.utils import get_process_path, get_window_rect, is_window_maximized

APPMODEL_ERROR_NO_PACKAGE = 15700
ERROR_PATH_NOT_FOUND = 3
ERROR_CLASS_ALREADY_EXISTS = 1410
WS_MAXIMIZE = 0x01000000
EVERYONE_SID = "S-1-1-0"
CONTROL_PANEL = "shell:::{21EC2020-3AEA-1069-A2DD-08002B30309D}"
KERNEL32_DLL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "kernel32.dll")
PKEY_SIZE = PROPERTYKEY(GUID.from_string("B725F130-47EF-101A-A5F1-02608C9EEBAC"), 12)


def test_snapshot_processes_includes_this_process():
    entries = {entry.pid: entry for entry in snapshot_processes()}
    me = entries[os.getpid()]
    assert me.parent_pid == os.getppid()
    assert me.exe.lower() == os.path.basename(get_process_path(os.getpid()) or "").lower()


def _fake_query(value: str, *, first: int = ERROR_INSUFFICIENT_BUFFER, second: int = 0) -> Callable[..., int]:
    """Answers like GetPackageFullName: the first call reports the length, the second fills the buffer."""

    def query(_process: int, length: Any, buffer: Any) -> int:
        size = ctypes.cast(length, POINTER(UINT)).contents
        if buffer is None:
            size.value = len(value) + 1 if first == ERROR_INSUFFICIENT_BUFFER else 0
            return first
        buffer.value = value
        return second

    return query


def test_last_error_survives_win32_calls_outside_the_bindings(tmp_path: Path):
    missing = str(tmp_path / "missing" / "file.txt")
    assert CreateFile(missing, 0, 0, None, OPEN_EXISTING, 0) == INVALID_HANDLE_VALUE
    ctypes.WinDLL("kernel32").SetLastError(0)
    assert GetLastError() == ERROR_PATH_NOT_FOUND


def test_process_string_query_reads_the_second_call():
    query = _fake_query("Microsoft.WindowsCalculator_11.2405.2.0_x64__8wekyb3d8bbwe")
    assert _query_process_string(query, 0) == "Microsoft.WindowsCalculator_11.2405.2.0_x64__8wekyb3d8bbwe"


@pytest.mark.parametrize(
    "query",
    [
        _fake_query("", first=APPMODEL_ERROR_NO_PACKAGE),
        _fake_query("Some.Package", second=ERROR_INSUFFICIENT_BUFFER),
        _fake_query(""),
    ],
    ids=["unpackaged", "second call fails", "empty"],
)
def test_process_string_query_returns_none(query: Callable[..., int]):
    assert _query_process_string(query, 0) is None


def test_unpackaged_process_has_no_package_or_aumid():
    if "WindowsApps" in sys.base_prefix:
        pytest.skip("Python from the Microsoft Store runs as a packaged app")
    process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, os.getpid())
    assert process
    try:
        assert GetPackageFullName(process) is None
        assert GetApplicationUserModelId(process) is None
    finally:
        CloseHandle(process)
    assert get_aumid_for_process(os.getpid()) is None
    assert get_aumid_for_process(0) is None


@pytest.mark.parametrize("text", ["886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99", "{9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3}"])
def test_guid_from_string_matches_the_windows_layout(text: str):
    guid = GUID.from_string(text)
    reference = uuid.UUID(text)
    assert bytes(guid) == reference.bytes_le
    assert bytes(guid) == bytes(comtypes.GUID("{" + str(reference) + "}"))
    assert guid.to_uuid() == reference
    assert str(guid) == str(reference)


def _make_shortcut(path: Path) -> None:
    link = CreateObject(ShellLink, interface=IShellLinkW)
    link.SetPath(sys.executable)
    link.QueryInterface(IPersistFile).Save(str(path), True)


def _set_aumid(path: Path, aumid: str) -> None:
    store = SHGetPropertyStoreFromParsingName(str(path), GPS_READWRITE)
    assert store is not None
    value = PROPVARIANT()
    value.vt = VT_LPWSTR
    # SetValue copies the string, so this PROPVARIANT must not go through PropVariantClear
    value.pwszVal = aumid
    store.SetValue(PKEY_AppUserModel_ID, value)
    store.Commit()


def test_shortcut_aumid_round_trip(tmp_path: Path):
    CoInitialize()
    shortcut = tmp_path / "app.lnk"
    _make_shortcut(shortcut)
    assert get_aumid_from_shortcut(str(shortcut)) is None
    _set_aumid(shortcut, "Yasb.Tests.Shortcut")
    assert get_aumid_from_shortcut(str(shortcut)) == "Yasb.Tests.Shortcut"


def test_string_property_of_another_type_is_none(tmp_path: Path):
    CoInitialize()
    path = tmp_path / "data.bin"
    path.write_bytes(b"x" * 10)
    store = SHGetPropertyStoreFromParsingName(str(path))
    assert store is not None
    assert get_string_property(store, PKEY_SIZE) is None


def test_property_store_of_a_missing_file_is_none(tmp_path: Path):
    CoInitialize()
    assert SHGetPropertyStoreFromParsingName(str(tmp_path / "missing.lnk")) is None
    assert get_aumid_from_shortcut(str(tmp_path / "missing.lnk")) is None


@pytest.fixture(scope="module")
def window_class() -> Iterator[str]:
    name = "YasbBindingsTestWindow"
    proc = WNDPROC(DefWindowProc)
    wc = WNDCLASS()
    wc.lpfnWndProc = proc
    wc.hInstance = GetModuleHandle(None)
    wc.lpszClassName = name
    assert user32.RegisterClassW(byref(wc)) or GetLastError() == ERROR_CLASS_ALREADY_EXISTS
    yield name


@pytest.fixture
def make_window(window_class: str) -> Iterator[Callable[..., int]]:
    created: list[int] = []

    def make(style: int = WS_POPUP, title: str = "YASB bindings test", parent: int | None = None) -> int:
        hwnd = CreateWindowEx(
            0, window_class, title, style, 10, 20, 300, 200, parent, None, GetModuleHandle(None), None
        )
        assert hwnd
        created.append(hwnd)
        return hwnd

    yield make
    for hwnd in reversed(created):
        if IsWindow(hwnd):
            DestroyWindow(hwnd)


def test_window_text_is_read_in_full(make_window: Callable[..., int]):
    title = "YASB " + "x" * 600
    assert GetWindowText(make_window(title=title)) == title


def test_window_thread_and_process_are_this_one(make_window: Callable[..., int]):
    assert get_window_thread_process_id(make_window()) == (GetCurrentThreadId(), os.getpid())


def test_enum_windows_lists_top_level_windows_and_their_children(make_window: Callable[..., int]):
    parent = make_window()
    child = make_window(style=WS_CHILD, parent=parent)

    assert parent in enum_windows()
    assert child not in enum_windows()
    assert enum_child_windows(parent) == [child]
    assert GetParent(child) == parent
    assert GetParent(parent) == 0


@pytest.mark.parametrize(("style", "maximized"), [(WS_POPUP, False), (WS_POPUP | WS_MAXIMIZE, True)])
def test_window_maximized_state(make_window: Callable[..., int], style: int, maximized: bool):
    assert is_window_maximized(make_window(style=style)) is maximized


def test_window_rect(make_window: Callable[..., int]):
    assert get_window_rect(make_window()) == {"x": 10, "y": 20, "width": 300, "height": 200}


def test_closed_window(make_window: Callable[..., int]):
    hwnd = make_window()
    DestroyWindow(hwnd)

    assert GetWindowText(hwnd) == ""
    assert get_window_thread_process_id(hwnd) == (0, 0)
    assert GetParent(hwnd) == 0
    with pytest.raises(OSError):
        is_window_maximized(hwnd)
    with pytest.raises(OSError):
        get_window_rect(hwnd)


def test_version_strings_of_a_system_dll():
    values = get_version_strings(KERNEL32_DLL, ("FileDescription", "ProductName", "NoSuchVersionString"))

    assert values["FileDescription"]
    assert values["ProductName"]
    assert "NoSuchVersionString" not in values


def test_version_strings_of_a_file_without_version_info(tmp_path: Path):
    plain = tmp_path / "plain.txt"
    plain.write_text("no version info")

    assert get_version_strings(str(plain), ("FileDescription",)) == {}


def test_monitors_describe_themselves():
    for hmonitor, rect in enum_display_monitors():
        info = GetMonitorInfo(hmonitor)

        assert info is not None
        assert (info.rcMonitor.left, info.rcMonitor.top, info.rcMonitor.right, info.rcMonitor.bottom) == rect
        assert info.szDevice
        assert MonitorFromRect(rect) == hmonitor


@pytest.fixture
def token() -> Iterator[int]:
    handle = OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY | TOKEN_ADJUST_PRIVILEGES)
    assert handle is not None
    yield handle
    CloseHandle(handle)


def test_token_user_is_the_current_user(token: int):
    sid = get_token_user_sid(token)

    assert sid is not None
    assert sid.startswith("S-1-5-")
    assert get_current_user_sid() == sid


def test_token_groups_include_everyone(token: int):
    assert EVERYONE_SID in get_token_group_sids(token)


def test_enable_token_privilege(token: int):
    assert enable_token_privilege(token, SE_SHUTDOWN_NAME) is True
    assert enable_token_privilege(token, "SeNoSuchPrivilege") is False


def test_read_shortcut(tmp_path: Path):
    CoInitialize()
    path = tmp_path / "app.lnk"
    link = CreateObject(ShellLink, interface=IShellLinkW)
    link.SetPath(sys.executable)
    link.SetArguments("--flag value")
    link.SetDescription("YASB test shortcut")
    link.SetIconLocation(KERNEL32_DLL, 3)
    link.SetWorkingDirectory(str(tmp_path))
    link.QueryInterface(IPersistFile).Save(str(path), True)

    shortcut = read_shortcut(str(path))

    assert shortcut is not None
    assert Path(shortcut.target) == Path(sys.executable)
    assert shortcut.arguments == "--flag value"
    assert shortcut.description == "YASB test shortcut"
    assert (shortcut.icon_file, shortcut.icon_index) == (KERNEL32_DLL, 3)
    assert shortcut.working_directory == str(tmp_path)


def test_read_shortcut_of_a_missing_file(tmp_path: Path):
    CoInitialize()
    assert read_shortcut(str(tmp_path / "missing.lnk")) is None


def test_shell_item_icon_location():
    CoInitialize()
    location = get_shell_item_icon_location(CONTROL_PANEL)

    assert location is not None
    icon_file, _ = location
    assert icon_file.lower().endswith(".dll")


def test_shell_item_icon_location_of_a_missing_item(tmp_path: Path):
    CoInitialize()
    assert get_shell_item_icon_location(str(tmp_path / "missing")) is None


def test_shell_item_icon_location_of_a_file_without_its_own_icon(tmp_path: Path):
    CoInitialize()
    text_file = tmp_path / "notes.txt"
    text_file.write_text("no icon of its own")

    assert get_shell_item_icon_location(str(text_file)) is None
