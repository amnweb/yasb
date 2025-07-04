DEFAULTS = {
    "label": "\uf017 {%H:%M:%S}",
    "label_alt": "\uf017 {%d-%m-%y %H:%M:%S}",
    "class_name": "",
    "update_interval": 1000,
    "locale": "",
    "tooltip": True,
    "timezones": [],
    "calendar": {
        "blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "System",
        "alignment": "right",
        "direction": "down",
        "distance": 6,  # deprecated
        "offset_top": 6,
        "offset_left": 0,
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_calendar", "on_middle": "next_timezone", "on_right": "toggle_label"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "class_name": {"type": "string", "required": False, "default": DEFAULTS["class_name"]},
    "locale": {"required": False, "type": "string", "default": DEFAULTS["locale"]},
    "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["tooltip"]},
    "update_interval": {"type": "integer", "default": 1000, "min": 0, "max": 60000},
    "timezones": {"type": "list", "default": DEFAULTS["timezones"], "schema": {"type": "string", "required": False}},
    "calendar": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["calendar"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["calendar"]["round_corners"]},
            "round_corners_type": {"type": "string", "default": DEFAULTS["calendar"]["round_corners_type"]},
            "border_color": {"type": "string", "default": DEFAULTS["calendar"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["calendar"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["calendar"]["direction"]},
            "distance": {"type": "integer", "default": DEFAULTS["calendar"]["distance"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["calendar"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["calendar"]["offset_left"]},
        },
        "default": DEFAULTS["calendar"],
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
