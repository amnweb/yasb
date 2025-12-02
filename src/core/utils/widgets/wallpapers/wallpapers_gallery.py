import os
import re
from functools import partial

from PyQt6.QtCore import (
    QEvent,
    QObject,
    QPoint,
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
from PyQt6.QtGui import QCursor, QImageReader, QPainter, QPainterPath, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

from core.config import get_stylesheet
from core.event_service import EventService
from core.utils.utilities import is_windows_10, refresh_widget_style
from core.utils.win32.win32_accent import Blur
from core.utils.win32.window_actions import force_foreground_focus


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

        # Add default background if .wallpapers-gallery-window doesn't have one
        if ".wallpapers-gallery-window" in filtered_stylesheet:
            # Check if background property exists in the wallpapers-gallery-window class
            # We need to check that to prevent clicking issues on transparent areas where click goes through
            window_style_match = re.search(r"\.wallpapers-gallery-window\s*\{([^}]*)\}", filtered_stylesheet, re.DOTALL)
            if window_style_match:
                style_content = window_style_match.group(1)
                if not re.search(r"background(-color)?\s*:", style_content, re.IGNORECASE):
                    filtered_stylesheet = re.sub(
                        r"(\.wallpapers-gallery-window\s*\{)", r"\1 background: rgba(0,0,0,0.01);", filtered_stylesheet
                    )
        else:
            # Class doesn't exist, add it with default background
            filtered_stylesheet += "\n.wallpapers-gallery-window { background: rgba(0,0,0,0.01); }"

        self.setStyleSheet(filtered_stylesheet)

    def extract_class_styles(self, stylesheet, classes):
        pattern = re.compile(
            r"(\.({})\s*\{{[^}}]*\}})".format("|".join(re.escape(cls) for cls in classes)), re.MULTILINE
        )
        matches = pattern.findall(stylesheet)
        return "\n".join(match[0] for match in matches)


class HoverLabel(QFrame, BaseStyledWidget):
    """HoverLabel: QFrame with hover, focus, and opacity effects for a wallpapers gallery."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._opacity = 0.0
        self._pixmap = None
        self.parent_gallery = parent
        self.setProperty("class", "wallpapers-gallery-image")
        self.apply_stylesheet()
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(self._opacity)

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def pixmap(self):
        return self._pixmap

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

        if self._pixmap and not self._pixmap.isNull():
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            path = QPainterPath()
            rect = QRectF(self.contentsRect())
            radius = self.parent_gallery.corner_radius
            path.addRoundedRect(rect, radius, radius)
            painter.setClipPath(path)

            painter.drawPixmap(self.contentsRect(), self._pixmap)

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
    def __init__(self, image_path, width, height, corner_radius, index, dpr: float = 1.0):
        super().__init__()
        self.image_path = image_path
        self.target_width = width
        self.target_height = height
        self.corner_radius = corner_radius
        self.index = index
        self.dpr = float(dpr) if dpr else 1.0
        self.signals = ImageSignals()

    def run(self):
        target_w = int(self.target_width * self.dpr)
        target_h = int(self.target_height * self.dpr)

        # Get original image dimensions first
        reader = QImageReader(self.image_path)
        original_size = reader.size()

        if not original_size.isValid():
            # Fallback if we can't determine original size
            reader.setScaledSize(QSize(target_w, target_h))
            image = reader.read()
        else:
            # Calculate dimensions to FILL the target area (may crop edges)
            orig_aspect = original_size.width() / original_size.height()
            target_aspect = target_w / target_h if target_h != 0 else 1.0

            if orig_aspect > target_aspect:
                # Image is wider than target - scale to match height and crop width
                scaled_height = target_h
                scaled_width = int(scaled_height * orig_aspect)
            else:
                # Image is taller than target - scale to match width and crop height
                scaled_width = target_w
                scaled_height = int(scaled_width / orig_aspect) if orig_aspect != 0 else target_h

            reader.setScaledSize(QSize(scaled_width, scaled_height))
            image = reader.read()

        # Create a transparent pixmap of the target size
        pixmap = QPixmap(target_w, target_h)
        pixmap.fill(Qt.GlobalColor.transparent)

        # Paint the image centered within the target area
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Calculate position to center the image (may crop edges)
        x = (target_w - image.width()) // 2
        y = (target_h - image.height()) // 2

        # Create source rectangle that ensures the image fills the target area
        source_x = max(0, -x)
        source_y = max(0, -y)
        source_width = min(image.width() - source_x, target_w)
        source_height = min(image.height() - source_y, target_h)

        # Draw only the visible portion of the image
        painter.drawImage(
            QRect(max(0, x), max(0, y), source_width, source_height),
            image,
            QRect(source_x, source_y, source_width, source_height),
        )
        painter.end()

        pixmap.setDevicePixelRatio(self.dpr)

        self.signals.loaded.emit(self.image_path, pixmap, self.index)


class ImageGallery(QMainWindow, BaseStyledWidget):
    """ImageGallery displays a gallery of images with navigation and lazy loading features."""

    def __init__(self, image_paths, gallery):
        super().__init__()
        self.gallery = gallery
        self._event_service = EventService()

        if isinstance(image_paths, str):
            self.image_paths = [image_paths]
        else:
            self.image_paths = image_paths

        all_files = []
        for path in self.image_paths:
            if os.path.exists(path):
                for root, dirs, files in os.walk(path):
                    for f in files:
                        if f.lower().endswith(("png", "jpg", "jpeg", "gif", "bmp")):
                            all_files.append(os.path.join(root, f))

        self.image_files = sorted(all_files)  # or any ordering you prefer
        self.current_index = 0
        self.images_per_page = self.gallery["image_per_page"]
        self.gallery_columns = self.gallery["gallery_columns"]
        self.orientation = self.gallery["orientation"]
        self.horizontal_position = self.gallery["horizontal_position"]
        self.vertical_position = self.gallery["vertical_position"]

        # Parse position_offset: supports int or list [vertical, horizontal] or [top, right, bottom, left]
        offset_input = self.gallery["position_offset"]
        if isinstance(offset_input, int):
            # Single value: all edges
            self.offset_top = self.offset_right = self.offset_bottom = self.offset_left = offset_input
        elif isinstance(offset_input, list):
            if len(offset_input) == 2:
                # [vertical, horizontal]
                self.offset_top = self.offset_bottom = offset_input[0]
                self.offset_left = self.offset_right = offset_input[1]
            elif len(offset_input) == 4:
                # [top, right, bottom, left]
                self.offset_top, self.offset_right, self.offset_bottom, self.offset_left = offset_input
            else:
                # Invalid, use default
                self.offset_top = self.offset_right = self.offset_bottom = self.offset_left = 0
        else:
            self.offset_top = self.offset_right = self.offset_bottom = self.offset_left = 0

        self.respect_work_area = self.gallery["respect_work_area"]
        self.image_spacing = self.gallery["image_spacing"]
        self.blur = self.gallery["blur"]

        # Calculate grid dimensions
        if self.gallery_columns <= 0:
            self.columns = self.images_per_page
        else:
            self.columns = min(self.gallery_columns, self.images_per_page)
        self.rows = (self.images_per_page + self.columns - 1) // self.columns

        # Calculate dimensions based on orientation
        if self.orientation == "landscape":
            self.image_width = self.gallery["image_width"]
            self.image_height = int(self.image_width * 9) // 16
        else:  # portrait
            self.image_width = self.gallery["image_width"]  # Keep width as specified
            self.image_height = int(self.image_width * 16) // 9  # Make height taller

        self.show_button = self.gallery["show_buttons"]
        self.lazy_load = self.gallery["lazy_load"]
        self.lazy_load_fadein = self.gallery["lazy_load_fadein"]
        self.corner_radius = self.gallery["image_corner_radius"]
        self.focused_index = None
        self.is_loading = False
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(self.images_per_page)
        self.apply_stylesheet()
        self.is_closing = False

        # Calculate gallery dimensions
        self.gallery_width = (self.image_width * self.columns) + (self.image_spacing * (self.columns - 1))
        self.gallery_height = (self.image_height * self.rows) + (self.image_spacing * (self.rows - 1))
        self.button_row_height = 0
        self.window_width = 0
        self.window_height = 0
        self.load_token = 0
        self.active_token = 0
        self.expected_images = 0
        self.loaded_images = 0

    def initUI(self, parent=None):
        """Initialize the UI components and layout for the wallpapers gallery window."""
        screen = None
        if parent:
            # First try to get the screen from the parent's window
            # This is robust for widgets inside bars that are assigned to specific screens
            if parent.window() and parent.window().screen():
                screen = parent.window().screen()

            if not screen:
                global_pos = parent.mapToGlobal(QPoint(0, 0))
                screen = QApplication.screenAt(global_pos)

            if not screen:
                screen = parent.screen()
        else:
            screen = QApplication.primaryScreen()

        self.target_screen = screen
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        try:
            self.dpr = float(screen.devicePixelRatio())
        except Exception:
            self.dpr = 1.0

        if self.blur:
            Blur(
                self.winId(),
                Acrylic=True if is_windows_10() else False,
                DarkMode=True,
                RoundCorners=True,
                BorderColor="System",
            )

        # Set up the layout
        central_widget = QFrame()
        self.setCentralWidget(central_widget)
        central_widget.setProperty("class", "wallpapers-gallery-window")
        self.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Set up scroll area to handle overflow when respecting work area
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("background-color:transparent;border:0")
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        # Disable wheel and keyboard events on scroll area to prevent scrolling
        self.scroll_area.wheelEvent = lambda event: event.ignore()
        self.scroll_area.keyPressEvent = lambda event: event.ignore()
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.scroll_area)

        # Set up the image container frame inside scroll area
        self.image_container = QFrame()
        self.image_container.setStyleSheet("background-color:transparent;border:0")
        self.scroll_area.setWidget(self.image_container)
        self.image_layout = QGridLayout()
        self.image_container.setLayout(self.image_layout)
        self.image_container.setContentsMargins(0, 0, 0, 0)
        self.image_container.setFixedSize(self.gallery_width, self.gallery_height)
        # Enable clipping to prevent overflow
        self.image_layout.setSizeConstraint(QGridLayout.SizeConstraint.SetFixedSize)
        self._configure_grid_constraints()
        # Add navigation buttons if needed
        if self.show_button:
            button_layout = QHBoxLayout()
            button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.prev_button = QPushButton("Prev")
            self.prev_button.setProperty("class", "wallpapers-gallery-buttons")
            self.prev_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.prev_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.prev_button.clicked.connect(self.load_prev_images)
            button_layout.addWidget(self.prev_button)

            self.next_button = QPushButton("Next")
            self.next_button.setProperty("class", "wallpapers-gallery-buttons")
            self.next_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.next_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.next_button.clicked.connect(self.load_next_images)
            button_layout.addWidget(self.next_button)

            layout.addLayout(button_layout)

            # Calculate actual button row height from the button widget
            self.prev_button.adjustSize()
            self.button_row_height = max(self.prev_button.sizeHint().height(), self.next_button.sizeHint().height())

        # Apply window bounds and center on screen
        self._apply_window_bounds(screen)

    def _apply_window_bounds(self, screen):
        """Size and center the gallery window within the active screen."""
        clamp_geometry = screen.geometry()
        work_geometry = screen.availableGeometry() if self.respect_work_area else clamp_geometry

        screen_width = work_geometry.width()
        screen_height = work_geometry.height()

        # Use individual offsets for each edge
        left_margin = abs(self.offset_left) if self.offset_left >= 0 else 0
        right_margin = abs(self.offset_right) if self.offset_right >= 0 else 0
        top_margin = abs(self.offset_top) if self.offset_top >= 0 else 0
        bottom_margin = abs(self.offset_bottom) if self.offset_bottom >= 0 else 0

        usable_width = max(1, screen_width - left_margin - right_margin)
        usable_height = max(1, screen_height - top_margin - bottom_margin)

        outer_margin = max(0, self.image_spacing)
        desired_width = self.gallery_width + (outer_margin * 2)
        desired_height = self.gallery_height + (outer_margin * 2) + self.button_row_height

        self.window_width = min(desired_width, screen_width, usable_width)
        self.window_height = min(desired_height, screen_height, usable_height)

        container_height = max(1, self.window_height - self.button_row_height)
        self.image_container.setFixedWidth(self.window_width)
        self.image_container.setFixedHeight(container_height)

        self._position_window(work_geometry, clamp_geometry, self.window_width, self.window_height)

    def _position_window(self, work_geometry, clamp_geometry, width, height):
        """Position the gallery window within the bounds of a screen."""
        screen_width = work_geometry.width()
        screen_height = work_geometry.height()

        # Calculate usable area with individual edge offsets
        left_margin = abs(self.offset_left) if self.offset_left >= 0 else 0
        right_margin = abs(self.offset_right) if self.offset_right >= 0 else 0
        top_margin = abs(self.offset_top) if self.offset_top >= 0 else 0
        bottom_margin = abs(self.offset_bottom) if self.offset_bottom >= 0 else 0

        usable_x = work_geometry.x() + left_margin
        usable_y = work_geometry.y() + top_margin
        usable_width = max(1, screen_width - left_margin - right_margin)
        usable_height = max(1, screen_height - top_margin - bottom_margin)

        target_width = min(width, usable_width)
        target_height = min(height, usable_height)

        available_width = max(0, usable_width - target_width)

        if self.horizontal_position == "left":
            offset_x = 0
        elif self.horizontal_position == "right":
            offset_x = available_width
        else:
            offset_x = available_width // 2

        available_height = max(0, usable_height - target_height)
        if self.vertical_position == "top":
            offset_y = 0
        elif self.vertical_position == "bottom":
            offset_y = available_height
        else:
            offset_y = available_height // 2

        # Apply negative offsets if specified (allows positioning outside work area)
        extra_offset_x = self.offset_left if self.offset_left < 0 else 0
        extra_offset_y = self.offset_top if self.offset_top < 0 else 0

        pos_x = usable_x + offset_x + extra_offset_x
        pos_y = usable_y + offset_y + extra_offset_y

        screen_left = clamp_geometry.x()
        screen_top = clamp_geometry.y()
        screen_right = screen_left + clamp_geometry.width()
        screen_bottom = screen_top + clamp_geometry.height()

        pos_x = max(screen_left, min(pos_x, screen_right - target_width))
        pos_y = max(screen_top, min(pos_y, screen_bottom - target_height))

        self.setGeometry(pos_x, pos_y, target_width, target_height)

    def _configure_grid_constraints(self):
        """Keep column and row sizes stable even when a page is not full."""
        if not hasattr(self, "image_layout"):
            return

        for col in range(self.columns):
            self.image_layout.setColumnMinimumWidth(col, self.image_width)
            self.image_layout.setColumnStretch(col, 0)

        for row in range(self.rows):
            self.image_layout.setRowMinimumHeight(row, self.image_height)
            self.image_layout.setRowStretch(row, 0)

    def load_images(self):
        """Load images for the current page in the background."""
        self.is_loading = True
        self.load_token += 1
        current_token = self.load_token
        self.active_token = current_token
        remaining_images = max(0, len(self.image_files) - self.current_index)
        self.expected_images = min(self.images_per_page, remaining_images)
        self.loaded_images = 0

        # Clear existing widgets and their pixmaps to free memory
        while self.image_layout.count():
            item = self.image_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setPixmap(QPixmap())  # Clear the pixmap to release memory
                widget.deleteLater()

        # Create placeholder labels and add to grid
        for i in range(self.expected_images):
            index = self.current_index + i
            row = i // self.columns
            col = i % self.columns

            label = HoverLabel(self)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            label.mousePressEvent = self.create_mouse_press_event(index)
            self.image_layout.addWidget(label, row, col)

            # Start loading the actual image in background
            image_path = self.image_files[index]
            loader = ImageLoader(
                image_path,
                self.image_width,
                self.image_height,
                self.corner_radius,
                i,
                dpr=getattr(self, "dpr", 1.0),
            )
            loader.signals.loaded.connect(partial(self._handle_image_loaded, current_token))
            self.threadpool.start(loader)

        self.image_layout.setSpacing(self.image_spacing)
        margin = max(0, self.image_spacing)
        self.image_layout.setContentsMargins(margin, margin, margin, margin)

        if self.expected_images == 0:
            self.is_loading = False
            return

        if self.focused_index is None and self.image_files:
            self.focused_index = self.current_index
        self.update_focus()

    def _handle_image_loaded(self, token, image_path, pixmap, index):
        """Process image load callbacks, ignoring stale requests."""
        if token != self.active_token:
            return

        self.update_image_label(image_path, pixmap, index)
        self.loaded_images += 1
        if self.loaded_images >= self.expected_images:
            self.is_loading = False

    def update_image_label(self, image_path, pixmap, index):
        """Update label with loaded image."""
        if index < self.image_layout.count():
            label = self.image_layout.itemAt(index).widget()
            label.setPixmap(pixmap)
            if self.lazy_load:
                label.fade_in(self.lazy_load_fadein)
            else:
                label.opacity = 1.0

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
                label.setProperty("class", "wallpapers-gallery-image focused")
            else:
                label.setProperty("class", "wallpapers-gallery-image")
            refresh_widget_style(label)

    # Navigation methods
    def _navigate_page(self, direction):
        """Navigate pages: direction is 1 for next, -1 for prev."""
        new_index = self.current_index + (direction * self.images_per_page)
        self.current_index = max(0, min(new_index, len(self.image_files) - self.images_per_page))
        self.load_images()
        self.focused_index = self.current_index

    def load_next_images(self):
        """Load the next page of images."""
        self._navigate_page(1)

    def load_prev_images(self):
        """Load the previous page of images."""
        self._navigate_page(-1)

    # Keyboard navigation handlers
    def _move_focus(self, delta):
        """Move focus by delta positions (negative for left/up, positive for right/down)."""
        if self.is_loading:
            return
        if self.focused_index is None:
            self.focused_index = self.current_index
            return

        new_index = self.focused_index + delta
        if 0 <= new_index < len(self.image_files):
            self.focused_index = new_index
            # Check if we need to change page
            if self.focused_index < self.current_index:
                self.load_prev_images()
                if delta == -1:  # left arrow wraps to end of prev page
                    self.focused_index = self.current_index + self.images_per_page - 1
            elif self.focused_index >= self.current_index + self.images_per_page:
                self.load_next_images()
                if delta == 1:  # right arrow wraps to start of next page
                    self.focused_index = self.current_index
            self.update_focus()

    def handle_left_arrow(self):
        """Handle left arrow key press."""
        self._move_focus(-1)

    def handle_right_arrow(self):
        """Handle right arrow key press."""
        self._move_focus(1)

    def handle_up_arrow(self):
        """Handle up arrow key press - move up by one row in grid."""
        self._move_focus(-self.columns)

    def handle_down_arrow(self):
        """Handle down arrow key press - move down by one row in grid."""
        self._move_focus(self.columns)

    def handle_prev_page(self):
        """Handle page up key press."""
        if not self.is_loading:
            self.load_prev_images()
            self.focused_index = self.current_index + self.images_per_page - 1
            self.update_focus()

    def handle_next_page(self):
        """Handle page down key press."""
        if not self.is_loading:
            self.load_next_images()
            self.focused_index = self.current_index
            self.update_focus()

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel events for page navigation."""
        if self.is_loading:
            return

        delta = event.angleDelta().y()
        has_prev_page = self.current_index > 0
        has_next_page = self.current_index + self.images_per_page < len(self.image_files)

        if delta > 0 and has_prev_page:
            self.load_prev_images()
            event.accept()
            return

        if delta < 0 and has_next_page:
            self.load_next_images()
            event.accept()
            return

        event.ignore()

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
            self.handle_up_arrow()
        elif event.key() == Qt.Key.Key_Down:
            self.handle_down_arrow()
        elif event.key() == Qt.Key.Key_PageUp:
            self.handle_prev_page()
        elif event.key() == Qt.Key.Key_PageDown:
            self.handle_next_page()

    def set_wallpaper(self):
        """Set the focused image as wallpaper."""
        if self.focused_index is not None:
            image_path = self.image_files[self.focused_index]
            self._event_service.emit_event("set_wallpaper_signal", image_path)

    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)
        force_foreground_focus(int(self.winId()))

        current_screen = getattr(self, "target_screen", None) or self.screen() or QApplication.primaryScreen()
        if current_screen:
            clamp_geometry = current_screen.geometry()
            work_geometry = current_screen.availableGeometry() if self.respect_work_area else clamp_geometry
            frame = self.frameGeometry()
            self._position_window(work_geometry, clamp_geometry, frame.width(), frame.height())

        QTimer.singleShot(200 if self.lazy_load else 0, self.load_images)

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
        self.fade_in_animation.setDuration(150)
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1)
        self.fade_in_animation.start()
        self.show()

    def fade_out_and_close_gallery(self):
        """Close the gallery with a fade-out animation."""
        if self.is_closing:
            return
        self.is_closing = True

        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_animation.setDuration(150)
        self.fade_out_animation.setStartValue(1)
        self.fade_out_animation.setEndValue(0)
        self.fade_out_animation.finished.connect(self._on_fade_out_finished)
        self.fade_out_animation.start()

    def _on_fade_out_finished(self):
        """Cleanup when fade-out animation finishes."""
        self.threadpool.clear()

        while self.image_layout.count():
            item = self.image_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setPixmap(QPixmap())
                widget.deleteLater()

        self.destroy()

    def mousePressEvent(self, event):
        """Handle mouse press events on the window itself."""
        super().mousePressEvent(event)
        event.accept()

    def changeEvent(self, event):
        """Handle window state changes - close when window becomes inactive."""
        if event.type() == QEvent.Type.ActivationChange:
            if not self.isActiveWindow() and not self.is_closing:
                cursor_pos = QCursor.pos()
                if not self.geometry().contains(cursor_pos):
                    self.fade_out_and_close_gallery()
        super().changeEvent(event)
