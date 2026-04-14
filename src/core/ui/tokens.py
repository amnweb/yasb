"""
YASB-UI Design Token System.

Complete color token dictionary sourced from microsoft-ui-xaml CommonStyles.
All values in #AARRGGBB hex for both Qt stylesheets and QColor().

Reference: github.com/microsoft/microsoft-ui-xaml/blob/main/src/controls/dev/CommonStyles/Common_themeresources_any.xaml

Note: Some color tokens are intentionally omitted as they are not relevant to YASB's UI components or themes,
some color values have been tweaked for better contrast and aesthetics in the context of a desktop application.
"""

ColorTokens = dict[str, dict[str, str]]

COLOR_TOKENS: ColorTokens = {
    "dark": {
        # Text Fill
        "text_primary": "#ffffff",
        "text_secondary": "#b4ffffff",
        "text_tertiary": "#87ffffff",
        "text_disabled": "#5cffffff",
        "text_inverse": "#e3000000",
        # Accent Text Fill
        "accent_text_primary": "#4cc2ff",
        "accent_text_secondary": "#e64cc2ff",
        "accent_text_tertiary": "#cc4cc2ff",
        "accent_text_disabled": "#5cffffff",
        # Text on Accent Fill
        "text_on_accent_primary": "#000000",
        "text_on_accent_secondary": "#80000000",
        "text_on_accent_disabled": "#87ffffff",
        "text_on_accent_selected": "#ffffff",
        # Control Fill
        "control_fill_default": "#0fffffff",
        "control_fill_secondary": "#14ffffff",
        "control_fill_tertiary": "#08ffffff",
        "control_fill_quarternary": "#0fffffff",
        "control_fill_disabled": "#0affffff",
        "control_fill_transparent": "#00000000",
        "control_fill_input_active": "#b21e1e1e",
        # Control Strong Fill
        "control_strong_fill_default": "#8cffffff",
        "control_strong_fill_disabled": "#40ffffff",
        # Control Solid Fill
        "control_solid_fill_default": "#454545",
        # Subtle Fill
        "subtle_fill_transparent": "#00000000",
        "subtle_fill_secondary": "#0fffffff",
        "subtle_fill_tertiary": "#0affffff",
        "subtle_fill_disabled": "#00000000",
        # Control Alt Fill
        "control_alt_fill_transparent": "#00000000",
        "control_alt_fill_secondary": "#1a000000",
        "control_alt_fill_tertiary": "#0affffff",
        "control_alt_fill_quarternary": "#12ffffff",
        "control_alt_fill_disabled": "#00000000",
        # Control on Image Fill
        "control_on_image_default": "#b21c1c1c",
        "control_on_image_secondary": "#1a1a1a",
        "control_on_image_tertiary": "#131313",
        "control_on_image_disabled": "#1e1e1e",
        # Accent Fill
        "accent_fill_default": "#4cc2ff",
        "accent_fill_secondary": "#e64cc2ff",
        "accent_fill_tertiary": "#cc4cc2ff",
        "accent_fill_disabled": "#29ffffff",
        # Control Stroke
        "control_stroke_default": "#02ffffff",
        "control_stroke_secondary": "#08ffffff",
        "control_stroke_on_accent_default": "#14ffffff",
        "control_stroke_on_accent_secondary": "#23000000",
        "control_stroke_on_accent_tertiary": "#37000000",
        "control_stroke_on_accent_disabled": "#33000000",
        "control_stroke_for_strong_fill_on_image": "#6b000000",
        # Card Stroke
        "card_stroke_default": "#1a000000",
        "card_stroke_default_solid": "#1c1c1c",
        # Control Strong Stroke
        "control_strong_stroke_default": "#8cffffff",
        "control_strong_stroke_disabled": "#29ffffff",
        # Surface Stroke
        "surface_stroke_default": "#66757575",
        "surface_stroke_flyout": "#33000000",
        "surface_stroke_inverse": "#0f000000",
        # Divider Stroke
        "divider_stroke_default": "#14ffffff",
        # Focus Stroke
        "focus_stroke_outer": "#ffffff",
        "focus_stroke_inner": "#b2000000",
        # Card Background Fill
        "card_bg_default": "#0dffffff",
        "card_bg_secondary": "#08ffffff",
        "card_bg_tertiary": "#12ffffff",
        # Dropdown Menu Fill
        "dropdown_menu_bg": "#66303030",
        "dropdown_menu_bg_solid": "#303030",
        # Smoke Fill
        "smoke_default": "#4c000000",
        # Layer Fill
        "layer_default": "#4c3a3a3a",
        "layer_alt": "#0dffffff",
        "layer_on_acrylic_default": "#0affffff",
        "layer_on_mica_default": "#733a3a3a",
        "layer_on_mica_secondary": "#0fffffff",
        "layer_on_mica_tertiary": "#2c2c2c",
        "layer_on_mica_transparent": "#00000000",
        # Solid Background Fill
        "solid_bg_base": "#202020",
        "solid_bg_secondary": "#1c1c1c",
        "solid_bg_tertiary": "#282828",
        "solid_bg_quarternary": "#2c2c2c",
        "solid_bg_quinary": "#333333",
        "solid_bg_senary": "#373737",
        "solid_bg_base_alt": "#0a0a0a",
        # System Fill
        "system_success": "#6ccb5f",
        "system_caution": "#fce100",
        "system_critical": "#ff99a4",
        "system_neutral": "#8cffffff",
        "system_solid_neutral": "#9d9d9d",
        "system_attention_bg": "#08ffffff",
        "system_success_bg": "#393d1b",
        "system_caution_bg": "#433519",
        "system_critical_bg": "#442726",
        "system_neutral_bg": "#08ffffff",
        "system_solid_attention_bg": "#2e2e2e",
        "system_solid_neutral_bg": "#2e2e2e",
    },
    "light": {
        # Text Fill
        "text_primary": "#e3000000",
        "text_secondary": "#9e000000",
        "text_tertiary": "#73000000",
        "text_disabled": "#5c000000",
        "text_inverse": "#ffffff",
        # Accent Text Fill
        "accent_text_primary": "#0078d4",
        "accent_text_secondary": "#cc0078d4",
        "accent_text_tertiary": "#ad0078d4",
        "accent_text_disabled": "#5c000000",
        # Text on Accent Fill
        "text_on_accent_primary": "#ffffff",
        "text_on_accent_secondary": "#b2ffffff",
        "text_on_accent_disabled": "#ffffff",
        "text_on_accent_selected": "#ffffff",
        # Control Fill
        "control_fill_default": "#b2ffffff",
        "control_fill_secondary": "#80f9f9f9",
        "control_fill_tertiary": "#4cf9f9f9",
        "control_fill_quarternary": "#c2f3f3f3",
        "control_fill_disabled": "#4cf9f9f9",
        "control_fill_transparent": "#00000000",
        "control_fill_input_active": "#ffffff",
        # Control Strong Fill
        "control_strong_fill_default": "#73000000",
        "control_strong_fill_disabled": "#52000000",
        # Control Solid Fill
        "control_solid_fill_default": "#ffffff",
        # Subtle Fill
        "subtle_fill_transparent": "#00000000",
        "subtle_fill_secondary": "#0a000000",
        "subtle_fill_tertiary": "#05000000",
        "subtle_fill_disabled": "#00000000",
        # Control Alt Fill
        "control_alt_fill_transparent": "#00000000",
        "control_alt_fill_secondary": "#05000000",
        "control_alt_fill_tertiary": "#0f000000",
        "control_alt_fill_quarternary": "#17000000",
        "control_alt_fill_disabled": "#00000000",
        # Control on Image Fill
        "control_on_image_default": "#c9ffffff",
        "control_on_image_secondary": "#f3f3f3",
        "control_on_image_tertiary": "#ebebeb",
        "control_on_image_disabled": "#00000000",
        # Accent Fill
        "accent_fill_default": "#0078d4",
        "accent_fill_secondary": "#e60078d4",
        "accent_fill_tertiary": "#cc0078d4",
        "accent_fill_disabled": "#38000000",
        # Control Stroke
        "control_stroke_default": "#29000000",
        "control_stroke_secondary": "#0f000000",
        "control_stroke_on_accent_default": "#14ffffff",
        "control_stroke_on_accent_secondary": "#66000000",
        "control_stroke_on_accent_tertiary": "#37000000",
        "control_stroke_on_accent_disabled": "#0f000000",
        "control_stroke_for_strong_fill_on_image": "#59ffffff",
        # Card Stroke
        "card_stroke_default": "#0f000000",
        "card_stroke_default_solid": "#ebebeb",
        # Control Strong Stroke
        "control_strong_stroke_default": "#73000000",
        "control_strong_stroke_disabled": "#38000000",
        # Surface Stroke
        "surface_stroke_default": "#66757575",
        "surface_stroke_flyout": "#0f000000",
        "surface_stroke_inverse": "#14ffffff",
        # Divider Stroke
        "divider_stroke_default": "#0f000000",
        # Focus Stroke
        "focus_stroke_outer": "#e3000000",
        "focus_stroke_inner": "#b2ffffff",
        # Card Background Fill
        "card_bg_default": "#b2ffffff",
        "card_bg_secondary": "#80f6f6f6",
        "card_bg_tertiary": "#ffffff",
        # Dropdown Menu Fill
        "dropdown_menu_bg": "#ccffffff",
        "dropdown_menu_bg_solid": "#f3f3f3",
        # Smoke Fill
        "smoke_default": "#4c000000",
        # Layer Fill
        "layer_default": "#80ffffff",
        "layer_alt": "#ffffff",
        "layer_on_acrylic_default": "#40ffffff",
        "layer_on_mica_default": "#b2ffffff",
        "layer_on_mica_secondary": "#0a000000",
        "layer_on_mica_tertiary": "#f9f9f9",
        "layer_on_mica_transparent": "#00000000",
        # Solid Background Fill
        "solid_bg_base": "#f3f3f3",
        "solid_bg_secondary": "#eeeeee",
        "solid_bg_tertiary": "#f9f9f9",
        "solid_bg_quarternary": "#ffffff",
        "solid_bg_quinary": "#fdfdfd",
        "solid_bg_senary": "#ffffff",
        "solid_bg_base_alt": "#dadada",
        # System Fill
        "system_success": "#0f7b0f",
        "system_caution": "#9d5d00",
        "system_critical": "#c42b1c",
        "system_neutral": "#73000000",
        "system_solid_neutral": "#8a8a8a",
        "system_attention_bg": "#80f6f6f6",
        "system_success_bg": "#dff6dd",
        "system_caution_bg": "#fff4ce",
        "system_critical_bg": "#fde7e9",
        "system_neutral_bg": "#05000000",
        "system_solid_attention_bg": "#f7f7f7",
        "system_solid_neutral_bg": "#f3f3f3",
    },
}
