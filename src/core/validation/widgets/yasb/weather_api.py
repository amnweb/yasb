DEFAULTS = {
    'label': '0',
    'label_alt': '0',
    'update_interval': 3600,
    'hide_decimal': False,
    'location': 'London',
    'api_key': '0',
    'icons': {
        'sunnyDay': '\ue30d',
        'clearNight': '\ue32b',
        'cloudyDay': '\ue312',
        'cloudyNight': '\ue311',
        'rainyDay': '\udb81\ude7e',
        'rainyNight': '\udb81\ude7e',
        'snowyIcyDay': '\udb81\udd98',
        'snowyIcyNight': '\udb81\udd98',
        'blizzard': '\uebaa',
        'default': '\uebaa'
    },
    'callbacks': {
        'on_left': 'do_nothing',
        'on_middle': 'do_nothing',
        'on_right': 'do_nothing'
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
        'min': 60,
        'max': 36000000
    },
    'hide_decimal': {
        'type': 'boolean',
        'default': DEFAULTS['hide_decimal']
    },
    'location': {
        'type': 'string',
        'default': DEFAULTS['location']
    },
    'api_key': {
        'type': 'string',
        'default': DEFAULTS['api_key']
    },
    'icons': {
        'type': 'dict',
        'required': False,
        'schema': {
            'sunnyDay': {
                'type': 'string',
                'default': DEFAULTS['icons']['sunnyDay']
            },
            'clearNight': {
                'type': 'string',
                'default': DEFAULTS['icons']['clearNight'],
            },
            'cloudyDay': {
                'type': 'string',
                'default': DEFAULTS['icons']['cloudyDay'],
            },
            'cloudyNight': {
                'type': 'string',
                'default': DEFAULTS['icons']['cloudyNight'],
            },
            'rainyDay': {
                'type': 'string',
                'default': DEFAULTS['icons']['rainyDay'],
            },
            'rainyNight': {
                'type': 'string',
                'default': DEFAULTS['icons']['rainyNight'],
            },
            'snowyIcyDay': {
                'type': 'string',
                'default': DEFAULTS['icons']['snowyIcyDay'],
            },
            'snowyIcyNight': {
                'type': 'string',
                'default': DEFAULTS['icons']['snowyIcyNight'],
            },
            'blizzard': {
                'type': 'string',
                'default': DEFAULTS['icons']['blizzard'],
            },
            'default': {
                'type': 'string',
                'default': DEFAULTS['icons']['default'],
            }
        },
        'default': DEFAULTS['icons']
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