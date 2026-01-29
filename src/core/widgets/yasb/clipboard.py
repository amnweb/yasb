import base64
import json
import logging
import os
import re

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from core.config import HOME_CONFIGURATION_DIR
from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.clipboard import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG


def get_clipboard_text() -> str:
    """Get the current text content from clipboard using Qt API."""
    try:
        clipboard = QApplication.clipboard()
        if clipboard:
            return clipboard.text() or ""
    except Exception:
        pass
    return ""


class ClipboardWidget(BaseWidget):
    """
    A clipboard history widget for yasb.

    Features:
    - Monitors Windows clipboard and stores text history
    - Pin important items to persist across restarts
    - Search through clipboard history
    - Clear history functionality
    """

    validation_schema = VALIDATION_SCHEMA
    _instances = []

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        max_length: int,
        max_history: int,
        data_path: str,
        container_padding: dict,
        animation: dict,
        menu: dict,
        icons: dict,
        callbacks: dict,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name=f"clipboard-widget {class_name}")
        ClipboardWidget._instances.append(self)

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._max_length = max_length
        self._max_history = max_history
        self._animation = animation
        self._padding = container_padding
        self._menu_config = menu
        self._icons = icons
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        self._last_clipboard = ""
        self._search_query = ""

        # Data storage path
        if data_path and data_path.strip():
            self._data_file = os.path.expanduser(data_path)
        else:
            self._data_file = os.path.join(HOME_CONFIGURATION_DIR, "clipboard.json")

        self._data = self._load_data()

        # Initialize container layout
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(
            self._padding["left"], self._padding["top"], self._padding["right"], self._padding["bottom"]
        )

        # Initialize container widget
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        build_widget_label(self, self._label_content, self._label_alt_content, self._label_shadow)

        # Register callbacks
        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("clear_history", self._clear_history)
        self.register_callback("update_label", self._update_label)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"

        # Clipboard monitoring timer
        self._clipboard_timer = QTimer(self)
        self._clipboard_timer.timeout.connect(self._check_clipboard)
        self._clipboard_timer.start(1000)  # Check every second

        self._update_label()

    def __del__(self):
        try:
            ClipboardWidget._instances.remove(self)
        except ValueError:
            pass

    @classmethod
    def update_all(cls):
        """Update all instances of ClipboardWidget."""
        for instance in cls._instances:
            instance._data = instance._load_data()
            instance._update_label()

    def _toggle_label(self):
        """Toggle between primary and alternate labels."""
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])

        self._show_alt_label = not self._show_alt_label

        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)

        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)

        self._update_label()

    def _toggle_menu(self):
        """Toggle the clipboard history popup menu."""
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_menu()

    def _check_clipboard(self):
        """Check clipboard for new content and add to history."""
        current_text = get_clipboard_text() or ""
        if current_text and current_text != self._last_clipboard:
            self._last_clipboard = current_text
            # Only add if not already in pinned or history
            if current_text not in self._data["pinned"] and current_text not in self._data["history"]:
                self._data["history"].insert(0, current_text)
                self._data["history"] = self._data["history"][: self._max_history]
                self._save_data()
            self._update_label()

    def _update_label(self):
        """Update the widget label with current clipboard content."""
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content

        label_parts = re.split(r"(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]

        # Get current clipboard display text
        current_text = self._last_clipboard or get_clipboard_text() or ""
        display_text = current_text.replace("\n", " ").replace("\r", "").strip()
        if len(display_text) > self._max_length:
            display_text = display_text[: self._max_length] + "..."
        if not display_text:
            display_text = "Empty"

        for widget_index, part in enumerate(label_parts):
            if widget_index >= len(active_widgets) or not isinstance(active_widgets[widget_index], QLabel):
                continue

            current_widget = active_widgets[widget_index]

            if "<span" in part and "</span>" in part:
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                current_widget.setText(icon)
            else:
                formatted_text = part.format(clipboard=display_text)
                current_widget.setText(formatted_text)

    def _show_menu(self):
        """Display the clipboard history popup menu."""
        self._menu = PopupWidget(
            self,
            self._menu_config["blur"],
            self._menu_config["round_corners"],
            self._menu_config["round_corners_type"],
            self._menu_config["border_color"],
        )
        self._menu.setProperty("class", "clipboard-menu")

        # Main layout
        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Search bar container
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(8, 8, 8, 8)
        search_layout.setSpacing(5)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search clipboard history...")
        self._search_input.setProperty("class", "search-input")
        self._search_input.textChanged.connect(self._on_search_changed)

        # Search wrapper to include clear button inside
        search_wrapper = QWidget()
        search_wrapper.setProperty("class", "search-wrapper")
        wrapper_layout = QHBoxLayout(search_wrapper)
        wrapper_layout.setContentsMargins(0, 0, 4, 0)
        wrapper_layout.setSpacing(0)

        # Inner input needs transparent background in CSS
        self._search_input.setProperty("class", "search-input-inner")

        wrapper_layout.addWidget(self._search_input, 1)

        # Clear search button
        self._search_clear_btn = QPushButton(self._icons.get("search_clear", "\uf00d"))
        self._search_clear_btn.setProperty("class", "search-clear-button")
        self._search_clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._search_clear_btn.setFixedSize(20, 20)
        self._search_clear_btn.clicked.connect(self._search_input.clear)
        self._search_clear_btn.hide()

        # Show/hide clear button based on text
        self._search_input.textChanged.connect(lambda t: self._search_clear_btn.setVisible(bool(t)))

        wrapper_layout.addWidget(self._search_clear_btn)

        search_layout.addWidget(search_wrapper, 1)

        # Clear history button
        clear_btn = QPushButton(f"{self._icons['clear']} History")
        clear_btn.setProperty("class", "clear-button")
        clear_btn.setToolTip("Clear clipboard history (keeps pinned)")
        clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear_btn.clicked.connect(self._clear_history_and_refresh)
        search_layout.addWidget(clear_btn)

        # Persistence toggle button
        is_persistent = self._data.get("settings", {}).get("persistence", True)
        self._persist_btn = QPushButton(self._icons["persistent"] if is_persistent else self._icons["temporary"])
        self._persist_btn.setProperty("class", "persistence-button-active" if is_persistent else "persistence-button")
        self._persist_btn.setToolTip(f"History Persistence: {'ON' if is_persistent else 'OFF'}")
        self._persist_btn.setFixedSize(28, 28)
        self._persist_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._persist_btn.clicked.connect(self._toggle_persistence)
        search_layout.addWidget(self._persist_btn)

        main_layout.addWidget(search_container)

        # Scroll area for items
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setProperty("class", "scroll-area")
        scroll_area.setViewportMargins(0, 0, -4, 0)
        scroll_area.setStyleSheet("""
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
        """)

        scroll_widget = QWidget()
        scroll_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._scroll_layout = QVBoxLayout(scroll_widget)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(0)

        scroll_area.setWidget(scroll_widget)

        self._refresh_list()

        main_layout.addWidget(scroll_area)

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self._menu_config["alignment"],
            direction=self._menu_config["direction"],
            offset_left=self._menu_config["offset_left"],
            offset_top=self._menu_config["offset_top"],
        )
        self._menu.show()
        self._search_input.setFocus()

    def _refresh_list(self):
        """Refresh the items list in the popup menu."""
        # Clear existing items
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        query = self._search_query.lower()
        pinned = [t for t in self._data["pinned"] if query in t.lower()]
        history = [t for t in self._data["history"] if query in t.lower()]

        if pinned:
            self._add_section_header("PINNED")
            for text in pinned:
                self._add_item_row(text, is_pinned=True)

        if history:
            self._add_section_header("RECENT")
            for text in history:
                self._add_item_row(text, is_pinned=False)

        if not pinned and not history:
            empty_label = QLabel(f"{self._icons['clipboard']}  No items found")
            empty_label.setProperty("class", "empty-list")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._scroll_layout.addWidget(empty_label)

        # Add spacer at bottom
        self._scroll_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Resize menu to fit new content
        if hasattr(self, "_menu") and self._menu:
            self._menu.adjustSize()

    def _add_section_header(self, text: str):
        """Add a section header to the list."""
        header = QLabel(text)
        header.setProperty("class", "section-header")
        self._scroll_layout.addWidget(header)

    def _get_image_from_base64(self, text: str) -> QPixmap | None:
        """Convert base64 text to QPixmap if valid image."""
        if not text.startswith("data:image/") or ";base64," not in text:
            return None

        try:
            # Extract base64 data
            _, data_str = text.split(";base64,")
            data = base64.b64decode(data_str)
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                return pixmap
        except Exception:
            pass
        return None

    def _add_item_row(self, text: str, is_pinned: bool):
        """Add an item row to the list."""
        container = QWidget()
        container.setProperty("class", "clipboard-item")
        container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Content
        pixmap = self._get_image_from_base64(text)

        if pixmap:
            # Display image
            image_label = QLabel()
            image_label.setPixmap(
                pixmap.scaled(300, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
            image_label.setProperty("class", "item-image")
            layout.addWidget(image_label, 1)
        else:
            # Display text
            max_len = self._menu_config["max_item_length"]
            display_text = text.replace("\n", " ").replace("\r", "").strip()
            if len(display_text) > max_len:
                display_text = display_text[:max_len] + "..."

            text_label = QLabel(display_text)
            text_label.setProperty("class", "item-text")
            text_label.setWordWrap(False)
            layout.addWidget(text_label, 1)

        # Pin/unpin button
        pin_btn = QPushButton(self._icons["pin"] if is_pinned else self._icons["unpin"])
        pin_btn.setProperty("class", "pin-button-active" if is_pinned else "pin-button")
        pin_btn.setFixedWidth(28)
        pin_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        pin_btn.clicked.connect(lambda _, t=text, p=is_pinned: self._toggle_pin(t, p))
        layout.addWidget(pin_btn)

        # Delete button
        del_btn = QPushButton(self._icons["clear"])
        del_btn.setProperty("class", "delete-button")
        del_btn.setFixedWidth(28)
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.clicked.connect(lambda _, t=text, p=is_pinned: self._delete_item(t, p))
        layout.addWidget(del_btn)

        # Click on container to copy
        container.mousePressEvent = (
            lambda e, t=text: self._copy_item(t) if e.button() == Qt.MouseButton.LeftButton else None
        )

        self._scroll_layout.addWidget(container)

    def _toggle_pin(self, text: str, is_pinned: bool):
        """Toggle pin status of an item."""
        if is_pinned:
            if text in self._data["pinned"]:
                self._data["pinned"].remove(text)
            self._data["history"].insert(0, text)
        else:
            if text in self._data["history"]:
                self._data["history"].remove(text)
            self._data["pinned"].insert(0, text)

        self._save_data()
        self._refresh_list()

    def _delete_item(self, text: str, is_pinned: bool):
        """Delete an item from history or pinned list."""
        if is_pinned:
            if text in self._data["pinned"]:
                self._data["pinned"].remove(text)
        else:
            if text in self._data["history"]:
                self._data["history"].remove(text)

        self._save_data()
        self._refresh_list()

    def _copy_item(self, text: str):
        """Copy an item to clipboard and close menu."""

        pixmap = self._get_image_from_base64(text)
        if pixmap:
            QApplication.clipboard().setPixmap(pixmap)
        else:
            QApplication.clipboard().setText(text)

        self._last_clipboard = text
        self._update_label()
        if hasattr(self, "_menu"):
            self._menu.hide()

    def _clear_history(self):
        """Clear clipboard history (keeps pinned items)."""
        self._data["history"] = []
        self._save_data()
        ClipboardWidget.update_all()

    def _clear_history_and_refresh(self):
        """Clear history and refresh the menu."""
        self._clear_history()
        self._refresh_list()

    def _on_search_changed(self, text: str):
        """Handle search input changes."""
        self._search_query = text
        self._refresh_list()

    def _toggle_persistence(self):
        """Toggle clipboard history persistence."""
        if "settings" not in self._data:
            self._data["settings"] = {}

        current = self._data["settings"].get("persistence", True)
        new_state = not current
        self._data["settings"]["persistence"] = new_state

        # Update button
        if hasattr(self, "_persist_btn"):
            self._persist_btn.setText(self._icons["persistent"] if new_state else self._icons["temporary"])
            self._persist_btn.setProperty("class", "persistence-button-active" if new_state else "persistence-button")
            self._persist_btn.setToolTip(f"History Persistence: {'ON' if new_state else 'OFF'}")

            # Force style refresh
            self._persist_btn.style().unpolish(self._persist_btn)
            self._persist_btn.style().polish(self._persist_btn)

        self._save_data()

    def _load_data(self) -> dict:
        """Load clipboard data from JSON file."""
        try:
            if os.path.exists(self._data_file):
                if DEBUG:
                    logging.debug(f"Loading clipboard data from {self._data_file}")
                with open(self._data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Ensure proper structure
                    if "pinned" not in data:
                        data["pinned"] = []
                    if "history" not in data:
                        data["history"] = []
                    if "settings" not in data:
                        data["settings"] = {"persistence": True}
                    return data
        except Exception as e:
            logging.error(f"Error loading clipboard data: {e}")

        return {"pinned": [], "history": []}

    def _save_data(self):
        """Save clipboard data to JSON file."""
        try:
            os.makedirs(os.path.dirname(self._data_file), exist_ok=True)

            # Prepare data dump (handle persistence)
            persistence = self._data.get("settings", {}).get("persistence", True)

            dump_data = {
                "pinned": self._data["pinned"],
                "settings": self._data.get("settings", {"persistence": True}),
                # Only save history to disk if persistence is ON
                "history": self._data["history"] if persistence else [],
            }

            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving clipboard data: {e}")
