import logging

from humanize import naturalsize

from core.utils.widgets.ai_chat.message_composer import compose_user_message


class InputController:
    def __init__(self, owner):
        self._owner = owner

    def update_send_button_state(self):
        if not self._owner._is_popup_valid():
            return

        try:
            has_provider_and_model = bool(
                self._owner._provider and self._owner._model and not self._owner._model.startswith("No models")
            )
            has_input_text = bool(self._owner.input_edit.toPlainText().strip())
            has_attachments = bool(getattr(self._owner, "_attachments", []))
            has_processing = any(att.get("processing") for att in self._owner._attachments)
            is_enabled = has_provider_and_model and (has_input_text or has_attachments) and not has_processing
            self._owner.send_btn.setEnabled(is_enabled)

            if hasattr(self._owner, "attach_btn"):
                self._owner.attach_btn.setEnabled(
                    has_provider_and_model
                    and self._owner._attachment_manager.attachments_supported()
                    and not has_processing
                )
        except RuntimeError:
            pass

    def on_send_clicked(self):
        user_text = self._owner.input_edit.toPlainText().strip()
        has_attachments = bool(self._owner._attachments)
        has_processing = any(att.get("processing") for att in self._owner._attachments)
        if (
            (not user_text and not has_attachments)
            or not self._owner._provider
            or not self._owner._model
            or self._owner._model.startswith("No models")
            or has_processing
        ):
            return

        payload_text, ui_text = compose_user_message(
            user_text,
            self._owner._attachments,
            lambda size_bytes: naturalsize(size_bytes, binary=True, format="%.1f"),
        )

        attachments_copy = [dict(att) for att in self._owner._attachments]

        self._owner.input_edit.clear()
        self._owner._attachments = []
        self._owner._attachment_manager.refresh_attachments_ui()
        self._owner._append_message("user", ui_text)
        self._owner._chat_session.add_to_history(
            self._owner._provider,
            self._owner._model_index,
            "user",
            payload_text,
            user_text=user_text,
            attachments=attachments_copy,
        )
        self._owner._stream_ui.set_ui_state(streaming=True)
        self._owner.stop_btn.setEnabled(True)
        self._owner._stop_event = False
        self._owner._stream_worker_manager.send_to_api()

    def on_stop_clicked(self):
        self._owner._stop_event = True

        # Stop the throttle timer to prevent any more UI updates
        self._owner._stream_worker_manager.stop_and_reset_stream()

        if hasattr(self._owner, "_worker") and hasattr(self._owner._worker, "client") and self._owner._worker.client:
            try:
                self._owner._worker.client.stop()
            except Exception:
                logging.error("Failed to stop the AI chat client gracefully.")
                pass

        partial_text = self._owner._chat_session.stream.partial_text
        if partial_text:
            stopped_text = partial_text
            stopped_display = partial_text
        else:
            stopped_text = "You stopped this response"
            stopped_display = f"*{stopped_text}*"
        self._owner._stream_ui.stop_thinking_animation()
        self._owner._chat_session.stream.msg_label = None
        history = self._owner._chat_session.get_history(self._owner._provider, self._owner._model_index)
        if not partial_text:
            for entry in reversed(history):
                if entry.get("role") == "user" and not entry.get("stopped"):
                    entry["stopped"] = True
                    break
        if not history or history[-1]["role"] != "assistant":
            entry = self._owner._chat_session.add_to_history(
                self._owner._provider,
                self._owner._model_index,
                "assistant",
                stopped_text,
            )
            entry["display"] = stopped_display
            if not partial_text:
                entry["stopped"] = True
        else:
            history[-1]["content"] = stopped_text
            history[-1]["display"] = stopped_display
            if not partial_text:
                history[-1]["stopped"] = True

        msg_label = self._owner._chat_session.stream.msg_label
        if msg_label is None:
            msg_label = self._owner._chat_session.find_last_assistant_label(self._owner.chat_layout)
        if msg_label is not None:
            try:
                msg_label.setText(stopped_display)
            except RuntimeError:
                pass

        self._owner._stream_ui.set_ui_state(streaming=False)
        self._owner._chat_session.stream.in_progress = False

    def on_popup_destroyed(self, *args):
        if hasattr(self._owner, "input_edit"):
            self._owner._input_draft = self._owner.input_edit.toPlainText()
        else:
            self._owner._input_draft = ""
        if hasattr(self._owner, "_loading_label"):
            del self._owner._loading_label
        self._owner._popup_chat = None
        self._owner._stream_ui.stop_thinking_animation()
        self._owner._focus_manager.restore_previous_focus()
        self._owner._chat_render.clear_batch_state()
