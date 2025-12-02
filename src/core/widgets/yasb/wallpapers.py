from PyQt6.QtWidgets import QFrame, QHBoxLayout

from core.utils.tooltip import set_tooltip
from core.utils.utilities import add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.wallpapers.wallpaper_manager import WallpaperManager
from core.utils.widgets.wallpapers.wallpapers_gallery import ImageGallery
from core.validation.widgets.yasb.wallpapers import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class WallpapersWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        update_interval: int,
        change_automatically: bool,
        image_path: str,
        tooltip: bool,
        animation: dict[str, str],
        run_after: list[str],
        container_padding: dict[str, int],
        gallery: dict = None,
        label_shadow: dict = None,
        container_shadow: dict = None,
        callbacks: dict = None,
    ):
        """Initialize the WallpapersWidget with configuration parameters."""
        super().__init__(0, class_name="wallpapers-widget")
        self._image_gallery = None

        self._label_content = label
        self._image_path = image_path
        self._tooltip = tooltip
        self._gallery = gallery
        self._animation = animation
        self._padding = container_padding
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        # Initialize Manager
        self._manager = WallpaperManager()
        self._manager.configure(image_path, update_interval, change_automatically, run_after)

        # Connect signals
        self._manager.toggle_gallery_signal.connect(self._on_toggle_gallery_request)

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)

        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, None, self._label_shadow)

        if self._tooltip:
            set_tooltip(self, "Change Wallpaper")

        self.register_callback("toggle_gallery", self._toggle_widget)
        self.register_callback("change_wallpaper", self._manager.change_background)

        self.callback_left = callbacks["on_left"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_right = callbacks["on_right"]

    def _on_toggle_gallery_request(self, screen: str):
        """Handle toggle gallery request from manager."""
        current_screen = self.window().screen() if self.window() else None
        current_screen_name = current_screen.name() if current_screen else None

        if not screen or (current_screen_name and screen.lower() == current_screen_name.lower()):
            self._toggle_widget()

    def _toggle_widget(self):
        """Toggle the visibility of the widget."""
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])

        if self._image_gallery is not None and self._image_gallery.isVisible():
            self._image_gallery.fade_out_and_close_gallery()
        else:
            self._image_gallery = ImageGallery(self._image_path, self._gallery)
            self._image_gallery.fade_in_gallery(parent=self)
