DEFAULTS = {
    "icon_size": 16,
    "tooltip": False,
    "monitor_exclusive": False,
    "ignore_apps": {"classes": [], "processes": [], "titles": []},
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "title_label": {"enabled": False, "show": "focused", "min_length": 10, "max_length": 30},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_window", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "icon_size": {"type": "integer", "default": DEFAULTS["icon_size"]},
    "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["tooltip"]},
    "monitor_exclusive": {"type": "boolean", "required": False, "default": DEFAULTS["monitor_exclusive"]},
    "ignore_apps": {
        "type": "dict",
        "schema": {
            "classes": {"type": "list", "schema": {"type": "string"}, "default": DEFAULTS["ignore_apps"]["classes"]},
            "processes": {
                "type": "list",
                "schema": {"type": "string"},
                "default": DEFAULTS["ignore_apps"]["processes"],
            },
            "titles": {"type": "list", "schema": {"type": "string"}, "default": DEFAULTS["ignore_apps"]["titles"]},
        },
        "default": DEFAULTS["ignore_apps"],
    },
    "title_label": {
        "type": "dict",
        "schema": {
            "enabled": {"type": "boolean", "default": DEFAULTS["title_label"]["enabled"]},
            "show": {"type": "string", "allowed": ["focused", "always"], "default": DEFAULTS["title_label"]["show"]},
            "min_length": {"type": "integer", "default": DEFAULTS["title_label"]["min_length"]},
            "max_length": {"type": "integer", "default": DEFAULTS["title_label"]["max_length"]},
        },
        "default": DEFAULTS["title_label"],
    },
    "animation": {
        "type": ["dict", "boolean"],
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": DEFAULTS["animation"]["enabled"]},
            "type": {"type": "string", "default": DEFAULTS["animation"]["type"]},
            "duration": {"type": "integer", "default": DEFAULTS["animation"]["duration"]},
        },
        "default": DEFAULTS["animation"],
    },
    "container_padding": {"type": "dict", "default": DEFAULTS["container_padding"], "required": False},
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
            "on_right": {"type": "string", "default": DEFAULTS["callbacks"]["on_right"]},
        },
        "default": DEFAULTS["callbacks"],
    },
}
