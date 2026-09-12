import json
import logging
import os
import struct
import subprocess
from typing import Any

from PyQt6.QtCore import QObject, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QIcon, QMouseEvent, QMovie
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.validation.widgets.yasb.gif_player import GifPlayerConfig
from core.widgets.base import BaseWidget

logger = logging.getLogger(__name__)

try:
    from core.utils.utilities import PopupWidget
except ImportError:
    PopupWidget = None

try:
    from core.utils.tooltip import set_tooltip
except ImportError:

    def set_tooltip(widget: QWidget, text: str):
        widget.setToolTip(text)


def get_gif_dimensions(path: str) -> tuple[int, int]:
    """Reads native GIF resolution from the 10-byte header with sub-millisecond speed."""
    if not path or not os.path.isfile(path):
        return 1, 1
    try:
        with open(path, "rb") as f:
            head = f.read(10)
            if len(head) >= 10 and head[:3] == b"GIF":
                w, h = struct.unpack("<HH", head[6:10])
                if w > 0 and h > 0:
                    return w, h
    except (OSError, struct.error) as e:
        logger.debug("Failed to read GIF dimensions from %s: %s", path, e)
    return 1, 1


class GifSignalBus(QObject):
    """Global event bus to synchronize all live GifPlayerWidget instances sharing the same ID."""

    gif_changed = pyqtSignal(str, str)  # (instance_id, new_gif_path)


_gif_signal_bus = GifSignalBus()


def get_state_file_path() -> str:
    """Returns the persistent state JSON file path in YASB AppData."""
    local_app_data = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
    yasb_dir = os.path.join(local_app_data, "YASB")
    os.makedirs(yasb_dir, exist_ok=True)
    return os.path.join(yasb_dir, "gif_widget_state.json")


def load_saved_gif(instance_id: str) -> str | None:
    """Loads the last selected GIF path for a specific widget instance."""
    state_file = get_state_file_path()
    if os.path.isfile(state_file):
        try:
            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
                return data.get(instance_id)
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Failed to load saved GIF for %s: %s", instance_id, e)
    return None


def save_selected_gif(instance_id: str, gif_path: str):
    """Saves the currently selected GIF path for a specific widget instance."""
    state_file = get_state_file_path()
    data = {}
    if os.path.isfile(state_file):
        try:
            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
        except OSError:
            data = {}
        except json.JSONDecodeError:
            data = {}
    data[instance_id] = gif_path
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        logger.warning("GifPlayerWidget: Failed to save state: %s", e)


class GifPlayerWidget(BaseWidget):
    """
    High-performance, ultra-low CPU/GPU animated GIF player widget for YASB.
    Accurately scales non-square GIFs without edge clipping or distortion.
    Includes an interactive popup grid to preview and switch between animations.
    """

    validation_schema = GifPlayerConfig

    def __init__(self, config: GifPlayerConfig):
        # Support dict fallback if instantiated directly
        if isinstance(config, dict):
            config = GifPlayerConfig.model_validate(config)

        super().__init__(class_name=config.class_name)
        self.config = config

        # Standard container initialization
        self._init_container()

        # Instance sync identifier
        if self.config.id:
            self.instance_id = str(self.config.id)
        elif self.config.class_name and self.config.class_name != "gif-widget":
            self.instance_id = f"gif_{self.config.class_name}"
        else:
            self.instance_id = "primary_gif"

        # Resolve gif_folder
        self.gif_folder = self.config.gif_folder
        if not self.gif_folder or not os.path.isdir(self.gif_folder):
            if self.config.gif_path and os.path.isfile(self.config.gif_path):
                self.gif_folder = os.path.dirname(os.path.abspath(self.config.gif_path))
            else:
                user_icons = os.path.expanduser("~/.config/yasb/icons/gifs")
                if os.path.isdir(user_icons):
                    self.gif_folder = user_icons
                else:
                    self.gif_folder = os.path.dirname(os.path.abspath(__file__))

        # Resolve initial GIF path: persistent state > config.gif_path > bundled sample
        saved = load_saved_gif(self.instance_id)
        if saved and os.path.isfile(saved):
            self.current_gif_path = saved
        elif self.config.gif_path and os.path.isfile(self.config.gif_path):
            self.current_gif_path = self.config.gif_path
        else:
            available = self._get_available_gifs()
            if available:
                self.current_gif_path = available[0]
            else:
                self.current_gif_path = os.path.join(os.path.dirname(__file__), "parrot.gif")

        # Label & Movie components
        self.label = QLabel(self)
        self.label.setProperty("class", "gif-icon")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._widget_container_layout.addWidget(self.label)

        self.movie: QMovie | None = None
        self._load_and_play_gif(self.current_gif_path)

        # Connect global bus for multi-bar synchronisation
        _gif_signal_bus.gif_changed.connect(self._on_global_gif_changed)

        # Active popup and preview movie tracking
        self._menu: Any = None
        self._popup_movies: list[QMovie] = []

        # Register callbacks
        self.register_callback("toggle_popup", self.toggle_popup)
        self.register_callback("show_menu", self.toggle_popup)
        self.register_callback("toggle_animation", self.toggle_animation)
        self.register_callback("do_nothing", lambda: None)

        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle

    def _on_global_gif_changed(self, changed_id: str, new_path: str):
        """Immediately synchronizes when another widget instance with the same ID changes its GIF."""
        if changed_id == self.instance_id and self.current_gif_path != new_path:
            self.set_gif(new_path, broadcast=False)

    def _get_available_gifs(self) -> list[str]:
        """Scans the configured folder and returns valid .gif file paths."""
        if not self.gif_folder or not os.path.isdir(self.gif_folder):
            return []
        try:
            files = [
                os.path.join(self.gif_folder, f)
                for f in os.listdir(self.gif_folder)
                if f.lower().endswith(".gif") and os.path.isfile(os.path.join(self.gif_folder, f))
            ]
            files.sort(key=lambda x: os.path.basename(x).lower())
            return files
        except OSError as e:
            logger.warning("GifPlayerWidget: Error scanning folder: %s", e)
            return []

    def _load_and_play_gif(self, path: str):
        """Loads and starts a GIF animation, calculating proportional dimensions."""
        if self.movie:
            try:
                self.movie.stop()
                self.movie.deleteLater()
            except RuntimeError:
                pass
            self.movie = None

        if not path or not os.path.isfile(path):
            self.label.setText("?")
            return

        self.current_gif_path = path

        # Fast proportional aspect-ratio calculation
        native_w, native_h = get_gif_dimensions(path)
        aspect = native_w / max(1, native_h)
        target_h = self.config.icon_size
        target_w = max(1, round(target_h * aspect))

        self.movie = QMovie(path)
        self.movie.setScaledSize(QSize(target_w, target_h))
        if self.config.speed_percent != 100:
            self.movie.setSpeed(self.config.speed_percent)

        self.label.setMovie(self.movie)
        self.label.setFixedSize(target_w, target_h)
        self.movie.start()

        # Tooltip formatting
        if self.config.tooltip:
            gif_name = os.path.splitext(os.path.basename(path))[0]
            tip_text = self.config.tooltip_text.format(
                name=gif_name,
                width=native_w,
                height=native_h,
            )
            set_tooltip(self.label, tip_text)

    def set_gif(self, path: str, broadcast: bool = True):
        """Switches the active animation, saves state, and synchronizes peer instances."""
        if not path or not os.path.isfile(path):
            return
        self._load_and_play_gif(path)
        save_selected_gif(self.instance_id, path)
        if broadcast:
            _gif_signal_bus.gif_changed.emit(self.instance_id, path)

    def toggle_animation(self):
        """Pauses or resumes the status bar GIF animation."""
        if self.movie:
            if self.movie.state() == QMovie.MovieState.Running:
                self.movie.setPaused(True)
            else:
                self.movie.setPaused(False)

    def _cleanup_popup_movies(self):
        """Stops and frees all popup QMovie instances immediately."""
        for m in self._popup_movies:
            try:
                m.stop()
                m.deleteLater()
            except RuntimeError:
                pass
        self._popup_movies.clear()

    def toggle_popup(self):
        """Opens or toggles the grid popup displaying all GIFs."""
        try:
            if self._menu and self._menu.isVisible():
                self._menu.hide()
                return

            icons_per_row = self.config.popup.icons_per_row or self.config.icons_per_row

            # Build PopupWidget
            if PopupWidget:
                menu = PopupWidget(
                    self,
                    blur=self.config.popup.blur,
                    round_corners=self.config.popup.round_corners,
                    round_corners_type=self.config.popup.round_corners_type,
                    border_color=self.config.popup.border_color,
                    persistent=False,
                )
            else:
                menu = QWidget(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)

            menu.setProperty("class", "gif-popup")
            self._menu = menu

            main_layout = QVBoxLayout(menu)
            main_layout.setContentsMargins(6, 6, 6, 6)
            main_layout.setSpacing(4)

            container = QWidget()
            container.setProperty("class", "gif-popup-container")
            grid = QGridLayout(container)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(4)

            self._cleanup_popup_movies()

            gifs = self._get_available_gifs()
            current_norm = os.path.normpath(self.current_gif_path).lower() if self.current_gif_path else ""

            row, col = 0, 0
            for gif_path in gifs:
                btn = QPushButton()
                btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                is_active = os.path.normpath(gif_path).lower() == current_norm
                btn.setProperty("class", "button active" if is_active else "button")
                btn.setFixedSize(40, 40)

                btn_layout = QHBoxLayout(btn)
                btn_layout.setContentsMargins(2, 2, 2, 2)
                btn_layout.setSpacing(0)

                lbl = QLabel()
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

                # Scaled preview movie
                gw, gh = get_gif_dimensions(gif_path)
                aspect = gw / max(1, gh)
                if aspect >= 1:
                    pw, ph = 32, max(8, round(32 / aspect))
                else:
                    ph, pw = 32, max(8, round(32 * aspect))

                movie = QMovie(gif_path)
                movie.setScaledSize(QSize(pw, ph))
                lbl.setMovie(movie)
                movie.start()
                self._popup_movies.append(movie)

                btn_layout.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)

                gif_name = os.path.splitext(os.path.basename(gif_path))[0]
                if self.config.tooltip:
                    set_tooltip(btn, gif_name)

                # Selection callback
                def make_select_handler(path_to_set=gif_path):
                    def handler():
                        self.set_gif(path_to_set)
                        menu.close()

                    return handler

                btn.clicked.connect(make_select_handler())
                grid.addWidget(btn, row, col)

                col += 1
                if col >= icons_per_row:
                    col = 0
                    row += 1

            # "Open Folder" tile
            folder_btn = QPushButton()
            folder_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            folder_btn.setProperty("class", "button folder-tile")
            folder_btn.setFixedSize(40, 40)
            if self.config.tooltip:
                set_tooltip(folder_btn, "Open GIF folder")

            folder_layout = QHBoxLayout(folder_btn)
            folder_layout.setContentsMargins(2, 2, 2, 2)
            folder_layout.setSpacing(0)

            folder_icon_path = self.config.folder_icon
            if folder_icon_path and os.path.isfile(folder_icon_path):
                folder_lbl = QLabel()
                folder_lbl.setPixmap(QIcon(folder_icon_path).pixmap(QSize(22, 22)))
                folder_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                folder_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                folder_layout.addWidget(folder_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
            else:
                folder_lbl = QLabel("\ue8b7")  # Explorer icon glyph
                folder_lbl.setProperty("class", "folder-icon")
                folder_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                folder_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                folder_layout.addWidget(folder_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

            def open_folder():
                try:
                    if os.path.isdir(self.gif_folder):
                        os.startfile(self.gif_folder)
                    else:
                        subprocess.Popen(["explorer", "/select,", self.current_gif_path])
                except OSError as e:
                    logger.warning("GifPlayerWidget: Failed to open folder: %s", e)
                menu.close()

            folder_btn.clicked.connect(open_folder)
            grid.addWidget(folder_btn, row, col)

            main_layout.addWidget(container)

            # Cleanup movies on dismiss
            if hasattr(menu, "hideEvent"):
                orig_hide = menu.hideEvent

                def on_hide(event):
                    self._cleanup_popup_movies()
                    orig_hide(event)

                menu.hideEvent = on_hide

            menu.adjustSize()

            # Positioning
            if hasattr(menu, "setPosition"):
                menu.setPosition(
                    alignment=self.config.popup.alignment,
                    direction=self.config.popup.direction,
                    offset_left=self.config.popup.offset_left,
                    offset_top=self.config.popup.offset_top,
                )
            else:
                # Fallback manual positioning
                global_pos = self.mapToGlobal(QPoint(0, 0))
                widget_rect = self.rect()
                menu_size = menu.sizeHint()
                x = global_pos.x() + (widget_rect.width() - menu_size.width()) // 2 + self.config.popup.offset_left
                y = global_pos.y() + widget_rect.height() + self.config.popup.offset_top
                menu.move(x, y)

            menu.show()

        except (RuntimeError, OSError, TypeError) as e:
            logger.error("GifPlayerWidget: Failed to open popup: %s", e)

    def contextMenuEvent(self, event: Any):
        event.accept()
        self.toggle_popup()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            cb = getattr(self, "callback_right", "toggle_popup")
            if cb and cb in self.callbacks:
                self.callbacks[cb]()
        elif event.button() == Qt.MouseButton.LeftButton:
            cb = getattr(self, "callback_left", None)
            if cb and cb in self.callbacks:
                self.callbacks[cb]()
        elif event.button() == Qt.MouseButton.MiddleButton:
            cb = getattr(self, "callback_middle", None)
            if cb and cb in self.callbacks:
                self.callbacks[cb]()
        super().mouseReleaseEvent(event)


class GifWidget(GifPlayerWidget):
    """Backward compatibility alias for GifPlayerWidget."""

    pass
