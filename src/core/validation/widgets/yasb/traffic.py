DEFAULTS = {
    "label": "\ueb01 \ueab4 {download_speed} | \ueab7 {upload_speed}",
    "label_alt": "\ueb01 \ueab4 {upload_speed} | \ueab7 {download_speed}",
    "update_interval": 1000,
    "callbacks": {
        "on_left": "toggle_label",
        "on_middle": "do_nothing",
        "on_right": "do_nothing",
    },
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "update_interval": {
        "type": "integer",
        "default": DEFAULTS["update_interval"],
        "min": 0,
        "max": 60000,
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
