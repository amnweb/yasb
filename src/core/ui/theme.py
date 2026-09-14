"""
Theme detection and token resolution.

Uses Qt's QStyleHints.colorScheme() to determine dark vs light mode,
then returns the matching token set from tokens.py.
"""

import logging

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


# The accent tokens are the only ones carrying a hue the user controls. Windows exposes the
# same shade ladder WinUI derives its accent brushes from, and picks a different rung per
# theme so text on the accent stays legible: Light2 on dark, Dark1 on light.
_ACCENT_SOURCE = {"dark": "ACCENT_LIGHT2", "light": "ACCENT_DARK1"}
_ACCENT_TOKENS = (
    "accent_text_primary",
    "accent_text_secondary",
    "accent_text_tertiary",
    "accent_fill_default",
    "accent_fill_secondary",
    "accent_fill_tertiary",
)

_accent_cache: dict[str, dict[str, str]] | None = None


def _recolour(value: str, rgb: str) -> str:
    """Swap the RGB of a token, keeping whatever alpha prefix it already had."""
    return value[:3] + rgb[1:] if len(value) == 9 else rgb


def _system_accent() -> dict[str, dict[str, str]]:
    """Per-theme accent token overrides taken from the Windows accent colour."""
    global _accent_cache
    if _accent_cache is not None:
        return _accent_cache
    overrides: dict[str, dict[str, str]] = {"dark": {}, "light": {}}
    try:
        import winrt.windows.ui.viewmanagement as viewmanagement

        settings = viewmanagement.UISettings()
        for theme, source in _ACCENT_SOURCE.items():
            colour = settings.get_color_value(getattr(viewmanagement.UIColorType, source))
            rgb = f"#{colour.r:02x}{colour.g:02x}{colour.b:02x}"
            overrides[theme] = {k: _recolour(COLOR_TOKENS[theme][k], rgb) for k in _ACCENT_TOKENS}
    except Exception:
        # No WinRT, or an OS that does not report the shade: keep the built-in blue.
        logging.getLogger("theme").debug("System accent unavailable, using default", exc_info=True)
    _accent_cache = overrides
    return _accent_cache


def refresh_accent() -> None:
    """Drop the cached accent so the next get_tokens() re-reads it."""
    global _accent_cache
    _accent_cache = None


def get_tokens(theme: str | None = None) -> dict[str, str]:
    """Return color tokens for the given theme, or auto-detect from OS palette."""
    key = theme if theme in ("dark", "light") else theme_key()
    accent = _system_accent()[key]
    return {**COLOR_TOKENS[key], **accent} if accent else COLOR_TOKENS[key]
