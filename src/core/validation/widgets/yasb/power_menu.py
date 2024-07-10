DEFAULTS = {
    'label': "power",
    'blur': True,
    "icons": {
        "lock": "\uea75",
        "signout": "\udb80\udf43",
        "sleep": "\u23fe",
        "restart": "\uead2",
        "shutdown": "\uf011",
        "cancel": "\udb81\udf3a",
    },
}

VALIDATION_SCHEMA = {
    'label': {
        'type': 'string',
        'default': DEFAULTS['label']
    },
    'blur': {
        'type': 'boolean',
        'default': DEFAULTS['blur']
    },
    "icons": {
        "type": "dict",
        "schema": {
            "lock": {
                "type": "string",
                "default": DEFAULTS["icons"]["lock"],
            },
            "signout": {
                "type": "string",
                "default": DEFAULTS["icons"]["signout"],
            },
            "sleep": {
                "type": "string",
                "default": DEFAULTS["icons"]["sleep"],
            },
            "restart": {
                "type": "string",
                "default": DEFAULTS["icons"]["restart"],
            },
            "shutdown": {
                "type": "string",
                "default": DEFAULTS["icons"]["shutdown"],
            },
            "cancel": {
                "type": "string",
                "default": DEFAULTS["icons"]["cancel"],
            }
        },
        "default": DEFAULTS["icons"],
    },
}