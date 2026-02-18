import math
import random
import re

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QWidget

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult
from core.utils.widgets.quick_launch.providers.resources.icons import ICON_COLOR, ICON_COLOR_PICKER

# Constants

_D65_X, _D65_Y, _D65_Z = 0.95047, 1.0, 1.08883

# Command regexes

_CONTRAST_RE = re.compile(r"^(?:contrast|vs)\s+(.+?)\s+(?:vs\.?|and|&)\s+(.+)$", re.IGNORECASE)
_MIX_RE = re.compile(r"^mix\s+(.+?)\s+(?:and|&|\+)\s+(.+?)(?:\s+(\d+))?$", re.IGNORECASE)
_LIGHTEN_RE = re.compile(r"^lighten\s+(.+?)\s+(\d+)%?$", re.IGNORECASE)
_DARKEN_RE = re.compile(r"^darken\s+(.+?)\s+(\d+)%?$", re.IGNORECASE)
_RANDOM_RE = re.compile(r"^random$", re.IGNORECASE)
_BLINDNESS_RE = re.compile(r"^(?:blind|cvd|colorblind)\s+(.+)$", re.IGNORECASE)
_HARMONY_RE = re.compile(r"^(?:harmony|harmonies)\s+(.+)$", re.IGNORECASE)

# Color parsing regexes

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGB_RE = re.compile(r"^rgb\s*\(\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})\s*\)$", re.IGNORECASE)
_RGBA_RE = re.compile(
    r"^rgba\s*\(\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})\s*[,/\s]\s*([\d.]+)%?\s*\)$", re.IGNORECASE
)
_RGB_PLAIN_RE = re.compile(r"^(\d{1,3})\s*[,\s]\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})$")
_HSL_RE = re.compile(r"^hsl\s*\(\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})%?\s*[,\s]\s*(\d{1,3})%?\s*\)$", re.IGNORECASE)
_HWB_RE = re.compile(r"^hwb\s*\(\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})%?\s*[,\s]\s*(\d{1,3})%?\s*\)$", re.IGNORECASE)
_LAB_RE = re.compile(r"^lab\s*\(\s*([\d.]+)\s*[,\s]\s*(-?[\d.]+)\s*[,\s]\s*(-?[\d.]+)\s*\)$", re.IGNORECASE)
_LCH_RE = re.compile(r"^lch\s*\(\s*([\d.]+)\s*[,\s]\s*([\d.]+)\s*[,\s]\s*([\d.]+)\s*\)$", re.IGNORECASE)
_OKLAB_RE = re.compile(r"^oklab\s*\(\s*([\d.]+)\s*[,\s]\s*(-?[\d.]+)\s*[,\s]\s*(-?[\d.]+)\s*\)$", re.IGNORECASE)
_OKLCH_RE = re.compile(r"^oklch\s*\(\s*([\d.]+)\s*[,\s]\s*([\d.]+)\s*[,\s]\s*([\d.]+)\s*\)$", re.IGNORECASE)

# Named CSS colors

_NAMED_COLORS: dict[str, str] = {
    "black": "#000000",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "green": "#008000",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "orange": "#FFA500",
    "purple": "#800080",
    "pink": "#FFC0CB",
    "brown": "#A52A2A",
    "gray": "#808080",
    "grey": "#808080",
    "silver": "#C0C0C0",
    "gold": "#FFD700",
    "navy": "#000080",
    "teal": "#008080",
    "maroon": "#800000",
    "olive": "#808000",
    "lime": "#00FF00",
    "aqua": "#00FFFF",
    "fuchsia": "#FF00FF",
    "coral": "#FF7F50",
    "salmon": "#FA8072",
    "turquoise": "#40E0D0",
    "violet": "#EE82EE",
    "indigo": "#4B0082",
    "crimson": "#DC143C",
    "khaki": "#F0E68C",
    "plum": "#DDA0DD",
    "sienna": "#A0522D",
    "tomato": "#FF6347",
    "peru": "#CD853F",
    "tan": "#D2B48C",
    "wheat": "#F5DEB3",
    "lavender": "#E6E6FA",
    "beige": "#F5F5DC",
    "ivory": "#FFFFF0",
    "mint": "#98FF98",
    "chartreuse": "#7FFF00",
    "azure": "#F0FFFF",
    "skyblue": "#87CEEB",
    "steelblue": "#4682B4",
    "firebrick": "#B22222",
    "darkred": "#8B0000",
    "darkgreen": "#006400",
    "darkblue": "#00008B",
    "darkcyan": "#008B8B",
    "darkmagenta": "#8B008B",
    "darkorange": "#FF8C00",
    "darkviolet": "#9400D3",
    "deeppink": "#FF1493",
    "deepskyblue": "#00BFFF",
    "dodgerblue": "#1E90FF",
    "hotpink": "#FF69B4",
    "lightblue": "#ADD8E6",
    "lightcoral": "#F08080",
    "lightgreen": "#90EE90",
    "lightyellow": "#FFFFE0",
    "lightgray": "#D3D3D3",
    "lightgrey": "#D3D3D3",
    "royalblue": "#4169E1",
    "slategray": "#708090",
    "slategrey": "#708090",
}


# SVG Helpers


def _color_swatch_svg(hex_color: str) -> str:
    """Return an inline SVG of a small rounded square filled with the given color."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
        f'<rect width="24" height="24" rx="5" ry="5" fill="{hex_color}"/>'
        f"</svg>"
    )


def _split_swatch_svg(hex_left: str, hex_right: str) -> str:
    """Return an inline SVG with two colors side-by-side, rounded only on the outer edges."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
        f'<rect width="24" height="24" rx="5" ry="5" fill="{hex_right}"/>'
        f'<path d="M5,0 H12 V24 H5 A5,5 0 0,1 0,19 V5 A5,5 0 0,1 5,0 Z" fill="{hex_left}"/>'
        "</svg>"
    )


def _generate_palette(r: int, g: int, b: int, steps: int = 11) -> list[tuple[int, int, int, str]]:
    """Generate a palette of shades from light to dark for a given RGB color.

    Returns a list of (r, g, b, hex) tuples. Lightness ranges from 95% to 5%
    to avoid pure white and pure black extremes.
    """
    h, s, _ = _rgb_to_hsl(r, g, b)
    palette: list[tuple[int, int, int, str]] = []
    l_max, l_min = 95, 5
    for i in range(steps):
        l = round(l_max - (i * (l_max - l_min) / (steps - 1)))
        pr, pg, pb = _hsl_to_rgb(h, s, l)
        palette.append((pr, pg, pb, _rgb_to_hex(pr, pg, pb)))
    return palette


# WCAG Contrast Ratio


def _relative_luminance(r: int, g: int, b: int) -> float:
    """Compute relative luminance per WCAG 2.x definition."""
    rs = _srgb_to_linear(r / 255)
    gs = _srgb_to_linear(g / 255)
    bs = _srgb_to_linear(b / 255)
    return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs


def _contrast_ratio(r1: int, g1: int, b1: int, r2: int, g2: int, b2: int) -> float:
    """Return the WCAG contrast ratio between two colors (1:1 to 21:1)."""
    l1 = _relative_luminance(r1, g1, b1)
    l2 = _relative_luminance(r2, g2, b2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _wcag_grade(ratio: float) -> str:
    """Return WCAG pass/fail string for normal and large text."""
    parts: list[str] = []
    if ratio >= 7:
        parts.append("AAA")
    elif ratio >= 4.5:
        parts.append("AA")
    else:
        parts.append("Fail")
    if ratio >= 4.5:
        parts.append("AAA Large")
    elif ratio >= 3:
        parts.append("AA Large")
    return " - ".join(parts)


# Color Harmonies


def _harmonies(r: int, g: int, b: int) -> dict[str, list[tuple[int, int, int, str]]]:
    """Return color harmonies: complementary, analogous, triadic, split-complementary, tetradic."""
    h, s, l = _rgb_to_hsl(r, g, b)
    result: dict[str, list[tuple[int, int, int, str]]] = {}

    def _from_hue(hue: float) -> tuple[int, int, int, str]:
        hue = hue % 360
        cr, cg, cb = _hsl_to_rgb(round(hue), s, l)
        return cr, cg, cb, _rgb_to_hex(cr, cg, cb)

    result["Complementary"] = [_from_hue(h + 180)]
    result["Analogous"] = [_from_hue(h - 30), _from_hue(h + 30)]
    result["Triadic"] = [_from_hue(h + 120), _from_hue(h + 240)]
    result["Split-Complementary"] = [_from_hue(h + 150), _from_hue(h + 210)]
    result["Tetradic"] = [_from_hue(h + 90), _from_hue(h + 180), _from_hue(h + 270)]
    return result


# Mix / Blend


def _mix_colors(
    r1: int, g1: int, b1: int, r2: int, g2: int, b2: int, steps: int = 5
) -> list[tuple[int, int, int, str, int]]:
    """Mix two colors producing intermediate steps. Returns list of (r, g, b, hex, pct)."""
    result: list[tuple[int, int, int, str, int]] = []
    for i in range(steps):
        t = i / (steps - 1) if steps > 1 else 0.5
        pct = round(t * 100)
        mr = round(r1 + (r2 - r1) * t)
        mg = round(g1 + (g2 - g1) * t)
        mb = round(b1 + (b2 - b1) * t)
        result.append((mr, mg, mb, _rgb_to_hex(mr, mg, mb), pct))
    return result


# Lighten / Darken


def _adjust_lightness(r: int, g: int, b: int, amount: int, lighten: bool = True) -> tuple[int, int, int, str]:
    """Lighten or darken a color by adjusting L in HSL by the given percentage points."""
    h, s, l = _rgb_to_hsl(r, g, b)
    l = min(100, l + amount) if lighten else max(0, l - amount)
    nr, ng, nb = _hsl_to_rgb(h, s, l)
    return nr, ng, nb, _rgb_to_hex(nr, ng, nb)


# Color Blindness Simulation


def _simulate_cvd(r: int, g: int, b: int) -> dict[str, tuple[int, int, int, str]]:
    """Simulate color vision deficiency using Brettel/Viénot matrices.

    Returns dict with keys: Protanopia (no red cones), Deuteranopia (no green cones),
    Tritanopia (no blue cones), Achromatopsia (total color blindness).
    """
    rl = _srgb_to_linear(r / 255)
    gl = _srgb_to_linear(g / 255)
    bl = _srgb_to_linear(b / 255)

    # Viénot simulation matrices
    matrices = {
        "Protanopia": (
            (0.152286, 1.052583, -0.204868),
            (0.114503, 0.786281, 0.099216),
            (-0.003882, -0.048116, 1.051998),
        ),
        "Deuteranopia": (
            (0.367322, 0.860646, -0.227968),
            (0.280085, 0.672501, 0.047413),
            (-0.011820, 0.042940, 0.968881),
        ),
        "Tritanopia": (
            (1.255528, -0.076749, -0.178779),
            (-0.078411, 0.930809, 0.147602),
            (0.004733, 0.691367, 0.303900),
        ),
    }

    result: dict[str, tuple[int, int, int, str]] = {}
    for name, mat in matrices.items():
        sr = mat[0][0] * rl + mat[0][1] * gl + mat[0][2] * bl
        sg = mat[1][0] * rl + mat[1][1] * gl + mat[1][2] * bl
        sb = mat[2][0] * rl + mat[2][1] * gl + mat[2][2] * bl
        nr = round(_linear_to_srgb(max(0.0, min(1.0, sr))) * 255)
        ng = round(_linear_to_srgb(max(0.0, min(1.0, sg))) * 255)
        nb = round(_linear_to_srgb(max(0.0, min(1.0, sb))) * 255)
        nr, ng, nb = max(0, min(255, nr)), max(0, min(255, ng)), max(0, min(255, nb))
        result[name] = (nr, ng, nb, _rgb_to_hex(nr, ng, nb))

    # Achromatopsia (total color blindness) - just luminance
    gray = round(0.2126 * rl + 0.7152 * gl + 0.0722 * bl, 6)
    gv = round(_linear_to_srgb(max(0.0, min(1.0, gray))) * 255)
    gv = max(0, min(255, gv))
    result["Achromatopsia"] = (gv, gv, gv, _rgb_to_hex(gv, gv, gv))

    return result


# Color Conversion Helpers


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int, int]:
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
        a = 255
    elif len(hex_str) == 4:
        hex_str = "".join(c * 2 for c in hex_str)
        a = int(hex_str[6:8], 16)
        hex_str = hex_str[:6]
    elif len(hex_str) == 8:
        a = int(hex_str[6:8], 16)
        hex_str = hex_str[:6]
    else:
        a = 255
    r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    return r, g, b, a


def _rgb_to_hex(r: int, g: int, b: int, a: int = 255) -> str:
    if a < 255:
        return f"#{r:02X}{g:02X}{b:02X}{a:02X}"
    return f"#{r:02X}{g:02X}{b:02X}"


def _rgb_to_hsl(r: int, g: int, b: int) -> tuple[int, int, int]:
    r1, g1, b1 = r / 255, g / 255, b / 255
    mx, mn = max(r1, g1, b1), min(r1, g1, b1)
    l = (mx + mn) / 2
    if mx == mn:
        h = s = 0
    else:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r1:
            h = (g1 - b1) / d + (6 if g1 < b1 else 0)
        elif mx == g1:
            h = (b1 - r1) / d + 2
        else:
            h = (r1 - g1) / d + 4
        h /= 6
    return round(h * 360), round(s * 100), round(l * 100)


def _hsl_to_rgb(h: int, s: int, l: int) -> tuple[int, int, int]:
    h1, s1, l1 = h / 360, s / 100, l / 100
    if s1 == 0:
        v = round(l1 * 255)
        return v, v, v

    def hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l1 * (1 + s1) if l1 < 0.5 else l1 + s1 - l1 * s1
    p = 2 * l1 - q
    r = round(hue_to_rgb(p, q, h1 + 1 / 3) * 255)
    g = round(hue_to_rgb(p, q, h1) * 255)
    b = round(hue_to_rgb(p, q, h1 - 1 / 3) * 255)
    return r, g, b


def _rgb_to_hsv(r: int, g: int, b: int) -> tuple[int, int, int]:
    r1, g1, b1 = r / 255, g / 255, b / 255
    mx, mn = max(r1, g1, b1), min(r1, g1, b1)
    v = mx
    d = mx - mn
    s = 0 if mx == 0 else d / mx
    if mx == mn:
        h = 0
    elif mx == r1:
        h = (g1 - b1) / d + (6 if g1 < b1 else 0)
    elif mx == g1:
        h = (b1 - r1) / d + 2
    else:
        h = (r1 - g1) / d + 4
    h /= 6
    return round(h * 360), round(s * 100), round(v * 100)


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _rgb_to_hwb(r: int, g: int, b: int) -> tuple[int, int, int]:
    h, _, _ = _rgb_to_hsl(r, g, b)
    w = min(r, g, b) / 255 * 100
    bk = (1 - max(r, g, b) / 255) * 100
    return h, round(w), round(bk)


def _hwb_to_rgb(h: int, w: int, bk: int) -> tuple[int, int, int]:
    w1, b1 = w / 100, bk / 100
    if w1 + b1 >= 1:
        gray = round(w1 / (w1 + b1) * 255)
        return gray, gray, gray
    r0, g0, b0 = _hsl_to_rgb(h, 100, 50)
    f = 1 - w1 - b1
    r = round((r0 / 255) * f * 255 + w1 * 255)
    g = round((g0 / 255) * f * 255 + w1 * 255)
    b = round((b0 / 255) * f * 255 + w1 * 255)
    return max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))


def _rgb_to_xyz(r: int, g: int, b: int) -> tuple[float, float, float]:
    rl = _srgb_to_linear(r / 255)
    gl = _srgb_to_linear(g / 255)
    bl = _srgb_to_linear(b / 255)
    x = 0.4124564 * rl + 0.3575761 * gl + 0.1804375 * bl
    y = 0.2126729 * rl + 0.7151522 * gl + 0.0721750 * bl
    z = 0.0193339 * rl + 0.1191920 * gl + 0.9503041 * bl
    return x, y, z


def _xyz_to_rgb(x: float, y: float, z: float) -> tuple[int, int, int]:
    rl = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    gl = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    bl = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    r = round(_linear_to_srgb(rl) * 255)
    g = round(_linear_to_srgb(gl) * 255)
    b = round(_linear_to_srgb(bl) * 255)
    return max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))


def _rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    x, y, z = _rgb_to_xyz(r, g, b)

    def _f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = _f(x / _D65_X), _f(y / _D65_Y), _f(z / _D65_Z)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b_val = 200 * (fy - fz)
    return round(L, 2), round(a, 2), round(b_val, 2)


def _lab_to_rgb(L: float, a: float, b_val: float) -> tuple[int, int, int]:
    fy = (L + 16) / 116
    fx = a / 500 + fy
    fz = fy - b_val / 200

    def _finv(t: float) -> float:
        return t**3 if t**3 > 0.008856 else (t - 16 / 116) / 7.787

    x = _finv(fx) * _D65_X
    y = _finv(fy) * _D65_Y
    z = _finv(fz) * _D65_Z
    return _xyz_to_rgb(x, y, z)


def _to_polar(a: float, b: float) -> tuple[float, float]:
    """Convert Cartesian (a, b) to polar (chroma, hue)."""
    return math.sqrt(a * a + b * b), math.degrees(math.atan2(b, a)) % 360


def _from_polar(C: float, H: float) -> tuple[float, float]:
    """Convert polar (chroma, hue) to Cartesian (a, b)."""
    return C * math.cos(math.radians(H)), C * math.sin(math.radians(H))


def _rgb_to_lch(r: int, g: int, b: int) -> tuple[float, float, float]:
    L, a, b_val = _rgb_to_lab(r, g, b)
    C, H = _to_polar(a, b_val)
    return round(L, 2), round(C, 2), round(H, 2)


def _lch_to_rgb(L: float, C: float, H: float) -> tuple[int, int, int]:
    a, b_val = _from_polar(C, H)
    return _lab_to_rgb(L, a, b_val)


def _rgb_to_oklab(r: int, g: int, b: int) -> tuple[float, float, float]:
    rl = _srgb_to_linear(r / 255)
    gl = _srgb_to_linear(g / 255)
    bl = _srgb_to_linear(b / 255)
    l = 0.4122214708 * rl + 0.5363325363 * gl + 0.0514459929 * bl
    m = 0.2119034982 * rl + 0.6806995451 * gl + 0.1073969566 * bl
    s = 0.0883024619 * rl + 0.2024326059 * gl + 0.7092649322 * bl
    l_ = math.copysign(abs(l) ** (1 / 3), l)
    m_ = math.copysign(abs(m) ** (1 / 3), m)
    s_ = math.copysign(abs(s) ** (1 / 3), s)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_val = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return round(L, 4), round(a, 4), round(b_val, 4)


def _oklab_to_rgb(L: float, a: float, b_val: float) -> tuple[int, int, int]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b_val
    m_ = L - 0.1055613458 * a - 0.0638541728 * b_val
    s_ = L - 0.0894841775 * a - 1.2914855480 * b_val
    l = l_**3
    m = m_**3
    s = s_**3
    rl = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    gl = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bl = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    r = round(_linear_to_srgb(rl) * 255)
    g = round(_linear_to_srgb(gl) * 255)
    b = round(_linear_to_srgb(bl) * 255)
    return max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))


def _rgb_to_oklch(r: int, g: int, b: int) -> tuple[float, float, float]:
    L, a, b_val = _rgb_to_oklab(r, g, b)
    C, H = _to_polar(a, b_val)
    return round(L, 4), round(C, 4), round(H, 2)


def _oklch_to_rgb(L: float, C: float, H: float) -> tuple[int, int, int]:
    a, b_val = _from_polar(C, H)
    return _oklab_to_rgb(L, a, b_val)


def _parse_color(text: str) -> tuple[int, int, int, int] | None:
    """Try to parse a color string into (R, G, B, A). Returns None on failure."""
    text = text.strip()

    if text.lower() in _NAMED_COLORS:
        return _hex_to_rgb(_NAMED_COLORS[text.lower()])

    m = _HEX_RE.match(text)
    if m:
        return _hex_to_rgb(m.group(1))

    m = _RGBA_RE.match(text)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a_raw = float(m.group(4))
        a = round(a_raw) if a_raw > 1 else round(a_raw * 255)
        if all(0 <= v <= 255 for v in (r, g, b, a)):
            return r, g, b, a
        return None

    m = _RGB_RE.match(text)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if all(0 <= v <= 255 for v in (r, g, b)):
            return r, g, b, 255
        return None

    m = _RGB_PLAIN_RE.match(text)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if all(0 <= v <= 255 for v in (r, g, b)):
            return r, g, b, 255
        return None

    m = _HSL_RE.match(text)
    if m:
        h, s, l = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 0 <= h <= 360 and 0 <= s <= 100 and 0 <= l <= 100:
            r, g, b = _hsl_to_rgb(h, s, l)
            return r, g, b, 255
        return None

    m = _HWB_RE.match(text)
    if m:
        h, w, bk = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 0 <= h <= 360 and 0 <= w <= 100 and 0 <= bk <= 100:
            r, g, b = _hwb_to_rgb(h, w, bk)
            return r, g, b, 255
        return None

    m = _LAB_RE.match(text)
    if m:
        L, a, b = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if 0 <= L <= 100:
            r, g, b = _lab_to_rgb(L, a, b)
            return r, g, b, 255
        return None

    m = _LCH_RE.match(text)
    if m:
        L, C, H = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if 0 <= L <= 100 and 0 <= H <= 360:
            r, g, b = _lch_to_rgb(L, C, H)
            return r, g, b, 255
        return None

    m = _OKLAB_RE.match(text)
    if m:
        L, a, b = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if 0 <= L <= 1:
            r, g, b = _oklab_to_rgb(L, a, b)
            return r, g, b, 255
        return None

    m = _OKLCH_RE.match(text)
    if m:
        L, C, H = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if 0 <= L <= 1 and 0 <= H <= 360:
            r, g, b = _oklch_to_rgb(L, C, H)
            return r, g, b, 255
        return None

    return None


# Color Picker


class _ColorPickerOverlay(QWidget):
    """Small floating loupe centered on the cursor for picking colors."""

    color_picked = pyqtSignal(str)

    GRID_SIZE = 11
    CELL_SIZE = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.BlankCursor)

        self._src_img: QImage | None = None
        self._current_color = QColor(0, 0, 0)
        self._dpr: float = 1.0
        self._screen_x = 0
        self._screen_y = 0

        grid_px = self.GRID_SIZE * self.CELL_SIZE
        loupe_r = grid_px // 2 + 4
        self._loupe_r = loupe_r
        self._grid_px = grid_px
        self._win_w = loupe_r * 2 + 6
        self._win_h = loupe_r * 2 + 6 + 36
        self.setFixedSize(self._win_w, self._win_h)
        self._wcx = self._win_w // 2
        self._wcy = loupe_r + 3

        self._grid_overlay = QPixmap(grid_px, grid_px)
        self._grid_overlay.fill(Qt.GlobalColor.transparent)
        p = QPainter(self._grid_overlay)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        for i in range(1, self.GRID_SIZE):
            coord = i * self.CELL_SIZE
            p.drawLine(coord, 0, coord, grid_px)
            p.drawLine(0, coord, grid_px, coord)
        p.end()

        self._label_font = QFont("Segoe UI", 9)
        self._label_font.setBold(True)
        self._label_fm = QFontMetrics(self._label_font)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

    def start(self):
        self._capture_screens()
        self._reposition()
        self.show()
        self.activateWindow()
        self.setFocus()
        self._timer.start()

    def _capture_screens(self):
        screens = QApplication.screens()
        if not screens:
            return
        combined = screens[0].geometry()
        for s in screens[1:]:
            combined = combined.united(s.geometry())
        self._screen_x = combined.x()
        self._screen_y = combined.y()
        self._dpr = screens[0].devicePixelRatio()
        px_w = int(combined.width() * self._dpr)
        px_h = int(combined.height() * self._dpr)
        img = QImage(px_w, px_h, QImage.Format.Format_RGB32)
        img.setDevicePixelRatio(self._dpr)
        img.fill(Qt.GlobalColor.black)
        painter = QPainter(img)
        for s in screens:
            geo = s.geometry()
            grab = s.grabWindow(0, 0, 0, geo.width(), geo.height())
            painter.drawPixmap(geo.x() - combined.x(), geo.y() - combined.y(), grab)
        painter.end()
        self._src_img = img.copy()
        self._src_img.setDevicePixelRatio(1.0)

    def _reposition(self):
        pos = QCursor.pos()
        self.move(pos.x() - self._wcx, pos.y() - self._wcy)

    def _on_tick(self):
        self._reposition()
        self.update()

    def paintEvent(self, event):
        if not self._src_img:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pos = QCursor.pos()
        cx = pos.x() - self._screen_x
        cy = pos.y() - self._screen_y
        half = self.GRID_SIZE // 2
        cell = self.CELL_SIZE
        grid_px = self._grid_px
        loupe_r = self._loupe_r
        wcx = self._wcx
        wcy = self._wcy

        src_x = int((cx - half) * self._dpr)
        src_y = int((cy - half) * self._dpr)
        crop = self._src_img.copy(src_x, src_y, self.GRID_SIZE, self.GRID_SIZE)
        zoomed = crop.scaled(
            grid_px,
            grid_px,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

        csx = int(cx * self._dpr)
        csy = int(cy * self._dpr)
        if 0 <= csx < self._src_img.width() and 0 <= csy < self._src_img.height():
            center_color = QColor(self._src_img.pixel(csx, csy))
        else:
            center_color = QColor(0, 0, 0)
        self._current_color = center_color

        loupe_rect = QRectF(wcx - grid_px / 2, wcy - grid_px / 2, grid_px, grid_px)
        circle_rect = QRectF(wcx - loupe_r, wcy - loupe_r, loupe_r * 2, loupe_r * 2)

        painter.save()
        clip_path = QPainterPath()
        clip_path.addEllipse(circle_rect)
        painter.setClipPath(clip_path)
        painter.drawImage(loupe_rect, zoomed)
        painter.drawPixmap(int(loupe_rect.x()), int(loupe_rect.y()), self._grid_overlay)
        painter.restore()

        painter.setPen(QPen(QColor(40, 40, 40, 220), 2.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(circle_rect)

        center_rect = QRectF(loupe_rect.x() + half * cell, loupe_rect.y() + half * cell, cell, cell)
        luma = 0.299 * center_color.red() + 0.587 * center_color.green() + 0.114 * center_color.blue()
        hl = QColor(255, 255, 255) if luma < 128 else QColor(0, 0, 0)
        painter.setPen(QPen(hl, 2))
        painter.drawRect(center_rect)

        hex_str = center_color.name().upper()
        label_y = int(circle_rect.bottom()) + 6
        painter.setFont(self._label_font)
        text_w = self._label_fm.horizontalAdvance(hex_str) + 16
        text_h = self._label_fm.height() + 8
        swatch_sz = text_h - 6
        total_w = swatch_sz + 4 + text_w
        pill_x = wcx - total_w / 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 20, 20, 210))
        painter.drawRoundedRect(QRectF(pill_x, label_y, total_w, text_h), text_h / 2, text_h / 2)

        swatch_rect = QRectF(pill_x + 5, label_y + 3, swatch_sz, swatch_sz)
        painter.setBrush(center_color)
        painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
        painter.drawRoundedRect(swatch_rect, swatch_sz / 2, swatch_sz / 2)

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            QRectF(swatch_rect.right() + 4, label_y, text_w, text_h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            hex_str,
        )
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._timer.stop()
            self.color_picked.emit(self._current_color.name().upper())
            self.close()
        elif event.button() == Qt.MouseButton.RightButton:
            self._timer.stop()
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._timer.stop()
            self.close()


# Color Provider


class ColorProvider(BaseProvider):
    """Pick colors and convert between HEX, RGB, HSL, HSV, HWB, LAB, LCH, OKLAB, and OKLCH."""

    name = "color"
    display_name = "Color"
    input_placeholder = "Enter a color value..."
    icon = ICON_COLOR

    _picker_overlay = None

    def match(self, text: str) -> bool:
        text = text.strip()
        if self.prefix and text.startswith(self.prefix):
            return True
        return False

    def get_results(self, text: str, **kwargs) -> list[ProviderResult]:
        query = self.get_query_text(text).strip()
        if not query:
            return [
                ProviderResult(
                    title="Color Converter",
                    description="Type a color: #hex, rgb(), hsl(), hwb(), lab(), lch(), oklab(), oklch(), or name",
                    icon_char=ICON_COLOR,
                    provider=self.name,
                ),
                ProviderResult(
                    title="Pick Color from Screen",
                    description="Open a magnifying loupe to pick any color from the desktop",
                    icon_char=ICON_COLOR_PICKER,
                    provider=self.name,
                    action_data={"_pick_color": True},
                ),
                ProviderResult(
                    title="Random Color",
                    description="Generate a random color with all conversions",
                    icon_char=ICON_COLOR,
                    provider=self.name,
                    action_data={"_replace_input": "random"},
                ),
                ProviderResult(
                    title="Contrast Check",
                    description="Type: contrast #fff vs #333",
                    icon_char=ICON_COLOR,
                    provider=self.name,
                    action_data={"_replace_input": "contrast "},
                ),
                ProviderResult(
                    title="Mix / Blend",
                    description="Type: mix #ff0000 + #0000ff",
                    icon_char=ICON_COLOR,
                    provider=self.name,
                    action_data={"_replace_input": "mix "},
                ),
                ProviderResult(
                    title="Lighten / Darken",
                    description="Type: lighten #ff6347 20 or darken #ff6347 20",
                    icon_char=ICON_COLOR,
                    provider=self.name,
                    action_data={"_replace_input": "lighten "},
                ),
                ProviderResult(
                    title="Color Harmonies",
                    description="Type: harmony #ff6347",
                    icon_char=ICON_COLOR,
                    provider=self.name,
                    action_data={"_replace_input": "harmony "},
                ),
                ProviderResult(
                    title="Color Blindness Simulation",
                    description="Type: blind #ff6347",
                    icon_char=ICON_COLOR,
                    provider=self.name,
                    action_data={"_replace_input": "blind "},
                ),
            ]

        # --- Random Color ---
        if _RANDOM_RE.match(query):
            results: list[ProviderResult] = []
            for _ in range(20):
                rr, rg, rb = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
                rand_hex = _rgb_to_hex(rr, rg, rb)
                results.append(
                    ProviderResult(
                        title=rand_hex,
                        description=f"rgb({rr}, {rg}, {rb}) - press Enter to view all conversions",
                        icon_char=_color_swatch_svg(rand_hex),
                        provider=self.name,
                        action_data={"_replace_input": rand_hex},
                    )
                )
            return results

        # --- WCAG Contrast ---
        m = _CONTRAST_RE.match(query)
        if m:
            return self._contrast_results(m.group(1).strip(), m.group(2).strip())

        # --- Mix / Blend ---
        m = _MIX_RE.match(query)
        if m:
            return self._mix_results(m.group(1).strip(), m.group(2).strip(), m.group(3))

        # --- Lighten ---
        m = _LIGHTEN_RE.match(query)
        if m:
            return self._adjust_results(m.group(1).strip(), int(m.group(2)), lighten=True)

        # --- Darken ---
        m = _DARKEN_RE.match(query)
        if m:
            return self._adjust_results(m.group(1).strip(), int(m.group(2)), lighten=False)

        # --- Color Blindness ---
        m = _BLINDNESS_RE.match(query)
        if m:
            return self._blindness_results(m.group(1).strip())

        # --- Color Harmonies ---
        m = _HARMONY_RE.match(query)
        if m:
            return self._harmony_results(m.group(1).strip())

        # --- Partial command hints (typed keyword but not enough args) ---
        _PARTIAL_HINTS = [
            (("contrast", "vs"), "Contrast Check", "Enter two colors: contrast #ffffff vs #333333"),
            (("mix",), "Mix / Blend", "Enter two colors: mix #ff0000 + #0000ff"),
            (("lighten",), "Lighten", "Enter a color and amount: lighten #ff6347 20"),
            (("darken",), "Darken", "Enter a color and amount: darken #ff6347 20"),
            (("harmony", "harmonies"), "Color Harmonies", "Enter a color: harmony #ff6347"),
            (("blind", "cvd", "colorblind"), "Color Blindness Simulation", "Enter a color: blind #ff6347"),
        ]
        ql = query.lower().strip()
        for prefixes, title, desc in _PARTIAL_HINTS:
            if any(ql.startswith(p) for p in prefixes):
                return [ProviderResult(title=title, description=desc, icon_char=ICON_COLOR, provider=self.name)]

        parsed = _parse_color(query)
        if parsed is None:
            return [
                ProviderResult(
                    title="Invalid color",
                    description="Try: #FF550090, rgba(255,85,0,0.5), hsl(20,100,50), lab(50,0,0), oklab(0.5,0,0)",
                    icon_char=ICON_COLOR,
                    provider=self.name,
                )
            ]

        r, g, b, a = parsed
        has_alpha = a < 255
        a_frac = round(a / 255, 2)
        swatch = _color_swatch_svg(_rgb_to_hex(r, g, b))

        # Build all color format conversions
        h, s, l = _rgb_to_hsl(r, g, b)
        hv, sv, vv = _rgb_to_hsv(r, g, b)
        hw, ww, bw = _rgb_to_hwb(r, g, b)
        lL, la, lb = _rgb_to_lab(r, g, b)
        cL, cC, cH = _rgb_to_lch(r, g, b)
        oL, oa, ob = _rgb_to_oklab(r, g, b)
        olL, olC, olH = _rgb_to_oklch(r, g, b)

        formats: list[tuple[str, str, str]] = [
            (_rgb_to_hex(r, g, b, a), "HEX", "HEX"),
            (
                f"rgba({r}, {g}, {b}, {a_frac})" if has_alpha else f"rgb({r}, {g}, {b})",
                "RGBA" if has_alpha else "RGB",
                "RGB",
            ),
            (
                f"hsla({h}, {s}%, {l}%, {a_frac})" if has_alpha else f"hsl({h}, {s}%, {l}%)",
                "HSLA" if has_alpha else "HSL",
                "HSL",
            ),
            (
                f"hsva({hv}, {sv}%, {vv}%, {a_frac})" if has_alpha else f"hsv({hv}, {sv}%, {vv}%)",
                "HSVA" if has_alpha else "HSV",
                "HSV",
            ),
            (f"hwb({hw} {ww}% {bw}% / {a_frac})" if has_alpha else f"hwb({hw}, {ww}%, {bw}%)", "HWB", "HWB"),
            (f"lab({lL} {la} {lb} / {a_frac})" if has_alpha else f"lab({lL}, {la}, {lb})", "CIE LAB", "LAB"),
            (f"lch({cL} {cC} {cH} / {a_frac})" if has_alpha else f"lch({cL}, {cC}, {cH})", "CIE LCH", "LCH"),
            (f"oklab({oL} {oa} {ob} / {a_frac})" if has_alpha else f"oklab({oL}, {oa}, {ob})", "OKLAB", "OKLAB"),
            (f"oklch({olL} {olC} {olH} / {a_frac})" if has_alpha else f"oklch({olL}, {olC}, {olH})", "OKLCH", "OKLCH"),
        ]

        results = [
            ProviderResult(
                title=val,
                description=f"{label} - press Enter to copy",
                icon_char=swatch,
                provider=self.name,
                action_data={"value": val},
            )
            for val, label, _ in formats
        ]

        # Generate color palette (lighter/darker shades)
        palette = _generate_palette(r, g, b)
        for pr, pg, pb, p_hex in palette:
            shade_swatch = _color_swatch_svg(p_hex)
            p_rgb = f"rgb({pr}, {pg}, {pb})"
            p_h, p_s, p_l = _rgb_to_hsl(pr, pg, pb)
            p_hsl = f"hsl({p_h}, {p_s}%, {p_l}%)"
            results.append(
                ProviderResult(
                    title=f"{p_hex}",
                    description=f"{p_rgb} - {p_hsl}",
                    icon_char=shade_swatch,
                    provider=self.name,
                    action_data={"_replace_input": p_hex},
                )
            )

        return results

    def execute(self, result: ProviderResult) -> bool:
        if result.action_data.get("_pick_color"):
            return self._launch_color_picker()
        replace_input = result.action_data.get("_replace_input")
        if replace_input:
            self._update_search_input(replace_input)
            return False
        value = result.action_data.get("value", "")
        if value:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(value)
            return True
        return False

    def _update_search_input(self, text: str):
        """Replace the current search input text to show conversions for a palette color."""
        from core.widgets.yasb.quick_launch import QuickLaunchWidget

        widget = QuickLaunchWidget._active_instance
        if widget is None:
            for w in QApplication.allWidgets():
                if isinstance(w, QuickLaunchWidget):
                    widget = w
                    break
        if widget and widget._popup:
            widget._popup.search_input.setText(text)

    def _parse_error(self, text: str, hint: str) -> list[ProviderResult]:
        """Return a single-item error list for an unparseable color string."""
        return [
            ProviderResult(
                title=f"Cannot parse: {text}",
                description=hint,
                icon_char=ICON_COLOR,
                provider=self.name,
            )
        ]

    def _contrast_results(self, text1: str, text2: str) -> list[ProviderResult]:
        """WCAG contrast ratio between two colors."""
        c1 = _parse_color(text1)
        c2 = _parse_color(text2)
        if c1 is None or c2 is None:
            bad = text1 if c1 is None else text2
            return self._parse_error(bad, "Use: contrast #fff vs #333")
        r1, g1, b1, _ = c1
        r2, g2, b2, _ = c2
        ratio = _contrast_ratio(r1, g1, b1, r2, g2, b2)
        grade = _wcag_grade(ratio)
        hex1, hex2 = _rgb_to_hex(r1, g1, b1), _rgb_to_hex(r2, g2, b2)

        # Build a two-tone swatch SVG
        swatch = _split_swatch_svg(hex1, hex2)
        results = [
            ProviderResult(
                title=f"{ratio:.2f}:1",
                description=f"WCAG Contrast - {grade}",
                icon_char=swatch,
                provider=self.name,
                action_data={"value": f"{ratio:.2f}:1"},
            ),
            ProviderResult(
                title=hex1,
                description=f"rgb({r1}, {g1}, {b1}) - press Enter to view conversions",
                icon_char=_color_swatch_svg(hex1),
                provider=self.name,
                action_data={"_replace_input": hex1},
            ),
            ProviderResult(
                title=hex2,
                description=f"rgb({r2}, {g2}, {b2}) - press Enter to view conversions",
                icon_char=_color_swatch_svg(hex2),
                provider=self.name,
                action_data={"_replace_input": hex2},
            ),
        ]
        return results

    def _mix_results(self, text1: str, text2: str, steps_str: str | None) -> list[ProviderResult]:
        """Mix/blend two colors with intermediate steps."""
        c1 = _parse_color(text1)
        c2 = _parse_color(text2)
        if c1 is None or c2 is None:
            bad = text1 if c1 is None else text2
            return self._parse_error(bad, "Use: mix #ff0000 + #0000ff")
        r1, g1, b1, _ = c1
        r2, g2, b2, _ = c2
        steps = int(steps_str) if steps_str else 7
        steps = max(3, min(steps, 20))
        mixed = _mix_colors(r1, g1, b1, r2, g2, b2, steps)
        results: list[ProviderResult] = []
        for mr, mg, mb, m_hex, pct in mixed:
            swatch = _color_swatch_svg(m_hex)
            results.append(
                ProviderResult(
                    title=m_hex,
                    description=f"rgb({mr}, {mg}, {mb}) - {pct}% blend - press Enter to view conversions",
                    icon_char=swatch,
                    provider=self.name,
                    action_data={"_replace_input": m_hex},
                )
            )
        return results

    def _adjust_results(self, color_text: str, amount: int, lighten: bool) -> list[ProviderResult]:
        """Lighten or darken a color by a given percentage."""
        parsed = _parse_color(color_text)
        if parsed is None:
            return self._parse_error(color_text, "Use: lighten #ff6347 20 or darken red 30")
        r, g, b, _ = parsed
        amount = max(0, min(100, amount))
        orig_hex = _rgb_to_hex(r, g, b)
        results: list[ProviderResult] = [
            ProviderResult(
                title=f"Original: {orig_hex}",
                description=f"rgb({r}, {g}, {b})",
                icon_char=_color_swatch_svg(orig_hex),
                provider=self.name,
                action_data={"_replace_input": orig_hex},
            ),
        ]
        action = "Lighten" if lighten else "Darken"
        steps = list(range(10, amount + 1, 10))
        if amount % 10 != 0:
            steps.append(amount)
        for step in steps:
            nr, ng, nb, n_hex = _adjust_lightness(r, g, b, step, lighten)
            results.append(
                ProviderResult(
                    title=n_hex,
                    description=f"rgb({nr}, {ng}, {nb}) - {action} {step}%",
                    icon_char=_color_swatch_svg(n_hex),
                    provider=self.name,
                    action_data={"_replace_input": n_hex},
                )
            )
        return results

    def _harmony_results(self, color_text: str) -> list[ProviderResult]:
        """Show color harmonies for a given color."""
        parsed = _parse_color(color_text)
        if parsed is None:
            return self._parse_error(color_text, "Use: harmony #ff6347")
        r, g, b, _ = parsed
        orig_hex = _rgb_to_hex(r, g, b)
        results: list[ProviderResult] = [
            ProviderResult(
                title=f"Base: {orig_hex}",
                description=f"rgb({r}, {g}, {b})",
                icon_char=_color_swatch_svg(orig_hex),
                provider=self.name,
                action_data={"_replace_input": orig_hex},
            ),
        ]
        for harmony_name, colors in _harmonies(r, g, b).items():
            for cr, cg, cb, c_hex in colors:
                results.append(
                    ProviderResult(
                        title=c_hex,
                        description=f"{harmony_name} - rgb({cr}, {cg}, {cb})",
                        icon_char=_color_swatch_svg(c_hex),
                        provider=self.name,
                        action_data={"_replace_input": c_hex},
                    )
                )
        return results

    def _blindness_results(self, color_text: str) -> list[ProviderResult]:
        """Show how a color appears under different color vision deficiencies."""
        parsed = _parse_color(color_text)
        if parsed is None:
            return self._parse_error(color_text, "Use: blind #ff6347")
        r, g, b, _ = parsed
        orig_hex = _rgb_to_hex(r, g, b)
        orig_lab = _rgb_to_lab(r, g, b)
        results: list[ProviderResult] = [
            ProviderResult(
                title=f"Original: {orig_hex}",
                description=f"rgb({r}, {g}, {b}) - Normal vision",
                icon_char=_color_swatch_svg(orig_hex),
                provider=self.name,
                action_data={"_replace_input": orig_hex},
            ),
        ]
        descriptions = {
            "Protanopia": "No red cones",
            "Deuteranopia": "No green cones",
            "Tritanopia": "No blue cones",
            "Achromatopsia": "Total color blindness",
        }
        for name, (sr, sg, sb, s_hex) in _simulate_cvd(r, g, b).items():
            sim_lab = _rgb_to_lab(sr, sg, sb)
            delta_e = math.sqrt(sum((a - b) ** 2 for a, b in zip(orig_lab, sim_lab)))
            if delta_e < 1:
                shift = "No change"
            elif delta_e < 5:
                shift = "Slight shift"
            elif delta_e < 15:
                shift = "Moderate shift"
            elif delta_e < 30:
                shift = "Strong shift"
            else:
                shift = "Very different"
            split_swatch = _split_swatch_svg(orig_hex, s_hex)
            results.append(
                ProviderResult(
                    title=f"{name}: {s_hex}",
                    description=f"{descriptions.get(name, '')} \u00b7 {shift} \u00b7 rgb({sr}, {sg}, {sb})",
                    icon_char=split_swatch,
                    provider=self.name,
                    action_data={"_replace_input": s_hex},
                )
            )
        return results

    def _launch_color_picker(self) -> bool:
        """Open the floating color picker loupe."""
        overlay = _ColorPickerOverlay()
        ColorProvider._picker_overlay = overlay
        overlay.color_picked.connect(lambda hex_val: self._on_color_picked(hex_val))
        overlay.destroyed.connect(lambda: setattr(ColorProvider, "_picker_overlay", None))
        QTimer.singleShot(100, overlay.start)
        return True

    def _on_color_picked(self, hex_color: str):
        """Handle the picked color by reopening quick launch with the color filled in."""
        from core.widgets.yasb.quick_launch import QuickLaunchWidget

        ColorProvider._picker_overlay = None

        def _reopen():
            widget = QuickLaunchWidget._active_instance
            if widget is None:
                for w in QApplication.topLevelWidgets():
                    ql = w.findChild(QuickLaunchWidget)
                    if ql:
                        widget = ql
                        break
            if widget is None:
                for w in QApplication.allWidgets():
                    if isinstance(w, QuickLaunchWidget):
                        widget = w
                        break
            if widget:
                widget._show_popup()
                if self.prefix:
                    widget._set_prefix_chip(self.prefix, hex_color)

        QTimer.singleShot(100, _reopen)
