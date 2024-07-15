import os
import logging
from settings import APP_BAR_TITLE, DEBUG
from core.utils.win32.windows import WinEvent
from core.widgets.base import BaseWidget
from core.event_service import EventService
from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap, QImage
from core.validation.widgets.yasb.active_window import VALIDATION_SCHEMA
from core.utils.win32.utilities import get_hwnd_info
from PIL import Image
import win32gui
import win32ui
import win32con
from core.utils.win32.uwp import get_package
import xml.etree.ElementTree as ET
from pathlib import Path
from glob import glob
import locale
import re

pil_logger = logging.getLogger('PIL')
pil_logger.setLevel(logging.INFO)

IGNORED_TITLES = ['', ' ', 'FolderView', 'Program Manager', 'python3', 'pythonw3', 'YasbBar', 'Search', 'Start']
IGNORED_CLASSES = ['WorkerW', 'TopLevelWindowForOverflowXamlIsland', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd']
IGNORED_PROCESSES = ['SearchHost.exe', 'komorebi.exe']
IGNORED_YASB_TITLES = [APP_BAR_TITLE]
IGNORED_YASB_CLASSES = [
    'Qt662QWindowIcon',
    'Qt662QWindowIcon',
    'Qt662QWindowToolSaveBits',
    'Qt662QWindowToolSaveBits'
]
TARGETSIZE_REGEX = re.compile(r'targetsize-([0-9]+)')

try:
    from core.utils.win32.event_listener import SystemEventListener
except ImportError:
    SystemEventListener = None
    logging.warning("Failed to load Win32 System Event Listener")


def get_window_icon(hwnd):
    """Fetch the icon of the window."""
    try:
        hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0)
        if hicon == 0:
            hicon = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)
        if hicon == 0:
            hicon = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)

        if hicon:
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, 32, 32)
            hdc = hdc.CreateCompatibleDC()
            hdc.SelectObject(hbmp)
            hdc.DrawIcon((0, 0), hicon)

            bmpinfo = hbmp.GetInfo()
            bmpstr = hbmp.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGBA',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRA', 0, 1
            )
            return img
        else:
            import win32api
            import ctypes
            import ctypes.wintypes
            import win32process
            try:
                class_name = win32gui.GetClassName(hwnd)
            except:
                return None
            actual_hwnd = 1

            def cb(hwnd, b):
                nonlocal actual_hwnd
                try:
                    class_name = win32gui.GetClassName(hwnd)
                except:
                    class_name = ""
                if "ApplicationFrame" in class_name:
                    return True
                actual_hwnd = hwnd
                return False

            if class_name == "ApplicationFrameWindow":
                win32gui.EnumChildWindows(hwnd, cb, False)
            else:
                actual_hwnd = hwnd

            package = get_package(actual_hwnd)
            if package is None:
                return None
            if package.package_path is None:
                return None
            manifest_path = os.path.join(package.package_path, "AppXManifest.xml")
            if not os.path.exists(manifest_path):
                if DEBUG:
                    print(f"manifest not found {manifest_path}")
                return None
            root = ET.parse(manifest_path)
            velement = root.find(".//VisualElements")
            if velement is None:
                velement = root.find(".//{http://schemas.microsoft.com/appx/manifest/uap/windows10}VisualElements")
            if not velement:
                return None
            if "Square44x44Logo" not in velement.attrib:
                return None
            package_path = Path(package.package_path)
            # logopath = Path(package.package_path) / (velement.attrib["Square44x44Logo"])
            logofile = Path(velement.attrib["Square44x44Logo"])
            logopattern = str(logofile.parent / '**') + '\\' + str(logofile.stem) + '*' + str(logofile.suffix)
            logofiles = glob(logopattern, recursive=True, root_dir=package_path)
            logofiles = [x.lower() for x in logofiles]
            if len(logofiles) == 0:
                return None
            def filter_logos(logofiles, qualifiers, values):
                for qualifier in qualifiers:
                    for value in values:
                        filtered_files = list(filter(lambda x: (qualifier + "-" + value in x), logofiles))
                        if len(filtered_files) > 0:
                            return filtered_files
                return logofiles

            langs = []
            current_lang_code = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if current_lang_code in locale.windows_locale:
                current_lang = locale.windows_locale[current_lang_code].lower().replace('_', '-')
                current_lang_short = current_lang.split('-', 1)[0]
                langs += [current_lang, current_lang_short]
            if "en" not in langs:
                langs += ["en", "en-us"]

            # filter_logos will try to select only the files matching the qualifier values
            # if nothing matches, the list is unchanged
            if langs:
                logofiles = filter_logos(logofiles, ["lang", "language"], langs)
            logofiles = filter_logos(logofiles, ["contrast"], ["standard"])
            logofiles = filter_logos(logofiles, ["alternateform", "altform"], ["unplated"])
            logofiles = filter_logos(logofiles, ["contrast"], ["standard"])
            logofiles = filter_logos(logofiles, ["scale"], ["100", "150", "200"])

            # find the one closest to 48, but bigger
            def target_size_sort(s):
                m = TARGETSIZE_REGEX.search(s)
                if m:
                    size = int(m.group(1))
                    if size < 48:
                        return 5000-size
                    return size - 48
                return 10000

            logofiles.sort(key=target_size_sort)

            img = Image.open(package_path / logofiles[0])
            if not img:
                return None
            return img
    except Exception as e:
        logging.exception("")
        print(f"Error fetching icon: {e}")
        return None



class ActiveWindowWidget(BaseWidget):
    foreground_change = pyqtSignal(int, WinEvent)
    window_name_change = pyqtSignal(int, WinEvent)
    validation_schema = VALIDATION_SCHEMA
    event_listener = SystemEventListener

    def __init__(
            self,
            label: str,
            label_alt: str,
            callbacks: dict[str, str],
            label_no_window: str,
            label_icon: bool,
            label_icon_size: int,
            ignore_window: dict[str, list[str]],
            monitor_exclusive: bool,
            max_length: int,
            max_length_ellipsis: str
    ):
        super().__init__(class_name="active-window-widget")

        self._win_info = None
        self._show_alt = False
        self._label = label
        self._label_alt = label_alt
        self._active_label = label
        self._label_no_window = label_no_window
        self._label_icon = label_icon
        self._label_icon_size = label_icon_size
        self._monitor_exclusive = monitor_exclusive
        self._max_length = max_length
        self._max_length_ellipsis = max_length_ellipsis
        self._event_service = EventService()
        self._update_retry_count = 0
 
        self._window_title_text = QLabel()
        self._window_title_text.setProperty("class", "label")
        self._window_title_text.setText(self._label_no_window)

        if self._label_icon:
            self._window_icon_label = QLabel()
            self._window_icon_label.setProperty("class", "label icon")
            self._window_icon_label.setText(self._label_no_window)

        self._ignore_window = ignore_window
        self._ignore_window['classes'] += IGNORED_CLASSES
        self._ignore_window['processes'] += IGNORED_PROCESSES
        self._ignore_window['titles'] += IGNORED_TITLES
        self._icon_cache = dict()
        if self._label_icon:
            self.widget_layout.addWidget(self._window_icon_label)
        self.widget_layout.addWidget(self._window_title_text)
        self.register_callback("toggle_label", self._toggle_title_text)
        if not callbacks:
            callbacks = {
                "on_left": "toggle_label",
                "on_middle": "do_nothing",
                "on_right": "toggle_label"
            }

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']

        self.foreground_change.connect(self._on_focus_change_event)
        self._event_service.register_event(WinEvent.EventSystemForeground, self.foreground_change)
        self._event_service.register_event(WinEvent.EventSystemMoveSizeEnd, self.foreground_change)

        self.window_name_change.connect(self._on_window_name_change_event)
        self._event_service.register_event(WinEvent.EventObjectNameChange, self.window_name_change)
        self._event_service.register_event(WinEvent.EventObjectStateChange, self.window_name_change)

    def _toggle_title_text(self) -> None:
        self._show_alt = not self._show_alt
        self._active_label = self._label_alt if self._show_alt else self._label
        self._update_text()

    def _on_focus_change_event(self, hwnd: int, event: WinEvent) -> None:
        win_info = get_hwnd_info(hwnd)
        if (not win_info or not hwnd or
                not win_info['title'] or
                win_info['title'] in IGNORED_YASB_TITLES or
                win_info['class_name'] in IGNORED_YASB_CLASSES):
            return

        monitor_name = win_info['monitor_info'].get('device', None)

        if self._monitor_exclusive and self.screen().name() != monitor_name and win_info.get('monitor_hwnd', 'Unknown') != self.monitor_hwnd:
            self.hide()
        else:
            self.show()
            self._update_window_title(hwnd, win_info, event)

        # Check if the window title is in the list of ignored titles
        if(win_info['title'] in IGNORED_TITLES):
            self.hide()

    def _on_window_name_change_event(self, hwnd: int, event: WinEvent) -> None:
        if self._win_info and hwnd == self._win_info["hwnd"]:
            self._on_focus_change_event(hwnd, event)

    def _update_window_title(self, hwnd: int, win_info: dict, event: WinEvent) -> None:
        try:
            if hwnd != win32gui.GetForegroundWindow():
                return
            title = win_info['title']
            process = win_info['process']
            pid = process["pid"]
            class_name = win_info['class_name']

            if self._label_icon: 
                if event != WinEvent.WinEventOutOfContext:
                    self._update_retry_count = 0
                if (hwnd, title, pid) in self._icon_cache:
                    icon_img = self._icon_cache[(hwnd, title, pid)]
                else:
                    icon_img = get_window_icon(hwnd)
                    if icon_img:
                        icon_img = icon_img.resize((self._label_icon_size, self._label_icon_size), Image.LANCZOS).convert("RGBA")
                    else:
                        # UWP apps might need a moment to start under ApplicationFrameHost
                        # So we delay the detection, but only do it once.
                        if process["name"] == "ApplicationFrameHost.exe":
                            if self._update_retry_count < 10:
                                self._update_retry_count += 1
                                QTimer.singleShot(500, lambda: self._update_window_title(hwnd, win_info, WinEvent.WinEventOutOfContext))
                                return
                            else:
                                self._update_retry_count = 0

                    if not DEBUG:
                        self._icon_cache[(hwnd, title, pid)] = icon_img
                if icon_img:
                    qimage = QImage(icon_img.tobytes(), icon_img.width, icon_img.height, QImage.Format.Format_RGBA8888)
                    self.pixmap = QPixmap.fromImage(qimage)
                else:
                    self.pixmap = None


            if (title.strip() in self._ignore_window['titles'] or
                    class_name in self._ignore_window['classes'] or
                    process in self._ignore_window['processes']):
                return
            else:
                if self._max_length and len(win_info['title']) > self._max_length:
                    truncated_title = f"{win_info['title'][:self._max_length]}{self._max_length_ellipsis}"
                    win_info['title'] = truncated_title
                    self._window_title_text.setText(self._label_no_window)
                    self._window_icon_label.setText(self._label_no_window)
                    
                self._win_info = win_info
                self._update_text()

                if self._window_title_text.isHidden():
                    self._window_title_text.show()
        except Exception:
            logging.exception(
                f"Failed to update active window title for window with HWND {hwnd} emitted by event {event}"
            )

    def _update_text(self):
        try:
            self._window_title_text.setText(self._active_label.format(win=self._win_info))
            if self._label_icon:
                if self.pixmap: 
                    self._window_icon_label.show()
                    self._window_icon_label.setPixmap(self.pixmap)
                else:
                    self._window_icon_label.hide()
        except Exception:
            self._window_title_text.setText(self._active_label)