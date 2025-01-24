DEFAULTS = {
    "offline_label": "GlazeWM Offline",
    "populated_label": None,
    "empty_label": None,
    "hide_empty_workspaces": True,
    "hide_if_offline": False,
    "glazewm_server_uri": "ws://localhost:6123",
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
    "hide_empty_workspaces": {
        "type": "boolean",
        "default": DEFAULTS["hide_empty_workspaces"],
    },
    "hide_if_offline": {
        "type": "boolean",
        "default": DEFAULTS["hide_if_offline"],
    },
    "glazewm_server_uri": {
        "type": "string",
        "default": DEFAULTS["glazewm_server_uri"],
    },
}
