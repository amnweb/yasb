import datetime
import json
import logging
import os
import re
from typing import Any

from pydantic import BaseModel
from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from core.config import HOME_CONFIGURATION_DIR
from core.utils.qobject import is_valid_qobject
from core.utils.tooltip import set_tooltip
from core.utils.win32.utils import find_focused_screen, get_foreground_hwnd, set_foreground_hwnd  # type: ignore
from core.utils.win32.window_actions import force_foreground_focus
from core.validation.widgets.yasb.notes import NotesConfig
from core.widgets.base import BaseWidget
from core.widgets.services.notes.utils import ElidedLabel, FloatingWindowController, NotesPopup, NoteTextEdit


class NotesWidget(BaseWidget):
    validation_schema: dict[str, Any] | type[BaseModel] | None = NotesConfig
    _instances: list[NotesWidget] = []

    def __init__(self, config: NotesConfig) -> None:
        super().__init__(class_name=f"notes-widget {config.class_name}")
        self.config = config
        NotesWidget._instances.append(self)

        self._show_alt_label: bool = False
        self._label_content: str = self.config.label
        self._label_alt_content: str = self.config.label_alt
        self.icons: dict[str, str] = self.config.icons.model_dump(by_alias=True)
        self._start_floating: bool = config.start_floating
        self.is_floating: bool = False
        self.previous_hwnd: int = 0  # Used for restoring focus
        self.original_position: Any = None
        self.drag_position: QPoint | None = None
        self.menu: NotesPopup | None = None

        self.scroll_area: QScrollArea | None = None
        self.scroll_widget: QWidget | None = None
        self.scroll_layout: QVBoxLayout | None = None
        self.editing_note: dict[str, str] | None = None
        self._pending_note_html: str = ""
        self.notes_file: str = ""
        self.notes: list[dict[str, str]] = []

        self.note_input: NoteTextEdit
        self.add_button: QPushButton
        self.cancel_button: QPushButton
        self.float_btn: QPushButton
        self.close_btn: QPushButton

        self._floating_controller = FloatingWindowController(self)

        # Use custom data path if provided, otherwise use default
        if config.data_path and config.data_path.strip():
            self.notes_file = os.path.expanduser(config.data_path)
        else:
            self.notes_file = os.path.join(HOME_CONFIGURATION_DIR, "notes.json")
        self.notes = self._load_notes()

        self._init_container()
        self.build_widget_label(self._label_content, self._label_alt_content)

        self.register_callback("toggle_label", self._toggle_label)
        self.register_callback("toggle_menu", self._toggle_menu)
        self.register_callback("update_label", self._update_label)

        self.callback_left = config.callbacks.on_left
        self.callback_right = config.callbacks.on_right
        self.callback_middle = config.callbacks.on_middle
        self.callback_timer = "update_label"

        self._update_label()

    def __del__(self):
        # Remove instance on deletion
        try:
            self._instances.remove(self)
        except ValueError:
            pass

    @classmethod
    def update_all(cls) -> None:
        """Update all instances of NotesWidget"""
        for instance in cls._instances:
            instance.notes = instance._load_notes()
            instance._update_label()
            if instance.is_menu_active():
                instance._refresh_notes_list()

    def get_target_screen(self) -> Any:
        screen_mode = "cursor"
        for kb in self.config.keybindings:
            if kb.action == "toggle_menu":
                screen_mode = kb.screen
                break
        if screen_mode == "cursor":
            screen_name = find_focused_screen(follow_mouse=True, follow_window=False)
        elif screen_mode == "active":
            screen_name = find_focused_screen(follow_mouse=False, follow_window=True)
        elif screen_mode == "primary":
            return QApplication.primaryScreen() or QApplication.screens()[0]
        else:
            return self.screen() or QApplication.primaryScreen() or QApplication.screens()[0]
        if screen_name:
            for s in QApplication.screens():
                if s.name() == screen_name:
                    return s
        return self.screen() or QApplication.primaryScreen() or QApplication.screens()[0]

    def is_menu_active(self) -> bool:
        """Check if menu exists and is visible without crashing on deleted objects."""
        if not is_valid_qobject(self.menu):
            return False
        try:
            return self.menu.isVisible()
        except RuntimeError:
            return False

    def is_menu_valid(self) -> bool:
        if not self.is_menu_active() or self.menu is None:
            return False
        try:
            _ = self.menu.size()
        except RuntimeError:
            return False
        return True

    def _toggle_label(self) -> None:

        self._show_alt_label = not self._show_alt_label

        for widget in self._widgets:
            widget.setVisible(not self._show_alt_label)

        for widget in self._widgets_alt:
            widget.setVisible(self._show_alt_label)

        self._update_label()

    def _toggle_menu(self) -> None:
        # If popup is not visible or doesn't exist, open it
        if not self.is_menu_active():
            self._show_menu()
        else:
            self._close_menu()

    def _close_menu(self) -> None:
        if not self.is_menu_active() or self.menu is None:
            return
        self.menu.hide_animated()

    def _on_menu_destroyed(self, *_args: Any) -> None:
        self.menu = None
        self.scroll_widget = None
        self.scroll_layout = None
        self.scroll_area = None
        self.is_floating = False
        # Restore focus
        if self.previous_hwnd:
            try:
                set_foreground_hwnd(self.previous_hwnd)
            finally:
                self.previous_hwnd = 0

    def _refresh_notes_list(self) -> None:
        """Refresh the notes list in the scroll area without closing the menu."""
        if not is_valid_qobject(self.menu):
            return

        if not is_valid_qobject(self.scroll_layout):
            return

        # Clear layout
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()

        # Add notes
        if self.notes:
            for note in self.notes:
                self._add_note_to_menu(note, self.scroll_layout)
        else:
            # Show empty state
            empty_label = QLabel(f"{self.config.icons.note}  No notes yet!")
            empty_label.setProperty("class", "empty-list")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(empty_label)

        # Use a short timer to ensure layout is updated before adjusting size
        # We want this to run even if not visible yet to set initial size hints
        QTimer.singleShot(50, self.adjust_menu_geometry)

    def adjust_menu_geometry(self):
        """Adjust menu size and position based on current content."""
        if not is_valid_qobject(self.menu):
            return

        # Force scroll widget to update its size hint based on new content
        if self.scroll_widget:
            self.scroll_widget.adjustSize()

        # Calculate height for up to 3 notes
        if self.scroll_layout and self.scroll_area:
            count = self.scroll_layout.count()
            if count > 0:
                # Calculate height of up to 3 items
                total_h = 0
                for i in range(min(count, 3)):
                    item = self.scroll_layout.itemAt(i)
                    if item:
                        widget = item.widget()
                        if widget:
                            total_h += widget.sizeHint().height()

                self.scroll_area.setFixedHeight(total_h)
            else:
                if self.is_floating:
                    self.scroll_area.setMinimumHeight(0)
                    self.scroll_area.setMaximumHeight(60)
                    self.scroll_area.setMinimumHeight(60)
                else:
                    self.scroll_area.setFixedHeight(60)  # Fallback for empty state

        self.menu.adjustSize()
        # setPosition is now overridden in NotesPopup to ignore moves when floating
        self.menu.setPosition(
            alignment=self.config.menu.alignment,
            direction=self.config.menu.direction,
            offset_left=self.config.menu.offset_left,
            offset_top=self.config.menu.offset_top,
        )

    def _update_label(self):
        active_widgets = self._widgets_alt if self._show_alt_label else self._widgets
        active_label_content = self._label_alt_content if self._show_alt_label else self._label_content

        label_parts = re.split("(<span.*?>.*?</span>)", active_label_content)
        label_parts = [part for part in label_parts if part]

        notes_count = len(self.notes)

        for widget_index, part in enumerate(label_parts):
            if widget_index >= len(active_widgets):
                continue

            current_widget = active_widgets[widget_index]
            if not isinstance(current_widget, QLabel):
                continue

            if "<span" in part and "</span>" in part:
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                current_widget.setText(icon)
            else:
                formatted_text = part.format(count=notes_count)
                current_widget.setText(formatted_text)
            widget_index += 1

    def _build_menu_button(
        self,
        parent: QWidget,
        label: str,
        class_name: str,
        on_click: Any,
        visible: bool = True,
    ) -> QPushButton:
        btn = QPushButton(label, parent)
        btn.setProperty("class", class_name)
        if on_click:
            btn.clicked.connect(on_click)
        btn.setVisible(visible)
        return btn

    def _create_header(self, layout: QVBoxLayout):
        header_widget = QFrame()
        header_widget.setProperty("class", "notes-header")
        header_widget.mousePressEvent = lambda a0: self._floating_controller.header_mouse_press(a0)
        header_widget.mouseMoveEvent = lambda a0: self._floating_controller.header_mouse_move(a0)
        header_widget.mouseReleaseEvent = lambda a0: self._floating_controller.header_mouse_release(a0)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setSpacing(0)
        header_layout.setContentsMargins(8, 4, 8, 4)

        header_title = QLabel("Notes")
        header_title.setProperty("class", "header-title")
        header_layout.addWidget(header_title)

        header_layout.addStretch()

        self.float_btn = self._build_menu_button(
            header_widget,
            self.icons["float_on"],
            "float-button",
            self._floating_controller.toggle_floating,
        )
        set_tooltip(self.float_btn, "Float window")
        header_layout.addWidget(self.float_btn)

        self.close_btn = self._build_menu_button(
            header_widget,
            self.icons["close"],
            "close-button",
            self._close_menu,
            visible=False,
        )
        set_tooltip(self.close_btn, "Close window")
        header_layout.addWidget(self.close_btn)

        layout.addWidget(header_widget)

    def _show_menu(self) -> None:
        # Remember the current foreground window so we can restore focus when closing
        self.previous_hwnd = get_foreground_hwnd()

        # Capture current position to restore after recreation if floating
        current_pos = self.menu.pos() if self.is_menu_active() and self.menu else None

        self.menu = NotesPopup(
            self,
            self.config.menu.blur,
            self.config.menu.round_corners,
            self.config.menu.round_corners_type,
            self.config.menu.border_color,
        )
        self.menu.setProperty("class", "notes-menu")
        self.menu.destroyed.connect(self._on_menu_destroyed)

        # Create main layout
        main_layout = QVBoxLayout(self.menu)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Create Header
        self._create_header(main_layout)

        # Add text input area with button row
        input_container = QWidget()
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(5)

        # Text input field
        self.note_input = NoteTextEdit(self)
        self.note_input.setPlaceholderText("Type your note here...")
        self.note_input.setProperty("class", "note-input")

        # Restore pending content if any
        if self._pending_note_html:
            self.note_input.setHtml(self._pending_note_html)
            # Move cursor to end
            cursor = self.note_input.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.note_input.setTextCursor(cursor)

        self.note_input.textChanged.connect(self._save_pending_note)

        # Make actual tabs 4 spaces wide
        metrics = self.note_input.fontMetrics()
        self.note_input.setTabStopDistance(float(metrics.horizontalAdvance(" ") * 4))

        input_layout.addWidget(self.note_input)

        # Button row
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(5)

        # Add Note button
        self.add_button = QPushButton("Add Note")
        self.add_button.setProperty("class", "add-button")
        self.add_button.clicked.connect(self.add_note_from_input)
        button_layout.addWidget(self.add_button)

        # Cancel button (hidden by default)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("class", "cancel-button")
        self.cancel_button.clicked.connect(self._cancel_editing)
        self.cancel_button.hide()
        button_layout.addWidget(self.cancel_button)

        # If we are in edit mode, update buttons
        if self.editing_note:
            self.add_button.setText("Save Changes")
            self.cancel_button.show()

        input_layout.addWidget(button_container)
        main_layout.addWidget(input_container)

        # Create scroll area for notes
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setProperty("class", "scroll-area")

        # Style the scrollbar
        self.scroll_area.setViewportMargins(0, 0, -4, 0)
        self.scroll_area.setStyleSheet("""
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
        """)

        # Create scroll widget and layout
        self.scroll_widget = QWidget()
        self.scroll_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(0)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.scroll_widget)

        # Add notes to the scroll area
        self._refresh_notes_list()

        main_layout.addWidget(self.scroll_area)

        if self.menu:
            self.menu.adjustSize()
            self.menu.setPosition(
                alignment=self.config.menu.alignment,
                direction=self.config.menu.direction,
                offset_left=self.config.menu.offset_left,
                offset_top=self.config.menu.offset_top,
            )
            self.menu.show()

            if self.is_floating:
                self.menu.set_floating(True)
                if current_pos is not None:
                    self.menu.move(current_pos)
                self.float_btn.setText(self.icons["float_off"])
                set_tooltip(self.float_btn, "Dock window")
                self.close_btn.setVisible(True)
            elif self._start_floating:
                self._floating_controller.toggle_floating()

            force_foreground_focus(int(self.menu.winId()))
        self.note_input.setFocus()

    def _save_pending_note(self) -> None:
        """Save the current input content to memory"""
        if is_valid_qobject(self.note_input):
            if self.note_input.toPlainText().strip():
                self._pending_note_html = self.note_input.toHtml()
            else:
                self._pending_note_html = ""

    def add_note_from_input(self) -> None:
        """Add a new note or save changes to an existing note"""
        plain_text = self.note_input.toPlainText().strip()
        if not plain_text:
            return

        note_data: dict[str, str] = {
            "title": plain_text,
            "html": self.note_input.toHtml(),
            "timestamp": datetime.datetime.now().isoformat(),
        }

        if self.editing_note:
            # Update existing note
            for i, existing_note in enumerate(self.notes):
                if existing_note == self.editing_note:
                    self.notes[i] = note_data
                    break
            self.editing_note = None  # Reset edit mode
            self.add_button.setText("Add Note")
            self.cancel_button.hide()
        else:
            # Add new note
            self.notes.insert(0, note_data)

        self._save_notes()
        self.note_input.clear()
        NotesWidget.update_all()  # Update all widget instances

    def _add_note_to_menu(self, note: dict[str, str], layout: QVBoxLayout) -> None:
        container = QWidget()
        container.setProperty("class", "note-item")
        container.setContentsMargins(0, 0, 0, 0)

        # Main row
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(5)

        # Note icon
        icon_label = QLabel(self.config.icons.note)
        icon_label.setProperty("class", "icon")
        container_layout.addWidget(icon_label)

        # Vertical layout for title + date
        text_container = QWidget()
        text_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)

        # Title
        lines = note["title"].splitlines()
        display_title = lines[0] if lines else ""
        if len(display_title) > self.config.menu.max_title_size:
            display_title = display_title[: (self.config.menu.max_title_size - 3)] + "..."
        title_label = ElidedLabel(display_title)
        title_label.setProperty("class", "title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        text_layout.addWidget(title_label)

        # Date under title
        if "timestamp" in note and self.config.menu.show_date_time:
            try:
                timestamp = datetime.datetime.fromisoformat(note["timestamp"])
                date_str = timestamp.strftime("%Y-%m-%d %H:%M")
                date_label = QLabel(date_str)
                date_label.setProperty("class", "date")
                text_layout.addWidget(date_label)
            except ValueError, TypeError:
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
        copy_button = QPushButton(self.config.icons.copy_icon)
        copy_button.setProperty("class", "copy-button")
        copy_button.clicked.connect(lambda: self._copy_note(note))
        buttons_layout.addWidget(copy_button, 0, Qt.AlignmentFlag.AlignCenter)

        # Delete button on bottom
        delete_button = QPushButton(self.config.icons.delete)
        delete_button.setProperty("class", "delete-button")
        delete_button.clicked.connect(lambda: self._delete_note(note))
        buttons_layout.addWidget(delete_button, 0, Qt.AlignmentFlag.AlignCenter)

        # Add the buttons container to the main layout
        container_layout.addWidget(buttons_container)

        # Edit on click
        container.mousePressEvent = lambda a0: (
            self._edit_note(note) if a0 and a0.button() == Qt.MouseButton.LeftButton else None
        )

        # Add container to vertical layout
        layout.addWidget(container)

    def _edit_note(self, note: dict[str, str]) -> None:
        """Edit an existing note in the popup menu"""
        # Set editing mode
        self.editing_note = note

        # Load note content into the input field
        if "html" in note:
            self.note_input.setHtml(note["html"])
        else:
            self.note_input.setText(note["title"])
        self.note_input.setFocus()

        # Update UI to show we're in edit mode
        self.add_button.setText("Save Changes")
        self.cancel_button.show()

    def _delete_note(self, note: dict[str, str]) -> None:
        """Delete a note"""
        if note in self.notes:
            self.notes.remove(note)
            self._save_notes()
            NotesWidget.update_all()  # Update all widget instances

    def _on_clear_chat(self) -> None:
        """Clear all notes (if such action is needed)"""
        self.notes = []
        self._save_notes()
        NotesWidget.update_all()

    def _cancel_editing(self) -> None:
        """Cancel editing mode"""
        self.editing_note = None
        self.note_input.clear()
        self.add_button.setText("Add Note")
        self.cancel_button.hide()

    def _copy_note(self, note: dict[str, str]) -> None:
        """Copy note content to clipboard"""

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(note["title"])

    def _load_notes(self) -> list[dict[str, str]]:
        """Load notes from JSON file"""
        try:
            if os.path.exists(self.notes_file):
                logging.debug("Loading notes from %s", self.notes_file)
                with open(self.notes_file, encoding="utf-8") as f:
                    return list(json.load(f))
        except Exception as e:
            logging.error("Error loading notes: %s", e)

        return []

    def _save_notes(self) -> None:
        """Save notes to JSON file"""
        try:
            logging.debug("Saving notes to %s", self.notes_file)
            with open(self.notes_file, "w", encoding="utf-8") as f:
                json.dump(self.notes, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error("Error saving notes: %s", e)
