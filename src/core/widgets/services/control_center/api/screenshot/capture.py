"""Per-monitor freeze capture (Qt grab + Win32 physical rects)."""

from dataclasses import dataclass

import win32api
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QGuiApplication, QPixmap


@dataclass(frozen=True)
class ScreenFreeze:
    """One monitor freeze: Qt logical geometry + grab pixmap + Win32 physical rect."""

    geo: QRect  # QScreen.geometry() - global logical (overlay widget)
    physical: QRect  # EnumDisplayMonitors - global physical (selection / crop)
    pixmap: QPixmap


def physical_monitors() -> list[QRect]:
    out: list[QRect] = []
    for _h, _hdc, rc in win32api.EnumDisplayMonitors(None, None):
        l, t, r, b = rc
        out.append(QRect(l, t, r - l, b - t))
    return out


def capture_screens() -> list[ScreenFreeze] | None:
    """
    Freeze each QScreen with grabWindow
    """
    screens = list(QGuiApplication.screens())
    if not screens:
        return None

    # Pair logical QScreens with physical monitor rects by sorted position.
    mons = physical_monitors()
    mons.sort(key=lambda r: (r.x(), r.y()))
    screens_sorted = sorted(screens, key=lambda s: (s.geometry().x(), s.geometry().y()))

    freezes: list[ScreenFreeze] = []
    for i, s in enumerate(screens_sorted):
        geo = QRect(s.geometry())
        pm = s.grabWindow(0)
        if pm.isNull() or geo.isEmpty():
            return None
        dpr = float(s.devicePixelRatio())
        if abs(pm.devicePixelRatio() - dpr) > 0.01:
            pm.setDevicePixelRatio(dpr)
        # Fallback physical rect if monitor count mismatches.
        if i < len(mons):
            physical = QRect(mons[i])
        else:
            physical = QRect(
                int(round(geo.x() * dpr)),
                int(round(geo.y() * dpr)),
                pm.width(),
                pm.height(),
            )
        freezes.append(ScreenFreeze(geo=geo, physical=physical, pixmap=pm))
    return freezes
