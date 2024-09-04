DEFAULTS = {
    'icon_size': 16,
    'ignore_apps': {
        'classes': [],
        'processes': [],
        'titles': []
    },
}

VALIDATION_SCHEMA = {
    'icon_size': {
        'type': 'integer',
        'default': DEFAULTS['icon_size']
    },
    'ignore_apps': {
        'type': 'dict',
        'schema': {
            'classes': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                },
                'default': DEFAULTS['ignore_apps']['classes']
            },
            'processes': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                },
                'default': DEFAULTS['ignore_apps']['processes']
            },
            'titles': {
                'type': 'list',
                'schema': {
                    'type': 'string'
                },
                'default': DEFAULTS['ignore_apps']['titles']
            }
        },
        'default': DEFAULTS['ignore_apps']
    },
}