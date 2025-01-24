DEFAULTS = {
    "horizontal_label": "\udb81\udce1",
    "vertical_label": "\udb81\udce2",
    "glazewm_server_uri": "ws://localhost:6123",
}


VALIDATION_SCHEMA = {
    "glazewm_server_uri": {
        "type": "string",
        "default": DEFAULTS["glazewm_server_uri"],
    },
    "horizontal_label": {
        "type": "string",
        "default": DEFAULTS["horizontal_label"]
    },
    "vertical_label": {
        "type": "string",
        "default": DEFAULTS["vertical_label"]
    },
}
