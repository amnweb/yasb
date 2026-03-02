import logging
import os
import re
from ctypes import windll

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from core.utils.tooltip import set_tooltip
from core.utils.utilities import PopupWidget, add_shadow, is_valid_qobject, refresh_widget_style
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.widgets.update_check.service import UpdateCheckService
from core.validation.widgets.yasb.update_check import UpdateCheckWidgetConfig
from core.widgets.base import BaseWidget

logger = logging.getLogger("UpdateCheckWidget")

# Sources and their config attribute names
_SOURCES = ("winget", "scoop", "windows")


class UpdateCheckWidget(BaseWidget):
    validation_schema = UpdateCheckWidgetConfig

    def __init__(self, config: UpdateCheckWidgetConfig):
        super().__init__(class_name="update-check-widget")
        self.config = config

        self._containers: dict[str, QFrame | None] = {}
        self._label_widgets: dict[str, list[QLabel]] = {}
        self._counts: dict[str, int] = {}

        # Create a variable for the popup
        self._popup = None

        # Variables in the WindowsUpdateConfig that will be populated via "for source in _SOURCES" below
        self._show_popup_menu = False
        self._popup_menu_padding = 0  # Default value will be set via the WindowsUpdateConfig

        # These are the two hard-coded menu items to show in the popup - just the metadata - the execution commands happen below
        self._popup_menu_items = [
            {"icon": "\ue62a", "launch": "windows_update", "name": "Open Windows Update"},
            {"icon": "\udb84\udfb6", "launch": "update_virus_defs", "name": "Update Virus Definitions"},
        ]

        # Set up defaults for all variables that are used for the popup but for which we do not yet have configuration / validation schema
        self._container_shadow = None
        self._blur = False
        self._popup_image_icon_size = 16
        self._animation = {"enabled": True, "type": "fadeInOut", "duration": 200}
        self._alignment = "center"
        self._direction = "down"
        self._popup_offset = {"top": 8, "left": 0}

        for source in _SOURCES:
            cfg = getattr(self.config, f"{source}_update", None)
            if cfg and cfg.enabled:
                container, widgets = self._create_container(source, cfg.label)
                self._containers[source] = container
                self._label_widgets[source] = widgets
                if source == "windows":
                    self._show_popup_menu = cfg.show_popup_menu
                    self._popup_menu_padding = cfg.popup_menu_padding
            else:
                self._containers[source] = None
                self._label_widgets[source] = []
            self._counts[source] = 0

        # Register with shared service
        self._service = UpdateCheckService()
        self._service.register_widget(self)

        self._update_visibility()

    def on_update(self, source: str, result: dict):
        """Receive update data from the service."""
        count = result.get("count", 0)
        names = result.get("names", [])
        self._counts[source] = count
        self._update_labels(source, count, names)
        self._update_visibility()

    def _create_container(self, source: str, label_text: str) -> tuple[QFrame, list[QLabel]]:
        """Create a container with label widgets for a source."""
        container = QFrame()
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        container.setLayout(layout)
        container.setProperty("class", f"widget-container {source}")
        add_shadow(container, self.config.container_shadow.model_dump())
        self.widget_layout.addWidget(container)
        container.hide()

        label_parts = re.split(r"(<span.*?>.*?</span>)", label_text)
        label_parts = [p for p in label_parts if p]
        widgets: list[QLabel] = []

        for part in label_parts:
            part = part.strip()
            if not part:
                continue
            if "<span" in part and "</span>" in part:
                class_match = re.search(r'class=(["\'])([^"\']+?)\1', part)
                class_result = class_match.group(2) if class_match else "icon"
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                label = QLabel(icon)
                label.setProperty("class", class_result)
            else:
                label = QLabel(part)
                label.setProperty("class", "label")

            add_shadow(label, self.config.label_shadow.model_dump())
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            widgets.append(label)
            label.mousePressEvent = self._make_mouse_handler(source)

        return container, widgets

    def _update_labels(self, source: str, count: int, names: list[str]):
        """Update text in label widgets for a source."""
        container = self._containers.get(source)
        if container is None:
            return

        if count == 0:
            container.hide()
            return

        container.show()
        cfg = getattr(self.config, f"{source}_update", None)
        if cfg is None:
            return

        label_parts = re.split(r"(<span.*?>.*?</span>)", cfg.label)
        label_parts = [p for p in label_parts if p]
        widgets = self._label_widgets.get(source, [])
        idx = 0

        for part in label_parts:
            part = part.strip()
            if not part or idx >= len(widgets):
                continue
            w = widgets[idx]
            if not isinstance(w, QLabel):
                idx += 1
                continue

            if "<span" in part and "</span>" in part:
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                w.setText(icon)
            else:
                w.setText(part.format(count=count))
            w.setCursor(Qt.CursorShape.PointingHandCursor)
            idx += 1

        if cfg.tooltip:
            title = {"winget": "Winget Update", "scoop": "Scoop Update", "windows": "Windows Update"}.get(
                source, source
            )
            body = "<br>".join(names)
            set_tooltip(container, f"<b>{title}</b><br><br>{body}")

    def _update_visibility(self):
        """Show/hide widget and adjust paired styling."""
        visible_sources = [s for s in _SOURCES if self._counts.get(s, 0) > 0]

        for source in _SOURCES:
            container = self._containers.get(source)
            if container is None:
                continue
            if source in visible_sources:
                idx = visible_sources.index(source)
                has_left = idx > 0
                has_right = idx < len(visible_sources) - 1
                self._set_container_class(container, source, has_left, has_right)
            else:
                self._set_container_class(container, source, False, False)

        if visible_sources:
            self.show()
        else:
            self.hide()

        refresh_widget_style(self)

    def _set_container_class(self, container: QFrame, base_class: str, has_left: bool, has_right: bool):
        """Set the CSS class on a container."""
        class_name = f"widget-container {base_class}"
        if has_left:
            class_name += " paired-left"
        if has_right:
            class_name += " paired-right"
        container.setStyleSheet("")
        container.setProperty("class", class_name)
        container.setStyleSheet(container.styleSheet())
        refresh_widget_style(container)

    def _make_mouse_handler(self, source: str):
        """Create a mouse event handler for a source container."""

        def handler(event):
            if event.button() == Qt.MouseButton.LeftButton:
                if source == "windows":
                    if self._show_popup_menu == True:
                        self._toggle_popup()
                    else:
                        self._service.handle_left_click("windows")
                else:
                    self._service.handle_left_click(source)
            elif event.button() == Qt.MouseButton.RightButton:
                self._service.handle_right_click(source)

        return handler

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
            parent=self, blur=self._blur, round_corners=True, round_corners_type="normal", border_color="None"
        )
        self._popup.setProperty("class", "widget-container windows menu-popup")

        # Prevent click-through to windows behind the popup
        self._popup.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay)

        # Create popup layout directly on the PopupWidget (like media.py does)
        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setSpacing(0)
        popup_layout.setContentsMargins(
            self._popup_menu_padding,
            self._popup_menu_padding,
            self._popup_menu_padding,
            self._popup_menu_padding,
        )

        # Add menu items directly to the popup layout
        if isinstance(self._popup_menu_items, list):
            item = self.create_menu_item(
                item_data=self._popup_menu_items[0],
                parent=self,
                icon_size=self._popup_image_icon_size,
                animation=self._animation,
                bottom_padding=self._popup_menu_padding,
            )
            popup_layout.addWidget(item)

            item = self.create_menu_item(
                item_data=self._popup_menu_items[1],
                parent=self,
                icon_size=self._popup_image_icon_size,
                animation=self._animation,
                bottom_padding=0,
            )
            popup_layout.addWidget(item)

        # Adjust popup size to content
        self._popup.adjustSize()

        # Force Qt to apply the stylesheet to the popup and its children (guard against None)
        popup_style = self._popup.style()
        if popup_style is not None:
            popup_style.unpolish(self._popup)
            popup_style.polish(self._popup)

        popup_content = getattr(self._popup, "_popup_content", None)
        if popup_content is not None:
            content_style = popup_content.style()
            if content_style is not None:
                content_style.unpolish(popup_content)
                content_style.polish(popup_content)

        # Position and show popup
        self._popup.setPosition(
            alignment=self._alignment,
            direction=self._direction,
            offset_left=self._popup_offset["left"],
            offset_top=self._popup_offset["top"],
        )
        self._popup.show()

    def create_menu_item(self, item_data, parent, icon_size, animation, bottom_padding):
        if "icon" in item_data and "launch" in item_data:
            # Create menu item
            item = MenuItemWidget(
                parent=parent,
                icon=item_data["icon"],
                label=item_data.get("name", ""),
                launch=item_data["launch"],
                icon_size=icon_size,
                animation=animation,
                bottom_padding=bottom_padding,
            )
            return item

    def execute_code(self, data):
        """Execute the command associated with a menu item."""
        try:
            try:
                if data == "windows_update":
                    self._service.handle_left_click("windows")
                elif data == "update_virus_defs":
                    # Execute the Windows Defender command to update signatures
                    exePath = r"C:\Program Files\Windows Defender\MpCmdRun.exe"
                    parameters = r"-SignatureUpdate"
                    windll.shell32.ShellExecuteW(
                        None,
                        "runas",
                        exePath,
                        parameters,
                        None,
                        1,
                    )
                    # Run the right-click command too, to tell the service to clear and refresh
                    self._service.handle_right_click("windows")

            except Exception as e:
                logger.error(f"Error executing popup menu choice: {str(e)}")

            # Close popup after executing command
            try:
                if self._popup and is_valid_qobject(self._popup) and self._popup.isVisible():
                    self._popup.hide_animated()
            except RuntimeError:
                pass
        except Exception as e:
            logger.error(f'Exception occurred: {str(e)} "{data}"')


class MenuItemWidget(QFrame):
    """A single menu item in the popup."""

    def __init__(self, parent, icon, label, launch, icon_size, animation, bottom_padding):
        super().__init__()
        self.parent_widget = parent
        self._launch = launch
        self._animation = animation
        self._bottom_padding = bottom_padding

        self.setProperty("class", "menu-item")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.setStyleSheet(f"QFrame .menu-item {{ margin-bottom: {self._bottom_padding}px; }}")

        # Create layout
        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(3, 3, 3, 3)

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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()  # Accept the event to prevent propagation
            if self._animation["enabled"]:
                AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
            self.parent_widget.execute_code(self._launch)
        else:
            super().mousePressEvent(event)
