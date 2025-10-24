"""
Pin Manager for Taskbar Widget

Handles all pinned application functionality including:
- Loading/saving pinned apps from/to JSON file
- Icon caching and management
- App identification (AUMID, exe path, explorer folders)
- Signal coordination between taskbar instances
- Launching pinned applications
"""

import json
import logging
import os
import shlex
import subprocess
from pathlib import Path

import win32gui
import win32process
from PIL import Image
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from core.utils.utilities import app_data_path
from core.utils.widgets.taskbar.pin_context import (
    WindowContext,
    collect_window_context,
    ensure_command_line,
)
from core.utils.widgets.taskbar.shortcut_resolver import (
    extract_appname_from_cmdline,
    extract_title_from_cmdline,
    find_app_shortcut,
    find_shortcut_by_aumid,
    find_shortcut_by_name,
    get_wscript_shell,
    normalized_targets,
)
from core.utils.win32.utilities import get_app_name_from_aumid
from settings import DEBUG


class TaskbarSignalBus(QObject):
    """Signal bus for coordinating pinned app changes across multiple taskbar instances."""

    pinned_apps_changed = pyqtSignal(str, str)  # action, unique_id


_taskbar_signal_bus = TaskbarSignalBus()


class PinManager:
    """
    Manages pinned applications for the taskbar widget.
    """

    # Global cache for pinned app icons (shared across all PinManager instances)
    _icon_cache = {}  # {(unique_id, size, dpi): QPixmap}

    # Global cache for pinned apps data (shared across all PinManager instances)
    _apps_global_cache = {
        "data": None,  # {"pinned_apps": {}, "pinned_order": []}
        "file_path": None,
        "mtime": None,  # Last modification time for cache invalidation
    }

    # Cache: normalized exe path -> shortcut .lnk file path
    _shortcut_cache: dict[str, str] = {}

    # Cache: normalized shortcut display name -> shortcut path
    _shortcut_name_cache: dict[str, str] = {}

    @staticmethod
    def _parse_unique_id(unique_id: str) -> tuple[str, str, str]:
        """
        Parse unique_id into (type, value, args) tuple.

        Examples:
            'path:C:\\...\\app.exe' -> ('path', 'C:\\...\\app.exe', '')
            'path:C:\\...\\mmc.exe|eventvwr.msc' -> ('path', 'C:\\...\\mmc.exe', 'eventvwr.msc')
            'aumid:Microsoft.App' -> ('aumid', 'Microsoft.App', '')
            'explorer:C:\\folder' -> ('explorer', 'C:\\folder', '')
            'explorer:shell:RecycleBinFolder' -> ('explorer', 'shell:RecycleBinFolder', '')
            'explorer:::{645FF040-...}' -> ('explorer', '::{645FF040-...}', '')
        """
        if ":" in unique_id:
            type_prefix, value_with_args = unique_id.split(":", 1)
            # Check for command line args after pipe
            if "|" in value_with_args:
                value, args = value_with_args.split("|", 1)
                return type_prefix, value, args
            return type_prefix, value_with_args, ""
        return "unknown", unique_id, ""

    def __init__(self):
        """Initialize the pin manager."""
        self.pinned_apps = {}  # {unique_id: {path, aumid, icon, process_name, title}}
        self.pinned_order = []  # [unique_id, ...]
        self.running_pinned = {}  # Maps hwnd -> unique_id for running pinned apps

    @staticmethod
    def get_signal_bus():
        """Get the shared signal bus for taskbar communication."""
        return _taskbar_signal_bus

    @staticmethod
    def get_path_for_pinned_app(unique_id: str) -> str | None:
        """Get the exe path for a pinned app from its unique_id."""
        id_type, value, _ = PinManager._parse_unique_id(unique_id)
        if id_type == "path":
            return value
        elif id_type == "explorer":
            # Use environment variable to get the correct Windows directory
            windows_dir = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or "C:\\Windows"
            return os.path.join(windows_dir, "explorer.exe")
        return None

    @staticmethod
    def get_pinned_apps_file() -> Path:
        """Get the path to the pinned apps JSON file."""
        return app_data_path("taskbar_pinned.json")

    @staticmethod
    def get_pinned_icons_folder() -> Path:
        """Get the folder path for storing pinned app icons."""
        folder = app_data_path("taskbar_icons")
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @staticmethod
    def get_icon_cache_path(unique_id: str) -> Path:
        """Get the file path for a cached icon."""
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in unique_id)
        return PinManager.get_pinned_icons_folder() / f"{safe_name}.png"

    def load_pinned_apps(self) -> None:
        """Load pinned apps from disk using global cache to avoid redundant file reads."""
        file_path = self.get_pinned_apps_file()

        try:
            should_reload = False

            if not file_path.exists():
                self.pinned_apps = {}
                self.pinned_order = []
                return

            current_mtime = file_path.stat().st_mtime
            if (
                PinManager._apps_global_cache["data"] is None
                or PinManager._apps_global_cache["file_path"] != str(file_path)
                or PinManager._apps_global_cache["mtime"] != current_mtime
            ):
                should_reload = True

            if should_reload:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    PinManager._apps_global_cache["data"] = data
                    PinManager._apps_global_cache["file_path"] = str(file_path)
                    PinManager._apps_global_cache["mtime"] = current_mtime
                    logging.debug(
                        "Loaded %s pinned apps from %s",
                        len(data.get("pinned_apps", {})),
                        file_path,
                    )

            data = PinManager._apps_global_cache["data"] or {}
            self.pinned_apps = data.get("pinned_apps", {})
            self.pinned_order = data.get("pinned_order", [])

            PinManager._shortcut_cache.clear()
            for unique_id, metadata in self.pinned_apps.items():
                try:
                    id_type, value, _ = PinManager._parse_unique_id(unique_id)
                    exe_path = value if id_type == "path" else None
                    if not exe_path:
                        exe_path = metadata.get("path") if isinstance(metadata, dict) else None

                    shortcut_path = metadata.get("shortcut_path") if isinstance(metadata, dict) else None
                    if not exe_path or not shortcut_path or not os.path.exists(shortcut_path):
                        continue

                    # Skip caching for mmc.exe and rundll32.exe - they host different snap-ins
                    # Maybe revisit this later with more context and understanding
                    exe_name = Path(exe_path).stem.lower()
                    if exe_name not in ("mmc", "rundll32"):
                        for key in normalized_targets(exe_path):
                            PinManager._shortcut_cache[key] = shortcut_path
                except Exception:
                    continue

        except (json.JSONDecodeError, FileNotFoundError) as exc:
            logging.debug("Could not load pinned apps: %s", exc)
            self.pinned_apps = {}
            self.pinned_order = []
        except Exception as exc:
            logging.error("Error loading pinned apps: %s", exc)
            self.pinned_apps = {}
            self.pinned_order = []

    def save_pinned_apps(self) -> None:
        """Save pinned apps to disk and update global cache."""
        file_path = self.get_pinned_apps_file()
        try:
            data = {
                "pinned_apps": self.pinned_apps,
                "pinned_order": self.pinned_order,
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            PinManager._apps_global_cache["data"] = data
            PinManager._apps_global_cache["file_path"] = str(file_path)
            PinManager._apps_global_cache["mtime"] = file_path.stat().st_mtime

        except Exception as exc:
            logging.error("Error saving pinned apps: %s", exc)

    @staticmethod
    def _resolve_pin_metadata(context: WindowContext, base_title: str | None = None) -> dict[str, str]:
        metadata: dict[str, str] = {}

        exe_path = context.exe_path
        aumid = context.aumid
        window_title = context.window_title
        process_name = context.process_name

        shortcut_path: str | None = None
        shortcut_name: str | None = None

        cmdline_text: str | None = None
        cmdline_app_name: str | None = None
        cmdline_title: str | None = None

        def ensure_cmdline_hints() -> None:
            nonlocal cmdline_text, cmdline_app_name, cmdline_title
            if cmdline_text is not None:
                return
            cmdline_text = ensure_command_line(context)
            if cmdline_text:
                cmdline_app_name = extract_appname_from_cmdline(cmdline_text)
                cmdline_title = extract_title_from_cmdline(cmdline_text)

        if exe_path and not aumid and not context.is_explorer and not context.explorer_path:
            for key in normalized_targets(exe_path):
                cached_shortcut = PinManager._shortcut_cache.get(key)
                if cached_shortcut and isinstance(cached_shortcut, str):
                    if os.path.exists(cached_shortcut):
                        shortcut_path = cached_shortcut
                        shortcut_name = Path(cached_shortcut).stem
                        break
                    PinManager._shortcut_cache.pop(key, None)

            if not shortcut_path:
                ensure_cmdline_hints()
                candidate_names = [cmdline_title, cmdline_app_name, window_title, process_name]
                try:
                    candidate_names.append(Path(exe_path).stem if exe_path else None)
                except Exception:
                    pass

                filtered_candidates = [name for name in candidate_names if name]
                if filtered_candidates:
                    app_shortcut = find_app_shortcut(
                        exe_path,
                        candidate_names=filtered_candidates,
                        shortcut_cache=PinManager._shortcut_cache,
                    )
                    if app_shortcut:
                        shortcut_path, shortcut_name = app_shortcut
                    else:
                        fallback = find_shortcut_by_name(
                            filtered_candidates,
                            shortcut_name_cache=PinManager._shortcut_name_cache,
                        )
                        if fallback:
                            shortcut_path, shortcut_name = fallback
                            for key in normalized_targets(exe_path):
                                PinManager._shortcut_cache[key] = shortcut_path

        elif aumid and not shortcut_path:
            # AUMID apps can be either:
            # 1. UWP/PWA apps - have AUMIDs ending with !App, launch via shell:AppsFolder
            # 2. Win32 apps with AUMID (like Steam, Electron) - need shortcut to launch properly

            # FIRST: Try to find shortcut by AUMID (most reliable, same as Windows does)
            aumid_shortcut = find_shortcut_by_aumid(aumid)
            if aumid_shortcut:
                shortcut_path, shortcut_name = aumid_shortcut
                logging.debug(f"Found shortcut by AUMID: {shortcut_path}")
            else:
                # If no shortcut found by AUMID, determine if this is Win32 app that needs shortcut
                # Key insight: All UWP/PWA apps end with !App, Win32 apps with AUMID do NOT
                # Examples:
                #   - YouTube PWA: www.youtube.com-54E21B02_pd8mbgmqs65xy!App -> ends with !App
                #   - TikTok Store PWA: BytedancePte.Ltd.TikTok_6yccndn6064se!App -> ends with !App
                #   - Calculator UWP: Microsoft.WindowsCalculator_8wekyb3d8bbwe!App -> ends with !App
                #   - Steam Win32: Valve.Steam.Client → does NOT end with !App
                #   - Discord Electron: com.squirrel.Discord.Discord → does NOT end with !App

                is_uwp_or_pwa = aumid and aumid.endswith("!App")

                # Only search for shortcuts if this is a Win32 app (no !App suffix)
                if not is_uwp_or_pwa and exe_path:
                    # This is a Win32 app with AUMID - search for shortcut by exe path
                    # First check cache
                    for key in normalized_targets(exe_path):
                        cached_shortcut = PinManager._shortcut_cache.get(key)
                        if cached_shortcut and isinstance(cached_shortcut, str):
                            if os.path.exists(cached_shortcut):
                                shortcut_path = cached_shortcut
                                shortcut_name = Path(cached_shortcut).stem
                                break
                            PinManager._shortcut_cache.pop(key, None)

                    # If not in cache, search by name
                    if not shortcut_path:
                        ensure_cmdline_hints()
                        candidate_names = [cmdline_title, cmdline_app_name, window_title, process_name]
                        try:
                            candidate_names.append(Path(exe_path).stem if exe_path else None)
                        except Exception:
                            pass

                        filtered_candidates = [name for name in candidate_names if name]
                        if filtered_candidates:
                            app_shortcut = find_app_shortcut(
                                exe_path,
                                candidate_names=filtered_candidates,
                                shortcut_cache=PinManager._shortcut_cache,
                            )
                            if app_shortcut:
                                shortcut_path, shortcut_name = app_shortcut
                            else:
                                fallback = find_shortcut_by_name(
                                    filtered_candidates,
                                    shortcut_name_cache=PinManager._shortcut_name_cache,
                                )
                                if fallback:
                                    shortcut_path, shortcut_name = fallback
                                    for key in normalized_targets(exe_path):
                                        PinManager._shortcut_cache[key] = shortcut_path

        best_title = base_title or ""

        if shortcut_path:
            metadata["shortcut_path"] = shortcut_path
            if not shortcut_name:
                shortcut_name = Path(shortcut_path).stem

        # Title priority depends on whether we found a shortcut:
        # - With shortcut: shortcut_name > window_title > base_title (shortcut name is most reliable)
        # - Without shortcut (UWP apps): base_title > window_title (window_title can be tab/document name)
        # - Fallback: cmdline hints > process_name
        if shortcut_name:
            best_title = shortcut_name
        elif not aumid or not base_title:
            # For non-AUMID apps or if base_title is empty, prefer window_title
            if window_title:
                best_title = window_title
            elif base_title:
                best_title = base_title
            else:
                ensure_cmdline_hints()
                if cmdline_title:
                    best_title = cmdline_title
                elif cmdline_app_name:
                    best_title = cmdline_app_name
                elif process_name:
                    best_title = process_name
        else:
            # For AUMID apps without shortcut (UWP), prefer base_title over window_title
            if base_title:
                best_title = base_title
            elif window_title:
                best_title = window_title
            else:
                ensure_cmdline_hints()
                if cmdline_title:
                    best_title = cmdline_title
                elif cmdline_app_name:
                    best_title = cmdline_app_name
                elif process_name:
                    best_title = process_name

        if best_title:
            metadata["title"] = best_title
        return metadata

    @staticmethod
    def get_app_identifier(hwnd: int, window_data: dict, *, resolve_shortcut: bool = False) -> tuple[str | None, dict]:
        """
        Get a unique identifier for an app and its metadata.
        For File Explorer, includes the folder path or shell location in the unique_id to allow
        multiple pinned folders and special folders (e.g., Recycle Bin, This PC).
        Returns (unique_id, metadata_dict) or (None, {}) if unable to identify the app.
        """
        from core.utils.win32.utilities import get_app_name_from_pid

        context = collect_window_context(hwnd, window_data)
        if not context:
            return None, {}

        exe_path = context.exe_path
        exe_lower = exe_path.lower() if exe_path else ""
        needs_args = exe_lower.endswith(("mmc.exe", "rundll32.exe"))
        cmdline_args: str | None = None

        if needs_args:
            try:
                cmd_text = ensure_command_line(context)
                if cmd_text:
                    if cmd_text.startswith('"'):
                        end_quote = cmd_text.find('"', 1)
                        if end_quote != -1:
                            cmdline_args = cmd_text[end_quote + 1 :].strip()
                    else:
                        parts = cmd_text.split(None, 1)
                        if len(parts) > 1:
                            cmdline_args = parts[1]
            except Exception as exc:
                if DEBUG:
                    logging.debug(f"Could not get command line args: {exc}")

        app_name: str | None = None

        if context.is_explorer:
            app_name = context.window_title
        elif not context.aumid:
            app_name = context.window_title or context.process_name

        if not app_name:
            try:
                pid_for_name = context.base_pid

                if exe_path and "ApplicationFrameHost.exe" in exe_path and pid_for_name:
                    try:
                        child_hwnd = win32gui.FindWindowEx(hwnd, 0, "Windows.UI.Core.CoreWindow", None)
                        if child_hwnd:
                            _, child_pid = win32process.GetWindowThreadProcessId(child_hwnd)
                            if child_pid:
                                pid_for_name = child_pid
                    except Exception:
                        pass

                # For UWP apps (including PWAs), try to get real app name from PackageManager first
                if context.aumid:
                    resolved_name = get_app_name_from_aumid(context.aumid)
                    if resolved_name:
                        app_name = resolved_name

                # If AUMID lookup failed or no AUMID, use normal flow
                if not app_name and pid_for_name:
                    real_name = get_app_name_from_pid(pid_for_name)
                    if real_name:
                        app_name = real_name

            except Exception as e:
                logging.warning(f"Error resolving app name: {e}")

        if not app_name:
            app_name = context.window_title or context.process_name

        unique_id: str | None = None

        if context.aumid:
            unique_id = f"aumid:{context.aumid}"
        elif context.explorer_path:
            unique_id = f"explorer:{context.explorer_path}"
        elif exe_path:
            normalized_paths = normalized_targets(exe_path)
            stable_path = normalized_paths[1] if len(normalized_paths) > 1 else exe_path
            unique_id = f"path:{stable_path}"
            if cmdline_args:
                unique_id = f"{unique_id}|{cmdline_args}"
        else:
            logging.debug("Cannot create identifier for app - no AUMID, explorer path, or exe path found")
            return None, {}

        base_title = app_name or context.window_title or context.process_name or ""
        metadata: dict[str, str] = {"title": base_title}

        if resolve_shortcut:
            enriched = PinManager._resolve_pin_metadata(context, base_title)
            if "title" in enriched:
                metadata["title"] = enriched["title"]
            if "shortcut_path" in enriched:
                metadata["shortcut_path"] = enriched["shortcut_path"]

        if not metadata["title"]:
            metadata["title"] = context.window_title or context.process_name or metadata["title"]

        return unique_id, metadata

    def pin_app(self, hwnd: int, window_data: dict, icon_image: Image.Image = None, position: int = -1) -> str | None:
        """
        Pin an application to the taskbar (pinned apps are global across all monitors).
        """
        try:
            unique_id, metadata = self.get_app_identifier(hwnd, window_data, resolve_shortcut=True)

            # Check if we got a valid identifier
            if not unique_id or not metadata:
                logging.warning("Cannot pin app - unable to determine valid identifier")
                return None

            # Cache icon if provided
            if icon_image:
                # Save original sized icon as PNG
                icon_image.convert("RGBA").save(
                    str(self.get_icon_cache_path(unique_id)),
                    "PNG",
                    optimize=False,
                    compress_level=1,
                )

            self.pinned_apps[unique_id] = metadata

            # Handle position in pinned_order
            if unique_id in self.pinned_order:
                # Already in order, move it to the new position if specified
                if position >= 0:
                    self.pinned_order.remove(unique_id)
                    position = max(0, min(position, len(self.pinned_order)))
                    self.pinned_order.insert(position, unique_id)
            else:
                # New app, add at specified position
                if position >= 0:
                    position = max(0, min(position, len(self.pinned_order)))
                    self.pinned_order.insert(position, unique_id)
                else:
                    self.pinned_order.append(unique_id)

            self.running_pinned[hwnd] = unique_id

            # Save once with correct position
            self.save_pinned_apps()

            # Notify other taskbar instances
            _taskbar_signal_bus.pinned_apps_changed.emit("pin", unique_id)

            return unique_id

        except Exception as e:
            logging.error(f"Error pinning app: {e}")
            return None

    def unpin_app(self, hwnd: int, window_data: dict = None) -> None:
        """Unpin an application from the taskbar."""
        try:
            # Get unique_id for this app
            unique_id = self.running_pinned.get(hwnd)
            if not unique_id and window_data:
                unique_id, _ = self.get_app_identifier(hwnd, window_data)

            if unique_id and unique_id in self.pinned_apps:
                del self.pinned_apps[unique_id]
                self.pinned_order.remove(unique_id)
                self.running_pinned.pop(hwnd, None)
                self.delete_cached_icon(unique_id)
                self.save_pinned_apps()

                # Notify other taskbar instances
                _taskbar_signal_bus.pinned_apps_changed.emit("unpin", unique_id)
        except Exception as e:
            logging.error(f"Error unpinning app: {e}")

    def is_app_pinned(self, hwnd: int) -> bool:
        """Check if an app is pinned."""
        return hwnd in self.running_pinned

    def update_pinned_order(self, new_order: list[str]) -> None:
        """Update the pinned order and notify other instances."""
        if new_order != self.pinned_order:
            self.pinned_order = new_order
            self.save_pinned_apps()

            # Notify other taskbar instances about the reorder
            _taskbar_signal_bus.pinned_apps_changed.emit("reorder", "")

    def load_cached_icon(self, unique_id: str, size: int, dpi: float = 1.0) -> QPixmap | None:
        """
        Load a cached icon from PNG file and scale to proper size with DPI awareness.
        If cached icon is missing, extracts native Windows icon as fallback.
        Uses a global cache to avoid reloading the same icon across multiple instances.
        """
        from core.utils.win32.app_icons import get_window_icon

        # Check global cache first (include DPI in cache key)
        cache_key = (unique_id, size, dpi)
        if cache_key in PinManager._icon_cache:
            return PinManager._icon_cache[cache_key]

        try:
            icon_path = self.get_icon_cache_path(unique_id)

            # If cached icon doesn't exist, extract native icon using get_window_icon with fake hwnd
            if not icon_path.exists():
                icon_img = get_window_icon(0)  # Fake hwnd - will fallback to native icons
                if icon_img:
                    icon_img.convert("RGBA").save(str(icon_path), "PNG", optimize=False, compress_level=1)

            if icon_path.exists():
                pixmap = QPixmap(str(icon_path))
                if not pixmap.isNull():
                    physical_size = int(size * dpi)
                    scaled = pixmap.scaled(
                        physical_size,
                        physical_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    scaled.setDevicePixelRatio(dpi)

                    # Store in global cache for reuse
                    PinManager._icon_cache[cache_key] = scaled
                    return scaled
        except Exception as e:
            logging.error(f"Error loading cached icon for {unique_id}: {e}")
        return None

    def delete_cached_icon(self, unique_id: str) -> None:
        """Delete a cached icon file and remove from global cache."""
        try:
            # Remove from global cache (all size variants)
            keys_to_remove = [k for k in PinManager._icon_cache.keys() if k[0] == unique_id]
            for key in keys_to_remove:
                del PinManager._icon_cache[key]

            # Delete the file
            icon_path = self.get_icon_cache_path(unique_id)
            if icon_path.exists():
                icon_path.unlink()

        except Exception as e:
            logging.error(f"Error deleting cached icon: {e}")

    @staticmethod
    def _launch_exe(exe_path: str, arguments: str = "", working_dir: str = None) -> None:
        """Launch an executable with subprocess, with UAC elevation if needed."""
        # Validate working directory
        if not working_dir or not os.path.exists(working_dir):
            working_dir = os.path.dirname(exe_path)

        if not os.path.exists(working_dir):
            working_dir = None

        try:
            cmd = [exe_path]
            if arguments:
                try:
                    # Use shlex to split arguments, then strip quotes from each arg
                    parsed_args = shlex.split(arguments, posix=False)
                    # Remove surrounding quotes if shlex preserved them
                    cleaned_args = [arg.strip('"') for arg in parsed_args]
                    cmd.extend(cleaned_args)
                except ValueError:
                    # Fallback to simple split if shlex fails
                    cmd.extend(arguments.split())

            subprocess.Popen(
                cmd,
                cwd=working_dir,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            # Check if elevation is required (WinError 740)
            if e.winerror == 740:
                import win32api
                import win32con

                try:
                    win32api.ShellExecute(0, "runas", exe_path, arguments, working_dir, win32con.SW_SHOWNORMAL)
                except Exception as shell_error:
                    logging.error(f"Failed to launch with elevation: {shell_error}")
                    raise
            else:
                raise

    def launch_pinned_app(self, unique_id: str, extra_arguments: str = "") -> None:
        """
        Launch a pinned application completely detached from the parent process.
        """
        try:
            id_type, value, cmdline_args = PinManager._parse_unique_id(unique_id)

            # Use the unique_id as-is to look up metadata
            # Each pinned entry (including AUMID variants like Firefox Private) has its own metadata
            metadata = self.pinned_apps.get(unique_id, {})
            shortcut_path = metadata.get("shortcut_path")

            # Launch AUMID apps (UWP) unless a shortcut override exists
            if id_type == "aumid" and not shortcut_path:
                # Prefer shell:AppsFolder for plain launches to avoid falling back to default browser
                try:
                    if extra_arguments:
                        os.startfile(value, arguments=extra_arguments)
                    else:
                        os.startfile(f"shell:AppsFolder\\{value}")
                    return
                except Exception:
                    args = {"arguments": extra_arguments} if extra_arguments else {}
                    try:
                        os.startfile(f"shell:AppsFolder\\{value}", **args)
                        return
                    except Exception:
                        if extra_arguments:
                            os.startfile(value, arguments=extra_arguments)
                        else:
                            os.startfile(value)
                        return

            if id_type == "aumid" and shortcut_path and os.path.exists(shortcut_path) and not extra_arguments:
                os.startfile(shortcut_path)
                return

            # Launch File Explorer folders and special shell locations
            # This handles both regular file paths (C:\folder) and shell: URLs (shell:RecycleBinFolder)
            if id_type == "explorer":
                os.startfile(value)
                return

            # Determine target exe and arguments from shortcut or direct path
            target = None
            arguments = ""
            working_dir = None

            if shortcut_path and os.path.exists(shortcut_path):
                # Read shortcut properties to get target and args
                wsh = get_wscript_shell()
                shortcut = wsh.CreateShortcut(shortcut_path)
                target = shortcut.Targetpath or ""
                arguments = shortcut.Arguments or ""
                working_dir = shortcut.WorkingDirectory or ""

            # Fallback to direct exe path if shortcut didn't provide target
            if not target and id_type == "path" and os.path.exists(value):
                target = value

            # If we have command line args from the unique_id (e.g., mmc.exe with .msc file), prefer them
            if cmdline_args:
                if id_type == "path" and os.path.exists(value):
                    target = value
                if arguments and arguments not in cmdline_args:
                    arguments = f"{cmdline_args} {arguments}".strip()
                else:
                    arguments = cmdline_args

            if target:
                # Combine shortcut arguments with extra arguments
                all_args = f"{arguments} {extra_arguments}".strip()
                PinManager._launch_exe(target, all_args, working_dir)
            else:
                logging.warning(f"Cannot launch app {unique_id} - no valid target")

        except Exception as e:
            logging.error(f"Error launching pinned app: {e}")
