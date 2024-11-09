DEFAULTS = {
    'label': "{microphone[percent]}%",
    'label_alt': "{microphone[percent]}%",
    'microphone_icons': [
        "\uf131",  # Icon for muted
        "\uf130",  # Icon for 0-100%
    ],
    'callbacks': {
        'on_middle': 'do_nothing',
        'on_right': 'do_nothing'
    },
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
    'microphone_icons': {
        'type': 'list',
        'default': DEFAULTS['microphone_icons'],
        "schema": {
            'type': 'string',
            'required': False
        }
    },
    'callbacks': {
        'type': 'dict',
        'schema': {
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
