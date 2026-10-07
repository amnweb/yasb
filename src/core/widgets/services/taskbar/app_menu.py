"""
Context menu utilities for taskbar widget.

This module provides context menu functionality for taskbar buttons,
including app-specific menu items for File Explorer, Recycle Bin, Edge, Firefox, VS Code, and Windows Terminal.
"""

import json
import logging
import os
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

import pythoncom
import win32gui
from humanize import naturalsize
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtWidgets import QMenu
from win32comext.shell import shell, shellcon

from core.utils.win32.constants import KnownCLSID
from core.utils.win32.utils import apply_qmenu_style
from core.utils.win32.window_actions import close_application

if TYPE_CHECKING:
    from collections.abc import Iterable

    from _win32typing import PyIDL  # pyright: ignore[reportMissingModuleSource]

    from core.widgets.services.recycle_bin.recycle_bin_monitor import EmptyBinThread
    from core.widgets.yasb.taskbar import TaskbarWidget

# Global reference to keep thread alive
_empty_bin_thread_ref: EmptyBinThread | None = None


class LaunchCallback(Protocol):
    def __call__(self, unique_id_or_hwnd: int | str, extra_arguments: str = "") -> None: ...


def _launch(on_launch: LaunchCallback, target: str, extra_arguments: str, checked: bool = False) -> None:
    on_launch(target, extra_arguments=extra_arguments)


def _add_launch_action(
    menu: QMenu, text: str, on_launch: LaunchCallback, target: str, extra_arguments: str = ""
) -> None:
    action = QAction(text, menu)
    menu.addAction(action)
    action.triggered.connect(partial(_launch, on_launch, target, extra_arguments))


def _empty_recycle_bin() -> None:
    """Empty the Windows Recycle Bin using RecycleBinMonitor async method."""
    global _empty_bin_thread_ref

    try:
        from core.widgets.services.recycle_bin.recycle_bin_monitor import RecycleBinMonitor

        monitor = RecycleBinMonitor.get_instance()
        # Use async version with confirmation, keep global reference to prevent garbage collection
        signal, thread = monitor.empty_recycle_bin_async(show_confirmation=True, show_progress=True)
        _empty_bin_thread_ref = thread  # Keep thread alive

        # Clear reference when done
        signal.connect(lambda: _clear_thread_ref())
    except Exception as e:
        logging.error("Failed to empty Recycle Bin: %s", e)


def _clear_thread_ref():
    """Clear the global thread reference."""
    global _empty_bin_thread_ref
    _empty_bin_thread_ref = None


def get_explorer_pinned_folders() -> list[tuple[str, str]]:
    """
    Get pinned folders from Windows Quick Access using Shell COM API.
    Returns list of (folder_name, folder_path) tuples.
    """
    try:
        pythoncom.CoInitialize()

        pinned_folders: list[tuple[str, str]] = []

        try:
            # Get desktop folder first
            desktop = shell.SHGetDesktopFolder()

            # Parse Quick Access using its GUID
            quick_access_path = f"shell:::{{{KnownCLSID.QUICK_ACCESS}}}"
            pidl = shell.SHParseDisplayName(quick_access_path, 0)  # pyright: ignore[reportUnknownMemberType]

            # Bind to Quick Access folder
            quick_access_folder = desktop.BindToObject(
                pidl[0],  # pyright: ignore[reportArgumentType]
                None,  # pyright: ignore[reportArgumentType]
                shell.IID_IShellFolder,
            )

            # Enumerate folders in Quick Access
            enum_objects = quick_access_folder.EnumObjects(  # pyright: ignore[reportUnknownMemberType]
                0, shellcon.SHCONTF_FOLDERS | shellcon.SHCONTF_INCLUDEHIDDEN
            )

            # Iterate through all items
            for pidl_item in cast("Iterable[PyIDL]", enum_objects):
                try:
                    # Get display name
                    display_name = cast(
                        str,
                        quick_access_folder.GetDisplayNameOf(  # pyright: ignore[reportUnknownMemberType]
                            pidl_item, shellcon.SHGDN_NORMAL
                        ),
                    )

                    # Get file system path using FORPARSING flag
                    fs_path = cast(
                        str,
                        quick_access_folder.GetDisplayNameOf(  # pyright: ignore[reportUnknownMemberType]
                            pidl_item, shellcon.SHGDN_FORPARSING
                        ),
                    )

                    # Check attributes to ensure it's a folder
                    attrs = cast(
                        int,
                        quick_access_folder.GetAttributesOf(  # pyright: ignore[reportUnknownMemberType]
                            (pidl_item,), shellcon.SFGAO_FOLDER | shellcon.SFGAO_FILESYSTEM
                        ),
                    )
                    is_folder = bool(attrs & shellcon.SFGAO_FOLDER)
                    is_filesystem = bool(attrs & shellcon.SFGAO_FILESYSTEM)

                    # Only include filesystem folders (skip virtual folders except Recycle Bin)
                    if not fs_path:
                        continue

                    is_recycle_bin = KnownCLSID.RECYCLE_BIN in fs_path.upper()

                    if is_folder and ((is_filesystem and os.path.isdir(fs_path)) or is_recycle_bin):
                        folder_name = display_name or os.path.basename(fs_path) or fs_path
                        pinned_folders.append((folder_name, fs_path))

                except Exception as e:
                    logging.debug("Error processing Quick Access item: %s", e)
                    continue

        except Exception as e:
            logging.debug("Error accessing Quick Access folder: %s", e)

        pythoncom.CoUninitialize()
        return pinned_folders[:10]  # Limit to 10 items

    except Exception as e:
        logging.debug("Error reading Quick Access pinned folders: %s", e)
        return []


def get_windows_terminal_profiles(identifier: str | None = None) -> list[tuple[str, str]]:
    """
    Get Windows Terminal profiles from settings.json.
    Automatically detects whether it's stable, preview, or portable version from the identifier.

    Args:
        identifier: The app identifier (unique_id) to detect Terminal version

    Returns list of (profile_name, profile_guid) tuples.
    """
    try:
        settings_path = None

        # Detect version from identifier
        if identifier:
            check_str = identifier.lower()
            is_portable = identifier.startswith("path:") and "windowsterminal.exe" in check_str
            is_preview = "windowsterminalpre" in check_str or "microsoft.windowsterminalpre" in check_str
        else:
            is_portable = False
            is_preview = False

        if is_portable:
            # For portable version, settings are always stored in AppData
            # Location: %LOCALAPPDATA%\Microsoft\Windows Terminal\settings.json
            settings_path = (
                Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows Terminal" / "settings.json"
            )

        else:
            # Choose the correct package based on version for UWP installations
            if is_preview:
                package_name = "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe"
            else:
                package_name = "Microsoft.WindowsTerminal_8wekyb3d8bbwe"

            # Windows Terminal UWP settings location
            settings_path = (
                Path(os.environ.get("LOCALAPPDATA", "")) / "Packages" / package_name / "LocalState" / "settings.json"
            )

        if not settings_path or not settings_path.exists():
            logging.debug("Windows Terminal settings.json not found at %s", settings_path)
            return []

        # Read and parse the settings
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)

        profiles: list[tuple[str, str]] = []

        # Get profiles list
        if "profiles" in settings and "list" in settings["profiles"]:
            for profile in settings["profiles"]["list"]:
                # Skip hidden profiles
                if profile.get("hidden", False):
                    continue

                profile_name = profile.get("name", "Unknown")
                profile_guid = profile.get("guid", "")

                if profile_guid:
                    profiles.append((profile_name, profile_guid))

        return profiles[:20]  # Limit to 20 profiles

    except Exception as e:
        logging.debug("Error reading Windows Terminal profiles: %s", e)
        return []


def show_context_menu(taskbar_widget: TaskbarWidget, hwnd: int, pos: QPoint) -> QMenu | None:
    """
    Show context menu for a taskbar button.

    Args:
        taskbar_widget: The taskbar widget instance
        hwnd: Window handle (negative for pinned-only apps)
        pos: Position to show the menu
    """
    try:
        # Get widget and temporarily unset its cursor
        widget = taskbar_widget.hwnd_to_widget.get(hwnd)
        if widget:
            try:
                widget.unsetCursor()
            except RuntimeError:
                widget = None

        # Determine if this is a pinned-only button (not running)
        is_pinned_only = hwnd < 0
        is_pinned = is_pinned_only or taskbar_widget.is_app_pinned(hwnd)

        # Get unique_id
        unique_id = None

        if is_pinned_only:
            # For pinned-only apps, get unique_id from widget property
            if widget:
                unique_id = widget.property("unique_id")
        elif hwnd > 0:
            # For running pinned apps, get unique_id from running_pinned
            if is_pinned and hwnd in taskbar_widget.pin_manager.running_pinned:
                unique_id = taskbar_widget.pin_manager.running_pinned.get(hwnd)
            elif not is_pinned:
                # For running but NOT pinned apps, get the real unique_id
                from core.widgets.services.taskbar.pin_manager import PinManager

                # Get full window_data from ApplicationWindow if available
                window_data: dict[str, Any] = {"process_name": "", "title": ""}
                task_manager = taskbar_widget.task_manager
                app_window = task_manager.get_window(hwnd) if task_manager else None
                if app_window is not None:
                    window_data = app_window.as_dict()
                elif widget:
                    window_data = {
                        "process_name": widget.property("process_name") or "",
                        "title": widget.property("title") or "",
                    }
                unique_id, _ = PinManager.get_app_identifier(hwnd, window_data, resolve_shortcut=False)

        menu = QMenu(taskbar_widget.window())
        apply_qmenu_style(menu)
        menu.setProperty("class", "context-menu")

        # Determine app type from unique_id
        is_explorer = False
        is_recycle_bin = False
        is_chromium_browser = False  # Edge, Chrome
        is_firefox_browser = False  # Firefox, Zen
        is_vscode = False  # VSCode or VSCode Insiders
        is_terminal = False

        if unique_id:
            check_str = unique_id.lower()

            is_explorer = "explorer.exe" in check_str or check_str.startswith("explorer:")
            # Check if this is specifically the Recycle Bin
            is_recycle_bin = KnownCLSID.RECYCLE_BIN in check_str.upper()
            is_chromium_browser = (
                "msedge.exe" in check_str or "msedge" in check_str or "chrome.exe" in check_str or "chrome" in check_str
            )
            is_firefox_browser = (
                "firefox.exe" in check_str
                or "308046b0af4a39cb" in check_str
                or "zen.exe" in check_str
                or "f0dc299d809b9700" in check_str
            )
            is_vscode = "code.exe" in check_str or "code - insiders.exe" in check_str
            is_terminal = "windowsterminal.exe" in check_str or "windowsterminal" in check_str

        # Add app-specific menu items
        if is_recycle_bin and is_pinned:
            _add_recycle_bin_menu_items(menu, taskbar_widget.launch_pinned_app)
        elif is_explorer:
            _add_explorer_menu_items(menu, taskbar_widget.launch_pinned_app)
        elif is_chromium_browser and unique_id:
            _add_chromium_browser_menu_items(menu, unique_id, taskbar_widget.launch_pinned_app)
        elif is_firefox_browser and unique_id:
            _add_firefox_browser_menu_items(menu, unique_id, taskbar_widget.launch_pinned_app)
        elif is_vscode and unique_id:
            _add_vscode_menu_items(menu, unique_id, taskbar_widget.launch_pinned_app)
        elif is_terminal and unique_id:
            _add_terminal_menu_items(menu, unique_id, taskbar_widget.launch_pinned_app)

        menu.addSeparator()

        # Open App (only show for pinned apps, not for running non-pinned apps)
        if is_pinned and not is_explorer:
            open_action = QAction("Open app", menu)
            menu.addAction(open_action)
            open_action.triggered.connect(lambda: taskbar_widget.launch_pinned_app(hwnd))

        # Pin/Unpin
        if is_pinned:
            menu.addSeparator()
            pin_action = QAction("Unpin from taskbar", menu)
            menu.addAction(pin_action)
            if is_pinned_only:
                pin_action.triggered.connect(lambda: taskbar_widget.unpin_pinned_only_app(unique_id or "", hwnd))
            else:
                pin_action.triggered.connect(lambda: taskbar_widget.unpin_app(hwnd))
        else:
            pin_action = QAction("Pin to taskbar", menu)
            menu.addAction(pin_action)
            pin_action.triggered.connect(lambda: taskbar_widget.pin_app(hwnd))
            menu.addSeparator()

        # End task and Close window (only for running apps)
        if not is_pinned_only and win32gui.IsWindow(hwnd):
            end_task_action = QAction("End task", menu)
            menu.addAction(end_task_action)
            end_task_action.triggered.connect(lambda: close_application(hwnd, force=True))

            close_action = QAction("Close window", menu)
            menu.addAction(close_action)
            close_action.triggered.connect(lambda: close_application(hwnd))

            group_hwnds = taskbar_widget.group_hwnds.get(taskbar_widget.hwnd_to_group.get(hwnd, ""), [])
            if len(group_hwnds) > 1:

                def close_all(_checked: bool = False, hwnds: list[int] = list(group_hwnds)) -> None:
                    for group_hwnd in hwnds:
                        close_application(group_hwnd)

                close_all_action = QAction("Close all windows", menu)
                menu.addAction(close_all_action)
                close_all_action.triggered.connect(close_all)

        # Adjust menu position so it appears just outside the bar
        margin = 6
        menu_size = menu.sizeHint()

        bar_widget = taskbar_widget.window()
        if bar_widget is None:
            return None
        bar_top_left = bar_widget.mapToGlobal(bar_widget.rect().topLeft())
        bar_height = bar_widget.height()

        button_center = widget.mapToGlobal(widget.rect().center()) if widget else pos
        new_x = button_center.x() - menu_size.width() / 2

        bar_alignment: object = getattr(bar_widget, "alignment", {}) if bar_widget else {}
        bar_position = (
            cast(dict[str, object], bar_alignment).get("position") if isinstance(bar_alignment, dict) else None
        )
        if bar_position == "top":
            new_y = bar_top_left.y() + bar_height + margin
        else:
            new_y = bar_top_left.y() - menu_size.height() - margin
        pos = QPoint(int(new_x), int(new_y))

        # Use popup instead of exec to allow proper focus handling
        menu.popup(pos)
        menu.activateWindow()

        # Restore cursor when menu closes
        def restore_cursor():
            if widget:
                try:
                    # Check if widget still exists before setting cursor
                    widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                except RuntimeError:
                    # Widget has been deleted, ignore
                    pass

        menu.aboutToHide.connect(restore_cursor)

        return menu

    except Exception as e:
        logging.error("Error showing context menu: %s", e)
        return None


def _add_recycle_bin_menu_items(menu: QMenu, on_launch_callback: LaunchCallback) -> None:
    """Add Recycle Bin specific menu items."""
    # Get recycle bin info from singleton monitor
    try:
        from core.widgets.services.recycle_bin.recycle_bin_monitor import RecycleBinMonitor

        monitor = RecycleBinMonitor.get_instance()
        # Use cached info (fast, non-blocking)
        info = monitor.last_info
        num_items = int(info.get("num_items", 0))
        size_bytes = int(info.get("size_bytes", 0))
    except Exception:
        num_items = 0
        size_bytes = 0

    # Add info item only if there are items in the recycle bin
    if num_items > 0:
        info_text = (
            f"{num_items} item{'s' if num_items != 1 else ''} ({naturalsize(size_bytes, binary=True, format='%.2f')})"
        )
        info_action = QAction(info_text, menu)
        menu.addAction(info_action)
        info_action.setEnabled(False)
        menu.addSeparator()

    # Add "Open" option to open Recycle Bin
    _add_launch_action(menu, "Open", on_launch_callback, f"explorer:::{{{KnownCLSID.RECYCLE_BIN}}}")

    menu.addSeparator()

    # Add "Empty Recycle Bin" option
    empty_action = QAction("Empty Recycle Bin", menu)
    menu.addAction(empty_action)

    # Check if Recycle Bin is empty and disable the option if it is
    is_empty = num_items == 0 and size_bytes == 0
    empty_action.setEnabled(not is_empty)
    if is_empty:
        empty_action.setToolTip("Recycle Bin is already empty")

    empty_action.triggered.connect(_empty_recycle_bin)
    menu.addSeparator()


def _add_explorer_menu_items(menu: QMenu, on_launch_callback: LaunchCallback) -> None:
    """Add File Explorer specific menu items."""
    # Get pinned folders from File Explorer's Jump List
    pinned_folders = get_explorer_pinned_folders()

    if pinned_folders:
        # Add pinned folders directly to menu
        for folder_name, folder_path in pinned_folders:
            # Use explorer: prefix to indicate this is a folder launch
            _add_launch_action(menu, folder_name, on_launch_callback, f"explorer:{folder_path}")
        menu.addSeparator()

    # Always add "File Explorer" option - opens "This PC"
    _add_launch_action(menu, "File Explorer", on_launch_callback, "explorer:::{20D04FE0-3AEA-1069-A2D8-08002B30309D}")
    menu.addSeparator()


def _add_chromium_browser_menu_items(menu: QMenu, identifier: str | None, on_launch_callback: LaunchCallback) -> None:
    """Add Chromium-based browser specific menu items (Edge, Chrome)."""
    if identifier:
        # Determine which browser (Chrome uses --incognito, Edge uses --inprivate)
        check_str = identifier.lower()
        is_chrome = "chrome.exe" in check_str or "chrome" in check_str
        private_flag = "--incognito" if is_chrome else "--inprivate"
        private_label = "New Incognito Window" if is_chrome else "New InPrivate Window"

        _add_launch_action(menu, "New Window", on_launch_callback, identifier)
        _add_launch_action(menu, private_label, on_launch_callback, identifier, private_flag)
        menu.addSeparator()


def _add_firefox_browser_menu_items(menu: QMenu, identifier: str | None, on_launch_callback: LaunchCallback) -> None:
    """Add Firefox-based browser specific menu items (Firefox, Zen)."""
    if identifier:
        # Check if this is UWP (AUMID) or Win32 (path)
        is_uwp = identifier.startswith("aumid:")

        if is_uwp:
            # For UWP browsers, format AUMID directly with suffix
            _add_launch_action(menu, "New Window", on_launch_callback, identifier)
            _add_launch_action(menu, "New Private Window", on_launch_callback, f"{identifier};PrivateBrowsingAUMID")
        else:
            # For Win32 browsers, use command-line arguments
            _add_launch_action(menu, "New Window", on_launch_callback, identifier, "-new-window")
            _add_launch_action(menu, "New Private Window", on_launch_callback, identifier, "-private-window")
        menu.addSeparator()


def _add_vscode_menu_items(menu: QMenu, identifier: str | None, on_launch_callback: LaunchCallback) -> None:
    """Add VS Code specific menu items (VS Code and VS Code Insiders)."""
    if identifier:
        _add_launch_action(menu, "New Window", on_launch_callback, identifier, "-n")
        menu.addSeparator()


def _add_terminal_menu_items(menu: QMenu, identifier: str | None, on_launch_callback: LaunchCallback) -> None:
    """Add Windows Terminal specific menu items.

    Args:
        menu: The QMenu to add items to
        identifier: The app identifier (unique_id) - used to detect Terminal version
        on_launch_callback: Callback function to launch the app
    """
    # Get Windows Terminal profiles (auto-detects version from identifier)
    profiles = get_windows_terminal_profiles(identifier=identifier)

    if identifier:
        if profiles:
            # Add each profile as a menu item
            for profile_name, profile_guid in profiles:
                _add_launch_action(menu, profile_name, on_launch_callback, identifier, f"-p {profile_guid}")
            menu.addSeparator()

        # Add "New Window" option
        _add_launch_action(menu, "New Window", on_launch_callback, identifier)
        menu.addSeparator()
