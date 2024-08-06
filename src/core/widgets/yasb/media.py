import logging
import time

from PIL import Image, ImageStat
from PIL.ImageDraw import ImageDraw
from PIL.ImageQt import QPixmap
from PyQt6.QtCore import Qt
from qasync import asyncSlot
from PIL.ImageQt import ImageQt
from core.utils.win32.media import MediaOperations
from core.widgets.base import BaseWidget
from core.validation.widgets.yasb.media import VALIDATION_SCHEMA
from PyQt6.QtWidgets import QLabel, QGridLayout, QHBoxLayout, QWidget, QVBoxLayout
from core.widgets.yasb.applications import ClickableLabel


class MediaWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(self, label_main: str, label_sub: str, hide_empty:bool, update_interval: int, callbacks: dict[str, str],
                 max_field_size: dict[str, int], show_thumbnail: bool, controls_only: bool, controls_left: bool,
                 thumbnail_alpha_multiplier: float,
                 thumbnail_alpha_range: float,
                 thumbnail_padding: int,
                 thumbnail_corner_radius: int,
                 icons: dict[str, str]):
        super().__init__(update_interval, class_name="media-widget")
        self._label_main_content = label_main
        self._label_sub_content = label_sub

        self._max_field_size = max_field_size
        self._show_thumbnail = show_thumbnail
        self._thumbnail_alpha_multiplier = thumbnail_alpha_multiplier
        self._thumbnail_alpha_range = thumbnail_alpha_range
        self._media_button_icons = icons
        self._controls_only = controls_only
        self._controls_left = controls_left
        self._thumbnail_padding = thumbnail_padding
        self._thumbnail_corner_radius = thumbnail_corner_radius
        self._hide_empty = hide_empty

        # Construct container
        self._widget_container_layout: QHBoxLayout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
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

        self._main_text_label = QLabel()
        self._sub_text_label = QLabel()

        self._main_text_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._sub_text_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._main_text_label.setProperty("class", "label maintext")
        self._sub_text_label.setProperty("class", "label subtext")

        self._text_layout = QVBoxLayout()
        self._text_layout.addWidget(self._main_text_label)
        self._text_layout.addWidget(self._sub_text_label)
        self._text_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._thumbnail_label = QLabel()
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.thumbnail_box.addWidget(self._thumbnail_label, 0, 0)
        self.thumbnail_box.addLayout(self._text_layout, 0, 0)

        self.register_callback("update_label", self._update_label)

        self.callback_left = callbacks['on_left']
        self.callback_right = callbacks['on_right']
        self.callback_middle = callbacks['on_middle']
        self.callback_timer = "update_label"

        if not self._controls_only:
            self._main_text_label.show()

        self._show_alt_label = False

        self.start_timer()

        self._last_title = None
        self._last_artist = None
        self._last_thumbnail = None

    @asyncSlot()
    async def _update_label(self):
        text_labels = [self._main_text_label, self._sub_text_label]

        try:
            media_info = await MediaOperations.get_media_properties()
        except Exception as e:
            logging.error(f"Error fetching media properties: {e}")
            return  # Exit early if there's an error

        # If no media is playing, set disable class on all buttons
        # Give next/previous buttons a different css class based on whether they are available
        disabled_if = lambda disabled: "disabled" if disabled else ""
        self._prev_label.setProperty("class", f"btn prev {disabled_if(media_info is None or not media_info['prev_available'])}")
        self._play_label.setProperty("class", f"btn play {disabled_if(media_info is None)}")
        self._next_label.setProperty("class", f"btn next {disabled_if(media_info is None or not media_info['next_available'])}")

        # Refresh style sheets
        self._prev_label.setStyleSheet('')
        self._play_label.setStyleSheet('')
        self._next_label.setStyleSheet('')

        # If nothing playing, hide thumbnail and empty text, stop here
        if media_info is None:
            # Hide thumbnail and label fields
            for label in text_labels:
                label.hide()
                label.setText('')
            self._play_label.setText(self._media_button_icons['play'])

            if self._hide_empty:
                self._widget_frame.hide()
            return

        # Change icon based on if song is playing
        self._play_label.setText(self._media_button_icons['pause' if media_info['playing'] else 'play'])

        # If media is not None, we show the frame
        self._widget_frame.show()

        # If we only have controls, stop update here
        if self._controls_only:
            return

        # If we are playing, make sure the label field is showing
        for label in text_labels:
            label.show()

        # Shorten fields if necessary with ...
        media_info = {k: self._format_max_field_size(v) if isinstance(v, str) else v for k, v in
                      media_info.items()}

        # Format the labels
        self._main_text_label.setText(self._label_main_content.format(**media_info))
        self._sub_text_label.setText(self._label_sub_content.format(**media_info))

        # If we don't want the thumbnail, stop here
        if not self._show_thumbnail:
            return

        # Catches odd cases where media info is not None, but title and artist fields are
        if media_info['title'] is None or media_info['artist'] is None:
            return

        # Only update the thumbnail if the title/artist changes or if we did a toggle (resize)
        if self._last_title == media_info['title'] and self._last_artist == media_info['artist']:
            return

        # If thumbnail reference is not there, stop here
        if media_info['thumbnail'] is None:
            return

        # Get thumbnail
        thumbnail = await MediaOperations.get_thumbnail(media_info['thumbnail'])

        # If the thumbnail image is the same as our previous, the title and artist changed but the thumbnail didn't
        # We return and wait until the thumbnail also changes before we do the update
        if self._last_thumbnail == thumbnail:
            return
        else:
            self._last_thumbnail = thumbnail
            self._last_title = media_info['title']
            self._last_artist = media_info['artist']

        self._thumbnail_label.show()

        thumbnail = self._process_thumbnail(thumbnail, self._text_layout.sizeHint().width())
        pixmap = QPixmap.fromImage(ImageQt(thumbnail))

        self._thumbnail_label.setPixmap(pixmap)

    def _process_thumbnail(self, thumbnail: Image, active_label_width: int) -> Image:
        # Scale image with 1:1 ratio to fit width of widget
        new_width = active_label_width + self._thumbnail_padding
        new_height = round(thumbnail.height * (new_width / thumbnail.width))
        thumbnail = thumbnail.resize((new_width, new_height))

        # Center crop the image in height direction
        new_h = self._widget_frame.size().height()
        y1 = (thumbnail.height - new_h) // 2
        thumbnail = thumbnail.crop((0, y1, thumbnail.width, y1 + new_h))

        # Calculate lightness to scale alpha
        thumbnail_alpha = (1.0 - self._thumbnail_alpha_range) * 255 + self._thumbnail_alpha_range * (255 - self._avg_lightness(thumbnail))
        thumbnail_alpha = round(self._thumbnail_alpha_multiplier * thumbnail_alpha)

        # If we want a rounded thumbnail, draw a rounded-corner mask and use it to make the image transparent
        if self._thumbnail_corner_radius > 0:
            corner_mask = Image.new('L', thumbnail.size, color=0)
            painter = ImageDraw(corner_mask)

            # If controls left, make right corners round and vice versa
            corners = (False, True, True, False) if self._controls_left else (True, False, False, True)

            # Paint alpha
            painter.rounded_rectangle([0, 0, thumbnail.width - 1, thumbnail.height - 1], self._thumbnail_corner_radius, thumbnail_alpha, None, 0, corners=corners)
            thumbnail.putalpha(corner_mask)
        else:
            thumbnail.putalpha(thumbnail_alpha)

        return thumbnail

    @staticmethod
    def _avg_lightness(im):
        im_l = im.convert('L')
        return sum(im_l.getdata()) / ImageStat.Stat(im_l).count[0]

    def _format_max_field_size(self, text: str):
        max_field_size = self._max_field_size['label_alt' if self._show_alt_label else 'label']
        if len(text) > max_field_size:
            return text[:max_field_size - 3] + '...'
        else:
            return text

    def _create_media_button(self, icon, action):
        label = ClickableLabel(self)
        label.setProperty("class", "btn")
        label.setText(icon)
        label.data = action
        self._widget_container_layout.addWidget(label)
        return label

    def _create_media_buttons(self):
        return self._create_media_button(self._media_button_icons['prev_track'],
                                         MediaOperations.prev), self._create_media_button(
            self._media_button_icons['play'], MediaOperations.play_pause), self._create_media_button(
            self._media_button_icons['next_track'], MediaOperations.next)

    def execute_code(self, func):
        try:
            func()
            time.sleep(0.1)
            self._update_label()
        except Exception as e:
            logging.error(f"Error executing code: {e}")
