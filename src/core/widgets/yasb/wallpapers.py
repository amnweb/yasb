from PyQt6.QtWidgets import QApplication

from core.utils.tooltip import set_tooltip
from core.utils.win32.utils import find_focused_screen
from core.validation.widgets.yasb.wallpapers import WallpapersConfig
from core.widgets.base import BaseWidget
from core.widgets.services.wallpapers.gallery import TYPES
from core.widgets.services.wallpapers.manager import WallpaperManager


class WallpapersWidget(BaseWidget):
    validation_schema = WallpapersConfig

    def __init__(self, config: WallpapersConfig):
        super().__init__(0, class_name="wallpapers-widget")
        self.config = config
        self._image_gallery = None
        self._manager = WallpaperManager()
        self._manager.configure(
            self.config.image_path,
            self.config.update_interval,
            self.config.change_automatically,
            self.config.run_after,
            self.config.engine,
        )

        self._manager.toggle_gallery_signal.connect(self._on_toggle_gallery_request)

        self._init_container()
        self.build_widget_label(self.config.label, None)

        if self.config.tooltip:
            set_tooltip(self, "Change Wallpaper")

        self.register_callback("toggle_gallery", self._toggle_widget)
        self.register_callback("change_wallpaper", self._manager.change_background)

        self.callback_left = self.config.callbacks.on_left
        self.callback_middle = self.config.callbacks.on_middle
        self.callback_right = self.config.callbacks.on_right

    def _on_toggle_gallery_request(self, screen: str):
        current_screen = self.window().screen() if self.window() else None
        current_screen_name = current_screen.name() if current_screen else None

        if not screen or (current_screen_name and screen.lower() == current_screen_name.lower()):
            self._toggle_widget()

    def _target_screen(self):
        """The screen the gallery should open on, per the keybinding."""
        mode = "active"
        for binding in self.config.keybindings:
            if binding.action == "toggle_gallery":
                mode = binding.screen
                break

        if mode == "primary":
            return QApplication.primaryScreen()
        # Unrestricted on purpose: the hotkey layer only considers bar screens.
        name = find_focused_screen(follow_mouse=mode == "cursor", follow_window=mode == "active")
        for screen in QApplication.screens():
            if screen.name() == name:
                return screen
        return None

    def _toggle_widget(self):

        if self._image_gallery is not None and self._image_gallery.isVisible():
            self._image_gallery.fade_out_and_close_gallery()
        else:
            gallery_type = TYPES[self.config.gallery.type]
            self._image_gallery = gallery_type(
                self.config.image_path,
                self.config.gallery.model_dump(),
            )
            self._image_gallery.fade_in_gallery(parent=self, screen=self._target_screen())
