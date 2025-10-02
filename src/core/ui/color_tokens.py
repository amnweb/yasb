"""Shared color token definitions for UI components."""

from typing import Dict

# Theme -> Variant -> Property -> Value
ButtonColorTokens = Dict[str, Dict[str, Dict[str, str]]]
# Theme -> Property -> Value
LinkColorTokens = Dict[str, Dict[str, str]]

BUTTON_COLOR_TOKENS: ButtonColorTokens = {
    "dark": {
        "primary": {
            "bg": "#4cc2ff",
            "border": "#4cc2ff",
            "text": "#000000",
            "hover_bg": "#47b1e8",
            "hover_border": "#47b1e8",
            "pressed_bg": "#42a2d2",
            "pressed_border": "#42a2d2",
            "disabled_bg": "#2e3230",
            "disabled_border": "#303432",
            "disabled_text": "rgba(255, 255, 255, 0.5)",
        },
        "secondary": {
            "bg": "rgba(53, 57, 55, 0.7)",
            "border": "rgba(60, 65, 62, 0.8)",
            "text": "rgb(255, 255, 255)",
            "hover_bg": "rgba(53, 57, 55, 0.9)",
            "hover_border": "rgba(60, 65, 62, 0.9)",
            "pressed_bg": "rgba(47, 51, 49, 0.7)",
            "pressed_border": "rgba(47, 51, 49, 1)",
            "disabled_bg": "rgba(42, 45, 44, 0.8)",
            "disabled_border": "rgba(47, 50, 49, 0.8)",
            "disabled_text": "rgba(255, 255, 255, 0.45)",
        },
    },
    "light": {
        "primary": {
            "bg": "#0078d4",
            "border": "#0078d4",
            "text": "#ffffff",
            "hover_bg": "#106ebe",
            "hover_border": "#106ebe",
            "pressed_bg": "#005a9e",
            "pressed_border": "#005a9e",
            "disabled_bg": "#c7e0f4",
            "disabled_border": "#c7e0f4",
            "disabled_text": "rgba(0, 0, 0, 0.45)",
        },
        "secondary": {
            "bg": "rgba(255, 255, 255, 0.9)",
            "border": "rgba(235, 235, 235, 0.9)",
            "text": "rgb(0, 0, 0)",
            "hover_bg": "rgba(255, 255, 255, 0.6)",
            "hover_border": "rgba(235, 235, 235, 0.9)",
            "pressed_bg": "rgba(236, 236, 236, 0.9)",
            "pressed_border": "rgba(218, 218, 218, 1)",
            "disabled_bg": "rgba(249, 249, 249, 0.9)",
            "disabled_border": "rgba(224, 224, 224, 0.8)",
            "disabled_text": "rgba(0, 0, 0, 0.4)",
        },
    },
}

LINK_COLOR_TOKENS: LinkColorTokens = {
    "dark": {
        "text": "#9fdcff",
        "hover_text": "#c3f0ff",
        "hover_bg": "rgba(255,255,255,0.03)",
    },
    "light": {
        "text": "#0b66c3",
        "hover_text": "#064a8a",
        "hover_bg": "rgba(0,0,0,0.04)",
    },
}
