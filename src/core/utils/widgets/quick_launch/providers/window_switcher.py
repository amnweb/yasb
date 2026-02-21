import hashlib
import logging
import os
import tempfile
import time

import win32con
import win32gui
from PyQt6.QtCore import QTimer

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.fuzzy import fuzzy_score
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_WINDOWS_SWITCHER
from core.utils.widgets.taskbar.window_manager import get_shared_task_manager
from core.utils.win32.app_icons import get_window_icon
from core.utils.win32.window_actions import (
    force_foreground_focus,
    resolve_base_and_focus,
    restore_window,
    show_window,
)


class WindowSwitcherProvider(BaseProvider):
    """Switch to currently open application windows."""

    name = "window"
    display_name = "Window Switcher"
    icon = ICON_WINDOWS_SWITCHER
    input_placeholder = "Switch to window..."

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.max_results = self.config.get("max_results", 50)
        self._task_manager = get_shared_task_manager(strict_filtering=False)

        self._icons_dir = os.path.join(tempfile.gettempdir(), "yasb_quick_launch_icons")
        os.makedirs(self._icons_dir, exist_ok=True)

    def match(self, text: str) -> bool:
        if self.prefix:
            return text.strip().startswith(self.prefix)
        return True

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        if not self._task_manager.is_initialized():
            now = time.time()
            if not hasattr(self, "_last_enum_time") or (now - self._last_enum_time > 1.0):
                self._task_manager._windows.clear()
                self._task_manager._enumerate_existing_windows()
                self._last_enum_time = now

        query_text = self.get_query_text(text) if self.prefix and text.startswith(self.prefix) else text
        query_lower = query_text.strip().lower()

        windows = list(self._task_manager.get_windows().values())
        taskbar_windows = [w for w in windows if w.is_taskbar_window()]

        z_order = []
        try:

            def enum_cb(hwnd, lParam):
                z_order.append(hwnd)
                return True

            win32gui.EnumWindows(enum_cb, 0)
        except Exception as e:
            logging.debug(f"EnumWindows failed in Window Switcher: {e}")

        z_order_map = {hwnd: i for i, hwnd in enumerate(z_order)}

        results_data = []
        for win in taskbar_windows:
            # Re-fetch title because the window might still have an old title in the dict
            title = win.title or win._get_title() or "Unknown"
            app_id = win.process_name or "Unknown"

            if query_lower:
                score_title = fuzzy_score(query_lower, title)
                score_app = fuzzy_score(query_lower, app_id)

                fs = None
                if score_title is not None and score_app is not None:
                    fs = max(score_title, score_app)
                elif score_title is not None:
                    fs = score_title
                elif score_app is not None:
                    fs = score_app

                if fs is None:
                    continue  # Filter out
            else:
                fs = 0.0

            results_data.append((fs, z_order_map.get(win.hwnd, 99999), win, title, app_id))

        # Sort match score (descending), then Z-order (ascending)
        results_data.sort(key=lambda x: (-x[0], x[1]))

        # Format output
        results = []
        for _, _, win, title, app_id in results_data[: self.max_results]:
            icon_path = self._get_window_icon_path(win)

            results.append(
                ProviderResult(
                    title=title,
                    description=f"Running - {os.path.splitext(app_id)[0]}",
                    icon_path=icon_path,
                    icon_char=self.icon if not icon_path else "",
                    provider=self.name,
                    id=f"win_{win.hwnd}",
                    action_data={"hwnd": win.hwnd},
                )
            )

        return results

    def _get_window_icon_path(self, win) -> str:
        is_uwp = win.class_name == "ApplicationFrameWindow"

        if win.process_path and os.path.isfile(win.process_path) and not is_uwp:
            path_hash = hashlib.md5(win.process_path.lower().encode()).hexdigest()[:10]
            base = os.path.splitext(os.path.basename(win.process_path))[0]
            temp_png = os.path.join(self._icons_dir, f"{base}_{path_hash}_0.png")

            if os.path.isfile(temp_png):
                return temp_png

            try:
                img = get_window_icon(win.hwnd)
                if img:
                    img = img.convert("RGBA").resize((48, 48))
                    img.save(temp_png, format="PNG")
                    return temp_png
            except Exception as e:
                logging.debug(f"Failed to extract shared window icon for {win.process_path}: {e}")

        icon_name = f"window_icon_{win.hwnd}.png"
        icon_path = os.path.join(self._icons_dir, icon_name)
        if os.path.isfile(icon_path):
            return icon_path

        try:
            img = get_window_icon(win.hwnd)
            if img:
                img = img.convert("RGBA").resize((48, 48))
                img.save(icon_path, format="PNG")
                return icon_path
        except Exception as e:
            logging.debug(f"Failed to extract window icon for hwnd {win.hwnd}: {e}")

        return ""

    def execute(self, result: ProviderResult) -> bool:
        hwnd = result.action_data.get("hwnd")
        if hwnd:
            if not win32gui.IsWindow(hwnd):
                return False

            try:

                def _do_focus():
                    try:
                        base, focus_target = resolve_base_and_focus(hwnd)
                        if win32gui.IsIconic(base):
                            restore_window(base)
                        else:
                            show_window(base)

                        force_foreground_focus(focus_target or base)
                    except Exception:
                        try:
                            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                            win32gui.SetActiveWindow(hwnd)
                        except Exception:
                            try:
                                win32gui.ShowWindow(
                                    hwnd, win32con.SW_RESTORE if win32gui.IsIconic(hwnd) else win32con.SW_SHOW
                                )
                            except Exception as final_e:
                                logging.error(f"Failed to show window {hwnd}: {final_e}")

                # Defer the actual focus call so the Quick Launch widget has time to hide
                QTimer.singleShot(0, _do_focus)
                return True
            except Exception as e:
                logging.error(f"Failed to set up delayed window focus {hwnd}: {e}")
        return False
