import logging
from typing import override

from pycaw.api.audioclient import ISimpleAudioVolume
from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from core.bar_helper import GlobalState
from core.utils.icons.service import IconService, ProcessIcon
from core.utils.utilities import ElidedLabel, refresh_widget_style
from core.utils.win32.utils import apply_qmenu_style, get_app_name_from_pid
from core.widgets.services.volume.service import AudioOutputService

APP_ICON_SIZE = 16
# Segoe Fluent Icons "Speakers"
SYSTEM_SOUNDS_ICON = ""


def _format_session_name(name: str) -> str:
    return name.removesuffix(".exe").replace(".", " ").title()


class _AppVolumeRow(QFrame):
    """One app: icon (click to mute), name, volume slider and value."""

    def __init__(self, parent: QWidget, name: str, volume: ISimpleAudioVolume, pid: int | None, glyph: str = ""):
        super().__init__(parent)
        self._volume = volume
        self._pid = pid
        self._glyph = glyph
        self._muted = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._icon = QLabel(self)
        self._icon.setProperty("class", "app-icon system" if glyph else "app-icon")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon.installEventFilter(self)
        layout.addWidget(self._icon)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(0)
        name_label = ElidedLabel(name, self)
        name_label.setProperty("class", "app-name")
        info.addWidget(name_label)

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setProperty("class", "slider-control")
        self._slider.setRange(0, 100)
        try:
            self._slider.setValue(round(volume.GetMasterVolume() * 100))
        except Exception:
            self._slider.setValue(100)
        self._slider.valueChanged.connect(self._on_slider_changed)
        info.addWidget(self._slider)
        layout.addLayout(info, 1)

        self._value = QLabel(f"{self._slider.value()}%", self)
        self._value.setProperty("class", "value")
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._value)

        try:
            self._set_muted(bool(volume.GetMute()))
        except Exception:
            self._set_muted(False)
        if pid is not None:
            IconService.instance().icons_changed.connect(self._update_icon)

    def _update_icon(self) -> None:
        if self._glyph:
            self._icon.setText(self._glyph)
            return
        if self._pid is None:
            return
        pixmap = IconService.instance().get_icon(
            ProcessIcon(self._pid), APP_ICON_SIZE, self.devicePixelRatioF(), grayscale=self._muted
        )
        if pixmap is not None:
            self._icon.setPixmap(pixmap)

    def _set_muted(self, muted: bool) -> None:
        self._muted = muted
        self.setProperty("class", "app-volume muted" if muted else "app-volume")
        # Children too: `.app-volume.muted .app-name` etc. depend on the row's class.
        refresh_widget_style(self, *self.findChildren(QWidget))
        self._update_icon()

    def _on_slider_changed(self, value: int) -> None:
        try:
            self._volume.SetMasterVolume(value / 100, None)
            # Dragging a muted app's slider unmutes it, like the main volume slider.
            if value > 0 and self._muted:
                self._volume.SetMute(False, None)
                self._set_muted(False)
        except Exception as e:
            logging.error("Failed to set application volume: %s", e)
        self._value.setText(f"{value}%")

    def _toggle_mute(self) -> None:
        try:
            self._volume.SetMute(not self._muted, None)
            self._set_muted(not self._muted)
        except Exception as e:
            logging.error("Failed to toggle application mute: %s", e)

    @override
    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if (
            a0 is self._icon
            and isinstance(a1, QMouseEvent)
            and a1.type() == QEvent.Type.MouseButtonRelease
            and a1.button() == Qt.MouseButton.LeftButton
        ):
            self._toggle_mute()
            return True
        return super().eventFilter(a0, a1)


class AppMixerMenu(QMenu):
    """Scrollable dropdown with System sounds and a volume slider for every app playing audio.

    The menu is `width` wide and grows with the number of apps until it is
    `max_height` tall, after which the list scrolls.
    """

    def __init__(self, parent: QWidget, output_service: AudioOutputService, width: int, max_height: int):
        super().__init__(parent)
        # A new menu is built on every open; drop the old one (and its icon updates) when it closes.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        apply_qmenu_style(self)
        self.setProperty("class", "context-menu app-mixer dark" if GlobalState.is_dark() else "context-menu app-mixer")

        self._container = QFrame()
        self._container.setProperty("class", "app-mixer-list")
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        scroll = QScrollArea(self._container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; border-radius: 0; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical { border: none; background: transparent; width: 4px; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        container_layout.addWidget(scroll)

        self._content = QWidget(scroll)
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        system_sounds = output_service.get_system_sounds_volume()
        if system_sounds is not None:
            content_layout.addWidget(
                _AppVolumeRow(self._content, "System sounds", system_sounds, None, SYSTEM_SOUNDS_ICON)
            )
        for session in output_service.get_active_audio_sessions(
            get_app_name_callback=get_app_name_from_pid,
            format_name_callback=_format_session_name,
        ):
            content_layout.addWidget(
                _AppVolumeRow(self._content, session["app_name"], session["volume_interface"], session["pid"])
            )
        if content_layout.count() == 0:
            empty = QLabel("No apps are playing audio", self._content)
            empty.setProperty("class", "empty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            content_layout.addWidget(empty)
        scroll.setWidget(self._content)

        self._action = QWidgetAction(self)
        self._action.setDefaultWidget(self._container)
        self._fit(width, max_height)

    def _fit(self, width: int, max_height: int) -> None:
        # Adding the action parents the list to the menu, which is when the
        # `.control-center-menu .app-mixer ...` rules (row padding etc.) start
        # to apply, so measure after it. The rows are still hidden, so their
        # layout has to be told to recompute.
        self.addAction(self._action)
        content_layout = self._content.layout()
        if content_layout is None:
            return
        content_layout.invalidate()
        content_height = self._content.sizeHint().height()

        # Measure the menu's own border/padding with a trial size, then size the
        # list so the whole menu is `width` wide and at most `max_height` tall.
        self._resize_list(width, content_height)
        hint = self.sizeHint()
        chrome_w = hint.width() - width
        chrome_h = hint.height() - content_height

        first_item = content_layout.itemAt(0)
        first_row = first_item.sizeHint().height() if first_item is not None else 0
        self._resize_list(width - chrome_w, max(min(content_height, max_height - chrome_h), first_row))

    def _resize_list(self, width: int, height: int) -> None:
        self._container.setFixedSize(max(width, 1), max(height, 1))
        # Re-add the action so QMenu recomputes its geometry with the new size.
        self.removeAction(self._action)
        self.addAction(self._action)
