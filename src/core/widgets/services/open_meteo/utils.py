from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget


def copy_painter_state(source: QPainter, destination: QPainter):
    """Copy all the essential painter state from source to destination"""
    destination.setPen(source.pen())
    destination.setBrush(source.brush())
    destination.setFont(source.font())
    destination.setBackground(source.background())
    destination.setBackgroundMode(source.backgroundMode())
    destination.setOpacity(source.opacity())
    destination.setTransform(source.transform())
    destination.setRenderHints(source.renderHints())


def create_path_from_points(points: list[QPointF]) -> QPainterPath:
    """Create a path from a list of points using quadratic bezier curves"""
    if not points:
        return QPainterPath()
    path = QPainterPath(points[0])
    for i in range(1, len(points)):
        # Curve path
        if i < len(points) - 1:
            mid_x = (points[i].x() + points[i + 1].x()) / 2
            mid_y = (points[i].y() + points[i + 1].y()) / 2
            path.quadTo(points[i], QPointF(mid_x, mid_y))
        else:
            path.lineTo(points[i])
    return path


def find_point_and_percent(path: QPainterPath, x: float, tolerance: float = 0.05) -> tuple[QPointF, float]:
    """
    Find the point and percent of the path that is closest to the given global x coordinate.
    Since path is guaranteed to be x-monotonic (at least in hourly line case) binary search is appropriate.
    """
    l, r = 0.0, 1.0
    for _ in range(100):
        mid = (l + r) / 2
        pt = path.pointAtPercent(mid)
        diff = pt.x() - x
        if abs(diff) < tolerance:
            return pt, mid
        if diff < 0:
            l = mid
        else:
            r = mid
    return path.pointAtPercent((l + r) / 2), (l + r) / 2


class ColorFetchWidget(QWidget):
    """Dummy invisible widget to get colors from the stylesheet based on class name"""

    def __init__(
        self,
        parent: QWidget | None,
        class_name: str,
    ):
        super().__init__(parent=parent)
        self.setProperty("class", class_name)
        self.setVisible(False)
        self.setEnabled(False)

    def get_colors(self):
        self.ensurePolished()
        palette = self.palette()
        color = palette.color(self.foregroundRole())
        background_color = palette.color(self.backgroundRole())
        return color, background_color
