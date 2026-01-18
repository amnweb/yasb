"""
Media Background Handler for Overlay Container Widget
Supports images, animated images (GIF, APNG), and videos as backgrounds.
"""

import logging
import os
from pathlib import Path
from PyQt6.QtCore import Qt, QUrl, QSize, QRect, QPoint
from PyQt6.QtGui import QPixmap, QMovie, QPainter
from PyQt6.QtWidgets import QLabel, QSizePolicy, QGraphicsOpacityEffect, QWidget
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

# Hardcoded limits based on typical YASB bar dimensions
MAX_MEDIA_HEIGHT = 200  # Pixels - double typical bar height
MAX_MEDIA_WIDTH = 3840  # Pixels - 4K monitor width
MIN_MEDIA_HEIGHT = 10   # Pixels - minimum visible
MIN_MEDIA_WIDTH = 10    # Pixels - minimum visible

# Supported formats
IMAGE_FORMATS = {'.png', '.jpg', '.jpeg', '.bmp', '.webp', '.svg'}
ANIMATED_FORMATS = {'.gif', '.apng', '.webp'}  # webp can be both static and animated
VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.webm', '.mkv', '.m4v', '.flv'}


class OffsetMediaLabel(QLabel):
    """Custom QLabel that supports view offset for precise media positioning."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_offset_x = 0
        self._view_offset_y = 0
        self._original_pixmap = None
        self._original_movie = None
        self._cached_scaled_pixmap = None  # Cache scaled pixmap to avoid recreating every frame
        self._last_widget_size = None  # Track size changes
        
    def set_view_offset(self, x: int, y: int):
        """Set the view offset for the media."""
        self._view_offset_x = x
        self._view_offset_y = y
        self._cached_scaled_pixmap = None  # Invalidate cache
        self.update()  # Trigger repaint
        
    def setPixmap(self, pixmap: QPixmap):
        """Override setPixmap to store original pixmap."""
        # Clear old pixmap to free memory
        if self._original_pixmap:
            self._original_pixmap = None
        self._original_pixmap = pixmap
        self._cached_scaled_pixmap = None  # Invalidate cache
        super().setPixmap(pixmap)
        
    def setMovie(self, movie: QMovie):
        """Override setMovie to store original movie."""
        # Clear old movie reference
        if self._original_movie:
            self._original_movie = None
        self._original_movie = movie
        self._cached_scaled_pixmap = None  # Invalidate cache
        super().setMovie(movie)
        
    def resizeEvent(self, event):
        """Handle resize to invalidate cache."""
        super().resizeEvent(event)
        self._cached_scaled_pixmap = None
        self._last_widget_size = None
        
    def paintEvent(self, event):
        """Custom paint event to apply view offset."""
        if self._view_offset_x == 0 and self._view_offset_y == 0:
            # No offset, use default painting
            super().paintEvent(event)
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Get the pixmap to draw (from movie or static pixmap)
        pixmap_to_draw = None
        if self._original_movie and self._original_movie.isValid():
            pixmap_to_draw = self._original_movie.currentPixmap()
        elif self._original_pixmap and not self._original_pixmap.isNull():
            pixmap_to_draw = self._original_pixmap
            
        if not pixmap_to_draw or pixmap_to_draw.isNull():
            super().paintEvent(event)
            return
            
        # Calculate scaled size based on widget size and scaling mode
        widget_rect = self.rect()
        current_size = widget_rect.size()
        
        # Use cached scaled pixmap if size hasn't changed (CRITICAL for performance)
        if self.hasScaledContents():
            # Check if we need to rescale
            if self._cached_scaled_pixmap is None or self._last_widget_size != current_size:
                # Scaled contents - pixmap fills widget
                self._cached_scaled_pixmap = pixmap_to_draw.scaled(
                    current_size,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._last_widget_size = current_size
            scaled_pixmap = self._cached_scaled_pixmap
        else:
            # Not scaled - use original size or fit to widget
            scaled_pixmap = pixmap_to_draw
            
        # Apply view offset
        draw_x = self._view_offset_x
        draw_y = self._view_offset_y
        
        # Draw the pixmap with offset
        painter.drawPixmap(draw_x, draw_y, scaled_pixmap)
        painter.end()
    
    def cleanup(self):
        """Clean up resources to prevent memory leaks."""
        # Clear cached pixmaps
        self._cached_scaled_pixmap = None
        self._original_pixmap = None
        self._original_movie = None
        self._last_widget_size = None


class OverlayBackgroundMedia:
    """Handles media (image/video) backgrounds for overlay panel."""

    def __init__(self, media_config: dict, parent_widget):
        self.config = media_config
        self.parent = parent_widget
        self.widget = None
        self.media_player = None
        self.media_type = None

        if not self.config.get("enabled", False):
            return

        file_path = self.config.get("file", "")
        if not file_path or not os.path.exists(file_path):
            logging.error(f"OverlayBackgroundMedia: File not found: {file_path}")
            return

        self._load_media(file_path)

    def _detect_media_type(self, file_path: str) -> str:
        """Detect media type from file extension and content."""
        ext = Path(file_path).suffix.lower()

        # User specified type
        specified_type = self.config.get("type", "auto")
        if specified_type != "auto":
            return specified_type

        # Auto-detect from extension
        if ext in VIDEO_FORMATS:
            return "video"
        elif ext in ANIMATED_FORMATS:
            # For webp, we'd need to check if it's actually animated
            # For now, treat as animated
            return "animated"
        elif ext in IMAGE_FORMATS:
            return "image"
        else:
            logging.warning(f"OverlayBackgroundMedia: Unknown media type for {ext}, defaulting to image")
            return "image"

    def _validate_media_dimensions(self, width: int, height: int) -> bool:
        """Validate media dimensions against hardcoded limits."""
        if width < MIN_MEDIA_WIDTH or height < MIN_MEDIA_HEIGHT:
            logging.error(
                f"OverlayBackgroundMedia: Media too small ({width}x{height}). "
                f"Minimum: {MIN_MEDIA_WIDTH}x{MIN_MEDIA_HEIGHT}px"
            )
            return False

        if width > MAX_MEDIA_WIDTH or height > MAX_MEDIA_HEIGHT:
            logging.warning(
                f"OverlayBackgroundMedia: Media very large ({width}x{height}). "
                f"Recommended max: {MAX_MEDIA_WIDTH}x{MAX_MEDIA_HEIGHT}px. "
                f"Performance may be affected."
            )
            # Allow but warn - Qt will handle scaling

        return True

    def _load_media(self, file_path: str):
        """Load media file and create appropriate widget."""
        self.media_type = self._detect_media_type(file_path)
        logging.info(f"OverlayBackgroundMedia: Loading {self.media_type} from {file_path}")

        try:
            if self.media_type == "image":
                self._load_static_image(file_path)
            elif self.media_type == "animated":
                self._load_animated_image(file_path)
            elif self.media_type == "video":
                self._load_video(file_path)
        except Exception as e:
            logging.error(f"OverlayBackgroundMedia: Error loading media: {e}", exc_info=True)

    def _load_static_image(self, file_path: str):
        """Load static image as background."""
        pixmap = QPixmap(file_path)

        if pixmap.isNull():
            logging.error(f"OverlayBackgroundMedia: Failed to load image: {file_path}")
            return

        # Validate dimensions
        if not self._validate_media_dimensions(pixmap.width(), pixmap.height()):
            return

        # Create label widget with offset support
        self.widget = OffsetMediaLabel(self.parent)
        self.widget.setPixmap(pixmap)
        self._apply_widget_settings()
        
        # Apply view offset if specified
        view_offset_x = self.config.get("view_offset_x", 0)
        view_offset_y = self.config.get("view_offset_y", 0)
        if view_offset_x != 0 or view_offset_y != 0:
            self.widget.set_view_offset(view_offset_x, view_offset_y)
            logging.info(f"OverlayBackgroundMedia: Applied view offset ({view_offset_x}, {view_offset_y})")

        logging.info(f"OverlayBackgroundMedia: Loaded static image ({pixmap.width()}x{pixmap.height()})")

    def _load_animated_image(self, file_path: str):
        """Load animated image (GIF, APNG) as background."""
        movie = QMovie(file_path)

        if not movie.isValid():
            logging.error(f"OverlayBackgroundMedia: Failed to load animated image: {file_path}")
            return

        # Get first frame to validate dimensions
        movie.jumpToFrame(0)
        pixmap = movie.currentPixmap()
        if not self._validate_media_dimensions(pixmap.width(), pixmap.height()):
            return

        # Create label widget with offset support
        self.widget = OffsetMediaLabel(self.parent)
        self.widget.setMovie(movie)

        # Configure caching and playback speed
        movie.setCacheMode(QMovie.CacheMode.CacheAll)

        # Set playback speed (100 = normal speed)
        movie.setSpeed(int(self.config.get("playback_rate", 1.0) * 100))

        # Configure looping via signal handler
        # QMovie doesn't have setLoopCount in PyQt6, so we use finished signal
        if self.config.get("loop", True):
            # Reconnect to start on finish for infinite loop
            movie.finished.connect(movie.start)
        # If loop is False, movie will stop after playing once (default behavior)

        self._apply_widget_settings()
        
        # Apply view offset if specified
        view_offset_x = self.config.get("view_offset_x", 0)
        view_offset_y = self.config.get("view_offset_y", 0)
        if view_offset_x != 0 or view_offset_y != 0:
            self.widget.set_view_offset(view_offset_x, view_offset_y)
            logging.info(f"OverlayBackgroundMedia: Applied view offset ({view_offset_x}, {view_offset_y})")
        
        movie.start()

        logging.info(f"OverlayBackgroundMedia: Loaded animated image ({pixmap.width()}x{pixmap.height()})")

    def _load_video(self, file_path: str):
        """Load video as background."""
        # Create video widget
        self.widget = QVideoWidget(self.parent)
        self.widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Create media player
        self.media_player = QMediaPlayer(self.parent)

        # Create audio output with volume control
        audio_output = QAudioOutput(self.parent)

        # Set muted state
        audio_output.setMuted(self.config.get("muted", True))

        # Set volume (0.0 to 1.0)
        volume = self.config.get("volume", 1.0)
        audio_output.setVolume(volume)

        # Set up player
        self.media_player.setAudioOutput(audio_output)
        self.media_player.setVideoOutput(self.widget)
        self.media_player.setSource(QUrl.fromLocalFile(file_path))

        # Configure playback rate
        playback_rate = self.config.get("playback_rate", 1.0)
        self.media_player.setPlaybackRate(playback_rate)

        # Configure looping
        if self.config.get("loop", True):
            self.media_player.setLoops(QMediaPlayer.Loops.Infinite)

        self._apply_widget_settings()

        # Start playback
        self.media_player.play()

        logging.info(f"OverlayBackgroundMedia: Loaded video from {file_path}")

    def _apply_widget_settings(self):
        """Apply common widget settings (fit, opacity, etc.)."""
        if not self.widget:
            return

        # Set as background (don't accept focus/input)
        self.widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Apply CSS class for custom styling
        css_class = self.config.get("css_class", "")
        if css_class:
            self.widget.setProperty("class", f"overlay-background-media {css_class}")
            logging.info(f"OverlayBackgroundMedia: Applied CSS class: {css_class}")
        else:
            self.widget.setProperty("class", "overlay-background-media")

        # Store offset values as widget attributes for positioning
        self.widget.media_offset_x = self.config.get("offset_x", 0)
        self.widget.media_offset_y = self.config.get("offset_y", 0)

        # Apply opacity using QGraphicsOpacityEffect (works for child widgets)
        opacity = self.config.get("opacity", 1.0)
        if opacity < 1.0:
            opacity_effect = QGraphicsOpacityEffect()
            opacity_effect.setOpacity(opacity)
            self.widget.setGraphicsEffect(opacity_effect)

        # Apply fit mode and alignment
        fit_mode = self.config.get("fit", "cover")
        alignment = self.config.get("alignment", "center")
        self._apply_fit_mode(fit_mode, alignment)

    def _apply_fit_mode(self, fit_mode: str, alignment: str = "center"):
        """Apply the fit mode and alignment to the widget."""
        if not self.widget:
            return

        # Convert alignment string to Qt alignment flags
        qt_alignment = self._get_qt_alignment(alignment)

        # For QLabel with pixmap/movie
        if isinstance(self.widget, QLabel):
            if fit_mode == "fill":
                self.widget.setScaledContents(True)
                self.widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                self.widget.setAlignment(qt_alignment)
            elif fit_mode == "contain":
                self.widget.setScaledContents(False)
                self.widget.setAlignment(qt_alignment)
            elif fit_mode == "cover":
                self.widget.setScaledContents(True)
                self.widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                self.widget.setAlignment(qt_alignment)
            elif fit_mode == "stretch":
                self.widget.setScaledContents(True)
                self.widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                self.widget.setAlignment(qt_alignment)
            elif fit_mode == "center":
                self.widget.setScaledContents(False)
                self.widget.setAlignment(qt_alignment)
            elif fit_mode == "scale-down":
                self.widget.setScaledContents(False)
                self.widget.setAlignment(qt_alignment)

        # For QVideoWidget
        elif isinstance(self.widget, QVideoWidget):
            if fit_mode == "fill" or fit_mode == "cover":
                self.widget.setAspectRatioMode(Qt.AspectRatioMode.IgnoreAspectRatio)
            elif fit_mode == "contain":
                self.widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
            elif fit_mode == "stretch":
                self.widget.setAspectRatioMode(Qt.AspectRatioMode.IgnoreAspectRatio)
            else:
                self.widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

    def _get_qt_alignment(self, alignment: str) -> Qt.AlignmentFlag:
        """Convert alignment string to Qt alignment flags."""
        alignment_map = {
            "top-left": Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            "top-center": Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            "top-right": Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
            "center-left": Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignCenter,
            "center-right": Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            "bottom-left": Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
            "bottom-center": Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            "bottom-right": Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
        }
        
        return alignment_map.get(alignment, Qt.AlignmentFlag.AlignCenter)

    def get_widget(self):
        """Get the media widget."""
        return self.widget

    def cleanup(self):
        """Clean up resources."""
        logging.debug("OverlayBackgroundMedia: Starting cleanup")
        
        # Stop and clean up media player
        if self.media_player:
            try:
                self.media_player.stop()
                self.media_player.setSource(QUrl())
                # Disconnect all signals to prevent memory leaks
                self.media_player.disconnect()
            except Exception as e:
                logging.debug(f"OverlayBackgroundMedia: Error cleaning up media player: {e}")
            finally:
                self.media_player = None

        # Clean up widget
        if self.widget:
            try:
                if isinstance(self.widget, QLabel):
                    movie = self.widget.movie()
                    if movie:
                        # Stop movie and disconnect signals
                        movie.stop()
                        try:
                            movie.disconnect()
                        except Exception:
                            pass  # Ignore if no connections
                        
                # Call cleanup on OffsetMediaLabel if it has the method
                if hasattr(self.widget, 'cleanup'):
                    self.widget.cleanup()
                    
                self.widget.setParent(None)
                self.widget.deleteLater()
            except Exception as e:
                logging.debug(f"OverlayBackgroundMedia: Error cleaning up widget: {e}")
            finally:
                self.widget = None
                
        logging.debug("OverlayBackgroundMedia: Cleanup completed")
