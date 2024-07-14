DEFAULTS = {
    'label': "{volume[percent]}%",
    'label_alt': "{volume[percent]}%",
    'volume_icons': [
        "\ueee8",  # Icon for muted
        "\uf026",  # Icon for 0-10% volume
        "\uf027",  # Icon for 11-30% volume
        "\uf027",  # Icon for 31-60% volume
        "\uf028"   # Icon for 61-100% volume
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
    'volume_icons': {
        'type': 'list',
        'default': DEFAULTS['volume_icons'],
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
