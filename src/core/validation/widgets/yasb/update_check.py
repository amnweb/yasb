DEFAULTS = {
    "windows_update": {"enabled": False, "label": "{count}", "tooltip": True, "interval": 1440, "exclude": []},
    "winget_update": {"enabled": False, "label": "{count}", "tooltip": True, "interval": 240, "exclude": []},
}

VALIDATION_SCHEMA = {
    "windows_update": {
        "type": "dict",
        "schema": {
            "enabled": {"type": "boolean", "default": DEFAULTS["windows_update"]["enabled"]},
            "label": {"type": "string", "default": DEFAULTS["windows_update"]["label"]},
            "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["windows_update"]["tooltip"]},
            "interval": {"type": "integer", "default": DEFAULTS["windows_update"]["interval"], "min": 30, "max": 10080},
            "exclude": {"type": "list", "default": DEFAULTS["windows_update"]["exclude"], "schema": {"type": "string"}},
        },
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
    "winget_update": {
        "type": "dict",
        "schema": {
            "enabled": {"type": "boolean", "default": DEFAULTS["winget_update"]["enabled"]},
            "label": {"type": "string", "default": DEFAULTS["winget_update"]["label"]},
            "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["windows_update"]["tooltip"]},
            "interval": {"type": "integer", "default": DEFAULTS["winget_update"]["interval"], "min": 10, "max": 10080},
            "exclude": {"type": "list", "default": DEFAULTS["winget_update"]["exclude"], "schema": {"type": "string"}},
        },
    },
}
