from datetime import datetime

from PyQt6.QtCore import QPropertyAnimation, Qt, QTimer
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.utils.widgets.ai_chat.constants import (
    BATCH_RENDER_DELAY_MS,
    BATCH_RENDER_SIZE,
    SCROLL_ANIMATION_MS,
    THINKING_PLACEHOLDER,
)


class ChatRender:
    def __init__(self, owner):
        self._owner = owner
        self._history_to_load: list[dict] | None = None
        self._streaming_partial_to_load: str | None = None
        self._message_batch_index: int | None = None
        self._batch_size: int = BATCH_RENDER_SIZE

    def clear_batch_state(self):
        self._history_to_load = None
        self._streaming_partial_to_load = None
        self._message_batch_index = None

    def render_chat_history(self):
        self.clear_batch_state()

        for i in reversed(range(self._owner.chat_layout.count())):
            item = self._owner.chat_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                self._owner.chat_layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()

        history = self._owner._chat_session.get_history(self._owner._provider, self._owner._model_index)

        streaming_partial = None
        if self._owner._chat_session.stream.in_progress:
            streaming_partial = self._owner._chat_session.stream.partial_text
        if not history and not streaming_partial:
            self.show_empty_chat_placeholder()
        else:
            QTimer.singleShot(BATCH_RENDER_DELAY_MS, lambda: self.load_all_messages_async(history, streaming_partial))
        self._owner.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def show_empty_chat_placeholder(self):
        self.remove_placeholder()
        hour = datetime.now().hour
        greeting = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 18 else "Good evening"
        prompt_by_greeting = {
            "Good morning": "What can I help you get done this morning?",
            "Good afternoon": "How can I help you today?",
            "Good evening": "What can I do for you this evening?",
        }
        placeholder = QWidget()
        placeholder.setProperty("class", "empty-chat")
        layout = QVBoxLayout(placeholder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        label1 = QLabel(greeting)
        label1.setProperty("class", "greeting")
        label1.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        label2 = QLabel(prompt_by_greeting.get(greeting, "How can I help you?"))
        label2.setProperty("class", "message")
        label2.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label1)
        layout.addWidget(label2)
        self._owner.chat_layout.insertWidget(self._owner.chat_layout.count() - 1, placeholder, stretch=1)

    def load_all_messages_async(self, history, streaming_partial):
        filtered_history = list(history)
        if streaming_partial and filtered_history:
            last_msg = filtered_history[-1]
            if last_msg["role"] == "assistant":
                filtered_history = filtered_history[:-1]
        self._message_batch_index = 0
        self._history_to_load = filtered_history
        self._streaming_partial_to_load = streaming_partial
        self._batch_size = BATCH_RENDER_SIZE
        self.load_next_message_batch()

    def load_next_message_batch(self):
        if not hasattr(self._owner, "chat_layout"):
            return
        chat_layout = self._owner.chat_layout
        try:
            parent = chat_layout.parentWidget()
        except RuntimeError:
            return
        if parent is None or not isinstance(parent, QWidget) or parent is not self._owner.chat_widget:
            return
        if self._history_to_load is None:
            return

        total = len(self._history_to_load)
        start_idx = self._message_batch_index or 0
        end_idx = min(start_idx + self._batch_size, total)

        for idx in range(start_idx, end_idx):
            msg = self._history_to_load[idx]
            display_text = self._owner._chat_session.history.compute_display_for_history_entry(msg)
            self._owner._append_message(msg["role"], display_text)

        self._message_batch_index = end_idx

        if self._message_batch_index < total:
            QTimer.singleShot(BATCH_RENDER_DELAY_MS, self.load_next_message_batch)
        else:
            if self._streaming_partial_to_load is not None:
                partial = self._streaming_partial_to_load or THINKING_PLACEHOLDER
                self._owner._append_message("assistant", partial)
                msg_label = self._owner._chat_session.find_last_assistant_label(self._owner.chat_layout)
                if self._owner._chat_session.stream.in_progress and msg_label is not None:
                    self._owner._chat_session.stream.msg_label = msg_label
                    if hasattr(self._owner, "_worker"):
                        try:
                            self._owner._worker.chunk_signal.disconnect(
                                self._owner._stream_worker_manager.streaming_chunk_handler
                            )
                        except Exception:
                            pass
                        self._owner._worker.chunk_signal.connect(
                            self._owner._stream_worker_manager.streaming_chunk_handler
                        )
                    if not self._streaming_partial_to_load:
                        self._owner._stream_ui.start_thinking_animation(msg_label)
            self.clear_batch_state()

    def remove_placeholder(self):
        for i in reversed(range(self._owner.chat_layout.count())):
            item = self._owner.chat_layout.itemAt(i)
            widget = item.widget()
            if widget and widget.property("class") == "empty-chat":
                self._owner.chat_layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()
                break

    def remove_last_message(self):
        if self._owner.chat_layout.count() > 1:
            item = self._owner.chat_layout.itemAt(self._owner.chat_layout.count() - 2)
            if item:
                widget = item.widget()
                if widget:
                    self._owner.chat_layout.removeWidget(widget)
                    widget.setParent(None)
                    widget.deleteLater()

    def scroll_to_bottom(self):
        """Smoothly scroll chat area to bottom."""
        if hasattr(self._owner, "chat_scroll") and self._owner.chat_scroll:
            scrollbar = self._owner.chat_scroll.verticalScrollBar()
            end_value = scrollbar.maximum()
            if scrollbar.value() == end_value:
                return
            animation = QPropertyAnimation(scrollbar, b"value", self._owner)
            animation.setDuration(SCROLL_ANIMATION_MS)
            animation.setStartValue(scrollbar.value())
            animation.setEndValue(end_value)
            animation.start()
            self._owner._scroll_animation = animation
