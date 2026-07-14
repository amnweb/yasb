"""Drawing helpers for the screenshot editor (arrow, blur, circle, …)."""

from PyQt6.QtCore import QPoint, QPointF, QRect, Qt
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap, QPolygonF


def draw_arrow(p: QPainter, a: QPoint, b: QPoint, color: QColor, width: int = 3) -> None:
    """Arrow: shaft stops at the head so thick strokes don't form a teardrop."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    tip = QPointF(b)
    start = QPointF(a)
    v = tip - start
    length = (v.x() ** 2 + v.y() ** 2) ** 0.5
    if length < 2:
        return

    ux, uy = v.x() / length, v.y() / length
    # Head scales with stroke width; keep it shorter than the shaft.
    head_len = max(10.0, float(width) * 3.2)
    head_half = max(5.0, float(width) * 1.6)
    if head_len > length * 0.55:
        head_len = max(6.0, length * 0.45)
        head_half = max(4.0, head_len * 0.45)

    # End shaft at the base of the triangle (not at the tip).
    base = tip - QPointF(ux * head_len, uy * head_len)
    px, py = -uy, ux
    left = base + QPointF(px * head_half, py * head_half)
    right = base - QPointF(px * head_half, py * head_half)

    pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if length > head_len + 1:
        p.drawLine(start, base)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color))
    p.drawPolygon(QPolygonF([tip, left, right]))


def draw_rect_stroke(p: QPainter, a: QPoint, b: QPoint, color: QColor, width: int = 3) -> None:
    """Sharp-corner rectangle (miter joins; no round caps / no AA soften)."""
    # Antialiasing rounds outer corners of thick strokes - keep it off for boxes.
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    pen = QPen(
        color,
        width,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.FlatCap,
        Qt.PenJoinStyle.MiterJoin,
    )
    pen.setMiterLimit(4.0)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(QRect(a, b).normalized())


def draw_ellipse_stroke(p: QPainter, a: QPoint, b: QPoint, color: QColor, width: int = 3) -> None:
    """Ellipse / circle outline from drag rect (smooth AA)."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(
        color,
        width,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRect(a, b).normalized())


def draw_pen_segment(
    p: QPainter,
    a: QPoint,
    b: QPoint,
    color: QColor,
    width: int = 3,
    *,
    alpha: int | None = None,
) -> None:
    """Solid pen, or highlighter when alpha is set (0-255)."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    c = QColor(color)
    if alpha is not None:
        c.setAlpha(max(0, min(255, int(alpha))))
    p.setPen(
        QPen(
            c,
            width,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    p.drawLine(a, b)


def apply_blur_region(layer: QPixmap, composite: QPixmap, r: QRect, strength: int = 5) -> None:
    """
    Soft frosted blur into layer over rect r (image-buffer coords).

    Multi-pass smooth scale - not chunky pixelation.
    strength: 1 (light) … 10 (heavy).
    """
    bounds = QRect(0, 0, composite.width(), composite.height())
    r = r.intersected(bounds)
    if r.width() < 4 or r.height() < 4:
        return
    src = composite.toImage().copy(r)
    if src.isNull():
        return
    if src.format() != QImage.Format.Format_ARGB32_Premultiplied:
        src = src.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)

    w, h = src.width(), src.height()
    s = max(1, min(10, int(strength)))
    # Higher strength -> smaller intermediate size -> stronger frost.
    factor = 2 + s  # 3 … 12
    sw = max(1, w // factor)
    sh = max(1, h // factor)
    passes = 2 + s // 3  # 2 … 5

    blurred = src
    for _ in range(passes):
        blurred = blurred.scaled(
            sw,
            sh,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        blurred = blurred.scaled(
            w,
            h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    lp = QPainter(layer)
    lp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    lp.drawImage(r.topLeft(), blurred)
    lp.end()
