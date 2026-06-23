import ctypes
from ctypes import wintypes

import win32api
import win32con
import win32gui

from core.utils.win32.bindings import DwmGetWindowAttribute, IsWindowEnabled
from core.utils.win32.utils import get_process_info


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


ole32 = ctypes.windll.ole32

ole32.CoCreateInstance.argtypes = [
    ctypes.POINTER(GUID),
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.POINTER(GUID),
    ctypes.POINTER(ctypes.c_void_p),
]
ole32.CoCreateInstance.restype = ctypes.c_long


# CLSID_VirtualDesktopManager = {aa509086-5ca9-4c25-8f95-589d3c07b48a}
CLSID_VirtualDesktopManager = GUID(
    0xAA509086, 0x5CA9, 0x4C25, (ctypes.c_ubyte * 8)(0x8F, 0x95, 0x58, 0x9D, 0x3C, 0x07, 0xB4, 0x8A)
)
# IID_IVirtualDesktopManager = {a5cd92ff-29be-454c-8d04-d82879fb3f1b}
IID_IVirtualDesktopManager = GUID(
    0xA5CD92FF, 0x29BE, 0x454C, (ctypes.c_ubyte * 8)(0x8D, 0x04, 0xD8, 0x28, 0x79, 0xFB, 0x3F, 0x1B)
)

GetWindowDesktopId_Proto = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.HWND, ctypes.POINTER(GUID))
Release_Proto = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)


class ApplicationWindow:
    """
    Represents a top-level window tracked by the taskbar.
    Holds identity (hwnd) and metadata used for filtering and UI state.
    """

    _vdm_ptr = None
    _vdm_get_id_func = None

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

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.title = self._get_title()
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
            monitor_handle = int(mh) if mh is not None else None
        except Exception:
            pass

        self._refresh_process_info()

        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "class_name": self.class_name,
            "is_active": self.is_active,
            "is_flashing": self.is_flashing,
            "is_cloaked": self._is_cloaked(),
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

    def _get_title(self):
        try:
            return win32gui.GetWindowText(self.hwnd)
        except Exception:
            return ""

    def _get_class_name(self):
        try:
            return win32gui.GetClassName(self.hwnd)
        except Exception:
            return ""

    def _is_cloaked(self) -> bool:
        """Return True if the window is cloaked (hidden by the system, e.g., UWP)."""
        try:
            DWMWA_CLOAKED = 14
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
            ex_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)

            if cls in (
                "ApplicationFrameWindow",
                "Windows.UI.Core.CoreWindow",
                "StartMenuSizingFrame",
                "Shell_LightDismissOverlay",
            ):
                if (ex_style & win32con.WS_EX_WINDOWEDGE) == 0:
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
            extended = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
            is_window = bool(win32gui.IsWindow(self.hwnd))
            is_visible = bool(win32gui.IsWindowVisible(self.hwnd))
            is_toolwindow = bool(extended & win32con.WS_EX_TOOLWINDOW)
            is_appwindow = bool(extended & win32con.WS_EX_APPWINDOW)
            is_noactivate = bool(extended & win32con.WS_EX_NOACTIVATE)
            owner = win32gui.GetWindow(self.hwnd, 4)  # GW_OWNER
            # ITaskList_Deleted property
            is_deleted = False
            try:
                is_deleted = bool(win32gui.GetProp(self.hwnd, "ITaskList_Deleted"))
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

        if not self._is_cloaked():
            return False

        try:
            # Initialize the COM object globally on the first call
            if ApplicationWindow._vdm_ptr is None:
                ptr = ctypes.c_void_p()
                hr = ole32.CoCreateInstance(
                    ctypes.byref(CLSID_VirtualDesktopManager),
                    None,
                    1,
                    ctypes.byref(IID_IVirtualDesktopManager),
                    ctypes.byref(ptr),
                )
                if hr != 0:
                    return True

                vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
                get_id_addr = vtable[0][4]
                ApplicationWindow._vdm_get_id_func = GetWindowDesktopId_Proto(get_id_addr)
                ApplicationWindow._vdm_ptr = ptr

            desktop_id = GUID()
            hr = ApplicationWindow._vdm_get_id_func(
                ApplicationWindow._vdm_ptr, int(self.hwnd), ctypes.byref(desktop_id)
            )

            # Binary check for empty GUID (Null Desktop ID)
            if hr != 0 or bytes(desktop_id) == b"\x00" * 16:
                return True

            return False

        except Exception:
            return True

    def can_minimize(self) -> bool:
        """Return True if the window has a minimize box and is enabled."""
        try:
            styles = win32gui.GetWindowLong(self.hwnd, win32con.GWL_STYLE)
            has_minimize_box = bool(styles & win32con.WS_MINIMIZEBOX)
            try:
                is_enabled = bool(win32gui.IsWindowEnabled(self.hwnd))
            except AttributeError:
                is_enabled = bool(IsWindowEnabled(int(self.hwnd)))
            return has_minimize_box and is_enabled
        except Exception:
            return False

    def is_taskbar_window(self):
        """Main filter: top-level, titled, not cloaked/immersive shell, passes policy and ignore lists."""
        try:
            # Must be a top-level window
            GA_ROOT = 2
            if win32gui.GetAncestor(self.hwnd, GA_ROOT) != self.hwnd:
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

        self.title = self._get_title()
        self.class_name = self._get_class_name()
        # is_active is managed by the window manager

        return old_title != self.title or old_class_name != self.class_name

    def __eq__(self, other):
        """Two ApplicationWindow objects are equal if they wrap the same hwnd."""
        if isinstance(other, ApplicationWindow):
            return self.hwnd == other.hwnd
        return False

    def __hash__(self):
        """Hash by hwnd for use in sets/dicts."""
        return hash(self.hwnd)
