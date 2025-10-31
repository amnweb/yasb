DEFAULTS = {
    "label": "<span>\ud83e\ude78<span><span class='sgv'>{sgv}</span><span>{direction}</span>",
    "error_label": "<span>\ud83e\ude78</span>{error_message}",
    "tooltip": "({sgv_delta}) {delta_time_in_minutes} min",
    "host": "",
    "secret": "",
    "secret_env_name": "",
    "direction_icons": {
        "double_up": "\u2b06\ufe0f\u2b06\ufe0f",
        "single_up": "\u2b06\ufe0f",
        "forty_five_up": "\u2197\ufe0f",
        "flat": "\u27a1\ufe0f",
        "forty_five_down": "\u2198\ufe0f",
        "single_down": "\u2b07\ufe0f",
        "double_down": "\u2b07\ufe0f\u2b07\ufe0f",
    },
    "sgv_measurement_units": "mmol/l",  # "mg/dl" or "mmol/l"
    "callbacks": {"on_left": "open_cgm", "on_middle": "do_nothing", "on_right": "do_nothing"},
    "notify_on_error": True,
    "sgv_range": {
        "min": 4,
        "max": 9,
    },
}

VALIDATION_SCHEMA = {
    "label": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["label"],
    },
    "error_label": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["error_label"],
    },
    "tooltip": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["tooltip"],
    },
    "host": {
        "type": "string",
        "default": DEFAULTS["host"],
    },
    "secret": {
        "type": "string",
        "default": DEFAULTS["secret"],
    },
    "secret_env_name": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["secret_env_name"],
    },
    "direction_icons": {
        "type": "dict",
        "required": False,
        "schema": {
            "double_up": {
                "type": "string",
                "default": DEFAULTS["direction_icons"]["double_up"],
            },
            "single_up": {
                "type": "string",
                "default": DEFAULTS["direction_icons"]["single_up"],
            },
            "forty_five_up": {
                "type": "string",
                "default": DEFAULTS["direction_icons"]["forty_five_up"],
            },
            "flat": {
                "type": "string",
                "default": DEFAULTS["direction_icons"]["flat"],
            },
            "forty_five_down": {
                "type": "string",
                "default": DEFAULTS["direction_icons"]["forty_five_down"],
            },
            "single_down": {
                "type": "string",
                "default": DEFAULTS["direction_icons"]["single_down"],
            },
            "double_down": {
                "type": "string",
                "default": DEFAULTS["direction_icons"]["double_down"],
            },
        },
        "default": DEFAULTS["direction_icons"],
    },
    "sgv_measurement_units": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["sgv_measurement_units"],
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
    "notify_on_error": {
        "type": "boolean",
        "required": False,
        "default": DEFAULTS["notify_on_error"],
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
    "sgv_range": {
        "type": "dict",
        "required": False,
        "schema": {
            "min": {"type": "float", "default": DEFAULTS["sgv_range"]["min"]},
            "max": {"type": "float", "default": DEFAULTS["sgv_range"]["max"]},
        },
        "default": {
            "min": DEFAULTS["sgv_range"]["min"],
            "max": DEFAULTS["sgv_range"]["max"],
        },
    },
}
