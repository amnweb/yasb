DEFAULTS = {
    "gpu_index": 0,
    "label": "{info[utilization]}%",
    "label_alt": "{info[mem_used]}/{info[mem_total]}",
    "class_name": "",
    "update_interval": 2000,
    "histogram_icons": ["\u2581", "\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"],
    "histogram_num_columns": 10,
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"},
    "gpu_thresholds": {"low": 30, "medium": 60, "high": 90},
    "hide_decimal": False,
    "units": "metric",
}

VALIDATION_SCHEMA = {
    "gpu_index": {
        "type": "integer",
        "required": False,
        "default": DEFAULTS["gpu_index"],
        "min": 0,
    },
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "class_name": {"type": "string", "required": False, "default": DEFAULTS["class_name"]},
    "update_interval": {"type": "integer", "default": DEFAULTS["update_interval"], "min": 2000, "max": 60000},
    "histogram_icons": {
        "type": "list",
        "default": DEFAULTS["histogram_icons"],
        "minlength": 9,
        "maxlength": 9,
        "schema": {"type": "string"},
    },
    "histogram_num_columns": {"type": "integer", "default": DEFAULTS["histogram_num_columns"], "min": 1, "max": 128},
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
    "progress_bar": {
        "type": "dict",
        "default": {"enabled": False},
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "size": {"type": "integer", "default": 18, "min": 8, "max": 64},
            "thickness": {"type": "integer", "default": 3, "min": 1, "max": 10},
            "color": {
                "anyof": [{"type": "string"}, {"type": "list", "schema": {"type": "string"}}],
                "default": "#00C800",
            },
            "background_color": {"type": "string", "default": "#3C3C3C"},
            "position": {"type": "string", "allowed": ["left", "right"], "default": "left"},
            "animation": {
                "type": "boolean",
                "default": True,
            },
        },
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
    "gpu_thresholds": {
        "type": "dict",
        "required": False,
        "schema": {
            "low": {"type": "integer", "default": DEFAULTS["gpu_thresholds"]["low"], "min": 0, "max": 100},
            "medium": {"type": "integer", "default": DEFAULTS["gpu_thresholds"]["medium"], "min": 0, "max": 100},
            "high": {"type": "integer", "default": DEFAULTS["gpu_thresholds"]["high"], "min": 0, "max": 100},
        },
        "default": DEFAULTS["gpu_thresholds"],
    },
    "hide_decimal": {"type": "boolean", "default": DEFAULTS["hide_decimal"]},
    "units": {"type": "string", "default": DEFAULTS["units"], "allowed": ["metric", "imperial"]},
}
