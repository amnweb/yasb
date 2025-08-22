DEFAULTS = {
    "label": "{icon}",
    "label_alt": "{icon} {level}%",
    "class_name": "",
    "mute_text": "mute",
    "tooltip": True,
    "scroll_step": 2,
    "icons": {
        "normal": "\uf130",
        "muted": "\uf131",
    },
    "mic_menu": {
        "blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "system",
        "alignment": "right",
        "direction": "down",
        "offset_top": 6,
        "offset_left": 0,
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_mic_menu", "on_middle": "toggle_label", "on_right": "toggle_mute"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "class_name": {"type": "string", "required": False, "default": DEFAULTS["class_name"]},
    "mute_text": {"type": "string", "default": DEFAULTS["mute_text"]},
    "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["tooltip"]},
    "scroll_step": {
        "type": "integer",
        "required": False,
        "default": DEFAULTS["scroll_step"],
        "min": 1,
        "max": 100,
    },
    "icons": {
        "type": "dict",
        "schema": {
            "normal": {"type": "string", "default": DEFAULTS["icons"]["normal"]},
            "muted": {"type": "string", "default": DEFAULTS["icons"]["muted"]},
        },
        "default": DEFAULTS["icons"],
    },
    "mic_menu": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["mic_menu"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["mic_menu"]["round_corners"]},
            "round_corners_type": {"type": "string", "default": DEFAULTS["mic_menu"]["round_corners_type"]},
            "border_color": {"type": "string", "default": DEFAULTS["mic_menu"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["mic_menu"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["mic_menu"]["direction"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["mic_menu"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["mic_menu"]["offset_left"]},
        },
        "default": DEFAULTS["mic_menu"],
    },
    "animation": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": DEFAULTS["animation"]["enabled"]},
            "type": {"type": "string", "default": DEFAULTS["animation"]["type"]},
            "duration": {"type": "integer", "default": DEFAULTS["animation"]["duration"]},
        },
        "default": DEFAULTS["animation"],
    },
    "container_padding": {
        "type": "dict",
        "required": False,
        "schema": {
            "top": {"type": "integer", "default": DEFAULTS["container_padding"]["top"]},
            "left": {"type": "integer", "default": DEFAULTS["container_padding"]["left"]},
            "bottom": {"type": "integer", "default": DEFAULTS["container_padding"]["bottom"]},
            "right": {"type": "integer", "default": DEFAULTS["container_padding"]["right"]},
        },
        "default": DEFAULTS["container_padding"],
    },
    "label_shadow": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "color": {"type": "string", "default": "black"},
            "offset": {"type": "list", "default": [1, 1]},
            "radius": {"type": "integer", "default": 3},
        },
        "default": {"enabled": False, "color": "black", "offset": [1, 1], "radius": 3},
    },
    "container_shadow": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "color": {"type": "string", "default": "black"},
            "offset": {"type": "list", "default": [1, 1]},
            "radius": {"type": "integer", "default": 3},
        },
        "default": {"enabled": False, "color": "black", "offset": [1, 1], "radius": 3},
    },
    "progress_bar": {
        "type": "dict",
        "default": {"enabled": False},
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "size": {"type": "integer", "default": 18, "min": 8, "max": 64},
            "thickness": {"type": "integer", "default": 3, "min": 1, "max": 10},
            "color": {
                "anyof": [{"type": "string"}, {"type": "list", "schema": {"type": "string"}}],
                "default": "#00C800",
            },
            "background_color": {"type": "string", "default": "#3C3C3C"},
            "position": {"type": "string", "allowed": ["left", "right"], "default": "left"},
            "animation": {
                "type": "boolean",
                "default": True,
            },
        },
    },
    "callbacks": {
        "type": "dict",
        "schema": {
            "on_left": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_left"],
            },
            "on_middle": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_middle"],
            },
            "on_right": {
                "type": "string",
                "default": DEFAULTS["callbacks"]["on_right"],
            },
        },
        "default": DEFAULTS["callbacks"],
    },
}
