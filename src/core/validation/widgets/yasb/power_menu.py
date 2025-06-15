DEFAULTS = {
    "label": "power",
    "uptime": True,
    "blur": False,
    "blur_background": True,
    "animation_duration": 200,
    "button_row": 3,
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "uptime": {"type": "boolean", "default": DEFAULTS["uptime"], "required": False},
    "blur": {"type": "boolean", "default": DEFAULTS["blur"]},
    "blur_background": {"type": "boolean", "default": DEFAULTS["blur_background"]},
    "animation_duration": {"type": "integer", "default": DEFAULTS["animation_duration"], "min": 0, "max": 2000},
    "button_row": {"type": "integer", "default": DEFAULTS["button_row"], "min": 1, "max": 5},
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
    "buttons": {
        "type": "dict",
        "schema": {
            "lock": {"type": "list", "required": False},
            "signout": {"type": "list", "required": False},
            "sleep": {"type": "list", "required": False},
            "restart": {"type": "list", "required": True},
            "shutdown": {"type": "list", "required": True},
            "cancel": {"type": "list", "required": True},
            "hibernate": {"type": "list", "required": False},
            "force_shutdown": {"type": "list", "required": False},
            "force_restart": {"type": "list", "required": False},
        },
    },
}
