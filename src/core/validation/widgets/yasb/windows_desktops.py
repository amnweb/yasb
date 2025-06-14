DEFAULTS = {
    "label_workspace_btn": "{index}",
    "label_workspace_active_btn": "{index}",
    "switch_workspace_animation": True,
    "animation": False,
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
}
VALIDATION_SCHEMA = {
    "label_workspace_btn": {"type": "string", "default": DEFAULTS["label_workspace_btn"]},
    "label_workspace_active_btn": {"type": "string", "default": DEFAULTS["label_workspace_active_btn"]},
    "switch_workspace_animation": {
        "type": "boolean",
        "required": False,
        "default": DEFAULTS["switch_workspace_animation"],
    },
    "animation": {"type": "boolean", "required": False, "default": DEFAULTS["animation"]},
    "btn_shadow": {
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
