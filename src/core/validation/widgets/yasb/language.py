DEFAULTS = {
    "label": "{lang[language_code]}-{lang[country_code]}",
    "label_alt": "{lang[full_name]}",
    "update_interval": 5,
    "class_name": "",
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "language_menu": {
        "blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "system",
        "alignment": "right",
        "direction": "down",
        "offset_top": 6,
        "offset_left": 0,
        "layout_icon": "\uf11c",
        "show_layout_icon": True,
    },
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "update_interval": {"type": "integer", "default": DEFAULTS["update_interval"], "min": 1, "max": 3600},
    "class_name": {"type": "string", "required": False, "default": DEFAULTS["class_name"]},
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
    "language_menu": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["language_menu"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["language_menu"]["round_corners"]},
            "round_corners_type": {"type": "string", "default": DEFAULTS["language_menu"]["round_corners_type"]},
            "border_color": {"type": "string", "default": DEFAULTS["language_menu"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["language_menu"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["language_menu"]["direction"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["language_menu"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["language_menu"]["offset_left"]},
            "layout_icon": {"type": "string", "default": DEFAULTS["language_menu"]["layout_icon"]},
            "show_layout_icon": {"type": "boolean", "default": DEFAULTS["language_menu"]["show_layout_icon"]},
        },
        "default": DEFAULTS["language_menu"],
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
