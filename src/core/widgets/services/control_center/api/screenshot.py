import ctypes
import logging
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QImage, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication, QFileDialog, QFrame, QHBoxLayout, QPushButton, QWidget

from core.ui.theme import get_tokens
from core.utils.tooltip import set_tooltip

user32 = ctypes.WinDLL("user32")
gdi32 = ctypes.WinDLL("gdi32")
SRCCOPY = 0x00CC0020

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER)]


LP_BITMAPINFO = ctypes.POINTER(BITMAPINFO)

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.BitBlt.argtypes = [
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HDC,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.DWORD,
]
gdi32.BitBlt.restype = wintypes.BOOL
gdi32.GetDIBits.argtypes = [
    wintypes.HDC,
    wintypes.HBITMAP,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.LPVOID,
    LP_BITMAPINFO,
    wintypes.UINT,
]
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL


def virtual_screen_rect() -> tuple[int, int, int, int]:
    return (
        user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


def capture_raw(x: int, y: int, width: int, height: int) -> bytes | None:
    hdc = user32.GetDC(0)
    if not hdc:
        logging.error("capture_raw: GetDC failed")
        return None
    mem = gdi32.CreateCompatibleDC(hdc)
    if not mem:
        user32.ReleaseDC(0, hdc)
        logging.error("capture_raw: CreateCompatibleDC failed")
        return None
    bmp = gdi32.CreateCompatibleBitmap(hdc, width, height)
    if not bmp:
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(0, hdc)
        logging.error("capture_raw: CreateCompatibleBitmap failed")
        return None
    old = gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, width, height, hdc, x, y, SRCCOPY)

    bitmap_info = BITMAPINFO()
    bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bitmap_info.bmiHeader.biWidth = width
    bitmap_info.bmiHeader.biHeight = -height
    bitmap_info.bmiHeader.biPlanes = 1
    bitmap_info.bmiHeader.biBitCount = 32

    buffer = ctypes.create_string_buffer(width * 4 * height)
    gdi32.GetDIBits(mem, bmp, 0, height, buffer, ctypes.byref(bitmap_info), 0)

    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(0, hdc)
    return bytes(buffer)


def raw_to_image(raw: bytes, width: int, height: int) -> QImage:
    return QImage(raw, width, height, width * 4, QImage.Format.Format_RGB32).copy()


def capture_virtual_screen() -> tuple[tuple[int, int, int, int], QImage] | None:
    x, y, width, height = virtual_screen_rect()
    raw = capture_raw(x, y, width, height)
    if raw is None:
        return None
    return (x, y, width, height), raw_to_image(raw, width, height)


SVG_COPY = """\
<svg viewBox="64 64 896 896" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <path d="M540.5,768C519.5,768 499.5,763.75 480.5,755.25C461.5,746.75 444.917,735.417 430.75,721.25C416.583,707.083 405.25,690.5 396.75,671.5C388.25,652.5 384,632.5 384,611.5L384,220.5C384,199.5 388.25,179.5 396.75,160.5C405.25,141.5 416.583,124.917 430.75,110.75C444.917,96.5834 461.5,85.2501 480.5,76.75C499.5,68.2501 519.5,64.0001 540.5,64L803.5,64C824.5,64.0001 844.5,68.2501 863.5,76.75C882.5,85.2501 899.083,96.5834 913.25,110.75C927.417,124.917 938.75,141.5 947.25,160.5C955.75,179.5 960,199.5 960,220.5L960,611.5C960,632.5 955.75,652.5 947.25,671.5C938.75,690.5 927.417,707.083 913.25,721.25C899.083,735.417 882.5,746.75 863.5,755.25C844.5,763.75 824.5,768 803.5,768ZM800,704C813,704 825.333,701.5 837,696.5C848.667,691.5 858.917,684.583 867.75,675.75C876.583,666.917 883.5,656.667 888.5,645C893.5,633.333 896,621 896,608L896,224C896,211 893.5,198.667 888.5,187C883.5,175.333 876.583,165.083 867.75,156.25C858.917,147.417 848.667,140.5 837,135.5C825.333,130.5 813,128 800,128L544,128C531,128 518.667,130.5 507,135.5C495.333,140.5 485.083,147.417 476.25,156.25C467.417,165.083 460.5,175.333 455.5,187C450.5,198.667 448,211 448,224L448,608C448,621 450.5,633.333 455.5,645C460.5,656.667 467.417,666.917 476.25,675.75C485.083,684.583 495.333,691.5 507,696.5C518.667,701.5 531,704 544,704ZM220.5,960C199.5,960 179.5,955.75 160.5,947.25C141.5,938.75 124.917,927.417 110.75,913.25C96.5833,899.083 85.25,882.5 76.75,863.5C68.25,844.5 64,824.5 64,803.5L64,412.5C64,391.5 68.25,371.5 76.75,352.5C85.25,333.5 96.5833,316.917 110.75,302.75C124.917,288.583 141.5,277.25 160.5,268.75C179.5,260.25 199.5,256 220.5,256L320,256L320,320L224,320C211,320 198.667,322.5 187,327.5C175.333,332.5 165.083,339.417 156.25,348.25C147.417,357.083 140.5,367.333 135.5,379C130.5,390.667 128,403 128,416L128,800C128,813 130.5,825.333 135.5,837C140.5,848.667 147.417,858.917 156.25,867.75C165.083,876.583 175.333,883.5 187,888.5C198.667,893.5 211,896 224,896L480,896C490.333,896 500.167,894.5 509.5,891.5C518.833,888.5 527.5,884.167 535.5,878.5C543.5,872.833 550.5,866.083 556.5,858.25C562.5,850.417 567.167,841.667 570.5,832L637,832C633.333,850.333 626.583,867.333 616.75,883C606.917,898.667 595,912.167 581,923.5C567,934.833 551.333,943.75 534,950.25C516.667,956.75 498.667,960 480,960Z" fill="currentColor"></path>
</svg>
"""

SVG_SAVE = """\
<svg viewBox="64 64 896 896" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <path d="M960,328L960,832C960,849 956.667,865.25 950,880.75C943.333,896.25 934.333,909.833 923,921.5C911.667,933.167 898.417,942.5 883.25,949.5C868.083,956.5 851.833,960 834.5,960L192,960C175,960 158.75,956.667 143.25,950C127.75,943.333 114.167,934.333 102.5,923C90.8333,911.667 81.5,898.417 74.5,883.25C67.5,868.083 64,851.833 64,834.5L64,192C64,175 67.3333,158.75 74,143.25C80.6667,127.75 89.6667,114.167 101,102.5C112.333,90.8334 125.583,81.5001 140.75,74.5C155.917,67.5001 172.167,64.0001 189.5,64L696,64C713,64.0001 729.333,67.2501 745,73.75C760.667,80.2501 774.5,89.5001 786.5,101.5L922.5,237.5C934.5,249.5 943.75,263.333 950.25,279C956.75,294.667 960,311 960,328ZM896,328C896,310 889.833,294.833 877.5,282.5L741.5,146.5C731.167,136.167 718.667,130.167 704,128.5L704,288C704,301 701.5,313.333 696.5,325C691.5,336.667 684.583,346.917 675.75,355.75C666.917,364.583 656.667,371.5 645,376.5C633.333,381.5 621,384 608,384L352,384C339,384 326.667,381.5 315,376.5C303.333,371.5 293.083,364.583 284.25,355.75C275.417,346.917 268.5,336.667 263.5,325C258.5,313.333 256,301 256,288L256,128L192,128C183,128 174.667,129.667 167,133C159.333,136.333 152.583,140.917 146.75,146.75C140.917,152.583 136.333,159.333 133,167C129.667,174.667 128,183 128,192L128,832C128,841 129.667,849.417 133,857.25C136.333,865.083 140.833,871.833 146.5,877.5C152.167,883.167 158.917,887.667 166.75,891C174.583,894.333 183,896 192,896L192,608C192,595 194.5,582.667 199.5,571C204.5,559.333 211.417,549.083 220.25,540.25C229.083,531.417 239.333,524.5 251,519.5C262.667,514.5 275,512 288,512L736,512C749,512 761.333,514.5 773,519.5C784.667,524.5 794.917,531.417 803.75,540.25C812.583,549.083 819.5,559.333 824.5,571C829.5,582.667 832,595 832,608L832,896C841,896 849.333,894.333 857,891C864.667,887.667 871.417,883.083 877.25,877.25C883.083,871.417 887.667,864.667 891,857C894.333,849.333 896,841 896,832ZM320,128L320,288C320,296.667 323.167,304.167 329.5,310.5C335.833,316.833 343.333,320 352,320L608,320C616.667,320 624.167,316.833 630.5,310.5C636.833,304.167 640,296.667 640,288L640,128ZM768,896L768,608C768,599.333 764.833,591.833 758.5,585.5C752.167,579.167 744.667,576 736,576L288,576C279.333,576 271.833,579.167 265.5,585.5C259.167,591.833 256,599.333 256,608L256,896Z" fill="currentColor"></path>
</svg>
"""

SVG_CANCEL = """\
<svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <path d="M512,620.5L131,1001.5C124,1008.5 115.75,1014 106.25,1018C96.75,1022 87,1024 77,1024C66.3333,1024 56.3333,1022 47,1018C37.6667,1014 29.5,1008.5 22.5,1001.5C15.5,994.5 10,986.333 6,977C2,967.667 0,957.667 0,947C0,937 2,927.25 6,917.75C10,908.25 15.5,900 22.5,893L403.5,512L22.5,131C15.1667,123.667 9.58333,115.25 5.75,105.75C1.91667,96.25 0,86.5 0,76.5C0,65.8334 2,55.8334 6,46.5C10,37.1667 15.5,29.0834 22.5,22.25C29.5,15.4167 37.6667,10 47,6C56.3333,2 66.3333,0 77,0C87,0 96.75,2 106.25,6C115.75,10 124,15.5 131,22.5L512,403.5L893,22.5C908,7.5 926.167,0 947.5,0C957.833,0 967.667,2 977,6C986.333,10 994.5,15.5 1001.5,22.5C1008.5,29.5 994.5,15.5 1001.5,22.5C1008.5,29.5 1014,37.6667 1018,47C1022,56.3334 1024,66.1667 1024,76.5C1024,86.5 1022.08,96.25 1018.25,105.75C1014.42,115.25 1008.83,123.667 1001.5,131L620.5,512L1001.5,893C1008.5,900 1014,908.25 1018,917.75C1022,927.25 1024,937 1024,947C1024,957.667 1022,967.667 1018,977C1014,986.333 1008.5,994.5 1001.5,1001.5C994.5,1008.5 986.333,1014 977,1018C967.667,1022 957.667,1024 947,1024C937,1024 927.25,1022 917.75,1018C908.25,1014 900,1008.5 893,1001.5Z" fill="currentColor"></path>
</svg>
"""


def svg_to_icon(svg_text: str, size: int, color: str) -> QIcon:
    try:
        svg_text = svg_text.replace("currentColor", color)
        renderer = QSvgRenderer(svg_text.encode("utf-8"))
        if not renderer.isValid():
            return QIcon()
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)
    except Exception as exc:
        logging.error("Failed to render SVG to icon: %s", exc)
        return QIcon()


class ScreenshotToolbar(QFrame):
    def __init__(self, parent: QWidget, on_action):
        super().__init__(parent)
        self.on_action = on_action
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        t = get_tokens()
        bg_color = t["solid_bg_base"]
        border_color = t["solid_bg_tertiary"]
        hover_bg = t["subtle_fill_secondary"]

        icon_color = t["text_primary"]

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 6px;
                min-width: 28px;
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        icon_size = QSize(16, 16)

        self.btn_copy = QPushButton(self)
        self.btn_copy.setIcon(svg_to_icon(SVG_COPY, 16, icon_color))
        self.btn_copy.setIconSize(icon_size)
        set_tooltip(
            self.btn_copy,
            "Copy",
            delay=0,
        )
        self.btn_copy.clicked.connect(lambda: self.on_action("copy"))

        self.btn_save = QPushButton(self)
        self.btn_save.setIcon(svg_to_icon(SVG_SAVE, 16, icon_color))
        self.btn_save.setIconSize(icon_size)
        set_tooltip(self.btn_save, "Save as", delay=0)
        self.btn_save.clicked.connect(lambda: self.on_action("save"))

        self.btn_cancel = QPushButton(self)
        self.btn_cancel.setIcon(svg_to_icon(SVG_CANCEL, 16, icon_color))
        self.btn_cancel.setIconSize(icon_size)
        set_tooltip(self.btn_cancel, "Cancel", delay=0)
        self.btn_cancel.clicked.connect(lambda: self.on_action("cancel"))

        for btn in (self.btn_copy, self.btn_save, self.btn_cancel):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self.btn_copy)
        layout.addWidget(self.btn_save)
        layout.addWidget(self.btn_cancel)


class RegionSelector(QWidget):
    def __init__(self, on_done):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._pad = 1
        self._on_done = on_done
        self._start: QPoint | None = None
        self._end: QPoint | None = None
        self._toolbar: ScreenshotToolbar | None = None
        self._drag_mode: str | None = None
        self._active_handle: str | None = None
        self._last_pos: QPoint | None = None

        result = capture_virtual_screen()
        if result is None:
            logging.error("RegionSelector: failed to capture screen")
            self.deleteLater()
            return
        self._screen_rect, self._frozen_image = result
        self._background = QPixmap.fromImage(self._frozen_image)

        sx, sy, sw, sh = self._screen_rect
        self.setGeometry(sx - self._pad, sy - self._pad, sw + self._pad * 2, sh + self._pad * 2)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.show()

    def _selection_geometry(self) -> tuple[int, int, int, int] | None:
        if not self._start or not self._end:
            return None
        return (
            min(self._start.x(), self._end.x()),
            min(self._start.y(), self._end.y()),
            abs(self._end.x() - self._start.x()) + 1,
            abs(self._end.y() - self._start.y()) + 1,
        )

    def _selection_result(self) -> tuple[int, int, int, int, int, int, QImage] | None:
        geom = self._selection_geometry()
        if not geom or geom[2] < 5 or geom[3] < 5:
            return None
        x, y, w, h = geom
        sx, sy = self._screen_rect[:2]
        return (x - self._pad + sx, y - self._pad + sy, w, h, sx, sy, self._frozen_image.copy())

    def _get_handles(self) -> dict[str, QRect]:
        geom = self._selection_geometry()
        if not geom:
            return {}
        x, y, w, h = geom
        mx, my = x + w // 2, y + h // 2
        hs = 8
        h_hs = hs // 2
        return {
            "TL": QRect(x - h_hs, y - h_hs, hs, hs),
            "TR": QRect(x + w - h_hs, y - h_hs, hs, hs),
            "BL": QRect(x - h_hs, y + h - h_hs, hs, hs),
            "BR": QRect(x + w - h_hs, y + h - h_hs, hs, hs),
            "T": QRect(mx - h_hs, y - h_hs, hs, hs),
            "B": QRect(mx - h_hs, y + h - h_hs, hs, hs),
            "L": QRect(x - h_hs, my - h_hs, hs, hs),
            "R": QRect(x + w - h_hs, my - h_hs, hs, hs),
        }

    def _update_hover_cursor(self, pos: QPoint) -> None:
        if self._toolbar is not None:
            for name, rect in self._get_handles().items():
                if rect.contains(pos):
                    diag_1 = Qt.CursorShape.SizeFDiagCursor
                    diag_2 = Qt.CursorShape.SizeBDiagCursor
                    cursors = {
                        "TL": diag_1,
                        "BR": diag_1,
                        "TR": diag_2,
                        "BL": diag_2,
                        "T": Qt.CursorShape.SizeVerCursor,
                        "B": Qt.CursorShape.SizeVerCursor,
                        "L": Qt.CursorShape.SizeHorCursor,
                        "R": Qt.CursorShape.SizeHorCursor,
                    }
                    self.setCursor(cursors[name])
                    return

            geom = self._selection_geometry()
            if geom and QRect(*geom).contains(pos):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                return

        self.setCursor(Qt.CursorShape.CrossCursor)

    def paintEvent(self, a0: QPaintEvent | None):
        if self._background is None:
            return
        painter = QPainter(self)
        painter.drawPixmap(self._pad, self._pad, self._background)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))

        geom = self._selection_geometry()
        if geom is not None:
            x, y, w, h = geom
            painter.drawPixmap(QRect(x, y, w, h), self._background, QRect(x - self._pad, y - self._pad, w, h))
            painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x, y, w - 1, h - 1)

            if w == 1 and h == 1:
                r = self.rect()
                painter.drawLine(max(x - 8, 0), y, min(x + 8, r.width() - 1), y)
                painter.drawLine(x, max(y - 8, 0), x, min(y + 8, r.height() - 1))

            if self._toolbar is not None:
                painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.PenStyle.SolidLine))
                painter.setBrush(QColor(0, 120, 212))
                for rect in self._get_handles().values():
                    painter.drawRect(rect)
        painter.end()

    def mousePressEvent(self, a0: QMouseEvent | None):
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            pos = a0.pos()
            self._last_pos = pos

            if self._toolbar is not None:
                for name, rect in self._get_handles().items():
                    if rect.contains(pos):
                        self._drag_mode = "resize"
                        self._active_handle = name
                        self._toolbar.hide()
                        return

                geom = self._selection_geometry()
                if geom and QRect(*geom).contains(pos):
                    self._drag_mode = "move"
                    self._toolbar.hide()
                    return

            self.close_toolbar()
            self._drag_mode = "draw"
            sw, sh = self._screen_rect[2], self._screen_rect[3]
            clamped_x = max(self._pad, min(pos.x(), self._pad + sw - 1))
            clamped_y = max(self._pad, min(pos.y(), self._pad + sh - 1))
            self._start = self._end = QPoint(clamped_x, clamped_y)
            self.update()

    def mouseMoveEvent(self, a0: QMouseEvent | None):
        if a0 is None:
            return
        pos = a0.pos()

        if self._drag_mode is not None:
            sw, sh = self._screen_rect[2], self._screen_rect[3]
            clamped_x = max(self._pad, min(pos.x(), self._pad + sw - 1))
            clamped_y = max(self._pad, min(pos.y(), self._pad + sh - 1))
            clamped_pos = QPoint(clamped_x, clamped_y)

            if self._drag_mode == "draw" and self._start is not None:
                self._end = clamped_pos
                self.update()
            elif self._drag_mode == "resize" and self._start is not None and self._end is not None:
                if "T" in self._active_handle:
                    self._start.setY(clamped_pos.y())
                if "B" in self._active_handle:
                    self._end.setY(clamped_pos.y())
                if "L" in self._active_handle:
                    self._start.setX(clamped_pos.x())
                if "R" in self._active_handle:
                    self._end.setX(clamped_pos.x())
                self.update()
            elif (
                self._drag_mode == "move"
                and self._start is not None
                and self._end is not None
                and self._last_pos is not None
            ):
                delta = pos - self._last_pos
                w = self._end.x() - self._start.x()
                h = self._end.y() - self._start.y()

                new_x = max(self._pad, min(self._start.x() + delta.x(), self._pad + sw - w - 1))
                new_y = max(self._pad, min(self._start.y() + delta.y(), self._pad + sh - h - 1))

                self._start = QPoint(new_x, new_y)
                self._end = QPoint(new_x + w, new_y + h)
                self._last_pos = pos
                self.update()
        else:
            self._update_hover_cursor(pos)

    def mouseReleaseEvent(self, a0: QMouseEvent | None):
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            if self._drag_mode is not None:
                self._drag_mode = None
                self._active_handle = None
                self._last_pos = None

                geom = self._selection_geometry()
                if geom:
                    x, y, w, h = geom
                    self._start = QPoint(x, y)
                    self._end = QPoint(x + w - 1, y + h - 1)

                    if self._toolbar is not None:
                        self.align_toolbar()
                    else:
                        self.show_toolbar()
                else:
                    self._start = self._end = None
                    self.close_toolbar()
                    self.update()

            if a0 is not None:
                self._update_hover_cursor(a0.pos())

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None):
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            result = self._selection_result()
            if result is not None:
                on_done = self._on_done
                self.close()
                if on_done:
                    on_done(result, "copy")

    def keyPressEvent(self, a0: QKeyEvent | None):
        if a0 is not None:
            if a0.key() == Qt.Key.Key_Escape:
                on_done = self._on_done
                self.close()
                if on_done:
                    on_done(None, "cancel")
            elif a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                result = self._selection_result()
                if result is not None:
                    on_done = self._on_done
                    self.close()
                    if on_done:
                        on_done(result, "copy")

    def show_toolbar(self) -> None:
        self.close_toolbar()
        self._toolbar = ScreenshotToolbar(self, self._on_toolbar_action)
        self._toolbar.adjustSize()
        self.align_toolbar()

    def align_toolbar(self) -> None:
        if self._toolbar is None:
            return

        geom = self._selection_geometry()
        if not geom:
            return

        x, y, w, h = geom
        tb_w, tb_h = self._toolbar.width(), self._toolbar.height()
        margin = 10

        tb_x = max(margin, min(x + (w - tb_w) // 2, self.width() - tb_w - margin))
        tb_y = y + h + margin

        if tb_y + tb_h > self.height() - margin:
            tb_y = y - tb_h - margin
            if tb_y < margin:
                tb_y = max(margin, y + h - tb_h - margin)
                if tb_y < y:
                    tb_y = y + h // 2 - tb_h // 2

        self._toolbar.setGeometry(int(tb_x), int(tb_y), int(tb_w), int(tb_h))
        self._toolbar.show()
        self._toolbar.raise_()

    def _on_toolbar_action(self, action_type: str) -> None:
        result = self._selection_result()
        on_done = self._on_done
        self.close()
        if on_done:
            on_done(result, action_type)

    def close_toolbar(self) -> None:
        if self._toolbar is not None:
            self._toolbar.deleteLater()
            self._toolbar = None

    def closeEvent(self, a0):
        self.close_toolbar()
        self._background = None
        self._frozen_image = None
        self._on_done = None
        super().closeEvent(a0)


class ScreenshotService:
    _SAVE_DIRECTORY = Path.home() / "Pictures" / "Screenshots"
    _selector: RegionSelector | None = None

    @classmethod
    def _ensure_directory(cls) -> Path:
        cls._SAVE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        return cls._SAVE_DIRECTORY

    @staticmethod
    def _build_filename() -> str:
        return f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"

    @classmethod
    def start(cls) -> None:
        # Close any active selector before creating a new one to prevent
        # multiple overlapping fullscreen windows.
        if cls._selector is not None:
            try:
                cls._selector.close()
            except Exception:
                pass
            cls._selector = None
        cls._selector = RegionSelector(cls._on_selection_done)

    @classmethod
    def _on_selection_done(
        cls, result: tuple[int, int, int, int, int, int, QImage] | None, action_type: str = "copy"
    ) -> None:
        cls._selector = None
        if result is None or action_type == "cancel":
            return

        x, y, width, height, sx, sy, frozen_image = result
        cropped = frozen_image.copy(x - sx, y - sy, width, height)

        if "copy" in action_type:
            try:
                QApplication.clipboard().setImage(cropped)
            except Exception as exc:
                logging.error("Failed to copy screenshot to clipboard: %s", exc)

        if "save" in action_type:
            try:
                initial_path = str(cls._ensure_directory() / cls._build_filename())
                file_path, _ = QFileDialog.getSaveFileName(
                    None, "Save Screenshot", initial_path, "PNG Image (*.png);;All Files (*)"
                )
                if file_path:
                    if not cropped.save(file_path, "PNG"):
                        logging.error("Failed to save screenshot to %s", file_path)
                    else:
                        logging.debug("Screenshot saved to %s", file_path)
                        cls._SAVE_DIRECTORY = Path(file_path).parent
            except Exception as exc:
                logging.error("Failed to save screenshot: %s", exc)
