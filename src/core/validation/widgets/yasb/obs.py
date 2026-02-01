DEFAULTS = {
    "icons": {
        "recording": "\ueba7",
        "stopped": "\ueba7",
        "paused": "\ueba7",
        "virtual_cam_on": "\udb81\udda0",
        "virtual_cam_off": "\udb81\udda0",
        "studio_mode_on": "\udb84\uddd8",
        "studio_mode_off": "\udb84\uddd8",
    },
    "connection": {"host": "localhost", "port": 4455, "password": ""},
    "hide_when_not_recording": False,
    "blinking_icon": True,
    "show_record_time": False,
    "show_virtual_cam": False,
    "show_studio_mode": False,
    "tooltip": True,
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "keybindings": [],
}

VALIDATION_SCHEMA = {
    "icons": {
        "type": "dict",
        "schema": {
            "recording": {"type": "string", "default": DEFAULTS["icons"]["recording"]},
            "stopped": {"type": "string", "default": DEFAULTS["icons"]["stopped"]},
            "paused": {"type": "string", "default": DEFAULTS["icons"]["paused"]},
            "virtual_cam_on": {"type": "string", "default": DEFAULTS["icons"]["virtual_cam_on"]},
            "virtual_cam_off": {"type": "string", "default": DEFAULTS["icons"]["virtual_cam_off"]},
            "studio_mode_on": {"type": "string", "default": DEFAULTS["icons"]["studio_mode_on"]},
            "studio_mode_off": {"type": "string", "default": DEFAULTS["icons"]["studio_mode_off"]},
        },
        "default": DEFAULTS["icons"],
    },
    "connection": {
        "type": "dict",
        "schema": {
            "host": {"type": "string", "default": DEFAULTS["connection"]["host"]},
            "port": {"type": "integer", "default": DEFAULTS["connection"]["port"]},
            "password": {"type": "string", "default": DEFAULTS["connection"]["password"]},
        },
        "default": DEFAULTS["connection"],
    },
    "hide_when_not_recording": {"type": "boolean", "default": DEFAULTS["hide_when_not_recording"]},
    "blinking_icon": {"type": "boolean", "default": DEFAULTS["blinking_icon"]},
    "show_record_time": {"type": "boolean", "default": DEFAULTS["show_record_time"]},
    "show_virtual_cam": {"type": "boolean", "default": DEFAULTS["show_virtual_cam"]},
    "show_studio_mode": {"type": "boolean", "default": DEFAULTS["show_studio_mode"]},
    "tooltip": {"type": "boolean", "default": DEFAULTS["tooltip"]},
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
    "keybindings": {
        "type": "list",
        "required": False,
        "default": DEFAULTS["keybindings"],
        "schema": {
            "type": "dict",
            "schema": {
                "keys": {"type": "string", "required": True},
                "action": {"type": "string", "required": True},
            },
        },
    },
}
