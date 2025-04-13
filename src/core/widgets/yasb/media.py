import logging
from typing import Any, Optional

from PIL import Image, ImageChops
from PIL.ImageDraw import ImageDraw
from PIL.ImageQt import QPixmap
from PyQt6 import QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QWheelEvent
from PIL.ImageQt import ImageQt
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackInfo

from core.utils.win32.media import WindowsMedia
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.media import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QGridLayout, QHBoxLayout, QWidget, QGraphicsDropShadowEffect
from core.utils.widgets.animation_manager import AnimationManager

class MediaWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    _playback_info_signal = QtCore.pyqtSignal(GlobalSystemMediaTransportControlsSessionPlaybackInfo)
    _media_info_signal = QtCore.pyqtSignal(object)
    _session_status_signal = QtCore.pyqtSignal(bool)

    def __init__(
            self,
            label: str,
            label_alt: str,
            label_shadow: bool,
            hide_empty: bool,
            callbacks: dict[str, str],
            max_field_size: dict[str, int],
            show_thumbnail: bool,
            controls_only: bool,
            controls_left: bool,
            controls_hide: bool,
            thumbnail_alpha: int,
            thumbnail_padding: int,
            thumbnail_corner_radius: int,
            thumbnail_edge_fade: bool,
            symmetric_corner_radius: bool,
            icons: dict[str, str],
            animation: dict[str, str],
            container_padding: dict[str, int]
        ):
        super().__init__(class_name="media-widget")
        self._label_content = label
        self._label_alt_content = label_alt

        self._label_shadow = label_shadow
        self._max_field_size = max_field_size
        self._show_thumbnail = show_thumbnail
        self._thumbnail_alpha = thumbnail_alpha
        self._media_button_icons = icons
        self._controls_only = controls_only
        self._controls_left = controls_left
        self._controls_hide = controls_hide
        self._thumbnail_padding = thumbnail_padding
        self._thumbnail_corner_radius = thumbnail_corner_radius
        self._thumbnail_edge_fade = thumbnail_edge_fade
        self._symmetric_corner_radius = symmetric_corner_radius
        self._hide_empty = hide_empty
        self._animation = animation
        self._padding = container_padding
        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(self._padding['left'],self._padding['top'],self._padding['right'],self._padding['bottom'])
        # Initialize container
        self._widget_container: QWidget = QWidget()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)
        if self._hide_empty:
            self._widget_frame.hide()
        # Make a grid box to overlay the text and thumbnail
        self.thumbnail_box = QGridLayout()

        if self._controls_left:
            self._prev_label, self._play_label, self._next_label = self._create_media_buttons()
            if not controls_only:
                self._widget_container_layout.addLayout(self.thumbnail_box)
        else:
            if not controls_only:
                self._widget_container_layout.addLayout(self.thumbnail_box)
            self._prev_label, self._play_label, self._next_label = self._create_media_buttons()

        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_text_shadow(self._label)
        
        self._label_alt = QLabel()
        self._label_alt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_text_shadow(self._label_alt)

        self._thumbnail_label = QLabel()
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label.setProperty("class", "label")
        self._label_alt.setProperty("class", "label alt")

        self.thumbnail_box.addWidget(self._thumbnail_label, 0, 0)
        self.thumbnail_box.addWidget(self._label, 0, 0)
        self.thumbnail_box.addWidget(self._label_alt, 0, 0)

        # Get media manager
        self.media = WindowsMedia()

        # Set configure signals and register them als callbacks
        self._playback_info_signal.connect(self._on_playback_info_changed)
        self.media.subscribe(lambda playback_info: self._playback_info_signal.emit(playback_info), 'playback_info')
        self._media_info_signal.connect(self._on_media_properties_changed)
        self.media.subscribe(lambda media_info: self._media_info_signal.emit(media_info), 'media_info')
        self._session_status_signal.connect(self._on_session_status_changed)
        self.media.subscribe(lambda session_status: self._session_status_signal.emit(session_status), 'session_status')

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']

        if not self._controls_only:
            self.register_callback("toggle_play_pause", self._toggle_play_pause)
            self.register_callback("toggle_label", self._toggle_label)
            self._label.show()

        self._label_alt.hide()
        self._show_alt_label = False

        # Force media update to detect running session
        self.timer.singleShot(0, self.media.force_update)

    def _apply_text_shadow(self, label: QLabel):
        """Apply shadow effect to a label."""
        if self._label_shadow:
            shadow_effect = QGraphicsDropShadowEffect(label)
            shadow_effect.setOffset(1, 1)
            shadow_effect.setBlurRadius(3)
            shadow_effect.setColor(Qt.GlobalColor.black)
            label.setGraphicsEffect(shadow_effect)
        
    def _toggle_label(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        self._show_alt_label = not self._show_alt_label

        if self._show_alt_label:
            self._label.hide()
            self._label_alt.show()
        else:
            self._label.show()
            self._label_alt.hide()

        # Force an update on the media info when toggling the label
        self.media.force_update()

    def _toggle_play_pause(self):
        if self._animation['enabled']:
            AnimationManager.animate(self, self._animation['type'], self._animation['duration'])
        WindowsMedia().play_pause()

    @QtCore.pyqtSlot(bool)
    def _on_session_status_changed(self, has_session: bool):
        active_label = self._label_alt if self._show_alt_label else self._label

        if has_session:
            # If media is not None, we show the frame
            self._widget_frame.show()

            # If we do not only have controls, make sure the label is shown
            if not self._controls_only:
                active_label.show()

        else:
            # Hide thumbnail and label fields
            self._thumbnail_label.hide()
            active_label.hide()
            active_label.setText('')
            if not self._controls_hide and self._play_label is not None:
                self._play_label.setText(self._media_button_icons['play'])

            # If we want to hide the widget when no music is playing, hide it!
            if self._hide_empty:
                self._widget_frame.hide()

    @QtCore.pyqtSlot(GlobalSystemMediaTransportControlsSessionPlaybackInfo)
    def _on_playback_info_changed(self, playback_info: GlobalSystemMediaTransportControlsSessionPlaybackInfo):
        # Set play-pause state icon
        if not self._controls_hide:
            self._play_label.setText(self._media_button_icons['pause' if playback_info.playback_status == 4 else 'play'])

            # Update prev button
            is_prev_enabled = playback_info.controls.is_previous_enabled
            self._prev_label.setProperty("class", f"btn prev {'disabled' if not is_prev_enabled else ''}")
            self._prev_label.setCursor(Qt.CursorShape.PointingHandCursor if is_prev_enabled else Qt.CursorShape.ArrowCursor)
            
            # Update play/pause button
            is_play_enabled = playback_info.controls.is_play_pause_toggle_enabled
            self._play_label.setProperty("class", f"btn play {'disabled' if not is_play_enabled else ''}")
            self._play_label.setCursor(Qt.CursorShape.PointingHandCursor if is_play_enabled else Qt.CursorShape.ArrowCursor)
            
            # Update next button
            is_next_enabled = playback_info.controls.is_next_enabled
            self._next_label.setProperty("class", f"btn next {'disabled' if not is_next_enabled else ''}")
            self._next_label.setCursor(Qt.CursorShape.PointingHandCursor if is_next_enabled else Qt.CursorShape.ArrowCursor)

            # Refresh style sheets
            self._prev_label.setStyleSheet('')
            self._play_label.setStyleSheet('')
            self._next_label.setStyleSheet('')

    @QtCore.pyqtSlot(object) # None or dict
    def _on_media_properties_changed(self, media_info: Optional[dict[str, Any]]):
        active_label = self._label_alt if self._show_alt_label else self._label
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content

        # If we only have controls, stop update here
        if self._controls_only:
            return

        # Shorten fields if necessary with ...
        media_info = {k: self._format_max_field_size(v) if isinstance(v, str) else v for k, v in
                      media_info.items()}

        # Format the label
        format_label_content = active_label_content.format(**media_info)
        active_label.setText(format_label_content)

        # If we don't want the thumbnail, stop here
        if not self._show_thumbnail:
            return

        # If no media in session, hide thumbnail and stop here
        if media_info['thumbnail'] is None and not media_info['title']:
            self._thumbnail_label.hide()
            return

        # Only update the thumbnail if the title/artist changes or if we did a toggle (resize)
        try:
            if media_info['thumbnail'] is not None:
                thumbnail = self._crop_thumbnail(media_info['thumbnail'], active_label.sizeHint().width())
                pixmap = QPixmap.fromImage(ImageQt(thumbnail))
                self._thumbnail_label.setPixmap(pixmap)
        except Exception as e:
            logging.error(f'MediaWidget: Error setting thumbnail: {e}')
            self._thumbnail_label.hide()
        else:
            self._thumbnail_label.show()

    def _crop_thumbnail(self, thumbnail: Image, active_label_width: int) -> Image:
        """Process an image thumbnail for proper display."""
        # Calculate dimensions while respecting container padding
        available_width = active_label_width - (self._padding['left'] + self._padding['right'])
        new_width = available_width + self._thumbnail_padding
        
        # Preserve aspect ratio during resize
        aspect_ratio = thumbnail.width / thumbnail.height
        new_height = int(new_width / aspect_ratio)
        
        # Resize with high-quality resampling
        thumbnail = thumbnail.resize((new_width, new_height), Image.LANCZOS)
        
        # Crop vertically to fit widget height
        available_height = self._widget_frame.size().height() - (self._padding['top'] + self._padding['bottom'])
        if thumbnail.height > available_height:
            y1 = (thumbnail.height - available_height) // 2
            thumbnail = thumbnail.crop((0, y1, thumbnail.width, y1 + available_height))
        
        # Apply base transparency
        if thumbnail.mode != 'RGBA':
            thumbnail = thumbnail.convert('RGBA')
        
        # Create base alpha channel filled with the thumbnail alpha value
        base_alpha = Image.new('L', thumbnail.size, color=self._thumbnail_alpha)
        
        # Apply effects based on priorities
        if self._thumbnail_edge_fade:
            # If edge fade is enabled, use it without corner radius
            base_alpha = self._apply_edge_fade(base_alpha)
        elif self._thumbnail_corner_radius > 0:
            # Only apply corner radius if edge fade is disabled
            base_alpha = self._create_corner_mask(thumbnail.size, base_alpha)

        # Apply final alpha channel
        thumbnail.putalpha(base_alpha)
        return thumbnail

    def _create_corner_mask(self, image_size: tuple, base_mask: Image) -> Image:
        """Create a rounded corner mask compatible with the base alpha mask."""
        # Determine which corners to round
        corners = (False, True, True, False) if self._controls_left else (True, False, False, True)
        if self._symmetric_corner_radius:
            corners = (True, True, True, True)
        
        # Use a higher resolution for better antialiasing
        scale_factor = 2
        hr_size = (image_size[0] * scale_factor, image_size[1] * scale_factor)
        hr_radius = self._thumbnail_corner_radius * scale_factor
        
        # Create the high-resolution mask
        corner_mask = Image.new('L', hr_size, color=0)
        painter = ImageDraw(corner_mask)
        
        try:
            # Draw rounded rectangle
            painter.rounded_rectangle(
                [0, 0, hr_size[0] - 1, hr_size[1] - 1],
                hr_radius,
                self._thumbnail_alpha,
                None,
                0,
                corners=corners
            )
        except Exception as e:
            logging.error(f"Error creating corner mask, return default thumb: {e}")
            return base_mask
        
        # Scale back down with antialiasing
        corner_mask = corner_mask.resize(image_size, Image.LANCZOS)

        return corner_mask

    def _apply_edge_fade(self, alpha_mask: Image) -> Image:
        """Apply edge fade effect to an alpha mask."""

        width, height = alpha_mask.size
        fade_width = int(width * 0.3)
        fade_mask = Image.new('L', (width, height), color=255)
        
        # Create gradient arrays for better performance
        left_gradient = [int(255 * (x / fade_width)) for x in range(fade_width)]
        right_gradient = [int(255 * ((width - x) / fade_width)) for x in range(width - fade_width, width)]
        
        # Apply gradients
        for x, alpha in enumerate(left_gradient):
            line = Image.new('L', (1, height), color=alpha)
            fade_mask.paste(line, (x, 0))
        
        for i, x in enumerate(range(width - fade_width, width)):
            line = Image.new('L', (1, height), color=right_gradient[i])
            fade_mask.paste(line, (x, 0))
        
        # Use ImageChops.darker instead of multiply to preserve corner transparency
        return ImageChops.darker(alpha_mask, fade_mask)

    def _format_max_field_size(self, text: str):
        max_field_size = self._max_field_size['label_alt' if self._show_alt_label else 'label']
        if len(text) > max_field_size:
            return text[:max_field_size - 3] + '...'
        else:
            return text

    def _create_media_button(self, icon, action):
        if not self._controls_hide:
            label = ClickableLabel(self)
            label.setProperty("class", "btn")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setText(icon)
            label.data = action
            self._widget_container_layout.addWidget(label)
            return label

    def _create_media_buttons(self):
        return (self._create_media_button(self._media_button_icons['prev_track'], WindowsMedia().prev),
                self._create_media_button(self._media_button_icons['play'], WindowsMedia().play_pause),
                self._create_media_button( self._media_button_icons['next_track'], WindowsMedia().next))

    def execute_code(self, func):
        try:
            func()
        except Exception as e:
            logging.error(f"Error executing code: {e}")

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.media.switch_session(+1) # Next
        elif event.angleDelta().y() < 0:
            self.media.switch_session(-1) # Prev
            
class ClickableLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.data = None 

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.data:
            if self.parent_widget._animation['enabled']:
                AnimationManager.animate(self, self.parent_widget._animation['type'], self.parent_widget._animation['duration'])
            self.parent_widget.execute_code(self.data)