import logging

from PyQt6.QtCore import (
    Qt,
    pyqtSlot,  # type: ignore
)
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QHBoxLayout, QPushButton

from core.utils.utilities import add_shadow
from core.utils.widgets.glazewm.client import GlazewmClient, TilingDirection
from core.validation.widgets.glazewm.tiling_direction import GlazewmTilingDirectionConfig
from core.widgets.base import BaseWidget
from settings import DEBUG

logger = logging.getLogger("glazewm_tiling_direction")

if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.CRITICAL)


class GlazewmTilingDirectionWidget(BaseWidget):
    validation_schema = GlazewmTilingDirectionConfig

    def __init__(self, config: GlazewmTilingDirectionConfig):
        super().__init__(class_name="glazewm-tiling-direction")
        self.horizontal_label = config.horizontal_label
        self.vertical_label = config.vertical_label
        self.container_shadow = config.container_shadow.model_dump()
        self.btn_shadow = config.btn_shadow.model_dump()
        self.current_tiling_direction = TilingDirection.HORIZONTAL

        self.workspace_container_layout = QHBoxLayout()
        self.workspace_container_layout.setSpacing(0)
        self.workspace_container_layout.setContentsMargins(0, 0, 0, 0)

        self.tiling_direction_button = QPushButton()
        self.tiling_direction_button.setProperty("class", "btn")
        self.tiling_direction_button.setVisible(False)
        self.tiling_direction_button.setLayout(self.workspace_container_layout)
        self.tiling_direction_button.clicked.connect(self.toggle_tiling_direction)  # type: ignore

        add_shadow(self._widget_frame, self.container_shadow)
        add_shadow(self.tiling_direction_button, self.btn_shadow)

        self.widget_layout.addWidget(self.tiling_direction_button)

        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.glazewm_client = GlazewmClient(
            config.glazewm_server_uri,
            [
                "sub -e focus_changed tiling_direction_changed focused_container_moved",
                "query tiling-direction",
            ],
        )
        self.glazewm_client.glazewm_connection_status.connect(self._update_connection_status)  # type: ignore
        self.glazewm_client.tiling_direction_processed.connect(self._update_tiling_direction)  # type: ignore
        self.glazewm_client.connect()

    @pyqtSlot()
    def toggle_tiling_direction(self):
        self.glazewm_client.toggle_tiling_direction()

    @pyqtSlot(bool)
    def _update_connection_status(self, status: bool):
        self.tiling_direction_button.setVisible(status)

    @pyqtSlot(TilingDirection)
    def _update_tiling_direction(self, direction: TilingDirection):
        self.current_tiling_direction = direction
        if direction == TilingDirection.HORIZONTAL:
            self.tiling_direction_button.setText(self.horizontal_label or direction)
        elif direction == TilingDirection.VERTICAL:
            self.tiling_direction_button.setText(self.vertical_label or direction)
