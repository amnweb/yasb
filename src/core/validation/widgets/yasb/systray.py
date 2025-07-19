DEFAULTS = {
    "class_name": "systray",
    "label_collapsed": "▼",
    "label_expanded": "▶",
    "label_position": "left",
    "icon_size": 16,
    "pin_click_modifier": "alt",
    "show_unpinned": True,
    "show_unpinned_button": True,
    "show_battery": False,
    "show_volume": False,
    "show_network": False,
    "tooltip": True,
    "container_padding": {"left": 0, "top": 0, "right": 0, "bottom": 0},
    "default_shadow": {
        "enabled": False,
        "color": "black",
        "offset": [1, 1],
        "radius": 3,
    },
}

VALIDATION_SCHEMA = {
    "class_name": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["class_name"],
    },
    "label_collapsed": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["label_collapsed"],
    },
    "label_expanded": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["label_expanded"],
    },
    "label_position": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["label_position"],
    },
    "icon_size": {
        "type": "integer",
        "required": False,
        "default": DEFAULTS["icon_size"],
        "min": 8,
        "max": 64,
    },
    "pin_click_modifier": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["pin_click_modifier"],
    },
    "show_unpinned": {
        "type": "boolean",
        "required": False,
        "default": DEFAULTS["show_unpinned"],
    },
    "show_unpinned_button": {
        "type": "boolean",
        "required": False,
        "default": DEFAULTS["show_unpinned_button"],
    },
    "show_battery": {
        "type": "boolean",
        "required": False,
        "default": DEFAULTS["show_battery"],
    },
    "show_volume": {
        "type": "boolean",
        "required": False,
        "default": DEFAULTS["show_volume"],
    },
    "show_network": {
        "type": "boolean",
        "required": False,
        "default": DEFAULTS["show_network"],
    },
    "tooltip": {"type": "boolean", "required": False, "default": DEFAULTS["tooltip"]},
    "container_padding": {
        "type": "dict",
        "required": False,
        "schema": {
            "left": {"type": "integer", "default": 0},
            "top": {"type": "integer", "default": 0},
            "right": {"type": "integer", "default": 0},
            "bottom": {"type": "integer", "default": 0},
        },
        "default": DEFAULTS["container_padding"],
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
        "default": DEFAULTS["default_shadow"],
    },
    "unpinned_shadow": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "color": {"type": "string", "default": "black"},
            "offset": {"type": "list", "default": [1, 1]},
            "radius": {"type": "integer", "default": 3},
        },
        "default": DEFAULTS["default_shadow"],
    },
    "pinned_shadow": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "color": {"type": "string", "default": "black"},
            "offset": {"type": "list", "default": [1, 1]},
            "radius": {"type": "integer", "default": 3},
        },
        "default": DEFAULTS["default_shadow"],
    },
    "unpinned_vis_btn_shadow": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "color": {"type": "string", "default": "black"},
            "offset": {"type": "list", "default": [1, 1]},
            "radius": {"type": "integer", "default": 3},
        },
        "default": DEFAULTS["default_shadow"],
    },
    "btn_shadow": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "default": False},
            "color": {"type": "string", "default": "black"},
            "offset": {"type": "list", "default": [1, 1]},
            "radius": {"type": "integer", "default": 3},
        },
        "default": DEFAULTS["default_shadow"],
    },
}
