DEFAULTS = {
    "label": "\udb80\udcb1",
    "label_alt": "\uf293",
    "class_name": "",
    "label_no_device": "No devices connected",
    "label_device_separator": ", ",
    "max_length": None,
    "max_length_ellipsis": "...",
    "tooltip": True,
    "icons": {
        "bluetooth_on": "\udb80\udcaf",
        "bluetooth_off": "\udb80\udcb2",
        "bluetooth_connected": "\udb80\udcb1",
    },
    "device_aliases": [],
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "class_name": {"type": "string", "required": False, "default": DEFAULTS["class_name"]},
    "label_no_device": {"type": "string", "default": DEFAULTS["label_no_device"]},
    "label_device_separator": {"type": "string", "default": DEFAULTS["label_device_separator"]},
    "max_length": {"type": "integer", "min": 1, "nullable": True, "default": DEFAULTS["max_length"]},
    "max_length_ellipsis": {"type": "string", "default": DEFAULTS["max_length_ellipsis"]},
    "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["tooltip"]},
    "icons": {
        "type": "dict",
        "schema": {
            "bluetooth_on": {"type": "string", "default": DEFAULTS["icons"]["bluetooth_on"]},
            "bluetooth_off": {"type": "string", "default": DEFAULTS["icons"]["bluetooth_off"]},
            "bluetooth_connected": {"type": "string", "default": DEFAULTS["icons"]["bluetooth_connected"]},
        },
        "default": DEFAULTS["icons"],
    },
    "device_aliases": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {"name": {"type": "string", "required": True}, "alias": {"type": "string", "required": True}},
        },
        "default": DEFAULTS["device_aliases"],
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
