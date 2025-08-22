DEFAULTS = {
    "label": "{volume_label} {space[used][percent]}",
    "label_alt": "{volume_label} {space[used][gb]} / {space[total][gb]}",
    "class_name": "",
    "volume_label": "C",
    "update_interval": 60,
    "decimal_display": 1,
    "group_label": {
        "volume_labels": ["C"],
        "show_label_name": True,
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
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "toggle_label", "on_middle": "do_nothing", "on_right": "do_nothing"},
    "disk_thresholds": {
        "low": 25,
        "medium": 50,
        "high": 90,
    },
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "class_name": {"type": "string", "required": False, "default": DEFAULTS["class_name"]},
    "volume_label": {"type": "string", "default": DEFAULTS["volume_label"]},
    "update_interval": {"type": "integer", "default": DEFAULTS["update_interval"], "min": 0, "max": 3600},
    "decimal_display": {
        "required": False,
        "type": "integer",
        "default": DEFAULTS["decimal_display"],
        "min": 0,
        "max": 3,
    },
    "group_label": {
        "type": "dict",
        "required": False,
        "schema": {
            "volume_labels": {
                "type": "list",
                "schema": {"type": "string"},
                "default": DEFAULTS["group_label"]["volume_labels"],
            },
            "show_label_name": {"type": "boolean", "default": DEFAULTS["group_label"]["show_label_name"]},
            "blur": {"type": "boolean", "default": DEFAULTS["group_label"]["blur"]},
            "round_corners": {"type": "boolean", "default": DEFAULTS["group_label"]["round_corners"]},
            "round_corners_type": {
                "type": "string",
                "default": DEFAULTS["group_label"]["round_corners_type"],
                "allowed": ["normal", "small"],
            },
            "border_color": {"type": "string", "default": DEFAULTS["group_label"]["border_color"]},
            "alignment": {"type": "string", "default": DEFAULTS["group_label"]["alignment"]},
            "direction": {"type": "string", "default": DEFAULTS["group_label"]["direction"]},
            "distance": {"type": "integer", "default": DEFAULTS["group_label"]["distance"]},
            "offset_top": {"type": "integer", "default": DEFAULTS["group_label"]["offset_top"]},
            "offset_left": {"type": "integer", "default": DEFAULTS["group_label"]["offset_left"]},
        },
        "default": DEFAULTS["group_label"],
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
    "disk_thresholds": {
        "type": "dict",
        "required": False,
        "schema": {
            "low": {"type": "integer", "default": DEFAULTS["disk_thresholds"]["low"], "min": 0, "max": 100},
            "medium": {"type": "integer", "default": DEFAULTS["disk_thresholds"]["medium"], "min": 0, "max": 100},
            "high": {"type": "integer", "default": DEFAULTS["disk_thresholds"]["high"], "min": 0, "max": 100},
        },
        "default": DEFAULTS["disk_thresholds"],
    },
}
