import time
from typing import Any

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtProperty, pyqtSignal

from core.services.audio_visualizer.loopback import AudioVisualizerCaptureService
from core.services.audio_visualizer.spectrum import FFT_SIZE, SpectrumAnalyzer, layout_mono, layout_stereo
from core.utils.qml import qml_property


class _Reader:
    """A claim on the shared capture stream.

    Holds no reference to its AudioLevels, so the destroyed signal can drop the claim without keeping it alive.
    """

    def __init__(self, service: AudioVisualizerCaptureService, framerate: int, channels: frozenset[str]) -> None:
        self.service = service
        self.framerate = framerate
        self.channels = channels
        self.visible = True
        self.attached = False

    def attach(self, visible: bool) -> None:
        self.service.attach(self.framerate, self.channels)
        self.attached = True
        self.visible = True
        self.set_visible(visible)

    def detach(self) -> None:
        if self.attached:
            self.service.detach(self.framerate, self.channels, self.visible)
            self.attached = False

    def set_visible(self, visible: bool) -> None:
        if self.attached and visible != self.visible:
            self.visible = visible
            self.service.set_reader_visible(visible)


class AudioLevels(QObject):
    """The level of each frequency band in what an output device plays, from 0 to 1, for drawing a visualizer."""

    @staticmethod
    def _option(kind: type | str, name: str) -> pyqtProperty[Any]:
        """A setting QML writes, which restarts the analysis with the new value."""

        def get(self: AudioLevels) -> Any:
            return self._options[name]

        def set(self: AudioLevels, value: Any) -> None:
            if value != self._options[name]:
                self._options[name] = value
                self._restart.start()

        return pyqtProperty(kind, get, set)

    levelsChanged = pyqtSignal()
    playingChanged = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._options: dict[str, Any] = {
            "source": "auto",
            "bands": 24,
            "stereo": False,
            "monoChannel": "average",
            "reverse": False,
            "sensitivity": 50,
            "smoothness": 55,
            "autoGain": True,
            "freqMin": 50,
            "freqMax": 12000,
            "framerate": 60,
            "idleAfter": 2000,
        }
        self._running = True
        self._levels: list[float] = [0.0] * 24
        self._playing = False
        self._reader: _Reader | None = None
        # The current claim, which the destroyed signal drops
        claim: list[_Reader | None] = [None]
        self._claim = claim
        self.destroyed.connect(lambda *_: claim[0] and claim[0].detach())
        self._left: SpectrumAnalyzer | None = None
        self._right: SpectrumAnalyzer | None = None
        self._audio_active = False
        self._last_frame_ns = 0

        # QML sets the options after creating the object, so the analysis starts once that is done
        self._restart = QTimer(self)
        self._restart.setSingleShot(True)
        self._restart.setInterval(0)
        self._restart.timeout.connect(self._start)
        self._restart.start()

        # Walks the bands down to zero once the audio stops, rather than freezing them on the last frame
        self._fade = QTimer(self)
        self._fade.setTimerType(Qt.TimerType.CoarseTimer)
        self._fade.timeout.connect(self._fade_step)

        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.timeout.connect(lambda: self._set_playing(False))

    # "auto" for the Windows default output device, or a device's full name
    source = _option(str, "source")
    # How many bands; with stereo, split between the left and right channel
    bands = _option(int, "bands")
    stereo = _option(bool, "stereo")
    # average, left or right: what mono shows
    monoChannel = _option(str, "monoChannel")
    # Mono: high to low frequencies. Stereo: bass on the outside edges instead of the middle
    reverse = _option(bool, "reverse")
    # 0 to 100. With autoGain it sets how hard the loudest bands push to the top, otherwise 50 is 1x and 100 is 2x
    sensitivity = _option(int, "sensitivity")
    # 0 to 100, higher is smoother and slower
    smoothness = _option(int, "smoothness")
    # Levels quiet and loud music to look the same
    autoGain = _option(bool, "autoGain")
    freqMin = _option(int, "freqMin")
    freqMax = _option(int, "freqMax")
    # Most updates per second
    framerate = _option(int, "framerate")
    # How long silence lasts before playing turns false, in milliseconds
    idleAfter = _option(int, "idleAfter")

    def _get_running(self) -> bool:
        return self._running

    def _set_running(self, running: bool) -> None:
        if running == self._running:
            return
        self._running = running
        if self._reader is not None:
            self._reader.set_visible(running)
        if not running:
            self._fade.stop()
            self._audio_active = False
            self._reset()

    # Off while the visualizer isn't on screen, which stops the analysis but still reports playing
    running = pyqtProperty(bool, _get_running, _set_running)

    @qml_property("QVariantList", notify=levelsChanged)
    def levels(self) -> list[float]:
        return self._levels

    # Whether audio is playing, staying true for idleAfter once it stops
    @qml_property(bool, notify=playingChanged)
    def playing(self) -> bool:
        return self._playing

    def _start(self) -> None:
        self._stop()
        options = self._options
        bands = max(2, min(128, options["bands"]))
        stereo = options["stereo"]
        right_bands = max(2, bands // 2) if stereo else 0
        service = AudioVisualizerCaptureService.instance(options["source"])

        def analyzer(count: int) -> SpectrumAnalyzer:
            return SpectrumAnalyzer(
                bands=count,
                fft_size=FFT_SIZE,
                sample_rate=service.sample_rate,
                f_min=float(max(20, min(options["freqMin"], options["freqMax"] - 1))),
                f_max=float(min(24000, options["freqMax"])),
                sensitivity=max(0.1, min(2.0, options["sensitivity"] / 50.0)),
                smoothness=max(0, min(100, options["smoothness"])) / 100.0,
                auto_gain=options["autoGain"],
            )

        self._left = analyzer(max(2, bands - right_bands) if stereo else bands)
        self._right = analyzer(right_bands) if stereo else None
        self._fade.setInterval(max(8, 1000 // self._framerate()))
        self._idle.setInterval(max(100, options["idleAfter"]))
        self._reset()

        channels = frozenset({"left", "right"}) if stereo else frozenset({options["monoChannel"]})
        reader = self._reader = self._claim[0] = _Reader(service, self._framerate(), channels)
        service.frame_ready.connect(self._on_frame)
        service.audio_started.connect(self._on_audio_started)
        service.audio_stopped.connect(self._on_audio_stopped)
        service.format_changed.connect(self._on_format_changed)
        reader.attach(self._running)
        if service.is_active:
            self._on_audio_started()
        else:
            self._idle.start()

    def _stop(self) -> None:
        reader, self._reader = self._reader, None
        if reader is None:
            return
        service = reader.service
        service.frame_ready.disconnect(self._on_frame)
        service.audio_started.disconnect(self._on_audio_started)
        service.audio_stopped.disconnect(self._on_audio_stopped)
        service.format_changed.disconnect(self._on_format_changed)
        reader.detach()
        self._fade.stop()
        self._idle.stop()
        self._audio_active = False

    def _framerate(self) -> int:
        return max(1, min(240, self._options["framerate"]))

    def _frame_delta(self) -> float:
        """Seconds since the last frame, which keeps the smoothing the same at any framerate."""
        now = time.monotonic_ns()
        previous, self._last_frame_ns = self._last_frame_ns, now
        return (now - previous) / 1e9 if previous else 1.0 / self._framerate()

    def _publish(self, left: list[float], right: list[float] | None) -> None:
        reverse = self._options["reverse"]
        levels = layout_mono(left, reverse) if right is None else layout_stereo(left, right, reverse)
        if levels != self._levels:
            self._levels = levels
            self.levelsChanged.emit()

    def _reset(self) -> None:
        if self._left is not None:
            self._left.reset()
            if self._right is not None:
                self._right.reset()
            count = self._left.bands + (self._right.bands if self._right is not None else 0)
            if self._levels != [0.0] * count:
                self._levels = [0.0] * count
                self.levelsChanged.emit()

    def _on_frame(self) -> None:
        if not self._running or self._reader is None or self._left is None:
            return
        if self._audio_active:
            if time.monotonic_ns() - self._last_frame_ns < 1_000_000_000 // self._framerate():
                return
        else:
            self._audio_active = True
            self._fade.stop()
        dt = self._frame_delta()
        service = self._reader.service
        if self._right is None:
            self._publish(self._left.map_bands(service.magnitudes(self._options["monoChannel"]), dt), None)
        else:
            left = self._left.map_bands(service.magnitudes("left"), dt)
            self._publish(left, self._right.map_bands(service.magnitudes("right"), dt))

    def _fade_step(self) -> None:
        if self._left is None:
            self._fade.stop()
            return
        dt = self._frame_delta()
        left, moving = self._left.decay(dt)
        right = None
        if self._right is not None:
            right, moving_right = self._right.decay(dt)
            moving = moving or moving_right
        self._publish(left, right)
        if not moving:
            self._fade.stop()

    def _on_audio_started(self) -> None:
        self._idle.stop()
        self._set_playing(True)

    def _on_audio_stopped(self) -> None:
        self._audio_active = False
        if self._running:
            self._fade.start()
        self._idle.start()

    def _on_format_changed(self, sample_rate: int) -> None:
        for analyzer in (self._left, self._right):
            if analyzer is not None:
                analyzer.set_sample_rate(sample_rate)

    def _set_playing(self, playing: bool) -> None:
        if playing != self._playing:
            self._playing = playing
            self.playingChanged.emit()
