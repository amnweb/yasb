DEFAULTS = {
    "label": "{icon}",
    "label_alt": "{online}/{offline} of {total} servers",
    "update_interval": 300,
    "tooltip": True,
    "servers": [""],
    "ssl_check": True,
    "ssl_warning": 30,
    "ssl_verify": True,
    "desktop_notifications": {"ssl": False, "offline": False},
    "timeout": 5,
    "menu": {
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
    "icons": {"online": "\uf444", "offline": "\uf4c3", "warning": "\uf4c3", "reload": "\udb81\udc50"},
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "update_interval": {"type": "integer", "default": DEFAULTS["update_interval"], "min": 10, "max": 36000},
    "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["tooltip"]},
    "servers": {"type": "list", "schema": {"type": "string"}, "default": DEFAULTS["servers"]},
    "ssl_check": {"type": "boolean", "required": False, "default": DEFAULTS["ssl_check"]},
    "ssl_verify": {"type": "boolean", "required": False, "default": DEFAULTS["ssl_verify"]},
    "ssl_warning": {"type": "integer", "default": DEFAULTS["ssl_warning"], "min": 1, "max": 365},
    "desktop_notifications": {
        "type": "dict",
        "required": False,
        "schema": {
            "ssl": {"type": "boolean", "default": DEFAULTS["desktop_notifications"]["ssl"]},
            "offline": {"type": "boolean", "default": DEFAULTS["desktop_notifications"]["offline"]},
        },
        "default": DEFAULTS["desktop_notifications"],
    },
    "timeout": {"type": "integer", "default": DEFAULTS["timeout"], "min": 1, "max": 30},
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
            "distance": {"type": "integer", "default": DEFAULTS["menu"]["distance"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["menu"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["menu"]["offset_left"]},
        },
        "default": DEFAULTS["menu"],
    },
    "icons": {
        "type": "dict",
        "required": False,
        "schema": {
            "online": {"type": "string", "default": DEFAULTS["icons"]["online"]},
            "offline": {"type": "string", "default": DEFAULTS["icons"]["offline"]},
            "warning": {"type": "string", "default": DEFAULTS["icons"]["warning"]},
            "reload": {"type": "string", "default": DEFAULTS["icons"]["reload"]},
        },
        "default": DEFAULTS["icons"],
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
