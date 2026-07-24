import ctypes
import logging
import os
from collections.abc import Callable
from typing import Any, cast

from PIL import Image, ImageFilter
from PIL.ImageQt import ImageQt
from pycaw.pycaw import AudioUtilities
from PyQt6 import QtCore
from PyQt6.QtCore import QEvent, QObject, QPoint, QRectF, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QMouseEvent, QPainter, QPainterPath, QPaintEvent, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from qasync import asyncSlot  # type: ignore

from core.utils.qobject import is_valid_qobject
from core.utils.tooltip import set_tooltip
from core.utils.utilities import ElidedLabel, PopupWidget, ScrollingLabel, refresh_widget_style
from core.utils.win32.app_icons import get_icon_for_aumid, get_process_icon
from core.utils.win32.aumid import (
    ERROR_INSUFFICIENT_BUFFER,
    PROCESS_QUERY_LIMITED_INFORMATION,
    CloseHandle,
    GetApplicationUserModelId,
    OpenProcess,
    activate_app_by_aumid,
)
from core.validation.widgets.yasb.media_lite import MediaLiteWidgetConfig
from core.widgets.base import BaseWidget
from core.widgets.services.media.aumid_process import (
    get_pid_for_window_aumid,
    get_process_name_for_aumid,
)
from core.widgets.services.media.media import SessionState, WindowsMedia
from core.widgets.services.media.source_apps import resolve_source_app_name
from settings import SCRIPT_PATH

logger = logging.getLogger("MediaLiteWidget")

MAX_TIMELINE_DURATION = 604800  # 7 days
SOURCE_ICON_SIZE = 16
_SCROLL_OPTIONS = {
    "update_interval_ms": 33,
    "style": "left",
    "always_scroll": True,
    "separator": " ",
}
_SCROLL_JOIN = " - "


class MediaWidget(BaseWidget):
    validation_schema = MediaLiteWidgetConfig

    def __init__(self, config: MediaLiteWidgetConfig):
        super().__init__(class_name=f"media-lite-widget {config.class_name}".strip())
        self.config = config

        self._init_container()
        self.hide()

        self.media = WindowsMedia()
        self.current_session: SessionState | None = None
        self.dialog: PopupWidget | None = None
        self._seeking = False
        self._empty_thumb_cache: dict[tuple[int, float], QPixmap] = {}
        self._source_icon_cache: dict[tuple[str, float], QPixmap] = {}
        self._default_source_icon: dict[float, QPixmap] = {}
        self._app_volume_session = None
        self._app_is_muted = False

        # Bar layout: thumb + title/artist
        self._bar_thumb = RoundedClickableLabel(self, radius=self.config.thumbnail_corner_radius)
        self._bar_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bar_thumb.setProperty("class", "thumbnail")
        self._bar_thumb.setFixedSize(self.config.image_size, self.config.image_size)
        self._bar_thumb.data = self._toggle_media_menu

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        text_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # scrolling_label: one line. Otherwise optional title + artist on two lines.
        self._bar_scroll_label: ScrollingLabel | None = None
        self._title_label: QLabel | None = None
        self._artist_label: QLabel | None = None
        scrolling = self.config.scrolling_label and (self.config.show_title or self.config.show_artist)

        if scrolling:
            max_width = self.config.max_label_size if self.config.max_label_size > 0 else None
            self._bar_scroll_label = ScrollingLabel(self, max_width=max_width, options=_SCROLL_OPTIONS)
            self._bar_scroll_label.setProperty("class", "label")
            self._bar_scroll_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            text_col.addWidget(self._bar_scroll_label)
        else:
            self._title_label = QLabel("")
            self._title_label.setProperty("class", "title")
            self._title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            self._artist_label = QLabel("")
            self._artist_label.setProperty("class", "artist")
            self._artist_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            text_col.addWidget(self._title_label)
            text_col.addWidget(self._artist_label)
            if not self.config.show_title:
                self._title_label.hide()
            if not self.config.show_artist:
                self._artist_label.hide()

        if self.config.show_thumbnail:
            self._widget_container_layout.addWidget(self._bar_thumb)
        else:
            self._bar_thumb.hide()

        self._text_col_widget = QFrame()
        self._text_col_widget.setProperty("class", "text")
        self._text_col_widget.setLayout(text_col)
        self._widget_container_layout.addWidget(self._text_col_widget)

        if not self.config.show_title and not self.config.show_artist:
            self._text_col_widget.hide()

        self.media.media_data_changed.connect(self._on_media_data_changed)
        self.media.current_session_changed.connect(self._on_session_status_changed)
        self.media.media_properties_changed.connect(self._on_media_properties_changed)
        self.media.timeline_info_changed.connect(self._on_timeline_properties_changed)
        self.media.playback_info_changed.connect(self._on_playback_info_changed)

        self._bar_hide_timer = QTimer(self)
        self._bar_hide_timer.setSingleShot(True)
        self._bar_hide_timer.setInterval(1000)
        self._bar_hide_timer.timeout.connect(self._hide_bar_now)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle
        self.register_callback("toggle_media_menu", self._toggle_media_menu)
        self.register_callback("toggle_play_pause", self._toggle_play_pause)
        self.register_callback("open_media_source", self._open_media_source)

    @pyqtSlot(dict)
    def _on_media_data_changed(self, data: dict[str, SessionState]):
        old = self.current_session
        self.current_session = next((s for s in data.values() if s.is_current), None)
        self._update_interpolated_position()

        if self.current_session is None:
            return
        if old is not None and old.app_id == self.current_session.app_id:
            return

        self._on_media_properties_changed()
        if self._popup_open():
            self._sync_popup_session()

    @QtCore.pyqtSlot()
    def _on_session_status_changed(self):
        if self.current_session is not None:
            self._bar_hide_timer.stop()
            self.show()
            if self.config.show_thumbnail:
                self._bar_thumb.show()
            if self.config.show_title or self.config.show_artist:
                self._text_col_widget.show()
            return
        if self.isVisible() and not self._bar_hide_timer.isActive():
            self._bar_hide_timer.start()

    def _hide_bar_now(self) -> None:
        if self.current_session is not None or not self.isVisible():
            return
        self.hide()
        if self._bar_scroll_label is not None:
            self._bar_scroll_label.setText("")
        if self._title_label is not None:
            self._title_label.setText("")
        if self._artist_label is not None:
            self._artist_label.setText("")

    @pyqtSlot()
    def _on_media_properties_changed(self):
        session = self.current_session
        if session is None:
            return
        self._apply_bar_text(session)
        self._apply_artwork(session)
        if self._popup_open():
            self._apply_popup_text(session)

    def _on_playback_info_changed(self):
        session = self.current_session
        if session is None or not session.playback_ready or not self._popup_open():
            return
        self._apply_transport(session)

    def _on_timeline_properties_changed(self):
        session = self.current_session
        if session is None or not self._popup_open():
            return
        self._apply_timeline(session)

    def _popup_open(self) -> bool:
        return bool(is_valid_qobject(self.dialog) and self.dialog.isVisible())

    def _toggle_media_menu(self):
        if self._popup_open():
            if is_valid_qobject(self.dialog):
                self.dialog.hide_animated()
        else:
            self.show_menu()

    def show_menu(self):
        if self.current_session is None:
            return
        if not is_valid_qobject(self.dialog):
            self._create_media_popup()
        if not is_valid_qobject(self.dialog):
            return
        self._refresh_popup()
        self.dialog.setPosition(
            alignment=self.config.media_menu.alignment,
            direction=self.config.media_menu.direction,
            offset_left=self.config.media_menu.offset_left,
            offset_top=self.config.media_menu.offset_top,
        )
        self.dialog.show()
        self._update_artwork_background()

    def _create_media_popup(self):
        menu = self.config.media_menu
        self.dialog = PopupWidget(
            self,
            menu.blur,
            menu.round_corners,
            menu.round_corners_type,
            menu.border_color,
            persistent=True,
        )
        self.dialog.setProperty("class", "media-lite-menu")

        outer = QGridLayout(self.dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._artwork_bg_label = QLabel(self.dialog)
        self._artwork_bg_label.setProperty("class", "artwork-background")
        self._artwork_bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._artwork_bg_label.setScaledContents(True)
        self._artwork_bg_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._artwork_bg_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._artwork_bg_label.hide()
        outer.addWidget(self._artwork_bg_label, 0, 0)

        stack_frame = QFrame(self.dialog)
        stack_frame.setFrameShape(QFrame.Shape.NoFrame)
        stack_frame.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        stack_frame.setAutoFillBackground(False)
        main_layout = QVBoxLayout(stack_frame)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header_frame = QFrame()
        header_frame.setProperty("class", "header")
        header = QHBoxLayout(header_frame)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)

        self._volume_hover = VolumeHoverWidget(self)
        header.addWidget(self._volume_hover, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        header.addStretch(1)

        self._popup_source_label = ClickableLabel(self)
        self._popup_source_label.setProperty("class", "source")
        self._popup_source_label.setFixedSize(SOURCE_ICON_SIZE, SOURCE_ICON_SIZE)
        self._popup_source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._popup_source_label.data = self._open_media_source
        header.addWidget(self._popup_source_label, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(header_frame, 0, Qt.AlignmentFlag.AlignTop)

        self._popup_thumbnail_label = RoundedClickableLabel(self, radius=menu.thumbnail_corner_radius)
        self._popup_thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._popup_thumbnail_label.setProperty("class", "thumbnail")
        self._popup_thumbnail_label.data = self._open_media_source
        self._popup_thumbnail_label.setFixedSize(menu.image_size, menu.image_size)
        main_layout.addWidget(self._popup_thumbnail_label, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        controls_frame = QFrame()
        controls_frame.setProperty("class", "controls")
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(0)

        self._popup_title_label = ElidedLabel("")
        self._popup_title_label.setProperty("class", "title")
        self._popup_title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self._popup_artist_label = ElidedLabel("")
        self._popup_artist_label.setProperty("class", "artist")
        self._popup_artist_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        controls_layout.addWidget(self._popup_title_label, 0, Qt.AlignmentFlag.AlignTop)
        controls_layout.addWidget(self._popup_artist_label, 0, Qt.AlignmentFlag.AlignTop)
        controls_layout.addStretch(1)

        self._time_slider_container = QFrame()
        self._time_slider_container.setProperty("class", "media-timeline-container")
        time_slider_layout = QVBoxLayout(self._time_slider_container)
        time_slider_layout.setContentsMargins(0, 0, 0, 0)
        time_slider_layout.setSpacing(0)

        time_labels_layout = QHBoxLayout()
        time_labels_layout.setContentsMargins(0, 0, 0, 0)
        time_labels_layout.setSpacing(0)

        self._popup_current_time_label = QLabel("00:00")
        self._popup_current_time_label.setProperty("class", "playback-time current")
        self._popup_current_time_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._popup_total_time_label = QLabel("00:00")
        self._popup_total_time_label.setProperty("class", "playback-time total")
        self._popup_total_time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        time_labels_layout.addWidget(self._popup_current_time_label)
        time_labels_layout.addStretch(1)
        time_labels_layout.addWidget(self._popup_total_time_label)

        self._progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._progress_slider.setProperty("class", "progress-slider")
        self._progress_slider.setMinimum(0)
        self._progress_slider.setMaximum(1000)
        self._progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self._progress_slider.sliderReleased.connect(self._on_slider_released)
        self._progress_slider.valueChanged.connect(self._on_slider_value_changed)

        time_slider_layout.addWidget(self._progress_slider)
        time_slider_layout.addLayout(time_labels_layout)
        controls_layout.addWidget(self._time_slider_container)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(0)
        control_layout.setContentsMargins(0, 0, 0, 0)

        icons = menu.icons
        self._popup_shuffle_label = self._make_btn("btn shuffle", icons.shuffle, self.media.toggle_shuffle, "Shuffle")
        self._popup_prev_label = self._make_btn("btn prev", icons.prev_track, self.media.prev, "Previous")
        self._popup_play_button = self._make_btn("btn play", icons.play, self.media.play_pause, "Play")
        self._popup_next_label = self._make_btn("btn next", icons.next_track, self.media.next, "Next")
        self._popup_repeat_label = self._make_btn("btn repeat", icons.repeat, self.media.cycle_repeat, "Repeat")

        control_layout.addStretch(1)
        control_layout.addWidget(self._popup_shuffle_label)
        control_layout.addWidget(self._popup_prev_label)
        control_layout.addWidget(self._popup_play_button)
        control_layout.addWidget(self._popup_next_label)
        control_layout.addWidget(self._popup_repeat_label)
        control_layout.addStretch(1)
        controls_layout.addLayout(control_layout)

        main_layout.addWidget(controls_frame)
        outer.addWidget(stack_frame, 0, 0)

        self._wheel_filter = WheelEventFilter(self)
        self.dialog.installEventFilter(self._wheel_filter)
        self.dialog.installEventFilter(ArtworkResizeFilter(self))

    def _set_tip(self, widget: QWidget | None, text: str) -> None:
        if not self.config.tooltip or widget is None or not text:
            return
        set_tooltip(widget, text)

    def _update_bar_tooltip(self, session: SessionState) -> None:
        title = (session.title or "").strip() or "Unknown Title"
        artist = (session.artist or "").strip()
        source = resolve_source_app_name(session.app_id) or ""
        tip = [f"<strong>{title}</strong>"]
        if artist:
            tip.append(artist)
        if source:
            tip.append(f"<br>{source}")
        self._set_tip(self, "<br>".join(tip))

    def _make_btn(self, class_name: str, text: str, action: Callable[..., Any], tip: str) -> ClickableLabel:
        btn = ClickableLabel(self)
        btn.setProperty("class", class_name)
        btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn.setText(text)
        btn.data = action
        self._set_tip(btn, tip)
        return btn

    def _refresh_popup(self):
        session = self.current_session
        if not is_valid_qobject(self.dialog) or session is None:
            return
        self._apply_popup_text(session)
        self._apply_artwork(session)
        self._sync_popup_session()

    def _sync_popup_session(self):
        """Volume / source / timeline / transport for the current session."""
        session = self.current_session
        if session is None or not is_valid_qobject(self.dialog):
            return
        self._bind_app_volume_session()
        self._apply_source_icon(session)
        self._apply_timeline(session)
        self._update_app_volume_slider()
        self._update_volume_icon()
        if session.playback_ready:
            self._apply_transport(session)

    def _apply_bar_text(self, session: SessionState) -> None:
        self._update_bar_tooltip(session)
        if not self.config.show_title and not self.config.show_artist:
            return
        title = (session.title or "").strip()
        artist = (session.artist or "").strip()
        if self._bar_scroll_label is not None:
            self._bar_scroll_label.setText(self._bar_scroll_text(title, artist))
            self._bar_scroll_label.setVisible(True)
            return
        if self._title_label is None or self._artist_label is None:
            return
        if self.config.show_title:
            self._title_label.setText(self._format_max_field_size(title) if title else "Unknown Title")
            self._title_label.setVisible(True)
        if self.config.show_artist:
            if artist:
                self._artist_label.setText(self._format_max_field_size(artist))
                self._artist_label.setVisible(True)
            else:
                self._artist_label.clear()
                self._artist_label.setVisible(False)

    def _bar_scroll_text(self, title: str, artist: str) -> str:
        """One scrolling line: title, artist, or 'title - artist' when both enabled."""
        parts: list[str] = []
        if self.config.show_title:
            parts.append(title or "Unknown Title")
        if self.config.show_artist:
            if artist:
                parts.append(artist)
            elif not self.config.show_title:
                parts.append("Unknown Artist")
        return _SCROLL_JOIN.join(parts)

    def _apply_popup_text(self, session: SessionState) -> None:
        if not is_valid_qobject(self.dialog):
            return
        title = (session.title or "").strip()
        artist = (session.artist or "").strip()
        self._popup_title_label.setText(title or "Unknown Title")
        self._popup_artist_label.setText(artist or "Unknown Artist")

    def _apply_artwork(self, session: SessionState) -> None:
        cover = session.thumbnail
        if self.config.show_thumbnail:
            try:
                self._bar_thumb.setPixmap(self._pixmap_from_cover(cover, self.config.image_size))
                self._bar_thumb.show()
            except Exception as e:
                logger.error("Error setting bar thumbnail: %s", e)
        if is_valid_qobject(self.dialog):
            self._popup_thumbnail_label.setPixmap(self._pixmap_from_cover(cover, self.config.media_menu.image_size))
        if self._popup_open():
            self._update_artwork_background()

    def _apply_transport(self, session: SessionState) -> None:
        if not is_valid_qobject(self.dialog):
            return
        icons = self.config.media_menu.icons
        playing = session.is_playing

        self._popup_play_button.setText(icons.pause if playing else icons.play)
        self._popup_play_button.setProperty(
            "class", f"btn play{' disabled' if not session.controls_play_enabled else ''}"
        )
        refresh_widget_style(self._popup_play_button)
        self._set_tip(self._popup_play_button, "Pause" if playing else "Play")

        self._popup_prev_label.setProperty(
            "class", f"btn prev{' disabled' if not session.controls_prev_enabled else ''}"
        )
        refresh_widget_style(self._popup_prev_label)
        self._popup_next_label.setProperty(
            "class", f"btn next{' disabled' if not session.controls_next_enabled else ''}"
        )
        refresh_widget_style(self._popup_next_label)

        shuffle_cls = "btn shuffle"
        if not session.controls_shuffle_enabled:
            shuffle_cls += " disabled"
        elif session.is_shuffle_active:
            shuffle_cls += " active"
        self._popup_shuffle_label.setText(icons.shuffle)
        self._popup_shuffle_label.setProperty("class", shuffle_cls)
        refresh_widget_style(self._popup_shuffle_label)
        self._set_tip(
            self._popup_shuffle_label,
            "Shuffle on" if session.controls_shuffle_enabled and session.is_shuffle_active else "Shuffle",
        )

        repeat_cls = "btn repeat"
        mode = session.auto_repeat_mode
        if not session.controls_repeat_enabled:
            repeat_cls += " disabled"
            icon = icons.repeat
            tip = "Repeat"
        elif mode == 1:
            repeat_cls += " active"
            icon = icons.repeat_one
            tip = "Repeat one"
        elif mode == 2:
            repeat_cls += " active"
            icon = icons.repeat
            tip = "Repeat all"
        else:
            icon = icons.repeat
            tip = "Repeat off"
        self._popup_repeat_label.setText(icon)
        self._popup_repeat_label.setProperty("class", repeat_cls)
        refresh_widget_style(self._popup_repeat_label)
        self._set_tip(self._popup_repeat_label, tip)

    def _apply_timeline(self, session: SessionState) -> None:
        if not is_valid_qobject(self.dialog):
            return
        duration = session.duration
        position = session.current_pos
        usable = bool(session.timeline_enabled and 0 < duration < MAX_TIMELINE_DURATION)

        self._popup_current_time_label.setText(self._format_time(min(position, duration)) if usable else "00:00")
        self._popup_total_time_label.setText(self._format_time(duration) if usable else "00:00")
        if usable:
            self._progress_slider.setEnabled(True)
            self._progress_slider.setValue(min(1000, int((min(position, duration) / duration) * 1000)))
        else:
            self._progress_slider.blockSignals(True)
            self._progress_slider.setValue(0)
            self._progress_slider.blockSignals(False)
            self._progress_slider.setEnabled(False)

    def _apply_source_icon(self, session: SessionState) -> None:
        if not is_valid_qobject(self._popup_source_label):
            return
        pixmap = self._get_source_app_icon(session.app_id)
        name = None
        try:
            name = resolve_source_app_name(session.app_id)
        except Exception:
            pass
        if pixmap is not None:
            self._popup_source_label.setPixmap(pixmap)
            self._popup_source_label.setText("")
        else:
            fallback = self._default_source_icon_pixmap()
            if fallback is not None:
                self._popup_source_label.setPixmap(fallback)
            else:
                self._popup_source_label.clear()
        if name:
            self._set_tip(self._popup_source_label, name)
        self._popup_source_label.show()

    def _dpr(self) -> float:
        screen = self.screen()
        if screen is None and is_valid_qobject(self.dialog):
            screen = self.dialog.screen()
        return float(screen.devicePixelRatio()) if screen is not None else 1.0

    def _update_artwork_background(self):
        if not is_valid_qobject(self._artwork_bg_label) or not is_valid_qobject(self.dialog):
            return
        menu = self.config.media_menu
        bg_img = self.current_session.thumbnail if self.current_session is not None else None
        if not menu.artwork_background or bg_img is None:
            self._artwork_bg_label.hide()
            return
        try:
            dpr = self._dpr()
            size = self.dialog.size()
            w, h = max(1, size.width()), max(1, size.height())
            pw, ph = max(1, int(round(w * dpr))), max(1, int(round(h * dpr)))
            img = bg_img.convert("RGBA")
            aspect = img.width / img.height if img.height else 1.0
            target_aspect = pw / ph
            if aspect > target_aspect:
                new_h, new_w = ph, int(ph * aspect)
            else:
                new_w = pw
                new_h = int(pw / aspect) if aspect else ph
            resized = img.resize((max(1, new_w), max(1, new_h)), Image.LANCZOS)
            left = (resized.width - pw) // 2
            top = (resized.height - ph) // 2
            cropped = resized.crop((left, top, left + pw, top + ph))
            if menu.artwork_blur_radius > 0:
                radius = max(1, int(round(menu.artwork_blur_radius * dpr)))
                cropped = cropped.filter(ImageFilter.GaussianBlur(radius=radius))
            opacity = max(0.0, min(1.0, 1.0 - menu.artwork_dim))
            if opacity <= 0:
                self._artwork_bg_label.hide()
                return
            if opacity < 1.0:
                alpha = cropped.getchannel("A")
                alpha = alpha.point(lambda a: int(a * opacity))
                cropped.putalpha(alpha)
            pix = QPixmap.fromImage(ImageQt(cropped).copy())
            pix.setDevicePixelRatio(dpr)
            self._artwork_bg_label.setPixmap(pix)
            self._artwork_bg_label.show()
        except Exception as e:
            logger.error("Error updating artwork background: %s", e)
            self._artwork_bg_label.hide()

    def _get_source_app_icon(self, aumid: str) -> QPixmap | None:
        if not aumid:
            return None
        dpr = self._dpr()
        cached = self._source_icon_cache.get((aumid, dpr))
        if cached is not None:
            return cached
        try:
            phys = max(1, int(round(SOURCE_ICON_SIZE * dpr)))
            img = get_icon_for_aumid(aumid, size=phys)
            if img is None:
                pid = get_pid_for_window_aumid(aumid)
                if not pid and self._app_volume_session is not None:
                    proc = getattr(self._app_volume_session, "Process", None)
                    if proc is not None:
                        pid = getattr(proc, "pid", None)
                if not pid:
                    exe = get_process_name_for_aumid(aumid)
                    if exe:
                        pid = self._find_pid_by_executable(exe)
                if pid:
                    img = get_process_icon(int(pid))
            if img is None:
                return None
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            if img.size != (phys, phys):
                img = img.resize((phys, phys), Image.LANCZOS)
            pixmap = self._pil_to_pixmap(img, dpr)
            self._source_icon_cache[(aumid, dpr)] = pixmap
            return pixmap
        except Exception:
            logger.exception("Error getting source app icon")
            return None

    @staticmethod
    def _pil_to_pixmap(img: Image.Image, dpr: float = 1.0) -> QPixmap:
        # Avoid a dangling view into PIL's buffer.
        pixmap = QPixmap.fromImage(ImageQt(img).copy())
        pixmap.setDevicePixelRatio(dpr)
        return pixmap

    def _find_pid_by_executable(self, exe_name: str) -> int | None:
        target = exe_name.lower()
        try:
            for session in AudioUtilities.GetAllSessions():
                proc = getattr(session, "Process", None)
                if not proc:
                    continue
                try:
                    if proc.name().lower() == target:
                        return int(proc.pid)
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _pixmap_from_cover(self, cover: Image.Image | None, square_size: int) -> QPixmap:
        if cover is not None:
            pix = self._create_square_thumbnail(cover, square_size)
            if pix is not None and not pix.isNull():
                return pix
        return self._default_thumbnail_pixmap(square_size) or QPixmap()

    def _default_thumbnail_pixmap(self, square_size: int) -> QPixmap | None:
        dpr = self._dpr()
        cached = self._empty_thumb_cache.get((square_size, dpr))
        if cached is not None:
            return cached
        try:
            icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "media.png")
            if not os.path.exists(icon_path):
                return None
            phys = max(1, int(round(square_size * dpr)))
            with Image.open(icon_path) as image:
                if image.mode != "RGBA":
                    image = image.convert("RGBA")
                resized = image.resize((phys, phys), Image.LANCZOS)
                pixmap = self._pil_to_pixmap(resized, dpr)
            self._empty_thumb_cache[(square_size, dpr)] = pixmap
            return pixmap
        except Exception as e:
            logger.error("Error creating default thumbnail: %s", e)
            return None

    def _default_source_icon_pixmap(self) -> QPixmap | None:
        dpr = self._dpr()
        cached = self._default_source_icon.get(dpr)
        if cached is not None:
            return cached
        try:
            icon_path = os.path.join(SCRIPT_PATH, "assets", "images", "app_icon.png")
            if not os.path.exists(icon_path):
                return None
            phys = max(1, int(round(SOURCE_ICON_SIZE * dpr)))
            with Image.open(icon_path) as image:
                if image.mode != "RGBA":
                    image = image.convert("RGBA")
                resized = image.resize((phys, phys), Image.LANCZOS)
                pixmap = self._pil_to_pixmap(resized, dpr)
            self._default_source_icon[dpr] = pixmap
            return pixmap
        except Exception as e:
            logger.error("Error creating default source icon: %s", e)
            return None

    def _create_square_thumbnail(self, img: Image.Image, square_size: int) -> QPixmap | None:
        try:
            dpr = self._dpr()
            phys = max(1, int(round(square_size * dpr)))
            aspect = img.width / img.height if img.height else 1.0
            if aspect > 1:
                new_height = phys
                new_width = int(phys * aspect)
            else:
                new_width = phys
                new_height = int(phys / aspect) if aspect else phys
            resized = img.resize((max(1, new_width), max(1, new_height)), Image.LANCZOS)
            if resized.width >= phys and resized.height >= phys:
                left = (resized.width - phys) // 2
                top = (resized.height - phys) // 2
                square_img = resized.crop((left, top, left + phys, top + phys))
            else:
                square_img = resized.resize((phys, phys), Image.LANCZOS)
            if square_img.mode != "RGBA":
                square_img = square_img.convert("RGBA")
            return self._pil_to_pixmap(square_img, dpr)
        except Exception as e:
            logger.error("Error creating square thumbnail: %s", e)
            return None

    def _format_time(self, seconds: float) -> str:
        minutes, seconds_i = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds_i:02d}"
        return f"{minutes:01d}:{seconds_i:02d}"

    def _format_max_field_size(self, text: str) -> str:
        max_size = self.config.max_label_size
        if max_size > 0 and len(text) > max_size:
            return text[: max_size - 3] + "..." if max_size > 3 else text[:max_size]
        return text

    def _toggle_play_pause(self):
        self.media.play_pause()

    def _open_media_source(self):
        if self.current_session and self.current_session.app_id:
            aumid = self.current_session.app_id
            activate_app_by_aumid(aumid, fallback_process_name=get_process_name_for_aumid(aumid))

    def execute_code(self, func: Callable[..., Any]):
        try:
            func()
        except Exception as e:
            logger.error("Error executing code: %s", e)

    def wheelEvent(self, a0: QWheelEvent | None):
        if a0 is None:
            return
        if a0.angleDelta().y() > 0:
            self.media.switch_current_session(+1)
        elif a0.angleDelta().y() < 0:
            self.media.switch_current_session(-1)

    def _update_interpolated_position(self):
        session = self.current_session
        if session is None or self._seeking or not self._popup_open():
            return
        try:
            duration = session.duration
            if not (session.timeline_enabled and 0 < duration < MAX_TIMELINE_DURATION):
                return
            position = min(session.current_pos, duration)
            if is_valid_qobject(self._popup_current_time_label):
                self._popup_current_time_label.setText(self._format_time(position))
            if is_valid_qobject(self._progress_slider):
                new_percent = min(1000, int((position / duration) * 1000))
                if abs(new_percent - self._progress_slider.value()) >= 5:
                    self._progress_slider.setValue(new_percent)
        except RuntimeError:
            pass
        except Exception as e:
            logger.error("Error updating interpolated position: %s", e)

    def _on_slider_pressed(self):
        self._seeking = True

    @asyncSlot()
    async def _on_slider_released(self):
        try:
            if not is_valid_qobject(self.dialog):
                return
            value = self._progress_slider.value()
            if self.current_session and self.current_session.duration > 0:
                try:
                    await self.media.seek_to_position((value / 1000.0) * self.current_session.duration)
                except Exception as e:
                    logger.error("Error seeking: %s", e)
        finally:
            self._seeking = False

    def _on_slider_value_changed(self, value: int):
        if not self._seeking or not self.current_session or self.current_session.duration <= 0:
            return
        if is_valid_qobject(self._popup_current_time_label):
            self._popup_current_time_label.setText(self._format_time((value / 1000.0) * self.current_session.duration))

    def _get_process_aumid(self, pid: int) -> str | None:
        if GetApplicationUserModelId is None:
            return None
        try:
            h_process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not h_process:
                return None
            try:
                length = ctypes.c_uint32(0)
                if GetApplicationUserModelId(h_process, ctypes.byref(length), None) == ERROR_INSUFFICIENT_BUFFER:
                    buf = ctypes.create_unicode_buffer(length.value)
                    if GetApplicationUserModelId(h_process, ctypes.byref(length), buf) == 0:
                        return buf.value
            finally:
                CloseHandle(h_process)
        except Exception:
            pass
        return None

    def _bind_app_volume_session(self):
        self._app_volume_session = None
        aumid = self.current_session.app_id if self.current_session else None
        if not aumid:
            return
        try:
            sessions = list(AudioUtilities.GetAllSessions())
            target = aumid.lower()
            for session in sessions:
                try:
                    proc = getattr(session, "Process", None)
                    if proc and proc.pid:
                        process_aumid = self._get_process_aumid(int(proc.pid))
                        if process_aumid and process_aumid.lower() == target:
                            self._app_volume_session = session
                            return
                except Exception:
                    continue
            if aumid.lower().endswith(".exe"):
                exe = aumid.lower()
            else:
                proc_name = get_process_name_for_aumid(aumid)
                exe = proc_name.lower() if proc_name else ""
            if not exe.endswith(".exe"):
                return
            for session in sessions:
                try:
                    proc = getattr(session, "Process", None)
                    if proc and proc.name().lower() == exe:
                        self._app_volume_session = session
                        return
                except Exception:
                    continue
        except Exception as e:
            logger.error("Failed to bind app volume session: %s", e)

    def _get_volume_interface(self):
        if not self._app_volume_session:
            return None
        return getattr(self._app_volume_session, "SimpleAudioVolume", None)

    def _volume_available(self) -> bool:
        return self._get_volume_interface() is not None

    def _update_app_volume_slider(self):
        if not is_valid_qobject(self.dialog):
            return
        volume_interface = self._get_volume_interface()
        if volume_interface is None:
            self._volume_hover.hide_slider()
            self.app_volume_slider.setEnabled(False)
            self._update_volume_icon()
            return
        try:
            level = int(round(float(volume_interface.GetMasterVolume()) * 100))
            self.app_volume_slider.blockSignals(True)
            self.app_volume_slider.setValue(level)
            self.app_volume_slider.blockSignals(False)
            self.app_volume_slider.setEnabled(True)
        except Exception as e:
            logger.error("Failed to read app volume: %s", e)
            self.app_volume_slider.setEnabled(False)

    def _on_app_volume_slider_changed(self, value: int):
        volume_interface = self._get_volume_interface()
        if not volume_interface:
            return
        try:
            volume_interface.SetMasterVolume(float(value) / 100.0, None)
            if value > 0 and self._app_is_muted:
                self._app_is_muted = False
                self._update_volume_icon()
        except Exception as e:
            logger.error("Failed to set app volume: %s", e)

    def _adjust_volume_by_delta(self, delta: int):
        if not is_valid_qobject(self.dialog) or not self._get_volume_interface():
            return
        self.app_volume_slider.setValue(max(0, min(100, self.app_volume_slider.value() + delta)))

    def _toggle_app_mute(self):
        volume_interface = self._get_volume_interface()
        if not volume_interface:
            return
        try:
            try:
                current_mute = bool(volume_interface.GetMute())
            except Exception:
                current_mute = False
            volume_interface.SetMute(not current_mute, None)
            self._app_is_muted = not current_mute
            self._update_volume_icon()
        except Exception as e:
            logger.error("Failed to toggle app mute: %s", e)

    def _update_volume_icon(self):
        if not is_valid_qobject(self._volume_icon):
            return
        icons = self.config.media_menu.icons
        volume_interface = self._get_volume_interface()
        if not volume_interface:
            self._volume_icon.setText(icons.volume)
            self._volume_icon.setProperty("class", "volume-button unavailable")
            refresh_widget_style(self._volume_icon)
            if is_valid_qobject(self._volume_hover):
                self._set_tip(self._volume_hover, "Volume unavailable")
                self._volume_hover.setCursor(Qt.CursorShape.ArrowCursor)
            return
        try:
            is_muted = bool(volume_interface.GetMute())
            self._app_is_muted = is_muted
            self._volume_icon.setText(icons.mute if is_muted else icons.volume)
            self._volume_icon.setProperty("class", "volume-button muted" if is_muted else "volume-button")
            refresh_widget_style(self._volume_icon)
            if is_valid_qobject(self._volume_hover):
                self._set_tip(self._volume_hover, "Unmute" if is_muted else "Mute")
                self._volume_hover.setCursor(Qt.CursorShape.PointingHandCursor)
        except Exception as e:
            logger.error("Failed to update volume icon: %s", e)


class ClickableLabel(QLabel):
    def __init__(self, parent: MediaWidget | None = None):
        super().__init__(parent)
        self.parent_widget: MediaWidget | None = parent
        self.data: Callable[..., Any] | None = None

    def mousePressEvent(self, ev: QMouseEvent | None):
        if ev is not None:
            ev.accept()

    def mouseReleaseEvent(self, ev: QMouseEvent | None):
        if ev is None:
            return
        classes = (self.property("class") or "").split()
        if "disabled" in classes:
            ev.accept()
            return
        if ev.button() == Qt.MouseButton.LeftButton and self.data and self.parent_widget:
            self.parent_widget.execute_code(self.data)
        ev.accept()


class RoundedClickableLabel(ClickableLabel):
    def __init__(self, parent: MediaWidget | None = None, radius: int = 0):
        super().__init__(parent)
        self._corner_radius = max(0, radius)

    def paintEvent(self, a0: QPaintEvent | None):
        pix = self.pixmap()
        if pix is None or pix.isNull() or self._corner_radius <= 0:
            super().paintEvent(a0)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.contentsRect())
        radius = min(float(self._corner_radius), min(rect.width(), rect.height()) / 2.0)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)
        # Logical size; pixmap already has devicePixelRatio set.
        painter.drawPixmap(self.contentsRect(), pix)
        painter.end()


class VolumeHoverWidget(QFrame):
    def __init__(self, media_widget: MediaWidget):
        super().__init__(media_widget.dialog if media_widget.dialog else media_widget)
        self.media_widget = media_widget
        self.setProperty("class", "volume-hover")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._icon = QLabel(self)
        self._icon.setProperty("class", "volume-button")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setText(media_widget.config.media_menu.icons.volume)
        layout.addWidget(self._icon)
        media_widget._volume_icon = self._icon
        media_widget._set_tip(self, "Mute")

        self._slider_popup = QFrame(media_widget.dialog)
        self._slider_popup.setProperty("class", "volume-slider-popup")
        self._slider_popup.hide()

        popup_layout = QVBoxLayout(self._slider_popup)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.setSpacing(0)

        slider = QSlider(Qt.Orientation.Vertical)
        slider.setProperty("class", "volume-slider")
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.valueChanged.connect(media_widget._on_app_volume_slider_changed)
        popup_layout.addWidget(slider, 0, Qt.AlignmentFlag.AlignCenter)
        media_widget.app_volume_slider = slider

        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.setInterval(150)
        self._show_timer.timeout.connect(self._show_slider)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(350)
        self._hide_timer.timeout.connect(self.hide_slider)
        self._slider_popup.installEventFilter(self)

    def enterEvent(self, event: QEvent | None):
        if self.media_widget._volume_available():
            self._hide_timer.stop()
            self._show_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent | None):
        self._show_timer.stop()
        self._hide_timer.start()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, a0: QMouseEvent | None):
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton and self.media_widget._volume_available():
            self.media_widget._toggle_app_mute()
            a0.accept()
            return
        super().mouseReleaseEvent(a0)

    def wheelEvent(self, a0: QWheelEvent | None):
        if a0 is None:
            return
        if not self.media_widget._volume_available():
            a0.ignore()
            return
        self.media_widget._adjust_volume_by_delta(5 if a0.angleDelta().y() > 0 else -5)
        a0.accept()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        if obj is self._slider_popup:
            if event.type() == QEvent.Type.Enter:
                self._hide_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                self._hide_timer.start()
        return super().eventFilter(obj, event)

    def _show_slider(self):
        if not self.media_widget._volume_available():
            return
        if not is_valid_qobject(self._slider_popup) or not is_valid_qobject(self.media_widget.dialog):
            return
        dialog = self.media_widget.dialog
        self._slider_popup.adjustSize()
        icon_pos = self._icon.mapTo(dialog, QPoint(0, self._icon.height()))
        x = icon_pos.x() + (self._icon.width() - self._slider_popup.width()) // 2
        self._slider_popup.move(max(0, x), icon_pos.y())
        self._slider_popup.show()
        self._slider_popup.raise_()

    def hide_slider(self):
        if is_valid_qobject(self._slider_popup):
            self._slider_popup.hide()


class ArtworkResizeFilter(QObject):
    def __init__(self, parent: MediaWidget):
        super().__init__(parent)
        self.media_widget = parent

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        if event.type() == QEvent.Type.Resize and obj is self.media_widget.dialog:
            self.media_widget._update_artwork_background()
        return False


class WheelEventFilter(QObject):
    def __init__(self, parent: MediaWidget):
        super().__init__(parent)
        self.media_widget = parent

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        if event.type() != QEvent.Type.Wheel:
            return False
        event = cast(QWheelEvent, event)
        dialog = self.media_widget.dialog
        if not is_valid_qobject(dialog) or not dialog.geometry().contains(event.globalPosition().toPoint()):
            return False

        hover = self.media_widget._volume_hover
        if is_valid_qobject(hover):
            hover_rect = QtCore.QRect(hover.mapToGlobal(QPoint(0, 0)), hover.size())
            if hover_rect.contains(event.globalPosition().toPoint()):
                return False
            if is_valid_qobject(hover._slider_popup) and hover._slider_popup.isVisible():
                slider_rect = QtCore.QRect(
                    hover._slider_popup.mapToGlobal(QPoint(0, 0)),
                    hover._slider_popup.size(),
                )
                if slider_rect.contains(event.globalPosition().toPoint()):
                    return False

        if event.angleDelta().y() > 0:
            self.media_widget.media.switch_current_session(+1)
        elif event.angleDelta().y() < 0:
            self.media_widget.media.switch_current_session(-1)
        return True
