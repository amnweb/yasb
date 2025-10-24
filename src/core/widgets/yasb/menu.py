import logging
import os
import subprocess

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, is_valid_qobject
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.system_function import function_map
from core.validation.widgets.yasb.menu import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class MenuWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        label: str,
        class_name: str,
        menu_items: list[dict[str]],
        icon: str,
        image_icon_size: int,
        popup_image_icon_size: int,
        animation: dict[str, str],
        tooltip: bool,
        container_padding: dict[str, int],
        popup_padding: dict[str, int],
        blur: bool,
        popup_offset: dict[str, int],
        alignment: str,
        direction: str,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name=f"menu-widget {class_name}")
        self._label = label
        self._icon = icon
        self._menu_items = menu_items
        self._padding = container_padding
        self._popup_padding = popup_padding
        self._image_icon_size = image_icon_size
        self._popup_image_icon_size = popup_image_icon_size
        self._animation = animation
        self._tooltip = tooltip
        self._blur = blur
        self._popup_offset = popup_offset
        self._alignment = alignment
        self._direction = direction
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._popup = None

        # Construct container
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )

        # Initialize container
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)

        # Create the menu button container
        self._button_container = QWidget()
        self._button_layout = QHBoxLayout(self._button_container)
        self._button_layout.setSpacing(4)
        self._button_layout.setContentsMargins(0, 0, 0, 0)

        # Create icon label if icon is provided
        if self._icon:
            self._icon_label = ClickableLabel(self)
            self._icon_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._icon_label.setProperty("class", "icon")
            self._icon_label.clicked.connect(self._toggle_popup)

            if os.path.isfile(self._icon):
                pixmap = QPixmap(self._icon).scaled(
                    self._image_icon_size,
                    self._image_icon_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._icon_label.setPixmap(pixmap)
            else:
                self._icon_label.setText(self._icon)

            add_shadow(self._icon_label, self._label_shadow)
            self._button_layout.addWidget(self._icon_label)

        # Create text label if label is provided
        if self._label:
            self._text_label = ClickableLabel(self)
            self._text_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._text_label.setProperty("class", "label")
            self._text_label.setText(self._label)
            self._text_label.clicked.connect(self._toggle_popup)

            add_shadow(self._text_label, self._label_shadow)
            self._button_layout.addWidget(self._text_label)

        # Set tooltip
        if self._tooltip:
            tooltip_text = self._label if self._label else "Menu"
            set_tooltip(self._button_container, tooltip_text, 0)

        # Add button container to widget container
        self._widget_container_layout.addWidget(self._button_container)

        # Add the container to the main widget layout
        self.widget_layout.addWidget(self._widget_container)

    def _toggle_popup(self):
        """Toggle the menu popup visibility."""
        try:
            if self._popup and is_valid_qobject(self._popup) and self._popup.isVisible():
                self._popup.hide_animated()
            else:
                self._show_popup()
        except RuntimeError:
            # Popup was deleted, create a new one
            self._show_popup()

    def _show_popup(self):
        """Create and show the popup menu."""
        # Close existing popup if any
        try:
            if self._popup and is_valid_qobject(self._popup):
                self._popup.hide()
        except RuntimeError:
            pass

        # Create new popup
        self._popup = PopupWidget(
            parent=self._widget_container,
            blur=self._blur,
            round_corners=True,
            round_corners_type="normal",
            border_color="None",
        )
        self._popup.setProperty("class", "menu-popup")
        # Prevent click-through to windows behind the popup
        self._popup.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay)

        # Create popup layout directly on the PopupWidget (like media.py does)
        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setSpacing(0)
        popup_layout.setContentsMargins(
            self._popup_padding["left"],
            self._popup_padding["top"],
            self._popup_padding["right"],
            self._popup_padding["bottom"],
        )

        # Add menu items directly to the popup layout
        if isinstance(self._menu_items, list):
            for item_data in self._menu_items:
                if "icon" in item_data and "launch" in item_data:
                    # Create menu item
                    item = MenuItemWidget(
                        parent=self,
                        icon=item_data["icon"],
                        label=item_data.get("name", ""),
                        launch=item_data["launch"],
                        icon_size=self._popup_image_icon_size,
                        animation=self._animation,
                        tooltip=self._tooltip,
                    )
                    popup_layout.addWidget(item)

        # Adjust popup size to content
        self._popup.adjustSize()

        # Force Qt to apply the stylesheet to the popup and its children
        self._popup.style().unpolish(self._popup)
        self._popup.style().polish(self._popup)
        self._popup._popup_content.style().unpolish(self._popup._popup_content)
        self._popup._popup_content.style().polish(self._popup._popup_content)

        # Position and show popup
        self._popup.setPosition(
            alignment=self._alignment,
            direction=self._direction,
            offset_left=self._popup_offset["left"],
            offset_top=self._popup_offset["top"],
        )
        self._popup.show()

    def execute_code(self, data):
        """Execute the command associated with a menu item."""
        try:
            if data in function_map:
                function_map[data]()
            else:
                try:
                    if not any(param in data for param in ["-new-tab", "-new-window", "-private-window"]):
                        data = data.split()
                    subprocess.Popen(data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
                except Exception as e:
                    logging.error(f"Error starting app: {str(e)}")

            # Close popup after executing command
            try:
                if self._popup and is_valid_qobject(self._popup) and self._popup.isVisible():
                    self._popup.hide_animated()
            except RuntimeError:
                pass
        except Exception as e:
            logging.error(f'Exception occurred: {str(e)} "{data}"')


class ClickableLabel(QLabel):
    """A label that emits a signal when clicked."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class MenuItemWidget(QFrame):
    """A single menu item in the popup."""

    def __init__(self, parent, icon, label, launch, icon_size, animation, tooltip):
        super().__init__()
        self.parent_widget = parent
        self._launch = launch
        self._animation = animation

        self.setProperty("class", "menu-item")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Create layout
        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Create icon label
        self._icon_label = QLabel()
        self._icon_label.setProperty("class", "icon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if os.path.isfile(icon):
            pixmap = QPixmap(icon).scaled(
                icon_size,
                icon_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._icon_label.setPixmap(pixmap)
        else:
            self._icon_label.setText(icon)

        layout.addWidget(self._icon_label)

        # Create text label
        self._text_label = QLabel(label)
        self._text_label.setProperty("class", "label")
        layout.addWidget(self._text_label, stretch=1)

        if tooltip and label:
            set_tooltip(self, label, 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()  # Accept the event to prevent propagation
            if self._animation["enabled"]:
                AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
            self.parent_widget.execute_code(self._launch)
        else:
            super().mousePressEvent(event)
