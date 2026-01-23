"""Window context helpers for the taskbar pin manager."""

import ctypes
import logging
from ctypes import POINTER, byref, create_string_buffer
from ctypes.wintypes import ULONG
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import unquote

import win32com.client

from core.utils.win32.aumid import get_aumid_for_window
from core.utils.win32.bindings.kernel32 import kernel32
from core.utils.win32.bindings.ntdll import ProcessCommandLineInformation, ntdll
from core.utils.win32.constants import PROCESS_QUERY_LIMITED_INFORMATION
from core.utils.win32.structs import UNICODE_STRING
from settings import DEBUG


@dataclass
class WindowContext:
    """
    Snapshot of the runtime state for a window we might pin.

    For Explorer windows, explorer_path contains:
    - File system paths (e.g., 'C:\\Users\\Documents')
    - Shell: URLs for special folders (e.g., 'shell:RecycleBinFolder')
    - CLSID paths for special folders (e.g., '::{645FF040-5081-101B-9F08-00AA002F954E}')

    Note: CLSID paths are language-independent and work across all Windows locales.
    """

    hwnd: int
    exe_path: str | None
    aumid: str | None
    base_pid: int | None
    process_name: str
    window_title: str
    is_explorer: bool
    explorer_path: str | None = None
    command_line: str | None = None
    command_line_loaded: bool = False


@lru_cache(maxsize=1)
def _get_shell_application():
    """Get the Shell.Application COM automation object."""
    return win32com.client.Dispatch("Shell.Application")


def collect_window_context(hwnd: int, window_data: dict[str, Any]) -> WindowContext | None:
    """Build a context object for the supplied window handle."""

    process_name = window_data.get("process_name", "")
    window_title = window_data.get("title", "")
    exe_path = window_data.get("process_path")
    aumid = get_aumid_for_window(hwnd)
    base_pid = window_data.get("process_pid")

    is_explorer = bool(exe_path and "explorer.exe" in exe_path.lower())
    explorer_path: str | None = None

    if is_explorer:
        try:
            shell_app = _get_shell_application()
            for window in shell_app.Windows():
                try:
                    if hasattr(window, "HWND") and window.HWND == hwnd:
                        location = window.LocationURL
                        if location:
                            if location.startswith("file:///"):
                                # Regular file system folder
                                explorer_path = unquote(location[8:]).replace("/", "\\")
                            else:
                                # Special shell folder (Recycle Bin, This PC, etc.)
                                # Use the LocationURL directly as the identifier
                                explorer_path = location
                            break
                except Exception as exc:
                    if DEBUG:
                        logging.debug(f"Error getting LocationURL for explorer window {hwnd}: {exc}")
                    continue
        except Exception as exc:
            if DEBUG:
                logging.debug(f"Error accessing Shell.Application for explorer window {hwnd}: {exc}")
            explorer_path = None

        # Fallback: If we couldn't get LocationURL but this is an explorer window,
        # try to detect special folders using Shell namespace GUIDs (language-independent)
        if explorer_path is None and hwnd:
            try:
                # Try to get the folder CLSID/GUID for special folders via Document interface
                shell_windows = win32com.client.Dispatch("Shell.Application").Windows()
                for window in shell_windows:
                    try:
                        if window.HWND == hwnd:
                            # Access the folder path which may contain CLSID for special folders
                            folder_path = window.Document.Folder.Self.Path
                            if folder_path and "::{" in folder_path:
                                # This is a CLSID path (e.g., Recycle Bin), use it directly
                                explorer_path = folder_path
                                break
                    except (AttributeError, Exception):
                        # Window doesn't have Document/Folder/Self, or COM error - skip it
                        continue
            except Exception as exc:
                if DEBUG:
                    logging.debug(f"Error detecting special folder for hwnd {hwnd}: {exc}")

    return WindowContext(
        hwnd=hwnd,
        exe_path=exe_path,
        aumid=aumid,
        base_pid=base_pid,
        process_name=process_name,
        window_title=window_title,
        is_explorer=is_explorer,
        explorer_path=explorer_path,
    )


def ensure_command_line(context: WindowContext) -> str | None:
    """Ensure the command line is populated for the window context."""

    if context.command_line_loaded:
        return context.command_line

    context.command_line_loaded = True
    if context.base_pid:
        context.command_line = _get_process_command_line(context.base_pid)
    else:
        context.command_line = None
    return context.command_line


def _get_process_command_line(pid: int) -> str | None:
    """Return the command line for a process, if available."""
    try:
        hProcess = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if hProcess:
            try:
                bufLen = ULONG(0)
                ntdll.NtQueryInformationProcess(hProcess, ProcessCommandLineInformation, None, 0, byref(bufLen))

                if bufLen.value > 0:
                    buffer = create_string_buffer(bufLen.value)
                    status = ntdll.NtQueryInformationProcess(
                        hProcess, ProcessCommandLineInformation, buffer, bufLen.value, byref(bufLen)
                    )

                    if status >= 0:
                        unicode_str = ctypes.cast(buffer, POINTER(UNICODE_STRING)).contents
                        if unicode_str.Buffer:
                            return unicode_str.Buffer
            finally:
                kernel32.CloseHandle(hProcess)
    except Exception as exc:
        if DEBUG:
            logging.debug("NtQueryInformationProcess failed for PID %s: %s", pid, exc)

    # Fallback to WMI if NtQueryInformationProcess fails
    try:
        wmi = win32com.client.GetObject("winmgmts:")
        processes = wmi.ExecQuery(f"SELECT CommandLine FROM Win32_Process WHERE ProcessId = {pid}")
        for process in processes:
            if process.CommandLine:
                return process.CommandLine
    except Exception as exc:
        if DEBUG:
            logging.debug("WMI fallback failed for PID %s: %s", pid, exc)

    return None
