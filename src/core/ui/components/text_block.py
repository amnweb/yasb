from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from core.ui.theme import FONT_FAMILIES, get_tokens, theme_key

_VARIANTS = {
    "title": {"size": 28, "weight": QFont.Weight.DemiBold, "color": "text_primary"},
    "title-large": {"size": 40, "weight": QFont.Weight.DemiBold, "color": "text_primary"},
    "subtitle": {"size": 20, "weight": QFont.Weight.DemiBold, "color": "text_primary"},
    "body": {"size": 14, "weight": QFont.Weight.Normal, "color": "text_primary"},
    "body-strong": {"size": 14, "weight": QFont.Weight.DemiBold, "color": "text_primary"},
    "body-secondary": {"size": 14, "weight": QFont.Weight.Normal, "color": "text_secondary"},
    "caption": {"size": 12, "weight": QFont.Weight.DemiBold, "color": "text_secondary"},
    "caption-strong": {"size": 12, "weight": QFont.Weight.DemiBold, "color": "text_primary"},
}


class TextBlock(QLabel):
    """Styled label with variant-based typography and theme reactivity."""

    def __init__(self, text: str = "", variant: str = "body", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        cfg = _VARIANTS.get(variant, _VARIANTS["body"])
        font = QFont()
        font.setFamilies(list(FONT_FAMILIES))
        font.setPixelSize(cfg["size"])
        font.setWeight(cfg["weight"])
        self.setFont(font)

        self._color_key = cfg["color"]
        self._override: str | None = None
        self._theme_key = theme_key()
        self._default_color = get_tokens()[self._color_key]
        self._apply_color()

        QApplication.instance().paletteChanged.connect(self._on_theme_changed)

    def _apply_color(self) -> None:
        self.setStyleSheet(f"color:{self._override or self._default_color}")

    def _on_theme_changed(self) -> None:
        key = theme_key()
        if key == self._theme_key:
            return
        self._theme_key = key
        self._default_color = get_tokens()[self._color_key]
        self._apply_color()

    def set_color_override(self, color: str | None) -> None:
        self._override = color
        self._apply_color()

    def reset_color(self) -> None:
        self._override = None
        self._apply_color()
