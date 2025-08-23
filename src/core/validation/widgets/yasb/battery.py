DEFAULTS = {
    "label": "{icon}",
    "label_alt": "{percent}% | remaining: {time_remaining}",
    "class_name": "",
    "update_interval": 5000,
    "time_remaining_natural": False,
    "hide_unsupported": True,
    "charging_options": {"icon_format": "{charging_icon} {icon}", "blink_charging_icon": True, "blink_interval": 500},
    "status_thresholds": {
        "critical": 10,
        "low": 25,
        "medium": 75,
        "high": 95,
        "full": 100,
    },
    "status_icons": {
        "icon_charging": "\uf0e7",
        "icon_critical": "\uf244",
        "icon_low": "\uf243",
        "icon_medium": "\uf242",
        "icon_high": "\uf241",
        "icon_full": "\uf240",
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"},
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "class_name": {"type": "string", "required": False, "default": DEFAULTS["class_name"]},
    "update_interval": {"type": "integer", "min": 0, "max": 60000, "default": DEFAULTS["update_interval"]},
    "time_remaining_natural": {"type": "boolean", "default": DEFAULTS["time_remaining_natural"]},
    "hide_unsupported": {"type": "boolean", "default": DEFAULTS["hide_unsupported"]},
    "charging_options": {
        "type": "dict",
        "schema": {
            "icon_format": {"type": "string", "default": DEFAULTS["charging_options"]["icon_format"]},
            "blink_charging_icon": {"type": "boolean", "default": DEFAULTS["charging_options"]["blink_charging_icon"]},
            "blink_interval": {
                "type": "integer",
                "min": 100,
                "max": 5000,
                "default": DEFAULTS["charging_options"]["blink_interval"],
            },
        },
        "default": DEFAULTS["charging_options"],
    },
    "status_thresholds": {
        "type": "dict",
        "schema": {
            "critical": {"type": "integer", "min": 0, "max": 100, "default": DEFAULTS["status_thresholds"]["critical"]},
            "low": {"type": "integer", "min": 0, "max": 100, "default": DEFAULTS["status_thresholds"]["low"]},
            "medium": {"type": "integer", "min": 0, "max": 100, "default": DEFAULTS["status_thresholds"]["medium"]},
            "high": {"type": "integer", "min": 0, "max": 100, "default": DEFAULTS["status_thresholds"]["high"]},
            "full": {"type": "integer", "min": 0, "max": 100, "default": DEFAULTS["status_thresholds"]["full"]},
        },
        "default": DEFAULTS["status_thresholds"],
    },
    "status_icons": {
        "type": "dict",
        "schema": {
            "icon_charging": {"type": "string", "default": DEFAULTS["status_icons"]["icon_charging"]},
            "icon_critical": {"type": "string", "default": DEFAULTS["status_icons"]["icon_critical"]},
            "icon_low": {"type": "string", "default": DEFAULTS["status_icons"]["icon_low"]},
            "icon_medium": {"type": "string", "default": DEFAULTS["status_icons"]["icon_medium"]},
            "icon_high": {"type": "string", "default": DEFAULTS["status_icons"]["icon_high"]},
            "icon_full": {"type": "string", "default": DEFAULTS["status_icons"]["icon_full"]},
        },
        "default": DEFAULTS["status_icons"],
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
            "on_right": {"type": "string", "default": DEFAULTS["callbacks"]["on_right"]},
        },
        "default": DEFAULTS["callbacks"],
    },
}
