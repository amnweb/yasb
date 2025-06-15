DEFAULTS = {
    "label": "<span>{icon}</span> {binding_mode}",
    "label_alt": "<span>{icon}</span> Current mode: {binding_mode}",
    "glazewm_server_uri": "ws://localhost:6123",
    "hide_if_no_active": True,
    "label_if_no_active": "No binding mode active",
    "default_icon": "\uf071",
    "icons": {
        "none": "",
        "resize": "\uf071",
        "pause": "\uf28c",
    },
    "binding_modes_to_cycle_through": [
        "none",
        "resize",
        "pause",
    ],
    "default_shadow": {
        "enabled": False,
        "color": "black",
        "offset": [1, 1],
        "radius": 3,
    },
    "animation": {"enabled": True, "type": "fadeInOut", "duration": 200},
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "callbacks": {"on_left": "next_binding_mode", "on_middle": "toggle_label", "on_right": "disable_binding_mode"},
}

VALIDATION_SCHEMA = {
    "label": {
        "type": "string",
        "default": DEFAULTS["label"],
    },
    "label_alt": {
        "type": "string",
        "default": DEFAULTS["label_alt"],
    },
    "glazewm_server_uri": {
        "type": "string",
        "default": DEFAULTS["glazewm_server_uri"],
    },
    "hide_if_no_active": {
        "type": "boolean",
        "default": DEFAULTS["hide_if_no_active"],
    },
    "label_if_no_active": {
        "type": "string",
        "default": DEFAULTS["label_if_no_active"],
    },
    "default_icon": {
        "type": "string",
        "default": DEFAULTS["default_icon"],
    },
    "icons": {
        "type": "dict",
        "required": False,
        "default": DEFAULTS["icons"],
        "keysrules": {
            "type": "string",
        },
        "valuesrules": {
            "type": "string",
        },
    },
    "binding_modes_to_cycle_through": {
        "type": "list",
        "default": DEFAULTS["binding_modes_to_cycle_through"],
        "schema": {
            "type": "string",
            "required": False,
        },
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
    "label_shadow": {
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
        "default": DEFAULTS["container_padding"],
        "required": False,
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
}
