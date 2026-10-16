import logging
import os
import time
from typing import Any

import win32gui
from PySide6.QtCore import QTimer

from core.utils.icons.service import WindowIcon
from core.utils.win32.window_actions import (
    resolve_base_and_focus,
    restore_window,
    set_foreground,
    show_window,
)
from core.widgets.services.quick_launch.base_provider import BaseProvider, ProviderResult
from core.widgets.services.quick_launch.fuzzy import fuzzy_score
from core.widgets.services.quick_launch.providers.resources.icons import ICON_WINDOWS_SWITCHER
from core.widgets.services.taskbar.application_window import ApplicationWindow
from core.widgets.services.taskbar.window_manager import get_shared_task_manager


class WindowSwitcherProvider(BaseProvider):
    """Switch to currently open application windows."""

    name = "window"
    display_name = "Window Switcher"
    icon = ICON_WINDOWS_SWITCHER
    input_placeholder = "Switch to window..."

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.max_results = self.config.get("max_results", 50)
        self._task_manager = get_shared_task_manager()
        self._task_manager.keep_cloaked_tasks = True
        self._last_enum_time: float | None = None

    def match(self, text: str) -> bool:
        if self.prefix:
            return text.strip().startswith(self.prefix)
        return True

    def get_results(self, text: str, **kwargs: Any) -> list[ProviderResult]:
        if not self._task_manager.is_initialized():
            now = time.time()
            if self._last_enum_time is None or (now - self._last_enum_time > 1.0):
                self._task_manager.rescan_windows()
                self._last_enum_time = now

        query_text = self.get_query_text(text) if self.prefix and text.startswith(self.prefix) else text
        query_lower = query_text.strip().lower()

        windows = list(self._task_manager.get_windows().values())
        taskbar_windows = [w for w in windows if w.is_taskbar_window()]

        z_order: list[int] = []
        try:

            def enum_cb(hwnd: int, lParam: object) -> bool:
                z_order.append(hwnd)
                return True

            win32gui.EnumWindows(enum_cb, 0)
        except Exception as e:
            logging.debug("EnumWindows failed in Window Switcher: %s", e)

        z_order_map = {hwnd: i for i, hwnd in enumerate(z_order)}

        results_data: list[tuple[float, int, ApplicationWindow, str, str]] = []
        for win in taskbar_windows:
            # Re-fetch title because the window might still have an old title in the dict
            title = win.title or win.get_title() or "Unknown"
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
        results: list[ProviderResult] = []
        for _, _, win, title, app_id in results_data[: self.max_results]:
            results.append(
                ProviderResult(
                    title=title,
                    description=f"Running - {os.path.splitext(app_id)[0]}",
                    icon_source=WindowIcon(win.hwnd),
                    provider=self.name,
                    id=f"win_{win.hwnd}",
                    action_data={"hwnd": win.hwnd},
                )
            )

        return results

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

                        set_foreground(focus_target or base)
                    except Exception:
                        try:
                            if win32gui.IsIconic(hwnd):
                                restore_window(hwnd)
                            else:
                                show_window(hwnd)
                        except Exception as final_e:
                            logging.error("Failed to show window %s: %s", hwnd, final_e)

                # Defer the actual focus call so the Quick Launch widget has time to hide
                QTimer.singleShot(0, _do_focus)
                return True
            except Exception as e:
                logging.error("Failed to set up delayed window focus %s: %s", hwnd, e)
        return False
