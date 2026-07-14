"""Selection toolbar (copy / save / edit / cancel)."""

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QWidget

from core.ui.components.button import Button
from core.utils.tooltip import set_tooltip
from core.widgets.services.control_center.api.screenshot.constants import UI
from core.widgets.services.control_center.api.screenshot.icons import (
    SVG_CANCEL,
    SVG_COPY,
    SVG_EDIT,
    SVG_SAVE,
    svg_to_icon,
)


class ScreenshotToolbar(QFrame):
    """Icon-only toolbar for the selection overlay."""

    def __init__(self, parent: QWidget, on_action):
        super().__init__(parent)
        self.on_action = on_action
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._icon_color = UI["text"]
        self._icon_size = QSize(16, 16)
        self._action_svgs = (
            ("copy", SVG_COPY, "Copy"),
            ("save", SVG_SAVE, "Save as"),
            ("edit", SVG_EDIT, "Edit"),
            ("cancel", SVG_CANCEL, "Cancel"),
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._btns: dict[str, Button] = {}
        for action, _, tip in self._action_svgs:
            b = Button("", variant="subtle", padding="6,6,6,6", parent=self)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setIconSize(self._icon_size)
            set_tooltip(b, tip)
            b.clicked.connect(lambda _=False, a=action: self.on_action(a))
            self._btns[action] = b
            layout.addWidget(b)

        self.btn_copy = self._btns["copy"]
        self.btn_save = self._btns["save"]
        self.btn_edit = self._btns["edit"]
        self.btn_cancel = self._btns["cancel"]
        self._reload_icons()

    def _reload_icons(self) -> None:
        dpr = float(self.devicePixelRatioF())
        for action, svg, _ in self._action_svgs:
            self._btns[action].setIcon(svg_to_icon(svg, 16, self._icon_color, dpr=dpr))

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._reload_icons()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(QColor(UI["border"]), 1))
        p.setBrush(QColor(UI["bg"]))
        p.drawRoundedRect(r, 8, 8)
        p.end()
