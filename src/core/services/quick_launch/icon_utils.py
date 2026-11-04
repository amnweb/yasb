from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_ICON_CACHE: dict[str, QPixmap] = {}


def load_and_scale_icon(icon_path: str, size: int, dpr: float = 1.0) -> QPixmap:
    key = f"{icon_path}_{size}_{dpr}"
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    try:
        target = int(size * dpr)
        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            return QPixmap()
        scaled = pixmap.scaled(
            QSize(target, target),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        _ICON_CACHE[key] = scaled
        return scaled
    except Exception:
        return QPixmap()


def svg_to_pixmap(svg_text: str, size: int, dpr: float = 1.0) -> QPixmap:

    key = f"svg_{hash(svg_text)}_{size}_{dpr}"
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    try:
        renderer = QSvgRenderer(svg_text.encode("utf-8"))
        if not renderer.isValid():
            return QPixmap()
        target = int(size * dpr)
        pixmap = QPixmap(target, target)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        vb = renderer.viewBoxF()
        if vb.width() > 0 and vb.height() > 0:
            from PyQt6.QtCore import QRectF

            aspect = vb.width() / vb.height()
            if aspect > 1:
                w = target
                h = target / aspect
            else:
                h = target
                w = target * aspect
            x = (target - w) / 2
            y = (target - h) / 2
            renderer.render(painter, QRectF(x, y, w, h))
        else:
            renderer.render(painter)
        painter.end()
        pixmap.setDevicePixelRatio(dpr)
        _ICON_CACHE[key] = pixmap
        return pixmap
    except Exception:
        return QPixmap()
