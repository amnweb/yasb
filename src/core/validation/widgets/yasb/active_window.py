DEFAULTS = {
    "label": "{win[title]}",
    "label_alt": "[class_name='{win[class_name]}' exe='{win[process][name]}' hwnd={win[hwnd]}]",
    "class_name": "",
    "label_no_window": None,
    "label_icon": True,
    "label_icon_size": 16,
    "max_length": None,
    "max_length_ellipsis": "...",
    "monitor_exclusive": True,
    "rewrite": [],
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "ignore_windows": {"classes": [], "processes": [], "titles": []},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "class_name": {"type": "string", "required": False, "default": DEFAULTS["class_name"]},
    "label_no_window": {"type": "string", "nullable": True, "required": False, "default": DEFAULTS["label_no_window"]},
    "label_icon": {"type": "boolean", "default": DEFAULTS["label_icon"]},
    "label_icon_size": {"type": "integer", "default": DEFAULTS["label_icon_size"]},
    "max_length": {"type": "integer", "min": 1, "nullable": True, "default": DEFAULTS["max_length"]},
    "max_length_ellipsis": {"type": "string", "default": DEFAULTS["max_length_ellipsis"]},
    "monitor_exclusive": {"type": "boolean", "required": False, "default": DEFAULTS["monitor_exclusive"]},
    "rewrite": {
        "type": "list",
        "required": False,
        "schema": {
            "type": "dict",
            "schema": {
                "pattern": {"type": "string", "required": True},
                "replacement": {"type": "string", "required": True},
                "case": {
                    "type": "string",
                    "required": False,
                    "allowed": ["lower", "upper", "title", "capitalize"],
                },
            },
        },
        "default": DEFAULTS["rewrite"],
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
    "ignore_window": {
        "type": "dict",
        "schema": {
            "classes": {"type": "list", "schema": {"type": "string"}, "default": DEFAULTS["ignore_windows"]["classes"]},
            "processes": {
                "type": "list",
                "schema": {"type": "string"},
                "default": DEFAULTS["ignore_windows"]["processes"],
            },
            "titles": {"type": "list", "schema": {"type": "string"}, "default": DEFAULTS["ignore_windows"]["titles"]},
        },
        "default": DEFAULTS["ignore_windows"],
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
            "on_right": {"type": "string", "default": DEFAULTS["callbacks"]["on_right"]},
        },
        "default": DEFAULTS["callbacks"],
    },
}
