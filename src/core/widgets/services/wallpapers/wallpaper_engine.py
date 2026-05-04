"""
YASB Wallpaper engine.
"""

import ctypes
import math
import os
import winreg
from ctypes import wintypes

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QThread, QTimeLine, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap, QPolygonF
from PyQt6.QtWidgets import QApplication, QWidget
from win32con import GWL_STYLE, SWP_FRAMECHANGED, SWP_NOACTIVATE, WM_DESTROY, WS_CHILD, WS_POPUP

from core.widgets.services.wallpapers.wallpaper_manager import WallpaperManager

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


def _locate_workerw() -> int:
    """Find the WorkerW window that sits behind desktop icons."""
    progman = user32.FindWindowW("Progman", None)
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
        raise RuntimeError("Could not locate WorkerW")
    return worker


def _attach_to_workerw(widget: QWidget) -> None:
    """Parent *widget* to WorkerW and compute per-monitor screen areas."""
    worker = _locate_workerw()
    hwnd = HWND(int(widget.winId()))
    user32.SetParent(hwnd, worker)

    style = GetWindowLongPtr(hwnd, GWL_STYLE)
    SetWindowLongPtr(hwnd, GWL_STYLE, LONG_PTR((style | WS_CHILD) & ~WS_POPUP))

    wr = wintypes.RECT()
    user32.GetWindowRect(worker, ctypes.byref(wr))
    ww, wh = wr.right - wr.left, wr.bottom - wr.top

    areas = []
    for ml, mt, mr, mb in _enum_physical_monitors():
        areas.append((ml - wr.left, mt - wr.top, mr - ml, mb - mt, 1.0))
    widget.set_screen_areas(areas)

    user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, ww, wh, SWP_NOACTIVATE | SWP_FRAMECHANGED)


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

    def __init__(self, image_path: str, animation: str = "circle") -> None:
        super().__init__()
        self._image_path = image_path
        self._animation = animation
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._pixmap_new = QPixmap()
        self._pixmap_old = QPixmap()

        self.fit_mode = _read_fit_mode()
        self._bg_color = _read_background_color()
        self._areas: list[tuple[int, int, int, int, float]] = []
        self._per_screen_scaled_old: list[tuple[QPixmap, int, int]] = []
        self._per_screen_scaled_new: list[tuple[QPixmap, int, int]] = []
        self._progress = 0.0
        self._committed = False
        self._revealed = False

        # Keep the window fully transparent until the first frame is painted.
        self.setWindowOpacity(0.0)
        self.winId()

        self._timeline = QTimeLine(self._ANIMATION_MS, self)
        self._timeline.setUpdateInterval(self._FRAME_MS)
        self._timeline.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._timeline.valueChanged.connect(self._on_progress)
        self._timeline.finished.connect(self._on_finished)

    def start(self) -> None:
        """Load images asynchronously, then attach to WorkerW and begin animation."""
        self._loader = _ImageLoader(self._image_path, _transcoded_wallpaper_path())
        self._loader.loaded.connect(self._on_images_loaded)
        self._loader.start()

    def _on_images_loaded(self, new_img: QImage, old_img: QImage) -> None:
        self._pixmap_new = QPixmap.fromImage(new_img)
        self._pixmap_old = QPixmap.fromImage(old_img)

        # If either image fails to load, skip animation and set wallpaper immediately
        if self._pixmap_new.isNull() or self._pixmap_old.isNull():
            try:
                WallpaperManager().set_wallpaper(self._image_path)
            except Exception:
                pass
            self.deleteLater()
            return

        _attach_to_workerw(self)
        self.show()
        QTimer.singleShot(0, self._start_animation)

    def _start_animation(self) -> None:
        if not self._revealed:
            self.update()
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
        self._per_screen_scaled_new = self._compute_per_screen_scaled(self._pixmap_new)
        self._per_screen_scaled_old = self._compute_per_screen_scaled(self._pixmap_old)

    def _compute_per_screen_scaled(self, px: QPixmap) -> list[tuple[QPixmap, int, int]]:
        """Compute (pixmap, offset_x, offset_y) per screen area for the given source image."""
        areas = self._areas
        if px.isNull():
            return []
        vw = max(dx + dw for dx, _, dw, _, _ in areas) if areas else self.width()
        vh = max(dy + dh for _, dy, _, dh, _ in areas) if areas else self.height()

        mode = self.fit_mode
        if mode == "span":
            return self._scale_span(px, areas, vw, vh)
        if mode == "tile":
            return self._scale_tile(px, areas, vw, vh)
        if mode == "center":
            return self._scale_center(px, areas, vw)
        if mode == "fill":
            return self._scale_fill(px, areas, vw, vh)
        if mode == "fit":
            return self._scale_fit(px, areas, vw, vh)
        # stretch, or unknown – handled per-monitor
        return [self._scale_for_screen(px, dw, dh) for _, _, dw, dh, _ in areas]

    #  Per-mode scaling helpers
    def _scale_span(self, px: QPixmap, areas, vw: int, vh: int) -> list[tuple[QPixmap, int, int]]:
        """Scale image to cover the entire virtual desktop."""
        scaled = px.scaled(
            vw,
            vh,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.FastTransformation,
        )
        ox = int((vw - scaled.width()) / 2)
        oy = int((vh - scaled.height()) / 2)
        if oy < 0:
            oy = -round((scaled.height() - vh) / 3)
        return [(scaled, ox - dx, oy - dy) for dx, dy, _, _, _ in areas]

    def _scale_tile(self, px: QPixmap, areas, vw: int, vh: int) -> list[tuple[QPixmap, int, int]]:
        """Tile the image at original size across the virtual desktop.

        Windows scales oversized images so that no dimension is smaller than the
        largest single-monitor dimension (e.g. 1920 for 1920x1080 monitors).
        """
        iw, ih = px.width(), px.height()
        if iw <= 0 or ih <= 0:
            return [(px, 0, 0) for _ in areas]

        # Determine per-monitor max dimension for the scaling threshold
        mon_rects = _enum_physical_monitors()
        max_mon_dim = max(
            (max(abs(r - l), abs(b - t)) for l, t, r, b in mon_rects),
            default=max(vw, vh),
        )

        # Scale down oversized images to cover (vw × max_mon_dim), preserving aspect ratio
        if iw > vw + 2 or ih > max_mon_dim + 2:
            tile_src = px.scaled(
                vw,
                max_mon_dim,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.FastTransformation,
            )
        else:
            tile_src = px

        # Compose the tiled canvas
        tw, th = tile_src.width(), tile_src.height()
        tiled = QPixmap(vw, vh)
        tiled.fill(QColor(0, 0, 0))
        tp = QPainter(tiled)
        for ty in range(0, vh, th):
            for tx in range(0, vw, tw):
                tp.drawPixmap(tx, ty, tile_src)
        tp.end()
        return [(tiled, -dx, -dy) for dx, dy, _, _, _ in areas]

    def _scale_center(self, px: QPixmap, areas, vw: int) -> list[tuple[QPixmap, int, int]]:
        """Centre the image on each monitor, scaling down only if larger than the screen."""
        iw, ih = px.width(), px.height()
        center_px = px
        max_monitor_w = max((dw for _, _, dw, _, _ in areas), default=vw)
        sx = vw / iw if iw > 0 else 1.0
        sy = max_monitor_w / ih if ih > 0 else 1.0
        scale = max(sx, sy)
        if scale < 1.0:
            center_px = px.scaled(
                max(1, int(iw * scale)),
                max(1, int(ih * scale)),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        result = []
        for _, _, dw, dh, _ in areas:
            cw, ch = center_px.width(), center_px.height()
            src_x = max(0, (cw - dw) // 2)
            src_y = max(0, (ch - dh) // 2)
            cropped = center_px.copy(src_x, src_y, min(cw, dw), min(ch, dh))
            ox = max(0, (dw - cw) // 2)
            oy = max(0, (dh - ch) // 2)
            result.append((cropped, ox, oy))
        return result

    def _scale_fill(self, px: QPixmap, areas, vw: int, vh: int) -> list[tuple[QPixmap, int, int]]:
        """Fill each monitor, with special handling for panoramic images on multi-monitor setups."""
        if len(areas) > 1:
            src_ratio = px.width() / max(1, px.height())
            # I'm not certain about the exact thresholds Windows uses, maybe this is wrong for some aspect ratios,
            # but it seems to work well for typical ultrawide wallpapers
            is_panoramic = px.width() >= int(vw * 1.10) and 2.2 <= src_ratio <= 2.5
            if is_panoramic:
                # Render one virtual-desktop image and slice it per monitor.
                scaled = px.scaled(
                    vw,
                    vh,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.FastTransformation,
                )
                ox = int((vw - scaled.width()) / 2)
                oy = int((vh - scaled.height()) / 2)
                if ox < 0:
                    ox = -round((scaled.width() - vw) / 3)
                if oy < 0:
                    oy = -round((scaled.height() - vh) / 3)
                return [(scaled, ox - dx, oy - dy) for dx, dy, _, _, _ in areas]
        return [self._scale_for_screen(px, dw, dh) for _, _, dw, dh, _ in areas]

    def _scale_fit(self, px: QPixmap, areas, vw: int, vh: int) -> list[tuple[QPixmap, int, int]]:
        """Fit image to each monitor, with special handling for panoramic images on multi-monitor setups."""
        if len(areas) > 1:
            src_ratio = px.width() / max(1, px.height())
            is_panoramic = px.width() >= int(vw * 1.10) and 2.2 <= src_ratio <= 2.5
            if is_panoramic:
                # Render one virtual-desktop image and slice it per monitor.
                scaled = px.scaled(
                    vw,
                    vh,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                ox = int((vw - scaled.width()) / 2)
                oy = int((vh - scaled.height()) / 2)
                return [(scaled, ox - dx, oy - dy) for dx, dy, _, _, _ in areas]
        return [self._scale_for_screen(px, dw, dh) for _, _, dw, dh, _ in areas]

    def _scale_for_screen(self, px: QPixmap, sw: int, sh: int) -> tuple[QPixmap, int, int]:
        """Scale a single image for one monitor (used by fill, fit, stretch)."""
        mode = self.fit_mode
        if mode == "fill":
            scaled = px.scaled(
                sw, sh, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.FastTransformation
            )
        elif mode == "fit":
            scaled = px.scaled(sw, sh, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        elif mode == "stretch":
            scaled = px.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        else:
            scaled = px
        ox = int((sw - scaled.width()) / 2)
        oy = int((sh - scaled.height()) / 2)
        if mode == "fill" and oy < 0:
            oy = -round((scaled.height() - sh) / 3)
        return scaled, ox, oy

    def _on_progress(self, value: float) -> None:
        self._progress = value
        self.update()

    def _on_finished(self) -> None:
        self._progress = 1.0
        self.update()
        if not self._committed:
            self._committed = True
            try:
                WallpaperManager().set_wallpaper(self._image_path)
            except Exception:
                pass

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
                    p.drawPixmap(dx + ox_o, dy + oy_o, scaled_o)
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
            p.drawPixmap(dx + ox_n, dy + oy_n, scaled_n)
            p.restore()

        if not self._revealed:
            self._revealed = True
            self.setWindowOpacity(1.0)

    def nativeEvent(self, _, message):
        msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
        if msg.message == WM_DESTROY:
            self.deleteLater()
            return True, 0
        return False, 0

    def closeEvent(self, event) -> None:
        if self._timeline and self._timeline.state() != QTimeLine.State.NotRunning:
            self._timeline.stop()
        super().closeEvent(event)
