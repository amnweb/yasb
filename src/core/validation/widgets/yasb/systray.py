DEFAULTS = {
    "class_name": "systray",
    "label_collapsed": "▼",
    "label_expanded": "▶",
    "label_position": "left",
    "icon_size": 16,
    "pin_click_modifier": "alt",
    "show_unpinned": True,
    "show_battery": False,
    "show_volume": False,
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
}
