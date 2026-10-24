from __future__ import annotations

from functools import lru_cache
from typing import Literal

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

SINGLE_NOTE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
\t<g fill="none">
\t\t<path fill="{fill_color}" d="M19.95 3.98L18.4 7.66l-6.7-1.33l.76-4.49zm-8.37 14.58a3.76 3.76 0 1 1-7.53 0a3.76 3.76 0 0 1 7.53 0" opacity="{fill_opacity}" />
\t\t<path stroke="{stroke_color}" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M11.57 18.56a3.75 3.75 0 0 1-3.76 3.76a3.76 3.76 0 1 1 3.76-3.76m.01 0l.02-12.22m0 0V5.29c-.02-1.86-.02-2.79.59-3.24c.6-.45 1.5-.19 3.27.35l3.6 1.09l.06.02a1 1 0 0 1 .68.98v.34a3 3 0 0 1-3.68 2.78l-.33-.09z" />
\t</g>
</svg>"""

BEAMED_NOTES_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
\t<g fill="none">
\t\t<rect width="3.97" height="11.92" fill="{fill_color}" opacity="{fill_opacity}" rx="1" transform="rotate(72.37 6.06 17.17)scale(-1 1)" />
\t\t<path fill="{fill_color}" d="M8.46 19.07a2.73 2.73 0 1 1-5.46 0a2.73 2.73 0 0 1 5.46 0m12.02-1.79a2.73 2.73 0 1 1-5.46 0a2.73 2.73 0 0 1 5.46 0" opacity="{fill_opacity}" />
\t\t<path stroke="{stroke_color}" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8.46 19.07a2.7 2.7 0 0 1-2.73 2.73a2.73 2.73 0 1 1 2.73-2.73m12.02-1.79a2.7 2.7 0 0 1-2.73 2.73a2.73 2.73 0 1 1 2.73-2.73" />
\t\t<path stroke="{stroke_color}" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M20.48 17.4V6.89c0-2.57 0-3.86-.85-4.45c-.84-.6-2.05-.18-4.47.67l-2.68.94c-1.94.68-2.91 1.01-3.47 1.8c-.55.77-.55 1.8-.55 3.86v9.18m0-8.72l11.66-4.3" />
\t</g>
</svg>"""


def derive_similar_palette_color(color: QColor) -> QColor:
    """Return a nearby color with a small lightness shift."""
    hsl = color.getHslF()
    h, s, l = (hsl[0] or 0.0, hsl[1] or 0.0, hsl[2] or 0.0) if hsl else (0.0, 0.0, 0.0)
    if h < 0:
        h = 0.0
    new_l = min(0.92, max(0.22, l + (0.16 if l < 0.55 else -0.16)))
    new_s = max(0.20, min(1.0, s * 0.92))
    return QColor.fromHslF(h, new_s, new_l)


def get_two_tone_colors(
    primary: QColor | None,
    secondary: QColor | None = None,
) -> tuple[QColor, QColor]:
    if primary is None or not primary.isValid():
        col1 = QColor(167, 139, 250)  # Soft violet fallback
    else:
        col1 = primary

    if secondary is not None and secondary.isValid():
        hsl1 = col1.getHslF()
        hsl2 = secondary.getHslF()
        h1 = (hsl1[0] or 0.0) if hsl1 else 0.0
        h2 = (hsl2[0] or 0.0) if hsl2 else 0.0
        if h1 >= 0 and h2 >= 0:
            h_diff = abs(h2 - h1)
            h_diff = min(h_diff, 1.0 - h_diff)
            if h_diff <= 0.18:
                return (col1, secondary)

    col2 = derive_similar_palette_color(col1)
    return (col1, col2)


@lru_cache(maxsize=128)
def _get_cached_svg_renderer(
    variant: str,
    stroke_color_hex: str,
    fill_color_hex: str,
    fill_opacity: float,
) -> QSvgRenderer:
    template = BEAMED_NOTES_SVG if variant == "beamed" else SINGLE_NOTE_SVG
    svg_str = template.format(
        stroke_color=stroke_color_hex,
        fill_color=fill_color_hex,
        fill_opacity=f"{fill_opacity:.2f}",
    )
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    return renderer


def paint_two_tone_note(
    painter: QPainter,
    rect: QRectF,
    variant: Literal["single", "beamed"] = "single",
    stroke_color: QColor | None = None,
    fill_color: QColor | None = None,
    fill_opacity: float = 0.25,
    opacity: float = 1.0,
) -> None:
    s_col = stroke_color or QColor(255, 255, 255)
    f_col = fill_color or s_col
    renderer = _get_cached_svg_renderer(
        variant=variant,
        stroke_color_hex=s_col.name(),
        fill_color_hex=f_col.name(),
        fill_opacity=round(fill_opacity, 2),
    )
    painter.save()
    if opacity < 0.999:
        painter.setOpacity(max(0.0, min(1.0, painter.opacity() * opacity)))
    renderer.render(painter, rect)
    painter.restore()


def create_two_tone_note_pixmap(
    size: int,
    variant: Literal["single", "beamed"] = "beamed",
    stroke_color: QColor | None = None,
    fill_color: QColor | None = None,
    fill_opacity: float = 0.25,
) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    paint_two_tone_note(
        painter,
        QRectF(0, 0, size, size),
        variant=variant,
        stroke_color=stroke_color,
        fill_color=fill_color,
        fill_opacity=fill_opacity,
    )
    painter.end()
    return pix
