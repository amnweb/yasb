"""YASB wallpaper transition engine.

Plays a short animation over the desktop when the wallpaper changes, then hands
the new image to Windows. The overlay is a frameless widget parented to WorkerW
so it draws above the wallpaper and below the desktop icons.

Scaling and positioning have to match what Windows does. If they do not, the
last frame of the animation sits on different pixels than the wallpaper Windows
settles on, and the desktop jumps when the overlay closes. The rules that are
not obvious:

  * Windows lays out its own transcoded copy, not the file on disk, and shrinks
    it for very large images. Centre and tile never rescale, so for those the
    transcoded size is the layout.
  * Fill and span anchor vertically at a third of the overflow, not a half.
  * Landscape images wider than 2.22 are spanned across all monitors in fit and
    fill. Windows calls this autospan.
  * Integer division truncates toward zero, not floor.

Verified against screenshots of the real desktop on Windows 11 26100.
"""

import ctypes
import logging
import math
import os
import winreg
from ctypes import wintypes

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QThread, QTimeLine, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap, QPolygonF
from PyQt6.QtWidgets import QApplication, QWidget
from win32con import (
    GWL_EXSTYLE,
    GWL_STYLE,
    SWP_FRAMECHANGED,
    SWP_NOACTIVATE,
    WM_DESTROY,
    WS_CHILD,
    WS_EX_LAYERED,
    WS_POPUP,
)

logger = logging.getLogger("wallpaper_engine")
user32 = ctypes.WinDLL("user32", use_last_error=True)

HWND = wintypes.HWND
ULONG_PTR = ctypes.c_ulonglong
LONG_PTR = ctypes.c_ssize_t

WM_SPAWN_WORKER = 0x052C
HWND_TOP = HWND(0)

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)
EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)

SetWindowLongPtr = user32.SetWindowLongPtrW
GetWindowLongPtr = user32.GetWindowLongPtrW
SetWindowLongPtr.restype = LONG_PTR
SetWindowLongPtr.argtypes = [HWND, ctypes.c_int, LONG_PTR]
GetWindowLongPtr.restype = LONG_PTR
GetWindowLongPtr.argtypes = [HWND, ctypes.c_int]

user32.FindWindowW.restype = HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]

user32.FindWindowExW.restype = HWND
user32.FindWindowExW.argtypes = [HWND, HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]

user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]

user32.EnumWindows.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]

user32.EnumChildWindows.restype = wintypes.BOOL
user32.EnumChildWindows.argtypes = [HWND, EnumChildProc, wintypes.LPARAM]

user32.SetParent.restype = HWND
user32.SetParent.argtypes = [HWND, HWND]

user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]

user32.SendMessageTimeoutW.restype = wintypes.LPARAM
user32.SendMessageTimeoutW.argtypes = [
    HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.POINTER(ULONG_PTR),
]

user32.ShowWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]

user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [HWND, ctypes.POINTER(wintypes.RECT)]

MonitorEnumProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
)

user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.EnumDisplayMonitors.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.RECT), MonitorEnumProc, wintypes.LPARAM]


def _enum_physical_monitors() -> list[tuple[int, int, int, int]]:
    """Return physical-pixel rects (left, top, right, bottom) for every monitor."""
    rects: list[tuple[int, int, int, int]] = []

    @MonitorEnumProc
    def _cb(hmon, hdc, lprect, _):
        r = lprect.contents
        rects.append((r.left, r.top, r.right, r.bottom))
        return True

    user32.EnumDisplayMonitors(None, None, _cb, 0)
    return rects


def _transcoded_wallpaper_path() -> str:
    """Path to Windows cached transcoded copy of the current wallpaper."""
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, r"Microsoft\Windows\Themes\TranscodedWallpaper")


def _read_fit_mode() -> str:
    """Read wallpaper fit mode from HKCU\\Control Panel\\Desktop (registry)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
        try:
            tile = winreg.QueryValueEx(key, "TileWallpaper")[0]
            style = winreg.QueryValueEx(key, "WallpaperStyle")[0]
        finally:
            winreg.CloseKey(key)
        if str(tile) == "1":
            return "tile"
        style = str(style)
        if style == "0":
            return "center"
        if style == "2":
            return "stretch"
        if style == "6":
            return "fit"
        if style == "10":
            return "fill"
        if style == "22":
            return "span"
        return "fill"
    except Exception:
        return "fill"


def _read_background_color() -> QColor:
    """Read the Windows desktop background color from the registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Colors")
        try:
            bg_str = winreg.QueryValueEx(key, "Background")[0]
        finally:
            winreg.CloseKey(key)
        r, g, b = map(int, bg_str.split())
        return QColor(r, g, b)
    except Exception:
        return QColor(0, 0, 0)


def _panorama_threshold(landscape: bool) -> float:
    """Aspect ratio past which Windows spans a wallpaper across the monitors.

    Stored as a DWORD in thousandths, defaulting to 2.22 for landscape images and
    1.0 for portrait ones. There is no upper bound; the wider the image, the more
    certainly it spans. An earlier version used a 2.2 to 2.5 range, which is why
    3840x1080 dual-monitor wallpapers were cropped on both screens instead of
    spanning.
    """
    default = 2.22 if landscape else 1.0
    name = "PanoramaThreshold" if landscape else "PanoramaPortraitThreshold"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
        try:
            value = int(winreg.QueryValueEx(key, name)[0])
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        # The usual case. Windows only writes these when someone overrides them
        # and otherwise falls back to the same defaults used here.
        return default
    except (OSError, ValueError) as exc:
        logger.debug("Could not read %s (%s), using %s", name, exc, default)
        return default
    return value / 1000.0 if value else default


def _monitors_tile_a_rectangle(areas) -> bool:
    """Whether the monitors cover their bounding box exactly, with no step or gap.

    Windows builds a region from the monitor rects and refuses to span unless
    that region comes back as a single rectangle, and unless every monitor is
    the same size. Two 1920x1080 screens stacked with even a few pixels of
    horizontal offset form a staircase, not a rectangle, and are enough to turn
    spanning off.

    Monitors never overlap, so comparing the covered area against the bounding
    box is an exact test for it.
    """
    if not areas:
        return False
    if len({(dw, dh) for _, _, dw, dh, _ in areas}) != 1:
        return False
    left = min(dx for dx, _, _, _, _ in areas)
    top = min(dy for _, dy, _, _, _ in areas)
    right = max(dx + dw for dx, _, dw, _, _ in areas)
    bottom = max(dy + dh for _, dy, _, dh, _ in areas)
    covered = sum(dw * dh for _, _, dw, dh, _ in areas)
    return covered == (right - left) * (bottom - top)


def _wants_autospan(px: QPixmap, areas) -> bool:
    """Whether Windows would turn this fit/fill into a span.

    Windows calls this autospan. A landscape image wider than the panorama
    threshold is no longer laid out per monitor and is treated as a span, while
    keeping the original mode's cover/contain and anchor. Portrait images never
    qualify.

    The arrangement has to be spannable as well, which is what
    _monitors_tile_a_rectangle covers. Leaving that check out is why wide
    images were spanned across screens that Windows lays out one at a time.
    """
    if len(areas) < 2 or px.isNull() or px.height() <= 0:
        return False
    if not _monitors_tile_a_rectangle(areas):
        return False
    if px.height() > px.width():
        return False
    return px.width() / px.height() > _panorama_threshold(landscape=True)


def _transcode_limits() -> tuple[int, int] | None:
    """The two DWORDs the wallpaper transcoder reads before resizing anything.

    Stored under HKCU\\Control Panel\\Desktop. These are not the current display
    size: Windows only ever raises them, so they are a high-water mark of the
    largest desktop ever attached and do not drop back when a monitor is
    unplugged. They differ from machine to machine, so they are read rather than
    hardcoded. If either read fails Windows skips the resize entirely, which is
    what returning None means here.
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
        try:
            max_virtual_desktop = int(winreg.QueryValueEx(key, "MaxVirtualDesktopDimension")[0])
            max_monitor = int(winreg.QueryValueEx(key, "MaxMonitorDimension")[0])
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        # Windows has not recorded them yet; it skips the resize in that case too.
        return None
    except (OSError, ValueError) as exc:
        logger.debug("Could not read the wallpaper transcode limits (%s)", exc)
        return None
    if max_virtual_desktop > 0 and max_monitor > 0:
        return max_virtual_desktop, max_monitor
    return None


def _transcode_size(iw: int, ih: int) -> tuple[int, int]:
    """The size Windows transcodes an *iw* x *ih* wallpaper to.

    Windows lays out its own transcoded copy and shrinks it for very large
    images. Two details are easy to get wrong: the limit scales with the image's
    aspect ratio, so a wide panorama is left alone where a square image of the
    same area is not, and each axis is derived from the limit separately rather
    than by one shared factor.

    Verified against thirteen image sizes, including the cases where those two
    details disagree by a pixel.
    """
    limits = _transcode_limits()
    if limits is None or iw <= 0 or ih <= 0:
        return iw, ih

    max_virtual_desktop, max_monitor = limits
    aspect = iw / ih
    limit = int(max(max_monitor * aspect, max_monitor / aspect))
    limit = max(max_virtual_desktop, limit)
    if iw <= limit and ih <= limit:
        return iw, ih

    # Both sides round down, never to nearest, so int() is correct here. A
    # 3900x3860 image comes out 3879x3839; rounding would give 3880x3840 and the
    # tile grid would then drift a pixel on every repeat.
    return (
        max(1, min(limit, int(limit / ih * iw))),
        max(1, min(limit, int(limit / iw * ih))),
    )


def _apply_transcode_cap(px: QPixmap) -> QPixmap:
    """Shrink *px* to the size Windows would have transcoded it to."""
    w, h = _transcode_size(px.width(), px.height())
    if (w, h) == (px.width(), px.height()):
        return px
    return px.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)


def _trunc_div(a: int, b: int) -> int:
    """Divide the way C does, truncating toward zero.

    Not interchangeable with //. Windows truncates, Python floors, and the two
    differ by a pixel whenever the numerator is negative, which is every case
    where the image overflows the monitor.
    """
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def _locate_workerw() -> int:
    """Find the WorkerW window that sits behind desktop icons."""
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        logger.warning("Could not locate Progman. Wallpaper animation skipped.")
        return 0
    user32.SendMessageTimeoutW(progman, WM_SPAWN_WORKER, 0, 0, 0, 1000, ctypes.byref(ULONG_PTR()))
    worker = HWND()

    @EnumChildProc
    def _child_proc(hwnd, _):
        nonlocal worker
        if worker:
            return False
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, len(buf))
        if buf.value == "WorkerW":
            worker = hwnd
            return False
        return True

    user32.EnumChildWindows(HWND(progman), _child_proc, 0)

    if not worker:

        @EnumWindowsProc
        def _enum_proc(hwnd, _):
            nonlocal worker
            if worker:
                return False
            if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
                candidate = user32.FindWindowExW(None, hwnd, "WorkerW", None)
                if candidate:
                    worker = candidate
                    return False
            return True

        user32.EnumWindows(_enum_proc, 0)

    if not worker:
        logger.warning("Could not locate WorkerW. Wallpaper animation skipped.")
        return 0
    user32.ShowWindow(worker, 5)
    return worker


def _attach_to_workerw(widget: QWidget) -> bool:
    """Parent *widget* to WorkerW and compute per-monitor screen areas."""
    worker = _locate_workerw()
    if not worker:
        return False
    hwnd = HWND(int(widget.winId()))

    exstyle = GetWindowLongPtr(hwnd, GWL_EXSTYLE)

    SetWindowLongPtr(hwnd, GWL_EXSTYLE, LONG_PTR(exstyle & ~WS_EX_LAYERED))
    user32.SetParent(hwnd, worker)
    SetWindowLongPtr(hwnd, GWL_EXSTYLE, LONG_PTR(exstyle))

    style = GetWindowLongPtr(hwnd, GWL_STYLE)
    SetWindowLongPtr(hwnd, GWL_STYLE, LONG_PTR((style | WS_CHILD) & ~WS_POPUP))

    wr = wintypes.RECT()
    user32.GetWindowRect(worker, ctypes.byref(wr))
    ww, wh = wr.right - wr.left, wr.bottom - wr.top
    dpr = widget.devicePixelRatioF() or 1.0

    areas = []
    for ml, mt, mr, mb in _enum_physical_monitors():
        areas.append(
            (
                int(round((ml - wr.left) / dpr)),
                int(round((mt - wr.top) / dpr)),
                int(round((mr - ml) / dpr)),
                int(round((mb - mt) / dpr)),
                dpr,
            )
        )
    widget.set_screen_areas(areas)

    user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, ww, wh, SWP_NOACTIVATE | SWP_FRAMECHANGED)
    return True


class _ImageLoader(QThread):
    """Background thread to load new and old wallpaper images without blocking the UI."""

    loaded = pyqtSignal(object, object)

    def __init__(self, new_path: str, old_path: str):
        super().__init__()
        self.new_path = new_path
        self.old_path = old_path

    def run(self):
        new_img = QImage(self.new_path)
        old_img = QImage(self.old_path)
        self.loaded.emit(new_img, old_img)


class WallpaperEngine(QWidget):
    _ANIMATION_MS = 1200
    _FRAME_MS = 16

    finished = pyqtSignal()

    def __init__(self, image_path: str, animation: str = "circle") -> None:
        super().__init__()
        self._image_path = image_path
        self._animation = animation
        self._progress = 0.0
        self._committed = False
        self._areas: list[tuple[int, int, int, int, float]] = []
        self._dpr = 1.0
        self._per_screen_scaled_old: list[tuple[QPixmap, int, int]] = []
        self._per_screen_scaled_new: list[tuple[QPixmap, int, int]] = []
        self.fit_mode = _read_fit_mode()
        self._bg_color = _read_background_color()
        self._pixmap_new = QPixmap()
        self._pixmap_old = QPixmap()
        self._resources_freed = False

        self.setGeometry(QApplication.primaryScreen().geometry())
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.winId()

        self._timeline = QTimeLine(self._ANIMATION_MS, self)
        self._timeline.setUpdateInterval(self._FRAME_MS)
        self._timeline.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._timeline.valueChanged.connect(self._on_progress)
        self._timeline.finished.connect(self._on_finished)

    def start(self) -> None:
        """Load images asynchronously, then attach to WorkerW and begin animation."""
        self._wallpaper_loader = _ImageLoader(self._image_path, _transcoded_wallpaper_path())
        self._wallpaper_loader.loaded.connect(self._on_images_loaded)
        self._wallpaper_loader.start()

    def _on_images_loaded(self, new_img: QImage, old_img: QImage) -> None:
        self._pixmap_new = QPixmap.fromImage(new_img)
        self._pixmap_old = QPixmap.fromImage(old_img)

        # If either image fails to load, skip animation and let caller commit immediately
        if self._pixmap_new.isNull() or self._pixmap_old.isNull():
            self.finished.emit()
            self.deleteLater()
            return

        self.setWindowOpacity(0.0)
        if not _attach_to_workerw(self):
            self.finished.emit()
            self.deleteLater()
            return

        self.show()
        QTimer.singleShot(0, self._start_fade_in)

    def _start_fade_in(self) -> None:
        self._fade_timeline = QTimeLine(50, self)
        self._fade_timeline.setUpdateInterval(self._FRAME_MS)
        self._fade_timeline.valueChanged.connect(self.setWindowOpacity)
        self._fade_timeline.finished.connect(self._on_fade_in_done)
        self._fade_timeline.start()

    def _on_fade_in_done(self) -> None:
        self.setWindowOpacity(1.0)
        self._timeline.start()

    def set_screen_areas(self, areas: list[tuple[int, int, int, int, float]]) -> None:
        if areas:
            min_x = min(dx for dx, _, _, _, _ in areas)
            min_y = min(dy for _, dy, _, _, _ in areas)
            self._areas = [(dx - min_x, dy - min_y, dw, dh, dpr) for dx, dy, dw, dh, dpr in areas]
            total_w = max(dx + dw for dx, _, dw, _, _ in self._areas)
            total_h = max(dy + dh for _, dy, _, dh, _ in self._areas)
            self.resize(total_w, total_h)
        else:
            self._areas = areas
        self._dpr = areas[0][4] if areas else (self.devicePixelRatioF() or 1.0)
        self._per_screen_scaled_new = self._compute_per_screen_scaled(self._pixmap_new)
        self._per_screen_scaled_old = self._compute_per_screen_scaled(self._pixmap_old)

    def _compute_per_screen_scaled(self, px: QPixmap) -> list[tuple[QPixmap, int, int]]:
        """Compute (pixmap, offset_x, offset_y) per screen area for the given source image."""
        areas = self._areas
        if px.isNull():
            return []
        # Lay out what Windows lays out: its transcoded copy, not the file.
        px = _apply_transcode_cap(px)
        dpr = self._dpr
        if dpr != 1.0:
            areas = [(*(int(round(v * dpr)) for v in (dx, dy, dw, dh)), d) for dx, dy, dw, dh, d in areas]
            px = QPixmap(px)
            px.setDevicePixelRatio(dpr)
        vw = max(dx + dw for dx, _, dw, _, _ in areas) if areas else int(round(self.width() * dpr))
        vh = max(dy + dh for _, dy, _, dh, _ in areas) if areas else int(round(self.height() * dpr))

        mode = self.fit_mode
        # Only span and tile are laid out against the virtual desktop; Windows
        # computes every other mode independently per monitor.
        if mode == "span":
            return self._scale_span(px, areas, vw, vh)
        if mode == "tile":
            return self._scale_tile(px, areas, vw, vh)
        if mode in ("fill", "fit") and _wants_autospan(px, areas):
            # Windows does not lay this out per monitor: it rewrites the position
            # to span and carries on. The original mode still decides cover vs
            # contain and the vertical anchor, so pass it through.
            return self._scale_span(px, areas, vw, vh, cover=mode == "fill")
        return [self._scale_for_screen(px, dw, dh) for _, _, dw, dh, _ in areas]

    #  Per-mode scaling helpers
    def _cover_or_contain(self, px: QPixmap, dw: int, dh: int, cover: bool) -> QPixmap:
        """Scale to cover or contain *dw* x *dh*, rounding the way Windows rounds.

        Windows works the ratios out in single precision, takes max for cover and
        min for contain, then adds a half to each axis before truncating. Done
        here rather than through QPixmap.scaled, which rounds differently and
        lands a pixel off.
        """
        ratios = (dw / px.width(), dh / px.height())
        s = max(ratios) if cover else min(ratios)
        return px.scaled(
            int(px.width() * s + 0.5),
            int(px.height() * s + 0.5),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _scale_span(self, px: QPixmap, areas, vw: int, vh: int, cover: bool = True) -> list[tuple[QPixmap, int, int]]:
        """One image across the whole virtual desktop, each monitor clips its part.

        *cover* is false only when a fit has been autospanned. Windows keeps the
        original position internally after switching to span, so a spanned fit
        still contains rather than covers, and anchors at a half instead of a
        third.
        """
        scaled = self._cover_or_contain(px, vw, vh, cover=cover)
        ox = _trunc_div(vw - scaled.width(), 2)
        oy = _trunc_div(vh - scaled.height(), 3 if cover else 2)
        return [(scaled, ox - dx, oy - dy) for dx, dy, _, _, _ in areas]

    def _scale_tile(self, px: QPixmap, areas, vw: int, vh: int) -> list[tuple[QPixmap, int, int]]:
        """Repeat the image at its native size from the virtual desktop origin.

        Windows never scales a tiled wallpaper, whatever its size, and the grid
        runs across the whole virtual desktop instead of restarting on each
        monitor. Tiling per monitor lines the seam up wrong.
        """
        iw, ih = px.width(), px.height()
        if iw <= 0 or ih <= 0:
            return [(px, 0, 0) for _ in areas]

        src = QPixmap(px)
        src.setDevicePixelRatio(1.0)
        tiled = QPixmap(vw, vh)
        tiled.fill(self._bg_color)
        tp = QPainter(tiled)
        for ty in range(0, vh, ih):
            for tx in range(0, vw, iw):
                tp.drawPixmap(tx, ty, src)
        tp.end()
        tiled.setDevicePixelRatio(self._dpr)
        return [(tiled, -dx, -dy) for dx, dy, _, _, _ in areas]

    def _scale_for_screen(self, px: QPixmap, sw: int, sh: int) -> tuple[QPixmap, int, int]:
        """Lay one image out on one monitor: centre, stretch, fit or fill.

        Centre never scales. An oversized image is cropped by the monitor rect,
        a smaller one leaves the desktop background showing around it.

        Fill anchors vertically at a third of the overflow rather than a half.
        This is deliberate and matches Windows; it is why a filled photo keeps
        more of its top than its bottom.
        """
        mode = self.fit_mode
        if mode == "stretch":
            scaled = px.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            return scaled, 0, 0
        if mode in ("fill", "fit"):
            scaled = self._cover_or_contain(px, sw, sh, cover=mode == "fill")
        else:
            scaled = px

        ox = _trunc_div(sw - scaled.width(), 2)
        oy = _trunc_div(sh - scaled.height(), 3 if mode == "fill" else 2)
        return scaled, ox, oy

    def _on_progress(self, value: float) -> None:
        self._progress = value
        self.update()

    def _on_finished(self) -> None:
        self._progress = 1.0
        self.update()
        if not self._committed:
            self._committed = True
            self.finished.emit()

    def _clip_path_for_monitor(self, dx: int, dy: int, dw: int, dh: int, t: float) -> QPainterPath:
        """Reveal shape for the new wallpaper."""
        if t >= 1.0:
            r = QRectF(float(dx), float(dy), float(dw), float(dh))
            p = QPainterPath()
            p.addRect(r)
            return p

        if self._animation == "circle":
            return self._clip_circle(dx, dy, dw, dh, t)
        if self._animation == "slide_top":
            return self._clip_slide_top(dx, dy, dw, dh, t)
        if self._animation == "diamond":
            return self._clip_diamond(dx, dy, dw, dh, t)
        if self._animation == "split":
            return self._clip_split(dx, dy, dw, dh, t)
        r = QRectF(float(dx), float(dy), float(dw), float(dh))
        p = QPainterPath()
        p.addRect(r)
        return p

    def _clip_circle(self, dx: int, dy: int, dw: int, dh: int, t: float) -> QPainterPath:
        cx, cy = dx + dw // 2, dy + dh // 2
        r = max(
            1.0,
            max(
                math.hypot(cx - dx, cy - dy),
                math.hypot(cx - (dx + dw), cy - dy),
                math.hypot(cx - dx, cy - (dy + dh)),
                math.hypot(cx - (dx + dw), cy - (dy + dh)),
            )
            * t,
        )
        path = QPainterPath()
        path.addEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        return path

    def _clip_diamond(self, dx: int, dy: int, dw: int, dh: int, t: float) -> QPainterPath:
        cx, cy = dx + dw // 2, dy + dh // 2
        max_r = max(
            abs(cx - dx) + abs(cy - dy),
            abs(cx - (dx + dw)) + abs(cy - dy),
            abs(cx - dx) + abs(cy - (dy + dh)),
            abs(cx - (dx + dw)) + abs(cy - (dy + dh)),
        )
        rr = max(1.0, float(max_r) * t)
        poly = QPolygonF(
            [
                QPointF(cx, cy - rr),
                QPointF(cx + rr, cy),
                QPointF(cx, cy + rr),
                QPointF(cx - rr, cy),
            ]
        )
        path = QPainterPath()
        path.addPolygon(poly)
        return path

    def _clip_split(self, dx: int, dy: int, dw: int, dh: int, t: float) -> QPainterPath:
        half = int(dh / 2 * t)
        top = QPainterPath()
        top.addRect(QRectF(float(dx), float(dy), float(dw), float(max(1, half))))
        bot = QPainterPath()
        bot.addRect(QRectF(float(dx), float(dy + dh - max(1, half)), float(dw), float(max(1, half))))
        return top.united(bot)

    def _clip_slide_top(self, dx: int, dy: int, dw: int, dh: int, t: float) -> QPainterPath:
        cx = dx + dw // 2
        max_r = math.hypot(dw / 2, dh)
        r = max(1.0, max_r * t)
        circ = QPainterPath()
        circ.addEllipse(QRectF(cx - r, dy - r, 2 * r, 2 * r))
        rect = QPainterPath()
        rect.addRect(QRectF(float(dx), float(dy), float(dw), float(dh)))
        return circ.intersected(rect)

    def paintEvent(self, _) -> None:
        p = QPainter(self)

        t = self._progress

        for i, (dx, dy, dw, dh, _) in enumerate(self._areas):
            clip = self._clip_path_for_monitor(dx, dy, dw, dh, t)

            if t < 1.0:
                if i < len(self._per_screen_scaled_old):
                    scaled_o, ox_o, oy_o = self._per_screen_scaled_old[i]
                    p.save()
                    p.setClipRect(QRectF(float(dx), float(dy), float(dw), float(dh)))

                    # Fill old area background
                    p.fillRect(QRectF(float(dx), float(dy), float(dw), float(dh)), self._bg_color)
                    p.drawPixmap(QPointF(dx + ox_o / self._dpr, dy + oy_o / self._dpr), scaled_o)
                    p.restore()
                else:
                    p.fillRect(QRectF(float(dx), float(dy), float(dw), float(dh)), self._bg_color)

            if i >= len(self._per_screen_scaled_new):
                continue
            scaled_n, ox_n, oy_n = self._per_screen_scaled_new[i]
            p.save()
            p.setClipPath(clip, Qt.ClipOperation.IntersectClip)
            p.setClipRect(QRectF(float(dx), float(dy), float(dw), float(dh)), Qt.ClipOperation.IntersectClip)

            # Fill new area background
            p.fillRect(QRectF(float(dx), float(dy), float(dw), float(dh)), self._bg_color)
            p.drawPixmap(QPointF(dx + ox_n / self._dpr, dy + oy_n / self._dpr), scaled_n)
            p.restore()

    def _free_resources(self):
        if getattr(self, "_resources_freed", True):
            return
        self._resources_freed = True

        for tl in (self._timeline, getattr(self, "_fade_timeline", None)):
            if tl and tl.state() != QTimeLine.State.NotRunning:
                tl.stop()

        self._pixmap_new = QPixmap()
        self._pixmap_old = QPixmap()
        self._per_screen_scaled_new.clear()
        self._per_screen_scaled_old.clear()

        wl = getattr(self, "_wallpaper_loader", None)
        if wl is not None:
            try:
                wl.loaded.disconnect()
            except TypeError, RuntimeError:
                pass
            if wl.isRunning():
                wl.quit()
                wl.wait(1000)
            self._wallpaper_loader = None

    def nativeEvent(self, _, message):
        msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
        if msg.message == WM_DESTROY:
            self._free_resources()
            self.deleteLater()
            return True, 0
        return False, 0

    def closeEvent(self, event) -> None:
        self._free_resources()
        super().closeEvent(event)
