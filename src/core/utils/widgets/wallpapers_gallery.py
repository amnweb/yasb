import os
import re
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QGraphicsOpacityEffect, QSizePolicy
from PyQt6.QtGui import QPixmap, QKeySequence, QShortcut, QPainter, QPainterPath
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, pyqtProperty, QRectF
from core.utils.win32.blurWindow import Blur
from core.event_service import EventService
from core.config import get_stylesheet
from core.utils.utilities import is_windows_10

class ImageCache:
    """
    Singleton cache for storing and retrieving images.
    """
    _instance = None
    _cache = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ImageCache, cls).__new__(cls)
        return cls._instance

    def get(self, key):
        return self._cache.get(key)

    def set(self, key, value):
        self._cache[key] = value

    def __contains__(self, key):
        return key in self._cache
    
class BaseStyledWidget(QWidget):
    """
    BaseStyledWidget applies filtered styles to the widget from a given stylesheet.
    """
    def apply_stylesheet(self):
        stylesheet = get_stylesheet()
        classes_to_include = [
            'wallpapers-gallery-window',
            'wallpapers-gallery-buttons',
            'wallpapers-gallery-buttons:hover',
            'wallpapers-gallery-image',
            'wallpapers-gallery-image.focused',
            'wallpapers-gallery-image:hover'
        ]
        filtered_stylesheet = self.extract_class_styles(stylesheet, classes_to_include)
        self.setStyleSheet(filtered_stylesheet)

    def extract_class_styles(self, stylesheet, classes):
        pattern = re.compile(r'(\.({})\s*\{{[^}}]*\}})'.format('|'.join(re.escape(cls) for cls in classes)), re.MULTILINE)
        matches = pattern.findall(stylesheet)
        return '\n'.join(match[0] for match in matches)


class HoverLabel(QLabel, BaseStyledWidget):
    """
    HoverLabel: QLabel with hover, focus, and opacity effects for a wallpapers gallery.
    """
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


class ImageGallery(QMainWindow, BaseStyledWidget):
    """
    ImageGallery displays a gallery of images with navigation and lazy loading features.
    """
    def __init__(self, image_folder, gallery):
        super().__init__()
        self.gallery = gallery
        self._event_service = EventService()
        self.image_folder = image_folder
        self.image_files = [f for f in os.listdir(image_folder) if f.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp'))]
        self.current_index = 0
        self.images_per_page = self.gallery['image_per_page']
        self.image_width = self.gallery['image_width']
        self.orientation = self.gallery['orientation']
        self.image_height = int(self.image_width * 9) // 16 if self.orientation == "landscape" else int(self.image_width * 16) // 9
        self.show_button = self.gallery['show_buttons']
        self.window_height = self.image_height + 20
        self.blur = self.gallery['blur']
        self.image_spacing = self.gallery['image_spacing']
        self.lazy_load = self.gallery['lazy_load']
        self.lazy_load_fadein = self.gallery['lazy_load_fadein']
        self.corner_radius = self.gallery['image_corner_radius']
        self.lazy_load_delay = self.gallery['lazy_load_delay']
        self.enable_cache = self.gallery['enable_cache']
        self.focused_index = None
        self.image_cache = ImageCache()
        self.is_loading = False
        self.initUI()
        self.apply_stylesheet()


    def initUI(self):
        """
        Initialize the UI components and layout for the wallpapers gallery window.
        """
        screen_geometry = QApplication.primaryScreen().geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        self.setGeometry(
            (screen_width - (screen_width - 60)) // 2,
            (screen_height - self.window_height) // 2,
            screen_width - 60,
            self.window_height
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
                BorderColor="System"
            )
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        self.scroll_area = QScrollArea()
        central_widget.setProperty("class", "wallpapers-gallery-window")
        self.scroll_area.setStyleSheet("background-color:transparent;border:0")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFixedHeight(self.window_height)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.scroll_area)
        self.image_container = QWidget()
       
        self.scroll_area.setWidget(self.image_container)
        self.image_layout = QHBoxLayout()
        self.image_container.setLayout(self.image_layout)
        self.image_container.setContentsMargins(0, 0, 0, 0)
        self.image_container.setFixedWidth(int(self.image_width * self.images_per_page + self.image_spacing * (self.images_per_page - 1)))
        if self.show_button:
            button_layout = QHBoxLayout()
            button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.prev_button = QPushButton('Prev')
            self.prev_button.setProperty("class", "wallpapers-gallery-buttons")
            self.prev_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.prev_button.clicked.connect(self.load_prev_images)
            button_layout.addWidget(self.prev_button)
            self.next_button = QPushButton('Next')
            self.next_button.setProperty("class", "wallpapers-gallery-buttons")
            self.next_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.next_button.clicked.connect(self.load_next_images)
            button_layout.addWidget(self.next_button)
            layout.addLayout(button_layout)
            layout.setSpacing(0)
            layout.setContentsMargins(0, 0, 0, 0)
        central_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self.handle_left_arrow)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self.handle_right_arrow)
        QShortcut(QKeySequence(Qt.Key.Key_Up), self, self.handle_prev_page)
        QShortcut(QKeySequence(Qt.Key.Key_Down), self, self.handle_next_page)

    def load_images(self):
        self.is_loading = True
        for i in reversed(range(self.image_layout.count())):
            self.image_layout.itemAt(i).widget().setParent(None)
        self.current_image_index = self.current_index
        self.load_next_image()

    def load_next_image(self):
        """
        Loads the next image in the gallery with optional caching and lazy loading.
        """
        if self.current_image_index < len(self.image_files) and self.current_image_index < self.current_index + self.images_per_page:
            image_path = os.path.join(self.image_folder, self.image_files[self.current_image_index])
            if self.enable_cache:
                pixmap = self.image_cache.get(image_path) or self.image_cache.set(image_path, self.create_pixmap(image_path)) or self.image_cache.get(image_path)
            else:
                pixmap = self.create_pixmap(image_path)
            label = HoverLabel(self)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            label.mousePressEvent = self.create_mouse_press_event(self.current_image_index)
            self.image_layout.addWidget(label)
            self.image_layout.setSpacing(self.image_spacing)
            self.image_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.image_layout.setContentsMargins(0, 0, 0, 0)
            self.current_image_index += 1
            if self.lazy_load:
                label.fade_in(self.lazy_load_fadein)
                QTimer.singleShot(self.lazy_load_delay, self.load_next_image)
            else:
                self.load_next_image()
                label.fade_in(0)
        else:
            self.is_loading = False
        if self.focused_index is None and self.image_files:
            self.focused_index = self.current_index
        self.update_focus()

    def create_pixmap(self, image_path):
        """
        Create a rounded pixmap from an image path with specified dimensions and orientation.
        """
        if self.orientation == "landscape":
            pixmap = QPixmap(image_path).scaled(self.image_width, self.image_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        else:
            pixmap = QPixmap(image_path).scaled(self.image_width, self.image_height, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        rounded_pixmap = QPixmap(self.image_width, self.image_height)
        rounded_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.image_width, self.image_height), self.corner_radius, self.corner_radius)
        painter.setClipPath(path)
        x = int((self.image_width - pixmap.width()) / 2)
        y = int((self.image_height - pixmap.height()) / 2)
        painter.drawPixmap(x, y, pixmap)
        painter.end()
        self.image_cache.set(image_path, pixmap)
 
        return rounded_pixmap

    def create_mouse_press_event(self, index):
        def mouse_press_event(event):
            self.focused_index = index
            self.update_focus()
        return mouse_press_event

    def update_focus(self):
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

    def load_next_images(self):
        if self.current_index + self.images_per_page < len(self.image_files):
            self.current_index += self.images_per_page
            self.load_images()
            if self.focused_index is not None:
                self.focused_index = self.current_index
        else:
            self.current_index = len(self.image_files) - self.images_per_page
            self.load_images()
            if self.focused_index is not None:
                self.focused_index = self.current_index

    def load_prev_images(self):
        if self.current_index - self.images_per_page >= 0:
            self.current_index -= self.images_per_page
            self.load_images()
            if self.focused_index is not None:
                self.focused_index = self.current_index
        else:
            self.current_index = 0
            self.load_images()
            if self.focused_index is not None:
                self.focused_index = self.current_index

    def handle_left_arrow(self):
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
        if self.is_loading:
            return
        if self.current_index - self.images_per_page >= 0:
            self.current_index -= self.images_per_page
            self.load_images()
            if self.focused_index is not None:
                self.focused_index = self.current_index + self.images_per_page - 1
            self.update_focus()

    def handle_next_page(self):
        if self.is_loading:
            return
        if self.current_index + self.images_per_page < len(self.image_files):
            self.current_index += self.images_per_page
            self.load_images()
            if self.focused_index is not None:
                self.focused_index = self.current_index
            self.update_focus()

    def keyPressEvent(self, event):
        """
        Handles key press events for gallery navigation and actions.
        """
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
        if self.focused_index is not None:
            image_path = os.path.join(self.image_folder, self.image_files[self.focused_index])
            self._event_service.emit_event("set_wallpaper_signal", image_path)

    def showEvent(self, event):
        """
        Handles the show event, activates window, sets focus, and loads images.
        """
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.setFocus()
        if self.lazy_load:
            QTimer.singleShot(400, self.load_images)
        else:
            self.load_images()

    def fade_in_gallery(self):
        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in_animation.setDuration(200)
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1)
        self.fade_in_animation.start()
        self.show()

    def fade_out_and_close_gallery(self):
        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_animation.setDuration(200)
        self.fade_out_animation.setStartValue(1)
        self.fade_out_animation.setEndValue(0)
        self.fade_out_animation.finished.connect(self.destroy)
        self.fade_out_animation.start()
         