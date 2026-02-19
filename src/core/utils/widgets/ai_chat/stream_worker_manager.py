import logging
import os

from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal

from core.utils.widgets.ai_chat.constants import FLUSH_INTERVAL_MS, SCROLL_DELAY_MS, THINKING_PLACEHOLDER
from core.utils.widgets.ai_chat.copilot_client import CopilotAiChatClient
from core.utils.widgets.ai_chat.message_composer import build_api_messages
from core.utils.widgets.ai_chat.openai_client import AiChatClient


class StreamWorkerManager:
    def __init__(self, owner):
        self._owner = owner
        self._pending_text = ""
        self._flush_timer = None
        self._copilot_clients: dict[str, CopilotAiChatClient] = {}  # provider_name -> client

    def stop_and_reset_stream(self):
        """Stop throttled UI updates and clear any pending text."""
        self._stop_flush_timer()
        self._pending_text = ""

    def _start_flush_timer(self):
        """Start the throttle timer for batched UI updates."""
        if self._flush_timer is None:
            self._flush_timer = QTimer(self._owner)
            self._flush_timer.timeout.connect(self._flush_pending_text)
        if not self._flush_timer.isActive():
            self._flush_timer.start(FLUSH_INTERVAL_MS)

    def _stop_flush_timer(self):
        """Stop the throttle timer."""
        if self._flush_timer is not None:
            self._flush_timer.stop()

    def _flush_pending_text(self):
        """Flush buffered text to UI."""
        if not self._pending_text:
            return
        if not self._owner._chat_session.stream.in_progress:
            self._stop_flush_timer()
            return

        msg_label = self._owner._chat_session.stream.msg_label
        if msg_label is None:
            return

        try:
            if hasattr(msg_label, "set_streaming_text"):
                msg_label.set_streaming_text(self._pending_text)
            else:
                msg_label.setText(self._pending_text)
        except RuntimeError:
            pass

    def send_to_api(self):
        msg_label = None
        instructions = None
        max_tokens = 0
        temperature = 0.7
        top_p = 0.95

        self.cleanup_previous_worker()

        self._owner._append_message("assistant", THINKING_PLACEHOLDER)
        msg_label = self._owner._chat_session.find_last_assistant_label(self._owner.chat_layout)
        if not self._owner._is_popup_valid() or msg_label is None:
            return
        self._owner._stream_ui.start_thinking_animation(msg_label)
        self._owner.chat_widget.layout().activate()
        QTimer.singleShot(SCROLL_DELAY_MS, self._owner._chat_render.scroll_to_bottom)

        self._owner.provider_btn.setEnabled(False)
        self._owner.model_btn.setEnabled(False)
        if hasattr(self._owner, "attach_btn"):
            self._owner.attach_btn.setEnabled(False)
        if hasattr(self._owner, "clear_btn"):
            self._owner.clear_btn.setEnabled(False)

        model_config = self._owner._get_model_config()
        if model_config:
            instructions = model_config.get("instructions")
            max_tokens = model_config.get("max_tokens", max_tokens)
            temperature = model_config.get("temperature", temperature)
            top_p = model_config.get("top_p", top_p)

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

        chat_history = [
            msg
            for msg in self._owner._chat_session.get_history(self._owner._provider, self._owner._model_index)
            if not msg.get("stopped")
        ]
        provider_type = (self._owner._provider_config.get("provider_type") or "openai").lower()
        if instructions:
            if chat_history and chat_history[0].get("role") == "system":
                if chat_history[0].get("content") != instructions:
                    chat_history[0] = {"role": "system", "content": instructions}
            else:
                chat_history = [{"role": "system", "content": instructions}] + chat_history

        api_messages = build_api_messages(chat_history, provider_type)

        self._owner._chat_session.start_streaming(msg_label)

        copilot_client = None
        if provider_type == "copilot":
            copilot_client = self._get_copilot_client(self._owner._provider)

        self._owner._thread = QThread()
        self._owner._worker = _StreamWorker(
            self._owner._provider_config,
            self._owner._model,
            api_messages,
            lambda: getattr(self._owner, "_stop_event", False),
            max_tokens,
            temperature,
            top_p,
            copilot_client=copilot_client,
        )
        self._owner._worker.moveToThread(self._owner._thread)
        self._owner._worker.chunk_signal.connect(self.streaming_chunk_handler, Qt.ConnectionType.QueuedConnection)
        self._owner._worker.done_signal.connect(self.streaming_done_handler, Qt.ConnectionType.QueuedConnection)
        self._owner._worker.error_signal.connect(self.streaming_error_handler, Qt.ConnectionType.QueuedConnection)
        self._owner._worker.finished_signal.connect(self._owner._thread.quit, Qt.ConnectionType.QueuedConnection)
        self._owner._thread.started.connect(self._owner._worker.run)
        self._owner._thread.finished.connect(self._owner._thread.deleteLater)
        self._owner._thread.start()

    def streaming_chunk_handler(self, text):
        if not self._owner._chat_session.stream.in_progress:
            return

        msg_label = self._owner._chat_session.stream.msg_label
        if not msg_label:
            return

        self._owner._chat_session.set_partial_text(text)
        self._owner._stream_ui.stop_thinking_animation()
        if self._owner._is_popup_valid():
            try:
                self._owner.stop_btn.setEnabled(True)
            except RuntimeError:
                pass

        # Buffer text and use throttled updates to reduce UI lag
        self._pending_text = text
        self._start_flush_timer()

    def streaming_done_handler(self, text):
        # Stop throttle timer and flush final text
        self._stop_flush_timer()
        self._pending_text = ""

        self._owner._chat_session.stream.in_progress = False
        msg_label = self._owner._chat_session.stream.msg_label
        self._owner._stream_ui.stop_thinking_animation()

        key = self._owner._chat_session.history_key(self._owner._provider, self._owner._model_index)
        if getattr(self._owner, "_stop_event", False):
            if hasattr(self._owner, "_thread") and self._owner._thread:
                QTimer.singleShot(SCROLL_DELAY_MS, self.clear_thread_reference)
            return

        # Store response in history
        if not self._owner._chat_session.history.update_last_assistant(key, text):
            self._owner._chat_session.add_to_history(
                self._owner._provider,
                self._owner._model_index,
                "assistant",
                text,
            )

        if self._owner._is_popup_valid() and msg_label is not None:
            try:
                msg_label.setText(text)
                # Show copy button after streaming completes
                if hasattr(msg_label, "copy_row") and msg_label.copy_row is not None:
                    msg_label.copy_row.setVisible(True)
                self._owner._stream_ui.set_ui_state(streaming=False)
            except RuntimeError:
                pass
        else:
            self._owner._new_notification = True
            self._owner._update_label()

        if hasattr(self._owner, "_thread") and self._owner._thread:
            QTimer.singleShot(SCROLL_DELAY_MS, self.clear_thread_reference)

    def streaming_error_handler(self, err):
        # Stop throttle timer on error
        self._stop_flush_timer()
        self._pending_text = ""

        self._owner._chat_session.stream.in_progress = False
        msg_label = self._owner._chat_session.stream.msg_label
        self._owner._stream_ui.stop_thinking_animation()

        if getattr(self._owner, "_stop_event", False):
            if hasattr(self._owner, "_thread") and self._owner._thread:
                QTimer.singleShot(SCROLL_DELAY_MS, self.clear_thread_reference)
            return

        # We do not want to store error messages in history - they're transient API failures
        key = self._owner._chat_session.history_key(self._owner._provider, self._owner._model_index)
        self._owner._chat_session.history.remove_last_assistant_if_empty(key)
        self._owner._chat_session.history.remove_last_user(key)

        if self._owner._is_popup_valid() and msg_label is not None:
            try:
                self._owner._chat_render.remove_last_message()
                self._owner._append_error_message(str(err))
                self._owner._stream_ui.set_ui_state(streaming=False)
            except RuntimeError:
                pass

        if hasattr(self._owner, "_thread") and self._owner._thread:
            QTimer.singleShot(SCROLL_DELAY_MS, self.clear_thread_reference)

    def cleanup_previous_worker(self):
        # Clean up throttle timer
        self._stop_flush_timer()
        self._pending_text = ""

        if hasattr(self._owner, "_worker") and self._owner._worker:
            try:
                self._owner._worker.chunk_signal.disconnect()
                self._owner._worker.done_signal.disconnect()
                self._owner._worker.error_signal.disconnect()
                self._owner._worker.finished_signal.disconnect()
            except Exception:
                pass
            self._owner._worker = None

        # Just clear our reference, the thread will clean itself up via deleteLater
        if hasattr(self._owner, "_thread"):
            self._owner._thread = None

    def clear_thread_reference(self):
        if hasattr(self._owner, "_thread") and self._owner._thread:
            try:
                if self._owner._thread.isFinished():
                    self._owner._thread = None
                else:
                    QTimer.singleShot(SCROLL_DELAY_MS, self.clear_thread_reference)
            except RuntimeError, AttributeError:
                self._owner._thread = None

    def reset_copilot_session(self, provider: str | None, model: str | None):
        """Close the Copilot client for the given provider so a fresh one is created."""
        if not provider:
            return
        client = self._copilot_clients.pop(provider, None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def close_all_copilot_clients(self):
        """Close all cached Copilot clients and their CLI processes."""
        for client in self._copilot_clients.values():
            try:
                client.close()
            except Exception:
                pass
        self._copilot_clients.clear()

    def _get_copilot_client(self, provider: str | None):
        """Get or create a shared CopilotAiChatClient for the given provider."""
        key = provider or "_default"
        client = self._copilot_clients.get(key)
        if client is None:
            client = CopilotAiChatClient(self._owner._provider_config)
            self._copilot_clients[key] = client
        return client


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
        copilot_client: CopilotAiChatClient | None = None,
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
        self._copilot_client = copilot_client

    def run(self):
        try:
            provider_type = (self.provider_config.get("provider_type") or "openai").lower()
            if provider_type == "copilot":
                self.client = self._copilot_client or CopilotAiChatClient(self.provider_config)
            else:
                self.client = AiChatClient(self.provider_config, self.model, self.max_tokens)
            full_text = ""
            if provider_type == "copilot":
                chunk_iter = self.client.chat(self.chat_history, model_name=self.model)
            else:
                chunk_iter = self.client.chat(self.chat_history, temperature=self.temperature, top_p=self.top_p)
            for chunk in chunk_iter:
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
