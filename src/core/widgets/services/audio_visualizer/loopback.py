"""WASAPI loopback capture of the default render device."""

import logging
import threading
import time
from array import array
from ctypes import POINTER, Structure, c_ubyte, c_uint16, c_uint32, c_uint64, c_void_p, cast

import win32event
from comtypes import CLSCTX_ALL, COMMETHOD, GUID, HRESULT, COMError, IUnknown
from pycaw.callbacks import MMNotificationClient
from pycaw.constants import DEVICE_STATE
from pycaw.pycaw import AudioUtilities, EDataFlow, ERole, IAudioClient
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.utils.win32.bindings.ole32 import COINIT_MULTITHREADED, RPC_E_CHANGED_MODE, ole32
from core.widgets.services.audio_visualizer.spectrum import FFT_SIZE, SpectrumSource

# Channel selectors a widget can ask for.
_CHANNELS = ("left", "right", "average")

# Returned by magnitudes() before the first frame and while the stream is idle.
_SILENT_SPECTRUM: list[float] = [0.0] * (FFT_SIZE // 2)

IID_IAudioCaptureClient = GUID("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
KSDATAFORMAT_SUBTYPE_IEEE_FLOAT = GUID("{00000003-0000-0010-8000-00AA00389B71}")
KSDATAFORMAT_SUBTYPE_PCM = GUID("{00000001-0000-0010-8000-00AA00389B71}")

AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_BUFFERFLAGS_SILENT = 0x2
REFTIMES_PER_SEC = 10_000_000
WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_IEEE_FLOAT = 0x0003
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

# cbSize of a WAVEFORMATEXTENSIBLE payload (2 + 4 + sizeof(GUID)).
_WFX_EXTENSIBLE_CBSIZE = 22

# Newest PCM frames kept per channel. Only the newest FFT window is ever
# transformed; the rest is headroom for several packets between publishes.
_RING_SIZE = 4096

# A healthy stream signals every device period (~10 ms). Waiting several
# periods with nothing to show means the render stream went away, which is how
# "the browser was closed" is detected without polling anything.
_STALE_TIMEOUT_MIN_MS = 160
_STALE_TIMEOUT_PERIODS = 4

_REOPEN_BACKOFF_MIN_MS = 500
_REOPEN_BACKOFF_MAX_MS = 8000

# Peak amplitude at or below which a packet counts as silence. About -100 dBFS,
# far below anything that could move a bar by a whole pixel.
_SILENCE_FLOOR = 1e-5

# Indices into the WaitForMultipleObjects handle list.
_STOP = 0
_WAKE = 1
_AUDIO = 2


class _WAVEFORMATEX(Structure):
    """Windows ABI layout: 18 bytes, no trailing padding.

    ``_pack_`` matters. The default ctypes alignment pads this to 20 bytes,
    which would put every WAVEFORMATEXTENSIBLE field at the wrong offset.
    """

    _pack_ = 1
    _fields_ = [
        ("wFormatTag", c_uint16),
        ("nChannels", c_uint16),
        ("nSamplesPerSec", c_uint32),
        ("nAvgBytesPerSec", c_uint32),
        ("nBlockAlign", c_uint16),
        ("wBitsPerSample", c_uint16),
        ("cbSize", c_uint16),
    ]


class _WAVEFORMATEXTENSIBLE(Structure):
    """Windows ABI layout: 40 bytes, SubFormat at offset 24."""

    _pack_ = 1
    _fields_ = [
        ("Format", _WAVEFORMATEX),
        ("wValidBitsPerSample", c_uint16),
        ("dwChannelMask", c_uint32),
        ("SubFormat", GUID),
    ]


class IAudioCaptureClient(IUnknown):
    _iid_ = IID_IAudioCaptureClient
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "GetBuffer",
            (["out"], POINTER(POINTER(c_ubyte)), "ppData"),
            (["out"], POINTER(c_uint32), "pNumFramesToRead"),
            (["out"], POINTER(c_uint32), "pdwFlags"),
            (["out"], POINTER(c_uint64), "pu64DevicePosition"),
            (["out"], POINTER(c_uint64), "pu64QPCPosition"),
        ),
        COMMETHOD([], HRESULT, "ReleaseBuffer", (["in"], c_uint32, "NumFramesRead")),
        COMMETHOD(
            [],
            HRESULT,
            "GetNextPacketSize",
            (["out"], POINTER(c_uint32), "pNumFramesInNextPacket"),
        ),
    ]


class UnsupportedFormatError(RuntimeError):
    """The endpoint mix format cannot be decoded, and retrying will not help."""


def _is_silent(samples: list[float]) -> bool:
    """Is this channel inaudible? Cheap because max()/min() run in C."""
    return not samples or (max(samples) <= _SILENCE_FLOOR and min(samples) >= -_SILENCE_FLOOR)


def _decode_stereo(buf: bytes, channels: int, sample_code: str, scale: float) -> tuple[list[float], list[float]]:
    """Split an interleaved packet into its first two channels.

    Strided slicing over an ``array`` keeps the per-sample work in C, which is
    roughly 20x faster than walking every frame from Python. Float mix formats
    need no scaling at all, which is the overwhelmingly common case.
    """
    samples = array(sample_code)
    samples.frombytes(buf)
    if channels >= 2:
        left = samples[0::channels]
        right = samples[1::channels]
    else:
        left = right = samples
    if scale == 1.0:
        return left.tolist(), right.tolist()
    return [v * scale for v in left], [v * scale for v in right]


class _WasapiLoopbackClient:
    """A live event-driven loopback client.

    Created, used and released entirely on the capture thread. Format details
    are read from the endpoint every time a client is opened, so a device
    switch can never leave a stale frame stride behind.
    """

    def __init__(self, audio_event: int) -> None:
        self.sample_rate = 48000
        self.channels = 2
        self.frame_bytes = 8
        self.bits = 32
        self.sample_code = "f"
        self.sample_scale = 1.0
        self.stale_timeout_ms = _STALE_TIMEOUT_MIN_MS
        self.running = False
        self.capture: IAudioCaptureClient | None = None
        self._client: IAudioClient | None = None
        self._open(audio_event)

    @property
    def format_summary(self) -> str:
        kind = {"f": "float", "h": "int16", "i": "int32"}.get(self.sample_code, self.sample_code)
        return f"{self.sample_rate} Hz, {self.channels} ch, {self.bits}-bit {kind}"

    def _open(self, audio_event: int) -> None:
        enumerator = AudioUtilities.GetDeviceEnumerator()
        device = enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
        client = device.Activate(IAudioClient._iid_, CLSCTX_ALL, None).QueryInterface(IAudioClient)

        wfx = client.GetMixFormat()
        try:
            self._read_format(wfx)
            client.Initialize(
                AUDCLNT_SHAREMODE_SHARED,
                AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK,
                REFTIMES_PER_SEC // 10,
                0,  # periodicity must be 0 alongside EVENTCALLBACK
                wfx,
                None,
            )
        finally:
            # GetMixFormat hands over a CoTaskMemAlloc'd block that comtypes
            # will not release. Initialize has copied what it needs by now.
            ole32.CoTaskMemFree(cast(wfx, c_void_p))

        default_period, _minimum = client.GetDevicePeriod()
        period_ms = max(1.0, default_period / 10_000.0)
        self.stale_timeout_ms = max(_STALE_TIMEOUT_MIN_MS, int(period_ms * _STALE_TIMEOUT_PERIODS) + 1)

        client.SetEventHandle(audio_event)
        capture = client.GetService(IAudioCaptureClient._iid_).QueryInterface(IAudioCaptureClient)
        client.Start()
        self._client = client
        self.capture = capture
        self.running = True

    def pause(self) -> None:
        """Freeze the stream while every visualizer is hidden. The client stays
        initialised, so :meth:`resume` costs nothing like a fresh open would."""
        if self._client is None or not self.running:
            return
        self._client.Stop()
        self.running = False

    def resume(self) -> None:
        if self._client is None or self.running:
            return
        self._client.Start()
        self.running = True

    def _read_format(self, wfx) -> None:
        fmt = cast(wfx, POINTER(_WAVEFORMATEX)).contents
        self.sample_rate = max(1, int(fmt.nSamplesPerSec))
        self.channels = max(1, int(fmt.nChannels))
        self.bits = int(fmt.wBitsPerSample)
        # nBlockAlign is the authoritative frame stride; only fall back to a
        # computed value if the driver reports nonsense.
        self.frame_bytes = int(fmt.nBlockAlign) or self.channels * max(1, self.bits // 8)

        tag = int(fmt.wFormatTag)
        if tag == WAVE_FORMAT_EXTENSIBLE:
            if int(fmt.cbSize) < _WFX_EXTENSIBLE_CBSIZE:
                raise UnsupportedFormatError(f"WAVE_FORMAT_EXTENSIBLE with truncated cbSize {int(fmt.cbSize)}")
            subtype = cast(wfx, POINTER(_WAVEFORMATEXTENSIBLE)).contents.SubFormat
            is_float = subtype == KSDATAFORMAT_SUBTYPE_IEEE_FLOAT
            if not is_float and subtype != KSDATAFORMAT_SUBTYPE_PCM:
                raise UnsupportedFormatError(f"unsupported loopback subformat {subtype}")
        else:
            is_float = tag == WAVE_FORMAT_IEEE_FLOAT
            if not is_float and tag != WAVE_FORMAT_PCM:
                raise UnsupportedFormatError(f"unsupported loopback format tag 0x{tag:04X}")

        bytes_per_sample = self.frame_bytes // self.channels
        if is_float and bytes_per_sample == 4:
            self.sample_code, self.sample_scale = "f", 1.0
        elif not is_float and bytes_per_sample == 2:
            self.sample_code, self.sample_scale = "h", 1.0 / 32768.0
        elif not is_float and bytes_per_sample == 4:
            self.sample_code, self.sample_scale = "i", 1.0 / 2147483648.0
        else:
            raise UnsupportedFormatError(
                f"cannot decode {self.bits}-bit {'float' if is_float else 'PCM'} ({bytes_per_sample} bytes per sample)"
            )

    def close(self) -> None:
        client, self._client = self._client, None
        self.capture = None
        self.running = False
        if client is None:
            return
        try:
            client.Stop()
            client.Reset()
        except Exception:
            logging.debug("Audio visualizer: WASAPI client teardown failed", exc_info=True)


class _RenderDeviceWatcher(MMNotificationClient):
    """Asks the capture thread to rebuild its client when the endpoint changes.

    Registered on the UI thread, matching how ``services/volume`` does it. The
    callbacks only flip a flag and signal an event, so they never block the
    audio service that invokes them.
    """

    def __init__(self, service: AudioVisualizerCaptureService) -> None:
        super().__init__()
        self._service = service
        self._last_device_id = self._current_render_device_id()
        self._last_states: dict[str, int] = {}

    @staticmethod
    def _current_render_device_id() -> str | None:
        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            endpoint = enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
            return endpoint.GetId()
        except Exception:
            return None

    def on_default_device_changed(self, flow, flow_id, role, role_id, default_device_id) -> None:
        logging.debug(
            "Audio visualizer: default device changed flow=%s role=%s device=%s",
            flow_id,
            role_id,
            default_device_id,
        )
        if flow_id != EDataFlow.eRender.value or role_id != ERole.eMultimedia.value:
            return
        if default_device_id == self._last_device_id:
            return
        self._last_device_id = default_device_id
        logging.debug("Audio visualizer: default device change accepted, reopening")
        self._service.request_reopen()

    def on_device_state_changed(self, device_id, new_state, new_state_id) -> None:
        logging.debug(
            "Audio visualizer: device state changed device=%s state=%#x",
            device_id,
            new_state_id,
        )
        # A device connecting or disconnecting can touch several unrelated
        # endpoints (a headset's own microphone, other devices Windows
        # happens to re-enumerate along the way), only the one we are
        # actually reading from matters to a render-only loopback capture.
        if device_id != self._last_device_id:
            return
        if new_state_id not in (
            DEVICE_STATE.ACTIVE.value,
            DEVICE_STATE.DISABLED.value,
            DEVICE_STATE.UNPLUGGED.value,
        ):
            return
        if self._last_states.get(device_id) == new_state_id:
            return
        self._last_states[device_id] = new_state_id
        logging.debug("Audio visualizer: device state change accepted, reopening")
        self._service.request_reopen()


class AudioVisualizerCaptureService(QObject):
    """Shared, event-driven loopback capture for every visualizer widget.

    A single WASAPI stream and a single capture thread serve all widgets, on
    every monitor. The stream is open while at least one widget is attached,
    frozen while every widget's bar is hidden, and torn down once the last
    widget goes away.
    """

    #: A new spectrum has been published. Rate limited to the fastest framerate
    #: among attached widgets.
    frame_ready = pyqtSignal()
    #: The render stream went away. The published spectra have been dropped, so
    #: magnitudes() now returns silence and widgets should fade out.
    audio_stopped = pyqtSignal()
    #: The endpoint sample rate changed; analyzers must be rebuilt.
    format_changed = pyqtSignal(int)

    _instance: AudioVisualizerCaptureService | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._ring_l: list[float] = []
        self._ring_r: list[float] = []
        # (framerate, wanted-channels) per attached widget, plus a count of the
        # ones that are currently visible (not paused by a hidden bar).
        self._readers: list[tuple[int, frozenset[str]]] = []
        self._active_readers = 0
        self._wanted_channels: frozenset[str] = frozenset()
        self._frame_interval_ns = 1_000_000_000 // 60
        self._last_emit_ns = 0
        self._frame_pending = False
        # One transform per channel selector, shared by every widget and every
        # monitor. Touched only from the capture thread (_publish_frame).
        self._sources = {ch: SpectrumSource(FFT_SIZE) for ch in _CHANNELS}
        # Last spectrum per channel. The capture thread swaps this dict in one
        # atomic rebind; the UI thread reads it lock-free in magnitudes().
        self._channel_mags: dict[str, list[float]] = {}
        self._sample_rate = 48000
        self._active = False
        self._running = False
        # Capture thread only: when real (non-silent) audio last arrived.
        self._last_audio_ns = 0
        self._device_dirty = False
        self._format_rejected = False
        self._thread: threading.Thread | None = None
        self._enumerator = None
        self._watcher: _RenderDeviceWatcher | None = None

        self._audio_event = win32event.CreateEvent(None, False, False, None)  # auto-reset
        self._wake_event = win32event.CreateEvent(None, False, False, None)  # auto-reset
        self._stop_event = win32event.CreateEvent(None, True, False, None)  # manual-reset

        # Connected first so it runs before the widget slots and re-arms
        # emission as early as possible.
        self.frame_ready.connect(self._on_frame_dispatched)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.shutdown)

    @classmethod
    def instance(cls) -> AudioVisualizerCaptureService:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def is_active(self) -> bool:
        """True while real audio is flowing."""
        return self._active

    def attach(self, framerate: int, channels: frozenset[str]) -> None:
        """Register a reader wanting ``channels`` at up to ``framerate`` fps.

        A reader starts visible; the widget calls :meth:`set_reader_visible`
        when its bar is hidden or shown.
        """
        with self._lock:
            self._readers.append((self._clamp_framerate(framerate), channels))
            self._active_readers += 1
            self._refresh_readers()
        self._ensure_thread()
        win32event.SetEvent(self._wake_event)

    def detach(self, framerate: int, channels: frozenset[str], visible: bool) -> None:
        """Drop a reader. The stream closes once the last one leaves."""
        with self._lock:
            if not self._running:
                return
            try:
                self._readers.remove((self._clamp_framerate(framerate), channels))
                if visible:
                    self._active_readers = max(0, self._active_readers - 1)
            except ValueError:
                logging.debug("Audio visualizer: detach without a matching attach")
            self._refresh_readers()
        win32event.SetEvent(self._wake_event)

    def set_reader_visible(self, visible: bool) -> None:
        """A widget's bar became visible (``True``) or hidden (``False``).

        When the last visible reader goes away the capture thread freezes the
        WASAPI stream without closing it, so a re-show resumes instantly.
        """
        with self._lock:
            self._active_readers = max(0, self._active_readers + (1 if visible else -1))
        win32event.SetEvent(self._wake_event)

    @staticmethod
    def _clamp_framerate(framerate: int) -> int:
        return max(1, min(240, int(framerate)))

    def _refresh_readers(self) -> None:
        """Recompute the emit interval and the union of wanted channels.

        Caller holds the lock.
        """
        if self._readers:
            fps = max(fr for fr, _ in self._readers)
            wanted: set[str] = set()
            for _, chans in self._readers:
                wanted |= chans
            self._wanted_channels = frozenset(wanted)
        else:
            fps = 60
            self._wanted_channels = frozenset()
        self._frame_interval_ns = max(1, 1_000_000_000 // fps)

    def _reader_state(self) -> tuple[bool, bool]:
        """(any readers, any visible readers). Capture thread poll."""
        with self._lock:
            return bool(self._readers), self._active_readers > 0

    def _raw_window_locked(self, n: int) -> tuple[list[float], list[float]]:
        """Newest ``n`` samples per channel, zero-padded at the front.

        Caller holds the lock. Returns silence while the stream is idle,
        because ``_mark_stopped`` and ``_open`` clear the rings.
        """
        left = self._ring_l[-n:]
        right = self._ring_r[-n:]
        pad = n - len(left)
        if pad > 0:
            head = [0.0] * pad
            left = head + left
            right = head + right
        return left, right

    def magnitudes(self, channel: str) -> list[float]:
        """Latest magnitude spectrum for ``channel`` (``"left"``, ``"right"`` or
        ``"average"``).

        The transform itself runs on the capture thread, once per frame per
        channel no matter how many widgets or monitors ask for it. This is a
        lock-free read of the last published result, cheap enough to call from
        paint; it returns silence until the first frame after audio starts.
        """
        return self._channel_mags.get(channel, _SILENT_SPECTRUM)

    def _safe_emit(self, signal_name: str, *args) -> None:
        try:
            getattr(self, signal_name).emit(*args)
        except RuntimeError:
            pass

    def request_reopen(self) -> None:
        """Rebuild the client, e.g. after the default endpoint changed."""
        with self._lock:
            self._device_dirty = True
            self._format_rejected = False
        win32event.SetEvent(self._wake_event)

    def _ensure_thread(self) -> None:
        # Only ever called from the UI thread (via attach), so the read of
        # _thread and the start below cannot race each other.
        with self._lock:
            thread = self._thread
            if self._running and thread is not None and thread.is_alive():
                return
            self._running = True
        self._register_device_watcher()
        win32event.ResetEvent(self._stop_event)
        self._thread = threading.Thread(target=self._capture_thread, name="yasb-audio-visualizer", daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        """Stop capturing and join the thread. Safe to call more than once."""
        with self._lock:
            self._readers.clear()
            self._active_readers = 0
            self._refresh_readers()
            was_running = self._running
            self._running = False
        if not was_running:
            return

        win32event.SetEvent(self._stop_event)
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=2.0)
            if thread.is_alive():
                logging.warning("Audio visualizer: capture thread did not exit in time")

        self._unregister_device_watcher()
        with self._lock:
            self._ring_l.clear()
            self._ring_r.clear()
            self._active = False

    def _register_device_watcher(self) -> None:
        if self._watcher is not None:
            return
        try:
            self._enumerator = AudioUtilities.GetDeviceEnumerator()
            self._watcher = _RenderDeviceWatcher(self)
            self._enumerator.RegisterEndpointNotificationCallback(self._watcher)
        except Exception:
            self._watcher = None
            self._enumerator = None
            logging.warning("Audio visualizer: device change notifications unavailable", exc_info=True)

    def _unregister_device_watcher(self) -> None:
        watcher, self._watcher = self._watcher, None
        enumerator, self._enumerator = self._enumerator, None
        if watcher is None or enumerator is None:
            return
        try:
            enumerator.UnregisterEndpointNotificationCallback(watcher)
        except Exception:
            logging.debug("Audio visualizer: could not unregister device watcher", exc_info=True)

    def _capture_thread(self) -> None:
        hr = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        if hr < 0 and hr != RPC_E_CHANGED_MODE:
            logging.error("Audio visualizer: CoInitializeEx failed (0x%08X)", hr & 0xFFFFFFFF)
            return
        try:
            self._capture_loop()
        except Exception:
            logging.exception("Audio visualizer: capture thread crashed")
        finally:
            self._mark_stopped()
            if hr >= 0:
                ole32.CoUninitialize()

    def _capture_loop(self) -> None:
        handles = [self._stop_event, self._wake_event, self._audio_event]
        idle_handles = [self._stop_event, self._wake_event]
        client: _WasapiLoopbackClient | None = None
        backoff_ms = _REOPEN_BACKOFF_MIN_MS
        try:
            while self._running:
                if self._take_device_dirty():
                    client = self._close(client)
                    backoff_ms = _REOPEN_BACKOFF_MIN_MS

                has_readers, has_visible = self._reader_state()

                # No widgets at all: close the stream and park.
                if not has_readers:
                    client = self._close(client)
                    self._mark_stopped()
                    if self._park(idle_handles, win32event.INFINITE):
                        break
                    continue

                # Widgets exist but every one is hidden (an auto-hiding bar, a
                # fullscreen window, a monitor asleep). Freeze the stream but
                # keep the client, so the next re-show resumes with no reopen.
                if not has_visible:
                    if client is not None:
                        try:
                            client.pause()
                        except Exception:
                            logging.debug("Audio visualizer: pause failed, closing", exc_info=True)
                            client = self._close(client)
                    self._mark_stopped()
                    if self._park(idle_handles, win32event.INFINITE):
                        break
                    continue

                if client is None:
                    if self._format_rejected:
                        # Only a device change can make this work; wait for one
                        # rather than retrying a format we cannot decode.
                        if self._park(idle_handles, win32event.INFINITE):
                            break
                        continue
                    client = self._open()
                    if client is None:
                        self._mark_stopped()
                        if self._park(idle_handles, backoff_ms):
                            break
                        backoff_ms = min(backoff_ms * 2, _REOPEN_BACKOFF_MAX_MS)
                        continue
                    backoff_ms = _REOPEN_BACKOFF_MIN_MS
                    # Give the new stream the full timeout to produce audio, so
                    # swapping devices mid-track does not blip the bars to zero.
                    self._last_audio_ns = time.monotonic_ns()
                elif not client.running:
                    try:
                        client.resume()
                    except Exception:
                        logging.warning("Audio visualizer: resume failed, reopening", exc_info=True)
                        client = self._close(client)
                        continue
                    self._last_audio_ns = time.monotonic_ns()

                rc = win32event.WaitForMultipleObjects(handles, False, client.stale_timeout_ms)
                if rc == win32event.WAIT_OBJECT_0 + _STOP:
                    break
                if rc == win32event.WAIT_OBJECT_0 + _WAKE:
                    continue

                if rc == win32event.WAIT_OBJECT_0 + _AUDIO:
                    try:
                        if self._drain(client):
                            self._last_audio_ns = time.monotonic_ns()
                            self._publish_frame()
                    except COMError as exc:
                        # The endpoint was invalidated mid-stream: another app
                        # claimed the device exclusively (ASIO and similar
                        # drivers bypass the shared mixer entirely), it was
                        # unplugged, or it was reconfigured. Reopening below
                        # succeeds on its own once the device is available
                        # again, same as _open()'s COMError handling.
                        logging.debug("Audio visualizer: loopback stream invalidated (%s), reopening", exc)
                        client = self._close(client)
                        self._mark_stopped()
                        if self._park(idle_handles, backoff_ms):
                            break
                        backoff_ms = min(backoff_ms * 2, _REOPEN_BACKOFF_MAX_MS)
                        continue
                    except Exception:
                        logging.warning("Audio visualizer: loopback stream failed, reopening", exc_info=True)
                        client = self._close(client)
                        self._mark_stopped()
                        # Back off like a failed open, so a packet that keeps
                        # failing to drain cannot spin this loop at the device
                        # period rate.
                        if self._park(idle_handles, backoff_ms):
                            break
                        backoff_ms = min(backoff_ms * 2, _REOPEN_BACKOFF_MAX_MS)
                        continue
                elif rc != win32event.WAIT_TIMEOUT:
                    continue

                # Idle means "no real audio for several device periods", which
                # covers both the render stream ending and it staying open while
                # feeding pure silence. Muting an app is the latter: packets keep
                # arriving forever, so waiting for them to stop would leave the
                # bars frozen on the last frame before the mute.
                if self._silent_for(client.stale_timeout_ms):
                    self._mark_stopped()
        finally:
            self._close(client)

    def _silent_for(self, timeout_ms: int) -> bool:
        """Has no real audio arrived for ``timeout_ms``? Capture thread only."""
        return time.monotonic_ns() - self._last_audio_ns >= timeout_ms * 1_000_000

    def _park(self, handles: list, timeout_ms: int) -> bool:
        """Block on wake/stop. Returns True when shutdown was requested."""
        rc = win32event.WaitForMultipleObjects(handles, False, timeout_ms)
        return rc == win32event.WAIT_OBJECT_0 + _STOP

    def _take_device_dirty(self) -> bool:
        with self._lock:
            dirty, self._device_dirty = self._device_dirty, False
        return dirty

    def _open(self) -> _WasapiLoopbackClient | None:
        try:
            client = _WasapiLoopbackClient(int(self._audio_event))
        except UnsupportedFormatError as exc:
            logging.error("Audio visualizer: %s", exc)
            with self._lock:
                self._format_rejected = True
            return None
        except COMError:
            return None
        except Exception:
            logging.debug("Audio visualizer: could not open WASAPI loopback", exc_info=True)
            return None

        with self._lock:
            self._ring_l.clear()
            self._ring_r.clear()
            rate_changed = client.sample_rate != self._sample_rate
            self._sample_rate = client.sample_rate
        if rate_changed:
            self._safe_emit("format_changed", client.sample_rate)
        logging.info("Audio visualizer: loopback capture open (%s)", client.format_summary)
        return client

    @staticmethod
    def _close(client: _WasapiLoopbackClient | None) -> None:
        if client is not None:
            client.close()
        return None

    def _drain(self, client: _WasapiLoopbackClient) -> bool:
        """Consume every ready packet. Returns True if real audio arrived."""
        capture = client.capture
        if capture is None:
            return False
        frame_bytes = client.frame_bytes
        got_audio = False

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
                # The packet must be released even if the copy raised, or the
                # capture buffer stays locked and the stream stalls for good.
                capture.ReleaseBuffer(nframes)

            # While "nothing is playing but the endpoint is open" every packet
            # is digital silence. count() is a C-level scan and roughly 35x
            # cheaper than decoding, so discard those before doing any work.
            if not buf or buf.count(0) == len(buf):
                self._publish_silence()
                continue

            left, right = _decode_stereo(buf, client.channels, client.sample_code, client.sample_scale)

            # Muting an app scales its samples by zero, which turns every
            # negative one into negative zero. Those are not zero bytes, so the
            # scan above lets them through and the stream would look alive
            # forever. Test amplitude as well; max() short-circuits this to a
            # single C pass for anything actually audible.
            if _is_silent(left) and _is_silent(right):
                self._publish_silence()
                continue

            with self._lock:
                self._ring_l.extend(left)
                self._ring_r.extend(right)
                overflow = len(self._ring_l) - _RING_SIZE
                if overflow > 0:
                    del self._ring_l[:overflow]
                    del self._ring_r[:overflow]
            got_audio = True

        return got_audio

    def _publish_frame(self) -> None:
        now = time.monotonic_ns()
        with self._lock:
            self._active = True
            if self._frame_pending or now - self._last_emit_ns < self._frame_interval_ns:
                return
            wanted = self._wanted_channels
            if not wanted:
                return
            self._frame_pending = True
            self._last_emit_ns = now
            left, right = self._raw_window_locked(FFT_SIZE)

        # The transform is the expensive part (~0.3 ms per channel). Run it here
        # on the capture thread, outside the lock, so it never competes with the
        # bar's own painting and animations on the UI thread.
        mags: dict[str, list[float]] = {}
        for channel in wanted:
            if channel == "left":
                window = left
            elif channel == "right":
                window = right
            else:
                window = [0.5 * (left[i] + right[i]) for i in range(FFT_SIZE)]
            mags[channel] = self._sources[channel].magnitudes(window)
        # One atomic rebind; magnitudes() reads it lock-free.
        self._channel_mags = mags
        self._safe_emit("frame_ready")

    def _publish_silence(self) -> None:
        """Publish a zero spectrum for a silent packet, the same as a real
        frame but without the transform. Gated on ``_active`` so it only
        applies while a stream was recently live, never during genuine idle.
        """
        now = time.monotonic_ns()
        with self._lock:
            if not self._active or self._frame_pending or now - self._last_emit_ns < self._frame_interval_ns:
                return
            wanted = self._wanted_channels
            if not wanted:
                return
            self._frame_pending = True
            self._last_emit_ns = now

        self._channel_mags = dict.fromkeys(wanted, _SILENT_SPECTRUM)
        self._safe_emit("frame_ready")

    def _on_frame_dispatched(self) -> None:
        """Runs on the UI thread ahead of the widget slots; re-arms emission."""
        self._frame_pending = False

    def _mark_stopped(self) -> None:
        """Drop captured history and tell the widgets the stream went away."""
        with self._lock:
            if not self._active:
                return
            self._active = False
            self._frame_pending = False
            self._ring_l.clear()
            self._ring_r.clear()
        self._channel_mags = {}
        self._safe_emit("audio_stopped")
