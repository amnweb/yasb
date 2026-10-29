"""Turn the bar's SVG silhouette into a native, physical-pixel window region."""

import ctypes
from html import escape

from PyQt6.QtCore import QByteArray, QRectF
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

from core.utils.win32.bindings.gdi32 import gdi32
from core.utils.win32.bindings.kernel32 import GetLastError
from core.utils.win32.structs import RECT, RGNDATA, RGNDATAHEADER

_COVERAGE = bytes(0 if value < 128 else 1 for value in range(256))


def svg_region(path: str, area: QRectF, width: int, height: int, scale: float) -> int:
    """The caller must transfer the returned HRGN to SetWindowRgn or delete it."""
    if width <= 0 or height <= 0:
        return _empty_region()
    # Use the entire native window, including the edge overhang outside the QML item.
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width / scale} {height / scale}">'
        f'<path transform="translate({area.x()} {area.y()})" d="{escape(path, quote=True)}" fill="white"/>'
        "</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    if not renderer.isValid():
        raise ValueError("The bar's backdropPath is not a valid SVG path")
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, width, height))
    painter.end()
    alpha = image.convertToFormat(QImage.Format.Format_Alpha8)
    pixels = alpha.constBits()
    if pixels is None:
        raise ValueError("Could not read the backdrop silhouette")
    data = pixels.asstring(alpha.sizeInBytes())
    stride = alpha.bytesPerLine()
    rectangles: list[RECT] = []
    band: list[RECT] = []
    previous = b""
    for y in range(height):
        row = data[y * stride : y * stride + width].translate(_COVERAGE)
        if row == previous:
            for rect in band:
                rect.bottom = y + 1
            continue
        previous, band = row, []
        start = row.find(b"\1")
        while start >= 0:
            end = row.find(b"\0", start)
            if end < 0:
                end = width
            band.append(RECT(start, y, end, y + 1))
            start = row.find(b"\1", end)
        rectangles += band
    if not rectangles:
        return _empty_region()
    bounds = RECT(
        min(rect.left for rect in rectangles),
        rectangles[0].top,
        max(rect.right for rect in rectangles),
        rectangles[-1].bottom,
    )
    header = RGNDATAHEADER(
        ctypes.sizeof(RGNDATAHEADER), 1, len(rectangles), ctypes.sizeof(RECT) * len(rectangles), bounds
    )
    buffer = ctypes.create_string_buffer(bytes(header) + bytes((RECT * len(rectangles))(*rectangles)))
    region = gdi32.ExtCreateRegion(None, ctypes.sizeof(buffer) - 1, ctypes.cast(buffer, ctypes.POINTER(RGNDATA)))
    if not region:
        raise ctypes.WinError(GetLastError())
    return region


def _empty_region() -> int:
    region = gdi32.CreateRectRgn(0, 0, 0, 0)
    if not region:
        raise ctypes.WinError(GetLastError())
    return region
