import ctypes

import win32api

from core.utils.win32.bindings.dwmapi import DwmGetWindowAttribute
from core.utils.win32.bindings.ole32 import create_com_object
from core.utils.win32.bindings.shell32 import CLSID_VirtualDesktopManager, IVirtualDesktopManager
from core.utils.win32.bindings.user32 import (
    GetAncestor,
    GetClassName,
    GetProp,
    GetWindow,
    GetWindowLong,
    GetWindowText,
    IsWindow,
    IsWindowEnabled,
    IsWindowVisible,
)
from core.utils.win32.constants import (
    CLSCTX_INPROC_SERVER,
    DWMWA_CLOAKED,
    GA_ROOT,
    GW_OWNER,
    GWL_EXSTYLE,
    GWL_STYLE,
    WS_EX_APPWINDOW,
    WS_EX_NOACTIVATE,
    WS_EX_TOOLWINDOW,
    WS_EX_WINDOWEDGE,
    WS_MINIMIZEBOX,
)
from core.utils.win32.utils import get_process_info


class ApplicationWindow:
    """
    Represents a top-level window tracked by the taskbar.
    Holds identity (hwnd) and metadata used for filtering and UI state.
    """

    _vdm: IVirtualDesktopManager | None = None

    DEFAULT_IGNORED_PROCESSES = {"SearchHost.exe"}

    DEFAULT_IGNORED_CLASSES = {
        "Progman",
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "DV2ControlHost",
        "Windows.UI.Composition.DesktopWindowContentBridge",
        "ForegroundStaging",
        "ApplicationManager_DesktopShellWindow",
        "WorkerW",
        "Button",  # Windows 10/11 notification buttons
        "Windows.UI.Input.InputSite.WindowClass",
        "Windows.Internal.Shell.TabProxyWindow",
        "Microsoft-Windows-Sts-ComponentHost-Elevated",
        "SysListView32",
        "XamlExplorerHostIslandWindow_WASDK",
        "Microsoft.UI.Content.PopupWindowSiteBridge",
        "Microsoft.UI.Content.DesktopChildSiteBridge",
        "SysHeader32",
        "#32768",
        "msctls_statusbar32",
        "DirectUIHWND",
        "SHELLDLL_DefView",
    }

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.title = self.get_title()
        self.class_name = self._get_class_name()
        self.is_active = False
        self.is_flashing = False

        self.process_name = None
        self.process_pid = 0
        self.process_path = None

        self._refresh_process_info()

    def as_dict(self):
        # Get monitor handle for this window
        monitor_handle = None
        try:
            mh = win32api.MonitorFromWindow(self.hwnd, 0)
            monitor_handle = int(mh) if mh is not None else None  # pyright: ignore[reportUnnecessaryComparison]
        except Exception:
            pass

        self._refresh_process_info()

        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "class_name": self.class_name,
            "is_active": self.is_active,
            "is_flashing": self.is_flashing,
            "is_cloaked": self.is_cloaked(),
            "monitor_handle": monitor_handle,
            "process_name": self.process_name,
            "process_pid": self.process_pid,
            "process_path": self.process_path,
            "can_minimize": self.can_minimize(),
        }

    def _refresh_process_info(self) -> None:
        """Refresh cached process information for this window."""
        try:
            process_info = get_process_info(self.hwnd)
        except Exception:
            process_info = None

        if process_info:
            self.process_name = process_info.get("name")
            self.process_pid = process_info.get("pid") or 0
            self.process_path = process_info.get("path")
        else:
            self.process_name = None
            self.process_pid = 0
            self.process_path = None

    def get_title(self):
        try:
            return GetWindowText(self.hwnd)
        except Exception:
            return ""

    def _get_class_name(self):
        try:
            return GetClassName(self.hwnd)
        except Exception:
            return ""

    def is_cloaked(self) -> bool:
        """Return True if the window is cloaked (hidden by the system, e.g., UWP)."""
        try:
            cloaked = ctypes.c_uint(0)
            res = DwmGetWindowAttribute(int(self.hwnd), DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            return res == 0 and cloaked.value > 0
        except Exception:
            return False

    def _is_immersive_shell_window(self) -> bool:
        """Detect Explorer immersive shell surfaces (Start/Search overlays, UWP frames) to exclude from taskbar.
        Uses class heuristics and, for certain classes, requires the process to be explorer.exe.
        """
        try:
            cls = self.class_name
            if not cls:
                return False
            ex_style = GetWindowLong(self.hwnd, GWL_EXSTYLE)

            if cls in (
                "ApplicationFrameWindow",
                "Windows.UI.Core.CoreWindow",
                "StartMenuSizingFrame",
                "Shell_LightDismissOverlay",
            ):
                if (ex_style & WS_EX_WINDOWEDGE) == 0:
                    return True
            elif cls in (
                "ImmersiveBackgroundWindow",
                "SearchPane",
                "NativeHWNDHost",
                "Shell_CharmWindow",
                "ImmersiveLauncher",
            ):
                # Explorer-only gate: treat these windows as immersive shell (Start/Search, etc.)
                # only when the owning process is explorer.exe, so they're excluded from the taskbar
                # without hiding third-party app windows that reuse similar classes.
                proc = (self.process_name or "").lower()
                if "explorer.exe" in proc:
                    return True
            return False
        except Exception:
            return False

    def can_add_to_taskbar(self) -> bool:
        """Policy for showing the window on the taskbar (top-level, visible, app window, minimizable)."""
        try:
            extended = GetWindowLong(self.hwnd, GWL_EXSTYLE)
            is_window = bool(IsWindow(self.hwnd))
            is_visible = bool(IsWindowVisible(self.hwnd))
            is_toolwindow = bool(extended & WS_EX_TOOLWINDOW)
            is_appwindow = bool(extended & WS_EX_APPWINDOW)
            is_noactivate = bool(extended & WS_EX_NOACTIVATE)
            owner = GetWindow(self.hwnd, GW_OWNER)
            # ITaskList_Deleted property
            is_deleted = False
            try:
                is_deleted = bool(GetProp(self.hwnd, "ITaskList_Deleted"))
            except Exception:
                is_deleted = False

            return (
                is_window
                and is_visible
                and ((owner == 0) or is_appwindow)
                and ((not is_noactivate) or is_appwindow)
                and (not is_toolwindow)
                and (not is_deleted)
            )
        except Exception:
            return False

    def _is_ghost_uwp_app(self) -> bool:
        """
        Check if the UWP app is a pre-launched (background ghost).
        Ghost apps are typically cloaked and NOT assigned to any Virtual Desktop.
        Real apps on other desktops are cloaked, but ARE assigned to a Virtual Desktop.
        Ghost apps are the ones that are slow, and Windows has to preload them, like Settings.
        Note: If we find a real solution for filtering out these apps, we can remove this workaround.
        """
        if self.process_name != "ApplicationFrameHost.exe":
            return False

        if not self.is_cloaked():
            return False

        try:
            if ApplicationWindow._vdm is None:
                ApplicationWindow._vdm = create_com_object(
                    CLSID_VirtualDesktopManager, IVirtualDesktopManager, CLSCTX_INPROC_SERVER
                )
            manager = ApplicationWindow._vdm
            if manager is None:
                return True

            # A window that belongs to no desktop has the null desktop ID
            return bytes(manager.GetWindowDesktopId(int(self.hwnd))) == b"\x00" * 16
        except Exception:
            return True

    def can_minimize(self) -> bool:
        """Return True if the window has a minimize box and is enabled."""
        try:
            styles = GetWindowLong(self.hwnd, GWL_STYLE)
            has_minimize_box = bool(styles & WS_MINIMIZEBOX)
            is_enabled = bool(IsWindowEnabled(self.hwnd))
            return has_minimize_box and is_enabled
        except Exception:
            return False

    def is_taskbar_window(self):
        """Main filter: top-level, titled, not cloaked/immersive shell, passes policy and ignore lists."""
        try:
            # Must be a top-level window
            if GetAncestor(self.hwnd, GA_ROOT) != self.hwnd:
                return False

            # Must have a non-empty title
            if not (self.title or "").strip():
                return False

            # Immersive shell windows should not appear
            if self._is_immersive_shell_window():
                return False

            if not self.can_add_to_taskbar():
                return False

            if self.process_name and self.process_name in self.DEFAULT_IGNORED_PROCESSES:
                return False

            if self.class_name in self.DEFAULT_IGNORED_CLASSES:
                return False

            if self._is_ghost_uwp_app():
                return False

            return True
        except Exception:
            return False

    def update(self):
        """Refresh cached title/class; returns True if anything changed."""
        old_title = self.title
        old_class_name = self.class_name

        self.title = self.get_title()
        self.class_name = self._get_class_name()
        # is_active is managed by the window manager

        return old_title != self.title or old_class_name != self.class_name

    def __eq__(self, other: object) -> bool:
        """Two ApplicationWindow objects are equal if they wrap the same hwnd."""
        if isinstance(other, ApplicationWindow):
            return self.hwnd == other.hwnd
        return False

    def __hash__(self):
        """Hash by hwnd for use in sets/dicts."""
        return hash(self.hwnd)
