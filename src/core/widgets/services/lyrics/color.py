from __future__ import annotations

import colorsys
import io
import logging
import math
from typing import cast

logger = logging.getLogger("core.widgets.services.lyrics.color")

BINS = 24
SAMPLES = 6000
MIN_ALPHA = 128
MIN_SATURATION = 0.035
MIN_LIGHTNESS = 0.08
MAX_LIGHTNESS = 0.96
MIN_SHARE = 0.005
MIN_WEIGHT = 6.0
SECONDARY_SHARE = 0.01
SECONDARY_WEIGHT = 4.0
SECONDARY_GAP = 3
SECONDARY_HUE = 0.05
TAU = math.tau


class _Bin:
    __slots__ = ("weight", "x", "y", "saturation", "lightness")

    def __init__(self) -> None:
        self.weight = 0.0
        self.x = 0.0
        self.y = 0.0
        self.saturation = 0.0
        self.lightness = 0.0

    def add(self, h: float, s: float, l: float, weight: float) -> None:
        angle = h * TAU
        self.weight += weight
        self.x += math.cos(angle) * weight
        self.y += math.sin(angle) * weight
        self.saturation += s * weight
        self.lightness += l * weight

    def merge(self, other: _Bin) -> None:
        self.weight += other.weight
        self.x += other.x
        self.y += other.y
        self.saturation += other.saturation
        self.lightness += other.lightness

    def colour(self) -> tuple[float, float, float] | None:
        if self.weight <= 0.0:
            return None
        h = (math.atan2(self.y, self.x) % TAU) / TAU
        s = max(0.0, min(1.0, self.saturation / self.weight))
        l = max(0.0, min(1.0, self.lightness / self.weight))
        return (h, s, l)


def _score(bins: list[_Bin], idx: int) -> float:
    prev_i = (idx + BINS - 1) % BINS
    next_i = (idx + 1) % BINS
    return bins[idx].weight + (bins[prev_i].weight + bins[next_i].weight) * 0.5


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)))


def sample_palette(data: bytes | None) -> tuple[tuple[int, int, int] | None, tuple[int, int, int] | None, float]:
    """
    Samples dominant primary and secondary hues and mean lightness from raw image bytes
    using 24-bin circular HSL clustering.
    """
    if not data:
        return (None, None, 0.0)

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("RGBA")
        if img.width > 128 or img.height > 128:
            img.thumbnail((128, 128), Image.Resampling.BOX)
        pixels = cast(
            "list[tuple[int, int, int, int]]",
            img.getdata(),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        )
        n_pixels = len(pixels)
        if not n_pixels:
            return (None, None, 0.0)

        stride = max(1, n_pixels // SAMPLES)
        bins = [_Bin() for _ in range(BINS)]
        sampled = 0.0
        lightness_sum = 0.0

        for i in range(0, n_pixels, stride):
            r, g, b, a = pixels[i]
            if a < MIN_ALPHA:
                continue
            sampled += 1.0
            h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
            lightness_sum += l
            if s < MIN_SATURATION or l < MIN_LIGHTNESS or l > MAX_LIGHTNESS:
                continue
            idx = min(BINS - 1, int(h * BINS))
            # On dark covers the little light colour is the accent: weight lifts with lightness
            weight = s * (0.3 + 0.7 * l)
            bins[idx].add(h, s, l, weight)

        mean_l = lightness_sum / sampled if sampled > 0.0 else 0.0

        peak = max(range(BINS), key=lambda i: _score(bins, i))
        if _score(bins, peak) < max(sampled * MIN_SHARE, MIN_WEIGHT):
            # Purely achromatic / monochrome cover: fall back to pure white and silver
            return ((255, 255, 255), (200, 200, 200), mean_l)

        # Merge peak with its 2 adjacent neighbor bins
        cluster = _Bin()
        cluster.merge(bins[peak])
        cluster.merge(bins[(peak + BINS - 1) % BINS])
        cluster.merge(bins[(peak + 1) % BINS])
        primary_hsl = cluster.colour()
        if not primary_hsl:
            return ((255, 255, 255), (200, 200, 200), mean_l)

        # Find secondary runner-up hue that stands apart
        eligible_runners: list[int] = []
        for idx in range(BINS):
            gap = min(abs(idx - peak), BINS - abs(idx - peak))
            if gap >= SECONDARY_GAP and _score(bins, idx) >= max(sampled * SECONDARY_SHARE, SECONDARY_WEIGHT):
                eligible_runners.append(idx)

        secondary_hsl = None
        if eligible_runners:
            runner = max(eligible_runners, key=lambda i: _score(bins, i))
            runner_cluster = _Bin()
            runner_cluster.merge(bins[runner])
            runner_cluster.merge(bins[(runner + BINS - 1) % BINS])
            runner_cluster.merge(bins[(runner + 1) % BINS])
            cand = runner_cluster.colour()
            if cand:
                h_diff = abs(cand[0] - primary_hsl[0])
                h_diff = min(h_diff, 1.0 - h_diff)
                if h_diff >= SECONDARY_HUE:
                    secondary_hsl = cand

        ph, ps, pl = primary_hsl
        pl = max(0.40, min(0.85, pl))
        ps = max(0.30, min(0.90, ps))
        p_rgb = _hsl_to_rgb(ph, ps, pl)

        if secondary_hsl:
            sh, ss, sl = secondary_hsl
            sl = max(0.40, min(0.85, sl))
            ss = max(0.30, min(0.90, ss))
            s_rgb = _hsl_to_rgb(sh, ss, sl)
        else:
            s_rgb = None
        return (p_rgb, s_rgb, mean_l)
    except Exception as e:
        logger.debug("Failed to extract palette: %s", e)
        return ((255, 255, 255), (200, 200, 200), 0.0)


def extract_color_palette(data: bytes | None) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
    """
    Extracts primary and secondary accent colors from image bytes.
    """
    if not data:
        return None
    primary, secondary, _ = sample_palette(data)
    if not primary:
        primary = (255, 255, 255)
    return (primary, secondary if secondary else primary)
