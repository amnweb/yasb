from PyQt6.QtCore import QTimer

from core.utils.widgets.ai_chat.constants import THINKING_ANIMATION_INTERVAL_MS, THINKING_PLACEHOLDER


class StreamUiController:
    def __init__(self, owner):
        self._owner = owner
        self._thinking_timer = None
        self._thinking_step = 0
        self._thinking_label = None

    def set_ui_state(self, streaming=False):
        if not self._owner._is_popup_valid():
            return

        try:
            self._owner.send_btn.setVisible(not streaming)
            self._owner.stop_btn.setVisible(streaming)
            if streaming:
                self._owner.stop_btn.setEnabled(True)
            if hasattr(self._owner, "header_loader_line"):
                if streaming:
                    self._owner.header_loader_line.start()
                else:
                    self._owner.header_loader_line.stop()
            if not streaming:
                self._owner.stop_btn.setEnabled(False)
                self._owner._input_controller.update_send_button_state()
            self._owner.input_edit.set_streaming(streaming)
            self._owner.provider_btn.setEnabled(not streaming)
            self._owner.model_btn.setEnabled(not streaming)
            if hasattr(self._owner, "attach_btn"):
                self._owner.attach_btn.setEnabled(not streaming)
            if hasattr(self._owner, "clear_btn"):
                self._owner.clear_btn.setEnabled(not streaming)
        except RuntimeError:
            pass

    def start_thinking_animation(self, msg_label):
        self._thinking_label = msg_label
        self._thinking_step = 0
        if self._thinking_timer is not None:
            self._thinking_timer.stop()
            self._thinking_timer.deleteLater()
        self._thinking_timer = QTimer(self._owner)
        self._thinking_timer.timeout.connect(self._update_thinking_animation)
        self._thinking_timer.start(THINKING_ANIMATION_INTERVAL_MS)
        self._update_thinking_animation()

    def _update_thinking_animation(self):
        if self._thinking_label is None:
            return
        dots = "." * (self._thinking_step % 4)
        self._thinking_label.setText(f"thinking {dots}")
        self._thinking_step += 1

    def stop_thinking_animation(self):
        if self._thinking_timer is not None:
            self._thinking_timer.stop()
            self._thinking_timer.deleteLater()
            self._thinking_timer = None
        self._thinking_label = None
        self._thinking_step = 0

    def reconnect_streaming_if_needed(self):
        if not self._owner._chat_session.stream.in_progress:
            return

        self.set_ui_state(streaming=True)

        self._owner.provider_btn.setEnabled(False)
        self._owner.model_btn.setEnabled(False)

        self._owner.stop_btn.setEnabled(True)

        last_role, msg_label = self._owner._chat_session.get_last_message_role(self._owner.chat_layout)
        partial = self._owner._chat_session.stream.partial_text
        if not partial:
            partial = THINKING_PLACEHOLDER
        if last_role == "user":
            self._owner._append_message("assistant", partial)
            msg_label = self._owner._chat_session.find_last_assistant_label(self._owner.chat_layout)
        elif last_role == "assistant" and msg_label is not None:
            try:
                msg_label.setText(partial)
            except RuntimeError:
                pass

        if msg_label is not None:
            self._owner._chat_session.stream.msg_label = msg_label
            if hasattr(self._owner, "_worker"):
                try:
                    self._owner._worker.chunk_signal.disconnect(
                        self._owner._stream_worker_manager.streaming_chunk_handler
                    )
                except Exception:
                    pass
                self._owner._worker.chunk_signal.connect(self._owner._stream_worker_manager.streaming_chunk_handler)
            if not self._owner._chat_session.stream.partial_text:
                self.start_thinking_animation(msg_label)
