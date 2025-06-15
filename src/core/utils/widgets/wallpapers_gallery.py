import os
import re

from PyQt6.QtCore import (
    QObject,
    QPropertyAnimation,
    QRect,
    QRectF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QImageReader, QKeySequence, QPainter, QPainterPath, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.config import get_stylesheet
from core.event_service import EventService
from core.utils.utilities import is_windows_10
from core.utils.win32.blurWindow import Blur


class BaseStyledWidget(QWidget):
    """BaseStyledWidget applies filtered styles to the widget from a given stylesheet."""

    def apply_stylesheet(self):
        stylesheet = get_stylesheet()
        classes_to_include = [
            "wallpapers-gallery-window",
            "wallpapers-gallery-buttons",
            "wallpapers-gallery-buttons:hover",
            "wallpapers-gallery-image",
            "wallpapers-gallery-image.focused",
            "wallpapers-gallery-image:hover",
        ]
        filtered_stylesheet = self.extract_class_styles(stylesheet, classes_to_include)
        self.setStyleSheet(filtered_stylesheet)

    def extract_class_styles(self, stylesheet, classes):
        pattern = re.compile(
            r"(\.({})\s*\{{[^}}]*\}})".format("|".join(re.escape(cls) for cls in classes)), re.MULTILINE
        )
        matches = pattern.findall(stylesheet)
        return "\n".join(match[0] for match in matches)


class HoverLabel(QLabel, BaseStyledWidget):
    """HoverLabel: QLabel with hover, focus, and opacity effects for a wallpapers gallery."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hovered = False
        self.focused = False
        self._opacity = 0.0
        self.parent_gallery = parent
        self.setProperty("class", "wallpapers-gallery-image")
        self.apply_stylesheet()
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(self._opacity)

    def set_focus(self, focused):
        self.focused = focused

    @pyqtProperty(float)
    def opacity(self):
        return self._opacity

    @opacity.setter
    def opacity(self, value):
        self._opacity = value
        self.opacity_effect.setOpacity(self._opacity)

    def fade_in(self, duration):
        self.animation = QPropertyAnimation(self, b"opacity")
        self.animation.setDuration(duration)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()

    def blink(self):
        self.animation = QPropertyAnimation(self, b"opacity")
        self.animation.setDuration(300)
        self.animation.setKeyValueAt(0, 1.0)
        self.animation.setKeyValueAt(0.25, 0.5)
        self.animation.setKeyValueAt(0.5, 1.0)
        self.animation.setKeyValueAt(0.75, 0.5)
        self.animation.setKeyValueAt(1, 1.0)
        self.animation.start()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.blink()
            if isinstance(self.parent_gallery, ImageGallery):
                self.parent_gallery.set_wallpaper()


class ImageSignals(QObject):
    loaded = pyqtSignal(str, QPixmap, int)


class ImageLoader(QRunnable):
    def __init__(self, image_path, width, height, corner_radius, index):
        super().__init__()
        self.image_path = image_path
        self.target_width = width
        self.target_height = height
        self.corner_radius = corner_radius
        self.index = index
        self.signals = ImageSignals()

    def run(self):
        # Get original image dimensions first
        reader = QImageReader(self.image_path)
        original_size = reader.size()

        if not original_size.isValid():
            # Fallback if we can't determine original size
            reader.setScaledSize(QSize(self.target_width, self.target_height))
            image = reader.read()
        else:
            # Calculate dimensions to FILL the target area (may crop edges)
            orig_aspect = original_size.width() / original_size.height()
            target_aspect = self.target_width / self.target_height

            if orig_aspect > target_aspect:
                # Image is wider than target - scale to match height and crop width
                scaled_height = self.target_height
                scaled_width = int(scaled_height * orig_aspect)
            else:
                # Image is taller than target - scale to match width and crop height
                scaled_width = self.target_width
                scaled_height = int(scaled_width / orig_aspect)

            reader.setScaledSize(QSize(scaled_width, scaled_height))
            image = reader.read()

        # Create a transparent pixmap of the target size
        pixmap = QPixmap(self.target_width, self.target_height)
        pixmap.fill(Qt.GlobalColor.transparent)

        # Paint the image centered within the target area
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Create rounded rectangle for clipping
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.target_width, self.target_height), self.corner_radius, self.corner_radius)
        painter.setClipPath(path)

        # Calculate position to center the image (may crop edges)
        x = (self.target_width - image.width()) // 2
        y = (self.target_height - image.height()) // 2

        # Create source rectangle that ensures the image fills the target area
        source_x = max(0, -x)
        source_y = max(0, -y)
        source_width = min(image.width() - source_x, self.target_width)
        source_height = min(image.height() - source_y, self.target_height)

        # Draw only the visible portion of the image
        painter.drawImage(
            QRect(max(0, x), max(0, y), source_width, source_height),
            image,
            QRect(source_x, source_y, source_width, source_height),
        )
        painter.end()

        self.signals.loaded.emit(self.image_path, pixmap, self.index)


class ImageGallery(QMainWindow, BaseStyledWidget):
    """ImageGallery displays a gallery of images with navigation and lazy loading features."""

    def __init__(self, image_folder, gallery):
        super().__init__()

        self.gallery = gallery
        self._event_service = EventService()
        self.image_folder = image_folder
        all_files = []
        for root, dirs, files in os.walk(self.image_folder):
            for f in files:
                if f.lower().endswith(("png", "jpg", "jpeg", "gif", "bmp")):
                    all_files.append(os.path.join(root, f))

        self.image_files = sorted(all_files)  # or any ordering you prefer
        self.current_index = 0
        self.images_per_page = self.gallery["image_per_page"]
        self.orientation = self.gallery["orientation"]

        # Calculate dimensions based on orientation
        if self.orientation == "landscape":
            self.image_width = self.gallery["image_width"]
            self.image_height = int(self.image_width * 9) // 16
        else:  # portrait
            self.image_width = self.gallery["image_width"]  # Keep width as specified
            self.image_height = int(self.image_width * 16) // 9  # Make height taller

        self.show_button = self.gallery["show_buttons"]
        self.window_height = self.image_height + 20
        self.blur = self.gallery["blur"]
        self.image_spacing = self.gallery["image_spacing"]
        self.lazy_load = self.gallery["lazy_load"]
        self.lazy_load_fadein = self.gallery["lazy_load_fadein"]
        self.corner_radius = self.gallery["image_corner_radius"]
        self.focused_index = None
        self.is_loading = False
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(self.images_per_page)
        self.apply_stylesheet()

    def initUI(self, parent=None):
        """Initialize the UI components and layout for the wallpapers gallery window."""
        if parent:
            screen = parent.screen()
        else:
            screen = QApplication.primaryScreen()

        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        self.setGeometry(
            screen_geometry.x() + (screen_width - (screen_width - 60)) // 2,
            screen_geometry.y() + (screen_height - self.window_height) // 2,
            screen_width - 60,
            self.window_height,
        )
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        if self.blur:
            Blur(
                self.winId(),
                Acrylic=True if is_windows_10() else False,
                DarkMode=True,
                RoundCorners=True,
                BorderColor="System",
            )

        # Set up the layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setProperty("class", "wallpapers-gallery-window")
        self.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Set up the scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("background-color:transparent;border:0")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedHeight(self.window_height)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.scroll_area)

        # Set up the image container
        self.image_container = QWidget()
        self.scroll_area.setWidget(self.image_container)
        self.image_layout = QHBoxLayout()
        self.image_container.setLayout(self.image_layout)
        self.image_container.setContentsMargins(0, 0, 0, 0)
        self.image_container.setFixedWidth(
            int(self.image_width * self.images_per_page + self.image_spacing * (self.images_per_page - 1))
        )

        # Add navigation buttons if needed
        if self.show_button:
            button_layout = QHBoxLayout()
            button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.prev_button = QPushButton("Prev")
            self.prev_button.setProperty("class", "wallpapers-gallery-buttons")
            self.prev_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.prev_button.clicked.connect(self.load_prev_images)
            button_layout.addWidget(self.prev_button)

            self.next_button = QPushButton("Next")
            self.next_button.setProperty("class", "wallpapers-gallery-buttons")
            self.next_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.next_button.clicked.connect(self.load_next_images)
            button_layout.addWidget(self.next_button)

            layout.addLayout(button_layout)
            layout.setSpacing(0)
            layout.setContentsMargins(0, 0, 0, 0)

        # Set up keyboard shortcuts
        central_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self.handle_left_arrow)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self.handle_right_arrow)
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, self.handle_prev_page)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, self.handle_next_page)

    def load_images(self):
        """Load images for the current page in the background."""
        self.is_loading = True
        for i in reversed(range(self.image_layout.count())):
            self.image_layout.itemAt(i).widget().setParent(None)

        # Create placeholder labels first
        for i in range(min(self.images_per_page, len(self.image_files) - self.current_index)):
            index = self.current_index + i
            label = HoverLabel(self)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            label.mousePressEvent = self.create_mouse_press_event(index)
            self.image_layout.addWidget(label)

            # Start loading the actual image in background
            image_path = os.path.join(self.image_folder, self.image_files[index])
            loader = ImageLoader(image_path, self.image_width, self.image_height, self.corner_radius, i)
            loader.signals.loaded.connect(self.update_image_label)
            self.threadpool.start(loader)

        self.image_layout.setSpacing(self.image_spacing)
        self.image_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.image_layout.setContentsMargins(0, 0, 0, 0)

        if self.focused_index is None and self.image_files:
            self.focused_index = self.current_index
        self.update_focus()

    def update_image_label(self, image_path, pixmap, index):
        """Update label with loaded image."""
        if index < self.image_layout.count():
            label = self.image_layout.itemAt(index).widget()
            label.setPixmap(pixmap)
            if self.lazy_load:
                label.fade_in(self.lazy_load_fadein)
            else:
                label.opacity = 1.0

        # Check if all images are loaded
        if index == self.images_per_page - 1 or index == len(self.image_files) - self.current_index - 1:
            self.is_loading = False

    def create_mouse_press_event(self, index):
        """Create a mouse press event handler for a specific image index."""

        def mouse_press_event(event):
            self.focused_index = index
            self.update_focus()

        return mouse_press_event

    def update_focus(self):
        """Update the visual focus state of all images."""
        for i in range(self.image_layout.count()):
            label = self.image_layout.itemAt(i).widget()
            label.setFixedWidth(self.image_width)
            label.setFixedHeight(self.image_height)
            if i == self.focused_index - self.current_index:
                label.set_focus(True)
                label.setProperty("class", "wallpapers-gallery-image focused")
            else:
                label.set_focus(False)
                label.setProperty("class", "wallpapers-gallery-image")
            label.style().unpolish(label)
            label.style().polish(label)

    # Navigation methods
    def load_next_images(self):
        """Load the next page of images."""
        if self.current_index + self.images_per_page < len(self.image_files):
            self.current_index += self.images_per_page
            self.load_images()
            self.focused_index = self.current_index
        else:
            self.current_index = max(0, len(self.image_files) - self.images_per_page)
            self.load_images()
            self.focused_index = self.current_index

    def load_prev_images(self):
        """Load the previous page of images."""
        if self.current_index - self.images_per_page >= 0:
            self.current_index -= self.images_per_page
            self.load_images()
            self.focused_index = self.current_index
        else:
            self.current_index = 0
            self.load_images()
            self.focused_index = self.current_index

    # Keyboard navigation handlers
    def handle_left_arrow(self):
        """Handle left arrow key press."""
        if self.is_loading:
            return
        if self.focused_index is None:
            self.focused_index = self.current_index
        if self.focused_index > 0:
            self.focused_index -= 1
            if self.focused_index < self.current_index:
                self.load_prev_images()
                self.focused_index = self.current_index + self.images_per_page - 1
            self.update_focus()

    def handle_right_arrow(self):
        """Handle right arrow key press."""
        if self.is_loading:
            return
        if self.focused_index is None:
            self.focused_index = self.current_index
        if self.focused_index < len(self.image_files) - 1:
            self.focused_index += 1
            if self.focused_index >= self.current_index + self.images_per_page:
                self.load_next_images()
                self.focused_index = self.current_index
            self.update_focus()

    def handle_prev_page(self):
        """Handle page up key press."""
        if self.is_loading:
            return
        if self.current_index - self.images_per_page >= 0:
            self.current_index -= self.images_per_page
            self.load_images()
            self.focused_index = self.current_index + self.images_per_page - 1
            self.update_focus()

    def handle_next_page(self):
        """Handle page down key press."""
        if self.is_loading:
            return
        if self.current_index + self.images_per_page < len(self.image_files):
            self.current_index += self.images_per_page
            self.load_images()
            self.focused_index = self.current_index
            self.update_focus()

    def keyPressEvent(self, event):
        """Handle key press events for gallery navigation."""
        if self.is_loading:
            return

        if event.key() == Qt.Key.Key_Escape:
            self.fade_out_and_close_gallery()
        elif event.key() == Qt.Key.Key_Return and self.focused_index is not None:
            label = self.image_layout.itemAt(self.focused_index - self.current_index).widget()
            label.blink()
            self.set_wallpaper()
        elif event.key() == Qt.Key.Key_Left:
            self.handle_left_arrow()
        elif event.key() == Qt.Key.Key_Right:
            self.handle_right_arrow()
        elif event.key() == Qt.Key.Key_Up:
            self.handle_prev_page()
        elif event.key() == Qt.Key.Key_Down:
            self.handle_next_page()

    def set_wallpaper(self):
        """Set the focused image as wallpaper."""
        if self.focused_index is not None:
            image_path = os.path.join(self.image_folder, self.image_files[self.focused_index])
            self._event_service.emit_event("set_wallpaper_signal", image_path)

    # Window events
    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus()
        if self.lazy_load:
            QTimer.singleShot(400, self.load_images)
        else:
            self.load_images()

    def fade_in_gallery(self, parent=None):
        """Show the gallery with a fade-in animation."""
        # Close any existing galleries
        existing_galleries = [
            widget for widget in QApplication.topLevelWidgets() if isinstance(widget, type(self)) and widget.isVisible()
        ]
        for gallery in existing_galleries:
            gallery.fade_out_and_close_gallery()

        self.initUI(parent)
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in_animation.setDuration(200)
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1)
        self.fade_in_animation.start()
        self.show()

    def fade_out_and_close_gallery(self):
        """Close the gallery with a fade-out animation."""
        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_animation.setDuration(200)
        self.fade_out_animation.setStartValue(1)
        self.fade_out_animation.setEndValue(0)
        self.fade_out_animation.finished.connect(self._on_fade_out_finished)
        self.fade_out_animation.start()

    def _on_fade_out_finished(self):
        """
        Handles the event when the fade-out animation is finished.
        This method destroys the current widget and forces garbage collection to free up memory.
        """
        self.destroy()
        import gc

        gc.collect()
