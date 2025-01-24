import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QHBoxLayout, QPushButton

from core.utils.glazewm.client import GlazewmClient, TilingDirection
from core.validation.widgets.glazewm.tiling_direction import VALIDATION_SCHEMA
from core.widgets.base import BaseWidget
from settings import DEBUG

logger = logging.getLogger("glazewm_workspaces")

if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.CRITICAL)


class GlazewmTilingDirectionWidget(BaseWidget):
    validation_schema = VALIDATION_SCHEMA

    def __init__(
        self,
        horizontal_label: str,
        vertical_label: str,
        glazewm_server_uri: str,
    ):
        super().__init__(class_name="glazewm-tiling-direction")
        self.horizontal_label = horizontal_label
        self.vertical_label = vertical_label
        self.current_tiling_direction = TilingDirection.HORIZONTAL

        self.workspace_container_layout = QHBoxLayout()
        self.workspace_container_layout.setSpacing(0)
        self.workspace_container_layout.setContentsMargins(0, 0, 0, 0)

        self.tiling_direction_button = QPushButton()
        self.tiling_direction_button.setProperty("class", "btn")
        self.tiling_direction_button.setVisible(False)
        self.tiling_direction_button.setLayout(self.workspace_container_layout)

        self.widget_layout.addWidget(self.tiling_direction_button)

        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.tiling_direction_button.clicked.connect(self.toggle_tiling_direction)

        self.glazewm_client = GlazewmClient(
            glazewm_server_uri,
            [
                "sub -e focus_changed tiling_direction_changed",
                "query tiling-direction",
            ],
        )
        self.glazewm_client.glazewm_connection_status.connect(self._update_connection_status)
        self.glazewm_client.tiling_direction_processed.connect(self._update_tiling_direction)
        self.glazewm_client.connect()

    def toggle_tiling_direction(self):
        self.glazewm_client.toggle_tiling_direction()

    def _update_connection_status(self, status):
        self.tiling_direction_button.setVisible(status)

    def _update_tiling_direction(self, direction: TilingDirection):
        self.current_tiling_direction = direction
        if direction == TilingDirection.HORIZONTAL:
            self.tiling_direction_button.setText(self.horizontal_label or direction)
        elif direction == TilingDirection.VERTICAL:
            self.tiling_direction_button.setText(self.vertical_label or direction)
