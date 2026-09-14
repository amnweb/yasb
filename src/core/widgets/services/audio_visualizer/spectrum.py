"""Spectrum analysis and band layout for the audio visualizer.

SpectrumSource turns a PCM window into a magnitude spectrum and is shared by
every widget on the same channel. SpectrumAnalyzer maps that spectrum onto
log-spaced bands and smooths them, one instance per widget since band count,
frequency range and smoothing are all configurable.
"""

import cmath
import math

FFT_SIZE = 512

# Below this a band is treated as fully silent and snapped to zero, so a
# fade-out terminates in finite time instead of approaching zero forever.
_SILENCE_EPSILON = 1e-3

# Smoothing is defined as a per-frame rate at this reference framerate and then
# converted to a time constant, so the motion looks the same at any framerate
# while still matching the rates the visualizer was originally tuned around.
_REFERENCE_FPS = 60.0

# Guard rails for the frame delta, so a long pause cannot produce a wild jump.
_MIN_DT = 1.0 / 240.0
_MAX_DT = 0.25

# Per-band equalizer shape: a cutoff^0.85 tilt that lifts the highs, divided
# by the band's bin count to average it.
#
# _EQ_SCALE sets the starting overall level. With auto_gain off it's the only
# level control, chosen so sensitivity 50 gives a usable level at the default
# band count. With auto_gain on, autosens only trims gain down on clipping and
# creeps it up slowly otherwise, so it can absorb a moderate mismatch but not
# an arbitrary one: too large a value still pins bands at the ceiling instead
# of releveling.
_EQ_SCALE = 0.18

# Autosens per-second rates, scaled from a 66fps reference so they behave the
# same at any real framerate. Drop fast when a band clips, creep up otherwise,
# ramp hard until the first clip.
_SENS_FALL = 0.02 * 66.0
_SENS_RISE = 0.001 * 66.0
_SENS_RISE_INIT = 0.1 * 66.0
# Not clamped in normal use; this only guards a runaway on a pathologically
# quiet feed.
_SENS_MIN = 1e-4
_SENS_MAX = 1e7

_HALF_NEG_J = complex(0.0, -0.5)


def layout_mono(samples: list[float], reverse: bool = False) -> list[float]:
    """Mono display order.

    reverse=False: left → right, low → high
    reverse=True:  left → right, high → low
    """
    return list(reversed(samples)) if reverse else samples


def layout_stereo(left: list[float], right: list[float], reverse: bool = False) -> list[float]:
    """Join left and right bands into one row.

    Left half = left channel, right half = right channel.
    reverse=False: bass in the center  (highs…bass | bass…highs)
    reverse=True:  bass on the edges   (bass…highs | highs…bass)
    """
    if reverse:
        return left + list(reversed(right))
    return list(reversed(left)) + right


def _rate_to_tau(rate_per_frame: float) -> float:
    """Convert a per-frame smoothing rate at the reference framerate to seconds."""
    rate = max(1e-4, min(0.999, rate_per_frame))
    return -(1.0 / _REFERENCE_FPS) / math.log(1.0 - rate)


def _hann_window(n: int) -> list[float]:
    if n <= 1:
        return [1.0] * n
    return [0.5 - 0.5 * math.cos(2.0 * math.pi * i / (n - 1)) for i in range(n)]


def _bit_reversal(m: int) -> list[int]:
    bits = m.bit_length() - 1
    rev = [0] * m
    for i in range(m):
        r = 0
        v = i
        for _ in range(bits):
            r = (r << 1) | (v & 1)
            v >>= 1
        rev[i] = r
    return rev


def _twiddle_stages(m: int) -> list[list[complex]]:
    stages: list[list[complex]] = []
    length = 2
    while length <= m:
        half = length >> 1
        stages.append([cmath.exp(complex(0.0, -2.0 * math.pi * j / length)) for j in range(half)])
        length <<= 1
    return stages


class SpectrumSource:
    """Windowed magnitude spectrum of a real signal.

    A real N-point transform is computed as a complex N/2-point transform plus
    an untangling pass, with every twiddle factor precomputed. That is about
    2.2x faster than transforming the real signal as if it were complex, and it
    avoids the numerical drift of accumulating twiddles by repeated multiply.
    """

    def __init__(self, fft_size: int = FFT_SIZE) -> None:
        if fft_size < 4 or fft_size & (fft_size - 1):
            raise ValueError("FFT size must be a power of two >= 4")
        self.fft_size = fft_size
        self.bins = fft_size // 2
        self._window = _hann_window(fft_size)
        self._reversal = _bit_reversal(self.bins)
        self._stages = _twiddle_stages(self.bins)
        self._untangle = [cmath.exp(complex(0.0, -2.0 * math.pi * k / fft_size)) for k in range(self.bins)]
        self._inv_size = 1.0 / fft_size

    def magnitudes(self, samples: list[float]) -> list[float]:
        """One-sided magnitude spectrum of the newest ``fft_size`` samples."""
        n = self.fft_size
        # Always analyse the newest window; a longer input must be trimmed from
        # the front, never truncated to its oldest n samples.
        if len(samples) > n:
            samples = samples[-n:]
        elif len(samples) < n:
            samples = [0.0] * (n - len(samples)) + samples

        window = self._window
        m = self.bins
        # Window and pack pairs of real samples into one complex sequence in a
        # single pass.
        packed = [complex(samples[2 * i] * window[2 * i], samples[2 * i + 1] * window[2 * i + 1]) for i in range(m)]
        spectrum = self._transform(packed)

        untangle = self._untangle
        inv = self._inv_size
        mags = [0.0] * m
        for k in range(m):
            head = spectrum[k]
            tail = spectrum[m - k if k else 0].conjugate()
            even = (head + tail) * 0.5
            odd = (head - tail) * _HALF_NEG_J
            mags[k] = abs(even + untangle[k] * odd) * inv
        return mags

    def _transform(self, values: list[complex]) -> list[complex]:
        """Iterative radix-2 FFT over a precomputed twiddle table."""
        m = self.bins
        reversal = self._reversal
        out = [values[reversal[i]] for i in range(m)]
        length = 2
        stage = 0
        while length <= m:
            table = self._stages[stage]
            half = length >> 1
            for start in range(0, m, length):
                for k in range(half):
                    i = start + k
                    j = i + half
                    u = out[i]
                    v = out[j] * table[k]
                    out[i] = u + v
                    out[j] = u - v
            length <<= 1
            stage += 1
        return out


class SpectrumAnalyzer:
    """Log-spaced bands with attack/decay smoothing, from a magnitude spectrum."""

    def __init__(
        self,
        bands: int = 24,
        fft_size: int = FFT_SIZE,
        sample_rate: int = 48000,
        f_min: float = 50.0,
        f_max: float = 12000.0,
        sensitivity: float = 1.0,
        smoothness: float = 0.55,
        auto_gain: bool = False,
    ) -> None:
        self.fft_size = fft_size
        self.sample_rate = sample_rate
        self.f_min = f_min
        self.f_max = f_max
        self.auto_gain = auto_gain
        self.attack_tau = _rate_to_tau(0.45)
        self.decay_tau = _rate_to_tau(0.18)
        self.bands = 0
        self._smooth: list[float] = []
        self._band_bins: list[tuple[int, int]] = []
        self._band_eq: list[float] = []
        # Autosens state: a global gain the loop tunes so the loudest band
        # sits near the top. _sens_init drives the fast startup ramp until the
        # first clip, then stays off.
        self._sens = 1.0
        self._sens_init = True
        self._alpha_key = -1
        self._attack_alpha = 0.5
        self._decay_alpha = 0.2
        self.set_bands(bands)
        self.set_sensitivity(sensitivity)
        self.set_smoothness(smoothness)

    def set_sample_rate(self, sample_rate: int) -> None:
        if sample_rate <= 0 or sample_rate == self.sample_rate:
            return
        self.sample_rate = sample_rate
        self._rebuild_bands()

    def set_bands(self, bands: int) -> None:
        bands = max(2, min(128, bands))
        if bands == self.bands:
            return
        self.bands = bands
        self._smooth = [0.0] * bands
        self._rebuild_bands()

    def set_sensitivity(self, value: float) -> None:
        self.sensitivity = max(0.1, min(2.0, value))

    def set_smoothness(self, value: float) -> None:
        """0 = snappy, 1 = very smooth."""
        t = max(0.0, min(1.0, value))
        self.attack_tau = _rate_to_tau(0.70 - t * 0.45)
        self.decay_tau = _rate_to_tau(0.32 - t * 0.26)
        self._alpha_key = -1

    def reset(self) -> None:
        """Snap every band to silence."""
        self._smooth = [0.0] * self.bands

    def _resolve_alphas(self, dt: float) -> tuple[float, float]:
        """Per-frame smoothing factors for a real elapsed time.

        Deriving these from ``dt`` rather than assuming a fixed frame rate is
        what makes ``smoothness`` mean the same thing at any framerate.
        """
        dt = min(_MAX_DT, max(_MIN_DT, dt))
        key = int(dt * 1000.0)
        if key != self._alpha_key:
            self._alpha_key = key
            self._attack_alpha = 1.0 - math.exp(-dt / self.attack_tau)
            self._decay_alpha = 1.0 - math.exp(-dt / self.decay_tau)
        return self._attack_alpha, self._decay_alpha

    def decay(self, dt: float) -> tuple[list[float], bool]:
        """Advance the envelope one frame toward silence, without a transform.

        Equivalent to feeding a frame of zeros through :meth:`map_bands` but far
        cheaper, which matters because this drives the whole fade-out after the
        stream ends. Returns the bands and whether any is still moving.
        """
        keep = 1.0 - self._resolve_alphas(dt)[1]
        smooth = self._smooth
        moving = False
        for i, previous in enumerate(smooth):
            value = previous * keep
            if value <= _SILENCE_EPSILON:
                smooth[i] = 0.0
            else:
                smooth[i] = value
                moving = True
        return [v if v < 1.0 else 1.0 for v in smooth], moving

    def map_bands(self, magnitudes: list[float], dt: float) -> list[float]:
        """Fold a magnitude spectrum into smoothed bands."""
        attack, decay = self._resolve_alphas(dt)
        gain = self.sensitivity * self._sens
        smooth = self._smooth
        peak = 0.0
        for band, (start, end) in enumerate(self._band_bins):
            # Empty bands are stored as (0, 0): the slice is [] and eq is 0, so
            # value is 0 and the band simply decays to rest.
            value = sum(magnitudes[start:end]) * self._band_eq[band] * gain
            previous = smooth[band]
            alpha = attack if value > previous else decay
            # Keep the envelope unclamped so the autosens loop reacts to a
            # sustained overshoot, not a one-frame transient. A generous
            # ceiling still bounds a runaway.
            s = previous + (value - previous) * alpha
            smooth[band] = s if s < 4.0 else 4.0
            if smooth[band] > peak:
                peak = smooth[band]

        if self.auto_gain:
            # Feed autosens the envelope with `sensitivity` divided back out, so
            # the loop always levels to the same target and `sensitivity` stays a
            # real trim on top: > 1 rides the bars into the ceiling, < 1 leaves
            # headroom. Otherwise autosens just cancels every sensitivity change.
            self._adapt_sens(peak / self.sensitivity, dt)
        return [v if v < 1.0 else 1.0 for v in smooth]

    def _adapt_sens(self, peak: float, dt: float) -> None:
        """Auto-sensitivity loop.

        ``peak`` is the loudest band before the 0..1 clamp. A value over 1
        means some band clipped, so drop the global gain quickly; otherwise
        creep it up, with a hard ramp until the first clip so the level finds
        itself in a fraction of a second.
        """
        dt = min(_MAX_DT, max(_MIN_DT, dt))
        if peak > 1.0:
            self._sens *= math.exp(-_SENS_FALL * dt)
            self._sens_init = False
        else:
            self._sens *= math.exp(_SENS_RISE * dt)
            if self._sens_init:
                self._sens *= math.exp(_SENS_RISE_INIT * dt)
        self._sens = min(_SENS_MAX, max(_SENS_MIN, self._sens))

    def _rebuild_bands(self) -> None:
        """Log-spaced band cutoffs, pushed apart when bins clump; extras stay empty."""
        half = self.fft_size // 2
        rate = float(self.sample_rate)
        nyquist = rate / 2.0
        lower = max(1.0, self.f_min)
        # Clamp so upper stays above lower even at a nonsensical sample rate;
        # otherwise the log10(lower / upper) below can hit a math domain error.
        upper = max(lower + 1.0, min(nyquist - 1.0, self.f_max))
        n_bars = self.bands

        # Logarithmic cutoff frequencies, low to high.
        freq_const = math.log10(lower / upper) / (1.0 / (n_bars + 1) - 1.0)
        cutoffs = [0.0] * (n_bars + 1)
        for n in range(n_bars + 1):
            coeff = freq_const * (-1.0) + (n + 1) / (n_bars + 1) * freq_const
            cutoffs[n] = upper * (10.0**coeff)
            if n > 0 and cutoffs[n - 1] >= cutoffs[n]:
                cutoffs[n] = cutoffs[n - 1] + rate / self.fft_size

        lowers = [0] * (n_bars + 1)
        uppers = [0] * n_bars
        for n in range(n_bars + 1):
            bin_i = int(cutoffs[n] / nyquist * half)
            # Bin 0 is DC: including it would light the first bar from any
            # constant offset in the stream.
            lowers[n] = max(1, min(half, bin_i))

        for n in range(1, n_bars + 1):
            if lowers[n] <= lowers[n - 1] and lowers[n - 1] + 1 <= half:
                lowers[n] = lowers[n - 1] + 1
            if n > 0:
                uppers[n - 1] = max(lowers[n - 1], lowers[n] - 1)

        bins: list[tuple[int, int]] = []
        eq: list[float] = []
        for n in range(n_bars):
            start = lowers[n]
            end = uppers[n] + 1
            if end <= start or start >= half:
                bins.append((0, 0))
                eq.append(0.0)
                continue
            bins.append((start, end))
            # A cutoff^0.85 tilt, averaged over the band's bins. The overall
            # level is set by _EQ_SCALE and then tracked dynamically by
            # auto_gain / _adapt_sens.
            eq.append((cutoffs[n + 1] ** 0.85) * _EQ_SCALE / (end - start))

        self._band_bins = bins
        self._band_eq = eq
