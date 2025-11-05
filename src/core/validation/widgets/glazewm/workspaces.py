DEFAULTS = {
    "offline_label": "GlazeWM Offline",
    "populated_label": None,
    "empty_label": None,
    "active_populated_label": None,
    "active_empty_label": None,
    "focused_populated_label": None,
    "focused_empty_label": None,
    "hide_empty_workspaces": True,
    "hide_if_offline": False,
    "glazewm_server_uri": "ws://localhost:6123",
    "enable_scroll_switching": True,
    "reverse_scroll_direction": False,
    "default_shadow": {
        "enabled": False,
        "color": "black",
        "offset": [1, 1],
        "radius": 3,
    },
    "container_padding": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    "app_icons": {
        "enabled_populated": False,
        "enabled_active": False,
        "enabled_focused": None,
        "size": 16,
        "max_icons": 0,
        "hide_label": False,
        "hide_duplicates": False,
        "hide_floating": False,
    },
    "animation": False,
}

VALIDATION_SCHEMA = {
    "offline_label": {
        "type": "string",
        "default": DEFAULTS["offline_label"],
    },
    "populated_label": {
        "type": "string",
        "default": DEFAULTS["populated_label"],
        "nullable": True,
    },
    "empty_label": {
        "type": "string",
        "default": DEFAULTS["empty_label"],
        "nullable": True,
    },
    "active_populated_label": {
        "type": "string",
        "default": DEFAULTS["active_populated_label"],
        "nullable": True,
    },
    "active_empty_label": {
        "type": "string",
        "default": DEFAULTS["active_empty_label"],
        "nullable": True,
    },
    "focused_populated_label": {
        "type": "string",
        "default": DEFAULTS["focused_populated_label"],
        "nullable": True,
    },
    "focused_empty_label": {
        "type": "string",
        "default": DEFAULTS["focused_empty_label"],
        "nullable": True,
    },
    "hide_empty_workspaces": {
        "type": "boolean",
        "default": DEFAULTS["hide_empty_workspaces"],
    },
    "hide_if_offline": {
        "type": "boolean",
        "default": DEFAULTS["hide_if_offline"],
    },
    "container_padding": {"type": "dict", "default": DEFAULTS["container_padding"], "required": False},
    "glazewm_server_uri": {
        "type": "string",
        "default": DEFAULTS["glazewm_server_uri"],
    },
    "enable_scroll_switching": {
        "type": "boolean",
        "default": DEFAULTS["enable_scroll_switching"],
    },
    "reverse_scroll_direction": {
        "type": "boolean",
        "default": DEFAULTS["reverse_scroll_direction"],
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
    "app_icons": {
        "type": "dict",
        "default": DEFAULTS["app_icons"],
        "schema": {
            "enabled_populated": {"type": "boolean", "default": DEFAULTS["app_icons"]["enabled_populated"]},
            "enabled_active": {"type": "boolean", "default": DEFAULTS["app_icons"]["enabled_active"]},
            "enabled_focused": {
                "type": "boolean",
                "default": DEFAULTS["app_icons"]["enabled_focused"],
                "nullable": True,
            },
            "size": {"type": "integer", "default": DEFAULTS["app_icons"]["size"]},
            "max_icons": {"type": "integer", "default": DEFAULTS["app_icons"]["max_icons"]},
            "hide_label": {"type": "boolean", "default": DEFAULTS["app_icons"]["hide_label"]},
            "hide_duplicates": {"type": "boolean", "default": DEFAULTS["app_icons"]["hide_duplicates"]},
            "hide_floating": {"type": "boolean", "default": DEFAULTS["app_icons"]["hide_floating"]},
        },
    },
    "animation": {"type": "boolean", "default": DEFAULTS["animation"]},
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
}
