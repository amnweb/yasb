DEFAULTS = {
    'label': '\uf017 {%H:%M:%S}',
    'label_alt': '\uf017 {%d-%m-%y %H:%M:%S}',
    'update_interval': 1000,
    'timezones': [],
    'callbacks': {
        'on_left': 'toggle_label',
        'on_middle': 'do_nothing',
        'on_right': 'next_timezone'
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
        'default': 1000,
        'min': 0,
        'max': 60000
    },
    'timezones': {
        'type': 'list',
        'default': DEFAULTS['timezones'],
        "schema": {
            'type': 'string',
            'required': False
        }
    },
    'callbacks': {
        'type': 'dict',
        'schema': {
            'on_left': {
                'type': 'string',
                'default': DEFAULTS['callbacks']['on_left'],
            },
            'on_middle': {
                'type': 'string',
                'default': DEFAULTS['callbacks']['on_middle'],
            },
            'on_right': {
                'type': 'string',
                'default': DEFAULTS['callbacks']['on_right'],
            }
        },
        'default': DEFAULTS['callbacks']
    }
}
