"""Physical-space selection mapping and multi-monitor crop stitch."""

import math

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap

from core.widgets.services.control_center.api.screenshot.capture import ScreenFreeze
from core.widgets.services.control_center.api.screenshot.constants import MIN_SIZE


def local_to_physical(f: ScreenFreeze, local: QPoint) -> QPoint:
    """Panel-local logical point -> Win32 physical pixel."""
    gw = max(1, f.geo.width())
    gh = max(1, f.geo.height())
    pw = max(1, f.physical.width())
    ph = max(1, f.physical.height())
    return QPoint(
        f.physical.x() + int(round(local.x() * pw / gw)),
        f.physical.y() + int(round(local.y() * ph / gh)),
    )


def physical_to_local_rect(f: ScreenFreeze, phys: QRect) -> QRect:
    """Physical selection -> local logical rect on this freeze (for paint)."""
    if phys.isEmpty():
        return QRect()
    inter = phys.intersected(f.physical)
    if inter.isEmpty():
        return QRect()
    gw = max(1, f.geo.width())
    gh = max(1, f.geo.height())
    pw = max(1, f.physical.width())
    ph = max(1, f.physical.height())
    rx0 = inter.x() - f.physical.x()
    ry0 = inter.y() - f.physical.y()
    rx1 = rx0 + inter.width()
    ry1 = ry0 + inter.height()
    lx0 = int(math.floor(rx0 * gw / pw))
    ly0 = int(math.floor(ry0 * gh / ph))
    lx1 = int(math.ceil(rx1 * gw / pw))
    ly1 = int(math.ceil(ry1 * gh / ph))
    return QRect(lx0, ly0, max(1, lx1 - lx0), max(1, ly1 - ly0))


def _crop_piece_from_physical(f: ScreenFreeze, inter: QRect) -> QImage | None:
    """Crop grab buffer for physical intersection with this monitor."""
    if inter.isEmpty() or inter.width() < 1 or inter.height() < 1:
        return None
    img = f.pixmap.toImage()
    if img.isNull():
        return None
    # grabWindow pixmaps keep devicePixelRatio > 1; force 1:1 for stitch.
    img.setDevicePixelRatio(1.0)
    img_w, img_h = img.width(), img.height()
    pw = max(1, f.physical.width())
    ph = max(1, f.physical.height())
    rx0 = inter.x() - f.physical.x()
    ry0 = inter.y() - f.physical.y()
    rx1 = rx0 + inter.width()
    ry1 = ry0 + inter.height()
    x0 = int(math.floor(rx0 * img_w / pw))
    y0 = int(math.floor(ry0 * img_h / ph))
    x1 = int(math.ceil(rx1 * img_w / pw))
    y1 = int(math.ceil(ry1 * img_h / ph))
    x0 = max(0, min(x0, img_w))
    y0 = max(0, min(y0, img_h))
    x1 = max(x0 + 1, min(x1, img_w))
    y1 = max(y0 + 1, min(y1, img_h))
    if (
        inter.x() <= f.physical.x()
        and inter.y() <= f.physical.y()
        and inter.right() >= f.physical.right()
        and inter.bottom() >= f.physical.bottom()
    ):
        x0, y0, x1, y1 = 0, 0, img_w, img_h
    piece = img.copy(x0, y0, x1 - x0, y1 - y0)
    if piece.isNull():
        return None
    piece.setDevicePixelRatio(1.0)
    if piece.format() not in (
        QImage.Format.Format_RGB32,
        QImage.Format.Format_ARGB32,
        QImage.Format.Format_ARGB32_Premultiplied,
    ):
        piece = piece.convertToFormat(QImage.Format.Format_ARGB32)
        piece.setDevicePixelRatio(1.0)
    return piece


def _to_pixmap(img: QImage) -> QPixmap:
    """QPixmap from physical crop buffer; never inherit monitor DPR."""
    img.setDevicePixelRatio(1.0)
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(1.0)
    return pm


def crop_selection(freezes: list[ScreenFreeze], sel: QRect) -> QPixmap | None:
    """
    Stitch crop in physical space.

    Selection is a single physical rectangle; each monitor contributes
    sel ∩ monitor_physical at that absolute physical position.
    """
    if sel.isEmpty() or sel.width() < MIN_SIZE or sel.height() < MIN_SIZE:
        return None

    pieces: list[tuple[int, int, QImage]] = []
    for f in freezes:
        inter = sel.intersected(f.physical)
        if inter.isEmpty():
            continue
        img = _crop_piece_from_physical(f, inter)
        if img is None:
            continue
        pieces.append((inter.x(), inter.y(), img))

    if not pieces:
        return None
    if len(pieces) == 1:
        return _to_pixmap(pieces[0][2])

    min_x = min(p[0] for p in pieces)
    min_y = min(p[1] for p in pieces)
    max_x = max(p[0] + p[2].width() for p in pieces)
    max_y = max(p[1] + p[2].height() for p in pieces)
    # Use selection bounds so real physical gaps stay black
    min_x = min(min_x, sel.x())
    min_y = min(min_y, sel.y())
    max_x = max(max_x, sel.x() + sel.width())
    max_y = max(max_y, sel.y() + sel.height())
    out = QImage(max_x - min_x, max_y - min_y, QImage.Format.Format_ARGB32)
    out.setDevicePixelRatio(1.0)
    out.fill(QColor(0, 0, 0, 255))
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    for x, y, img in pieces:
        painter.drawImage(x - min_x, y - min_y, img)
    painter.end()
    return _to_pixmap(out)
