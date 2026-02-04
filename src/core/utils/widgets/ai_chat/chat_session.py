from dataclasses import dataclass
from typing import Callable

from PyQt6.QtWidgets import QTextBrowser, QWidget

from core.utils.widgets.ai_chat.constants import THINKING_PLACEHOLDER
from core.utils.widgets.ai_chat.message_composer import format_attachments_for_display


@dataclass
class StreamState:
    in_progress: bool = False
    partial_text: str = ""
    msg_label: QTextBrowser | None = None


class ChatHistoryManager:
    def __init__(self, history_store: dict, size_formatter: Callable[[int], str]):
        self._store = history_store
        self._size_formatter = size_formatter

    def get(self, key) -> list[dict]:
        return self._store.get(key, [])

    def set(self, key, history: list[dict]):
        self._store[key] = list(history)

    def clear(self, key):
        if key in self._store:
            del self._store[key]

    def add_entry(
        self,
        key,
        role: str,
        content: str,
        user_text: str | None = None,
        attachments: list[dict] | None = None,
    ):
        if key not in self._store:
            self._store[key] = []

        history = self._store[key]
        entry: dict = {"role": role, "content": content}
        if user_text is not None:
            entry["user_text"] = user_text
        if attachments:
            entry["attachments"] = attachments
        history.append(entry)
        return entry

    def update_last_assistant(self, key, content: str) -> bool:
        history = self._store.get(key, [])
        if history and history[-1].get("role") == "assistant":
            history[-1]["content"] = content
            return True
        return False

    def remove_last_assistant_if_empty(self, key) -> bool:
        """Remove the last assistant entry if it's empty or just 'thinking...'"""
        history = self._store.get(key, [])
        if history and history[-1].get("role") == "assistant":
            content = history[-1].get("content", "")
            if not content or content == THINKING_PLACEHOLDER:
                history.pop()
                return True
        return False

    def remove_last_user(self, key) -> bool:
        """Remove the last user entry from history"""
        history = self._store.get(key, [])
        if history and history[-1].get("role") == "user":
            history.pop()
            return True
        return False

    def compute_display_for_history_entry(self, entry: dict) -> str:
        if not entry:
            return ""
        if entry.get("display"):
            return entry["display"]

        user_text = entry.get("user_text")
        attachments = entry.get("attachments") or []

        if user_text:
            attachments_display = format_attachments_for_display(attachments, self._size_formatter)
            return f"{user_text}\n\n{attachments_display}" if attachments_display else user_text

        return entry.get("content", "")


class ChatSession:
    def __init__(self, history_store: dict, size_formatter: Callable[[int], str], instance_id: int):
        self._instance_id = instance_id
        self.history = ChatHistoryManager(history_store, size_formatter)
        self.stream = StreamState()

    def history_key(self, provider: str | None, model: str | None):
        return (self._instance_id, provider, model)

    def get_history(self, provider: str | None, model: str | None) -> list[dict]:
        return self.history.get(self.history_key(provider, model))

    def save_history(self, provider: str | None, model: str | None):
        if provider and model is not None:
            key = self.history_key(provider, model)
            self.history.set(key, list(self.history.get(key)))

    def clear_history(self, provider: str | None, model: str | None):
        self.history.clear(self.history_key(provider, model))

    def add_to_history(
        self,
        provider: str | None,
        model: str | None,
        role: str,
        content: str,
        user_text: str | None = None,
        attachments: list[dict] | None = None,
    ):
        key = self.history_key(provider, model)
        return self.history.add_entry(key, role, content, user_text=user_text, attachments=attachments)

    def start_streaming(self, msg_label: QTextBrowser | None):
        self.stream.in_progress = True
        self.stream.msg_label = msg_label
        self.stream.partial_text = ""

    def stop_streaming(self):
        self.stream.in_progress = False

    def set_partial_text(self, text: str):
        self.stream.partial_text = text

    def get_last_message_role(self, chat_layout):
        row_widget = self._get_last_row_widget(chat_layout)
        if not row_widget:
            return None, None

        msg_label = self._find_label_in_row(row_widget, "assistant-message")
        if msg_label is not None:
            return "assistant", msg_label

        user_label = self._find_label_in_row(row_widget, "user-message")
        if user_label is not None:
            return "user", None

        return None, None

    def find_last_assistant_label(self, chat_layout) -> QTextBrowser | None:
        row_widget = self._get_last_row_widget(chat_layout)
        if not row_widget:
            return None
        return self._find_label_in_row(row_widget, "assistant-message")

    @staticmethod
    def _find_label_in_row(row_widget: QWidget, class_name: str) -> QTextBrowser | None:
        if not row_widget:
            return None
        layout = row_widget.layout()
        if not layout:
            return None
        for i in range(layout.count()):
            child = layout.itemAt(i).widget()
            if child and child.property("class") == class_name:
                child_layout = child.layout()
                if child_layout:
                    for j in range(child_layout.count()):
                        inner = child_layout.itemAt(j).widget()
                        if isinstance(inner, QTextBrowser):
                            return inner
        return None

    @staticmethod
    def _get_last_row_widget(chat_layout) -> QWidget | None:
        if chat_layout is None:
            return None
        last_idx = chat_layout.count() - 2
        if last_idx < 0:
            return None
        item = chat_layout.itemAt(last_idx)
        if not item:
            return None
        widget = item.widget()
        if widget and isinstance(widget, QWidget):
            return widget
        return None
