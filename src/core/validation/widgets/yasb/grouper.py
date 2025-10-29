DEFAULTS = {
    "class_name": "grouper",
    "widgets": [],
    "hide_empty": False,
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "collapse_options": {
        "enabled": False,
        "exclude_widgets": [],
        "expanded_label": "\uf054",
        "collapsed_label": "\uf053",
        "label_position": "right",
    },
}

VALIDATION_SCHEMA = {
    "class_name": {"type": "string", "default": DEFAULTS["class_name"]},
    "widgets": {
        "type": "list",
        "default": DEFAULTS["widgets"],
        "schema": {
            "type": "string",
            "required": False,
        },
    },
    "hide_empty": {"type": "boolean", "required": False, "default": DEFAULTS["hide_empty"]},
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
    # Collapsible grouper options (structured)
    "collapse_options": {
        "type": "dict",
        "required": False,
        "schema": {
            "enabled": {"type": "boolean", "required": False, "default": True},
            "exclude_widgets": {
                "type": "list",
                "required": False,
                "default": [],
                "schema": {"type": "string", "required": False},
            },
            "expanded_label": {"type": "string", "required": False},
            "collapsed_label": {"type": "string", "required": False},
            "label_position": {"type": "string", "required": False},
        },
        "default": DEFAULTS["collapse_options"],
    },
}
