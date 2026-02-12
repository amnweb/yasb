import math
import re

from PyQt6.QtWidgets import QApplication

from core.utils.widgets.quick_launch.base_provider import BaseProvider, ProviderResult

_ICON = "\ue790"


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


_D65_X, _D65_Y, _D65_Z = 0.95047, 1.0, 1.08883


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


def _rgb_to_lch(r: int, g: int, b: int) -> tuple[float, float, float]:
    L, a, b_val = _rgb_to_lab(r, g, b)
    C = math.sqrt(a * a + b_val * b_val)
    H = math.degrees(math.atan2(b_val, a)) % 360
    return round(L, 2), round(C, 2), round(H, 2)


def _lch_to_rgb(L: float, C: float, H: float) -> tuple[int, int, int]:
    a = C * math.cos(math.radians(H))
    b_val = C * math.sin(math.radians(H))
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
    C = math.sqrt(a * a + b_val * b_val)
    H = math.degrees(math.atan2(b_val, a)) % 360
    return round(L, 4), round(C, 4), round(H, 2)


def _oklch_to_rgb(L: float, C: float, H: float) -> tuple[int, int, int]:
    a = C * math.cos(math.radians(H))
    b_val = C * math.sin(math.radians(H))
    return _oklab_to_rgb(L, a, b_val)


# Patterns for parsing color inputs
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


def _parse_color(text: str) -> tuple[int, int, int, int] | None:
    """Try to parse a color string into (R, G, B, A). Returns None on failure."""
    text = text.strip()

    # Named color
    if text.lower() in _NAMED_COLORS:
        return _hex_to_rgb(_NAMED_COLORS[text.lower()])

    # HEX (3, 4, 6, or 8 digits)
    m = _HEX_RE.match(text)
    if m:
        return _hex_to_rgb(m.group(1))

    # rgba(r, g, b, a)
    m = _RGBA_RE.match(text)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a_raw = float(m.group(4))
        # Treat values > 1 as 0-255, values <= 1 as fraction
        a = round(a_raw) if a_raw > 1 else round(a_raw * 255)
        if all(0 <= v <= 255 for v in (r, g, b, a)):
            return r, g, b, a
        return None

    # rgb(r, g, b)
    m = _RGB_RE.match(text)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if all(0 <= v <= 255 for v in (r, g, b)):
            return r, g, b, 255
        return None

    # Plain "r, g, b" or "r g b"
    m = _RGB_PLAIN_RE.match(text)
    if m:
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if all(0 <= v <= 255 for v in (r, g, b)):
            return r, g, b, 255
        return None

    # hsl(h, s%, l%)
    m = _HSL_RE.match(text)
    if m:
        h, s, l = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 0 <= h <= 360 and 0 <= s <= 100 and 0 <= l <= 100:
            r, g, b = _hsl_to_rgb(h, s, l)
            return r, g, b, 255
        return None

    # hwb(h, w%, b%)
    m = _HWB_RE.match(text)
    if m:
        h, w, bk = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 0 <= h <= 360 and 0 <= w <= 100 and 0 <= bk <= 100:
            r, g, b = _hwb_to_rgb(h, w, bk)
            return r, g, b, 255
        return None

    # lab(L, a, b)
    m = _LAB_RE.match(text)
    if m:
        L, a, b = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if 0 <= L <= 100:
            r, g, b = _lab_to_rgb(L, a, b)
            return r, g, b, 255
        return None

    # lch(L, C, H)
    m = _LCH_RE.match(text)
    if m:
        L, C, H = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if 0 <= L <= 100 and 0 <= H <= 360:
            r, g, b = _lch_to_rgb(L, C, H)
            return r, g, b, 255
        return None

    # oklab(L, a, b)
    m = _OKLAB_RE.match(text)
    if m:
        L, a, b = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if 0 <= L <= 1:
            r, g, b = _oklab_to_rgb(L, a, b)
            return r, g, b, 255
        return None

    # oklch(L, C, H)
    m = _OKLCH_RE.match(text)
    if m:
        L, C, H = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if 0 <= L <= 1 and 0 <= H <= 360:
            r, g, b = _oklch_to_rgb(L, C, H)
            return r, g, b, 255
        return None

    return None


class ColorConverterProvider(BaseProvider):
    """Convert colors between HEX, RGB, HSL, HSV, HWB, LAB, LCH, OKLAB, and OKLCH."""

    name = "color_converter"

    def match(self, text: str) -> bool:
        text = text.strip()
        if self.prefix and text.startswith(self.prefix):
            return True
        return False

    def get_results(self, text: str) -> list[ProviderResult]:
        query = self.get_query_text(text).strip()
        if not query:
            return [
                ProviderResult(
                    title="Color Converter",
                    description="Enter a color: #hex, #hexAlpha, rgba(), hsl(), hwb(), lab(), lch(), oklab(), oklch(), or a name",
                    icon_char=_ICON,
                    provider=self.name,
                )
            ]

        parsed = _parse_color(query)
        if parsed is None:
            return [
                ProviderResult(
                    title="Invalid color",
                    description="Try: #FF550090, rgba(255,85,0,0.5), hsl(20,100,50), lab(50,0,0), oklab(0.5,0,0)",
                    icon_char=_ICON,
                    provider=self.name,
                )
            ]

        r, g, b, a = parsed
        has_alpha = a < 255
        a_frac = round(a / 255, 2)

        hex_val = _rgb_to_hex(r, g, b, a)
        rgb_val = f"rgba({r}, {g}, {b}, {a_frac})" if has_alpha else f"rgb({r}, {g}, {b})"
        h, s, l = _rgb_to_hsl(r, g, b)
        hsl_val = f"hsla({h}, {s}%, {l}%, {a_frac})" if has_alpha else f"hsl({h}, {s}%, {l}%)"
        hv, sv, vv = _rgb_to_hsv(r, g, b)
        hsv_val = f"hsva({hv}, {sv}%, {vv}%, {a_frac})" if has_alpha else f"hsv({hv}, {sv}%, {vv}%)"
        hw, ww, bw = _rgb_to_hwb(r, g, b)
        hwb_val = f"hwb({hw} {ww}% {bw}% / {a_frac})" if has_alpha else f"hwb({hw}, {ww}%, {bw}%)"
        lL, la, lb = _rgb_to_lab(r, g, b)
        lab_val = f"lab({lL} {la} {lb} / {a_frac})" if has_alpha else f"lab({lL}, {la}, {lb})"
        cL, cC, cH = _rgb_to_lch(r, g, b)
        lch_val = f"lch({cL} {cC} {cH} / {a_frac})" if has_alpha else f"lch({cL}, {cC}, {cH})"
        oL, oa, ob = _rgb_to_oklab(r, g, b)
        oklab_val = f"oklab({oL} {oa} {ob} / {a_frac})" if has_alpha else f"oklab({oL}, {oa}, {ob})"
        olL, olC, olH = _rgb_to_oklch(r, g, b)
        oklch_val = f"oklch({olL} {olC} {olH} / {a_frac})" if has_alpha else f"oklch({olL}, {olC}, {olH})"

        return [
            ProviderResult(
                title=f"{hex_val}",
                description="HEX - press Enter to copy",
                icon_char=_ICON,
                provider=self.name,
                action_data={"value": hex_val},
            ),
            ProviderResult(
                title=f"{rgb_val}",
                description="RGBA - press Enter to copy" if has_alpha else "RGB - press Enter to copy",
                icon_char=_ICON,
                provider=self.name,
                action_data={"value": rgb_val},
            ),
            ProviderResult(
                title=f"{hsl_val}",
                description="HSLA - press Enter to copy" if has_alpha else "HSL - press Enter to copy",
                icon_char=_ICON,
                provider=self.name,
                action_data={"value": hsl_val},
            ),
            ProviderResult(
                title=f"{hsv_val}",
                description="HSVA - press Enter to copy" if has_alpha else "HSV - press Enter to copy",
                icon_char=_ICON,
                provider=self.name,
                action_data={"value": hsv_val},
            ),
            ProviderResult(
                title=f"{hwb_val}",
                description="HWB - press Enter to copy",
                icon_char=_ICON,
                provider=self.name,
                action_data={"value": hwb_val},
            ),
            ProviderResult(
                title=f"{lab_val}",
                description="CIE LAB - press Enter to copy",
                icon_char=_ICON,
                provider=self.name,
                action_data={"value": lab_val},
            ),
            ProviderResult(
                title=f"{lch_val}",
                description="CIE LCH - press Enter to copy",
                icon_char=_ICON,
                provider=self.name,
                action_data={"value": lch_val},
            ),
            ProviderResult(
                title=f"{oklab_val}",
                description="OKLAB - press Enter to copy",
                icon_char=_ICON,
                provider=self.name,
                action_data={"value": oklab_val},
            ),
            ProviderResult(
                title=f"{oklch_val}",
                description="OKLCH - press Enter to copy",
                icon_char=_ICON,
                provider=self.name,
                action_data={"value": oklch_val},
            ),
        ]

    def execute(self, result: ProviderResult) -> bool:
        value = result.action_data.get("value", "")
        if value:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(value)
        return True
