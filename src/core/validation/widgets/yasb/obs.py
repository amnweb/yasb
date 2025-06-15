DEFAULTS = {
    "icons": {"recording": "\ueba7", "stopped": "\ueba7", "paused": "\ueba7"},
    "connection": {"host": "localhost", "port": 4455, "password": ""},
    "hide_when_not_recording": False,
    "blinking_icon": True,
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
}

VALIDATION_SCHEMA = {
    "icons": {
        "type": "dict",
        "schema": {
            "recording": {"type": "string", "default": DEFAULTS["icons"]["recording"]},
            "stopped": {"type": "string", "default": DEFAULTS["icons"]["stopped"]},
            "paused": {"type": "string", "default": DEFAULTS["icons"]["paused"]},
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
}
