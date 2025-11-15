import datetime
import json
import logging
import os
import re
from typing import Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config import HOME_CONFIGURATION_DIR
from core.utils.utilities import PopupWidget, add_shadow, build_widget_label
from core.utils.widgets.animation_manager import AnimationManager
from core.validation.widgets.yasb.notes import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG


class NotesWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    _instances = []

    def __init__(
        self,
        label: str,
        label_alt: str,
        class_name: str,
        data_path: str,
        container_padding: dict,
        animation: dict,
        menu: dict,
        icons: dict,
        callbacks: dict,
        label_shadow: dict = None,
        container_shadow: dict = None,
    ):
        super().__init__(class_name=f"notes-widget {class_name}")
        NotesWidget._instances.append(self)

        self._show_alt_label = False
        self._label_content = label
        self._label_alt_content = label_alt
        self._animation = animation
        self._padding = container_padding
        self._menu_config = menu
        self._icons = icons
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow

        # Use custom data path if provided, otherwise use default
        if data_path and data_path.strip():
            self._notes_file = os.path.expanduser(data_path)
        else:
            self._notes_file = os.path.join(HOME_CONFIGURATION_DIR, "notes.json")
        self._notes = self._load_notes()

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

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("update_label", self._update_label)

        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self.callback_timer = "update_label"

        self._update_label()

    def __del__(self):
        # Remove instance on deletion
        try:
            self._instances.remove(self)
        except ValueError:
            pass

    @classmethod
    def update_all(cls):
        """Update all instances of NotesWidget"""
        for instance in cls._instances:
            instance._notes = instance._load_notes()
            instance._update_label()

    def _toggle_label(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])

        self._show_alt_label = not self._show_alt_label

        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)

        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)

        self._update_label()

    def _toggle_menu(self):
        if self._animation["enabled"]:
            AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
        self._show_menu()

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content

        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]

        notes_count = len(self._notes)

        for widget_index, part in enumerate(label_parts):
            if widget_index >= len(active_widgets) or not isinstance(active_widgets[widget_index], QLabel):
                continue

            current_widget = active_widgets[widget_index]

            if "<span" in part and "</span>" in part:
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                current_widget.setText(icon)
            else:
                formatted_text = part.format(count=notes_count)
                current_widget.setText(formatted_text)
            widget_index += 1

    def _show_menu(self):
        self._menu = PopupWidget(
            self,
            self._menu_config["blur"],
            self._menu_config["round_corners"],
            self._menu_config["round_corners_type"],
            self._menu_config["border_color"],
        )
        self._menu.setProperty("class", "notes-menu")

        # Create main layout
        main_layout = QVBoxLayout(self._menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Add text input area with button row - MOVED TO TOP
        input_container = QWidget()
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(5)

        # Text input field
        self._note_input = NoteTextEdit(self)
        self._note_input.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._note_input.setPlaceholderText("Type your note here...")
        self._note_input.setProperty("class", "note-input")
        input_layout.addWidget(self._note_input)

        # Button row
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)

        # Add Note button
        self.add_button = QPushButton("Add Note")
        self.add_button.setProperty("class", "add-button")
        self.add_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_button.clicked.connect(self._add_note_from_input)
        button_layout.addWidget(self.add_button)

        # Cancel button (hidden by default)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("class", "cancel-button")
        self.cancel_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.cancel_button.clicked.connect(self._cancel_editing)
        self.cancel_button.hide()
        button_layout.addWidget(self.cancel_button)

        input_layout.addWidget(button_container)
        main_layout.addWidget(input_container)

        # Create scroll area for notes
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setProperty("class", "scroll-area")

        # Style the scrollbar
        scroll_area.setViewportMargins(0, 0, -4, 0)
        scroll_area.setStyleSheet("""
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
        """)

        # Create scroll widget and layout
        scroll_widget = QWidget()
        scroll_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        scroll_area.setWidget(scroll_widget)

        # Add notes to the scroll area
        if self._notes:
            for note in self._notes:
                self._add_note_to_menu(note, scroll_layout)
        else:
            # Show empty state
            empty_label = QLabel(f"{self._icons['note']}  No notes yet!")
            empty_label.setProperty("class", "empty-list")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scroll_layout.addWidget(empty_label)

        main_layout.addWidget(scroll_area)

        # Initialize edit mode tracking
        self._editing_note = None

        self._menu.adjustSize()
        self._menu.setPosition(
            alignment=self._menu_config["alignment"],
            direction=self._menu_config["direction"],
            offset_left=self._menu_config["offset_left"],
            offset_top=self._menu_config["offset_top"],
        )
        self._menu.show()
        self._note_input.setFocus()

    def _add_note_from_input(self):
        """Add a new note or save changes to an existing note"""
        note_text = self._note_input.toPlainText().strip()
        if not note_text:
            return

        note_data = {"title": note_text, "timestamp": datetime.datetime.now().isoformat()}

        if self._editing_note:
            # Update existing note
            for i, existing_note in enumerate(self._notes):
                if existing_note == self._editing_note:
                    self._notes[i] = note_data
                    break
            self._editing_note = None  # Reset edit mode
            self.add_button.setText("Add Note")
            self.cancel_button.hide()
        else:
            # Add new note
            self._notes.insert(0, note_data)

        self._save_notes()
        NotesWidget.update_all()  # Update all widget instances
        self._note_input.clear()

        if hasattr(self, "_menu"):
            self._menu.hide()
            self._show_menu()

    def _add_note_to_menu(self, note, layout):
        container = QWidget()
        container.setProperty("class", "note-item")
        container.setContentsMargins(0, 0, 0, 0)
        container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # Main row
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(5)

        # Note icon
        icon_label = QLabel(self._icons["note"])
        icon_label.setProperty("class", "icon")
        container_layout.addWidget(icon_label)

        # Vertical layout for title + date
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)

        # Title
        display_title = re.sub(r"[\n\t\r]+", "", note["title"])
        if len(display_title) > self._menu_config["max_title_size"]:
            display_title = display_title[: (self._menu_config["max_title_size"] - 3)] + "..."
        title_label = QLabel(display_title)
        title_label.setProperty("class", "title")
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        text_layout.addWidget(title_label)

        # Date under title
        if "timestamp" in note and self._menu_config["show_date_time"]:
            try:
                timestamp = datetime.datetime.fromisoformat(note["timestamp"])
                date_str = timestamp.strftime("%Y-%m-%d %H:%M")
                date_label = QLabel(date_str)
                date_label.setProperty("class", "date")
                text_layout.addWidget(date_label)
            except (ValueError, TypeError):
                pass

        container_layout.addWidget(text_container)

        # Spacer to push buttons to the right
        container_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        # Create vertical layout for the buttons
        buttons_container = QWidget()
        buttons_layout = QVBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(5)  # Space between buttons
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center the buttons vertically

        # Copy button on top
        copy_button = QPushButton(self._icons["copy"])
        copy_button.setProperty("class", "copy-button")
        copy_button.clicked.connect(lambda: self._copy_note(note))
        buttons_layout.addWidget(copy_button, 0, Qt.AlignmentFlag.AlignCenter)

        # Delete button on bottom
        delete_button = QPushButton(self._icons["delete"])
        delete_button.setProperty("class", "delete-button")
        delete_button.clicked.connect(lambda: self._delete_note(note))
        buttons_layout.addWidget(delete_button, 0, Qt.AlignmentFlag.AlignCenter)

        # Add the buttons container to the main layout
        container_layout.addWidget(buttons_container)

        # Edit on click
        container.mousePressEvent = lambda e: self._edit_note(note) if e.button() == Qt.MouseButton.LeftButton else None

        # Add container to vertical layout
        layout.addWidget(container)

    def _edit_note(self, note):
        """Edit an existing note in the popup menu"""
        # Set editing mode
        self._editing_note = note

        # Load note content into the input field
        self._note_input.setText(note["title"])
        self._note_input.setFocus()

        # Update UI to show we're in edit mode
        self.add_button.setText("Save Changes")
        self.cancel_button.show()

    def _delete_note(self, note):
        """Delete a note"""
        if note in self._notes:
            self._notes.remove(note)
            self._save_notes()
            NotesWidget.update_all()  # Update all widget instances

            if hasattr(self, "_menu"):
                self._menu.hide()
                self._show_menu()

    def _cancel_editing(self):
        """Cancel editing mode"""
        self._editing_note = None
        self._note_input.clear()
        self.add_button.setText("Add Note")
        self.cancel_button.hide()

    def _copy_note(self, note):
        """Copy note content to clipboard"""
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(note["title"])

    def _load_notes(self) -> List[Dict]:
        """Load notes from JSON file"""
        try:
            if os.path.exists(self._notes_file):
                if DEBUG:
                    logging.debug(f"Loading notes from {self._notes_file}")
                with open(self._notes_file, "r", encoding="utf-8") as f:
                    return list(json.load(f))
        except Exception as e:
            logging.error(f"Error loading notes: {e}")

        return []

    def _save_notes(self):
        """Save notes to JSON file"""
        try:
            if DEBUG:
                logging.debug(f"Saving notes to {self._notes_file}")
            with open(self._notes_file, "w", encoding="utf-8") as f:
                json.dump(self._notes, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving notes: {e}")


class NoteTextEdit(QTextEdit):
    """
    Custom QTextEdit widget for note input that overrides keyPressEvent.
    Captures Enter/Return key presses to trigger note addition in the parent widget,
    while allowing multiline input using Shift+Enter.
    """

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            parent = self.parent()
            while parent and not hasattr(parent, "_add_note_from_input"):
                parent = parent.parent()
            if parent:
                parent._add_note_from_input()
            event.accept()
        else:
            super().keyPressEvent(event)
