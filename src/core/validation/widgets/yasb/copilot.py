DEFAULTS = {
    "label": "{icon}",
    "label_alt": "{used}/{allowance}",
    "token": "",
    "plan": "pro",
    "tooltip": True,
    "update_interval": 3600,
    "icons": {
        "copilot": "\uf4b8",
        "error": "\uf4b9",
    },
    "thresholds": {
        "warning": 75,
        "critical": 90,
    },
    "menu": {
        "blur": True,
        "round_corners": True,
        "round_corners_type": "normal",
        "border_color": "System",
        "alignment": "right",
        "direction": "down",
        "offset_top": 6,
        "offset_left": 0,
        "chart": True,
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "callbacks": {"on_left": "toggle_popup", "on_middle": "do_nothing", "on_right": "toggle_label"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "token": {"type": "string", "default": DEFAULTS["token"]},
    "plan": {
        "type": "string",
        "default": DEFAULTS["plan"],
        "allowed": ["pro", "pro_plus"],
    },
    "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["tooltip"]},
    "update_interval": {
        "type": "integer",
        "default": DEFAULTS["update_interval"],
        "min": 60,
        "max": 86400,
    },
    "icons": {
        "type": "dict",
        "required": False,
        "schema": {
            "copilot": {"type": "string", "default": DEFAULTS["icons"]["copilot"]},
            "error": {"type": "string", "default": DEFAULTS["icons"]["error"]},
        },
        "default": DEFAULTS["icons"],
    },
    "thresholds": {
        "type": "dict",
        "required": False,
        "schema": {
            "warning": {
                "type": "integer",
                "default": DEFAULTS["thresholds"]["warning"],
                "min": 0,
                "max": 100,
            },
            "critical": {
                "type": "integer",
                "default": DEFAULTS["thresholds"]["critical"],
                "min": 0,
                "max": 100,
            },
        },
        "default": DEFAULTS["thresholds"],
    },
    "menu": {
        "type": "dict",
        "required": False,
        "schema": {
            "blur": {"type": "boolean", "default": DEFAULTS["menu"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["menu"]["round_corners"]},
            "round_corners_type": {"type": "string", "default": DEFAULTS["menu"]["round_corners_type"]},
            "border_color": {"type": "string", "default": DEFAULTS["menu"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["menu"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["menu"]["direction"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["menu"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["menu"]["offset_left"]},
            "chart": {"type": "boolean", "default": DEFAULTS["menu"]["chart"]},
        },
        "default": DEFAULTS["menu"],
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
        "required": False,
        "schema": {
            "on_left": {"type": "string", "default": DEFAULTS["callbacks"]["on_left"]},
            "on_middle": {"type": "string", "default": DEFAULTS["callbacks"]["on_middle"]},
            "on_right": {"type": "string", "default": DEFAULTS["callbacks"]["on_right"]},
        },
        "default": DEFAULTS["callbacks"],
    },
}
