from __future__ import annotations

import atexit
import logging
import re
import threading
import time
from typing import Any, cast, override

import PyQt6.QtGui as QtGui
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtCore import (
    pyqtProperty as _pyqtProperty,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType]
)
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import QApplication, QGraphicsOpacityEffect, QMenu, QWidget
from qasync import asyncSlot  # type: ignore

from core.utils.tooltip import set_tooltip
from core.utils.utilities import refresh_widget_style
from core.validation.widgets.yasb.lyrics import LyricsWidgetConfig
from core.widgets.base import BaseWidget
from core.widgets.services.lyrics.cache import LyricsCache
from core.widgets.services.lyrics.engine import SyncEngine, SyncStatus
from core.widgets.services.lyrics.karaoke_label import KaraokeLabel
from core.widgets.services.lyrics.lyrics_popup import LyricsPopup, resolve_yasb_theme_data
from core.widgets.services.lyrics.models import Hit, Line, Lyrics, Query, Word
from core.widgets.services.lyrics.orchestrator import LyricsOrchestrator
from core.widgets.services.lyrics.session import (
    PlaybackSnapshot,
    TrackInfo,
    select_session,
    snapshot_from_session,
    track_from_session,
)
from core.widgets.services.lyrics.track_filter import sanitize_song_title, should_search_lyrics
from core.widgets.services.media.media import SessionState, WindowsMedia

logger = logging.getLogger("core.widgets.services.lyrics.widget")

_pyqt_property = cast("Any", _pyqtProperty)


def _add_action(menu: QMenu, text: str) -> QAction:
    action = menu.addAction(text)
    assert action is not None
    return action


class LyricsWorker(QThread):
    """Fetches lyrics for the newest track request, dropping superseded ones."""

    lyrics_loaded = pyqtSignal(object, object)  # list[Hit], TrackInfo | None
    state_changed = pyqtSignal(str)  # "searching", "synced", "plain", "not-found", "failed"

    def __init__(self, config: LyricsWidgetConfig):
        super().__init__()
        self.config = config
        self._is_running = True
        self._cache = LyricsCache()
        self._orchestrator = LyricsOrchestrator(cache=self._cache)
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._pending: TrackInfo | None = None
        self._generation = 0

    @property
    def cache(self) -> LyricsCache:
        """Shared lyrics/offset cache."""
        return self._cache

    def request(self, track: TrackInfo) -> None:
        """Queues a fetch, invalidating any fetch still in flight."""
        with self._lock:
            self._pending = track
            self._generation += 1
        self._wake.set()

    def run(self):
        try:
            while self._is_running:
                if not self._wake.wait(0.2):
                    continue
                self._wake.clear()
                with self._lock:
                    track, generation = self._pending, self._generation
                    self._pending = None
                if track is not None:
                    self._fetch(track, generation)
        finally:
            self._orchestrator.close()

    def _is_stale(self, generation: int) -> bool:
        with self._lock:
            return not self._is_running or generation != self._generation

    def _fetch(self, track: TrackInfo, generation: int) -> None:
        query = Query(
            title=sanitize_song_title(track.title),
            artist=track.artist,
            duration_s=(track.duration_ms / 1000.0) if track.duration_ms else None,
        )
        self.state_changed.emit("searching")

        def _on_candidate_upgrade(hits: list[Hit]):
            self._emit_upgrade(hits, track, generation)

        try:
            hits = self._orchestrator.fetch(query, _on_candidate_upgrade)
        except Exception as e:
            if self._is_stale(generation):
                return
            logger.error("Failed to fetch lyrics for %s: %s", track.title, e)
            self.lyrics_loaded.emit([], track)
            self.state_changed.emit("failed")
            return

        if self._is_stale(generation):
            return
        if hits:
            self._emit_upgrade(hits, track, generation)
        else:
            self.lyrics_loaded.emit([], track)
            self.state_changed.emit("not-found")

    def _emit_upgrade(self, hits: list[Hit], track: TrackInfo, generation: int) -> None:
        if not hits or self._is_stale(generation):
            return

        popup_rom = getattr(getattr(self.config, "popup", None), "romanize", True)
        widget_rom_replace = getattr(self.config, "romanize_replace", False)
        if popup_rom or widget_rom_replace:
            try:
                from core.widgets.services.lyrics.romanize import romanize_lyrics

                for h in hits:
                    h.lyrics = romanize_lyrics(h.lyrics, target_scripts=None)
            except Exception as e:
                logger.debug("Romanization error: %s", e)

        if self._is_stale(generation):
            return
        self.lyrics_loaded.emit(hits, track)
        has_synced = any(h.lyrics.synced() if callable(h.lyrics.synced) else h.lyrics.synced for h in hits)
        self.state_changed.emit("synced" if has_synced else "plain")

    def stop(self) -> None:
        self._is_running = False
        self._wake.set()
        self.wait(1500)


class LyricsWidget(BaseWidget):
    validation_schema = LyricsWidgetConfig
    audio_frame_ready = pyqtSignal(list)

    def _get_anim_width(self) -> int:
        return self._cur_anim_width

    def _set_anim_width(self, w: int) -> None:
        self._cur_anim_width = w
        self.setFixedWidth(w)

    anim_width: Any = _pyqt_property(int, _get_anim_width, _set_anim_width)

    def __init__(self, config: LyricsWidgetConfig):
        super().__init__(class_name=f"lyrics-widget {config.class_name}".strip())
        self.config = config

        self._current_track: TrackInfo | None = None
        self._last_playback: PlaybackSnapshot | None = None
        self._hits: list[Hit] = []
        self._hit_index: int = 0
        self._active_lyrics: Lyrics | None = None
        self._current_state: str = "idle"
        self._paused_since: float | None = None
        self._popup: LyricsPopup | None = None

        self.audio_frame_ready.connect(self._on_audio_frame)
        self.destroyed.connect(self.stop)
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.stop)
        atexit.register(self.stop)

        self._audio_stream = None
        if self._is_audio_reactive_enabled():
            try:
                from core.widgets.services.lyrics.wasapi_audio import WasapiAudioStream

                mode = self._get_visualizer_mode()
                opts = self.config.visualizer_options
                bars_num = opts.bars_number or (14 if "waves" in mode else 10)
                self._audio_stream = WasapiAudioStream(
                    bars_number=bars_num,
                    framerate=opts.framerate,
                    noise_reduction=opts.noise_reduction,
                    on_frame=self.audio_frame_ready.emit,
                    monstercat=opts.monstercat,
                    sensitivity=opts.sensitivity,
                    lower_cutoff_freq=opts.lower_cutoff_freq,
                    higher_cutoff_freq=opts.higher_cutoff_freq,
                    layout=opts.layout,
                    reverse=opts.reverse,
                )
                self._audio_stream.start()
            except Exception as e:
                logger.debug("Failed to start WasapiAudioStream: %s", e)

        self._init_container()
        self._setup_label()

        self._target_visible: bool = False
        self._cur_anim_width: int = 0
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._width_anim: QPropertyAnimation | None = None
        self._opacity_anim: QPropertyAnimation | None = None

        self.setFixedWidth(0)
        self._widget_frame.setMinimumWidth(0)
        self._opacity_effect.setOpacity(0.0)
        self.hide()

        self._engine = SyncEngine()

        self._worker = LyricsWorker(config)
        self._worker.lyrics_loaded.connect(self._on_lyrics_loaded)
        self._worker.state_changed.connect(self._on_state_changed)
        self._worker.start()

        self._media = WindowsMedia()
        self._media_sessions: dict[str, SessionState] = {}
        self._track_key: tuple[str, str, str, int] | None = None
        self._artwork_key: int | None = None
        self._media.media_data_changed.connect(self._on_media_data_changed)
        for signal in (
            self._media.current_session_changed,
            self._media.media_properties_changed,
            self._media.timeline_info_changed,
            self._media.playback_info_changed,
        ):
            signal.connect(self._on_media_state_dirty)

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(16)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start()

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_popup", self._toggle_popup)
        self.register_callback("toggle_menu", self._show_context_menu)
        self.register_callback("cycle_hit", self._cycle_next_hit)
        self.register_callback("copy_lyrics", self._copy_current_lyrics)

        self.callback_left = self.config.callbacks.on_left
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_right = self.config.callbacks.on_right

    @staticmethod
    def _format_secondary_text(raw: str) -> str:
        cleaned = raw.strip()
        if cleaned.startswith("(") and cleaned.endswith(")"):
            return cleaned
        return f"({cleaned})"

    def _build_display_karaoke(
        self,
        line: Line,
    ) -> tuple[str, list[Word] | None, str, list[Word] | None]:
        main_text = line.text
        words = [Word(w.start_ms, w.end_ms, w.text) for w in line.words] if line.words else None

        if getattr(self.config, "romanize_replace", False) and line.romanized:
            main_text = line.romanized
            if words:
                words_list = line.romanized.split()
                if words_list:
                    total_chars = max(1, sum(len(w) for w in words_list))
                    start_ms = line.start_ms
                    end_ms = line.end_ms if line.end_ms is not None else (start_ms + 2500)
                    total_dur = max(len(words_list) * 200, end_ms - start_ms)
                    cur_start = start_ms
                    rom_words: list[Word] = []
                    for i, w_str in enumerate(words_list):
                        w_dur = max(120, int((len(w_str) / total_chars) * total_dur))
                        w_end = cur_start + w_dur
                        text_token = f"{w_str} " if i < len(words_list) - 1 else w_str
                        rom_words.append(Word(start_ms=cur_start, end_ms=w_end, text=text_token))
                        cur_start = w_end
                    words = rom_words

        sec_text = ""
        sec_words: list[Word] | None = None

        if line.secondary:
            sec_parts: list[str] = []
            sec_words_list: list[Word] = []
            for lane in line.secondary:
                lane_text = (
                    lane.romanized
                    if (getattr(self.config, "romanize_replace", False) and lane.romanized)
                    else lane.text
                )
                if not lane_text:
                    continue
                lane_fmt = self._format_secondary_text(lane_text)
                sec_parts.append(lane_fmt)

                if lane.words and not getattr(self.config, "romanize_replace", False):
                    lane_sec_words: list[Word] = []
                    for w in lane.words:
                        lane_sec_words.append(Word(start_ms=w.start_ms, end_ms=w.end_ms, text=w.text))

                    if not lane.text.strip().startswith("(") and lane_fmt.startswith("(") and lane_sec_words:
                        lane_sec_words[0] = Word(
                            lane_sec_words[0].start_ms, lane_sec_words[0].end_ms, f"({lane_sec_words[0].text}"
                        )
                        lane_sec_words[-1] = Word(
                            lane_sec_words[-1].start_ms, lane_sec_words[-1].end_ms, f"{lane_sec_words[-1].text})"
                        )
                    sec_words_list.extend(lane_sec_words)
                else:
                    lane_start = lane.start_ms
                    lane_end = lane.end_ms if lane.end_ms is not None else (lane_start + 1500)
                    words_list = lane_fmt.split()
                    if words_list:
                        total_chars = max(1, sum(len(w) for w in words_list))
                        total_dur = max(len(words_list) * 200, lane_end - lane_start)
                        cur_start = lane_start
                        for i, w_str in enumerate(words_list):
                            w_dur = max(150, int((len(w_str) / total_chars) * total_dur))
                            w_end = cur_start + w_dur
                            text_token = f"{w_str} " if i < len(words_list) - 1 else w_str
                            sec_words_list.append(Word(start_ms=cur_start, end_ms=w_end, text=text_token))
                            cur_start = w_end

            if sec_parts:
                sec_text = " ".join(sec_parts)
            if sec_words_list:
                sec_words = sec_words_list

        return main_text, words, sec_text, sec_words

    def _setup_label(self):
        self._label = KaraokeLabel(self, default_text="")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.set_transition_config(
            mode=self.config.line_transition,
            duration_ms=280,
            easing="out_cubic",
        )
        vis_mode = self._get_visualizer_mode()
        vis_enabled = vis_mode in ("bars", "bars_mirrored", "waves", "waves_mirrored")
        vis_style = "waves" if "waves" in vis_mode else "bars"
        vis_sym = "mirrored" in vis_mode

        sparkles_val = getattr(self.config, "sparkles", True)
        sparkles_enabled = (
            bool(sparkles_val)
            if isinstance(sparkles_val, bool)
            else (str(sparkles_val).lower().strip() in ("on", "true", "1"))
        )
        beat_jump_val = getattr(self.config, "beat_jump", True)
        beat_jump_enabled = (
            bool(beat_jump_val)
            if isinstance(beat_jump_val, bool)
            else (str(beat_jump_val).lower().strip() in ("on", "true", "1"))
        )

        self._label.set_audio_reactive_config(
            break_visualizer=vis_enabled,
            break_visualizer_style=vis_style,
            break_visualizer_symmetry=vis_sym,
            karaoke_beat_glow=True,
            sparkles=sparkles_enabled,
            beat_jump=beat_jump_enabled,
            line_sparks=True,
            line_beat_glow=True,
            line_beat_bounce=True,
        )
        vis_opts = self.config.visualizer_options
        self._label.set_visualizer_style_options(
            bar_width=vis_opts.bar_width,
            bar_spacing=vis_opts.bar_spacing,
            bar_radius=vis_opts.bar_radius,
            bar_height=vis_opts.bar_height,
            min_bar_height=vis_opts.min_bar_height,
            vertical_alignment=vis_opts.vertical_alignment,
        )
        accent_target = getattr(self.config, "apply_accent_to", getattr(self.config, "colors", "effects"))
        self._label.set_album_color_mode(accent_target)
        self._label.set_syllable_physics(True)
        if getattr(self.config, "accent", "album_art") == "yasb":
            p_col, s_col = self._get_yasb_accent_palette(self)
            self._label.set_album_art_palette(
                (p_col.red(), p_col.green(), p_col.blue()),
                (s_col.red(), s_col.green(), s_col.blue()),
            )

        font_scale = getattr(self.config, "font_scale", 1.0)
        if font_scale != 1.0:
            f = self._label.font()
            pt = f.pointSizeF()
            if pt > 0:
                f.setPointSizeF(pt * font_scale)
            else:
                px = f.pixelSize()
                if px > 0:
                    f.setPixelSize(max(8, int(px * font_scale)))
            self._label.setFont(f)

        self._label.setMinimumWidth(0)
        self._widget_frame.setMinimumWidth(0)

        self._label.setProperty("class", "label")
        self._widget_container_layout.addWidget(self._label)

    def _get_visualizer_mode(self) -> str:
        vis = getattr(self.config, "visualizer", None)
        if isinstance(vis, str):
            v = vis.lower().strip()
            if v in ("bars", "bars_mirrored", "waves", "waves_mirrored", "notes", "dots", "none"):
                return v
        elif vis is True:
            return "bars"
        elif vis is False:
            return "none"

        return "bars"

    def _display_break_or_prelude(self, progress: float, state_class: str) -> None:
        mode = self._get_visualizer_mode()
        if self._audio_stream:
            self._label.set_bass_energy(self._audio_stream.get_bass_energy())
        if mode == "notes":
            self._label.set_break_notes(progress=progress, state=state_class)
        elif mode == "dots":
            self._label.set_cue_dots(
                progress=progress,
                is_searching=False,
                prefix="",
                state=state_class,
            )
        elif mode in ("bars", "bars_mirrored", "waves", "waves_mirrored"):
            samples = self._audio_stream.get_spectrum() if self._audio_stream else None
            style = "waves" if "waves" in mode else "bars"
            sym = "mirrored" in mode
            self._label.set_break_visualizer_style(style, symmetry=sym)
            self._label.set_break_visualizer(
                samples=samples or [0.2] * 6,
                progress=progress,
                prefix="",
                state=state_class,
                style=mode,
            )
        else:  # "none" -> show 3 notes statically with only the progressive color fill
            self._label.set_break_notes(progress=progress, state=state_class, animated=False)
        self._apply_widget_classes(state_class)

    def _on_audio_frame(self, samples: list[float]) -> None:
        if getattr(self._label, "is_visualizer_active", False):
            self._label.update_break_visualizer_samples(samples)
        if self._audio_stream:
            self._label.set_bass_energy(self._audio_stream.get_bass_energy())

    def _is_audio_reactive_enabled(self) -> bool:
        mode = self._get_visualizer_mode()
        vis_audio_reactive = mode in ("bars", "bars_mirrored", "waves", "waves_mirrored", "notes", "dots")
        sparkles_val = getattr(self.config, "sparkles", True)
        sparkles_enabled = (
            bool(sparkles_val)
            if isinstance(sparkles_val, bool)
            else (str(sparkles_val).lower().strip() in ("on", "true", "1"))
        )
        beat_jump_val = getattr(self.config, "beat_jump", True)
        beat_jump_enabled = (
            bool(beat_jump_val)
            if isinstance(beat_jump_val, bool)
            else (str(beat_jump_val).lower().strip() in ("on", "true", "1"))
        )
        return bool(vis_audio_reactive or sparkles_enabled or beat_jump_enabled or mode != "none")

    def _on_media_data_changed(self, sessions: dict[str, SessionState]) -> None:
        self._media_sessions = sessions
        self._sync_media_state()

    def _on_media_state_dirty(self) -> None:
        """Session/property/timeline signals carry no payload; reuse the last snapshot."""
        self._sync_media_state()

    def _sync_media_state(self) -> None:
        state = select_session(self._media_sessions)
        if state is None or not state.title:
            if self._current_track is not None:
                self._track_key = None
                self._artwork_key = None
                self._on_track_changed(None)
            return

        key = (state.app_id, state.title, state.artist, int(state.duration))
        if key != self._track_key:
            self._track_key = key
            track = track_from_session(state)
            self._artwork_key = id(state.thumbnail)
            self._on_track_changed(track)
            if should_search_lyrics(track):
                self._worker.request(track)
        elif self._artwork_key != id(state.thumbnail) and self._current_track is not None:
            self._artwork_key = id(state.thumbnail)
            track = track_from_session(state)
            self._current_track.thumbnail_bytes = track.thumbnail_bytes
            self._update_album_art(track)
        elif (
            self._current_track is not None
            and not self._current_track.duration_ms
            and state.duration
            and state.duration > 0
        ):
            self._current_track.duration_ms = int(state.duration * 1000)
            self._engine.set_total_duration(self._current_track.duration_ms)

        self._on_playback_changed(snapshot_from_session(state))

    def _update_album_art(self, track: TrackInfo) -> None:
        if getattr(self.config, "accent", "album_art") == "yasb":
            p_col, s_col = self._get_yasb_accent_palette(self)
            self._label.set_album_art_palette(
                (p_col.red(), p_col.green(), p_col.blue()), (s_col.red(), s_col.green(), s_col.blue())
            )
            if hasattr(self, "_popup") and self._popup:
                self._popup.set_palette_colors(p_col, s_col)
        elif track.thumbnail_bytes:
            try:
                from core.widgets.services.lyrics.color import extract_color_palette

                palette = extract_color_palette(track.thumbnail_bytes)
                if palette:
                    self._label.set_album_art_palette(palette[0], palette[1])
                    if hasattr(self, "_popup") and self._popup:
                        self._popup.set_palette_colors(QColor(*palette[0]), QColor(*palette[1]))
                else:
                    self._label.set_album_art_palette(None, None)
                    if hasattr(self, "_popup") and self._popup:
                        self._popup.set_palette_colors(None, None)
            except Exception as e:
                logging.getLogger("core.widgets.services.lyrics.widget").debug("Failed to set album art color: %s", e)
        else:
            self._label.set_album_art_palette(None, None)
            if hasattr(self, "_popup") and self._popup:
                self._popup.set_palette_colors(None, None)

    def _on_track_changed(self, track: TrackInfo | None):
        is_new_song = track is not None and (
            self._current_track is None
            or track.title != self._current_track.title
            or track.artist != self._current_track.artist
        )
        self._current_track = track
        if track is None or not should_search_lyrics(track):
            self._hits.clear()
            self._hit_index = 0
            self._active_lyrics = None
            self._engine.set_lyrics(None)
            self._current_state = "idle"
            self._label.set_album_art_color(None)
            if hasattr(self, "_popup") and self._popup:
                self._popup.set_palette_colors(None, None)
        else:
            if is_new_song:
                self._current_state = "searching"
                self._set_label_text("", state_class="searching")

            self._update_album_art(track)
        self._update_tooltip()
        self._sync_popup()

    def _on_playback_changed(self, snapshot: PlaybackSnapshot):
        self._last_playback = snapshot
        dur = self._current_track.duration_ms if (self._current_track and self._current_track.duration_ms) else 0
        if not dur and self._hits and 0 <= self._hit_index < len(self._hits):
            h = self._hits[self._hit_index]
            if h.duration_s and h.duration_s > 0:
                dur = int(h.duration_s * 1000)
        if not dur and self._active_lyrics:
            span = self._active_lyrics.span_ms()
            if span and span > 0:
                dur = span
        if dur:
            if self._current_track and not self._current_track.duration_ms:
                self._current_track.duration_ms = dur
            self._engine.set_total_duration(dur)
        self._engine.update_snapshot(snapshot)
        self._sync_popup()

    def _on_lyrics_loaded(self, hits: list[Hit], track: TrackInfo | None):
        self._hits = hits
        self._hit_index = 0
        if hits and len(hits) > 0:
            self._active_lyrics = hits[0].lyrics
            if getattr(self.config.popup, "romanize", True):
                try:
                    from core.widgets.services.lyrics.romanize import romanize_lyrics

                    for h in hits:
                        romanize_lyrics(h.lyrics, target_scripts=None)
                except Exception as e:
                    logger.debug("Failed to romanize lyrics: %s", e)

            has_synced = any(h.lyrics.synced() if callable(h.lyrics.synced) else h.lyrics.synced for h in hits)
            self._current_state = "synced" if has_synced else "plain"
            total_dur = track.duration_ms if (track and track.duration_ms) else 0
            if not total_dur and hits[0].duration_s and hits[0].duration_s > 0:
                total_dur = int(hits[0].duration_s * 1000)
            elif not total_dur and self._active_lyrics:
                span = self._active_lyrics.span_ms()
                if span and span > 0:
                    total_dur = span

            if total_dur:
                if track and not track.duration_ms:
                    track.duration_ms = total_dur
                if self._current_track and not self._current_track.duration_ms:
                    self._current_track.duration_ms = total_dur

            self._engine.set_lyrics(self._active_lyrics, total_duration_ms=total_dur)
        else:
            self._active_lyrics = None
            self._current_state = "not-found"
            self._engine.set_lyrics(None)

        self._update_tooltip()
        self._sync_popup()

    def _on_state_changed(self, state: str):
        self._current_state = state
        self._sync_popup()

    def _animate_visibility(self, visible: bool):
        if self._target_visible == visible:
            return

        self._target_visible = visible

        target_width = self.config.fixed_width or (self._label.sizeHint().width() if self._label else 280)
        target_width = max(target_width, 60)

        if visible:
            start_w = 0 if self.isHidden() else max(0, self.width())
            self.show()
            end_w = target_width
            start_op = self._opacity_effect.opacity()
            end_op = 1.0
        else:
            start_w = max(0, self.width())
            end_w = 0
            start_op = self._opacity_effect.opacity()
            end_op = 0.0

        if self._width_anim and self._width_anim.state() == QPropertyAnimation.State.Running:
            self._width_anim.stop()
        if self._opacity_anim and self._opacity_anim.state() == QPropertyAnimation.State.Running:
            self._opacity_anim.stop()

        self.setMinimumWidth(0)
        self._widget_frame.setMinimumWidth(0)
        if self._label:
            self._label.setMinimumWidth(0)

        self._width_anim = QPropertyAnimation(self, b"anim_width", self)
        self._width_anim.setDuration(300)
        self._width_anim.setStartValue(start_w)
        self._width_anim.setEndValue(end_w)
        self._width_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._opacity_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._opacity_anim.setDuration(300)
        self._opacity_anim.setStartValue(start_op)
        self._opacity_anim.setEndValue(end_op)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _on_finish():
            try:
                if not self._target_visible:
                    self.hide()
                    self.setFixedWidth(0)
                    self._cur_anim_width = 0
                else:
                    if self.config.fixed_width:
                        self.setFixedWidth(self.config.fixed_width)
                        self._cur_anim_width = self.config.fixed_width
                    else:
                        self.setMinimumWidth(0)
                        self.setMaximumWidth(16777215)
            except Exception:
                pass

        self._width_anim.finished.connect(_on_finish)
        self._width_anim.start()
        self._opacity_anim.start()

    def _on_tick(self):
        status = self._engine.tick()

        mode = self._get_visualizer_mode()
        should_hide = False

        if (
            not self._current_track
            or (self._last_playback and self._last_playback.status in ("stopped", "closed"))
            or self._current_state == "idle"
        ):
            should_hide = True
            self._paused_since = None
        elif self._last_playback and self._last_playback.status == "paused":
            cfg_paused = self.config.hide_when_paused
            if cfg_paused is not False:
                delay = 5.0 if isinstance(cfg_paused, bool) else float(cfg_paused)
                if self._paused_since is None:
                    self._paused_since = time.monotonic()
                if time.monotonic() - self._paused_since >= delay:
                    should_hide = True
            else:
                self._paused_since = None
        else:
            self._paused_since = None

        if not should_hide and self._current_state == "searching":
            should_hide = True
        elif not should_hide and self._current_state in ("not-found", "failed"):
            if mode == "none" or self.config.hide_when_no_lyrics:
                should_hide = True

        if should_hide:
            if self._audio_stream:
                self._audio_stream.pause()
            self._animate_visibility(False)
            return
        else:
            if self._audio_stream:
                self._audio_stream.resume()
            self._animate_visibility(True)

        self._update_status_display(status)

    def _update_status_display(self, status: SyncStatus):
        if not self._current_track:
            self._set_label_text("", state_class="idle")
            return

        if self._current_state == "searching":
            placeholder = getattr(self.config, "label_placeholder", None)
            self._set_label_text(placeholder or "", state_class="searching")
            return

        if self._current_state in ("not-found", "failed"):
            dur = self._current_track.duration_ms if (self._current_track and self._current_track.duration_ms) else 0
            prog = max(0.0, min(1.0, status.effective_position_ms / dur)) if dur > 0 else 0.0
            state_class = f"break instrumental {self._current_state}"
            if self._last_playback and self._last_playback.status == "paused":
                state_class += " paused"
            self._display_break_or_prelude(progress=prog, state_class=state_class)
            return

        if status.is_break:
            state_class = "break instrumental"
            if self._last_playback and self._last_playback.status == "paused":
                state_class = "break instrumental paused"

            self._display_break_or_prelude(progress=status.break_progress, state_class=state_class)
            return

        if status.active_line is not None:
            state_class = "synced"
            if self._last_playback and self._last_playback.status == "paused":
                state_class = "synced paused"

            line = status.active_line
            main_text, karaoke_words, sec_text, sec_words = self._build_display_karaoke(line)
            combined_text = f"{main_text} {sec_text}" if sec_text else main_text

            if self._audio_stream:
                self._label.set_bass_energy(self._audio_stream.get_bass_energy())

            if karaoke_words or sec_words:
                self._label.set_karaoke_data(
                    text=combined_text,
                    words=karaoke_words,
                    position_ms=status.effective_position_ms,
                    is_active=True,
                    prefix="",
                    suffix="",
                    state="active",
                    secondary_text=sec_text,
                    secondary_words=sec_words,
                )
                self._apply_widget_classes(state_class)
                return
            else:
                rendered = self._apply_template(combined_text)
                start_ms = line.start_ms
                if line.end_ms is not None and line.end_ms > line.start_ms:
                    duration_ms = line.end_ms - line.start_ms
                elif self._active_lyrics and self._active_lyrics.lines:
                    try:
                        idx = self._active_lyrics.lines.index(line)
                        if idx + 1 < len(self._active_lyrics.lines):
                            duration_ms = max(500, self._active_lyrics.lines[idx + 1].start_ms - line.start_ms)
                        else:
                            duration_ms = 4000
                    except ValueError, IndexError:
                        duration_ms = 4000
                else:
                    duration_ms = 4000

                self._label.set_line_synced_data(
                    text=rendered,
                    start_ms=start_ms,
                    duration_ms=duration_ms,
                    position_ms=status.effective_position_ms,
                    state=state_class,
                )
                self._apply_widget_classes(state_class)
                return

        is_synced = False
        if self._active_lyrics is not None:
            synced_attr = self._active_lyrics.synced
            is_synced = synced_attr() if callable(synced_attr) else bool(synced_attr)
        if self._active_lyrics and is_synced:
            state_class = "synced"
            if self._last_playback and self._last_playback.status == "paused":
                state_class = "synced paused"

            prelude_prog = 0.0
            if self._active_lyrics.lines:
                first_start = self._active_lyrics.lines[0].start_ms
                if first_start > 0 and status.effective_position_ms < first_start:
                    prelude_prog = max(0.0, min(1.0, status.effective_position_ms / max(1, first_start)))
            self._display_break_or_prelude(progress=prelude_prog, state_class=state_class)
            return

        if self._active_lyrics and self._active_lyrics.plain:
            first_line = self._active_lyrics.plain.strip().splitlines()[0] if self._active_lyrics.plain.strip() else ""
            if getattr(self.config, "romanize_replace", False):
                try:
                    from core.widgets.services.lyrics.romanize import romanize_text

                    rom_first = romanize_text(first_line)
                    if rom_first:
                        first_line = rom_first
                except Exception:
                    pass
            rendered = self._apply_template(first_line)
            self._set_label_text(rendered, state_class="plain")
            return

        dur = self._current_track.duration_ms if (self._current_track and self._current_track.duration_ms) else 0
        prog = max(0.0, min(1.0, status.effective_position_ms / dur)) if dur > 0 else 0.0
        state_class = "break instrumental not-found"
        if self._last_playback and self._last_playback.status == "paused":
            state_class += " paused"
        self._display_break_or_prelude(progress=prog, state_class=state_class)

    def _set_label_text(self, text: str, state_class: str):
        self._label.set_plain_text(text, state=state_class)
        self._apply_widget_classes(state_class)

    def _apply_widget_classes(self, state_class: str):
        target_class = f"widget lyrics-widget {state_class}".strip()
        if self._widget_frame.property("class") != target_class:
            self._widget_frame.setProperty("class", target_class)
            self._label.setProperty("class", f"label {state_class}".strip())
            refresh_widget_style(self._widget_frame, self._label)

    def _apply_template(self, lyric_text: str, romanized: str | None = None) -> str:
        rendered = lyric_text
        if self.config.max_width:
            if len(rendered) > self.config.max_width:
                rendered = rendered[: self.config.max_width - 3] + "..."

        return rendered

    @staticmethod
    def _get_yasb_accent_palette(widget: QWidget | None = None) -> tuple[QColor, QColor]:
        theme_data = resolve_yasb_theme_data(widget)
        accent = theme_data.get("accent")
        secondary = theme_data.get("secondary")
        if accent and accent.isValid() and secondary and secondary.isValid():
            return accent, secondary
        p = accent if (accent and accent.isValid()) else QColor(208, 171, 249)
        hsv_primary = QtGui.QColor.getHsv(p)
        h, s, v = (hsv_primary[0] or 0, hsv_primary[1] or 0, hsv_primary[2] or 0) if hsv_primary else (0, 0, 0)
        hsv_sec = QColor.fromHsv(h, max(30, int(s * 0.7)), max(30, int(v * 0.6)))
        return p, QColor(hsv_sec.red(), hsv_sec.green(), hsv_sec.blue())

    @staticmethod
    def _format_limited_names(names: list[str] | str | None, max_count: int = 3) -> str:
        if not names:
            return ""
        if isinstance(names, str):
            parts = [p.strip() for p in re.split(r"[,;/]+", names) if p.strip()]
        else:
            parts = [str(p).strip() for p in names if str(p).strip()]
        if len(parts) <= max_count:
            return ", ".join(parts)
        return f"{', '.join(parts[:max_count])}, ..."

    def _update_tooltip(self):
        if not self._current_track:
            set_tooltip(self._widget_container, "")
            return

        artist_display = self._format_limited_names(self._current_track.artist, max_count=3)
        lines = [f"{self._current_track.title} - {artist_display}"]

        if self._hits and len(self._hits) > self._hit_index:
            hit = self._hits[self._hit_index]
            lines.append(f"Source: {hit.source}")
            if hit.writers:
                w_str = self._format_limited_names(hit.writers, max_count=3)
                lines.append(f"Artists: {w_str}")
            if len(self._hits) > 1:
                lines.append(f"Result {self._hit_index + 1} of {len(self._hits)} (Right-click to cycle)")

        if self._is_audio_reactive_enabled():
            vis_status = "Connected" if (self._audio_stream and self._audio_stream.is_running) else "Offline"
            lines.append(f"Audio Visualizer: {vis_status}")

        set_tooltip(self._widget_container, "\n".join(lines))

    def _toggle_label(self):
        self._show_alt_label = not getattr(self, "_show_alt_label", False)
        if self._show_alt_label and self._current_track:
            self._set_label_text(f"{self._current_track.artist} - {self._current_track.title}", state_class="idle")
        else:
            self._on_tick()

    def _toggle_popup(self):
        if self._popup is not None and self._popup.isVisible():
            self._popup.hide_animated()
            return

        if self._popup is None:
            self._popup = LyricsPopup(self, self.config)
            self._popup.seek_requested.connect(self._on_popup_seek_requested)
            self._popup.cycle_hit_requested.connect(self._cycle_next_hit)
            self._popup.retry_requested.connect(self._retry_fetch)
            self._popup.play_pause_requested.connect(self._media.play_pause)
            self._popup.prev_requested.connect(self._media.prev)
            self._popup.next_requested.connect(self._media.next)

        self._sync_popup()
        if getattr(self.config, "accent", "album_art") == "yasb":
            p_col, s_col = self._get_yasb_accent_palette(self)
            self._popup.set_palette_colors(p_col, s_col)
        off_h = self.config.popup.offset_left
        off_v = self.config.popup.offset_top
        self._popup.setPosition(
            alignment=self.config.popup.alignment,
            direction=self.config.popup.direction,
            offset_left=off_h,
            offset_top=off_v,
        )
        self._popup.show()
        if hasattr(self, "clear_hover_state"):
            self.clear_hover_state()

    def _sync_popup(self):
        if self._popup is not None:
            self._popup.sync_data(
                track=self._current_track,
                hits=self._hits,
                hit_index=self._hit_index,
                active_lyrics=self._active_lyrics,
                engine=self._engine,
                state=self._current_state,
            )

    @asyncSlot(int)
    async def _on_popup_seek_requested(self, position_ms: int):
        await self._media.seek_to_position(position_ms / 1000.0)
        if self._last_playback:
            self._last_playback = PlaybackSnapshot(
                position_ms=position_ms,
                rate=self._last_playback.rate,
                status=self._last_playback.status,
                wall_time=time.time(),
                can_seek=self._last_playback.can_seek,
            )
            self._engine.update_snapshot(self._last_playback)

    def _retry_fetch(self):
        if self._current_track:
            self._current_state = "searching"
            self._sync_popup()
            self._worker.request(self._current_track)

    def _cycle_next_hit(self):
        if len(self._hits) <= 1:
            return
        self._hit_index = (self._hit_index + 1) % len(self._hits)
        hit = self._hits[self._hit_index]
        self._active_lyrics = hit.lyrics
        total_dur = self._current_track.duration_ms if (self._current_track and self._current_track.duration_ms) else 0
        if not total_dur and hit.duration_s and hit.duration_s > 0:
            total_dur = int(hit.duration_s * 1000)
        elif not total_dur and self._active_lyrics:
            span = self._active_lyrics.span_ms()
            if span and span > 0:
                total_dur = span
        if total_dur and self._current_track and not self._current_track.duration_ms:
            self._current_track.duration_ms = total_dur
        self._engine.set_lyrics(self._active_lyrics, total_duration_ms=total_dur)
        self._update_tooltip()
        self._sync_popup()
        self._on_tick()

    def _copy_current_lyrics(self):
        status = self._engine.tick()
        clip = QApplication.clipboard()
        if clip and status.active_line:
            clip.setText(status.active_line.text)

    def _show_context_menu(self):
        menu = QMenu(self)

        if len(self._hits) > 1:
            action_cycle = _add_action(menu, f"Next Lyric Match ({self._hit_index + 1}/{len(self._hits)})")
            action_cycle.triggered.connect(self._cycle_next_hit)
            menu.addSeparator()

        status = self._engine.tick()
        if status.active_line:
            action_copy = _add_action(menu, "Copy Current Line")
            action_copy.triggered.connect(self._copy_current_lyrics)

        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def stop(self):
        try:
            atexit.unregister(self.stop)
        except Exception:
            pass
        if getattr(self, "_audio_stream", None) is not None:
            stream = self._audio_stream
            assert stream is not None
            try:
                stream.stop()
            except Exception:
                pass
            self._audio_stream = None
        if hasattr(self, "_tick_timer"):
            try:
                if self._tick_timer.isActive():
                    self._tick_timer.stop()
            except RuntimeError, Exception:
                pass
        if hasattr(self, "_worker"):
            try:
                if self._worker.isRunning():
                    self._worker.stop()
            except RuntimeError, Exception:
                pass
        if hasattr(self, "_media"):
            try:
                self._media.media_data_changed.disconnect(self._on_media_data_changed)
                self._media.current_session_changed.disconnect(self._on_media_state_dirty)
                self._media.media_properties_changed.disconnect(self._on_media_state_dirty)
                self._media.timeline_info_changed.disconnect(self._on_media_state_dirty)
                self._media.playback_info_changed.disconnect(self._on_media_state_dirty)
            except TypeError, RuntimeError:
                pass
        if getattr(self, "_popup", None) is not None:
            popup = self._popup
            assert popup is not None
            try:
                popup.hide()
                popup.close()
            except RuntimeError, Exception:
                pass

    @override
    def closeEvent(self, a0: Any) -> None:
        self.stop()
        super().closeEvent(a0)
