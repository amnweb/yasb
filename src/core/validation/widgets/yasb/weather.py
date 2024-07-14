DEFAULTS = {
    'label': "0",
    'label_alt': "0",
    'update_interval': 3600,
    'temp_format': 'celsius',
    'location_id': 'c3e96d6cc4965fc54f88296b54449571c4107c73b9638c16aafc83575b4ddf2e',
    'callbacks': {
        'on_left': "do_nothing",
        'on_middle': "do_nothing",
        'on_right': "do_nothing"
    },
    "icons": {
        "sunnyDay": "\ue30d",
        "clearNight": "\ue32b",
        "cloudyFoggyDay": "\ue312",
        "cloudyFoggyNight": "\ue311",
        "rainyDay": "\udb81\ude7e",
        "rainyNight": "\udb81\ude7e",
        "snowyIcyDay": "\udb81\udd98",
        "snowyIcyNight": "\udb81\udd98",
        "severe": "\uebaa",
        "default": "\uebaa"
    }
}

VALIDATION_SCHEMA = {
    'label': {
        'type': 'string',
        'default': DEFAULTS['label']
    },
    'label_alt': {
        'type': 'string',
        'default': DEFAULTS['label_alt']
    },
    'update_interval': {
        'type': 'integer',
        'default': DEFAULTS['update_interval'],
        'min': 600,
        'max': 36000000
    },
    'location_id': {
        'type': 'string',
        'default': DEFAULTS['location_id']
    },
    'temp_format': {
        'type': 'string',
        'default': DEFAULTS['temp_format']
    },
    "icons": {
        "type": "dict",
        "schema": {
            "sunnyDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["sunnyDay"],
            },
            "clearNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["clearNight"],
            },
            "cloudyFoggyDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["cloudyFoggyDay"],
            },
            "cloudyFoggyNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["cloudyFoggyNight"],
            },
            "rainyDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["rainyDay"],
            },
            "rainyNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["rainyNight"],
            },
            "snowyIcyDay": {
                "type": "string",
                "default": DEFAULTS["icons"]["snowyIcyDay"],
            },
            "snowyIcyNight": {
                "type": "string",
                "default": DEFAULTS["icons"]["snowyIcyNight"],
            },
            "severe": {
                "type": "string",
                "default": DEFAULTS["icons"]["severe"],
            },
            "default": {
                "type": "string",
                "default": DEFAULTS["icons"]["default"],
            }
        },
        "default": DEFAULTS["icons"]
    },
    'callbacks': {
        'type': 'dict',
        'schema': {
            'on_left': {
                'type': 'string',
                'nullable': True,
                'default': DEFAULTS['callbacks']['on_left'],
            },
            'on_middle': {
                'type': 'string',
                'nullable': True,
                'default': DEFAULTS['callbacks']['on_middle'],
            },
            'on_right': {
                'type': 'string',
                'nullable': True,
                'default': DEFAULTS['callbacks']['on_right']
            }
        },
        'default': DEFAULTS['callbacks']
    }
}
