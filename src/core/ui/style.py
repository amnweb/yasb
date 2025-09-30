"""
UI Style Utilities.
Provides functions to build and apply styles to UI components based on the current application theme (light or dark).
"""

from typing import Dict

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QPushButton

from core.ui.color_tokens import BUTTON_COLOR_TOKENS, LINK_COLOR_TOKENS

StyleSheetMap = Dict[str, str]


def _resolve_palette() -> QPalette | None:
    try:
        app = QApplication.instance()
    except Exception:
        app = None
    if app is None:
        return None
    try:
        return app.palette()
    except Exception:
        return None


def is_dark_palette() -> bool:
    palette_to_use = _resolve_palette()
    if palette_to_use is None:
        return True
    try:
        window_color = palette_to_use.color(QPalette.ColorRole.Window)
        return window_color.lightness() < 128
    except Exception:
        return True


def build_button_styles() -> StyleSheetMap:
    dark = is_dark_palette()
    theme_key = "dark" if dark else "light"
    tokens = BUTTON_COLOR_TOKENS[theme_key]

    def _build_style(variant_colors: Dict[str, str]) -> str:
        return f"""
            QPushButton {{
                background-color: {variant_colors["bg"]};
                color: {variant_colors["text"]};
                border: 1px solid {variant_colors["border"]};
                border-radius: 4px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI';
                padding: 4px 16px;
            }}
            QPushButton:hover {{
                background-color: {variant_colors["hover_bg"]};
                border: 1px solid {variant_colors["hover_border"]};
            }}
            QPushButton:pressed {{
                background-color: {variant_colors["pressed_bg"]};
                border: 1px solid {variant_colors["pressed_border"]};
            }}
            QPushButton:disabled {{
                background-color: {variant_colors["disabled_bg"]};
                border: 1px solid {variant_colors["disabled_border"]};
                color: {variant_colors["disabled_text"]};
            }}
            """.strip()

    return {variant: _build_style(variant_colors) for variant, variant_colors in tokens.items()}


def apply_button_style(
    button: QPushButton,
    variant: str = "primary",
) -> str:
    styles = build_button_styles()
    try:
        style_sheet = styles[variant]
    except KeyError as exc:
        raise ValueError(f"Unknown button style variant: {variant}") from exc
    button.setStyleSheet(style_sheet)
    return style_sheet


def build_link_button_style() -> str:
    is_dark = is_dark_palette()
    theme_key = "dark" if is_dark else "light"
    tokens = LINK_COLOR_TOKENS[theme_key]
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {tokens["text"]};
            border: none;
            border-radius: 4px;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {tokens["hover_bg"]};
            color: {tokens["hover_text"]};
        }}
        QPushButton#yasbLinkButton {{
            padding: 6px 8px;            
        }}
        """.strip()


def apply_link_button_style(button: QPushButton) -> str:
    style_sheet = build_link_button_style()
    button.setStyleSheet(style_sheet)
    return style_sheet
