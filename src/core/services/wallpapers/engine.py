"""YASB wallpaper transition engine.

Plays a short animation over the desktop when the wallpaper changes, then hands
the new image to Windows. The overlay is a window parented to WorkerW so it
draws above the wallpaper and below the desktop icons. Its visuals belong to the
shared compositor, and the Desktop Window Manager plays their animation, so it
keeps going while the GUI thread is busy and other windows animate smoothly.

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
from ctypes import COMError, wintypes
from datetime import timedelta
from functools import cache
from typing import Any, override

from PyQt6.QtCore import QCoreApplication, QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QImageReader, QPainter
from winrt.windows.ui.composition import CompositionClip, Compositor
from winrt.windows.ui.composition.desktop import DesktopWindowTarget
from winrt.windows.ui.composition.interop import create_desktop_window_target

from core.utils.win32.bindings.kernel32 import GetLastError, GetModuleHandle
from core.utils.win32.bindings.user32 import (
    MONITORENUMPROC,
    CreateWindowEx,
    DefWindowProc,
    DestroyWindow,
    EnumChildWindows,
    EnumWindows,
    FindWindow,
    FindWindowEx,
    GetClassName,
    GetWindowLongPtr,
    GetWindowRect,
    SendMessageTimeout,
    SetParent,
    SetWindowLongPtr,
    SetWindowPos,
    ShowWindow,
    user32,
)
from core.utils.win32.composition import compositor, drawing_surface
from core.utils.win32.constants import (
    GWL_EXSTYLE,
    GWL_STYLE,
    HWND_TOP,
    SW_SHOW,
    SW_SHOWNA,
    SWP_FRAMECHANGED,
    SWP_NOACTIVATE,
    WM_DESTROY,
    WS_CHILD,
    WS_EX_LAYERED,
    WS_EX_NOREDIRECTIONBITMAP,
    WS_POPUP,
)
from core.utils.win32.registry_keys import COLORS_KEY, DESKTOP_KEY
from core.utils.win32.structs import WNDCLASS, WNDENUMPROC, WNDPROC
from core.utils.win32.typecheck import CPointer
from core.utils.win32.undocumented import WM_SPAWN_WORKER

logger = logging.getLogger("wallpaper_engine")

TRANSITION_WINDOW_CLASS = "YasbWallpaperTransition"

# (x, y, width, height, device pixel ratio) of one monitor, in logical pixels.
type ScreenArea = tuple[int, int, int, int, float]


def _enum_physical_monitors() -> list[tuple[int, int, int, int]]:
    """Return physical-pixel rects (left, top, right, bottom) for every monitor."""
    rects: list[tuple[int, int, int, int]] = []

    @MONITORENUMPROC
    def _cb(hmon: int, hdc: int, lprect: CPointer[wintypes.RECT], _: int) -> bool:
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
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, DESKTOP_KEY)
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
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, COLORS_KEY)
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
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, DESKTOP_KEY)
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


def _monitors_tile_a_rectangle(areas: list[ScreenArea]) -> bool:
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


def _wants_autospan(px: QImage, areas: list[ScreenArea]) -> bool:
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
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, DESKTOP_KEY)
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


def _apply_transcode_cap(px: QImage) -> QImage:
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
    progman = FindWindow("Progman", None)
    if not progman:
        logger.warning("Could not locate Progman. Wallpaper animation skipped.")
        return 0
    SendMessageTimeout(progman, WM_SPAWN_WORKER, 0, 0, 0, 1000, None)
    worker = 0

    @WNDENUMPROC
    def _child_proc(hwnd: int, _: int) -> bool:
        nonlocal worker
        if worker:
            return False
        if GetClassName(hwnd) == "WorkerW":
            worker = hwnd
            return False
        return True

    EnumChildWindows(progman, _child_proc, 0)

    if not worker:

        @WNDENUMPROC
        def _enum_proc(hwnd: int, _: int) -> bool:
            nonlocal worker
            if worker:
                return False
            if FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None):
                candidate = FindWindowEx(0, hwnd, "WorkerW", None)
                if candidate:
                    worker = candidate
                    return False
            return True

        EnumWindows(_enum_proc, 0)

    if not worker:
        logger.warning("Could not locate WorkerW. Wallpaper animation skipped. (Windows OS animation must be enabled.)")
        return 0
    ShowWindow(worker, SW_SHOW)
    return worker


def _attach_to_workerw(hwnd: int) -> list[ScreenArea]:
    """Parent window *hwnd* to WorkerW, size it to WorkerW, and return each monitor's area in it, measured from the
    top-left monitor corner; none without a WorkerW."""
    worker = _locate_workerw()
    if not worker:
        return []

    # A child before SetParent, as its docs ask: made one after, the window becomes the active and focused window of
    # YASB's GUI thread, and YASB's own windows, the bar and the gallery, lose activation and keyboard focus to it
    style = GetWindowLongPtr(hwnd, GWL_STYLE)
    SetWindowLongPtr(hwnd, GWL_STYLE, (style | WS_CHILD) & ~WS_POPUP)

    exstyle = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
    SetWindowLongPtr(hwnd, GWL_EXSTYLE, exstyle & ~WS_EX_LAYERED)
    SetParent(hwnd, worker)
    SetWindowLongPtr(hwnd, GWL_EXSTYLE, exstyle)

    wr = wintypes.RECT()
    GetWindowRect(worker, ctypes.byref(wr))
    ww, wh = wr.right - wr.left, wr.bottom - wr.top
    screen = QGuiApplication.primaryScreen()
    dpr = (screen.devicePixelRatio() if screen is not None else 1.0) or 1.0

    areas: list[ScreenArea] = []
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

    SetWindowPos(hwnd, HWND_TOP, 0, 0, ww, wh, SWP_NOACTIVATE | SWP_FRAMECHANGED)
    if not areas:
        return []
    min_x = min(dx for dx, _, _, _, _ in areas)
    min_y = min(dy for _, dy, _, _, _ in areas)
    return [(dx - min_x, dy - min_y, dw, dh, d) for dx, dy, dw, dh, d in areas]


def _physical_areas(areas: list[ScreenArea]) -> list[ScreenArea]:
    """The areas in physical pixels, which Windows lays the wallpaper out in and the compositor draws in."""
    return [(round(dx * dpr), round(dy * dpr), round(dw * dpr), round(dh * dpr), dpr) for dx, dy, dw, dh, dpr in areas]


class _ImageLoader(QThread):
    """Reads the new and old wallpaper and lays each out on every monitor, off the GUI thread.

    Emits each wallpaper as one image per monitor, at the monitor's size in physical pixels with the desktop
    background colour where the picture does not reach, or two empty lists when either file could not be read.
    """

    loaded = pyqtSignal(object, object)

    def __init__(self, new_path: str, old_path: str, areas: list[ScreenArea], fit_mode: str, bg_color: QColor):
        super().__init__()
        self.new_path = new_path
        self.old_path = old_path
        self.fit_mode = fit_mode
        self._bg_color = bg_color
        self._areas = _physical_areas(areas)

    @override
    def run(self) -> None:
        new_img, old_img = self._read(self.new_path), self._read(self.old_path)
        if new_img.isNull() or old_img.isNull():
            logger.warning(
                "Could not read %s, the wallpaper is set without a transition",
                self.new_path if new_img.isNull() else self.old_path,
            )
            self.loaded.emit([], [])
            return
        self.loaded.emit(self._compose(old_img), self._compose(new_img))

    @staticmethod
    def _read(path: str) -> QImage:
        """The image at *path*, turned the way its EXIF orientation asks, as Windows shows it."""
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        return reader.read()

    def _compose(self, px: QImage) -> list[QImage]:
        """One image per monitor: the background colour with *px* laid out on it."""
        monitors: list[QImage] = []
        for (scaled, ox, oy), (_, _, dw, dh, _) in zip(self._compute_per_screen_scaled(px), self._areas):
            monitor = QImage(dw, dh, QImage.Format.Format_RGB32)
            monitor.fill(self._bg_color)
            painter = QPainter(monitor)
            painter.drawImage(ox, oy, scaled)
            painter.end()
            monitors.append(monitor)
        return monitors

    def _compute_per_screen_scaled(self, px: QImage) -> list[tuple[QImage, int, int]]:
        """Compute (image, offset_x, offset_y) per screen area for the given source image."""
        areas = self._areas
        # Lay out what Windows lays out: its transcoded copy, not the file.
        px = _apply_transcode_cap(px)
        vw = max(dx + dw for dx, _, dw, _, _ in areas)
        vh = max(dy + dh for _, dy, _, dh, _ in areas)

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
    def _cover_or_contain(self, px: QImage, dw: int, dh: int, cover: bool) -> QImage:
        """Scale to cover or contain *dw* x *dh*, rounding the way Windows rounds.

        Windows works the ratios out in single precision, takes max for cover and
        min for contain, then adds a half to each axis before truncating. Done
        here rather than through QImage.scaled with an aspect ratio mode, which
        rounds differently and lands a pixel off.
        """
        ratios = (dw / px.width(), dh / px.height())
        s = max(ratios) if cover else min(ratios)
        return px.scaled(
            int(px.width() * s + 0.5),
            int(px.height() * s + 0.5),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _scale_span(
        self, px: QImage, areas: list[ScreenArea], vw: int, vh: int, cover: bool = True
    ) -> list[tuple[QImage, int, int]]:
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

    def _scale_tile(self, px: QImage, areas: list[ScreenArea], vw: int, vh: int) -> list[tuple[QImage, int, int]]:
        """Repeat the image at its native size from the virtual desktop origin.

        Windows never scales a tiled wallpaper, whatever its size, and the grid
        runs across the whole virtual desktop instead of restarting on each
        monitor. Tiling per monitor lines the seam up wrong.
        """
        iw, ih = px.width(), px.height()
        if iw <= 0 or ih <= 0:
            return [(px, 0, 0) for _ in areas]

        tiled = QImage(vw, vh, QImage.Format.Format_RGB32)
        tiled.fill(self._bg_color)
        tp = QPainter(tiled)
        for ty in range(0, vh, ih):
            for tx in range(0, vw, iw):
                tp.drawImage(tx, ty, px)
        tp.end()
        return [(tiled, -dx, -dy) for dx, dy, _, _, _ in areas]

    def _scale_for_screen(self, px: QImage, sw: int, sh: int) -> tuple[QImage, int, int]:
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


# The engine of each transition window, for the window procedure
_engines: dict[int, WallpaperEngine] = {}


def _window_procedure(hwnd: int, message: int, wparam: int, lparam: int) -> int:
    if message == WM_DESTROY:
        engine = _engines.pop(hwnd, None)
        if engine is not None:
            # Not from the window procedure, as ending can set the wallpaper
            QTimer.singleShot(0, engine.on_window_destroyed)
    return DefWindowProc(hwnd, message, wparam, lparam)


_procedure = WNDPROC(_window_procedure)


@cache
def _window_class() -> str:
    window_class = WNDCLASS(
        lpfnWndProc=_procedure, hInstance=GetModuleHandle(None), lpszClassName=TRANSITION_WINDOW_CLASS
    )
    if not user32.RegisterClassW(ctypes.byref(window_class)):
        raise ctypes.WinError(GetLastError())
    return TRANSITION_WINDOW_CLASS


class WallpaperEngine(QObject):
    _ANIMATION_MS = 800

    # The animation is over: set the wallpaper, whose path it carries
    finished = pyqtSignal(str)
    # Windows took the wallpaper: the manager emits it once SetWallpaper succeeds, for whoever asked for it
    wallpaperSet = pyqtSignal(str)
    # The window is off the desktop: Windows destroyed it, putting the wallpaper up, or the engine closed it
    closed = pyqtSignal()

    def __init__(self, image_path: str, animation: str = "circle", shown_path: str = "") -> None:
        """*shown_path* is the wallpaper Windows was last given for every screen, "" when the screens differ."""
        super().__init__()
        self._image_path = image_path
        self._animation = animation
        # Windows rewrites its transcoded copy some time after SetWallpaper, so that copy can still be the wallpaper
        # before, or half written, when a transition starts soon after one ends
        self._old_path = shown_path if os.path.isfile(shown_path) else _transcoded_wallpaper_path()
        self._committed = False
        self._shown = False
        self._closed = False
        self._areas: list[ScreenArea] = []
        self.fit_mode = _read_fit_mode()
        self._bg_color = _read_background_color()
        self._wallpaper_loader: _ImageLoader | None = None
        self._target: DesktopWindowTarget | None = None
        # Without a redirection surface the window shows only its visuals
        self.hwnd = CreateWindowEx(
            WS_EX_NOREDIRECTIONBITMAP,
            _window_class(),
            None,
            WS_POPUP,
            0,
            0,
            0,
            0,
            None,
            None,
            GetModuleHandle(None),
            None,
        )
        if not self.hwnd:
            raise ctypes.WinError(GetLastError())
        _engines[self.hwnd] = self

    def start(self) -> None:
        """Attach to WorkerW, lay the images out on a worker thread, then play the animation."""
        if (app := QCoreApplication.instance()) is not None:
            # Before the shared compositor shuts down
            app.aboutToQuit.connect(self.close)
        self._areas = _attach_to_workerw(self.hwnd)
        if not self._areas:
            self._skip()
            return
        logger.debug("Transition %s to %s starts on %d monitors", self._animation, self._image_path, len(self._areas))
        self._wallpaper_loader = _ImageLoader(
            self._image_path, self._old_path, self._areas, self.fit_mode, self._bg_color
        )
        self._wallpaper_loader.loaded.connect(self._on_images_loaded)
        self._wallpaper_loader.start()

    def _skip(self) -> None:
        """Ends without an animation, so the caller sets the wallpaper at once."""
        self._on_finished()
        self.close()

    def _on_images_loaded(self, old: list[QImage], new: list[QImage]) -> None:
        # If either image fails to load, skip animation and let caller commit immediately
        if not new:
            self._skip()
            return
        try:
            self._show(old, new)
        except OSError, COMError:
            logger.exception("Wallpaper transition failed, the wallpaper is set without it")
            self._skip()
            return
        self._shown = True
        logger.debug("Transition to %s shown, ends in %d ms", self._image_path, self._ANIMATION_MS)
        # The compositor plays the animation by itself; this only tells when it is over
        QTimer.singleShot(self._ANIMATION_MS, self._on_finished)

    def _show(self, old: list[QImage], new: list[QImage]) -> None:
        """Each monitor shows the old wallpaper, and the new one grows in front of it through the animated clips."""
        shared = compositor()
        root = shared.create_container_visual()
        for (x, y, width, height, _), old_image, new_image in zip(_physical_areas(self._areas), old, new):
            monitor = shared.create_sprite_visual()
            monitor.offset = (x, y, 0)
            monitor.size = (width, height)
            monitor.brush = shared.create_surface_brush(drawing_surface(old_image))
            brush = shared.create_surface_brush(drawing_surface(new_image))
            for clip in self._reveal_clips(shared, width, height):
                reveal = shared.create_sprite_visual()
                reveal.size = (width, height)
                reveal.brush = brush
                if clip is not None:
                    reveal.clip = clip
                # A visual's children draw in front of its own brush
                monitor.children.insert_at_top(reveal)
            root.children.insert_at_top(monitor)
        self._target = create_desktop_window_target(shared, self.hwnd)
        self._target.root = root
        ShowWindow(self.hwnd, SW_SHOWNA)

    def _reveal_clips(self, shared: Compositor, width: int, height: int) -> list[CompositionClip | None]:
        """The clips the new wallpaper shows through on one monitor, already animating; None shows it at once."""
        # The centre the circle and diamond grow from, rounded down as the GDI version did
        cx, cy = width // 2, height // 2
        if self._animation in ("circle", "slide_top"):
            if self._animation == "slide_top":
                cy = 0
            # Until it reaches the farthest corner
            reach = max(math.hypot(x - cx, y - cy) for x in (0, width) for y in (0, height))
            ellipse = shared.create_ellipse_geometry()
            ellipse.center = (cx, cy)
            ellipse.radius = (0.0, 0.0)
            ellipse.start_animation(
                "Radius", self._ease_out(shared.create_vector2_key_frame_animation(), (0.0, 0.0), (reach, reach))
            )
            return [shared.create_geometric_clip(ellipse)]
        if self._animation == "diamond":
            # A square turned on its corner, whose half diagonal reaches the farthest corner
            side = (max(cx, width - cx) + max(cy, height - cy)) * math.sqrt(2)
            square = shared.create_rectangle_geometry()
            square.offset = (cx - side / 2, cy - side / 2)
            square.size = (side, side)
            diamond = shared.create_geometric_clip(square)
            diamond.center_point = (cx, cy)
            diamond.rotation_angle_in_degrees = 45
            diamond.scale = (0.0, 0.0)
            diamond.start_animation(
                "Scale", self._ease_out(shared.create_vector2_key_frame_animation(), (0.0, 0.0), (1.0, 1.0))
            )
            return [diamond]
        if self._animation == "split":
            # A band grows from the top edge and one from the bottom edge, meeting in the middle
            top, bottom = shared.create_inset_clip(), shared.create_inset_clip()
            top.bottom_inset = bottom.top_inset = height
            top.start_animation(
                "BottomInset", self._ease_out(shared.create_scalar_key_frame_animation(), height, height / 2)
            )
            bottom.start_animation(
                "TopInset", self._ease_out(shared.create_scalar_key_frame_animation(), height, height / 2)
            )
            return [top, bottom]
        return [None]

    def _ease_out(self, animation: Any, start: Any, end: Any) -> Any:
        """animation from start to end over the transition's length, easing out like Qt's OutQuad, 2p - p^2, which is
        exactly the cubic Bezier through control points (1/3, 2/3) and (2/3, 1)."""
        animation.insert_key_frame(0.0, start)
        animation.insert_key_frame(
            1.0, end, compositor().create_cubic_bezier_easing_function((1 / 3, 2 / 3), (2 / 3, 1.0))
        )
        animation.duration = timedelta(milliseconds=self._ANIMATION_MS)
        return animation

    def _on_finished(self) -> None:
        if not self._committed:
            self._committed = True
            logger.debug("Transition to %s finished", self._image_path)
            self.finished.emit(self._image_path)

    def on_window_destroyed(self) -> None:
        """Windows destroyed the window, as Explorer replaces WorkerW for the new wallpaper. Destroyed before the
        animation ended, the transition ends here, so the wallpaper is still set."""
        logger.debug("Transition window for %s destroyed by Windows", self._image_path)
        if not self._committed:
            logger.warning(
                "Windows destroyed the wallpaper transition %s, the wallpaper is set without it",
                "during its animation" if self._shown else "before it showed",
            )
            self._on_finished()
        self.close()

    def close(self) -> None:
        """Takes the transition off the desktop and deletes the engine."""
        if self._closed:
            return
        self._closed = True
        loader = self._wallpaper_loader
        if loader is not None:
            # Still reading only when YASB quits meanwhile; Qt must not delete it while it runs
            loader.loaded.disconnect()
            loader.wait()
            self._wallpaper_loader = None
        if self._target is not None:
            # The WinRT setter accepts null, although the projection's stub does not.
            self._target.root = None  # pyright: ignore[reportAttributeAccessIssue]
            self._target.close()
            self._target = None
        # Still there, unless Windows destroyed it
        if _engines.pop(self.hwnd, None) is not None:
            DestroyWindow(self.hwnd)
        self.closed.emit()
        self.deleteLater()
