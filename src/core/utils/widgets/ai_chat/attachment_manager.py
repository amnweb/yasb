import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from humanize import naturalsize
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton

from core.utils.alert_dialog import raise_info_alert
from core.utils.widgets.ai_chat.constants import BYTES_PER_KB, REMOVE_BUTTON_SIZE_PX
from core.utils.widgets.ai_chat.image_helper import is_image_extension, process_image, qimage_to_bytes


class ImageProcessWorker(QObject):
    success_signal = pyqtSignal(str, dict)
    error_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal()

    def __init__(self, image_bytes, name, path, placeholder_path, max_bytes):
        super().__init__()
        self.image_bytes = image_bytes
        self.name = name
        self.path = path
        self.placeholder_path = placeholder_path
        self.max_bytes = max_bytes

    def run(self):
        try:
            result = process_image(self.image_bytes, self.max_bytes)
            if result is None:
                self.error_signal.emit(
                    self.placeholder_path,
                    f"{self.name or 'Image'} could not be compressed enough to fit the size limit.",
                )
                return

            if self.name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                name = f"clipboard_image_{timestamp}.{result['ext']}"
            else:
                name_path = Path(self.name)
                name = f"{name_path.stem}.{result['ext']}"

            path = self.path if self.path is not None else name

            b64_data = base64.b64encode(result["bytes"]).decode("ascii")
            image_url = f"data:{result['mime_type']};base64,{b64_data}"
            compressed = result["compressed"] or result["scaled"]

            attachment = {
                "path": path,
                "name": name,
                "size": len(result["bytes"]),
                "is_image": True,
                "image_url": image_url,
                "prompt": f"[Image: {name}{' (compressed)' if compressed else ''}]",
                "compressed": compressed,
            }

            self.success_signal.emit(self.placeholder_path, attachment)
        except Exception as e:
            logging.exception(f"Failed to process image: {e}")
            self.error_signal.emit(self.placeholder_path, str(e))
        finally:
            self.finished_signal.emit()


class AttachmentManager:
    def __init__(self, owner):
        self._owner = owner
        self._image_process_workers: list[tuple[QThread, Any]] = []

    def add_attachments_via_dialog(self):
        """Open a file picker and stage selected files for the next message."""
        if not self._owner._is_popup_valid():
            return

        files: list[str] = []
        popup = self._owner._popup_chat
        try:
            popup.set_auto_close_enabled(False)
            popup.set_block_deactivate(True)

            files, _ = QFileDialog.getOpenFileNames(
                popup,
                "Select files",
                "",
                "All Files (*)",
            )
        finally:
            if popup and self._owner._is_popup_valid():
                popup.set_auto_close_enabled(True)
                popup.set_block_deactivate(False)

        if not files:
            return

        added_any = False
        for file_path in files:
            if self.add_attachment(file_path):
                added_any = True

        if added_any:
            self.refresh_attachments_ui()
            self._owner._input_controller.update_send_button_state()

    def get_max_image_bytes(self) -> int:
        model_config = self._owner._get_model_config()
        if model_config:
            return model_config.get("max_image_size", 0) * BYTES_PER_KB
        return 0

    def supports_vision(self) -> bool:
        model_config = self._owner._get_model_config()
        if model_config:
            return model_config.get("supports_vision", False) or model_config.get("max_image_size", 0) > 0
        return False

    def get_max_attachment_bytes(self) -> int:
        model_config = self._owner._get_model_config()
        if model_config:
            return model_config.get("max_attachment_size", 0) * BYTES_PER_KB
        return 0

    def attachments_supported(self) -> bool:
        return self.supports_vision() or self.get_max_attachment_bytes() > 0

    def prune_attachments_for_model(self) -> bool:
        if not hasattr(self._owner, "_attachments"):
            return False

        supports_images = self.supports_vision()
        max_attachment_bytes = self.get_max_attachment_bytes()

        pruned: list[dict[str, Any]] = []
        for att in getattr(self._owner, "_attachments", []):
            if att.get("is_image"):
                if supports_images:
                    pruned.append(att)
            else:
                if max_attachment_bytes > 0:
                    pruned.append(att)

        changed = len(pruned) != len(getattr(self._owner, "_attachments", []))
        self._owner._attachments = pruned
        return changed

    def create_image_attachment(
        self,
        image_bytes: bytes,
        name: str | None = None,
        path: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.supports_vision():
            QTimer.singleShot(
                0,
                lambda: raise_info_alert(
                    title="Images Not Supported",
                    msg="This model does not support image attachments.",
                    informative_msg="",
                    parent=None,
                ),
            )
            return None

        max_bytes = self.get_max_image_bytes()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        placeholder_path = f"_processing_{timestamp}"

        placeholder = {
            "path": placeholder_path,
            "name": "Processing file, please wait...",
            "size": 0,
            "is_image": True,
            "processing": True,
        }

        self._start_image_processing(image_bytes, name, path, placeholder_path, max_bytes)

        return placeholder

    def _start_image_processing(self, image_bytes, name, path, placeholder_path, max_bytes):
        thread = QThread()
        worker = ImageProcessWorker(image_bytes, name, path, placeholder_path, max_bytes)
        worker.moveToThread(thread)

        worker.success_signal.connect(self._on_image_processed, Qt.ConnectionType.QueuedConnection)
        worker.error_signal.connect(self._on_image_process_error, Qt.ConnectionType.QueuedConnection)
        worker.finished_signal.connect(
            lambda: self._cleanup_finished_image_worker(thread, worker), Qt.ConnectionType.QueuedConnection
        )
        worker.finished_signal.connect(thread.quit, Qt.ConnectionType.QueuedConnection)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)

        self._image_process_workers.append((thread, worker))
        thread.start()

    def _on_image_processed(self, placeholder_path: str, attachment: dict):
        for i, att in enumerate(self._owner._attachments):
            if att.get("path") == placeholder_path:
                self._owner._attachments[i] = attachment
                break

        if self._owner._is_popup_valid():
            self.refresh_attachments_ui()
            self._owner._input_controller.update_send_button_state()

    def _on_image_process_error(self, placeholder_path: str, error_message: str):
        self._owner._attachments = [att for att in self._owner._attachments if att.get("path") != placeholder_path]

        if self._owner._is_popup_valid():
            self.refresh_attachments_ui()
            self._owner._input_controller.update_send_button_state()

            QTimer.singleShot(
                0,
                lambda: raise_info_alert(
                    title="Image Processing Failed",
                    msg=error_message,
                    informative_msg="",
                    parent=None,
                ),
            )

    def handle_paste_mime(self, mime) -> bool:
        if not self._owner._is_popup_valid():
            return False

        added_any = False

        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    if self.add_attachment(url.toLocalFile()):
                        added_any = True
            if added_any:
                self.refresh_attachments_ui()
                self._owner._input_controller.update_send_button_state()
            return True

        if mime.hasImage():
            image_data = mime.imageData()
            if isinstance(image_data, QImage):
                attachment = self.process_paste_mime_image(image_data)
                if attachment:
                    self._owner._attachments.append(attachment)
                    added_any = True
            if added_any:
                self.refresh_attachments_ui()
                self._owner._input_controller.update_send_button_state()
            return True

        return False

    def process_paste_mime_image(self, qimage: QImage) -> dict[str, Any] | None:
        img_bytes = qimage_to_bytes(qimage, "PNG")
        if img_bytes is None:
            return None
        return self.create_image_attachment(img_bytes)

    def add_attachment(self, file_path: str) -> bool:
        try:
            path = Path(file_path)
        except TypeError:
            return False

        if not path.exists() or not path.is_file():
            return False

        if any(att.get("path") == str(path) for att in self._owner._attachments):
            return False

        attachment = self._read_attachment(path)
        if not attachment:
            return False

        self._owner._attachments.append(attachment)
        return True

    def _read_attachment(self, path: Path) -> dict[str, Any] | None:
        try:
            raw = path.read_bytes()
        except Exception as e:
            logging.error(f"Failed to read attachment {path}: {e}")
            return None

        size = len(raw)
        suffix = path.suffix.lower()

        if is_image_extension(suffix):
            return self.create_image_attachment(raw, name=path.name, path=str(path))

        max_attachment_bytes = self.get_max_attachment_bytes()
        truncated = False

        try:
            content_str = raw.decode("utf-8")
        except UnicodeDecodeError:
            QTimer.singleShot(
                0,
                lambda: raise_info_alert(
                    title="Unsupported File Type",
                    msg=f"{path.name} cannot be attached.",
                    informative_msg=(
                        "Only text files and images are supported.\nThis file appears to be binary and cannot be sent."
                    ),
                    parent=None,
                ),
            )
            return None

        if max_attachment_bytes > 0 and size > max_attachment_bytes:
            content_str = content_str[:max_attachment_bytes]
            truncated = True

        header = (
            f"[Attachment: {path.name} | size={naturalsize(size, binary=True, format='%.1f')}"
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

    def remove_attachment(self, path: str):
        self._owner._attachments = [att for att in self._owner._attachments if att.get("path") != path]
        self.refresh_attachments_ui()
        self._owner._input_controller.update_send_button_state()

    def refresh_attachments_ui(self):
        if not hasattr(self._owner, "attachments_layout"):
            return

        layout = self._owner.attachments_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        if not self._owner._attachments:
            return

        for attachment in self._owner._attachments:
            chip = QFrame()
            chip.setProperty("class", "attachment-chip")
            chip_layout = QHBoxLayout(chip)
            chip_layout.setContentsMargins(0, 0, 0, 0)
            chip_layout.setSpacing(0)

            name_label = QLabel(attachment["name"])
            name_label.setProperty("class", "attachment-label")
            chip_layout.addWidget(name_label)

            if not attachment.get("processing"):
                remove_btn = QPushButton("x")
                remove_btn.setProperty("class", "attachment-remove-button")
                remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                remove_btn.setFixedWidth(REMOVE_BUTTON_SIZE_PX)
                remove_btn.setFixedHeight(REMOVE_BUTTON_SIZE_PX)
                remove_btn.clicked.connect(lambda _=False, p=attachment["path"]: self.remove_attachment(p))
                chip_layout.addWidget(remove_btn)

            chip_layout.addStretch(1)
            layout.addWidget(chip)

    def _cleanup_finished_image_worker(self, thread, worker):
        try:
            self._image_process_workers.remove((thread, worker))
        except ValueError:
            pass
