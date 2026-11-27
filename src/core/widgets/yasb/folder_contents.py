import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from core.utils.utilities import PopupWidget
from core.validation.widgets.yasb.folder_contents import FolderContentsConfig
from core.widgets.base import BaseWidget


class FolderContentsWidget(BaseWidget):
    validation_schema = FolderContentsConfig
    event_listener = None

    def __init__(self, config: FolderContentsConfig):
        super().__init__(class_name="folder-contents-widget")
        self.config = config
        self._init_container()

        # Folder Path
        self.folder = Path(self.config.path)

        # File Count
        # self.count = len(list(self.folder.iterdir()))

        # Widget Label
        self.build_widget_label(self.config.label, None)

        # Popup Logic
        self.register_callback("show_menu", self.show_menu)
        self.callback_left = "show_menu"

    def show_menu(self):
        self._menu = PopupWidget(self)  # default blur, corners, and border
        self._menu.setProperty("class", "folder-popup")

        layout = QVBoxLayout(self._menu)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Inverse Sort File List
        files = sorted(self.folder.iterdir(), key=lambda f: f.name.lower(), reverse=True)

        # Load Files
        for item in files:
            layout.addWidget(FileLabel(item))

        # Margin, Size, Position
        layout.setContentsMargins(8, 8, 8, 8)
        self._menu.adjustSize()
        self._menu.setPosition(  # hard coded alignment and direction
            alignment="left",
            direction="down",
            # default offset
        )

        self._menu.show()


class FileLabel(QLabel):
    def __init__(self, filepath: Path):
        super().__init__(filepath.name)
        self.filepath = filepath
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if ev and ev.button() == Qt.MouseButton.LeftButton:
            os.startfile(self.filepath)
