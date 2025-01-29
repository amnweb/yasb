DEFAULTS = {
    "label": "\ueb01 \ueab4 {download_speed} | \ueab7 {upload_speed}",
    "label_alt": "\ueb01 \ueab4 {upload_speed} | \ueab7 {download_speed}",
    "interface": "Auto",
    "update_interval": 1000,
    "hide_if_offline": False,
    "max_label_length": 0,
    "animation": {
        'enabled': True,
        'type': 'fadeInOut',
        'duration': 200
    },
    'container_padding': {'top': 0, 'left': 0, 'bottom': 0, 'right': 0},
    "callbacks": {
        "on_left": "toggle_label",
        "on_middle": "do_nothing",
        "on_right": "do_nothing",
    },
}

VALIDATION_SCHEMA = {
    "label": {"type": "string", "default": DEFAULTS["label"]},
    "label_alt": {"type": "string", "default": DEFAULTS["label_alt"]},
    "interface": {
        "type": "string",
        "required": False,
        "default": DEFAULTS["interface"]
    },
    "update_interval": {
        "type": "integer",
        "default": DEFAULTS["update_interval"],
        "min": 0,
        "max": 60000,
    },
    "hide_if_offline": {
        "type": "boolean",
        "required": False,
        "default": DEFAULTS["hide_if_offline"],
    },
    'max_label_length': {
        'type': 'integer',
        'required': False,
        'default': DEFAULTS['max_label_length'],
        'min': 0
    },
    'animation': {
        'type': 'dict',
        'required': False,
        'schema': {
            'enabled': {
                'type': 'boolean',
                'default': DEFAULTS['animation']['enabled']
            },
            'type': {
                'type': 'string',
                'default': DEFAULTS['animation']['type']
            },
            'duration': {
                'type': 'integer',
                'default': DEFAULTS['animation']['duration']
            }
        },
        'default': DEFAULTS['animation']
    },    
    'container_padding': {
        'type': 'dict',
        'required': False,
        'schema': {
            'top': {
                'type': 'integer',
                'default': DEFAULTS['container_padding']['top']
            },
            'left': {
                'type': 'integer',
                'default': DEFAULTS['container_padding']['left']
            },
            'bottom': {
                'type': 'integer',
                'default': DEFAULTS['container_padding']['bottom']
            },
            'right': {
                'type': 'integer',
                'default': DEFAULTS['container_padding']['right']
            }
        },
        'default': DEFAULTS['container_padding']
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
