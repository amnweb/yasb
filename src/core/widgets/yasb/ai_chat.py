import base64
import functools
import logging
import os
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from PyQt6.QtCore import (
    QBuffer,
    QEvent,
    QIODevice,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QContextMenuEvent, QImage, QKeyEvent, QMouseEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.event_service import EventService
from core.utils.utilities import PopupWidget, add_shadow
from core.utils.widgets.ai_chat.client import AiChatClient
from core.utils.widgets.ai_chat.client_helper import format_chat_text
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.utilities import apply_qmenu_style, get_foreground_hwnd, set_foreground_hwnd
from core.utils.win32.window_actions import force_foreground_focus
from core.validation.widgets.yasb.ai_chat import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget


class ContextMenuMixin:
    """Mixin class to provide shared context menu functionality for chat widgets"""

    def _init_context_menu(self, is_input_widget=False):
        """Initialize context menu setup."""
        self._parent_widget = None
        self._is_input_widget = is_input_widget
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._handle_context_menu)

    def set_parent_widget(self, parent_widget):
        """Set the parent widget that contains the context menu handler"""
        self._parent_widget = parent_widget

    def _handle_context_menu(self, pos):
        """Handle custom context menu request"""
        if self._parent_widget and hasattr(self._parent_widget, "_show_context_menu"):
            self._parent_widget._show_context_menu(self, pos, is_input=self._is_input_widget)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events to show context menu on right click"""
        if event.button() == Qt.MouseButton.RightButton:
            if self._parent_widget and hasattr(self._parent_widget, "_show_context_menu"):
                self._parent_widget._show_context_menu(self, event.pos(), is_input=self._is_input_widget)
                event.accept()
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Override context menu event to show our custom menu"""
        if self._parent_widget and hasattr(self._parent_widget, "_show_context_menu"):
            local_pos = self.mapFromGlobal(event.globalPos())
            self._parent_widget._show_context_menu(self, local_pos, is_input=self._is_input_widget)
            event.accept()
        else:
            super().contextMenuEvent(event)


class ChatInputEdit(ContextMenuMixin, QTextEdit):
    """Custom text edit for chat input with enter key handling and signal for sending messages"""

    send_message = pyqtSignal()
    text_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_streaming = False
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._init_context_menu(is_input_widget=True)
        self.textChanged.connect(self.text_changed.emit)

    def set_streaming(self, value: bool):
        self._is_streaming = value

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            if not self._is_streaming:
                self.send_message.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        # Let parent handle attachments/images pasted from clipboard; fallback to text paste
        parent = getattr(self, "_parent_widget", None)
        if parent and hasattr(parent, "_handle_paste_mime"):
            try:
                if parent._handle_paste_mime(source):
                    return
            except Exception:
                pass
        self.insertPlainText(source.text())


class ChatMessageLabel(ContextMenuMixin, QLabel):
    """Custom label for chat messages with context menu support and proper word breaking"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.setOpenExternalLinks(True)
        self._init_context_menu(is_input_widget=False)

    def setText(self, text):
        """Override setText to handle long words and make URLs clickable, and store original HTML"""
        if text:
            processed_text = format_chat_text(text)
            processed_text = self._insert_break_opportunities(processed_text)
            super().setText(processed_text)
        else:
            super().setText(text)

    def _insert_break_opportunities(self, text):
        """Insert zero-width spaces to enable breaking of very long words, while preserving HTML and all original whitespace."""

        def process_text_parts(text):
            # Split by HTML tags to avoid breaking them
            parts = re.split(r"(<[^>]+>)", text)
            processed_parts = []

            def break_long_word(match):
                word = match.group(0)
                if len(word) > 50 and "&" not in word and "<" not in word:
                    # Insert zero-width space every 30 characters
                    return "".join(
                        char + ("\u200b" if (i + 1) % 30 == 0 and i + 1 < len(word) else "")
                        for i, char in enumerate(word)
                    )
                return word

            for part in parts:
                if part.startswith("<") and part.endswith(">"):
                    # This is an HTML tag, don't modify it
                    processed_parts.append(part)
                else:
                    # This is regular text, process for long words but preserve all whitespace
                    processed_parts.append(re.sub(r"\S+", break_long_word, part))

            return "".join(processed_parts)

        return process_text_parts(text)


class Corner(StrEnum):
    """Enum for notification dot position corners."""

    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class NotificationLabel(QLabel):
    """Draws a QLabel with a dot on any of the four corners."""

    def __init__(
        self,
        *args: Any,
        color: str = "red",
        corner: Corner = Corner.BOTTOM_LEFT,
        margin: list[int] = [1, 1],
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._show_dot = False
        self._color = color
        self._corner = corner
        self._margin = margin

    def show_dot(self, enabled: bool):
        self._show_dot = enabled
        self.update()

    def set_corner(self, corner: str | Corner):
        """Set the corner where the dot should appear."""
        self._corner = corner
        self.update()

    def set_color(self, color: str):
        """Set the color of the notification dot."""
        self._color = color
        self.update()

    def paintEvent(self, a0: QPaintEvent | None):
        super().paintEvent(a0)
        if self._show_dot:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(self._color))
            painter.setPen(Qt.PenStyle.NoPen)

            radius = 6
            margin_x = self._margin[0]
            margin_y = self._margin[1]

            # Calculate position based on the specified corner
            x = y = 0
            if self._corner == Corner.TOP_LEFT:
                x = margin_x
                y = margin_y
            elif self._corner == Corner.TOP_RIGHT:
                x = self.width() - radius - margin_x
                y = margin_y
            elif self._corner == Corner.BOTTOM_LEFT:
                x = margin_x
                y = self.height() - radius - margin_y
            elif self._corner == Corner.BOTTOM_RIGHT:
                x = self.width() - radius - margin_x
                y = self.height() - radius - margin_y

            painter.drawEllipse(QPoint(x + radius // 2, y + radius // 2), radius // 2, radius // 2)


class AiChatWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA
    _persistent_chat_history = {}
    handle_widget_cli = pyqtSignal(str, str)

    def __init__(
        self,
        label: str,
        chat: dict,
        icons: dict,
        notification_dot: dict[str, Any],
        animation: dict[str, str],
        container_padding: dict[str, int],
        callbacks: dict[str, str],
        label_shadow: dict = None,
        container_shadow: dict = None,
        providers: list = None,
    ):
        super().__init__(class_name="ai-chat-widget")
        self._label_content = label
        self._icons = icons
        self._notification_dot: dict[str, Any] = notification_dot
        self._providers = providers or []
        self._provider = None
        self._provider_config = None
        self._model = None
        self._initialize_provider_and_model()
        self._popup_chat = None
        self._animation = animation
        self._padding = container_padding
        self._chat = chat
        self._label_shadow = label_shadow
        self._container_shadow = container_shadow
        self._notification_label: NotificationLabel | None = None
        self._input_draft = ""
        self._attachments: list[dict[str, Any]] = []
        self._previous_hwnd = 0
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        self._create_dynamically_label(self._label_content)

        self.register_callback("toggle_chat", self._toggle_chat)
        self.callback_left = callbacks["on_left"]
        self.callback_right = callbacks["on_right"]
        self.callback_middle = callbacks["on_middle"]
        self._thinking_timer = None
        self._thinking_step = 0
        self._thinking_label = None
        self._new_notification = False

        self._event_service = EventService()
        self.handle_widget_cli.connect(self._handle_widget_cli)
        self._event_service.register_event("handle_widget_cli", self.handle_widget_cli)

    def _initialize_provider_and_model(self):
        """Initialize provider and model by finding the model with default: true flag.

        Validates that only one model has the default flag set.
        """
        default_models = []

        # Find all models with default flag set to true
        for provider_cfg in self._providers:
            for model_cfg in provider_cfg.get("models", []):
                if model_cfg.get("default", False):
                    default_models.append((provider_cfg["provider"], model_cfg["name"]))

        # Logs warning if more than one model has default flag set
        if len(default_models) > 1:
            logging.warning(
                f"Multiple models have default flag set: {default_models}. Using first model: {default_models[0]}"
            )

        # Set the default provider and model if found
        if default_models:
            self._provider = default_models[0][0]
            self._model = default_models[0][1]

        # Set provider config
        if self._provider:
            self._provider_config = next((p for p in self._providers if p["provider"] == self._provider), None)

    def _create_dynamically_label(self, content: str):
        label_parts = re.split("(<span.*?>.*?</span>)", content)
        label_parts = [part for part in label_parts if part]
        for part in label_parts:
            part = part.strip()
            if not part:
                continue
            if "<span" in part and "</span>" in part:
                class_name = re.search(r'class=(["\'])([^"\']+?)\1', part)
                class_result = class_name.group(2) if class_name else "icon"
                icon = re.sub(r"<span.*?>|</span>", "", part).strip()
                label = NotificationLabel(
                    icon,
                    corner=self._notification_dot["corner"],
                    color=self._notification_dot["color"],
                    margin=self._notification_dot["margin"],
                )
                label.setProperty("class", class_result)
                self._notification_label = label
            else:
                label = NotificationLabel(
                    part,
                    corner=self._notification_dot["corner"],
                    color=self._notification_dot["color"],
                    margin=self._notification_dot["margin"],
                )
                label.setProperty("class", "label")
                self._notification_label = label
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            add_shadow(label, self._label_shadow)
            self._widget_container_layout.addWidget(label)
            label.show()

    def _update_label(self):
        """Update the label content and notification dot state."""
        if not self._notification_dot["enabled"]:
            return

        if self._notification_label is not None:
            self._notification_label.show_dot(self._new_notification)

    def _update_send_button_state(self):
        """Update send button state based on provider/model selection and pending input"""
        if not self._is_popup_valid():
            return

        try:
            # Enable send button only if provider, model are selected and there is text or attachments
            has_provider_and_model = bool(self._provider and self._model and not self._model.startswith("No models"))
            has_input_text = bool(self.input_edit.toPlainText().strip())
            has_attachments = bool(getattr(self, "_attachments", []))
            is_enabled = has_provider_and_model and (has_input_text or has_attachments)
            self.send_btn.setEnabled(is_enabled)

            # Enable attachment button only when a provider/model is selected and attachments are supported
            if hasattr(self, "attach_btn"):
                self.attach_btn.setEnabled(has_provider_and_model and self._attachments_supported())
        except RuntimeError:
            pass

    def _set_ui_state(self, streaming=False):
        """Set UI state for streaming or normal mode"""
        if not self._is_popup_valid():
            return

        try:
            self.send_btn.setVisible(not streaming)
            self.stop_btn.setVisible(streaming)
            if not streaming:
                self.stop_btn.setEnabled(False)
                # Update send button state based on provider/model selection when not streaming
                self._update_send_button_state()
            self.input_edit.set_streaming(streaming)
            self.provider_btn.setEnabled(not streaming)
            self.model_btn.setEnabled(not streaming)
            if hasattr(self, "clear_btn"):
                self.clear_btn.setEnabled(not streaming)
        except RuntimeError:
            pass

    def _get_model_config(self):
        """Get the configuration for the current model"""
        if not (self._provider_config and self._provider_config.get("models")):
            return None
        return next((m for m in self._provider_config["models"] if m["name"] == self._model), None)

    def _get_max_image_bytes(self) -> int:
        """Get max image size in bytes from current model config."""
        model_config = self._get_model_config()
        if model_config:
            return model_config.get("max_image_size", 0) * 1024
        return 0  # Default disabled

    def _get_max_attachment_bytes(self) -> int:
        """Get max text attachment size in bytes from current model config."""
        model_config = self._get_model_config()
        if model_config:
            return model_config.get("max_attachment_size", 0) * 1024
        return 0  # Default disabled

    def _attachments_supported(self) -> bool:
        """Check if current model supports any type of attachments."""
        return self._get_max_image_bytes() > 0 or self._get_max_attachment_bytes() > 0

    def _prune_attachments_for_model(self) -> bool:
        """Remove attachments that are not supported by the current model.

        Returns True if any attachments were removed.
        """
        if not hasattr(self, "_attachments"):
            return False

        max_image_bytes = self._get_max_image_bytes()
        max_attachment_bytes = self._get_max_attachment_bytes()

        pruned: list[dict[str, Any]] = []
        for att in getattr(self, "_attachments", []):
            if att.get("is_image"):
                if max_image_bytes > 0:
                    pruned.append(att)
            else:
                if max_attachment_bytes > 0:
                    pruned.append(att)

        changed = len(pruned) != len(getattr(self, "_attachments", []))
        self._attachments = pruned
        return changed

    def _compress_image_if_needed(self, image_bytes: bytes, max_bytes: int) -> tuple[bytes, bool]:
        """Compress image bytes to fit within max_bytes using iterative quality reduction.

        Returns:
            tuple[bytes, bool]: (compressed_bytes, was_compressed)
        """
        if len(image_bytes) <= max_bytes:
            return image_bytes, False

        try:
            # Load image from bytes
            img = QImage()
            img.loadFromData(image_bytes)
            if img.isNull():
                return image_bytes, False

            # Start with quality 85 and reduce until we're under max_bytes
            quality = 85
            best_bytes = image_bytes
            while quality >= 5:
                qbuffer = QBuffer()
                qbuffer.open(QIODevice.OpenModeFlag.WriteOnly)
                img.save(qbuffer, "JPEG", quality)
                compressed_bytes = qbuffer.data().data()
                qbuffer.close()

                if len(compressed_bytes) <= max_bytes:
                    # This quality works, save it
                    best_bytes = compressed_bytes
                    return best_bytes, True
                quality -= 5

            # Even at quality 5, still too large - return best attempt
            return best_bytes, True
        except Exception as e:
            logging.exception(f"Failed to compress image: {e}")
            return image_bytes, False

    def _reconnect_streaming_if_needed(self):
        """Reconnect streaming state when popup is reopened"""
        streaming = hasattr(self, "_streaming_state") and self._streaming_state.get("in_progress")
        if not streaming:
            return

        # Update button states
        self.stop_btn.setVisible(True)
        self.send_btn.setVisible(False)

        # Ensure model and provider buttons are disabled during streaming
        self.provider_btn.setEnabled(False)
        self.model_btn.setEnabled(False)
        if hasattr(self, "clear_btn"):
            self.clear_btn.setEnabled(False)

        # Enable stop button only if AI has already started responding (has partial text)
        partial_text = self._streaming_state.get("partial_text", "")
        self.stop_btn.setEnabled(bool(partial_text))

        # Find or create assistant message label
        row_widget = None
        msg_label = None
        # Check last message role
        last_idx = self.chat_layout.count() - 2
        if self._is_popup_valid() and last_idx >= 0:
            item = self.chat_layout.itemAt(last_idx)
            if item:
                row_widget = item.widget()
        last_role = None
        if row_widget and isinstance(row_widget, QWidget):
            # Try to detect role by QLabel property
            for i in range(row_widget.layout().count()):
                child = row_widget.layout().itemAt(i).widget()
                if isinstance(child, QLabel):
                    if child.property("class") == "assistant-message":
                        msg_label = child
                        last_role = "assistant"
                        break
                    elif child.property("class") == "user-message":
                        last_role = "user"
        partial = self._streaming_state.get("partial_text", "")
        if not partial:
            partial = "thinking ..."
        # Only append assistant message if last message is user
        if last_role == "user":
            self._append_message("assistant", partial)
            # Get the new row_widget
            row_widget = None
            last_idx = self.chat_layout.count() - 2
            if self._is_popup_valid() and last_idx >= 0:
                item = self.chat_layout.itemAt(last_idx)
                if item:
                    row_widget = item.widget()
            if row_widget and isinstance(row_widget, QWidget):
                for i in range(row_widget.layout().count()):
                    child = row_widget.layout().itemAt(i).widget()
                    if isinstance(child, QLabel) and child.property("class") == "assistant-message":
                        msg_label = child
                        break
        elif last_role == "assistant" and msg_label is not None:
            # Just update the label
            try:
                msg_label.setText(partial)
            except RuntimeError:
                pass
        # If not found, fallback to previous logic
        if msg_label is not None:
            self._streaming_state["msg_label"] = msg_label
            # Ensure only one handler is connected
            if hasattr(self, "_worker"):
                try:
                    self._worker.chunk_signal.disconnect(self._streaming_chunk_handler)
                except Exception:
                    pass
                self._worker.chunk_signal.connect(self._streaming_chunk_handler)
            # If still thinking (no chunk yet), restart thinking animation
            if not self._streaming_state.get("partial_text", ""):
                self._start_thinking_animation(msg_label)

    def _toggle_chat(self):
        # If popup is not visible or doesn't exist, open it
        if self._popup_chat is None or not (self._popup_chat and self._popup_chat.isVisible()):
            if self._animation["enabled"]:
                AnimationManager.animate(self, self._animation["type"], self._animation["duration"])
            self._show_chat()

            # Focus and move cursor to end of text
            self.input_edit.setFocus()
            cursor = self.input_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.input_edit.setTextCursor(cursor)
        else:
            self._popup_chat.hide()
            self._popup_chat.deleteLater()
            self._popup_chat = None

    def _handle_widget_cli(self, widget: str, screen: str):
        """Handle widget CLI commands"""
        if widget == "ai_chat":
            current_screen = self.window().screen() if self.window() else None
            current_screen_name = current_screen.name() if current_screen else None
            if not screen or (current_screen_name and screen.lower() == current_screen_name.lower()):
                self._toggle_chat()

    def _show_chat(self):
        """Show the AI chat popup with all components initialized."""
        self._new_notification = False
        self._update_label()

        # Remember the current foreground window so we can restore focus when closing
        self._previous_hwnd = get_foreground_hwnd()

        self._popup_chat = PopupWidget(
            self,
            self._chat["blur"],
            self._chat["round_corners"],
            self._chat["round_corners_type"],
            self._chat["border_color"],
        )
        self._popup_chat.setProperty("class", "ai-chat-popup")

        self._popup_chat.destroyed.connect(self._on_popup_destroyed)
        self._popup_chat.destroyed.connect(self._stop_thinking_animation)

        layout = QVBoxLayout(self._popup_chat)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        header_widget = QFrame()
        header_widget.setProperty("class", "chat-header")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setSpacing(0)
        header_layout.setContentsMargins(0, 0, 0, 0)

        selection_row = QHBoxLayout()
        selection_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        provider_label = QLabel("Provider")
        provider_label.setProperty("class", "provider-label")
        self.provider_btn = QPushButton(self._provider or "Select provider")
        self.provider_btn.setProperty("class", "provider-button")
        self.provider_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 8px;
            }
            QPushButton::menu-indicator { image: none; width: 0px; height: 0px; }
        """)
        self.provider_menu = QMenu(self.provider_btn)
        self.provider_menu.setProperty("class", "context-menu")
        self.provider_menu.setStyleSheet("QMenu::indicator { width: 0px; height: 0px; }")
        apply_qmenu_style(self.provider_menu)
        self.provider_btn.clicked.connect(
            lambda: self.provider_menu.exec(self.provider_btn.mapToGlobal(self.provider_btn.rect().bottomLeft()))
        )
        self._populate_provider_menu()
        model_label = QLabel("Model")
        model_label.setProperty("class", "model-label")
        self.model_btn = QPushButton(self._get_model_label())
        self.model_btn.setProperty("class", "model-button")
        self.model_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 8px;
            }
            QPushButton::menu-indicator { image: none; width: 0px; height: 0px; }
        """)
        self.model_btn.setEnabled(bool(self._provider_config and self._provider_config.get("models")))
        self.model_menu = QMenu(self.model_btn)
        self.model_menu.setProperty("class", "context-menu")
        self.model_menu.setStyleSheet("QMenu::indicator { width: 0px; height: 0px; }")
        self.model_menu.aboutToShow.connect(
            lambda: (
                apply_qmenu_style(self.model_menu),
                [
                    action.setChecked(
                        any(
                            model_cfg.get("label", model_cfg["name"]) == action.text()
                            and model_cfg["name"] == self._model
                            for model_cfg in self._provider_config["models"]
                        )
                        if self._provider_config and self._provider_config.get("models")
                        else False
                    )
                    for action in self.model_menu.actions()
                ],
            )
        )
        self.model_btn.clicked.connect(
            lambda: self.model_menu.exec(self.model_btn.mapToGlobal(self.model_btn.rect().bottomLeft()))
        )
        self._populate_model_menu()

        selection_row.addWidget(provider_label, 0, Qt.AlignmentFlag.AlignVCenter)
        selection_row.addWidget(self.provider_btn, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        selection_row.addWidget(model_label, 0, Qt.AlignmentFlag.AlignVCenter)
        selection_row.addWidget(self.model_btn, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addLayout(selection_row)
        layout.addWidget(header_widget)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_scroll.setProperty("class", "chat-content")
        self.chat_scroll.setStyleSheet("""
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        self.chat_widget = QWidget()
        self.chat_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.chat_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.addSpacerItem(QSpacerItem(1, 1, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.chat_scroll.setWidget(self.chat_widget)
        layout.addWidget(self.chat_scroll, stretch=1)
        v_scrollbar = self.chat_scroll.verticalScrollBar()
        v_scrollbar.setSingleStep(6)
        # Restore chat history
        self._render_chat_history()

        footer = QFrame()
        footer.setProperty("class", "chat-footer")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(6)

        attachments_row = QHBoxLayout()
        attachments_row.setContentsMargins(4, 0, 0, 0)
        attachments_row.setSpacing(6)
        self.attachments_layout = attachments_row
        footer_layout.addLayout(attachments_row)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(4)

        self.attach_btn = QPushButton(self._icons["attach"])
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.setProperty("class", "attach-button")
        self.attach_btn.clicked.connect(self._on_add_attachment)
        input_row.addWidget(self.attach_btn)

        self.input_edit = ChatInputEdit()
        self.input_edit.setProperty("class", "chat-input")
        self.input_edit.setPlaceholderText("Type your message...")
        self.input_edit.send_message.connect(self._on_send_clicked)
        self.input_edit.text_changed.connect(self._update_send_button_state)
        self.input_edit.set_streaming(False)
        self.input_edit.set_parent_widget(self)
        if hasattr(self, "_input_draft") and self._input_draft:
            self.input_edit.setPlainText(self._input_draft)
        input_row.addWidget(self.input_edit, stretch=1)

        self.send_btn = QPushButton(self._icons["send"])
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setProperty("class", "send-button")
        self.send_btn.clicked.connect(self._on_send_clicked)
        input_row.addWidget(self.send_btn)

        self.stop_btn = QPushButton(self._icons["stop"])
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setProperty("class", "stop-button")
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.stop_btn.setVisible(False)
        input_row.addWidget(self.stop_btn)

        self.clear_btn = QPushButton(self._icons["clear"])
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setProperty("class", "clear-button")
        self.clear_btn.clicked.connect(self._on_clear_chat)
        input_row.addWidget(self.clear_btn)

        footer_layout.addLayout(input_row)
        layout.addWidget(footer)
        # Refresh attachments UI to show any existing attachments
        self._refresh_attachments_ui()
        self._popup_chat.setPosition(
            alignment=self._chat["alignment"],
            direction=self._chat["direction"],
            offset_left=self._chat["offset_left"],
            offset_top=self._chat["offset_top"],
        )
        self._popup_chat.show()
        force_foreground_focus(int(self._popup_chat.winId()))
        self._reconnect_streaming_if_needed()
        self._update_send_button_state()

    def _populate_provider_menu(self):
        self.provider_menu.clear()
        for provider_cfg in self._providers:
            provider_name = provider_cfg["provider"]
            action = self.provider_menu.addAction(provider_name)
            action.setCheckable(True)
            if provider_name == self._provider:
                action.setChecked(True)

            action.triggered.connect(functools.partial(self._on_provider_changed, provider_name))

    def _render_chat_history(self):
        """Render chat history for the current provider and model asynchronously."""
        if hasattr(self, "_history_to_load"):
            del self._history_to_load
        if hasattr(self, "_streaming_partial_to_load"):
            del self._streaming_partial_to_load
        if hasattr(self, "_message_batch_index"):
            del self._message_batch_index
        # Clear existing widgets
        for i in reversed(range(self.chat_layout.count())):  # Remove all widgets
            item = self.chat_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                self.chat_layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()

        history = self._get_current_history()

        streaming_partial = None
        if hasattr(self, "_streaming_state") and self._streaming_state.get("in_progress"):
            streaming_partial = self._streaming_state.get("partial_text", None)
        if not history and not streaming_partial:
            self._show_empty_chat_placeholder()
        else:
            QTimer.singleShot(10, lambda: self._load_all_messages_async(history, streaming_partial))
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def _append_message(self, role, text):
        """Append a message to the chat layout"""
        self._remove_placeholder()
        row = QFrame()
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        icon_label = QLabel()
        icon_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        msg_label = ChatMessageLabel()
        msg_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        msg_label.set_parent_widget(self)
        msg_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        msg_label.setOpenExternalLinks(True)
        if role == "user":
            msg_label.setText(text)
            msg_label.setProperty("class", "user-message")
            msg_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        else:
            icon_label.setText(self._icons["assistant"])
            icon_label.setProperty("class", "assistant-icon")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
            msg_label.setText(text)
            msg_label.setProperty("class", "assistant-message")
            msg_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        row_layout.addWidget(icon_label)
        row_layout.addWidget(msg_label)

        insert_pos = self.chat_layout.count() - 1
        self.chat_layout.insertWidget(insert_pos, row)

    def _show_empty_chat_placeholder(self):
        """Show the empty chat placeholder with greeting."""
        self._remove_placeholder()  # Ensure only one placeholder exists
        hour = datetime.now().hour
        greeting = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 18 else "Good evening"
        placeholder = QWidget()
        placeholder.setProperty("class", "empty-chat")
        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        label1 = QLabel(greeting)
        label1.setProperty("class", "greeting")
        label1.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        label2 = QLabel("How can I help you today?")
        label2.setProperty("class", "message")
        label2.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label1)
        layout.addWidget(label2)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, placeholder, stretch=1)

    def _load_all_messages_async(self, history, streaming_partial):
        """Load all messages asynchronously in batches to prevent UI blocking."""
        # Always exclude the last assistant message if streaming is in progress
        filtered_history = list(history)
        if streaming_partial and filtered_history:
            last_msg = filtered_history[-1]
            if last_msg["role"] == "assistant":
                filtered_history = filtered_history[:-1]
        self._message_batch_index = 0
        self._history_to_load = filtered_history
        self._streaming_partial_to_load = streaming_partial
        self._batch_size = 2  # Load 2 messages at a time
        self._load_next_message_batch()

    def _load_next_message_batch(self):
        """Load the next batch of messages and update loading percent."""
        if not hasattr(self, "chat_layout"):
            return
        chat_layout = self.chat_layout
        try:
            parent = chat_layout.parentWidget()
        except RuntimeError:
            return
        if parent is None or not isinstance(parent, QWidget) or parent is not self.chat_widget:
            return
        if not hasattr(self, "_history_to_load"):
            return

        total = len(self._history_to_load)

        start_idx = self._message_batch_index
        end_idx = min(start_idx + self._batch_size, total)

        for idx in range(start_idx, end_idx):
            msg = self._history_to_load[idx]
            # Compute display text lazily from history entry
            display_text = self._compute_display_for_history_entry(msg)
            self._append_message(msg["role"], display_text)

        self._message_batch_index = end_idx

        if self._message_batch_index < total:
            QTimer.singleShot(10, self._load_next_message_batch)
        else:
            # After all history is loaded, if streaming is in progress, append a single assistant message for partial text
            if self._streaming_partial_to_load is not None:
                partial = self._streaming_partial_to_load or "thinking ..."
                self._append_message("assistant", partial)
                # Set streaming label reference for real-time updates
                last_idx = self.chat_layout.count() - 2
                row_widget = None
                if self._is_popup_valid() and last_idx >= 0:
                    item = self.chat_layout.itemAt(last_idx)
                    if item:
                        row_widget = item.widget()
                msg_label = None
                if row_widget and isinstance(row_widget, QWidget):
                    for i in range(row_widget.layout().count()):
                        child = row_widget.layout().itemAt(i).widget()
                        if isinstance(child, QLabel) and child.property("class") == "assistant-message":
                            msg_label = child
                            break
                if hasattr(self, "_streaming_state") and msg_label is not None:
                    self._streaming_state["msg_label"] = msg_label
                    # Ensure only one handler is connected
                    if hasattr(self, "_worker"):
                        try:
                            self._worker.chunk_signal.disconnect(self._streaming_chunk_handler)
                        except Exception:
                            pass
                        self._worker.chunk_signal.connect(self._streaming_chunk_handler)
                    # If partial is empty, start thinking animation
                    if not self._streaming_partial_to_load:
                        self._start_thinking_animation(msg_label)
            # Clean up batch loading variables
            for attr in ("_history_to_load", "_streaming_partial_to_load", "_message_batch_index"):
                if hasattr(self, attr):
                    delattr(self, attr)

    def _on_clear_chat(self):
        key = self._get_history_key()
        if key in AiChatWidget._persistent_chat_history:
            del AiChatWidget._persistent_chat_history[key]
        self._render_chat_history()
        self._attachments = []
        self._refresh_attachments_ui()
        self._update_send_button_state()

    def _on_popup_destroyed(self, *args):
        if hasattr(self, "input_edit"):
            self._input_draft = self.input_edit.toPlainText()
        else:
            self._input_draft = ""
        # Keep attachments in memory across popup close/reopen
        if hasattr(self, "_loading_label"):
            del self._loading_label
        self._popup_chat = None
        self._stop_thinking_animation()
        self._restore_previous_focus()
        for attr in ("_history_to_load", "_streaming_partial_to_load", "_message_batch_index"):
            if hasattr(self, attr):
                delattr(self, attr)

    def _on_provider_changed(self, provider_name):
        # Save current history before switching
        self._save_current_history()
        if provider_name != self._provider:
            self._provider = provider_name
            self.provider_btn.setText(provider_name)
            # Find provider config
            self._provider_config = next((p for p in self._providers if p["provider"] == provider_name), None)
            self._populate_model_menu()
            self._render_chat_history()
            # Remove any attachments that are not supported by the new model
            self._prune_attachments_for_model()
            self._refresh_attachments_ui()
            self._update_send_button_state()

        for action in self.provider_menu.actions():
            action.setChecked(action.text() == provider_name)

    def _populate_model_menu(self):
        self.model_menu.clear()
        if (
            not hasattr(self, "_provider_config")
            or not self._provider_config
            or not self._provider_config.get("models")
        ):
            self.model_btn.setEnabled(False)
            return
        for model_cfg in self._provider_config["models"]:
            model_name = model_cfg["name"]
            model_label = model_cfg.get("label", model_name)
            action = self.model_menu.addAction(model_label)
            action.setCheckable(True)
            # Check the action if it matches the current model
            if model_name == self._model:
                action.setChecked(True)
            else:
                action.setChecked(False)
            action.triggered.connect(lambda checked, m=model_label: self._on_model_changed_by_label(m))
        self.model_btn.setEnabled(True)
        # Set first model as default from the provider config
        if self._model and any(m["name"] == self._model for m in self._provider_config["models"]):
            selected_model = next(m for m in self._provider_config["models"] if m["name"] == self._model)
            self.model_btn.setText(selected_model.get("label", self._model))
        else:
            self._model = self._provider_config["models"][0]["name"]
            self.model_btn.setText(self._provider_config["models"][0].get("label", self._model))

    def _on_model_changed_by_label(self, model_label):
        # Save current history before switching
        self._save_current_history()
        if not hasattr(self, "_provider_config") or not self._provider_config:
            return
        for model_cfg in self._provider_config["models"]:
            if model_cfg.get("label", model_cfg["name"]) == model_label:
                self._model = model_cfg["name"]
                self.model_btn.setText(model_label)
                self._render_chat_history()
                # Remove any attachments that are not supported by the new model
                self._prune_attachments_for_model()
                self._refresh_attachments_ui()
                # Update send button state after model change
                self._update_send_button_state()
                break

        for action in self.model_menu.actions():
            action.setChecked(action.text() == model_label)

    def _on_send_clicked(self):
        user_text = self.input_edit.toPlainText().strip()
        has_attachments = bool(self._attachments)
        if (
            (not user_text and not has_attachments)
            or not self._provider
            or not self._model
            or self._model.startswith("No models")
        ):
            return

        payload_text, ui_text, images, attachment_texts = self._compose_user_message(user_text)

        # Preserve attachments for history entry before clearing UI state
        attachments_copy = [dict(att) for att in self._attachments]

        self.input_edit.clear()
        self._attachments = []
        self._refresh_attachments_ui()
        self._append_message("user", ui_text)
        # Store structured entry: keep payload (content), original user_text and attachments
        self._add_to_history(
            "user",
            payload_text,
            user_text=user_text,
            attachments=attachments_copy,
        )
        self._set_ui_state(streaming=True)
        self.stop_btn.setEnabled(False)
        self._stop_event = False
        self._send_to_api()
        self.chat_widget.layout().activate()
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_add_attachment(self):
        """Open a file picker and stage selected files for the next message."""
        if not self._is_popup_valid():
            return
        files: list[str] = []
        popup = self._popup_chat
        # Store original flags and switch to Tool window to prevent auto-close on focus loss
        original_flags = popup.windowFlags()
        try:
            popup.set_auto_close_enabled(False)
            popup.setWindowFlags(
                Qt.WindowType.Tool
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.NoDropShadowWindowHint
            )
            popup.show()  # Required after changing window flags

            files, _ = QFileDialog.getOpenFileNames(
                None,
                "Select files",
                "",
                "All Files (*)",
            )
        finally:
            if popup and self._is_popup_valid():
                popup.setWindowFlags(original_flags)
                popup.show()  # Required after changing window flags
                popup.set_auto_close_enabled(True)

        if not files:
            return

        added_any = False
        for file_path in files:
            if self._add_attachment(file_path):
                added_any = True

        if added_any:
            self._refresh_attachments_ui()
            self._update_send_button_state()

    def _handle_paste_mime(self, mime) -> bool:
        """Handle pasted files/images from the clipboard. Returns True if handled."""
        if not self._is_popup_valid():
            return False

        added_any = False

        # Handle file paths from clipboard (e.g., copied files from Explorer)
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    if self._add_attachment(url.toLocalFile()):
                        added_any = True
            if added_any:
                self._refresh_attachments_ui()
                self._update_send_button_state()
            # Return True even if files were rejected to prevent default paste behavior (such as pasting file-urls to the input field)
            return True

        # Handle image data from clipboard
        if mime.hasImage():
            image_data = mime.imageData()
            if isinstance(image_data, QImage):
                try:
                    # Convert QImage directly to base64 without using temp files
                    buffer = QBuffer()
                    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                    image_data.save(buffer, "PNG")
                    img_bytes = buffer.data().data()
                    buffer.close()

                    # Compress if needed to fit within max_image_bytes
                    max_image_bytes = self._get_max_image_bytes()
                    compressed = False
                    if max_image_bytes > 0 and len(img_bytes) > max_image_bytes:
                        img_bytes, compressed = self._compress_image_if_needed(img_bytes, max_image_bytes)

                    # Create attachment dict directly from memory
                    b64_data = base64.b64encode(img_bytes).decode("ascii")
                    image_url = f"data:image/png;base64,{b64_data}"

                    # Generate a unique identifier for this clipboard image
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    clipboard_name = f"clipboard_image_{timestamp}.png"

                    attachment = {
                        "path": clipboard_name,  # Virtual path identifier
                        "name": clipboard_name,
                        "size": len(img_bytes),
                        "is_image": True,
                        "image_url": image_url,
                        "prompt": f"[Image: {clipboard_name}{' (compressed)' if compressed else ''}]",
                        "is_clipboard": True,  # Mark as clipboard to avoid file operations
                        "compressed": compressed,
                    }

                    self._attachments.append(attachment)
                    added_any = True
                except Exception as e:
                    logging.exception(f"Failed to process clipboard image: {e}")
            # Return True even if image was rejected to prevent default paste behavior
            if added_any:
                self._refresh_attachments_ui()
                self._update_send_button_state()
            return True

        return False

    def _add_attachment(self, file_path: str) -> bool:
        """Read file metadata and safe preview content for prompt inclusion."""
        try:
            path = Path(file_path)
        except TypeError:
            return False

        if not path.exists() or not path.is_file():
            return False

        if any(att.get("path") == str(path) for att in self._attachments):
            return False

        attachment = self._read_attachment(path)
        if not attachment:
            return False

        self._attachments.append(attachment)
        return True

    def _read_attachment(self, path: Path) -> dict[str, Any] | None:
        """Return attachment payload with size-safe content for prompting."""
        try:
            raw = path.read_bytes()
        except Exception as e:
            logging.error(f"Failed to read attachment {path}: {e}")
            return None

        size = len(raw)
        suffix = path.suffix.lower()

        # Check if this is an image file
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }

        if suffix in image_extensions:
            # Check if images are supported
            max_image_bytes = self._get_max_image_bytes()
            if max_image_bytes == 0:
                # Reject images if not supported by this model
                QTimer.singleShot(
                    0,
                    lambda: QMessageBox.warning(
                        self,
                        "Images Not Supported",
                        f"{path.name} cannot be attached.\n\nThis model does not support image attachments.",
                    ),
                )
                return None

            # For images, compress if needed to get as close as possible to max_image_bytes
            if max_image_bytes > 0 and size > max_image_bytes:
                raw, compressed = self._compress_image_if_needed(raw, max_image_bytes)
                size = len(raw)
            else:
                compressed = False

            mime_type = mime_types.get(suffix, "image/png")
            b64_data = base64.b64encode(raw).decode("ascii")
            image_url = f"data:{mime_type};base64,{b64_data}"

            return {
                "path": str(path),
                "name": path.name,
                "size": size,
                "is_image": True,
                "image_url": image_url,
                "prompt": f"[Image: {path.name}{' (compressed)' if compressed else ''}]",
                "compressed": compressed,
            }

        # For non-image files, only allow plain text (UTF-8 decodable)
        # Binary files are not supported as the API only accepts text and image_url types
        max_attachment_bytes = self._get_max_attachment_bytes()
        truncated = False

        # Try to decode as UTF-8 text - if it fails, treat as binary
        try:
            content_str = raw.decode("utf-8")
        except UnicodeDecodeError:
            # Reject binary files that can't be decoded as UTF-8
            QTimer.singleShot(
                0,
                lambda: QMessageBox.warning(
                    self,
                    "Unsupported File Type",
                    f"{path.name} cannot be attached.\n\n"
                    f"Only text files and images are supported.\n"
                    f"This file appears to be binary and cannot be sent.",
                ),
            )
            return None

        # Truncate if needed (after successful decode)
        if max_attachment_bytes > 0 and size > max_attachment_bytes:
            content_str = content_str[:max_attachment_bytes]
            truncated = True

        header = (
            f"[Attachment: {path.name} | size={self._human_readable_size(size)}"
            + (" | truncated" if truncated else "")
            + "]"
        )

        prompt_block = f"{header}\n{content_str}"

        return {
            "path": str(path),
            "name": path.name,
            "size": size,
            "truncated": truncated,
            "is_image": False,
            "prompt": prompt_block,
        }

    def _remove_attachment(self, path: str):
        self._attachments = [att for att in self._attachments if att.get("path") != path]
        self._refresh_attachments_ui()
        self._update_send_button_state()

    def _restore_previous_focus(self):
        """Return focus to the window that was active before opening the chat popup."""
        if getattr(self, "_previous_hwnd", 0):
            try:
                set_foreground_hwnd(self._previous_hwnd)
            finally:
                self._previous_hwnd = 0

    def _refresh_attachments_ui(self):
        """Render small chips for staged attachments."""
        if not hasattr(self, "attachments_layout"):
            return

        layout = self.attachments_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        if not self._attachments:
            return

        for attachment in self._attachments:
            chip = QFrame()
            chip.setProperty("class", "attachment-chip")
            chip_layout = QHBoxLayout(chip)
            chip_layout.setContentsMargins(6, 2, 6, 2)
            chip_layout.setSpacing(4)

            name_label = QLabel(attachment["name"])
            name_label.setProperty("class", "attachment-label")
            remove_btn = QPushButton("x")
            remove_btn.setProperty("class", "attachment-remove-button")
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.setFixedWidth(20)
            remove_btn.setFixedHeight(20)
            remove_btn.clicked.connect(lambda _=False, p=attachment["path"]: self._remove_attachment(p))

            chip_layout.addWidget(name_label)
            chip_layout.addWidget(remove_btn)
            chip_layout.addStretch(1)
            layout.addWidget(chip)

    def _compose_user_message(self, user_text: str) -> tuple[str, str, list, list[str]]:
        """Return (payload_text, display_text, images, attachment_texts) including any attachments."""
        text_attachments = [att for att in self._attachments if not att.get("is_image")]
        image_attachments = [att for att in self._attachments if att.get("is_image")]

        # Build text payload for non-image attachments (for display/history)
        payload_text = user_text
        if text_attachments:
            lines = ["Attachments:"]
            for idx, att in enumerate(text_attachments, 1):
                lines.append(f"{idx}) {att['prompt']}")
            attachments_text = "\n".join(lines)
            payload_text = f"{user_text}\n\n{attachments_text}" if user_text else attachments_text

        # Build display text with size info
        display_text = user_text
        if self._attachments:
            lines = ["Attachments (sent to AI):"]
            for idx, att in enumerate(self._attachments, 1):
                info = f"{idx}) {att['name']} ({self._human_readable_size(att.get('size', 0))})"
                if att.get("truncated"):
                    info += " [truncated]"
                if att.get("compressed"):
                    info += " [compressed]"
                lines.append(info)
            display_summary = "\n".join(lines)
            display_text = f"{user_text}\n\n{display_summary}" if user_text else display_summary

        # Collect image URLs for multimodal API
        images = [att["image_url"] for att in image_attachments]

        # Return individual attachment texts for separate API text blocks
        attachment_texts = [att["prompt"] for att in text_attachments]

        return payload_text, display_text, images, attachment_texts

    def _prepare_attachments_for_display(self, attachments: list[dict] | None = None) -> str:
        """Prepare a short attachments summary string from staged or provided attachments."""
        attachments = self._attachments if attachments is None else attachments
        if not attachments:
            return ""

        lines = ["Attachments (sent to AI):"]
        for idx, attachment in enumerate(attachments, 1):
            info = f"{idx}) {attachment.get('name')} ({self._human_readable_size(attachment.get('size', 0))})"
            if attachment.get("truncated"):
                info += " [truncated]"
            if attachment.get("compressed"):
                info += " [compressed]"
            lines.append(info)
        return "\n".join(lines)

    def _compute_display_for_history_entry(self, entry: dict) -> str:
        """Compute a UI-friendly display string for a history entry.

        Backwards compatible: uses stored user_text + attachments summary, or falls back to content.
        """
        if not entry:
            return ""
        if entry.get("display"):
            return entry["display"]

        user_text = entry.get("user_text")
        attachments = entry.get("attachments") or []

        if user_text:
            attachments_display = self._prepare_attachments_for_display(attachments)
            return f"{user_text}\n\n{attachments_display}" if attachments_display else user_text

        return entry.get("content", "")

    def _on_stop_clicked(self):
        self._stop_event = True

        if hasattr(self, "_worker") and hasattr(self._worker, "client") and self._worker.client:
            try:
                self._worker.client.stop()
            except Exception:
                logging.error("Failed to stop the AI chat client gracefully.")
                pass

        if hasattr(self, "_streaming_state") and self._streaming_state.get("partial_text"):
            # Use history management
            history = AiChatWidget._persistent_chat_history.get(self._get_history_key(), [])
            if not history or history[-1]["role"] != "assistant":
                self._add_to_history("assistant", self._streaming_state["partial_text"])
            else:
                history[-1]["content"] = self._streaming_state["partial_text"]

        self._set_ui_state(streaming=False)
        if hasattr(self, "_streaming_state"):
            self._streaming_state["in_progress"] = False

    def _is_popup_valid(self):
        if self._popup_chat is None or not self._popup_chat.isVisible():
            return False
        # Check if the popup layout and buttons are still valid
        try:
            _ = self.chat_layout.count()
            _ = self.send_btn.isVisible()
            _ = self.stop_btn.isVisible()
        except RuntimeError:
            return False
        return True

    class _StreamWorker(QObject):
        chunk_signal = pyqtSignal(str)
        done_signal = pyqtSignal(str)
        error_signal = pyqtSignal(str)
        finished_signal = pyqtSignal()

        def __init__(
            self,
            provider_config,
            model,
            chat_history,
            stop_event_func,
            max_tokens,
            temperature,
            top_p,
        ):
            super().__init__()
            self.provider_config = provider_config
            self.model = model
            self.chat_history = chat_history
            self.stop_event_func = stop_event_func
            self.max_tokens = max_tokens
            self.temperature = temperature
            self.top_p = top_p
            self.client = None

        def run(self):
            try:
                self.client = AiChatClient(self.provider_config, self.model, self.max_tokens)
                full_text = ""
                for chunk in self.client.chat(self.chat_history, temperature=self.temperature, top_p=self.top_p):
                    if self.stop_event_func():
                        self.client.stop()
                        break
                    full_text += chunk
                    self.chunk_signal.emit(full_text)
                self.done_signal.emit(full_text)
            except Exception as e:
                self.error_signal.emit(str(e))
            finally:
                self.finished_signal.emit()

    def _start_thinking_animation(self, msg_label):
        self._thinking_label = msg_label
        self._thinking_step = 0
        if self._thinking_timer is not None:
            self._thinking_timer.stop()
            self._thinking_timer.deleteLater()
        self._thinking_timer = QTimer(self)
        self._thinking_timer.timeout.connect(self._update_thinking_animation)
        self._thinking_timer.start(300)
        self._update_thinking_animation()

    def _update_thinking_animation(self):
        if self._thinking_label is None:
            return
        dots = "." * (self._thinking_step % 4)
        self._thinking_label.setText(f"thinking {dots}")
        self._thinking_step += 1

    def _stop_thinking_animation(self):
        if self._thinking_timer is not None:
            self._thinking_timer.stop()
            self._thinking_timer.deleteLater()
            self._thinking_timer = None
        self._thinking_label = None
        self._thinking_step = 0

    def _send_to_api(self):
        msg_label = None
        instructions = None

        self._cleanup_previous_worker()

        self._append_message("assistant", "thinking ...")
        # Find the last assistant message label in the layout
        msg_label = None
        for i in reversed(range(self.chat_layout.count())):
            item = self.chat_layout.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, QWidget):
                layout = widget.layout()
                for j in range(layout.count()):
                    child = layout.itemAt(j).widget()
                    if isinstance(child, QLabel) and child.property("class") == "assistant-message":
                        msg_label = child
                        break
                if msg_label:
                    break
        if not self._is_popup_valid() or msg_label is None:
            return
        self._start_thinking_animation(msg_label)

        # Disable provider and model selection while streaming
        self.provider_btn.setEnabled(False)
        self.model_btn.setEnabled(False)
        if hasattr(self, "clear_btn"):
            self.clear_btn.setEnabled(False)

        # Get model configuration
        model_config = self._get_model_config()
        if model_config:
            instructions = model_config.get("instructions")
            max_tokens = model_config["max_tokens"]
            temperature = model_config["temperature"]
            top_p = model_config["top_p"]

            # Load instructions from file if specified, file must end with "_chatmode.md"
            if isinstance(instructions, str) and instructions.strip().endswith("_chatmode.md"):
                file_path = instructions.strip()
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            instructions = f.read()
                    except Exception:
                        instructions = None
                        logging.error(f"Failed to read instructions from {file_path}")
                else:
                    instructions = None
                    logging.error(f"Instructions file {file_path} does not exist")

        chat_history = list(self._get_current_history())
        if instructions:
            if not (chat_history and chat_history[0]["role"] == "system"):
                chat_history = [{"role": "system", "content": instructions}] + chat_history

        # Convert history to API format, handling multimodal messages with images
        api_messages = []
        for msg in chat_history:
            role = msg["role"]
            content = msg["content"]
            attachments = msg.get("attachments", [])

            if attachments and role == "user":
                # Build multimodal parts from attachments
                content_parts = []

                # Add user's main text first (if any)
                user_text = msg.get("user_text", "")
                if user_text:
                    content_parts.append({"type": "text", "text": user_text})

                # Add attachments (text files and images)
                for att in attachments:
                    if att.get("is_image"):
                        # Add image
                        content_parts.append({"type": "image_url", "image_url": {"url": att["image_url"]}})
                    else:
                        # Add text attachment as separate text block
                        content_parts.append({"type": "text", "text": att["prompt"]})

                api_messages.append({"role": role, "content": content_parts})
            else:
                api_messages.append({"role": role, "content": content})

        # Setup streaming state for reconnection
        self._streaming_state = {
            "in_progress": True,
            "msg_label": msg_label,
            "partial_text": "",
        }

        # Setup worker and thread
        self._thread = QThread()
        self._worker = self._StreamWorker(
            self._provider_config,
            self._model,
            api_messages,
            lambda: getattr(self, "_stop_event", False),
            max_tokens,
            temperature,
            top_p,
        )
        self._worker.moveToThread(self._thread)
        self._worker.chunk_signal.connect(self._streaming_chunk_handler, Qt.ConnectionType.QueuedConnection)
        self._worker.done_signal.connect(self._streaming_done_handler, Qt.ConnectionType.QueuedConnection)
        self._worker.error_signal.connect(self._streaming_error_handler, Qt.ConnectionType.QueuedConnection)
        self._worker.finished_signal.connect(self._thread.quit, Qt.ConnectionType.QueuedConnection)
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _streaming_chunk_handler(self, text):
        """Handle streaming text chunks from the worker"""
        if not hasattr(self, "_streaming_state") or not self._streaming_state:
            return

        msg_label = self._streaming_state.get("msg_label")
        if not msg_label:
            return

        self._streaming_state["partial_text"] = text
        self._stop_thinking_animation()
        if self._is_popup_valid():
            try:
                self.stop_btn.setEnabled(True)
            except RuntimeError:
                pass
        try:
            msg_label.setText(text)
        except RuntimeError:
            pass

    def _cleanup_previous_worker(self):
        """Clean up previous worker and thread before starting new one"""
        if hasattr(self, "_worker") and self._worker:
            try:
                # Disconnect all signals
                self._worker.chunk_signal.disconnect()
                self._worker.done_signal.disconnect()
                self._worker.error_signal.disconnect()
                self._worker.finished_signal.disconnect()
            except Exception:
                pass
            self._worker = None

        if hasattr(self, "_thread") and self._thread:
            try:
                # Check if thread still exists and is running
                if not self._thread.isFinished():
                    self._thread.quit()
                    if self._thread.isRunning():
                        self._thread.terminate()
            except (RuntimeError, AttributeError):
                # Thread object has been deleted or is invalid
                pass
            # Clear the reference
            self._thread = None

    def _streaming_done_handler(self, text):
        if hasattr(self, "_streaming_state"):
            self._streaming_state["in_progress"] = False
        msg_label = self._streaming_state.get("msg_label") if hasattr(self, "_streaming_state") else None
        self._stop_thinking_animation()

        # Update chat history
        key = self._get_history_key()
        history = AiChatWidget._persistent_chat_history.get(key, [])
        if history and history[-1]["role"] == "assistant":
            history[-1]["content"] = text
        else:
            self._add_to_history("assistant", text)

        if self._is_popup_valid() and msg_label is not None:
            try:
                msg_label.setText(text)
                self._set_ui_state(streaming=False)
            except RuntimeError:
                pass
        else:
            self._new_notification = True
            self._update_label()

        # Thread will quit automatically via finished signal, just clear reference when safe
        if hasattr(self, "_thread") and self._thread:
            # Schedule cleanup after thread finishes naturally
            QTimer.singleShot(50, self._clear_thread_reference)

    def _streaming_error_handler(self, err):
        if hasattr(self, "_streaming_state"):
            self._streaming_state["in_progress"] = False
        msg_label = self._streaming_state.get("msg_label") if hasattr(self, "_streaming_state") else None
        self._stop_thinking_animation()
        reply = f"[Error: {err}]"

        # Update chat history
        key = self._get_history_key()
        history = AiChatWidget._persistent_chat_history.get(key, [])
        if history and history[-1]["role"] == "assistant":
            history[-1]["content"] = reply
        else:
            self._add_to_history("assistant", reply)

        if self._is_popup_valid() and msg_label is not None:
            try:
                self._remove_last_message()
                self._append_message("assistant", reply)
                self._set_ui_state(streaming=False)
            except RuntimeError:
                pass

        # Thread will quit automatically via finished signal, just clear reference when safe
        if hasattr(self, "_thread") and self._thread:
            # Schedule cleanup after thread finishes naturally
            QTimer.singleShot(50, self._clear_thread_reference)

    def _remove_placeholder(self):
        """Remove all empty-chat widgets if they exist with immediate cleanup"""
        for i in reversed(range(self.chat_layout.count())):
            item = self.chat_layout.itemAt(i)
            widget = item.widget()
            if widget and widget.property("class") == "empty-chat":
                self.chat_layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()
                break

    def _show_context_menu(self, widget, pos, is_input=False):
        """Show context menu for messages and input field"""
        context_menu = QMenu(widget)
        context_menu.setProperty("class", "context-menu")

        if is_input:
            text_edit = widget

            select_all_action = context_menu.addAction("Select All")
            select_all_action.triggered.connect(lambda: text_edit.selectAll())
            select_all_action.setEnabled(bool(text_edit.toPlainText()))

            selected_text = text_edit.textCursor().selectedText()
            if selected_text:
                copy_action = context_menu.addAction("Copy")
                copy_action.triggered.connect(lambda: QApplication.clipboard().setText(selected_text))

                cut_action = context_menu.addAction("Cut")
                cut_action.triggered.connect(
                    lambda: (
                        QApplication.clipboard().setText(selected_text),
                        text_edit.textCursor().removeSelectedText(),
                    )
                )

            clipboard = QApplication.clipboard()
            clipboard_text = clipboard.text()
            if clipboard_text:
                paste_action = context_menu.addAction("Paste")
                paste_action.triggered.connect(lambda: text_edit.insertPlainText(clipboard_text))

            if text_edit.toPlainText():
                context_menu.addSeparator()
                clear_action = context_menu.addAction("Clear")
                clear_action.triggered.connect(lambda: text_edit.clear())

        else:
            label = widget
            selected_text = label.selectedText()

            if selected_text:
                copy_selected_action = context_menu.addAction("Copy")

                def copy_selected():
                    try:
                        self._simulate_shortcut(label, Qt.Key.Key_C)
                    except Exception:
                        QApplication.clipboard().setText(selected_text)

                copy_selected_action.triggered.connect(copy_selected)

            select_all_action = context_menu.addAction("Select All")

            def select_all():
                try:
                    self._simulate_shortcut(label, Qt.Key.Key_A)
                except Exception:
                    pass

            select_all_action.triggered.connect(select_all)
        apply_qmenu_style(context_menu)

        global_pos = widget.mapToGlobal(pos)
        # For input field, show menu above the input to prevent closing the popup
        if is_input:
            menu_height = context_menu.sizeHint().height()
            global_pos.setY(global_pos.y() - menu_height)

        if is_input:
            QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)
            try:
                context_menu.exec(global_pos)
            finally:
                QApplication.restoreOverrideCursor()
        else:
            context_menu.exec(global_pos)

    def _simulate_shortcut(self, widget, key):
        """Simulate a Ctrl+<key> keyboard shortcut on the given widget."""
        press_event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.ControlModifier)
        release_event = QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.ControlModifier)
        QApplication.sendEvent(widget, press_event)
        QApplication.sendEvent(widget, release_event)

    def _remove_last_message(self):
        """Remove the last message from chat layout with immediate cleanup"""
        if self.chat_layout.count() > 1:
            item = self.chat_layout.itemAt(self.chat_layout.count() - 2)
            if item:
                widget = item.widget()
                if widget:
                    self.chat_layout.removeWidget(widget)
                    widget.setParent(None)
                    widget.deleteLater()

    def _get_model_label(self):
        if not self._model:
            return "Select model"
        model_config = self._get_model_config()
        return model_config.get("label", self._model) if model_config else self._model

    def _get_history_key(self):
        """
        Generate a unique key for the chat history based on bar_id, provider, and model
        We will use id(self) to ensure uniqueness across instances
        In that way, we can have different chat histories for the same provider and model
        """
        return (id(self), self._provider, self._model)

    def _save_current_history(self):
        """Save the current chat history to persistent storage"""
        if self._provider and self._model is not None:
            key = self._get_history_key()
            AiChatWidget._persistent_chat_history[key] = list(self._get_current_history())

    def _get_current_history(self):
        """Get the current chat history for the active provider and model"""
        key = self._get_history_key()
        history = AiChatWidget._persistent_chat_history.get(key, [])
        return history

    def _add_to_history(
        self,
        role: str,
        content: str,
        user_text: str = None,
        attachments: list[dict] | None = None,
    ):
        """Add a message to chat history.

        We store `content` (what is sent to the API), optional `user_text` (original
        text typed by the user) and `attachments` (list of attachment metadata including
        image_url and prompt fields). UI display is computed lazily from these fields.
        """
        key = self._get_history_key()
        if key not in AiChatWidget._persistent_chat_history:
            AiChatWidget._persistent_chat_history[key] = []

        history = AiChatWidget._persistent_chat_history[key]
        entry: dict = {"role": role, "content": content}
        if user_text is not None:
            entry["user_text"] = user_text
        if attachments:
            entry["attachments"] = attachments
        history.append(entry)

    def _human_readable_size(self, size_bytes: int) -> str:
        """Convert byte counts to small human-readable strings."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        for unit in ("KB", "MB", "GB"):
            size_bytes /= 1024.0
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
        return f"{size_bytes:.1f} TB"

    def _scroll_to_bottom(self):
        """Smoothly scroll chat area to bottom"""
        if hasattr(self, "chat_scroll") and self.chat_scroll:
            scrollbar = self.chat_scroll.verticalScrollBar()
            end_value = scrollbar.maximum()
            if scrollbar.value() == end_value:
                return
            animation = QPropertyAnimation(scrollbar, b"value", self)
            animation.setDuration(200)
            animation.setStartValue(scrollbar.value())
            animation.setEndValue(end_value)
            animation.start()
            self._scroll_animation = animation

    def _clear_thread_reference(self):
        """Safely clear thread reference after it has finished"""
        if hasattr(self, "_thread") and self._thread:
            try:
                if self._thread.isFinished():
                    self._thread = None
                else:
                    QTimer.singleShot(50, self._clear_thread_reference)
            except (RuntimeError, AttributeError):
                self._thread = None
