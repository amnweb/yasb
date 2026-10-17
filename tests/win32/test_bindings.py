# pyright: reportPrivateUsage=false

import ctypes
import os
import sys
import uuid
from collections.abc import Callable, Iterator
from ctypes import POINTER, byref
from ctypes.wintypes import UINT, WORD
from functools import cmp_to_key
from pathlib import Path
from typing import Any

import comtypes  # pyright: ignore[reportMissingTypeStubs]
import pytest
from comtypes.client import CreateObject  # pyright: ignore[reportMissingTypeStubs]
from comtypes.persist import IPersistFile  # pyright: ignore[reportMissingTypeStubs]
from comtypes.shelllink import IShellLinkW, ShellLink  # pyright: ignore[reportMissingTypeStubs]

from core.utils.win32.aumid import get_aumid_for_process, get_aumid_from_shortcut
from core.utils.win32.bindings.advapi32 import (
    GetUserName,
    OpenProcessToken,
    enable_token_privilege,
    get_current_user_sid,
    get_token_group_sids,
    get_token_user_sid,
    sid_to_string,
)
from core.utils.win32.bindings.kernel32 import (
    CloseHandle,
    CreateFile,
    FindClose,
    FindFirstFileEx,
    FindNextFile,
    GetApplicationUserModelId,
    GetCurrentProcess,
    GetCurrentThreadId,
    GetDiskFreeSpaceEx,
    GetLastError,
    GetModuleHandle,
    GetPackageFullName,
    OpenProcess,
    _query_process_string,
    get_volume_label,
    snapshot_processes,
)
from core.utils.win32.bindings.ole32 import CoInitialize
from core.utils.win32.bindings.secur32 import GetUserNameEx
from core.utils.win32.bindings.shell32 import (
    SHGetPropertyStoreFromParsingName,
    get_shell_item_icon_location,
    get_string_property,
    read_shortcut,
)
from core.utils.win32.bindings.shlwapi import SHLoadIndirectString, StrCmpLogical
from core.utils.win32.bindings.user32 import (
    CreateWindowEx,
    DefWindowProc,
    DestroyWindow,
    EnumDisplayDevices,
    FindWindowEx,
    GetMonitorInfo,
    GetParent,
    GetSystemMetrics,
    GetWindow,
    GetWindowText,
    IsWindow,
    MonitorFromRect,
    MonitorFromWindow,
    enum_child_windows,
    enum_display_monitors,
    enum_windows,
    get_window_thread_process_id,
    user32,
)
from core.utils.win32.bindings.version import GetFileVersionInfo, VerQueryValue, get_version_strings
from core.utils.win32.constants import (
    ERROR_INSUFFICIENT_BUFFER,
    FIND_EX_INFO_BASIC,
    FIND_FIRST_EX_LARGE_FETCH,
    GPS_READWRITE,
    GW_OWNER,
    INVALID_HANDLE_VALUE,
    OPEN_EXISTING,
    PROCESS_QUERY_LIMITED_INFORMATION,
    SE_SHUTDOWN_NAME,
    SM_CXICON,
    TOKEN_ADJUST_PRIVILEGES,
    TOKEN_QUERY,
    VT_LPWSTR,
    WS_CHILD,
    WS_POPUP,
    PKEY_AppUserModel_ID,
)
from core.utils.win32.structs import GUID, PROPERTYKEY, PROPVARIANT, WIN32_FIND_DATAW, WNDCLASS, WNDPROC
from core.utils.win32.utils import get_process_path, get_window_rect, is_window_maximized

APPMODEL_ERROR_NO_PACKAGE = 15700
ERROR_PATH_NOT_FOUND = 3
ERROR_CLASS_ALREADY_EXISTS = 1410
WS_MAXIMIZE = 0x01000000
MONITOR_DEFAULTTONEAREST = 2
NAME_SAM_COMPATIBLE = 2
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


def _list_directory(path: Path) -> dict[str, int]:
    data = WIN32_FIND_DATAW()
    handle = FindFirstFileEx(str(path / "*"), FIND_EX_INFO_BASIC, byref(data), 0, FIND_FIRST_EX_LARGE_FETCH)
    assert handle is not None
    found: dict[str, int] = {}
    try:
        while True:
            found[data.cFileName] = (data.nFileSizeHigh << 32) | data.nFileSizeLow
            if not FindNextFile(handle, byref(data)):
                break
    finally:
        assert FindClose(handle)
    return found


def test_find_first_file_lists_a_directory(tmp_path: Path):
    (tmp_path / "a.txt").write_bytes(b"12345")
    (tmp_path / "sub").mkdir()
    found = _list_directory(tmp_path)
    assert set(found) == {".", "..", "a.txt", "sub"}
    assert found["a.txt"] == 5


def test_find_first_file_returns_none_for_a_missing_directory(tmp_path: Path):
    data = WIN32_FIND_DATAW()
    assert FindFirstFileEx(str(tmp_path / "missing" / "*"), FIND_EX_INFO_BASIC, byref(data), 0, 0) is None


def test_version_info_of_a_system_dll():
    block = GetFileVersionInfo(KERNEL32_DLL)
    assert block is not None
    translation = VerQueryValue(block, "\\VarFileInfo\\Translation")
    assert translation is not None
    assert translation[1] >= 4
    lang, codepage = ctypes.cast(translation[0], POINTER(WORD * 2)).contents
    company = VerQueryValue(block, f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\CompanyName")
    assert company is not None
    assert "Microsoft" in ctypes.wstring_at(company[0])
    assert VerQueryValue(block, "\\StringFileInfo\\00000000\\NoSuchValue") is None


def test_version_info_of_a_file_without_one(tmp_path: Path):
    path = tmp_path / "plain.txt"
    path.write_text("no version resource here")
    assert GetFileVersionInfo(str(path)) is None


def test_load_indirect_string():
    assert SHLoadIndirectString("@%SystemRoot%\\system32\\shell32.dll,-21769")
    assert SHLoadIndirectString("plain text") == "plain text"
    assert SHLoadIndirectString("@yasb-no-such.dll,-1") is None


def test_str_cmp_logical_orders_numbers_by_value():
    names = ["img10.png", "img2.png", "IMG1.png", "img1.png"]
    assert sorted(names, key=cmp_to_key(StrCmpLogical)) == ["IMG1.png", "img1.png", "img2.png", "img10.png"]
    assert StrCmpLogical("2", "10") < 0
    assert StrCmpLogical("b", "a") > 0
    assert StrCmpLogical("abc", "ABC") == 0


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


def test_owned_window_reports_its_owner(make_window: Callable[..., int]):
    owner = make_window()
    owned = make_window(parent=owner)

    assert GetWindow(owned, GW_OWNER) == owner
    assert GetWindow(owner, GW_OWNER) == 0


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


def test_find_window_ex_without_a_match_is_zero():
    assert FindWindowEx(0, 0, "YasbNoSuchWindowClass", None) == 0


def test_version_strings_of_a_system_dll():
    values = get_version_strings(KERNEL32_DLL, ("FileDescription", "ProductName", "NoSuchVersionString"))

    assert values["FileDescription"]
    assert values["ProductName"]
    assert "NoSuchVersionString" not in values


def test_version_strings_of_a_file_without_version_info(tmp_path: Path):
    plain = tmp_path / "plain.txt"
    plain.write_text("no version info")

    assert get_version_strings(str(plain), ("FileDescription",)) == {}


def test_disk_free_space_of_a_folder(tmp_path: Path):
    space = GetDiskFreeSpaceEx(str(tmp_path))

    assert space is not None
    free_to_caller, total, free = space
    assert 0 < free_to_caller <= total
    assert 0 < free <= total


def test_disk_free_space_and_label_of_a_missing_folder(tmp_path: Path):
    missing = str(tmp_path / "missing" / "")

    assert GetDiskFreeSpaceEx(missing) is None
    assert get_volume_label(missing) is None


def test_volume_label_of_the_system_drive():
    assert isinstance(get_volume_label(os.environ.get("SystemDrive", "C:") + "\\"), str)


def test_monitors_describe_themselves():
    for hmonitor, rect in enum_display_monitors():
        info = GetMonitorInfo(hmonitor)

        assert info is not None
        assert (info.rcMonitor.left, info.rcMonitor.top, info.rcMonitor.right, info.rcMonitor.bottom) == rect
        assert info.szDevice
        assert MonitorFromRect(rect) == hmonitor


def test_missing_monitor():
    assert GetMonitorInfo(0) is None
    assert MonitorFromRect((-99999, -99999, -99990, -99990)) is None


def test_window_is_on_its_nearest_monitor(make_window: Callable[..., int]):
    if not enum_display_monitors():
        pytest.skip("no monitors")
    hmonitor = MonitorFromWindow(make_window(), MONITOR_DEFAULTTONEAREST)

    assert hmonitor in [monitor for monitor, _ in enum_display_monitors()]


def test_display_devices_end_with_none():
    devices = [EnumDisplayDevices(None, index) for index in range(64)]

    assert devices[0] is not None
    assert devices[-1] is None
    for device in devices:
        if device is None:
            break
        assert device.DeviceName.startswith("\\\\.\\")


def test_system_metrics():
    assert GetSystemMetrics(SM_CXICON) > 0


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


def test_token_of_an_invalid_process_handle_is_none():
    assert OpenProcessToken(0, TOKEN_QUERY) is None


def test_sid_to_string_of_no_sid_is_none():
    assert sid_to_string(None) is None


def test_enable_token_privilege(token: int):
    assert enable_token_privilege(token, SE_SHUTDOWN_NAME) is True
    assert enable_token_privilege(token, "SeNoSuchPrivilege") is False


def test_user_names_agree():
    name = GetUserName()
    sam_name = GetUserNameEx(NAME_SAM_COMPATIBLE)

    assert name
    assert sam_name is not None
    assert sam_name.lower().endswith("\\" + name.lower())


def test_user_name_in_an_unknown_format_is_none():
    assert GetUserNameEx(99) is None


def test_read_shortcut(tmp_path: Path):
    CoInitialize()
    path = tmp_path / "app.lnk"
    link = CreateObject(ShellLink, interface=IShellLinkW)
    link.SetPath(sys.executable)
    link.SetArguments("--flag value")
    link.SetDescription("YASB test shortcut")
    link.SetIconLocation(KERNEL32_DLL, 3)
    link.QueryInterface(IPersistFile).Save(str(path), True)

    shortcut = read_shortcut(str(path))

    assert shortcut is not None
    assert Path(shortcut.target) == Path(sys.executable)
    assert shortcut.arguments == "--flag value"
    assert shortcut.description == "YASB test shortcut"
    assert (shortcut.icon_file, shortcut.icon_index) == (KERNEL32_DLL, 3)


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
