DEFAULTS = {
    "label": "",
    "label_alt": "{gif_path}",
    "file_path": "",
    "width": 24,
    "height": 24,
    "speed": 100,
    "keep_aspect_ratio": True,
    "update_interval": 5000,
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_label", "on_middle": "pause_gif", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "label": {
        "type": "string",
        "default": DEFAULTS["label"],
    },
    "label_alt": {
        "type": "string",
        "default": DEFAULTS["label_alt"],
    },
    "file_path": {
        "type": "string",
        "default": DEFAULTS["file_path"],
    },
    "width": {
        "type": "integer",
        "default": DEFAULTS["width"],
    },
    "height": {
        "type": "integer",
        "default": DEFAULTS["height"],
    },
    "speed": {
        "type": "integer",
        "default": DEFAULTS["speed"],
    },
    "keep_aspect_ratio": {
        "type": "boolean",
        "default": DEFAULTS["keep_aspect_ratio"],
    },
    "update_interval": {
        "type": "integer",
        "default": DEFAULTS["update_interval"],
    },
    "callbacks": {
        "type": "dict",
        "schema": {
            "on_left": {
                "type": "string",
                "nullable": True,
                "default": DEFAULTS["callbacks"]["on_left"],
            },
            "on_middle": {
                "type": "string",
                "nullable": True,
                "default": DEFAULTS["callbacks"]["on_middle"],
            },
            "on_right": {"type": "string", "nullable": True, "default": DEFAULTS["callbacks"]["on_right"]},
        },
        "default": DEFAULTS["callbacks"],
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
    "animation": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": DEFAULTS["animation"]["enabled"]},
            "type": {"type": "string", "default": DEFAULTS["animation"]["type"]},
            "duration": {"type": "integer", "default": DEFAULTS["animation"]["duration"], "min": 0},
        },
        "default": DEFAULTS["animation"],
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
}
