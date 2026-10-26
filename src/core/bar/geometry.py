from PyQt6.QtCore import QRect

from core.validation.bar import BarConfig


def bar_length(config: BarConfig, screen: QRect, content_length: int) -> int:
    margin = config.margin
    if config.vertical:
        screen_length, available = screen.height(), screen.height() - margin.top - margin.bottom
    else:
        screen_length, available = screen.width(), screen.width() - margin.left - margin.right
    if config.length == "auto":
        length = content_length
    elif isinstance(config.length, str):
        length = screen_length * int(config.length[:-1]) // 100
    else:
        length = config.length
    return max(0, min(length, available))


def _aligned(start: int, end: int, length: int, align: str) -> int:
    if align == "center":
        return start + max(0, (end - start - length) // 2)
    if align in ("right", "bottom"):
        return max(end - length, start)
    return min(start, end - length)


def bar_geometry(config: BarConfig, screen: QRect, length: int) -> QRect:
    margin, thickness = config.margin, config.thickness
    if config.vertical:
        y = _aligned(screen.y() + margin.top, screen.y() + screen.height() - margin.bottom, length, config.align)
        if config.edge == "right":
            x = screen.x() + screen.width() - thickness - margin.right
        else:
            x = screen.x() + margin.left
        return QRect(x, y, thickness, length)

    x = _aligned(screen.x() + margin.left, screen.x() + screen.width() - margin.right, length, config.align)
    if config.edge == "bottom":
        y = screen.y() + screen.height() - thickness - margin.bottom
    else:
        y = screen.y() + margin.top
    return QRect(x, y, length, thickness)
