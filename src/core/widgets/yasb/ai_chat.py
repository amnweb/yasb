from typing import Any

from humanize import naturalsize
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from core.utils.tooltip import set_tooltip
from core.utils.utilities import LoaderLine, add_shadow
from core.utils.widgets.ai_chat.attachment_manager import AttachmentManager
from core.utils.widgets.ai_chat.chat_render import ChatRender
from core.utils.widgets.ai_chat.chat_session import ChatSession
from core.utils.widgets.ai_chat.constants import THINKING_PLACEHOLDER
from core.utils.widgets.ai_chat.context_menu_service import ContextMenuService
from core.utils.widgets.ai_chat.input_controller import InputController
from core.utils.widgets.ai_chat.provider_model_manager import ProviderModelManager
from core.utils.widgets.ai_chat.stream_ui_controller import StreamUiController
from core.utils.widgets.ai_chat.stream_worker_manager import StreamWorkerManager
from core.utils.widgets.ai_chat.ui_components import AiChatPopup, ChatInputEdit, ChatMessageBrowser, NotificationLabel
from core.utils.widgets.ai_chat.ui_helpers import FloatingWindowController, FocusManager, LabelBuilder
from core.utils.widgets.animation_manager import AnimationManager
from core.utils.win32.utilities import apply_qmenu_style
from core.utils.win32.window_actions import force_foreground_focus
from core.validation.widgets.yasb.ai_chat import AiChatConfig
from core.widgets.base import BaseWidget


class AiChatWidget(BaseWidget):
    validation_schema = AiChatConfig
    _persistent_chat_history = {}

    def __init__(self, config: AiChatConfig):
        super().__init__(class_name="ai-chat-widget")
        self.config = config
        self._label_content = config.label
        self._icons = config.icons.model_dump(by_alias=True)
        self._notification_dot: dict[str, Any] = config.notification_dot.model_dump()
        self._start_floating = config.start_floating
        self._providers = [x.model_dump() for x in config.providers]
        self._provider = None
        self._provider_config = None
        self._model = None
        self._model_index = None
        self._popup_chat = None
        self._animation = config.animation.model_dump()
        self._chat = config.chat.model_dump()
        self._label_shadow = config.label_shadow.model_dump()
        self._container_shadow = config.container_shadow.model_dump()
        self._notification_label: NotificationLabel | None = None
        self._input_draft = ""
        self._attachments: list[dict[str, Any]] = []
        self._chat_session = ChatSession(
            AiChatWidget._persistent_chat_history,
            lambda size_bytes: naturalsize(size_bytes, binary=True, format="%.1f"),
            id(self),
        )
        self._attachment_manager = AttachmentManager(self)
        self._chat_render = ChatRender(self)
        self._context_menu = ContextMenuService(self)
        self._stream_ui = StreamUiController(self)
        self._provider_model_manager = ProviderModelManager(self)
        self._provider_model_manager.initialize_provider_and_model()
        self._input_controller = InputController(self)
        self._stream_worker_manager = StreamWorkerManager(self)
        self._focus_manager = FocusManager(self)
        self._floating_controller = FloatingWindowController(self)
        self._label_builder = LabelBuilder(self)
        self._model_list_workers: list[tuple[object, Any]] = []
        self._previous_hwnd = 0
        self._is_floating = False
        self._original_position = None
        self._widget_container_layout = QHBoxLayout()
        self._widget_container_layout.setSpacing(0)
        self._widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._widget_container = QFrame()
        self._widget_container.setLayout(self._widget_container_layout)
        self._widget_container.setProperty("class", "widget-container")
        add_shadow(self._widget_container, self._container_shadow)
        self.widget_layout.addWidget(self._widget_container)

        self._label_builder.create_dynamically_label(self._label_content)

        self.register_callback("toggle_chat", self._toggle_chat)
        self.callback_left = self.config.callbacks.on_left
        self.callback_right = self.config.callbacks.on_right
        self.callback_middle = self.config.callbacks.on_middle
        self._new_notification = False

    def _update_label(self):
        """Update the label content and notification dot state."""
        if not self._notification_dot["enabled"]:
            return

        if self._notification_label is not None:
            self._notification_label.show_dot(self._new_notification)

    def _set_header_loader(self, active: bool):
        loader = getattr(self, "header_loader_line", None)
        if loader is None:
            return
        try:
            if active:
                loader.start()
            else:
                loader.stop()
        except RuntimeError:
            return

    def _get_model_config(self):
        """Get the configuration for the current model"""
        if not (self._provider_config and self._provider_config.get("models")):
            return None
        if self._model_index is not None and 0 <= self._model_index < len(self._provider_config["models"]):
            return self._provider_config["models"][self._model_index]
        return next((m for m in self._provider_config["models"] if m["name"] == self._model), None)

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
            self._close_popup()

    def _close_popup(self):
        if self._popup_chat is None:
            return
        self._popup_chat.hide_animated()

    def _build_chat_button(
        self,
        parent: QWidget,
        label: str,
        class_name: str,
        on_click,
        visible: bool = True,
    ) -> QPushButton:
        btn = QPushButton(label, parent)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("class", class_name)
        if on_click:
            btn.clicked.connect(on_click)
        btn.setVisible(visible)
        return btn

    def _open_menu(self, menu: QMenu, button: QPushButton):
        # If menu is already visible, close it (toggle behavior)
        if menu.isVisible():
            menu.close()
            return
        # Skip if menu was just closed (flag set by aboutToHide)
        if getattr(menu, "_just_closed", False):
            return
        if self._popup_chat:
            self._popup_chat.set_block_deactivate(True)
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))
        if self._popup_chat:
            self._popup_chat.set_block_deactivate(False)

    def _on_menu_hide(self, menu: QMenu):
        """Called when menu is about to hide - set flag and clear it after a short delay"""
        menu._just_closed = True
        QTimer.singleShot(150, lambda: setattr(menu, "_just_closed", False))

    def _create_header(self, layout: QVBoxLayout):
        header_widget = QFrame()
        header_widget.setProperty("class", "chat-header")
        header_widget.mousePressEvent = lambda event: self._floating_controller.header_mouse_press(event)
        header_widget.mouseMoveEvent = lambda event: self._floating_controller.header_mouse_move(event)
        header_widget.mouseReleaseEvent = lambda event: self._floating_controller.header_mouse_release(event)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setSpacing(0)
        header_layout.setContentsMargins(0, 0, 0, 0)

        selection_row = QHBoxLayout()
        selection_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.provider_btn = QPushButton(self._provider or "Select provider")
        self.provider_btn.setProperty("class", "provider-button")
        self.provider_btn.setStyleSheet(
            """
            QPushButton {
                text-align: left;
                padding-left: 8px;
            }
            QPushButton::menu-indicator { image: none; width: 0px; height: 0px; }
            """
        )
        self.provider_menu = QMenu(self.provider_btn)
        self.provider_menu.setProperty("class", "context-menu")
        self.provider_menu.setStyleSheet("QMenu::indicator { width: 0px; height: 0px; }")
        self.provider_menu.aboutToHide.connect(lambda: self._on_menu_hide(self.provider_menu))
        apply_qmenu_style(self.provider_menu)
        self.provider_btn.clicked.connect(lambda: self._open_menu(self.provider_menu, self.provider_btn))
        self._provider_model_manager.populate_provider_menu()
        self.model_btn = QPushButton(self._get_model_label())
        self.model_btn.setProperty("class", "model-button")
        self.model_btn.setStyleSheet(
            """
            QPushButton {
                text-align: left;
                padding-left: 8px;
            }
            QPushButton::menu-indicator { image: none; width: 0px; height: 0px; }
            """
        )
        self.model_btn.setEnabled(bool(self._provider_config and self._provider_config.get("models")))
        self.model_menu = QMenu(self.model_btn)
        self.model_menu.setProperty("class", "context-menu")
        self.model_menu.setStyleSheet("QMenu::indicator { width: 0px; height: 0px; }")
        self.model_menu.aboutToHide.connect(lambda: self._on_menu_hide(self.model_menu))
        apply_qmenu_style(self.model_menu)
        self.model_menu.aboutToShow.connect(
            lambda: (
                [
                    action.setChecked(
                        action.data() == self._model_index
                        if self._provider_config and self._provider_config.get("models")
                        else False
                    )
                    for action in self.model_menu.actions()
                ],
            )
        )
        self.model_btn.clicked.connect(lambda: self._open_menu(self.model_menu, self.model_btn))
        self._provider_model_manager.populate_model_menu()

        selection_row.addWidget(self.provider_btn, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        selection_row.addWidget(self.model_btn, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        selection_row.addStretch()

        self._is_floating = False
        self.float_btn = self._build_chat_button(
            header_widget,
            self._icons["float_on"],
            "float-button",
            self._floating_controller.toggle_floating,
        )
        set_tooltip(self.float_btn, "Float window")
        selection_row.addWidget(self.float_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.close_btn = self._build_chat_button(
            header_widget,
            self._icons["close"],
            "close-button",
            self._close_popup,
            visible=False,
        )
        set_tooltip(self.close_btn, "Close window")
        selection_row.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        header_layout.addLayout(selection_row)
        layout.addWidget(header_widget)
        self._header_widget = header_widget
        self.header_loader_line = LoaderLine(self._header_widget)
        self.header_loader_line.attach_to_widget(self._header_widget)

    def _create_chat_area(self, layout: QVBoxLayout):
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chat_scroll.setProperty("class", "chat-content")
        self.chat_scroll.setStyleSheet(
            """
            QScrollBar:vertical { border: none; background:transparent; width: 4px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.2); min-height: 10px; border-radius: 2px; }
            QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.35); }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
            """
        )

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
        self._chat_render.render_chat_history()

    def _create_footer(self, layout: QVBoxLayout):
        footer = QFrame()
        footer.setProperty("class", "chat-footer")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(6)

        attachments_row = QHBoxLayout()
        attachments_row.setContentsMargins(0, 0, 0, 0)
        attachments_row.setSpacing(6)
        self.attachments_layout = attachments_row
        footer_layout.addLayout(attachments_row)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(4)
        input_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.attach_btn = self._build_chat_button(
            footer,
            self._icons["attach"],
            "attach-button",
            self._attachment_manager.add_attachments_via_dialog,
        )
        input_row.addWidget(self.attach_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.input_wrapper = QFrame()
        self.input_wrapper.setProperty("class", "chat-input-wrapper")
        input_wrapper_layout = QHBoxLayout(self.input_wrapper)
        input_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        input_wrapper_layout.setSpacing(0)

        self.input_edit = ChatInputEdit()
        self.input_edit.setPlaceholderText("Type your message...")
        self.input_edit.send_message.connect(self._input_controller.on_send_clicked)
        self.input_edit.text_changed.connect(self._input_controller.update_send_button_state)
        self.input_edit.focus_changed.connect(self._on_input_focus_changed)
        self.input_edit.set_streaming(False)
        self.input_edit.set_parent_widget(self)
        if hasattr(self, "_input_draft") and self._input_draft:
            self.input_edit.setPlainText(self._input_draft)
        input_wrapper_layout.addWidget(self.input_edit)
        input_row.addWidget(self.input_wrapper, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.send_btn = self._build_chat_button(
            footer,
            self._icons["send"],
            "send-button",
            self._input_controller.on_send_clicked,
        )
        input_row.addWidget(self.send_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.stop_btn = self._build_chat_button(
            footer,
            self._icons["stop"],
            "stop-button",
            self._input_controller.on_stop_clicked,
            visible=False,
        )
        input_row.addWidget(self.stop_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.clear_btn = self._build_chat_button(
            footer,
            self._icons["clear"],
            "clear-button",
            self._on_clear_chat,
        )
        input_row.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        footer_layout.addLayout(input_row)
        layout.addWidget(footer)
        self._attachment_manager.refresh_attachments_ui()

    def _show_chat(self):
        """Show the AI chat popup with all components initialized."""
        self._new_notification = False
        self._update_label()

        # Remember the current foreground window so we can restore focus when closing
        self._focus_manager.remember_foreground()

        self._popup_chat = AiChatPopup(
            self,
            self._chat["blur"],
            self._chat["round_corners"],
            self._chat["round_corners_type"],
            self._chat["border_color"],
        )
        self._popup_chat.setProperty("class", "ai-chat-popup")

        self._popup_chat.destroyed.connect(self._input_controller.on_popup_destroyed)
        self._popup_chat.destroyed.connect(self._stream_ui.stop_thinking_animation)

        layout = QVBoxLayout(self._popup_chat)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._create_header(layout)
        self._create_chat_area(layout)
        self._create_footer(layout)
        self._popup_chat.setPosition(
            alignment=self._chat["alignment"],
            direction=self._chat["direction"],
            offset_left=self._chat["offset_left"],
            offset_top=self._chat["offset_top"],
        )
        self._popup_chat.show()
        if self._start_floating:
            self._floating_controller.toggle_floating()
        force_foreground_focus(int(self._popup_chat.winId()))
        self._stream_ui.reconnect_streaming_if_needed()
        if self._chat_session.stream.in_progress:
            self._stream_ui.set_ui_state(streaming=True)
        else:
            self._input_controller.update_send_button_state()

    def _append_error_message(self, error_text: str):
        """Append an error message to the chat"""
        self._append_message("assistant", f"Error: {error_text}", is_error=True)

    def _append_message(self, role, text, is_error=False):
        """Append a message to the chat layout"""
        self._chat_render.remove_placeholder()
        row = QFrame()
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        icon_label = QLabel()
        icon_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        msg_wrapper = QFrame()
        msg_wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        msg_wrapper_layout = QVBoxLayout(msg_wrapper)
        msg_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        msg_wrapper_layout.setSpacing(0)

        msg_label = ChatMessageBrowser()
        msg_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        msg_label.set_parent_widget(self)
        msg_wrapper_layout.addWidget(msg_label)

        if role == "user":
            msg_label.setText(text)
            msg_wrapper.setProperty("class", "user-message")
            msg_label.setProperty("class", "text")
        else:
            icon_label.setText(self._icons["assistant"])
            icon_label.setProperty("class", "assistant-icon")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
            msg_label.setText(text)
            msg_wrapper.setProperty("class", "assistant-message")
            msg_label.setProperty("class", "text")

            # Add copy button row for assistant messages
            copy_row = QFrame()
            copy_row.setStyleSheet("background: transparent;")
            copy_row_layout = QHBoxLayout(copy_row)
            copy_row_layout.setContentsMargins(0, 0, 0, 0)
            copy_row_layout.setSpacing(0)
            copy_row_layout.addStretch()

            copy_btn = QPushButton(self._icons["copy"])
            copy_btn.setProperty("class", "copy-button")
            copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            copy_btn.clicked.connect(lambda checked, ml=msg_label, btn=copy_btn: self._copy_message_content(ml, btn))
            copy_row_layout.addWidget(copy_btn)

            msg_wrapper_layout.addWidget(copy_row)
            # Hide copy button during streaming or for error messages
            copy_row.setVisible(text != THINKING_PLACEHOLDER and not is_error)
            # Store reference to copy row for later access
            msg_label.copy_row = copy_row

        row_layout.addWidget(icon_label)
        row_layout.addWidget(msg_wrapper)

        insert_pos = self.chat_layout.count() - 1
        self.chat_layout.insertWidget(insert_pos, row)

    def _on_clear_chat(self):
        self._chat_session.clear_history(self._provider, self._model_index)
        self._stream_worker_manager.reset_copilot_session(self._provider, self._model_index)
        self._chat_render.render_chat_history()
        self._attachments = []
        self._attachment_manager.refresh_attachments_ui()
        self._input_controller.update_send_button_state()

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

    def _get_model_label(self):
        if not self._model:
            return "Select model"
        model_config = self._get_model_config()
        return model_config.get("label", self._model) if model_config else self._model

    def _copy_message_content(self, msg_label, copy_btn):
        """Copy the plain text content of a message to clipboard"""
        try:
            text = msg_label.toPlainText()
            if text:
                QApplication.clipboard().setText(text)
                original_icon = self._icons["copy"]
                copy_btn.setText(self._icons["copy_check"])
                QTimer.singleShot(2000, lambda: self._restore_copy_icon(copy_btn, original_icon))
        except RuntimeError:
            pass

    def _restore_copy_icon(self, copy_btn, icon):
        """Restore the copy button icon after feedback"""
        try:
            copy_btn.setText(icon)
        except RuntimeError:
            pass

    def _on_input_focus_changed(self, focused: bool):
        """Handle input focus change to update wrapper styling"""
        try:
            if focused:
                self.input_wrapper.setProperty("class", "chat-input-wrapper focused")
            else:
                self.input_wrapper.setProperty("class", "chat-input-wrapper")
            self.input_wrapper.style().unpolish(self.input_wrapper)
            self.input_wrapper.style().polish(self.input_wrapper)
        except RuntimeError:
            pass
