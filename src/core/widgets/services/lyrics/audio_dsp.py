"""
Multirate spectrum processing in pure Python (no numpy, no external process).

Signal is decimated (exact integer CIC filters) into three streams, each analysed
with an FFT tailored to its frequency band:

    stream   rate    FFT    bin width   span    used for
    bass     fs/16   512    5.9 Hz      170 ms  bars under 100 Hz
    mid      fs/4    1024   11.7 Hz     85 ms   bars up to ~3 kHz
    high     fs      512    94 Hz       10 ms   wide treble bars

After the FFT, band sums, autosens, gravity fall-off, integral filter and
monstercat filter smooth and normalize the spectrum.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import accumulate
from operator import mul, sub

from core.widgets.services.audio_visualizer.spectrum import SpectrumSource

_CIC_ORDER = 3
_CIC_SCALE = 1 << 24


def optimal_fft_size(rate: int) -> int:
    """Optimal FFT buffer size for sample rate."""
    size = 512
    if 8125 < rate <= 16250:
        size *= 2
    elif 16250 < rate <= 32500:
        size *= 4
    elif 32500 < rate <= 75000:
        size *= 8
    elif 75000 < rate <= 150000:
        size *= 16
    elif 150000 < rate <= 300000:
        size *= 32
    elif rate > 300000:
        size *= 64
    return size


class _CicDecimator:
    """Order-3 CIC low-pass + decimate-by-R, in exact integer arithmetic (no float drift)."""

    def __init__(self, r: int) -> None:
        self.r = r
        self._integrators = [0] * _CIC_ORDER
        self._combs = [0] * _CIC_ORDER
        self._phase = 0
        self._norm = 1.0 / ((r**_CIC_ORDER) * _CIC_SCALE)

    def process(self, samples: list[float]) -> list[float]:
        if not samples:
            return []
        x = [int(v * _CIC_SCALE) for v in samples]
        for i in range(_CIC_ORDER):
            x = list(accumulate(x, initial=self._integrators[i]))[1:]
            self._integrators[i] = x[-1]
        start = (self.r - self._phase - 1) % self.r
        self._phase = (self._phase + len(samples)) % self.r
        y = x[start :: self.r]
        if not y:
            return []
        for i in range(_CIC_ORDER):
            prev = self._combs[i]
            self._combs[i] = y[-1]
            y = [y[0] - prev, *map(sub, y[1:], y[:-1])]
        norm = self._norm
        return [v * norm for v in y]


def _boxcar_response(f: float, fs: float, r: int) -> float:
    """Magnitude of one length-R moving average at frequency f (input rate fs)."""
    s = math.sin(math.pi * f / fs)
    if abs(s) < 1e-12:
        return 1.0
    return abs(math.sin(math.pi * f * r / fs) / (r * s))


@dataclass(frozen=True)
class BandGroup:
    """A set of log-spaced bars. ``count`` evaluates only the first N of ``bars`` (same edges)."""

    bars: int
    f_min: float = 50.0
    f_max: float = 10000.0
    count: int | None = None


class MultirateBands:
    """
    Raw (pre-autosens) spectrum band values from a mono PCM stream, for one or more band groups.

    Streams: bars under 100 Hz use bass FFT (512 points at fs/16, 170 ms span and 5.9 Hz bins);
    the other bars use mid FFT (1024 points at fs/4 for bars up to ~3 kHz, 85 ms span and
    11.7 Hz bins). Wide treble bars use a 512-point FFT at full rate, averaged over a few frames.

    All groups read the same FFTs, so adding a group (e.g. a fixed bass probe next to the
    displayed bars) costs a few multiply-adds, not another transform.

    push() feeds new samples; bands() returns one list of values per group.
    """

    # (decimation factor, FFT size, recompute every N calls to bands())
    _STREAMS = ((16, 512, 2), (4, 1024, 2), (1, 512, 1))
    # A 512-point FFT sums less noise energy than a large FFT, so noise-like treble
    # reads low; this lifts it part-way (tones in the treble read slightly high instead).
    _HIGH_GAIN = 2.0
    _HIGH_AVG_FRAMES = 4

    def __init__(self, sample_rate: int, groups: list[BandGroup]) -> None:
        self.sample_rate = sample_rate
        self._dec_mid = _CicDecimator(4)
        self._dec_bass = _CicDecimator(4)
        self._win: list[list[float]] = [[], [], []]
        self._src = {512: SpectrumSource(512), 1024: SpectrumSource(1024)}
        self._used_streams: set[int] = set()
        self._layouts = [self._build_group(g) for g in groups]
        self._values = [[0.0] * len(layout) for layout in self._layouts]
        self._high_hist: list[list[list[float]]] = [[] for _ in groups]
        self._tick = 0

    def _build_group(self, group: BandGroup) -> list[tuple[int, int, int, list[float]]]:
        fs = float(self.sample_rate)
        n_bars = group.bars
        limit = min(n_bars, group.count) if group.count else n_bars
        nyquist = fs / 2.0
        lower = max(1.0, group.f_min)
        upper = max(lower + 1.0, min(nyquist - 1.0, group.f_max))
        main_n = optimal_fft_size(self.sample_rate)

        freq_const = math.log10(lower / upper) / (1.0 / (n_bars + 1) - 1.0)
        cutoffs = [0.0] * (n_bars + 1)
        for n in range(n_bars + 1):
            coeff = -freq_const + (n + 1) / (n_bars + 1) * freq_const
            cutoffs[n] = upper * (10.0**coeff)
            if n > 0 and cutoffs[n - 1] >= cutoffs[n]:
                cutoffs[n] = cutoffs[n - 1] + fs / (main_n * 2)

        # Stream per bar: bass bars -> stream 0, then by usable ceiling of each stream.
        mid_ceiling = fs / 16.0
        bass_ceiling = fs / 64.0
        streams: list[int] = []
        for n in range(limit):
            if cutoffs[n] < 100.0 and cutoffs[n + 1] <= bass_ceiling:
                streams.append(0)
            elif cutoffs[n + 1] <= mid_ceiling:
                streams.append(1)
            else:
                streams.append(2)

        ranges: list[tuple[int, int]] = []
        for n in range(limit):
            r, size, _ = self._STREAMS[streams[n]]
            half = size // 2
            nyq_p = nyquist / r
            lo = max(1, min(half, int(cutoffs[n] / nyq_p * half)))
            hi = max(1, min(half, int(cutoffs[n + 1] / nyq_p * half)))
            ranges.append((lo, hi))
        for n in range(1, limit):  # neighbours in one stream never share or invert bins
            if streams[n] == streams[n - 1]:
                lo, hi = ranges[n]
                prev_lo, _ = ranges[n - 1]
                if lo <= prev_lo:
                    lo = prev_lo + 1
                ranges[n] = (lo, max(hi, lo + 1))
                ranges[n - 1] = (prev_lo, max(prev_lo + 1, lo))

        def droop(stream: int, f: float) -> float:
            h = 1.0
            if stream <= 1:
                h *= _boxcar_response(f, fs, 4) ** _CIC_ORDER
            if stream == 0:
                h *= _boxcar_response(f, fs / 4.0, 4) ** _CIC_ORDER
            return h

        layout: list[tuple[int, int, int, list[float]]] = []
        for n in range(limit):
            s = streams[n]
            r, size, _ = self._STREAMS[s]
            half = size // 2
            lo, hi = ranges[n]
            hi = min(hi, half)
            if hi <= lo:
                lo = min(lo, half - 1)
                hi = lo + 1
            fs_p = fs / r
            ref_n = main_n * 2 if cutoffs[n] < 100.0 else main_n
            # Normalisation factor matching 16-bit range samples through FFT.
            k = (2.0**-13) * size * r / math.log2(ref_n)
            if s == 2:
                k *= self._HIGH_GAIN
            eq = k * (cutoffs[n + 1] ** 0.85) / (hi - lo)
            weights = [eq / max(0.25, droop(s, b * fs_p / size)) for b in range(lo, hi)]
            layout.append((s, lo, hi, weights))
            self._used_streams.add(s)
        return layout

    def push(self, samples: list[float]) -> None:
        if not samples:
            return
        mid = self._dec_mid.process(samples)
        bass = self._dec_bass.process(mid)
        for idx, chunk in ((0, bass), (1, mid), (2, samples)):
            if idx not in self._used_streams:
                continue
            win = self._win[idx]
            win.extend(chunk)
            keep = self._STREAMS[idx][1]
            if len(win) > keep:
                del win[:-keep]

    def bands(self) -> list[list[float]]:
        self._tick += 1
        due = {s for s in self._used_streams if self._tick % self._STREAMS[s][2] == (s % self._STREAMS[s][2])}
        mags = {s: self._src[self._STREAMS[s][1]].magnitudes(self._win[s]) for s in due}
        for gi, layout in enumerate(self._layouts):
            values = self._values[gi]
            for n, (s, lo, hi, weights) in enumerate(layout):
                if s in due:
                    values[n] = sum(map(mul, mags[s][lo:hi], weights))
            if 2 in due and any(item[0] == 2 for item in layout):
                hist = self._high_hist[gi]
                hist.append(list(values))
                if len(hist) > self._HIGH_AVG_FRAMES:
                    del hist[0]
                for n, item in enumerate(layout):
                    if item[0] == 2:
                        values[n] = sum(h[n] for h in hist) / len(hist)
        return [list(v) for v in self._values]

    def reset(self) -> None:
        self._win = [[], [], []]
        self._values = [[0.0] * len(layout) for layout in self._layouts]
        self._high_hist = [[] for _ in self._layouts]


class SpectrumSmoother:
    """Autosens, gravity fall-off, integral filter and monstercat filter."""

    def __init__(
        self,
        bars: int,
        noise_reduction: float = 0.65,
        monstercat: float = 1.0,
        framerate: float = 60.0,
        sensitivity: float = 1.0,
    ) -> None:
        self.bars = bars
        self.noise_reduction = noise_reduction
        self.monstercat = monstercat
        self.framerate = framerate
        # A trim on top of autosens: above 1 the bars ride the ceiling, below 1 they keep headroom.
        # (Sensitivity is only the starting value once autosens is on.)
        self.sensitivity = max(0.05, sensitivity)
        self.reset()

    def reset(self) -> None:
        n = self.bars
        self._fall = [0.0] * n
        self._mem = [0.0] * n
        self._peak = [0.0] * n
        self._prev = [0.0] * n
        self._sens = 1.0
        self._sens_init = True

    def update_framerate(self, dt: float) -> None:
        if dt > 0:
            self.framerate += (max(10.0, min(240.0, 1.0 / dt)) - self.framerate) / 64.0

    def process(self, raw: list[float], silence: bool) -> list[float]:
        nr = self.noise_reduction
        trim = self.sensitivity
        out = [v * self._sens * trim for v in raw]

        framerate_mod = 66.0 / self.framerate
        gravity_mod = (framerate_mod**2.5) * 2.0 / nr if nr > 0.1 else 0.0
        integral_mod = framerate_mod**0.1

        overshoot = False
        for n in range(self.bars):
            if out[n] < self._prev[n] and nr > 0.1:
                out[n] = self._peak[n] * (1.0 - (self._fall[n] * self._fall[n] * gravity_mod))
                if out[n] < 0.0:
                    out[n] = 0.0
                self._fall[n] += 0.028
            else:
                self._peak[n] = out[n]
                self._fall[n] = 0.0
            self._prev[n] = out[n]

            out[n] = self._mem[n] * nr / integral_mod + out[n]
            self._mem[n] = out[n]
            # Autosens levels against the untrimmed value, so `sensitivity` stays a real trim.
            if out[n] / trim > 1.0:
                overshoot = True
            if out[n] > 1.0:
                out[n] = 1.0

        if overshoot:
            self._sens *= 1.0 - (0.02 * framerate_mod)
            self._sens_init = False
        elif not silence:
            self._sens *= 1.0 + (0.001 * framerate_mod)
            if self._sens_init:
                self._sens *= 1.0 + (0.1 * framerate_mod)
        self._sens = min(1e7, max(1e-4, self._sens))

        if self.monstercat > 0:
            factor = self.monstercat * 1.5
            n = self.bars
            for z in range(n):
                v = out[z]
                for m in range(z - 1, -1, -1):
                    out[m] = max(v / (factor ** (z - m)), out[m])
                for m in range(z + 1, n):
                    out[m] = max(v / (factor ** (m - z)), out[m])
        return out
