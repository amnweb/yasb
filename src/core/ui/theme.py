"""
Theme detection and token resolution.

Uses Qt's QStyleHints.colorScheme() to determine dark vs light mode,
then returns the matching token set from tokens.py.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QGuiApplication

from core.ui.tokens import COLOR_TOKENS

# Common font families and weights for consistent typography across components
FONT_FAMILIES = ("Segoe UI Variable", "Segoe UI", "system-ui")
FONT_WEIGHTS = {
    "thin": QFont.Weight.Thin,
    "light": QFont.Weight.Light,
    "normal": QFont.Weight.Normal,
    "medium": QFont.Weight.Medium,
    "demibold": QFont.Weight.DemiBold,
    "bold": QFont.Weight.Bold,
}


def is_dark() -> bool:
    app = QGuiApplication.instance()
    if app is None:
        return True
    return app.styleHints().colorScheme() == Qt.ColorScheme.Dark


def theme_key() -> str:
    return "dark" if is_dark() else "light"


def get_tokens(theme: str | None = None) -> dict[str, str]:
    """Return color tokens for the given theme, or auto-detect from OS palette."""
    key = theme if theme in ("dark", "light") else theme_key()
    return COLOR_TOKENS[key]
