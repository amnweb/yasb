import functools
import logging
import re

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal

from core.utils.widgets.ai_chat.copilot_client import list_copilot_models


def _strip_multiplier(label: str) -> str:
    """Remove multiplier suffix from label for button display."""
    return re.sub(r"\s*\(?(\d+\.?\d*x)\)?$", "", label)


def _split_label_and_multiplier(label: str) -> tuple[str, str | None]:
    """Split label into base label and multiplier suffix."""
    match = re.search(r"\s*(\(?\d+\.?\d*x\)?)$", label)
    if match:
        return label[: match.start()].rstrip(), match.group(1).strip("()")
    return label, None


def _format_multiplier_value(multiplier) -> str:
    if multiplier is None:
        return ""
    if isinstance(multiplier, (int, float)):
        if multiplier == int(multiplier):
            return f"{int(multiplier)}x"
    return f"{multiplier}x"


class _ModelListWorker(QObject):
    success_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, provider_config: dict | None):
        super().__init__()
        self._provider_config = provider_config

    def run(self):
        try:
            models = list_copilot_models(self._provider_config)
            self.success_signal.emit(models)
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            self.finished_signal.emit()


class ProviderModelManager:
    def __init__(self, owner):
        self._owner = owner

    def _apply_model_selection(self, model_index: int, model_cfg: dict):
        self._owner._model_index = model_index
        self._owner._model = model_cfg.get("name")

    def initialize_provider_and_model(self):
        """Initialize provider and model by finding the model with default: true flag.

        Validates that only one model has the default flag set.
        """
        default_models = []

        # Find all models with default flag set to true
        for provider_cfg in self._owner._providers:
            for model_index, model_cfg in enumerate(provider_cfg.get("models", [])):
                if model_cfg.get("default", False):
                    default_models.append((provider_cfg["provider"], model_index))

        # Logs warning if more than one model has default flag set
        if len(default_models) > 1:
            logging.warning(
                f"Multiple models have default flag set: {default_models}. Using first model: {default_models[0]}"
            )

        # Set the default provider and model if found
        if default_models:
            self._owner._provider = default_models[0][0]
            self._owner._model_index = default_models[0][1]

        # Set provider config
        if self._owner._provider:
            self._owner._provider_config = next(
                (p for p in self._owner._providers if p["provider"] == self._owner._provider), None
            )
            if (
                self._owner._provider_config
                and self._owner._provider_config.get("models")
                and self._owner._model_index is not None
                and 0 <= self._owner._model_index < len(self._owner._provider_config["models"])
            ):
                model_cfg = self._owner._provider_config["models"][self._owner._model_index]
                self._apply_model_selection(self._owner._model_index, model_cfg)

    def populate_provider_menu(self):
        self._owner.provider_menu.clear()
        for provider_cfg in self._owner._providers:
            provider_name = provider_cfg["provider"]
            action = self._owner.provider_menu.addAction(provider_name)
            action.setCheckable(True)
            if provider_name == self._owner._provider:
                action.setChecked(True)

            action.triggered.connect(functools.partial(self.on_provider_changed, provider_name))

    def ensure_copilot_models(self):
        if not self._owner._provider_config:
            return
        provider_type = (self._owner._provider_config.get("provider_type") or "openai").lower()
        if provider_type != "copilot" or self._owner._provider_config.get("models"):
            try:
                self._owner._set_header_loader(False)
            except Exception:
                pass
            return
        if getattr(self._owner, "_copilot_models_loading", False):
            return

        self._owner._copilot_models_loading = True
        try:
            self._owner._set_header_loader(True)
        except Exception:
            pass
        self._owner.model_btn.setEnabled(False)
        self._owner.model_btn.setText("Loading models...")
        self.start_copilot_model_fetch()

    def populate_model_menu(self):
        try:
            self._owner.model_menu.clear()
        except RuntimeError:
            return
        self.ensure_copilot_models()
        if (
            not hasattr(self._owner, "_provider_config")
            or not self._owner._provider_config
            or not self._owner._provider_config.get("models")
        ):
            try:
                self._owner.model_btn.setEnabled(False)
            except RuntimeError:
                return
            return

        added_separator = False
        for model_index, model_cfg in enumerate(self._owner._provider_config["models"]):
            # Add separator after free models
            if (
                not added_separator
                and model_cfg.get("multiplier") not in (0, None)
                and model_cfg.get("is_premium") is not False
            ):
                self._owner.model_menu.addSeparator()
                added_separator = True

            model_name = model_cfg["name"]
            model_label = model_cfg.get("label", model_name)
            base_label, parsed_multiplier = _split_label_and_multiplier(model_label)
            multiplier_label = _format_multiplier_value(model_cfg.get("multiplier")) or parsed_multiplier
            # Tab character makes QMenu render multiplier right-aligned (like shortcuts)
            # Since I can't find a better way to right-align text in QMenu, this is a decent workaround
            display_label = f"{base_label}\t{multiplier_label}" if multiplier_label else base_label
            action = self._owner.model_menu.addAction(display_label)
            action.setCheckable(True)
            action.setChecked(model_index == self._owner._model_index)
            action.setData(model_index)
            action.triggered.connect(lambda checked, idx=model_index: self.on_model_changed_by_index(idx))
        try:
            self._owner.model_btn.setEnabled(True)
            selected_index = None
            if self._owner._model_index is not None and 0 <= self._owner._model_index < len(
                self._owner._provider_config["models"]
            ):
                selected_index = self._owner._model_index
            elif self._owner._model is not None:
                for idx, model_cfg in enumerate(self._owner._provider_config["models"]):
                    if model_cfg.get("name") == self._owner._model:
                        selected_index = idx
                        break
            if selected_index is None:
                selected_index = 0

            selected_model = self._owner._provider_config["models"][selected_index]
            self._apply_model_selection(selected_index, selected_model)
            self._owner.model_btn.setText(_strip_multiplier(selected_model.get("label", self._owner._model)))
        except RuntimeError:
            return

    def start_copilot_model_fetch(self):
        self._owner._copilot_models_provider = self._owner._provider
        thread = QThread()
        worker = _ModelListWorker(self._owner._provider_config)
        worker.moveToThread(thread)

        worker.success_signal.connect(self.on_copilot_models_fetched, Qt.ConnectionType.QueuedConnection)
        worker.error_signal.connect(self.on_copilot_models_error, Qt.ConnectionType.QueuedConnection)
        worker.finished_signal.connect(
            lambda: self.cleanup_finished_model_worker(thread, worker), Qt.ConnectionType.QueuedConnection
        )
        worker.finished_signal.connect(thread.quit, Qt.ConnectionType.QueuedConnection)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)

        self._owner._model_list_workers.append((thread, worker))
        thread.start()

    def cleanup_finished_model_worker(self, thread: QThread, worker: QObject):
        self._owner._model_list_workers = [
            (t, w) for (t, w) in self._owner._model_list_workers if t is not thread and w is not worker
        ]

    def on_copilot_models_fetched(self, models: list[dict[str, str]]):
        self._owner._copilot_models_loading = False
        if getattr(self._owner, "_copilot_models_provider", None) != self._owner._provider:
            try:
                self._owner._set_header_loader(False)
            except Exception:
                pass
            return
        try:
            self._owner._set_header_loader(False)
        except Exception:
            pass
        if not self._owner._provider_config:
            return
        if not models:
            try:
                self._owner.model_btn.setEnabled(False)
                self._owner.model_btn.setText("No models (offline)")
            except RuntimeError:
                return
            return
        self._owner._provider_config["models"] = models
        self.populate_model_menu()
        try:
            self._owner._input_controller.update_send_button_state()
        except RuntimeError:
            return

    def on_copilot_models_error(self, error_message: str):
        self._owner._copilot_models_loading = False
        if getattr(self._owner, "_copilot_models_provider", None) != self._owner._provider:
            try:
                self._owner._set_header_loader(False)
            except Exception:
                pass
            return
        try:
            self._owner._set_header_loader(False)
        except Exception:
            pass
        logging.error(f"Failed to list Copilot models: {error_message}")
        try:
            self._owner.model_btn.setEnabled(False)
            self._owner.model_btn.setText("No models (offline)")
        except RuntimeError:
            return

    def on_provider_changed(self, provider_name):
        self._owner._chat_session.save_history(self._owner._provider, self._owner._model_index)
        if provider_name != self._owner._provider:
            self._owner._provider = provider_name
            self._owner.provider_btn.setText(provider_name)
            self._owner._provider_config = next(
                (p for p in self._owner._providers if p["provider"] == provider_name), None
            )
            try:
                self._owner._set_header_loader(False)
            except Exception:
                pass
            self.populate_model_menu()
            self._owner._chat_render.render_chat_history()
            self._owner._attachment_manager.prune_attachments_for_model()
            self._owner._attachment_manager.refresh_attachments_ui()
            self._owner._input_controller.update_send_button_state()

        for action in self._owner.provider_menu.actions():
            action.setChecked(action.text() == provider_name)

    def on_model_changed_by_index(self, model_index: int):
        self._owner._chat_session.save_history(self._owner._provider, self._owner._model_index)
        if not hasattr(self._owner, "_provider_config") or not self._owner._provider_config:
            return
        if model_index < 0 or model_index >= len(self._owner._provider_config["models"]):
            return

        model_cfg = self._owner._provider_config["models"][model_index]
        self._apply_model_selection(model_index, model_cfg)
        self._owner.model_btn.setText(_strip_multiplier(model_cfg.get("label", self._owner._model)))
        self._owner._chat_render.render_chat_history()
        self._owner._attachment_manager.prune_attachments_for_model()
        self._owner._attachment_manager.refresh_attachments_ui()
        self._owner._input_controller.update_send_button_state()

        for action in self._owner.model_menu.actions():
            action.setChecked(action.data() == model_index)
