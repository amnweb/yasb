from __future__ import annotations

import atexit
import logging
import threading
import time
from collections.abc import Callable
from ctypes import POINTER, c_ubyte, cast
from ctypes.wintypes import HANDLE

from comtypes import COMError  # pyright: ignore[reportMissingTypeStubs]
from pycaw.pycaw import AudioUtilities, EDataFlow, ERole

from core.utils.win32.bindings.kernel32 import (
    CreateEvent,
    ResetEvent,
    SetEvent,
    WaitForMultipleObjects,
    WaitForSingleObject,
)
from core.utils.win32.bindings.ole32 import ole32
from core.utils.win32.constants import (
    AUDCLNT_BUFFERFLAGS_SILENT,
    COINIT_MULTITHREADED,
    RPC_E_CHANGED_MODE,
    WAIT_OBJECT_0,
)
from core.widgets.services.audio_visualizer.loopback import (
    UnsupportedFormatError,
    _decode_stereo,  # pyright: ignore[reportPrivateUsage]
    _is_silent,  # pyright: ignore[reportPrivateUsage]
    _WasapiLoopbackClient,  # pyright: ignore[reportPrivateUsage]
)
from core.widgets.services.lyrics.audio_dsp import BandGroup, MultirateBands, SpectrumSmoother

logger = logging.getLogger("core.widgets.services.lyrics.wasapi_audio")

_STOP = 0
_AUDIO = 1
_REOPEN_BACKOFF_MIN_MS = 500
_REOPEN_BACKOFF_MAX_MS = 8000
_DEVICE_CHECK_EVERY_S = 1.0

# The beat effects (beat_jump, sparkles) read a small fixed set of bass bands that is analysed
# separately from the displayed bars, so no visualizer option can change how they react.
_PROBE_GROUP = BandGroup(bars=10, f_min=50.0, f_max=10000.0, count=4)
_PROBE_NOISE_REDUCTION = 0.65
_PROBE_MONSTERCAT = 1.0


class WasapiAudioStream:
    """
    Direct WASAPI loopback audio stream with pure-Python DSP.

    It owns its capture: one WASAPI loopback stream on the default output device, read on a
    dedicated thread, decoded to mono and run through audio_dsp (multirate FFT resolution,
    autosens, fall-off, integral and monstercat filters). It does not use the shared audio
    visualizer service, so it is independent of whether an audio_visualizer widget is running.

    Layouts: "linear" draws low to high (``reverse`` flips it). "mirrored" is symmetric
    about the vertical axis with the bass in the centre (``reverse`` puts it on the edges).
    Both halves come from one mono mix, which keeps CPU use at one channel.
    """

    def __init__(
        self,
        bars_number: int = 8,
        framerate: int = 60,
        noise_reduction: int = 65,
        on_frame: Callable[[list[float]], None] | None = None,
        monstercat: float = 1.0,
        sensitivity: int = 100,
        lower_cutoff_freq: int = 50,
        higher_cutoff_freq: int = 10000,
        layout: str = "linear",
        reverse: bool = False,
    ) -> None:
        self.bars_number = max(4, min(32, bars_number))
        self.framerate = max(10, min(120, framerate))
        self.noise_reduction = max(0, min(100, noise_reduction)) / 100.0
        self.monstercat = max(0.0, monstercat)
        self.sensitivity = max(10, min(200, sensitivity)) / 100.0
        self.lower_cutoff_freq = max(20, lower_cutoff_freq)
        self.higher_cutoff_freq = max(self.lower_cutoff_freq + 100, higher_cutoff_freq)
        self.layout = layout if layout in ("linear", "mirrored") else "linear"
        self.reverse = bool(reverse)
        self._on_frame = on_frame
        # Mirrored layout draws the full spectrum on each half, so only half the bars are analysed.
        self._analysed_bars = (self.bars_number + 1) // 2 if self.layout == "mirrored" else self.bars_number

        self._running = False
        self._paused = False
        self._client_open = False
        self._thread: threading.Thread | None = None
        self._stop_event = CreateEvent(None, True, False, None)  # manual-reset
        self._audio_event = CreateEvent(None, False, False, None)  # auto-reset

        self._samples: list[float] = [0.0] * self.bars_number
        self._bass_energy = 0.0
        self._rolling_bass_avg = 0.20
        self._rolling_transient_peak = 0.25

        atexit.register(self.stop)

    # Status
    @property
    def is_available(self) -> bool:
        return True

    @property
    def is_running(self) -> bool:
        return self._running and self._client_open and self._thread is not None and self._thread.is_alive()

    def restart(self) -> None:
        self.stop()
        self.start()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._paused = False
        ResetEvent(self._stop_event)
        self._thread = threading.Thread(target=self._capture_thread, name="yasb-lyrics-audio", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._running and self._thread is None:
            return
        self._running = False
        SetEvent(self._stop_event)
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=1.5)
        self._client_open = False
        self._samples = [0.0] * self.bars_number
        self._bass_energy = 0.0

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def get_spectrum(self) -> list[float]:
        return list(self._samples)

    def get_bass_energy(self) -> float:
        return self._bass_energy

    # Capture thread

    def _capture_thread(self) -> None:
        hr = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        if hr < 0 and hr != RPC_E_CHANGED_MODE:
            logger.error("CoInitializeEx failed (0x%08X)", hr & 0xFFFFFFFF)
            return
        try:
            self._capture_loop()
        except Exception:
            logger.exception("Lyrics audio capture thread crashed")
        finally:
            self._client_open = False
            if hr >= 0:
                ole32.CoUninitialize()

    def _wait_stop(self, timeout_ms: int) -> bool:
        return WaitForSingleObject(self._stop_event, timeout_ms) == WAIT_OBJECT_0

    @staticmethod
    def _default_device_id() -> str | None:
        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            return enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value).GetId()
        except Exception:
            return None

    def _open(self) -> tuple[_WasapiLoopbackClient, str | None] | None:
        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            device = enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
            device_id = device.GetId()
            client = _WasapiLoopbackClient(device, int(self._audio_event))
        except UnsupportedFormatError as exc:
            logger.error("Lyrics audio: %s", exc)
            return None
        except COMError:
            return None
        except Exception:
            logger.debug("Lyrics audio: could not open WASAPI loopback", exc_info=True)
            return None
        logger.info("Lyrics audio: loopback capture open (%s)", client.format_summary)
        return client, device_id

    def _capture_loop(self) -> None:
        handles = (HANDLE * 2)(self._stop_event, self._audio_event)
        interval = 1.0 / self.framerate
        backoff_ms = _REOPEN_BACKOFF_MIN_MS

        client: _WasapiLoopbackClient | None = None
        device_id: str | None = None
        dsp: MultirateBands | None = None
        smoother = SpectrumSmoother(
            self._analysed_bars, self.noise_reduction, self.monstercat, float(self.framerate), self.sensitivity
        )
        probe = SpectrumSmoother(4, _PROBE_NOISE_REDUCTION, _PROBE_MONSTERCAT, float(self.framerate), 1.0)
        pending: list[float] = []
        last_frame = 0.0
        last_audio = 0.0
        last_device_check = 0.0
        active = False  # real audio flowing (or still decaying)

        try:
            while self._running:
                if client is None:
                    opened = self._open()
                    if opened is None:
                        self._client_open = False
                        if self._wait_stop(backoff_ms):
                            break
                        backoff_ms = min(backoff_ms * 2, _REOPEN_BACKOFF_MAX_MS)
                        continue
                    client, device_id = opened
                    backoff_ms = _REOPEN_BACKOFF_MIN_MS
                    dsp = MultirateBands(
                        client.sample_rate,
                        [
                            BandGroup(self._analysed_bars, self.lower_cutoff_freq, self.higher_cutoff_freq),
                            _PROBE_GROUP,
                        ],
                    )
                    smoother.reset()
                    probe.reset()
                    pending.clear()
                    self._client_open = True
                    last_audio = last_device_check = time.monotonic()

                # While bars are still falling after the audio stopped, tick at the frame rate.
                timeout_ms = (
                    int(interval * 1000) if (active and pending == [] and self._decaying()) else client.stale_timeout_ms
                )
                rc = WaitForMultipleObjects(len(handles), handles, False, timeout_ms)
                if rc == WAIT_OBJECT_0 + _STOP:
                    break

                now = time.monotonic()
                try:
                    if rc == WAIT_OBJECT_0 + _AUDIO:
                        heard = self._drain(client, pending)
                        if heard:
                            last_audio = now
                            active = True
                except COMError as exc:
                    logger.debug("Lyrics audio: stream invalidated (%s), reopening", exc)
                    self._close(client)
                    client = None
                    self._reset_output()
                    active = False
                    if self._wait_stop(backoff_ms):
                        break
                    backoff_ms = min(backoff_ms * 2, _REOPEN_BACKOFF_MAX_MS)
                    continue
                except Exception:
                    logger.warning("Lyrics audio: stream failed, reopening", exc_info=True)
                    self._close(client)
                    client = None
                    self._reset_output()
                    active = False
                    if self._wait_stop(backoff_ms):
                        break
                    backoff_ms = min(backoff_ms * 2, _REOPEN_BACKOFF_MAX_MS)
                    continue

                # Default output device switched? The old stream usually just goes quiet.
                if now - last_device_check >= _DEVICE_CHECK_EVERY_S and (rc != WAIT_OBJECT_0 + _AUDIO):
                    last_device_check = now
                    current = self._default_device_id()
                    if current is not None and device_id is not None and current != device_id:
                        logger.debug("Lyrics audio: default device changed, reopening")
                        self._close(client)
                        client = None
                        self._reset_output()
                        active = False
                        continue

                if not active or dsp is None:
                    continue

                silent = now - last_audio >= client.stale_timeout_ms / 1000.0
                if now - last_frame < interval:
                    continue
                dt = now - last_frame if last_frame else interval
                last_frame = now

                if self._paused:
                    pending.clear()
                    self._samples = [s * 0.85 for s in self._samples]
                    self._bass_energy *= 0.85
                    continue

                smoother.update_framerate(dt)
                probe.update_framerate(dt)
                if silent:
                    # Nothing audible any more: let the bars fall off on zero input.
                    dsp.reset()
                    pending.clear()
                    half = smoother.process([0.0] * self._analysed_bars, True)
                    bass = probe.process([0.0] * 4, True)
                    if max(half) < 0.002:
                        active = False
                        smoother.reset()
                        probe.reset()
                        self._reset_output()
                        continue
                else:
                    dsp.push(pending)
                    pending.clear()
                    display_raw, probe_raw = dsp.bands()
                    half = smoother.process(display_raw, False)
                    bass = probe.process(probe_raw, False)

                bars = self._arrange(half)
                self._update_bass(bass)
                self._samples = bars
                if self._on_frame:
                    try:
                        self._on_frame(bars)
                    except Exception:
                        pass
        finally:
            self._close(client)
            self._client_open = False

    def _arrange(self, half: list[float]) -> list[float]:
        """Turn the analysed bars (low to high) into the displayed order for the chosen layout."""
        n = self.bars_number
        if self.layout == "mirrored":
            if self.reverse:  # bass on the outside, treble in the middle
                out = half + (half[::-1] if n % 2 == 0 else half[-2::-1])
            else:  # bass in the middle
                out = half[::-1] + (half if n % 2 == 0 else half[1:])
            return out[:n]
        return half[::-1] if self.reverse else list(half)

    def _decaying(self) -> bool:
        return any(s > 0.002 for s in self._samples)

    def _reset_output(self) -> None:
        self._samples = [0.0] * self.bars_number
        self._bass_energy = 0.0

    @staticmethod
    def _close(client: _WasapiLoopbackClient | None) -> None:
        if client is not None:
            client.close()

    def _drain(self, client: _WasapiLoopbackClient, pending: list[float]) -> bool:
        """Consume every ready packet into ``pending`` as mono. True if audible audio arrived."""
        capture = client.capture
        if capture is None:
            return False
        frame_bytes = client.frame_bytes
        heard = False

        while self._running:
            if not capture.GetNextPacketSize():
                break
            data_ptr, nframes, flags, *_ = capture.GetBuffer()
            nframes = int(nframes)
            try:
                if nframes and not (flags & AUDCLNT_BUFFERFLAGS_SILENT):
                    nbytes = nframes * frame_bytes
                    buf = bytes(cast(data_ptr, POINTER(c_ubyte * nbytes)).contents)
                else:
                    buf = b""
            finally:
                # Always release, or the capture buffer stays locked and the stream stalls.
                capture.ReleaseBuffer(nframes)

            if self._paused:
                continue
            if not buf or buf.count(0) == len(buf):
                continue
            left, right = _decode_stereo(buf, client.channels, client.sample_code, client.sample_scale)
            if _is_silent(left) and _is_silent(right):
                continue

            pending.extend([(a + b) * 0.5 for a, b in zip(left, right)])
            heard = True

        # Never let a stalled consumer grow memory: keep only the newest ~0.5 s.
        limit = client.sample_rate // 2
        if len(pending) > limit:
            del pending[:-limit]
        return heard

    def _update_bass(self, raw: list[float]) -> None:
        """Kick/beat detection based on low-frequency band energy."""
        if len(raw) >= 4:
            raw_bass = max(
                raw[0] * 0.90 + raw[1] * 0.35,
                raw[1] * 0.85 + raw[2] * 0.30,
                raw[2] * 0.70 + raw[3] * 0.25,
                raw[0],
                raw[1] * 0.85,
            )
        elif len(raw) >= 2:
            raw_bass = max(raw[0], raw[1] * 0.80)
        else:
            raw_bass = raw[0]

        self._rolling_bass_avg += (raw_bass - self._rolling_bass_avg) * 0.08
        diff = raw_bass - self._rolling_bass_avg
        transient = max(0.0, diff) if diff > 0.03 else 0.0

        self._rolling_transient_peak = max(0.08, max(self._rolling_transient_peak * 0.990, transient))
        norm_transient = min(1.0, transient / self._rolling_transient_peak)

        kick = min(1.0, ((norm_transient - 0.10) / 0.90) ** 1.35) if norm_transient > 0.10 else 0.0
        beat_pulse = min(1.0, (diff - 0.018) * 3.5) if diff > 0.018 else 0.0
        target_energy = max(kick, beat_pulse)

        if target_energy > self._bass_energy:
            self._bass_energy += (target_energy - self._bass_energy) * 0.85
        else:
            self._bass_energy *= 0.86
            if self._bass_energy < 0.02:
                self._bass_energy = 0.0
